"""Unit tests for P0 core model changes (v6 methodology).

Tests:
  WP-1:  Policy pillar binding constraint architecture
  WP-2:  Private credit decorrelation pipeline
  WP-3:  VRP time-varying estimation
  WP-4:  Breach interaction penalty derivation
  WP-12: Inflation proxy chain
"""

import math
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grri_mac.pillars.policy import PolicyPillar, PolicyIndicators, PolicyScores
from grri_mac.pillars.volatility import VolatilityPillar, VolatilityIndicators
from grri_mac.pillars.private_credit_decorrelation import (
    PrivateCreditDecorrelator,
    DecorrelationTimeSeries,
    blend_decorrelated_with_sloos,
)
from grri_mac.historical.inflation_proxies import (
    get_inflation_for_date,
    get_inflation_proxy_chain_name,
)


def _approx(a: float, b: float, tol: float = 0.05) -> bool:
    """Check approximate equality."""
    return abs(a - b) <= tol


# ═══════════════════════════════════════════════════════════════════════════
# WP-1: Policy Pillar — Binding Constraint Architecture
# ═══════════════════════════════════════════════════════════════════════════

class TestPolicyBindingConstraint:

    def setup(self):
        self.pillar = PolicyPillar()

    def test_min_function_high_dispersion(self):
        """When one dimension is severely constrained, min() should bind."""
        indicators = PolicyIndicators(
            policy_room_bps=200,              # Ample → ~1.0
            fed_balance_sheet_gdp_pct=20,     # Ample → ~1.0
            core_pce_vs_target_bps=250,       # Well above target → low score
            debt_to_gdp_pct=60,               # Ample
        )
        scores = self.pillar.calculate(indicators)
        # Inflation score should be very low (~0.0), binding via min()
        assert scores.composite_method == "min", f"Expected min, got {scores.composite_method}"
        assert scores.composite < 0.2, f"Expected < 0.2, got {scores.composite:.3f}"
        print(f"  [PASS] High dispersion → min() binds: composite={scores.composite:.3f}")

    def test_weighted_avg_low_dispersion(self):
        """When all dimensions similarly tight, weighted average applies."""
        indicators = PolicyIndicators(
            policy_room_bps=80,               # Moderate → ~0.65
            fed_balance_sheet_gdp_pct=30,     # Moderate → ~0.75
            core_pce_vs_target_bps=80,        # Moderate above → ~0.6
            debt_to_gdp_pct=80,               # Moderate → ~0.7
        )
        scores = self.pillar.calculate(indicators)
        # All scores close together → weighted average
        assert scores.composite_method == "weighted_avg", (
            f"Expected weighted_avg, got {scores.composite_method}"
        )
        assert 0.4 < scores.composite < 0.8, f"Expected 0.4-0.8, got {scores.composite:.3f}"
        print(f"  [PASS] Low dispersion → weighted avg: composite={scores.composite:.3f}")

    def test_asymmetric_inflation_above(self):
        """Above-target inflation should be penalised more heavily."""
        above = self.pillar.score_inflation(150)   # +150 bps above target
        below = self.pillar.score_inflation(-150)  # −150 bps below target
        assert above < below, f"Above ({above:.3f}) should score worse than below ({below:.3f})"
        print(f"  [PASS] Asymmetric inflation: above={above:.3f} < below={below:.3f}")

    def test_era_cap_pre_fed(self):
        """Pre-Fed era should cap policy at 0.30."""
        indicators = PolicyIndicators(
            policy_room_bps=300,
            core_pce_vs_target_bps=0,
            observation_date=datetime(1910, 1, 1),
        )
        scores = self.pillar.calculate(indicators)
        assert scores.composite <= 0.30 + 0.01, f"Pre-Fed cap: {scores.composite:.3f} > 0.30"
        assert scores.era_cap_applied == 0.30
        print(f"  [PASS] Pre-Fed era cap: composite={scores.composite:.3f}")

    def test_era_cap_early_fed(self):
        """Early Fed/Gold Standard era should cap at 0.55."""
        indicators = PolicyIndicators(
            policy_room_bps=300,
            core_pce_vs_target_bps=0,
            observation_date=datetime(1925, 6, 1),
        )
        scores = self.pillar.calculate(indicators)
        assert scores.composite <= 0.55 + 0.01, f"Early Fed cap: {scores.composite:.3f} > 0.55"
        print(f"  [PASS] Early Fed era cap: composite={scores.composite:.3f}")

    def test_era_cap_bretton_woods(self):
        """Bretton Woods era should cap at 0.65."""
        indicators = PolicyIndicators(
            policy_room_bps=400,
            core_pce_vs_target_bps=0,
            observation_date=datetime(1960, 6, 1),
        )
        scores = self.pillar.calculate(indicators)
        assert scores.composite <= 0.65 + 0.01, f"BW cap: {scores.composite:.3f} > 0.65"
        print(f"  [PASS] Bretton Woods era cap: composite={scores.composite:.3f}")

    def test_gold_constraint_severe(self):
        """Gold reserve ratio < 40% should severely constrain."""
        indicators = PolicyIndicators(
            policy_room_bps=200,
            core_pce_vs_target_bps=50,
            observation_date=datetime(1931, 9, 1),
            gold_reserve_ratio=0.35,
        )
        scores = self.pillar.calculate(indicators)
        assert scores.composite <= 0.15 + 0.01, f"Gold constraint: {scores.composite:.3f}"
        print(f"  [PASS] Gold constraint (severe): composite={scores.composite:.3f}")

    def test_covid_2020_approximate(self):
        """COVID 2020: rate room ~0, huge B/S → should yield ~0.25."""
        indicators = PolicyIndicators(
            policy_room_bps=15,               # Near ZLB
            fed_balance_sheet_gdp_pct=35,     # ~35% in mid-2020
            core_pce_vs_target_bps=-50,       # Below target (deflationary)
            debt_to_gdp_pct=130,              # Above 120% by mid-2020
        )
        scores = self.pillar.calculate(indicators)
        # Expect in neighborhood of 0.25 (policy room ~0 should bind)
        assert scores.composite < 0.35, f"COVID: expected < 0.35, got {scores.composite:.3f}"
        print(f"  [PASS] COVID 2020 proxy: composite={scores.composite:.3f}")

    def test_svb_2023_approximate(self):
        """SVB 2023: rate room OK but inflation very high → should bind low."""
        indicators = PolicyIndicators(
            policy_room_bps=475,              # Fed funds ~4.75%
            fed_balance_sheet_gdp_pct=33,     # Declining from peak
            core_pce_vs_target_bps=280,       # Core PCE ~4.8% → +280 bps
            debt_to_gdp_pct=120,              # High
        )
        scores = self.pillar.calculate(indicators)
        # Inflation should bind → composite low
        assert scores.composite < 0.30, f"SVB: expected < 0.30, got {scores.composite:.3f}"
        print(f"  [PASS] SVB 2023 proxy: composite={scores.composite:.3f}")

    def run_all(self):
        self.setup()
        print("\n=== WP-1: Policy Pillar Binding Constraint ===")
        self.test_min_function_high_dispersion()
        self.test_weighted_avg_low_dispersion()
        self.test_asymmetric_inflation_above()
        self.test_era_cap_pre_fed()
        self.test_era_cap_early_fed()
        self.test_era_cap_bretton_woods()
        self.test_gold_constraint_severe()
        self.test_covid_2020_approximate()
        self.test_svb_2023_approximate()


# ═══════════════════════════════════════════════════════════════════════════
# WP-3: VRP Time-Varying Estimation
# ═══════════════════════════════════════════════════════════════════════════

class TestVRPEstimation:

    def setup(self):
        self.pillar = VolatilityPillar()

    def test_vrp_stable_regime(self):
        """Low vol-of-vol → VRP near floor (1.05)."""
        # Simulate stable VIX around 18 for 252 days
        import random
        random.seed(42)
        vix_hist = [18 + random.gauss(0, 0.5) for _ in range(252)]
        vrp = self.pillar.calculate_vrp(vix_hist)
        assert vrp.vrp_multiplier < 1.15, f"Stable VRP too high: {vrp.vrp_multiplier:.3f}"
        assert vrp.data_quality == "good"
        print(f"  [PASS] Stable regime VRP: {vrp.vrp_multiplier:.3f}")

    def test_vrp_volatile_regime(self):
        """High vol-of-vol → VRP elevated."""
        import random
        random.seed(42)
        # Simulate volatile VIX with large daily swings
        vix_hist = [25 + random.gauss(0, 5.0) for _ in range(252)]
        vrp = self.pillar.calculate_vrp(vix_hist)
        assert vrp.vrp_multiplier > 1.10, f"Volatile VRP too low: {vrp.vrp_multiplier:.3f}"
        assert vrp.vrp_multiplier <= 1.55, f"VRP exceeded ceiling: {vrp.vrp_multiplier:.3f}"
        print(f"  [PASS] Volatile regime VRP: {vrp.vrp_multiplier:.3f}")

    def test_vrp_floor_ceiling(self):
        """VRP should always be in [1.05, 1.55]."""
        # Very stable
        vix_const = [20.0] * 252
        vrp_low = self.pillar.calculate_vrp(vix_const)
        assert vrp_low.vrp_multiplier >= 1.05

        # Extremely volatile
        import random
        random.seed(99)
        vix_wild = [30 + random.gauss(0, 20.0) for _ in range(252)]
        vrp_high = self.pillar.calculate_vrp(vix_wild)
        assert vrp_high.vrp_multiplier <= 1.55
        print(f"  [PASS] VRP bounds: [{vrp_low.vrp_multiplier:.3f}, {vrp_high.vrp_multiplier:.3f}]")

    def test_vrp_insufficient_data(self):
        """Too little data → insufficient quality."""
        vrp = self.pillar.calculate_vrp([18, 19, 20])
        assert vrp.data_quality == "insufficient"
        print(f"  [PASS] Insufficient data handled correctly")

    def test_dual_computation(self):
        """Calculate should produce both with- and without-VRP scores."""
        import random
        random.seed(42)
        vix_hist = [25 + random.gauss(0, 3.0) for _ in range(252)]
        indicators = VolatilityIndicators(
            vix_level=25,
            vix_history=vix_hist,
        )
        scores = self.pillar.calculate(indicators, apply_vrp=True)
        assert scores.vrp is not None
        assert scores.vrp.score_without_vrp != 0.5 or scores.vrp.score_with_vrp != 0.5
        print(f"  [PASS] Dual computation: without={scores.vrp.score_without_vrp:.3f}, "
              f"with={scores.vrp.score_with_vrp:.3f}, "
              f"divergence={scores.vrp.divergence:.3f}")

    def run_all(self):
        self.setup()
        print("\n=== WP-3: VRP Time-Varying Estimation ===")
        self.test_vrp_stable_regime()
        self.test_vrp_volatile_regime()
        self.test_vrp_floor_ceiling()
        self.test_vrp_insufficient_data()
        self.test_dual_computation()


# ═══════════════════════════════════════════════════════════════════════════
# WP-2: Private Credit Decorrelation
# ═══════════════════════════════════════════════════════════════════════════

class TestDecorrelation:

    def setup(self):
        self.decorrelator = PrivateCreditDecorrelator()

    def _make_synthetic_data(self, n=252, signal_strength=0.0):
        """Generate synthetic data: BDC = β·SPX + β·VIX + ε + signal.
        
        signal_strength: additional private-credit-specific shock in σ units
        """
        import random
        random.seed(42)

        ts = DecorrelationTimeSeries()
        for i in range(n):
            spx = random.gauss(0, 1.0)
            vix = random.gauss(0, 2.0)
            hy_oas = random.gauss(0, 0.5)
            noise = random.gauss(0, 0.3)

            # BDC return = factor exposure + private-credit-specific signal
            bdc = 0.6 * spx - 0.3 * vix + 0.2 * hy_oas + noise
            # Inject a negative PC-specific shock in the last 60 days
            if i >= n - 60 and signal_strength != 0:
                bdc += signal_strength * 0.3  # Scale by residual σ

            ts.bdc_returns.append(bdc)
            ts.spx_returns.append(spx)
            ts.vix_changes.append(vix)
            ts.hy_oas_changes.append(hy_oas)

        return ts

    def test_no_pc_signal(self):
        """Without PC-specific stress, decorrelated score should be neutral."""
        ts = self._make_synthetic_data(signal_strength=0.0)
        result = self.decorrelator.decorrelate(ts)
        assert result.data_quality == "good"
        assert result.decorrelated_score is not None
        # Should be roughly neutral (0.5-0.9)
        assert result.decorrelated_score > 0.3, (
            f"False alarm: score {result.decorrelated_score:.3f} with no signal"
        )
        print(f"  [PASS] No PC signal → neutral: score={result.decorrelated_score:.3f}, "
              f"z={result.ewma_z:.3f}")

    def test_negative_pc_signal(self):
        """With PC-specific stress, decorrelated score should drop."""
        ts = self._make_synthetic_data(signal_strength=-3.0)
        result = self.decorrelator.decorrelate(ts)
        assert result.data_quality == "good"
        assert result.ewma_z < -0.5, f"Expected z < -0.5, got {result.ewma_z:.3f}"
        assert result.decorrelated_score < 0.5, (
            f"Expected score < 0.5, got {result.decorrelated_score:.3f}"
        )
        print(f"  [PASS] Negative PC signal → stress: score={result.decorrelated_score:.3f}, "
              f"z={result.ewma_z:.3f}")

    def test_ols_recovers_betas(self):
        """OLS should approximately recover the true factor betas."""
        ts = self._make_synthetic_data(n=500, signal_strength=0.0)
        result = self.decorrelator.decorrelate(ts)
        # True betas: SPX=0.6, VIX=-0.3, HY_OAS=0.2
        assert result.beta_spx is not None
        assert abs(result.beta_spx - 0.6) < 0.15, f"SPX beta: {result.beta_spx:.3f}"
        assert abs(result.beta_vix - (-0.3)) < 0.15, f"VIX beta: {result.beta_vix:.3f}"
        print(f"  [PASS] OLS betas: SPX={result.beta_spx:.3f}, VIX={result.beta_vix:.3f}, "
              f"HY={result.beta_hy_oas:.3f}")

    def test_insufficient_data(self):
        """Too little data → insufficient."""
        ts = DecorrelationTimeSeries()
        for _ in range(10):
            ts.bdc_returns.append(0.01)
            ts.spx_returns.append(0.01)
            ts.vix_changes.append(0.0)
            ts.hy_oas_changes.append(0.0)
        result = self.decorrelator.decorrelate(ts)
        assert result.data_quality == "insufficient"
        print(f"  [PASS] Insufficient data handled correctly")

    def test_blend_with_sloos(self):
        """Blend should be 60/40 with good data, 100% SLOOS with bad."""
        # Good quality
        blended = blend_decorrelated_with_sloos(0.3, 0.7, "good")
        expected = 0.60 * 0.3 + 0.40 * 0.7  # 0.46
        assert _approx(blended, expected, 0.01)

        # Insufficient → 100% SLOOS
        fallback = blend_decorrelated_with_sloos(0.3, 0.7, "insufficient")
        assert _approx(fallback, 0.7, 0.01)

        # Partial → 40/60 blend
        partial = blend_decorrelated_with_sloos(0.3, 0.7, "partial")
        expected_partial = 0.40 * 0.3 + 0.60 * 0.7  # 0.54
        assert _approx(partial, expected_partial, 0.01)

        print(f"  [PASS] Blend: good={blended:.3f}, insufficient={fallback:.3f}, "
              f"partial={partial:.3f}")

    def run_all(self):
        self.setup()
        print("\n=== WP-2: Private Credit Decorrelation ===")
        self.test_no_pc_signal()
        self.test_negative_pc_signal()
        self.test_ols_recovers_betas()
        self.test_insufficient_data()
        self.test_blend_with_sloos()


# ═══════════════════════════════════════════════════════════════════════════
# WP-12: Inflation Proxy Chain
# ═══════════════════════════════════════════════════════════════════════════

class TestInflationProxyChain:

    def test_proxy_chain_names(self):
        """Each era should map to the correct proxy source."""
        assert "Core PCE" in get_inflation_proxy_chain_name(datetime(2024, 1, 1))
        assert "CPI-U" in get_inflation_proxy_chain_name(datetime(1955, 6, 1))
        assert "CPI NSA" in get_inflation_proxy_chain_name(datetime(1930, 1, 1))
        assert "Rees" in get_inflation_proxy_chain_name(datetime(1900, 1, 1))
        assert "Warren-Pearson" in get_inflation_proxy_chain_name(datetime(1870, 1, 1))
        assert "No proxy" in get_inflation_proxy_chain_name(datetime(1840, 1, 1))
        print(f"  [PASS] Proxy chain names correct across all eras")

    def test_rees_data_available(self):
        """Rees cost of living should return data for 1890-1913."""
        val = get_inflation_for_date(datetime(1900, 6, 1))
        assert val is not None, "Rees data missing for 1900"
        # 1900 had ~2.5% inflation, target 2% → deviation +50 bps
        assert isinstance(val, float)
        print(f"  [PASS] Rees 1900 deviation: {val:.0f} bps")

    def test_warren_pearson_available(self):
        """Warren-Pearson WPI should return data for 1850-1890."""
        val = get_inflation_for_date(datetime(1863, 1, 1))
        assert val is not None, "W-P data missing for 1863"
        # Civil War 1863: high inflation → large positive deviation
        assert val > 0, f"Expected positive deviation during Civil War, got {val:.0f}"
        print(f"  [PASS] Warren-Pearson 1863 (Civil War): {val:.0f} bps")

    def test_deflation_negative(self):
        """1870s Long Deflation should show negative deviation."""
        val = get_inflation_for_date(datetime(1878, 1, 1))
        assert val is not None
        assert val < -200, f"Expected strong deflation in 1878, got {val:.0f} bps"
        print(f"  [PASS] 1878 deflation: {val:.0f} bps")

    def test_no_data_before_1850(self):
        """Before 1850 should return None."""
        val = get_inflation_for_date(datetime(1840, 1, 1))
        assert val is None
        print(f"  [PASS] No data before 1850")

    def run_all(self):
        print("\n=== WP-12: Inflation Proxy Chain ===")
        self.test_proxy_chain_names()
        self.test_rees_data_available()
        self.test_warren_pearson_available()
        self.test_deflation_negative()
        self.test_no_data_before_1850()


# ═══════════════════════════════════════════════════════════════════════════
# WP-4: Breach Interaction Penalty Derivation
# ═══════════════════════════════════════════════════════════════════════════

class TestBreachPenaltyDerivation:

    def test_derivation_matches_table(self):
        """Derived penalties should match the hardcoded table."""
        from grri_mac.mac.composite import (
            derive_breach_interaction_penalties,
            BREACH_INTERACTION_PENALTY,
        )
        derived = derive_breach_interaction_penalties()
        for n_breach, penalty in BREACH_INTERACTION_PENALTY.items():
            assert n_breach in derived, f"Missing n={n_breach} in derived"
            assert _approx(derived[n_breach], penalty, 0.02), (
                f"n={n_breach}: derived {derived[n_breach]:.4f} ≠ table {penalty}"
            )
        print(f"  [PASS] Derived penalties match hardcoded table")

    def test_sensitivity(self):
        """Penalties should be robust to ±10% perturbation."""
        from grri_mac.mac.composite import validate_breach_penalty_sensitivity
        result = validate_breach_penalty_sensitivity()
        assert result["all_within_tolerance"], (
            f"Breach penalties not robust: {result['max_deviations']}"
        )
        print(f"  [PASS] Penalties robust to perturbation")

    def run_all(self):
        print("\n=== WP-4: Breach Interaction Penalty Derivation ===")
        self.test_derivation_matches_table()
        self.test_sensitivity()


# ═══════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("P0 UNIT TESTS — v6 Core Model Changes")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = []

    test_suites = [
        TestPolicyBindingConstraint(),
        TestVRPEstimation(),
        TestDecorrelation(),
        TestInflationProxyChain(),
        TestBreachPenaltyDerivation(),
    ]

    for suite in test_suites:
        try:
            suite.run_all()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append(f"{suite.__class__.__name__}: {e}")
        except Exception as e:
            failed += 1
            errors.append(f"{suite.__class__.__name__}: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    if errors:
        print(f"RESULTS: {len(test_suites) - len(errors)} suites passed, {len(errors)} failed")
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print(f"ALL {len(test_suites)} TEST SUITES PASSED")
    print("=" * 60)

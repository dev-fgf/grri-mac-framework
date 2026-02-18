"""Tests for P1 work packages: WP-5 (CSR) and WP-6 (Thematic Holdout).

Covers:
  - CSR dimension scoring functions
  - CSR composite calculation
  - CSR data integrity for all 14 scenarios
  - Calibration CSR-anchoring
  - Thematic holdout set definitions
  - Thematic holdout validation logic
"""

import unittest
from datetime import datetime

# ---------------------------------------------------------------------------
# WP-5: Crisis Severity Rubric
# ---------------------------------------------------------------------------

from grri_mac.backtest.scenarios import (
    HistoricalScenario,
    CrisisSeverityScores,
    KNOWN_EVENTS,
)
from grri_mac.backtest.crisis_severity_rubric import (
    CSRInput,
    MarketDysfunction,
    PolicyResponse,
    ContagionBreadth,
    calculate_csr,
    score_drawdown,
    score_duration,
    score_market_dysfunction,
    score_policy_response,
    score_contagion_breadth,
    validate_csr_independence,
)
from grri_mac.backtest.calibration import CalibrationValidator
from grri_mac.backtest.thematic_holdout import (
    HOLDOUT_SETS,
    ANCHOR_SCENARIOS,
    HoldoutResult,
    ThematicHoldoutReport,
    run_thematic_holdout_validation,
    diagnose_holdout_failure,
    format_holdout_report,
)


class TestCSRDimensionScoring(unittest.TestCase):
    """Test individual CSR dimension scoring functions."""

    # -- Dimension 1: Drawdown --
    def test_drawdown_orderly(self):
        self.assertEqual(score_drawdown(3.0), 0.90)

    def test_drawdown_correction(self):
        self.assertEqual(score_drawdown(7.0), 0.70)

    def test_drawdown_significant(self):
        self.assertEqual(score_drawdown(15.0), 0.45)

    def test_drawdown_severe(self):
        self.assertEqual(score_drawdown(25.0), 0.25)

    def test_drawdown_systemic(self):
        self.assertEqual(score_drawdown(50.0), 0.10)

    def test_drawdown_negative_input(self):
        """Negative drawdown is treated as absolute."""
        self.assertEqual(score_drawdown(-30.0), 0.25)

    # -- Dimension 2: Market dysfunction --
    def test_dysfunction_none(self):
        val = score_market_dysfunction(MarketDysfunction.NONE)
        self.assertEqual(val, 0.90)

    def test_dysfunction_extreme(self):
        val = score_market_dysfunction(
            MarketDysfunction.EXTREME,
        )
        self.assertEqual(val, 0.10)

    # -- Dimension 3: Policy response --
    def test_policy_none(self):
        self.assertEqual(score_policy_response(PolicyResponse.NONE), 0.90)

    def test_policy_unlimited(self):
        self.assertEqual(score_policy_response(PolicyResponse.UNLIMITED), 0.10)

    # -- Dimension 4: Contagion breadth --
    def test_contagion_single(self):
        val = score_contagion_breadth(
            ContagionBreadth.SINGLE,
        )
        self.assertEqual(val, 0.85)

    def test_contagion_global(self):
        val = score_contagion_breadth(
            ContagionBreadth.GLOBAL_SYSTEMIC,
        )
        self.assertEqual(val, 0.10)

    # -- Dimension 5: Duration --
    def test_duration_flash(self):
        self.assertEqual(score_duration(3), 0.85)

    def test_duration_short(self):
        self.assertEqual(score_duration(10), 0.60)

    def test_duration_extended(self):
        self.assertEqual(score_duration(30), 0.40)

    def test_duration_prolonged(self):
        self.assertEqual(score_duration(60), 0.20)

    def test_duration_structural(self):
        self.assertEqual(score_duration(120), 0.10)


class TestCSRComposite(unittest.TestCase):
    """Test CSR composite calculation and helper properties."""

    def test_lehman_csr(self):
        """Lehman should score 0.10 — all dimensions at minimum."""
        inp = CSRInput(
            drawdown_pct=50.0,
            dysfunction=MarketDysfunction.EXTREME,
            policy=PolicyResponse.UNLIMITED,
            contagion=ContagionBreadth.GLOBAL_SYSTEMIC,
            duration_trading_days=120,
        )
        result = calculate_csr(inp)
        self.assertAlmostEqual(result.composite, 0.10, places=2)
        self.assertEqual(result.severity_label, "Extreme")

    def test_flash_crash_csr(self):
        """Flash Crash — moderate event, high composite."""
        inp = CSRInput(
            drawdown_pct=7.0,
            dysfunction=MarketDysfunction.MODERATE,
            policy=PolicyResponse.NONE,
            contagion=ContagionBreadth.SINGLE,
            duration_trading_days=3,
        )
        result = calculate_csr(inp)
        self.assertGreater(result.composite, 0.70)
        self.assertEqual(result.severity_label, "Moderate")

    def test_expected_range(self):
        """Expected MAC range is CSR ± 0.10."""
        scores = CrisisSeverityScores(0.45, 0.55, 0.20, 0.30, 0.40)
        lo, hi = scores.expected_mac_range
        self.assertAlmostEqual(lo, scores.composite - 0.10, places=6)
        self.assertAlmostEqual(hi, scores.composite + 0.10, places=6)

    def test_expected_range_clamp(self):
        """Range should not exceed [0, 1]."""
        # Very high composite
        scores = CrisisSeverityScores(0.95, 0.95, 0.95, 0.95, 0.95)
        _, hi = scores.expected_mac_range
        self.assertLessEqual(hi, 1.0)
        # Very low composite
        scores_low = CrisisSeverityScores(0.02, 0.02, 0.02, 0.02, 0.02)
        lo, _ = scores_low.expected_mac_range
        self.assertGreaterEqual(lo, 0.0)


class TestCSRScenarioData(unittest.TestCase):
    """Verify CSR data integrity for all 14 modern scenarios."""

    def test_all_scenarios_have_csr(self):
        """Every scenario in KNOWN_EVENTS must have a CSR."""
        for key, scenario in KNOWN_EVENTS.items():
            self.assertIsNotNone(
                scenario.csr,
                f"Scenario {key} is missing CSR scores",
            )

    def test_csr_composites_match_v6_table(self):
        """CSR composites should match §13.2.4 table values."""
        expected = {
            "ltcm_crisis_1998": 0.38,
            "dotcom_peak_2000": 0.73,
            "sept11_2001": 0.47,
            "dotcom_bottom_2002": 0.45,
            "bear_stearns_2008": 0.43,
            "lehman_2008": 0.10,
            "flash_crash_2010": 0.77,
            "us_downgrade_2011": 0.53,
            "volmageddon_2018": 0.72,
            "repo_spike_2019": 0.60,
            "covid_crash_2020": 0.12,
            "ukraine_invasion_2022": 0.64,
            "svb_crisis_2023": 0.56,
            "april_tariffs_2025": 0.48,
        }
        for key, expected_csr in expected.items():
            scenario = KNOWN_EVENTS[key]
            self.assertAlmostEqual(
                scenario.csr.composite,
                expected_csr,
                places=2,
                msg=(
                    f"{key}: CSR composite "
                    f"{scenario.csr.composite:.3f}"
                    f" != {expected_csr}"
                ),
            )

    def test_severity_labels_match_v6(self):
        """Legacy severity labels (§13.2.5) should map correctly."""
        extreme = ["ltcm_crisis_1998", "lehman_2008", "covid_crash_2020"]
        for key in extreme:
            csr = KNOWN_EVENTS[key].csr.composite
            self.assertLess(
                csr, 0.40,
                f"{key} should be Extreme (CSR={csr:.2f})",
            )

        moderate = [
            "dotcom_peak_2000", "flash_crash_2010", "volmageddon_2018",
            "repo_spike_2019", "ukraine_invasion_2022",
        ]
        for key in moderate:
            csr = KNOWN_EVENTS[key].csr.composite
            self.assertGreaterEqual(
                csr, 0.55,
                f"{key} Moderate (CSR={csr:.2f})",
            )

    def test_csr_dimension_range(self):
        """All CSR sub-scores should be in [0.10, 0.90]."""
        for key, scenario in KNOWN_EVENTS.items():
            for dim in ["drawdown", "mkt_dysfunction", "policy_response",
                        "contagion", "duration"]:
                val = getattr(scenario.csr, dim)
                self.assertGreaterEqual(
                    val, 0.10, f"{key}.{dim}={val} below minimum"
                )
                self.assertLessEqual(
                    val, 0.90, f"{key}.{dim}={val} above maximum"
                )


class TestCalibrationCSRAnchoring(unittest.TestCase):
    """Test that calibration uses CSR targets correctly."""

    def test_target_score_uses_csr(self):
        """_target_score prefers CSR over expected_mac_range."""
        scenario = KNOWN_EVENTS["lehman_2008"]
        target = CalibrationValidator._target_score(scenario)
        self.assertAlmostEqual(target, 0.10, places=2)

    def test_target_score_fallback(self):
        """_target_score falls back to expected_mac_range when no CSR."""
        scenario = HistoricalScenario(
            name="Test",
            date=datetime(2020, 1, 1),
            description="...",
            expected_mac_range=(0.30, 0.50),
            expected_breaches=[],
            treasury_hedge_worked=True,
            csr=None,  # No CSR
        )
        target = CalibrationValidator._target_score(scenario)
        self.assertEqual(target, 0.30)

    def test_csr_composite_accessor(self):
        """HistoricalScenario.csr_composite convenience property."""
        scenario = KNOWN_EVENTS["flash_crash_2010"]
        self.assertAlmostEqual(scenario.csr_composite, 0.77, places=2)

    def test_csr_composite_none_when_missing(self):
        """csr_composite returns None when CSR is absent."""
        scenario = HistoricalScenario(
            name="Test",
            date=datetime(2020, 1, 1),
            description="...",
            expected_mac_range=(0.30, 0.50),
            expected_breaches=[],
            treasury_hedge_worked=True,
        )
        self.assertIsNone(scenario.csr_composite)


class TestCSRIndependence(unittest.TestCase):
    """Test CSR independence documentation."""

    def test_independence_verification(self):
        info = validate_csr_independence()
        self.assertIn("independence_statement", info)
        self.assertIn("drawdown", info)
        self.assertIn("duration", info)


# ---------------------------------------------------------------------------
# WP-6: Thematic Holdout Validation
# ---------------------------------------------------------------------------

class TestHoldoutSetDefinitions(unittest.TestCase):
    """Test holdout set structure and coverage."""

    def test_five_holdout_sets(self):
        self.assertEqual(len(HOLDOUT_SETS), 5)
        self.assertEqual(set(HOLDOUT_SETS.keys()), {"A", "B", "C", "D", "E"})

    def test_all_holdout_scenarios_exist(self):
        """Every scenario key in holdout sets must exist in KNOWN_EVENTS."""
        for hk, hdef in HOLDOUT_SETS.items():
            for key in hdef["held_out"]:
                self.assertIn(
                    key, KNOWN_EVENTS,
                    f"Holdout {hk} references unknown scenario: {key}",
                )

    def test_holdout_sizes(self):
        """Sets A–D have 3 each; set E has 4."""
        for hk in ["A", "B", "C", "D"]:
            self.assertEqual(
                len(HOLDOUT_SETS[hk]["held_out"]), 3,
                f"Holdout {hk} should have 3 scenarios",
            )
        self.assertEqual(len(HOLDOUT_SETS["E"]["held_out"]), 4)

    def test_every_scenario_in_at_least_one_holdout(self):
        """Every scenario appears in ≥1 holdout OR is an anchor (§13.4.4)."""
        held_out_ever = set()
        for hdef in HOLDOUT_SETS.values():
            held_out_ever.update(hdef["held_out"])
        all_keys = set(KNOWN_EVENTS.keys())
        never_held_out = all_keys - held_out_ever
        self.assertTrue(
            never_held_out.issubset(ANCHOR_SCENARIOS),
            f"Scenarios not in any holdout and not anchors: "
            f"{never_held_out - ANCHOR_SCENARIOS}",
        )

    def test_anchor_scenarios_never_held_out(self):
        """Anchor scenarios must not appear in any holdout set."""
        for hdef in HOLDOUT_SETS.values():
            for key in hdef["held_out"]:
                self.assertNotIn(
                    key, ANCHOR_SCENARIOS,
                    f"Anchor {key} should not be in a holdout set",
                )

    def test_holdout_themes_present(self):
        """Each holdout set has a theme and thesis."""
        for hk, hdef in HOLDOUT_SETS.items():
            self.assertIn("theme", hdef)
            self.assertIn("thesis", hdef)
            self.assertTrue(len(hdef["theme"]) > 0)


class TestThematicHoldoutValidation(unittest.TestCase):
    """Test holdout validation logic (uses CalibrationValidator)."""

    def test_holdout_report_structure(self):
        """run_thematic_holdout_validation returns well-formed report."""
        report = run_thematic_holdout_validation(full_alpha=0.78)
        self.assertIsInstance(report, ThematicHoldoutReport)
        self.assertEqual(report.alpha_full, 0.78)
        self.assertEqual(len(report.holdout_results), 5)
        for hk in ["A", "B", "C", "D", "E"]:
            self.assertIn(hk, report.holdout_results)
            r = report.holdout_results[hk]
            self.assertIsInstance(r, HoldoutResult)
            self.assertGreater(r.n_train, 0)
            self.assertGreater(r.n_test, 0)
            self.assertGreater(r.alpha_train, 0.0)

    def test_acceptance_criteria_present(self):
        """Report includes all four acceptance criteria."""
        report = run_thematic_holdout_validation(full_alpha=0.78)
        expected_criteria = {
            "delta_alpha_all_below_0.05",
            "oos_mae_all_below_0.15",
            "alpha_range_below_0.08",
            "mean_oos_mae_below_0.12",
        }
        self.assertEqual(set(report.acceptance.keys()), expected_criteria)

    def test_alpha_range_consistent(self):
        """α range matches max-min of per-holdout alphas."""
        report = run_thematic_holdout_validation(full_alpha=0.78)
        alphas = [r.alpha_train for r in report.holdout_results.values()]
        self.assertAlmostEqual(
            report.alpha_range, max(alphas) - min(alphas), places=6
        )

    def test_holdout_train_test_partition(self):
        """Train + test sizes should equal 14 total scenarios."""
        report = run_thematic_holdout_validation(full_alpha=0.78)
        for hk, r in report.holdout_results.items():
            self.assertEqual(
                r.n_train + r.n_test, 14,
                f"Holdout {hk}: train({r.n_train})+test({r.n_test}) != 14",
            )

    def test_format_report(self):
        """format_holdout_report produces non-empty string."""
        report = run_thematic_holdout_validation(full_alpha=0.78)
        text = format_holdout_report(report)
        self.assertIn("THEMATIC HOLDOUT", text)
        self.assertIn("ACCEPTANCE CRITERIA", text)

    def test_diagnose_returns_list(self):
        """diagnose_holdout_failure always returns a list of strings."""
        report = run_thematic_holdout_validation(full_alpha=0.78)
        diagnostics = diagnose_holdout_failure(report)
        self.assertIsInstance(diagnostics, list)
        self.assertTrue(all(isinstance(d, str) for d in diagnostics))


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

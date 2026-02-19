"""Tests for P1 work packages: WP-7, WP-9, WP-10, WP-11.

Covers:
  WP-7:  Precision-recall framework
  WP-9:  SVAR cascade estimation
  WP-10: Sovereign bond proxy
  WP-11: Backtest enhancements
"""

import json
import math
import unittest
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np

# ---------------------------------------------------------------------------
# WP-7: Precision-Recall Framework
# ---------------------------------------------------------------------------

from grri_mac.backtest.precision_recall import (
    ClientArchetype,
    FPCategory,
    PRPoint,
    STANDARD_OPERATING_POINTS,
    build_crisis_windows,
    compute_precision_recall_curve,
    optimal_threshold_for_beta,
    breakeven_precision,
    format_precision_recall_report,
    export_precision_recall_json,
    _f_beta,
    _classify_fp,
    _is_in_any_window,
)

# ---------------------------------------------------------------------------
# WP-9: SVAR Cascade Estimation
# ---------------------------------------------------------------------------

from grri_mac.predictive.cascade_var import (
    CHOLESKY_ORDERING,
    CRITICAL_THRESHOLDS,
    CIRF_HORIZON,
    MAC_STRESS_THRESHOLD,
    SVAREstimate,
    RobustnessResult,
    AccelerationFactors,
    GrangerResult,
    CascadeVARReport,
    estimate_var,
    select_lag_order,
    compute_irf,
    compute_girf,
    normalise_matrix,
    estimate_svar,
    robustness_all_orderings,
    estimate_acceleration_factors,
    granger_causality_tests,
    transmission_matrix_to_dict,
    update_interaction_matrix,
    format_svar_report,
    run_svar_pipeline,
    _f_test_p_value,
)

# ---------------------------------------------------------------------------
# WP-10: Sovereign Bond Proxy
# ---------------------------------------------------------------------------

from grri_mac.historical.sovereign_proxy import (
    BenchmarkEra,
    QuadraticCoefficients,
    SovereignSpreadObservation,
    SovereignProxyMAC,
    HistoricalStressEpisode,
    DEFAULT_COEFFICIENTS,
    UK_STRESS_EPISODES,
    DATA_SOURCES,
    PROXY_LIMITATIONS,
    get_benchmark_era,
    compute_sovereign_spread,
    map_spread_to_mac,
    compute_proxy_mac,
    calibrate_coefficients,
    build_proxy_mac_series,
    format_proxy_mac_report,
)

# ---------------------------------------------------------------------------
# WP-11: Backtest Enhancements (runner.py)
# ---------------------------------------------------------------------------

from grri_mac.backtest.runner import BacktestRunner, BacktestPoint


# ═══════════════════════════════════════════════════════════════════════════
# WP-7 TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestFBeta(unittest.TestCase):
    """Fβ score computation."""

    def test_f1_balanced(self):
        """F1 with perfect precision and recall = 1.0."""
        self.assertAlmostEqual(_f_beta(1.0, 1.0, 1.0), 1.0)

    def test_f1_zero(self):
        """F1 with precision=0 and recall=0 → 0."""
        self.assertEqual(_f_beta(0.0, 0.0, 1.0), 0.0)

    def test_f1_standard(self):
        """F1 = 2PR/(P+R) for known values."""
        p, r = 0.6, 0.8
        expected = 2 * p * r / (p + r)
        self.assertAlmostEqual(_f_beta(p, r, 1.0), expected, places=6)

    def test_f2_weights_recall(self):
        """F2 should weight recall more than F0.5."""
        p, r = 0.4, 0.9
        f2 = _f_beta(p, r, 2.0)
        f05 = _f_beta(p, r, 0.5)
        # F2 weights recall → higher score when recall is high
        self.assertGreater(f2, f05)

    def test_f05_weights_precision(self):
        """F0.5 should weight precision more than F2."""
        p, r = 0.9, 0.3
        f05 = _f_beta(p, r, 0.5)
        f2 = _f_beta(p, r, 2.0)
        self.assertGreater(f05, f2)


class TestCrisisWindows(unittest.TestCase):
    """Crisis window construction."""

    def test_build_crisis_windows(self):
        """Windows have correct start/end offsets."""
        events = [
            ("TestCrisis", datetime(2020, 3, 16)),
        ]
        windows = build_crisis_windows(events)
        self.assertEqual(len(windows), 1)
        w = windows[0]
        self.assertEqual(w.event_name, "TestCrisis")
        self.assertEqual(w.event_date, datetime(2020, 3, 16))
        # ±6 weeks
        expected_start = datetime(2020, 3, 16) - timedelta(weeks=6)
        expected_end = datetime(2020, 3, 16) + timedelta(weeks=6)
        self.assertEqual(w.window_start, expected_start)
        self.assertEqual(w.window_end, expected_end)
        # Lead time = 8 weeks before
        expected_lead = datetime(2020, 3, 16) - timedelta(weeks=8)
        self.assertEqual(w.lead_start, expected_lead)

    def test_is_in_window_inside(self):
        """Date within crisis window is detected."""
        events = [("Crisis", datetime(2020, 6, 1))]
        windows = build_crisis_windows(events)
        # 2 weeks before = inside window
        self.assertTrue(_is_in_any_window(datetime(2020, 5, 18), windows))

    def test_is_in_window_outside(self):
        """Date far from any crisis window is not detected."""
        events = [("Crisis", datetime(2020, 6, 1))]
        windows = build_crisis_windows(events)
        self.assertFalse(_is_in_any_window(datetime(2021, 1, 1), windows))

    def test_lead_time_detection(self):
        """7 weeks before event date is within lead-time window."""
        events = [("Crisis", datetime(2020, 6, 1))]
        windows = build_crisis_windows(events)
        # 7 weeks before — within lead-time but outside ±6w window
        test_date = datetime(2020, 6, 1) - timedelta(weeks=7)
        self.assertTrue(
            _is_in_any_window(
                test_date, windows, include_lead=True,
            )
        )
        self.assertFalse(
            _is_in_any_window(
                test_date, windows, include_lead=False,
            )
        )


class TestFPClassification(unittest.TestCase):
    """False positive taxonomy."""

    def test_pre_1971_is_regime_artefact(self):
        """Pre-1971 dates classified as regime artefact."""
        fp = _classify_fp(datetime(1960, 5, 1), 0.35)
        self.assertEqual(fp.category, FPCategory.REGIME_ARTEFACT)

    def test_near_miss_heuristic(self):
        """MAC 0.35–0.50 outside crisis → near-miss (heuristic)."""
        fp = _classify_fp(datetime(2015, 8, 15), 0.42)
        self.assertEqual(fp.category, FPCategory.NEAR_MISS)

    def test_genuine_fp(self):
        """MAC well below threshold in modern era → genuine FP."""
        fp = _classify_fp(datetime(2017, 3, 1), 0.20)
        self.assertEqual(fp.category, FPCategory.GENUINE)

    def test_near_miss_explicit(self):
        """Explicit near-miss dates list is respected."""
        near_miss = [
            (datetime(2016, 6, 20), datetime(2016, 7, 10), "Brexit vote"),
        ]
        fp = _classify_fp(datetime(2016, 6, 25), 0.30, near_miss)
        self.assertEqual(fp.category, FPCategory.NEAR_MISS)
        self.assertIn("Brexit vote", fp.reason)


class TestPRCurve(unittest.TestCase):
    """Precision-recall curve computation."""

    def setup_method(self, method=None):
        """Generate synthetic weekly data + crisis events for testing."""
        # 200 weeks, 2 crisis events
        base_date = datetime(2020, 1, 1)
        self.crisis_events = [
            ("Crisis1", base_date + timedelta(weeks=50)),
            ("Crisis2", base_date + timedelta(weeks=150)),
        ]
        # Generate MAC scores: mostly 0.65, dip to 0.30 around crises
        self.weekly_data = []
        for i in range(200):
            date = base_date + timedelta(weeks=i)
            # Dip near crises
            if 45 <= i <= 55 or 145 <= i <= 155:
                mac = 0.30
            else:
                mac = 0.65
            self.weekly_data.append({
                "date": date,
                "mac_score": mac,
                "mac_status": "COMFORTABLE" if mac > 0.50 else "STRETCHED",
                "is_deteriorating": mac < 0.40,
            })

    def test_curve_length(self):
        """PR curve has ~71 points (τ 0.10 to 0.80)."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        self.assertGreaterEqual(len(report.curve), 70)

    def test_recall_monotone(self):
        """Recall should be non-decreasing as τ increases."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        recalls = [pt.recall for pt in report.curve]
        for i in range(1, len(recalls)):
            self.assertGreaterEqual(recalls[i], recalls[i - 1] - 1e-9)

    def test_both_crises_detected_at_default(self):
        """Both crises detected at τ=0.50 (MAC dips to 0.30)."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        # Find point closest to τ=0.50
        pt = min(report.curve, key=lambda p: abs(p.tau - 0.50))
        self.assertEqual(pt.tp, 2)
        self.assertEqual(pt.recall, 1.0)

    def test_operating_points_present(self):
        """All 5 standard operating points are reported."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        names = {op.name for op in report.operating_points}
        for name in STANDARD_OPERATING_POINTS:
            self.assertIn(name, names)

    def test_optimal_tau_by_archetype(self):
        """Each client archetype gets a τ* and Fβ*."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        for arch in ClientArchetype:
            self.assertIn(arch.label, report.optimal_tau_by_beta)
            tau_star, fb_star = report.optimal_tau_by_beta[arch.label]
            self.assertGreaterEqual(tau_star, 0.10)
            self.assertLessEqual(tau_star, 0.80)
            self.assertGreaterEqual(fb_star, 0.0)

    def test_era_fpr_present(self):
        """Era FPR list is populated."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        self.assertGreater(len(report.era_fpr), 0)

    def test_fp_taxonomy_present(self):
        """FP classifications are generated."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        # Some FPs should exist
        # (non-crisis weeks with MAC < 0.50)
        # The exact count depends on momentum signals; just check structure
        self.assertIsInstance(report.fp_classifications, list)


class TestPRHelpers(unittest.TestCase):
    """Helper functions for precision-recall."""

    def test_optimal_threshold_for_beta(self):
        """optimal_threshold_for_beta returns a valid τ."""
        # Minimal synthetic curve
        curve = [
            PRPoint(
                tau=0.30, tp=5, fp=2, fn=5,
                precision=0.71, recall=0.50,
                f1=0.59, f05=0.66, f2=0.53,
                signal_weeks=7, fp_per_year=0.5,
            ),
            PRPoint(
                tau=0.50, tp=8, fp=5, fn=2,
                precision=0.62, recall=0.80,
                f1=0.70, f05=0.65, f2=0.76,
                signal_weeks=13, fp_per_year=1.2,
            ),
        ]
        tau_star, fb = optimal_threshold_for_beta(curve, beta=1.0)
        self.assertIn(tau_star, [0.30, 0.50])
        self.assertGreater(fb, 0.0)

    def test_breakeven_precision(self):
        """Breakeven precision: cost_FP / (cost_FP + cost_FN)."""
        be = breakeven_precision(30, 1500)
        self.assertAlmostEqual(be, 30 / 1530, places=4)

    def test_breakeven_precision_zero(self):
        self.assertEqual(breakeven_precision(0, 0), 0.0)


class TestPRReporting(unittest.TestCase):
    """Formatting and export."""

    def setup_method(self, method=None):
        base_date = datetime(2020, 1, 1)
        self.crisis_events = [
            ("Crisis1", base_date + timedelta(weeks=50)),
        ]
        self.weekly_data = []
        for i in range(100):
            date = base_date + timedelta(weeks=i)
            mac = 0.30 if 45 <= i <= 55 else 0.65
            self.weekly_data.append({
                "date": date,
                "mac_score": mac,
                "mac_status": "COMFORTABLE" if mac > 0.50 else "STRETCHED",
                "is_deteriorating": mac < 0.40,
            })

    def test_format_report(self):
        """format_precision_recall_report produces non-empty string."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        text = format_precision_recall_report(report)
        self.assertIn("PRECISION-RECALL", text)
        self.assertIn("STANDARD OPERATING POINTS", text)

    def test_export_json(self):
        """export_precision_recall_json produces valid JSON."""
        report = compute_precision_recall_curve(
            self.weekly_data, self.crisis_events,
        )
        json_str = export_precision_recall_json(report)
        data = json.loads(json_str)
        self.assertIn("curve", data)
        self.assertIn("operating_points", data)
        self.assertIn("optimal_by_archetype", data)
        self.assertGreater(len(data["curve"]), 0)


class TestClientArchetypes(unittest.TestCase):
    """Client archetype enumeration."""

    def test_all_archetypes_have_beta(self):
        """All four archetypes have a beta value."""
        for arch in ClientArchetype:
            self.assertIsInstance(arch.beta, float)
            self.assertGreater(arch.beta, 0.0)

    def test_beta_values(self):
        """Specific β values match v6 §15.6.6."""
        self.assertEqual(ClientArchetype.SOVEREIGN_WEALTH_FUND.beta, 2.0)
        self.assertEqual(ClientArchetype.CENTRAL_BANK.beta, 1.0)
        self.assertEqual(ClientArchetype.MACRO_HEDGE_FUND.beta, 0.5)
        self.assertEqual(ClientArchetype.INSURANCE_PENSION.beta, 1.5)

    def test_standard_operating_points(self):
        """Five standard operating points defined."""
        self.assertEqual(len(STANDARD_OPERATING_POINTS), 5)
        self.assertEqual(STANDARD_OPERATING_POINTS["Default"], 0.50)
        self.assertEqual(STANDARD_OPERATING_POINTS["Conservative"], 0.30)
        self.assertEqual(STANDARD_OPERATING_POINTS["Maximum recall"], 0.70)


# ═══════════════════════════════════════════════════════════════════════════
# WP-9 TESTS
# ═══════════════════════════════════════════════════════════════════════════

def _make_synthetic_pillar_data(
    T: int = 200, seed: int = 42,
) -> Dict[str, List[float]]:
    """Generate synthetic pillar score data for SVAR testing."""
    rng = np.random.RandomState(seed)
    pillars = CHOLESKY_ORDERING
    data = {}
    # Generate correlated random walks bounded in [0, 1]
    base = rng.randn(T, len(pillars)) * 0.02
    levels = np.zeros((T, len(pillars)))
    levels[0] = 0.55
    for t in range(1, T):
        levels[t] = levels[t - 1] + base[t]
        levels[t] = np.clip(levels[t], 0.05, 0.95)
    for i, p in enumerate(pillars):
        data[p] = levels[:, i].tolist()
    return data


class TestVAREstimation(unittest.TestCase):
    """VAR estimation basics."""

    def setup_method(self, method=None):
        self.data = _make_synthetic_pillar_data(200)
        raw = np.column_stack(
            [np.array(self.data[p])
             for p in CHOLESKY_ORDERING]
        )
        self.diff = np.diff(raw, axis=0)

    def test_estimate_var_shapes(self):
        """B and Sigma have correct shapes."""
        K = len(CHOLESKY_ORDERING)
        p = 2
        B, Sigma, bic = estimate_var(self.diff, p)
        self.assertEqual(B.shape, (K * p + 1, K))
        self.assertEqual(Sigma.shape, (K, K))

    def test_bic_finite(self):
        """BIC is a finite number."""
        _, _, bic = estimate_var(self.diff, 2)
        self.assertTrue(math.isfinite(bic))

    def test_select_lag_order(self):
        """BIC selects a lag order from candidates."""
        lag, bic = select_lag_order(self.diff)
        self.assertIn(lag, [1, 2, 3, 4])
        self.assertTrue(math.isfinite(bic))


class TestIRF(unittest.TestCase):
    """Impulse response functions."""

    def setup_method(self, method=None):
        self.data = _make_synthetic_pillar_data(200)
        K = len(CHOLESKY_ORDERING)
        raw = np.column_stack(
            [np.array(self.data[p])
             for p in CHOLESKY_ORDERING]
        )
        diff = np.diff(raw, axis=0)
        self.K = K
        B, self.Sigma, _ = estimate_var(diff, 2)
        from grri_mac.predictive.cascade_var import (  # noqa: E501
            _extract_coefficient_matrices,
        )
        self.A = _extract_coefficient_matrices(B, K, 2)

    def test_cirf_shape(self):
        """CIRF matrix is K×K."""
        cirf = compute_irf(
            self.A, self.Sigma, CHOLESKY_ORDERING, CHOLESKY_ORDERING,
        )
        self.assertEqual(cirf.shape, (self.K, self.K))

    def test_girf_shape(self):
        """GIRF matrix is K×K."""
        girf = compute_girf(self.A, self.Sigma)
        self.assertEqual(girf.shape, (self.K, self.K))

    def test_normalise_matrix(self):
        """normalise_matrix maps to [-1, 1]."""
        M = np.array([[3.0, -5.0], [2.0, 1.0]])
        N = normalise_matrix(M)
        self.assertAlmostEqual(np.max(np.abs(N)), 1.0)

    def test_normalise_zero_matrix(self):
        """normalise_matrix handles zero matrix."""
        M = np.zeros((3, 3))
        N = normalise_matrix(M)
        self.assertTrue(np.allclose(N, 0.0))


class TestSVAREstimate(unittest.TestCase):
    """Full SVAR estimation pipeline."""

    def test_estimate_svar(self):
        """estimate_svar returns SVAREstimate with correct fields."""
        data = _make_synthetic_pillar_data(200)
        est = estimate_svar(data)
        self.assertIsInstance(est, SVAREstimate)
        self.assertIn(est.lag_order, [1, 2, 3, 4])
        self.assertEqual(est.pillar_names, CHOLESKY_ORDERING)
        self.assertEqual(est.transmission_matrix.shape, (6, 6))
        # Normalised → max abs = 1
        self.assertAlmostEqual(
            np.max(np.abs(est.transmission_matrix)),
            1.0, places=5,
        )

    def test_transmission_matrix_to_dict(self):
        """Converts numpy matrix to nested dict for shock_propagation.py."""
        data = _make_synthetic_pillar_data(200)
        est = estimate_svar(data)
        d = transmission_matrix_to_dict(
            est.transmission_matrix,
            est.pillar_names,
        )
        # Should have 6 sources
        self.assertEqual(len(d), 6)
        for source, targets in d.items():
            self.assertIn(source, CHOLESKY_ORDERING)
            self.assertEqual(d[source][source], 0.0)  # diagonal = 0

    def test_update_interaction_matrix(self):
        """update_interaction_matrix is a drop-in dict."""
        data = _make_synthetic_pillar_data(200)
        est = estimate_svar(data)
        d = update_interaction_matrix(est)
        self.assertIn("liquidity", d)
        self.assertIn("volatility", d["liquidity"])


class TestRobustness(unittest.TestCase):
    """Robustness across orderings."""

    def test_robustness_small_data(self):
        """Robustness check runs on small dataset."""
        # Use small max_permutations to keep test fast
        data = _make_synthetic_pillar_data(150)
        result = robustness_all_orderings(data, max_permutations=10)
        self.assertIsInstance(result, RobustnessResult)
        self.assertEqual(result.n_permutations_tested, 10)
        self.assertEqual(result.median_cirf.shape, (6, 6))
        self.assertEqual(result.girf_matrix.shape, (6, 6))


class TestAcceleration(unittest.TestCase):
    """Regime-dependent acceleration factors."""

    def test_acceleration_factors(self):
        """Acceleration factors produce normal and stress matrices."""
        data = _make_synthetic_pillar_data(200)
        mac = [0.55] * 100 + [0.35] * 100  # half normal, half stress (T=200)
        result = estimate_acceleration_factors(data, mac)
        self.assertIsInstance(result, AccelerationFactors)
        self.assertEqual(result.acceleration.shape, (6, 6))
        # Capped at 5×
        self.assertTrue(np.all(result.acceleration <= 5.0))
        self.assertTrue(np.all(result.acceleration >= 0.0))


class TestGranger(unittest.TestCase):
    """Granger causality tests."""

    def test_granger_all_pairs(self):
        """30 directed pairs for 6 pillars."""
        data = _make_synthetic_pillar_data(200)
        results = granger_causality_tests(data, lag_order=2)
        # 6 pillars × 5 targets each = 30 pairs
        self.assertEqual(len(results), 30)
        for g in results:
            self.assertIsInstance(g, GrangerResult)
            self.assertGreaterEqual(g.p_value, 0.0)
            self.assertLessEqual(g.p_value, 1.0)


class TestFTestPValue(unittest.TestCase):
    """F-test p-value approximation."""

    def test_large_f_stat(self):
        """Large F-stat → small p-value."""
        p = _f_test_p_value(500.0, 10, 200)
        self.assertLess(p, 0.05)

    def test_zero_f_stat(self):
        """F=0 → p=1."""
        p = _f_test_p_value(0.0, 3, 100)
        self.assertEqual(p, 1.0)

    def test_negative_df(self):
        """Negative df → p=1."""
        p = _f_test_p_value(5.0, -1, 100)
        self.assertEqual(p, 1.0)


class TestSVARPipeline(unittest.TestCase):
    """Full pipeline integration test."""

    def test_run_svar_pipeline(self):
        """run_svar_pipeline returns complete CascadeVARReport."""
        data = _make_synthetic_pillar_data(200)
        mac = [0.55] * 100 + [0.35] * 100
        report = run_svar_pipeline(
            data, mac,
            run_robustness=False,  # fast
            run_acceleration=True,
            run_granger=True,
        )
        self.assertIsInstance(report, CascadeVARReport)
        self.assertIsInstance(report.primary_estimate, SVAREstimate)
        self.assertIsNone(report.robustness)  # skipped
        self.assertIsNotNone(report.acceleration)
        self.assertEqual(len(report.granger_tests), 30)
        self.assertIn("liquidity", report.transmission_dict)

    def test_format_svar_report(self):
        """Report formatting produces readable text."""
        data = _make_synthetic_pillar_data(200)
        report = run_svar_pipeline(
            data,
            run_robustness=False,
            run_acceleration=False,
            run_granger=True,
        )
        text = format_svar_report(report)
        self.assertIn("SVAR CASCADE ESTIMATION REPORT", text)
        self.assertIn("GRANGER CAUSALITY", text)


class TestSVARConstants(unittest.TestCase):
    """SVAR constants match v6."""

    def test_cholesky_ordering(self):
        """6 pillars in theory-motivated order."""
        self.assertEqual(len(CHOLESKY_ORDERING), 6)
        self.assertEqual(CHOLESKY_ORDERING[0], "policy")      # slowest
        self.assertEqual(
            CHOLESKY_ORDERING[-1], "positioning",
        )  # fastest

    def test_critical_thresholds(self):
        """Critical thresholds defined for all 6 pillars."""
        for pillar in CHOLESKY_ORDERING:
            self.assertIn(pillar, CRITICAL_THRESHOLDS)
            self.assertGreater(CRITICAL_THRESHOLDS[pillar], 0.0)
            self.assertLess(CRITICAL_THRESHOLDS[pillar], 1.0)

    def test_cirf_horizon(self):
        self.assertEqual(CIRF_HORIZON, 4)

    def test_mac_stress_threshold(self):
        self.assertEqual(MAC_STRESS_THRESHOLD, 0.50)


# ═══════════════════════════════════════════════════════════════════════════
# WP-10 TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestBenchmarkEra(unittest.TestCase):
    """Era-dependent benchmark selection."""

    def test_pre_1914_uk_consol(self):
        self.assertEqual(get_benchmark_era(1870), BenchmarkEra.UK_CONSOL)

    def test_interwar_blend(self):
        self.assertEqual(get_benchmark_era(1930), BenchmarkEra.BLEND)

    def test_post_1945_us_treasury(self):
        self.assertEqual(get_benchmark_era(2000), BenchmarkEra.US_TREASURY)

    def test_boundary_1914(self):
        self.assertEqual(get_benchmark_era(1913), BenchmarkEra.UK_CONSOL)
        self.assertEqual(get_benchmark_era(1914), BenchmarkEra.BLEND)

    def test_boundary_1945(self):
        self.assertEqual(get_benchmark_era(1944), BenchmarkEra.BLEND)
        self.assertEqual(get_benchmark_era(1945), BenchmarkEra.US_TREASURY)


class TestSovereignSpread(unittest.TestCase):
    """Sovereign spread computation."""

    def test_positive_spread(self):
        """Higher gov yield → positive spread."""
        ss = compute_sovereign_spread(5.0, 3.0)
        self.assertAlmostEqual(ss, 2.0)

    def test_negative_spread(self):
        """Lower gov yield → negative spread (unusual but possible)."""
        ss = compute_sovereign_spread(2.0, 3.0)
        self.assertAlmostEqual(ss, -1.0)

    def test_zero_spread(self):
        ss = compute_sovereign_spread(4.0, 4.0)
        self.assertAlmostEqual(ss, 0.0)


class TestQuadraticMapping(unittest.TestCase):
    """Quadratic spread → MAC proxy mapping."""

    def test_zero_spread_returns_intercept(self):
        """At SS=0, MAC_proxy ≈ a."""
        coef = QuadraticCoefficients(a=0.75, b=0.12, c=0.005, residual_se=0.10)
        mac, ci_lo, ci_hi = map_spread_to_mac(0.0, coef)
        self.assertAlmostEqual(mac, 0.75)

    def test_high_spread_lowers_mac(self):
        """Higher spread → lower MAC proxy."""
        coef = QuadraticCoefficients(a=0.75, b=0.12, c=0.005, residual_se=0.10)
        mac_low, _, _ = map_spread_to_mac(0.0, coef)
        mac_high, _, _ = map_spread_to_mac(3.0, coef)
        self.assertGreater(mac_low, mac_high)

    def test_bounded_to_01(self):
        """MAC proxy is clamped to [0, 1]."""
        coef = QuadraticCoefficients(a=0.75, b=0.50, c=0.001, residual_se=0.10)
        mac, ci_lo, ci_hi = map_spread_to_mac(10.0, coef)  # extreme spread
        self.assertGreaterEqual(mac, 0.0)
        self.assertLessEqual(mac, 1.0)
        self.assertGreaterEqual(ci_lo, 0.0)
        self.assertLessEqual(ci_hi, 1.0)

    def test_confidence_band_width(self):
        """80% CI width ≈ 2 × 1.28 × residual_se."""
        coef = QuadraticCoefficients(a=0.75, b=0.12, c=0.005, residual_se=0.10)
        mac, ci_lo, ci_hi = map_spread_to_mac(1.0, coef)
        expected_width = 2 * 1.28 * 0.10
        actual_width = ci_hi - ci_lo
        self.assertAlmostEqual(actual_width, expected_width, places=2)


class TestComputeProxyMAC(unittest.TestCase):
    """End-to-end proxy MAC computation."""

    def test_compute_proxy_mac_uk(self):
        """Compute proxy MAC for a UK observation."""
        obs = SovereignSpreadObservation(
            date=datetime(1890, 11, 1),
            country_code="UK",
            gov_yield_pct=3.5,
            benchmark_yield_pct=2.8,
            spread_pct=0.7,
            benchmark_era=BenchmarkEra.UK_CONSOL,
        )
        result = compute_proxy_mac(obs)
        self.assertIsInstance(result, SovereignProxyMAC)
        self.assertGreater(result.mac_proxy, 0.0)
        self.assertLess(result.mac_proxy, 1.0)
        self.assertLess(result.confidence_80_low, result.mac_proxy)
        self.assertGreater(result.confidence_80_high, result.mac_proxy)
        self.assertTrue(result.is_aggregate_only)

    def test_default_coefficients_fallback(self):
        """Unknown country gets global default coefficients."""
        obs = SovereignSpreadObservation(
            date=datetime(1950, 1, 1),
            country_code="ZZ",  # unknown
            gov_yield_pct=4.0,
            benchmark_yield_pct=3.0,
            spread_pct=1.0,
            benchmark_era=BenchmarkEra.US_TREASURY,
        )
        result = compute_proxy_mac(obs)
        # Should not raise and should return a valid score
        self.assertGreater(result.mac_proxy, 0.0)


class TestCalibration(unittest.TestCase):
    """Overlap calibration."""

    def test_calibrate_with_known_data(self):
        """Calibrate from known linear relationship."""
        # Generate points from MAC = 0.80 - 0.10 * SS + 0.002 * SS²
        n = 50
        spreads = [0.5 + i * 0.1 for i in range(n)]
        macs = [0.80 - 0.10 * ss + 0.002 * ss ** 2 for ss in spreads]
        coef = calibrate_coefficients(spreads, macs)
        self.assertAlmostEqual(coef.a, 0.80, places=1)
        self.assertAlmostEqual(coef.b, 0.10, places=1)
        self.assertGreaterEqual(coef.residual_se, 0.0)

    def test_calibrate_requires_10_points(self):
        """ValueError if fewer than 10 overlap observations."""
        with self.assertRaises(ValueError):
            calibrate_coefficients([1.0] * 5, [0.5] * 5)


class TestBuildProxyMACSeries(unittest.TestCase):
    """Build historical time series."""

    def test_build_series(self):
        """Series length matches input."""
        obs = [
            SovereignSpreadObservation(
                date=datetime(1880, 1, 1) + timedelta(days=365 * i),
                country_code="UK",
                gov_yield_pct=3.0 + i * 0.1,
                benchmark_yield_pct=2.5,
                spread_pct=0.5 + i * 0.1,
                benchmark_era=BenchmarkEra.UK_CONSOL,
            )
            for i in range(20)
        ]
        series = build_proxy_mac_series(obs)
        self.assertEqual(len(series), 20)
        for s in series:
            self.assertIsInstance(s, SovereignProxyMAC)


class TestSovereignProxyConstants(unittest.TestCase):
    """Module constants and data."""

    def test_default_coefficients_countries(self):
        """Default coefficients for UK, DE, FR, IT, JP."""
        self.assertIn("UK", DEFAULT_COEFFICIENTS)
        self.assertIn("JP", DEFAULT_COEFFICIENTS)
        self.assertEqual(len(DEFAULT_COEFFICIENTS), 5)

    def test_uk_stress_episodes(self):
        """UK has ≥ 8 calibration episodes."""
        self.assertGreaterEqual(len(UK_STRESS_EPISODES), 8)
        for ep in UK_STRESS_EPISODES:
            self.assertIsInstance(ep, HistoricalStressEpisode)
            self.assertTrue(
                ep.expected_mac_range[0]
                < ep.expected_mac_range[1]
            )

    def test_data_sources(self):
        """At least 5 data sources documented."""
        self.assertGreaterEqual(len(DATA_SOURCES), 5)

    def test_proxy_limitations(self):
        """Limitations documented."""
        self.assertGreaterEqual(len(PROXY_LIMITATIONS), 5)
        for lim in PROXY_LIMITATIONS:
            self.assertIn("limitation", lim)
            self.assertIn("mitigation", lim)


class TestProxyMACReport(unittest.TestCase):
    """Reporting."""

    def test_format_report(self):
        """Report text includes key sections."""
        obs = [
            SovereignSpreadObservation(
                date=datetime(1890, 1, 1),
                country_code="UK",
                gov_yield_pct=3.2,
                benchmark_yield_pct=2.8,
                spread_pct=0.4,
                benchmark_era=BenchmarkEra.UK_CONSOL,
            ),
            SovereignSpreadObservation(
                date=datetime(1900, 1, 1),
                country_code="UK",
                gov_yield_pct=3.5,
                benchmark_yield_pct=2.8,
                spread_pct=0.7,
                benchmark_era=BenchmarkEra.UK_CONSOL,
            ),
        ]
        series = build_proxy_mac_series(obs)
        text = format_proxy_mac_report(
            series, "United Kingdom",
            UK_STRESS_EPISODES,
        )
        self.assertIn("SOVEREIGN BOND PROXY MAC", text)
        self.assertIn("STRESS EPISODE VALIDATION", text)

    def test_format_empty_series(self):
        text = format_proxy_mac_report([], "UK")
        self.assertIn("No observations", text)


# ═══════════════════════════════════════════════════════════════════════════
# WP-11 TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestDataQualityTiers(unittest.TestCase):
    """Data quality tier labels (v6 §15.5)."""

    def setup_method(self, method=None):
        self.runner = BacktestRunner.__new__(BacktestRunner)

    def test_excellent_post_2018(self):
        result = self.runner._assess_data_quality(
            datetime(2024, 1, 1),
        )
        self.assertEqual(result, "excellent")

    def test_good_2011_2018(self):
        result = self.runner._assess_data_quality(
            datetime(2015, 6, 1),
        )
        self.assertEqual(result, "good")

    def test_fair_1990_2011(self):
        result = self.runner._assess_data_quality(
            datetime(2005, 1, 1),
        )
        self.assertEqual(result, "fair")

    def test_poor_pre_1990(self):
        result = self.runner._assess_data_quality(
            datetime(1960, 1, 1),
        )
        self.assertEqual(result, "poor")

    def test_poor_pre_1907(self):
        result = self.runner._assess_data_quality(
            datetime(1890, 1, 1),
        )
        self.assertEqual(result, "poor")


class TestRunnerDocstring(unittest.TestCase):
    """Backtest runner docstring and metadata."""

    def test_module_docstring_mentions_fixes(self):
        """Module docstring references Fixes A–F."""
        import grri_mac.backtest.runner as runner_mod
        doc = runner_mod.__doc__
        self.assertIn("Fix A", doc)
        self.assertIn("Fix B", doc)
        self.assertIn("Fix C", doc)
        self.assertIn("Fix D", doc)
        self.assertIn("Fix E", doc)
        self.assertIn("Fix F", doc)

    def test_calculate_mac_for_date_docstring(self):
        """calculate_mac_for_date docstring references all 6 fixes."""
        doc = BacktestRunner.calculate_mac_for_date.__doc__
        self.assertIn("Fix A", doc)
        self.assertIn("Fix B", doc)
        self.assertIn("Fix C", doc)
        self.assertIn("Fix D", doc)
        self.assertIn("Fix E", doc)
        self.assertIn("Fix F", doc)


class TestValidationReportStructure(unittest.TestCase):
    """Validation report returns new v6 fields."""

    def test_report_has_era_detection(self):
        """generate_validation_report returns per_era_detection."""
        import pandas as pd
        # Minimal mock backtest DataFrame
        dates = pd.date_range("2020-01-01", periods=10, freq="W")
        df = pd.DataFrame({
            "mac_score": [0.65] * 10,
            "crisis_event": [None] * 10,
            "data_quality": ["excellent"] * 10,
            "momentum_4w": [0.0] * 10,
        }, index=dates)
        runner = BacktestRunner.__new__(BacktestRunner)
        report = runner.generate_validation_report(df)
        self.assertIn("per_era_detection", report)
        self.assertIn("data_quality_distribution", report)
        self.assertIn("fixes_applied", report)
        self.assertIsInstance(report["per_era_detection"], list)
        self.assertEqual(len(report["per_era_detection"]), 7)  # 7 eras

    def test_fixes_applied_all_six(self):
        """Fixes A through F are all documented."""
        import pandas as pd
        dates = pd.date_range("2020-01-01", periods=5, freq="W")
        df = pd.DataFrame({
            "mac_score": [0.60] * 5,
            "crisis_event": [None] * 5,
            "data_quality": ["excellent"] * 5,
            "momentum_4w": [0.0] * 5,
        }, index=dates)
        runner = BacktestRunner.__new__(BacktestRunner)
        report = runner.generate_validation_report(df)
        fixes = report["fixes_applied"]
        for key in ["A", "B", "C", "D", "E", "F"]:
            self.assertIn(key, fixes)


class TestBacktestPointDataclass(unittest.TestCase):
    """BacktestPoint includes data quality."""

    def test_data_quality_field(self):
        bp = BacktestPoint(
            date=datetime(2024, 1, 1),
            mac_score=0.55,
            pillar_scores={},
            breach_flags=[],
            interpretation="cautious",
            data_quality="excellent",
        )
        self.assertEqual(bp.data_quality, "excellent")


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()

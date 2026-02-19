#!/usr/bin/env python
"""Tests for all v7 MAC Framework modules.

Covers:
- Phase 1: Scenarios, Augmentation, Confidence, XGBoost
- Phase 2: Breach model, Policy, PCA, Kalman VRP, Hedge failure, Adaptive valuation
- Phase 3: Walk-forward, Crisis catalogue, FP cost analysis
- Phase 4: Sentiment pillar, HMM regime switching
- Phase 5: Multi-country validation
"""

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Foundation
# ═══════════════════════════════════════════════════════════════════════════


class TestScenarioExpansion:
    """WP 1.1: Expanded scenarios."""

    def test_scenario_count(self):
        from grri_mac.backtest.scenarios import KNOWN_EVENTS
        assert len(KNOWN_EVENTS) >= 30, (
            f"Expected ≥30 scenarios, got {len(KNOWN_EVENTS)}"
        )

    def test_new_scenarios_have_indicators(self):
        from grri_mac.backtest.scenarios import KNOWN_EVENTS
        for key, scenario in KNOWN_EVENTS.items():
            assert scenario.indicators, (
                f"Scenario '{key}' has empty indicators"
            )
            assert scenario.csr is not None, (
                f"Scenario '{key}' missing CSR scores"
            )

    def test_severity_distribution(self):
        """Training set should have mid-severity events."""
        from grri_mac.backtest.scenarios import KNOWN_EVENTS
        csr_values = []
        for s in KNOWN_EVENTS.values():
            if s.csr is not None:
                composite = (
                    s.csr.drawdown + s.csr.mkt_dysfunction
                    + s.csr.policy_response + s.csr.contagion
                    + s.csr.duration
                ) / 5
                csr_values.append(composite)
        mid_range = [v for v in csr_values if 0.35 <= v <= 0.70]
        assert len(mid_range) >= 5, (
            "Need at least 5 mid-severity scenarios"
        )


class TestAugmentation:
    """WP 1.2: Synthetic augmentation pipeline."""

    def test_augment_scenarios(self):
        from grri_mac.backtest.augmentation import (
            augment_scenarios,
            AugmentationConfig,
        )
        scenarios = [
            {"pillar_scores": {"liquidity": 0.3, "volatility": 0.5},
             "csr": 0.4, "name": "test1"},
            {"pillar_scores": {"liquidity": 0.7, "volatility": 0.8},
             "csr": 0.7, "name": "test2"},
        ]
        config = AugmentationConfig(n_augmented=4, noise_pct=0.10)
        result = augment_scenarios(scenarios, config)

        # 2 original + 2*4 augmented = 10
        assert len(result) == 10
        # CSR targets preserved (augmented copies same CSR)
        for item in result:
            assert "csr" in item

    def test_noise_bounded(self):
        from grri_mac.backtest.augmentation import (
            augment_scenarios,
            AugmentationConfig,
        )
        scenarios = [
            {"pillar_scores": {"a": 0.5, "b": 0.5},
             "csr": 0.5, "name": "test"},
        ]
        config = AugmentationConfig(n_augmented=100, noise_pct=0.10)
        result = augment_scenarios(scenarios, config)
        for item in result:
            for v in item["pillar_scores"].values():
                assert 0.0 <= v <= 1.0, (
                    f"Score {v} out of [0,1] range"
                )


class TestConfidence:
    """WP 1.3: Bootstrap CI."""

    def test_bootstrap_mac_ci(self):
        from grri_mac.mac.confidence import bootstrap_mac_ci

        pillar_scores = {
            "liquidity": 0.6,
            "valuation": 0.5,
            "positioning": 0.7,
            "volatility": 0.4,
            "policy": 0.6,
            "contagion": 0.5,
            "private_credit": 0.6,
        }
        weights = {k: 1 / 7 for k in pillar_scores}
        result = bootstrap_mac_ci(
            pillar_scores, weights, n_bootstrap=200,
        )
        assert result.ci_80 is not None
        assert result.ci_90 is not None
        assert result.ci_80[0] <= result.ci_90[1]
        assert result.bootstrap_std > 0

    def test_conformal_prediction(self):
        from grri_mac.mac.confidence import (
            conformal_prediction_band,
        )
        residuals = [0.02, -0.03, 0.01, -0.01, 0.04, -0.02]
        lo, hi = conformal_prediction_band(
            0.45, residuals, alpha=0.10,
        )
        assert lo < 0.45
        assert hi > 0.45


class TestXGBoost:
    """WP 1.4: XGBoost optimizer."""

    def test_xgb_optimizer_import(self):
        try:
            from grri_mac.mac.ml_weights_xgb import (
                XGBWeightOptimizer,
            )
            opt = XGBWeightOptimizer()
            assert opt is not None
        except ImportError:
            pytest.skip("xgboost/scikit-learn not installed")

    def test_xgb_optimize_severity(self):
        try:
            from grri_mac.mac.ml_weights_xgb import (
                XGBWeightOptimizer,
            )
            opt = XGBWeightOptimizer()
        except ImportError:
            pytest.skip("xgboost/scikit-learn not installed")
        # Small synthetic dataset as list of pillar-score dicts
        pillars = [
            "liquidity", "valuation", "positioning",
            "volatility", "policy", "contagion",
        ]
        pillar_scores = [
            {p: float(np.random.rand()) for p in pillars}
            for _ in range(30)
        ]
        y = np.random.rand(30).tolist()
        result = opt.optimize_for_severity(pillar_scores, y)
        assert result.weights is not None
        assert len(result.weights) == 6


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: Pillar Refinements
# ═══════════════════════════════════════════════════════════════════════════


class TestBreachModel:
    """WP 2.1: Pillar-specific breach probabilities."""

    def test_breach_model_init(self):
        from grri_mac.mac.breach_model import PillarBreachModel
        model = PillarBreachModel()
        assert model is not None

    def test_breach_model_fit(self):
        from grri_mac.mac.breach_model import PillarBreachModel
        model = PillarBreachModel()
        # Synthetic scenarios
        rng = np.random.default_rng(42)
        scenarios = []
        for i in range(20):
            scenarios.append({
                "name": f"scenario_{i}",
                "date": datetime(2000 + i, 1, 1),
                "pillar_scores": {
                    "liquidity": float(rng.random()),
                    "volatility": float(rng.random()),
                    "valuation": float(rng.random()),
                    "positioning": float(rng.random()),
                    "policy": float(rng.random()),
                    "contagion": float(rng.random()),
                    "private_credit": float(rng.random()),
                },
            })
        model.fit(scenarios)
        result = model.compute_interaction_penalties()
        assert result is not None
        assert result.penalties is not None
        assert len(result.penalties) > 0


class TestPolicyPillar:
    """WP 2.2: Policy pillar refinements."""

    def test_forward_inflation_scoring(self):
        from grri_mac.pillars.policy import PolicyPillar
        pillar = PolicyPillar()
        # Well-anchored expectations (20bps from target)
        score = pillar.score_forward_inflation(20)
        assert score > 0.7
        # Unanchored (200bps from target)
        score = pillar.score_forward_inflation(200)
        assert score < 0.2

    def test_sliding_gold_cap(self):
        from grri_mac.pillars.policy import PolicyPillar
        pillar = PolicyPillar()
        # Pre-1913 with high gold reserves
        cap = pillar._get_era_cap(
            datetime(1900, 1, 1), gold_reserve_ratio=0.80,
        )
        assert cap is not None
        assert cap <= 0.30
        # With very low gold reserves
        cap_low = pillar._get_era_cap(
            datetime(1900, 1, 1), gold_reserve_ratio=0.10,
        )
        assert cap_low < cap

    def test_forward_inflation_in_composite(self):
        from grri_mac.pillars.policy import (
            PolicyPillar,
            PolicyIndicators,
        )
        pillar = PolicyPillar()
        indicators = PolicyIndicators(
            policy_room_bps=200,
            fed_balance_sheet_gdp_pct=20,
            core_pce_vs_target_bps=50,
            debt_to_gdp_pct=80,
            forward_inflation_expectations_bps=25,
        )
        scores = pillar.calculate(indicators)
        assert scores.forward_inflation > 0.0
        assert scores.composite > 0.0

    def test_calibrate_homogeneity_threshold(self):
        from grri_mac.pillars.policy import PolicyPillar
        dispersions = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]
        threshold = PolicyPillar.calibrate_homogeneity_threshold(
            dispersions,
        )
        # 75th percentile of [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]
        # Index 4 (0-based) = 0.3 at int(0.75 * 6) = 4
        assert 0.25 <= threshold <= 0.40


class TestPrivateCreditPCA:
    """WP 2.3: 5-factor PCA decorrelation."""

    def test_pca_decorrelation(self):
        from grri_mac.pillars.private_credit_pca import (
            RollingPCADecorrelator,
        )
        rng = np.random.default_rng(42)
        n = 252

        decorrelator = RollingPCADecorrelator(
            window=252, n_components=3, min_observations=60,
        )
        result = decorrelator.decorrelate(
            bdc_returns=rng.normal(0, 0.01, n).tolist(),
            spx_returns=rng.normal(0, 0.01, n).tolist(),
            vix_changes=rng.normal(0, 1.0, n).tolist(),
            hy_oas_changes=rng.normal(0, 5, n).tolist(),
            move_changes=rng.normal(0, 2, n).tolist(),
        )
        assert 0.0 <= result.decorrelated_score <= 1.0
        assert result.method in ("pca", "ols_fallback")
        # R² can be slightly negative with random data
        assert result.r_squared >= -0.1

    def test_insufficient_data_fallback(self):
        from grri_mac.pillars.private_credit_pca import (
            RollingPCADecorrelator,
        )
        dec = RollingPCADecorrelator(min_observations=100)
        result = dec.decorrelate(
            bdc_returns=[0.01] * 10,
            spx_returns=[0.01] * 10,
            vix_changes=[0.1] * 10,
            hy_oas_changes=[1.0] * 10,
        )
        assert result.data_quality == "insufficient"


class TestKalmanVRP:
    """WP 2.4: Kalman filter VRP."""

    def test_linear_fallback(self):
        from grri_mac.pillars.vrp_kalman import KalmanVRPEstimator
        estimator = KalmanVRPEstimator()
        # Short history → linear fallback
        result = estimator.estimate(
            vix_history=list(range(10)),
        )
        assert result.method == "linear_fallback"
        assert 1.0 <= result.vrp_estimate <= 1.6

    def test_estimate_with_history(self):
        from grri_mac.pillars.vrp_kalman import KalmanVRPEstimator
        rng = np.random.default_rng(42)
        estimator = KalmanVRPEstimator()
        vix = (20 + rng.normal(0, 2, 300)).tolist()
        result = estimator.estimate(vix_history=vix)
        assert result.vrp_estimate >= 1.0
        assert result.vol_of_vol is not None


class TestHedgeFailure:
    """WP 2.5: Hedge failure analysis."""

    def test_hedge_failure_detection(self):
        from grri_mac.pillars.hedge_failure_analysis import (
            HedgeFailureDetector,
        )
        det = HedgeFailureDetector()
        # Both bonds and equities down → hedge failure
        assert det.is_hedge_failure(-0.03, -0.04) is True
        # Bonds up, equities down → hedge works
        assert det.is_hedge_failure(0.01, -0.04) is False
        # Below threshold on one side only
        assert det.is_hedge_failure(-0.03, -0.01) is False

    def test_episode_catalogue(self):
        from grri_mac.pillars.hedge_failure_analysis import (
            HEDGE_FAILURE_EPISODES,
        )
        assert len(HEDGE_FAILURE_EPISODES) >= 9
        severe = [
            e for e in HEDGE_FAILURE_EPISODES
            if e.severity == "severe"
        ]
        assert len(severe) >= 2

    def test_bayesian_posterior(self):
        from grri_mac.pillars.hedge_failure_analysis import (
            HedgeFailureDetector,
        )
        det = HedgeFailureDetector()
        result = det.bayesian_posterior()
        assert 0.0 < result["posterior_mean"] < 1.0
        assert result["ci_90"][0] < result["ci_90"][1]
        assert result["n_episodes"] >= 9

    def test_dealer_leverage_scoring(self):
        from grri_mac.pillars.hedge_failure_analysis import (
            HedgeFailureDetector,
        )
        det = HedgeFailureDetector()
        assert det.score_primary_dealer_leverage(10) == 1.0
        assert det.score_primary_dealer_leverage(40) == 0.0
        mid = det.score_primary_dealer_leverage(20)
        assert 0.0 < mid < 1.0


class TestAdaptiveValuation:
    """WP 2.6: Regime-dependent valuation bands."""

    def test_compute_bands(self):
        from grri_mac.pillars.valuation_adaptive import (
            AdaptiveValuationBands,
        )
        bands = AdaptiveValuationBands()
        rng = np.random.default_rng(42)
        history = (100 + rng.normal(0, 20, 520)).tolist()
        band = bands.compute_bands(history, regime="neutral")
        assert band is not None
        assert band.ample_low < band.ample_high
        assert band.thin_low < band.thin_high
        assert band.breach_low < band.breach_high

    def test_insufficient_data(self):
        from grri_mac.pillars.valuation_adaptive import (
            AdaptiveValuationBands,
        )
        bands = AdaptiveValuationBands()
        band = bands.compute_bands([100, 110, 105], regime="neutral")
        assert band is None

    def test_score_within_ample(self):
        from grri_mac.pillars.valuation_adaptive import (
            AdaptiveValuationBands,
        )
        bands = AdaptiveValuationBands()
        rng = np.random.default_rng(42)
        history = (100 + rng.normal(0, 10, 520)).tolist()
        # Score the median value — should be in ample range
        result = bands.score_with_regime(100, history, "neutral")
        assert result.score >= 0.8

    def test_regime_detection(self):
        from grri_mac.pillars.valuation_adaptive import (
            AdaptiveValuationBands,
        )
        bands = AdaptiveValuationBands()
        assert bands.detect_regime(
            fed_balance_sheet_gdp_pct=30,
        ) == "qe"
        assert bands.detect_regime(
            fed_funds_rate_change_12m=2.0,
        ) == "tightening"
        assert bands.detect_regime() == "neutral"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: Backtesting
# ═══════════════════════════════════════════════════════════════════════════


class TestWalkForward:
    """WP 3.1: Walk-forward backtest."""

    def test_walk_forward_engine(self):
        from grri_mac.backtest.walk_forward import (
            WalkForwardEngine,
            WalkForwardConfig,
        )
        rng = np.random.default_rng(42)
        n_weeks = 200

        weekly_data = []
        for i in range(n_weeks):
            date = datetime(2010, 1, 1) + timedelta(weeks=i)
            weekly_data.append({
                "date": date,
                "mac_score": float(0.5 + 0.2 * rng.normal()),
                "pillar_scores": {
                    "liquidity": float(rng.uniform(0.3, 0.8)),
                    "valuation": float(rng.uniform(0.3, 0.8)),
                    "positioning": float(rng.uniform(0.3, 0.8)),
                    "volatility": float(rng.uniform(0.3, 0.8)),
                    "policy": float(rng.uniform(0.3, 0.8)),
                    "contagion": float(rng.uniform(0.3, 0.8)),
                    "private_credit": float(rng.uniform(0.3, 0.8)),
                },
            })

        crisis_events = [
            ("Test Crisis 1", datetime(2011, 6, 1)),
            ("Test Crisis 2", datetime(2013, 3, 1)),
        ]

        config = WalkForwardConfig(
            min_training_weeks=52,
            refit_interval_weeks=52,
        )
        engine = WalkForwardEngine(config)
        result = engine.run(weekly_data, crisis_events)

        assert result.total_weeks_predicted > 0
        assert len(result.predictions) > 0
        assert len(result.refit_dates) > 0
        assert result.alpha_stability.mean_alpha > 0

    def test_config_defaults(self):
        from grri_mac.backtest.walk_forward import (
            WalkForwardConfig,
        )
        cfg = WalkForwardConfig()
        assert cfg.refit_interval_weeks == 52
        assert cfg.expanding_window is True


class TestCrisisCatalogue:
    """WP 3.2: Expanded crisis catalogue."""

    def test_crisis_count(self):
        from grri_mac.backtest.crisis_events import CRISIS_EVENTS
        assert len(CRISIS_EVENTS) >= 55, (
            f"Expected ≥55 crises, got {len(CRISIS_EVENTS)}"
        )

    def test_total_constant_matches(self):
        from grri_mac.backtest.crisis_events import CRISIS_EVENTS
        from grri_mac.backtest.precision_recall import (
            TOTAL_CRISIS_EVENTS,
        )
        assert TOTAL_CRISIS_EVENTS == len(CRISIS_EVENTS), (
            f"TOTAL_CRISIS_EVENTS={TOTAL_CRISIS_EVENTS} but "
            f"actual count={len(CRISIS_EVENTS)}"
        )

    def test_all_crises_have_required_fields(self):
        from grri_mac.backtest.crisis_events import CRISIS_EVENTS
        for crisis in CRISIS_EVENTS:
            assert crisis.name, "Crisis missing name"
            assert crisis.start_date < crisis.end_date, (
                f"'{crisis.name}': start >= end"
            )
            assert crisis.severity in (
                "moderate", "high", "extreme"
            ), f"'{crisis.name}': invalid severity"


class TestFPCostAnalysis:
    """WP 3.3: FP cost analysis."""

    def test_fp_cost_analyser(self):
        from grri_mac.backtest.fp_cost_analysis import (
            FPCostAnalyser,
            FPCostConfig,
        )
        rng = np.random.default_rng(42)

        weekly_data = []
        for i in range(200):
            date = datetime(2010, 1, 1) + timedelta(weeks=i)
            weekly_data.append({
                "date": date,
                "mac_score": float(0.55 + 0.15 * rng.normal()),
            })

        crisis_events = [
            ("Crisis A", datetime(2011, 6, 1)),
            ("Crisis B", datetime(2013, 3, 1)),
        ]

        config = FPCostConfig(
            tau_values=[0.40, 0.50, 0.60],
        )
        analyser = FPCostAnalyser(config)
        result = analyser.analyse(weekly_data, crisis_events)

        assert len(result.cost_curve) == 3
        assert result.breakeven_precision > 0
        assert result.breakeven_precision < 1.0

    def test_fp_classification(self):
        from grri_mac.backtest.fp_cost_analysis import (
            FPCostAnalyser,
            FPCategoryV7,
        )
        analyser = FPCostAnalyser()
        crisis_events = [
            ("GFC", datetime(2008, 9, 15)),
        ]
        # FP near a crisis → near_miss
        fp = analyser._classify_single_fp(
            datetime(2008, 7, 1), 0.45, crisis_events,
        )
        assert fp.category == FPCategoryV7.NEAR_MISS

        # FP before 1971 → regime_artefact
        fp = analyser._classify_single_fp(
            datetime(1960, 1, 1), 0.40, crisis_events,
        )
        assert fp.category == FPCategoryV7.REGIME_ARTEFACT

        # FP far from any crisis → pure_false
        fp = analyser._classify_single_fp(
            datetime(2015, 6, 1), 0.40, crisis_events,
        )
        assert fp.category == FPCategoryV7.PURE_FALSE


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4: New Features
# ═══════════════════════════════════════════════════════════════════════════


class TestSentimentPillar:
    """WP 4.1: Sentiment pillar."""

    def test_no_texts_returns_neutral(self):
        from grri_mac.pillars.sentiment import SentimentPillar
        pillar = SentimentPillar()
        result = pillar.score(texts=None)
        assert result.composite_score == 0.5
        assert result.method == "no_texts"

    def test_pre_data_era(self):
        from grri_mac.pillars.sentiment import SentimentPillar
        pillar = SentimentPillar()
        result = pillar.score(
            texts=["test"],
            observation_date=datetime(1950, 1, 1),
        )
        assert result.composite_score == 0.5
        assert result.method == "pre_data"

    def test_keyword_proxy_dovish(self):
        from grri_mac.pillars.sentiment import SentimentPillar
        pillar = SentimentPillar()
        dovish_text = (
            "The Committee decided to accommodate further. "
            "Easing will support the recovery. "
            "Downside risks remain. The economy shows weakness. "
            "Forward guidance will remain patient."
        )
        result = pillar.score(texts=[dovish_text])
        # Should score higher (dovish = more capacity)
        assert result.composite_score > 0.5
        assert result.method in ("keyword_proxy", "finbert")

    def test_keyword_proxy_hawkish(self):
        from grri_mac.pillars.sentiment import SentimentPillar
        pillar = SentimentPillar()
        hawkish_text = (
            "Inflation remains above target. "
            "The Committee will tighten policy. "
            "Price stability requires a restrictive stance. "
            "Upside risks to inflation are vigilant."
        )
        result = pillar.score(texts=[hawkish_text])
        # Should score lower (hawkish = less capacity)
        assert result.composite_score < 0.5
        assert result.method in ("keyword_proxy", "finbert")


class TestRegimeHMM:
    """WP 4.2: HMM regime switching."""

    def test_hmm_threshold_fallback(self):
        from grri_mac.mac.regime_hmm import RegimeHMM
        hmm = RegimeHMM()
        # No fitting — uses raw threshold
        result = hmm.predict(
            {"liquidity": 0.3, "volatility": 0.2,
             "valuation": 0.3, "positioning": 0.25,
             "policy": 0.3, "contagion": 0.2,
             "private_credit": 0.3},
        )
        assert result.regime in ("normal", "fragile")
        assert 0.0 <= result.fragile_prob <= 1.0
        # Low scores → should lean fragile
        assert result.fragile_prob > 0.4

    def test_hmm_fit_and_predict(self):
        from grri_mac.mac.regime_hmm import RegimeHMM
        rng = np.random.default_rng(42)
        hmm = RegimeHMM()

        # Generate 200 weeks of synthetic data
        history = []
        for i in range(200):
            # First 100: normal regime, last 100: fragile
            base = 0.65 if i < 100 else 0.30
            history.append({
                "liquidity": float(base + 0.1 * rng.normal()),
                "valuation": float(base + 0.1 * rng.normal()),
                "positioning": float(base + 0.1 * rng.normal()),
                "volatility": float(base + 0.1 * rng.normal()),
                "policy": float(base + 0.1 * rng.normal()),
                "contagion": float(base + 0.1 * rng.normal()),
                "private_credit": float(base + 0.1 * rng.normal()),
            })

        fitted = hmm.fit(history)
        assert fitted is True

        # Predict on fragile scores
        result = hmm.predict(
            {"liquidity": 0.25, "volatility": 0.20,
             "valuation": 0.30, "positioning": 0.25,
             "policy": 0.30, "contagion": 0.20,
             "private_credit": 0.25},
        )
        assert result.regime in ("normal", "fragile")
        assert 0.0 <= result.fragile_prob <= 1.0

    def test_hmm_insufficient_data(self):
        from grri_mac.mac.regime_hmm import RegimeHMM
        hmm = RegimeHMM()
        short_history = [
            {"liquidity": 0.5} for _ in range(10)
        ]
        fitted = hmm.fit(short_history)
        assert fitted is False


# ═══════════════════════════════════════════════════════════════════════════
# Phase 5: Validation & Documentation
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiCountryValidation:
    """WP 5.1: Multi-country sovereign proxy validation."""

    def test_reinhart_rogoff_catalogue(self):
        from grri_mac.backtest.multicountry_validation import (
            REINHART_ROGOFF_CRISES,
        )
        assert len(REINHART_ROGOFF_CRISES) >= 25
        countries = set(c.country for c in REINHART_ROGOFF_CRISES)
        assert "GBR" in countries
        assert "DEU" in countries
        assert "FRA" in countries
        assert "JPN" in countries

    def test_multicountry_validator(self):
        from grri_mac.backtest.multicountry_validation import (
            MultiCountryValidator,
        )
        validator = MultiCountryValidator()
        result = validator.validate()  # Uses synthetic proxies
        assert result.countries_tested == 4
        assert result.total_crises > 0
        assert 0.0 <= result.overall_detection_rate <= 1.0

    def test_format_report(self):
        from grri_mac.backtest.multicountry_validation import (
            run_multicountry_validation,
            format_multicountry_report,
        )
        result = run_multicountry_validation()
        report = format_multicountry_report(result)
        assert "MULTI-COUNTRY" in report
        assert "GBR" in report


class TestDocumentation:
    """WP 5.2: Documentation files exist and have content."""

    def test_decision_matrix_exists(self):
        path = os.path.join(
            os.path.dirname(__file__),
            "docs", "decision_matrix.md",
        )
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "Decision Matrix" in content
        assert "Sovereign Wealth Fund" in content

    def test_data_quality_exists(self):
        path = os.path.join(
            os.path.dirname(__file__),
            "docs", "data_quality.md",
        )
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "Reliability" in content

    def test_hedge_failure_caveat_exists(self):
        path = os.path.join(
            os.path.dirname(__file__),
            "docs", "hedge_failure_caveat.md",
        )
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "Bayesian" in content
        assert "N=9" in content


# ═══════════════════════════════════════════════════════════════════════════
# Integration: existing tests still pass
# ═══════════════════════════════════════════════════════════════════════════


class TestRegressionSafety:
    """Ensure new code doesn't break existing modules."""

    def test_import_composite(self):
        from grri_mac.mac.composite import MACResult
        assert hasattr(MACResult, "ci_80")
        assert hasattr(MACResult, "hmm_fragile_prob")

    def test_import_scenarios(self):
        from grri_mac.backtest.scenarios import KNOWN_EVENTS
        # Original 14 scenarios still present
        assert "lehman_2008" in KNOWN_EVENTS
        assert "covid_crash_2020" in KNOWN_EVENTS

    def test_import_crisis_events(self):
        from grri_mac.backtest.crisis_events import (
            get_crisis_for_date,
            get_major_crises,
        )
        gfc = get_crisis_for_date(datetime(2008, 10, 1))
        assert gfc is not None
        majors = get_major_crises()
        assert len(majors) > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

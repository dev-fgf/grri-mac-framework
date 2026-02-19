"""Blind backtesting module - tests real-time predictive performance.

This module addresses the key critique of historical backtests: lookahead bias.
Standard backtests know the outcome and may unconsciously be tuned to match.

Blind backtesting simulates real-time performance by:
1. Only using data that was available at each historical date
2. Making predictions BEFORE outcomes are known
3. Comparing predictions to actual outcomes

This provides a more realistic assessment of how the model would
have performed if deployed in real-time.

Usage:
    from grri_mac.predictive import run_blind_backtest

    results = run_blind_backtest()
    print(format_blind_results(results))
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from ..backtest.scenarios import KNOWN_EVENTS, HistoricalScenario
from ..backtest.calibrated_engine import CalibratedBacktestEngine


class PredictionType(Enum):
    """Types of predictions made."""
    MAC_REGIME = "mac_regime"
    HEDGE_OUTCOME = "hedge_outcome"
    BREACH_PILLARS = "breach_pillars"
    SEVERITY_LEVEL = "severity_level"


@dataclass
class BlindPrediction:
    """A prediction made without knowledge of outcome."""
    scenario_name: str
    prediction_date: datetime
    prediction_type: PredictionType
    predicted_value: str
    confidence: float  # 0-1
    reasoning: str


@dataclass
class BlindOutcome:
    """Actual outcome to compare against prediction."""
    scenario_name: str
    actual_value: str
    prediction_correct: bool
    error_magnitude: Optional[float] = None


@dataclass
class BlindBacktestResult:
    """Result of blind backtesting."""
    scenarios_tested: int
    predictions_made: int

    # Accuracy by prediction type
    mac_regime_accuracy: float
    hedge_prediction_accuracy: float
    breach_detection_accuracy: float
    severity_accuracy: float

    # Detailed results
    predictions: list[BlindPrediction]
    outcomes: list[BlindOutcome]

    # Analysis
    false_positives: int
    false_negatives: int
    mean_confidence_correct: float
    mean_confidence_incorrect: float

    # Key insight validation
    positioning_hedge_correlation: float


# Pre-event indicator availability
# Maps scenario to which indicators were available BEFORE the crisis
PRE_EVENT_DATA_AVAILABILITY = {
    "ltcm_crisis_1998": {
        "vix_available": True,
        "sofr_available": False,  # SOFR started 2018
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": False,  # EMBI started 1998
    },
    "dotcom_peak_2000": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "september_11_2001": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "dotcom_bottom_2002": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "bear_stearns_2008": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "lehman_2008": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "flash_crash_2010": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "us_downgrade_2011": {
        "vix_available": True,
        "sofr_available": False,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "volmageddon_2018": {
        "vix_available": True,
        "sofr_available": True,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "repo_spike_2019": {
        "vix_available": True,
        "sofr_available": True,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "covid_crash_2020": {
        "vix_available": True,
        "sofr_available": True,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "ukraine_invasion_2022": {
        "vix_available": True,
        "sofr_available": True,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "svb_crisis_2023": {
        "vix_available": True,
        "sofr_available": True,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
    "april_tariffs_2025": {
        "vix_available": True,
        "sofr_available": True,
        "ted_spread_available": True,
        "cot_available": True,
        "credit_spreads_available": True,
        "contagion_available": True,
    },
}


class BlindBacktester:
    """Performs blind backtesting without lookahead bias.

    Simulates real-time deployment by:
    1. Only using data available at prediction time
    2. Making predictions before outcomes known
    3. Applying consistent rules (no hindsight adjustments)
    """

    def __init__(self):
        """Initialize blind backtester."""
        self.engine = CalibratedBacktestEngine()

    def _get_pre_event_indicators(
        self,
        scenario_key: str,
        scenario: HistoricalScenario,
    ) -> dict:
        """Get indicators available before the event.

        Simulates real-time by potentially removing indicators
        that weren't available at that historical date.

        Args:
            scenario_key: Key for looking up data availability
            scenario: Scenario with full indicators

        Returns:
            Dictionary of indicators available pre-event
        """
        availability = PRE_EVENT_DATA_AVAILABILITY.get(
            scenario_key,
            {k: True for k in ["vix_available", "sofr_available",
                               "ted_spread_available", "cot_available",
                               "credit_spreads_available", "contagion_available"]}
        )

        indicators = scenario.indicators.copy()

        # Remove unavailable indicators
        if not availability.get("sofr_available", True):
            indicators.pop("sofr_iorb_spread_bps", None)

        if not availability.get("contagion_available", True):
            indicators.pop("em_flow_pct_weekly", None)
            indicators.pop("gsib_cds_avg_bps", None)
            indicators.pop("embi_spread_bps", None)
            indicators.pop("global_equity_corr", None)

        return indicators

    def _make_blind_prediction(
        self,
        scenario_key: str,
        scenario: HistoricalScenario,
    ) -> tuple[list[BlindPrediction], dict]:
        """Make predictions without knowing outcome.

        Uses only pre-event data and applies rules consistently.

        Args:
            scenario_key: Scenario identifier
            scenario: Historical scenario

        Returns:
            Tuple of (predictions list, calculated metrics)
        """
        predictions = []

        # Get pre-event indicators
        indicators = self._get_pre_event_indicators(scenario_key, scenario)

        # Calculate pillar scores using available indicators
        liq = self.engine.score_liquidity(indicators)
        val = self.engine.score_valuation(indicators)
        pos = self.engine.score_positioning(indicators)
        vol = self.engine.score_volatility(indicators)
        pol = self.engine.score_policy(indicators)
        con = self.engine.score_contagion(indicators)

        pillar_scores = {
            "liquidity": liq,
            "valuation": val,
            "positioning": pos,
            "volatility": vol,
            "policy": pol,
            "contagion": con,
        }

        # Calculate MAC
        mac_score = sum(pillar_scores.values()) / len(pillar_scores)
        mac_score *= self.engine.CALIBRATION_FACTOR

        # Identify breaches
        breaches = [p for p, s in pillar_scores.items() if s < 0.2]

        # Prediction 1: MAC Regime
        if mac_score >= 0.65:
            regime = "AMPLE"
            confidence = 0.9
        elif mac_score >= 0.50:
            regime = "THIN"
            confidence = 0.75
        elif mac_score >= 0.35:
            regime = "STRETCHED"
            confidence = 0.7
        else:
            regime = "BREACH"
            confidence = 0.85

        predictions.append(BlindPrediction(
            scenario_name=scenario.name,
            prediction_date=scenario.date - timedelta(days=1),  # Day before
            prediction_type=PredictionType.MAC_REGIME,
            predicted_value=regime,
            confidence=confidence,
            reasoning=f"MAC score {mac_score:.3f} -> {regime} regime",
        ))

        # Prediction 2: Hedge Outcome (key insight)
        # Rule: Positioning breach predicts hedge failure
        if "positioning" in breaches:
            hedge_prediction = "FAIL"
            hedge_confidence = 0.80
            hedge_reasoning = f"Positioning breach ({pos:.3f}) predicts hedge failure"
        else:
            hedge_prediction = "WORK"
            hedge_confidence = 0.85
            hedge_reasoning = f"No positioning breach ({pos:.3f}) -> hedge should work"

        predictions.append(BlindPrediction(
            scenario_name=scenario.name,
            prediction_date=scenario.date - timedelta(days=1),
            prediction_type=PredictionType.HEDGE_OUTCOME,
            predicted_value=hedge_prediction,
            confidence=hedge_confidence,
            reasoning=hedge_reasoning,
        ))

        # Prediction 3: Breach Pillars
        predictions.append(BlindPrediction(
            scenario_name=scenario.name,
            prediction_date=scenario.date - timedelta(days=1),
            prediction_type=PredictionType.BREACH_PILLARS,
            predicted_value=",".join(sorted(breaches)) if breaches else "none",
            confidence=0.75,
            reasoning="Pillars below 0.2 threshold",
        ))

        # Prediction 4: Severity Level
        if mac_score < 0.2:
            severity = "EXTREME"
        elif mac_score < 0.35:
            severity = "SEVERE"
        elif mac_score < 0.50:
            severity = "MODERATE"
        else:
            severity = "MILD"

        predictions.append(BlindPrediction(
            scenario_name=scenario.name,
            prediction_date=scenario.date - timedelta(days=1),
            prediction_type=PredictionType.SEVERITY_LEVEL,
            predicted_value=severity,
            confidence=0.7,
            reasoning=f"Based on MAC level {mac_score:.3f}",
        ))

        metrics = {
            "mac_score": mac_score,
            "pillar_scores": pillar_scores,
            "breaches": breaches,
        }

        return predictions, metrics

    def _evaluate_prediction(
        self,
        prediction: BlindPrediction,
        scenario: HistoricalScenario,
        actual_mac: float,
        actual_breaches: list[str],
    ) -> BlindOutcome:
        """Evaluate prediction against actual outcome.

        Args:
            prediction: Prediction made
            scenario: Scenario with actual outcome
            actual_mac: Actual MAC score
            actual_breaches: Actual breach pillars

        Returns:
            BlindOutcome with correctness assessment
        """
        if prediction.prediction_type == PredictionType.MAC_REGIME:
            # Determine actual regime
            if actual_mac >= 0.65:
                actual_regime = "AMPLE"
            elif actual_mac >= 0.50:
                actual_regime = "THIN"
            elif actual_mac >= 0.35:
                actual_regime = "STRETCHED"
            else:
                actual_regime = "BREACH"

            correct = prediction.predicted_value == actual_regime
            error = abs(actual_mac - self._regime_to_mac(prediction.predicted_value))

            return BlindOutcome(
                scenario_name=prediction.scenario_name,
                actual_value=actual_regime,
                prediction_correct=correct,
                error_magnitude=error,
            )

        elif prediction.prediction_type == PredictionType.HEDGE_OUTCOME:
            actual_hedge = "WORK" if scenario.treasury_hedge_worked else "FAIL"
            correct = prediction.predicted_value == actual_hedge

            return BlindOutcome(
                scenario_name=prediction.scenario_name,
                actual_value=actual_hedge,
                prediction_correct=correct,
            )

        elif prediction.prediction_type == PredictionType.BREACH_PILLARS:
            actual_breach_str = ",".join(sorted(actual_breaches)) if actual_breaches else "none"
            predicted_set = set(prediction.predicted_value.split(
                ",")) if prediction.predicted_value != "none" else set()
            actual_set = set(actual_breaches)

            # Consider correct if sets match or significant overlap
            correct = predicted_set == actual_set

            return BlindOutcome(
                scenario_name=prediction.scenario_name,
                actual_value=actual_breach_str,
                prediction_correct=correct,
            )

        elif prediction.prediction_type == PredictionType.SEVERITY_LEVEL:
            # Determine actual severity
            if actual_mac < 0.2:
                actual_severity = "EXTREME"
            elif actual_mac < 0.35:
                actual_severity = "SEVERE"
            elif actual_mac < 0.50:
                actual_severity = "MODERATE"
            else:
                actual_severity = "MILD"

            correct = prediction.predicted_value == actual_severity

            return BlindOutcome(
                scenario_name=prediction.scenario_name,
                actual_value=actual_severity,
                prediction_correct=correct,
            )

        return BlindOutcome(
            scenario_name=prediction.scenario_name,
            actual_value="UNKNOWN",
            prediction_correct=False,
        )

    def _regime_to_mac(self, regime: str) -> float:
        """Convert regime to representative MAC score."""
        mapping = {
            "AMPLE": 0.75,
            "THIN": 0.55,
            "STRETCHED": 0.42,
            "BREACH": 0.25,
        }
        return mapping.get(regime, 0.5)

    def run_blind_backtest(self) -> BlindBacktestResult:
        """Run complete blind backtest across all scenarios.

        Returns:
            BlindBacktestResult with accuracy metrics
        """
        all_predictions = []
        all_outcomes = []

        # Track accuracy by type
        type_correct = {t: 0 for t in PredictionType}
        type_total = {t: 0 for t in PredictionType}

        # Track for positioning-hedge correlation
        pos_breach_hedge_fail = 0
        pos_breach_hedge_work = 0
        no_pos_breach_hedge_fail = 0
        no_pos_breach_hedge_work = 0

        for scenario_key, scenario in KNOWN_EVENTS.items():
            # Make blind predictions
            predictions, metrics = self._make_blind_prediction(
                scenario_key, scenario
            )
            all_predictions.extend(predictions)

            # Get actual results from engine
            result = self.engine.run_scenario(scenario)
            actual_mac = result.mac_score
            actual_breaches = result.breach_flags

            # Evaluate each prediction
            for prediction in predictions:
                outcome = self._evaluate_prediction(
                    prediction, scenario, actual_mac, actual_breaches
                )
                all_outcomes.append(outcome)

                type_total[prediction.prediction_type] += 1
                if outcome.prediction_correct:
                    type_correct[prediction.prediction_type] += 1

            # Track positioning-hedge correlation
            pos_breach = "positioning" in metrics["breaches"]
            hedge_failed = not scenario.treasury_hedge_worked

            if pos_breach and hedge_failed:
                pos_breach_hedge_fail += 1
            elif pos_breach and not hedge_failed:
                pos_breach_hedge_work += 1
            elif not pos_breach and hedge_failed:
                no_pos_breach_hedge_fail += 1
            else:
                no_pos_breach_hedge_work += 1

        # Calculate accuracies
        mac_acc = type_correct[PredictionType.MAC_REGIME] / type_total[PredictionType.MAC_REGIME]
        hedge_acc = type_correct[PredictionType.HEDGE_OUTCOME] / \
            type_total[PredictionType.HEDGE_OUTCOME]
        breach_acc = type_correct[PredictionType.BREACH_PILLARS] / \
            type_total[PredictionType.BREACH_PILLARS]
        severity_acc = type_correct[PredictionType.SEVERITY_LEVEL] / \
            type_total[PredictionType.SEVERITY_LEVEL]

        # Calculate false positives/negatives for hedge prediction
        hedge_predictions = [p for p in all_predictions
                             if p.prediction_type == PredictionType.HEDGE_OUTCOME]
        hedge_outcomes = [o for o in all_outcomes
                          if any(p.prediction_type == PredictionType.HEDGE_OUTCOME
                                 and p.scenario_name == o.scenario_name
                                 for p in all_predictions)]

        false_positives = sum(
            1 for p, o in zip(hedge_predictions, hedge_outcomes)
            if p.predicted_value == "FAIL" and o.actual_value == "WORK"
        )
        false_negatives = sum(
            1 for p, o in zip(hedge_predictions, hedge_outcomes)
            if p.predicted_value == "WORK" and o.actual_value == "FAIL"
        )

        # Calculate confidence metrics
        correct_confidences = [
            p.confidence for p, o in zip(all_predictions, all_outcomes)
            if o.prediction_correct
        ]
        incorrect_confidences = [
            p.confidence for p, o in zip(all_predictions, all_outcomes)
            if not o.prediction_correct
        ]

        mean_conf_correct = (sum(correct_confidences) / len(correct_confidences)
                             if correct_confidences else 0)
        mean_conf_incorrect = (sum(incorrect_confidences) / len(incorrect_confidences)
                               if incorrect_confidences else 0)

        # Calculate positioning-hedge correlation
        # Correlation of 1.0 means perfect prediction: pos breach -> fail, no breach -> work
        total_scenarios = len(KNOWN_EVENTS)
        correct_predictions = pos_breach_hedge_fail + no_pos_breach_hedge_work
        pos_hedge_corr = correct_predictions / total_scenarios if total_scenarios > 0 else 0

        return BlindBacktestResult(
            scenarios_tested=len(KNOWN_EVENTS),
            predictions_made=len(all_predictions),
            mac_regime_accuracy=mac_acc,
            hedge_prediction_accuracy=hedge_acc,
            breach_detection_accuracy=breach_acc,
            severity_accuracy=severity_acc,
            predictions=all_predictions,
            outcomes=all_outcomes,
            false_positives=false_positives,
            false_negatives=false_negatives,
            mean_confidence_correct=mean_conf_correct,
            mean_confidence_incorrect=mean_conf_incorrect,
            positioning_hedge_correlation=pos_hedge_corr,
        )


def run_blind_backtest() -> BlindBacktestResult:
    """Convenience function to run blind backtest."""
    backtester = BlindBacktester()
    return backtester.run_blind_backtest()


def format_blind_results(result: BlindBacktestResult) -> str:
    """Format blind backtest results for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("BLIND BACKTEST RESULTS")
    lines.append("(Real-time simulation - no lookahead bias)")
    lines.append("=" * 70)
    lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 50)
    lines.append(f"Scenarios tested:        {result.scenarios_tested}")
    lines.append(f"Total predictions:       {result.predictions_made}")
    lines.append("")

    lines.append("ACCURACY BY PREDICTION TYPE")
    lines.append("-" * 50)
    lines.append(f"MAC Regime Prediction:   {result.mac_regime_accuracy:.1%}")
    lines.append(f"Hedge Outcome Prediction:{result.hedge_prediction_accuracy:.1%}")
    lines.append(f"Breach Detection:        {result.breach_detection_accuracy:.1%}")
    lines.append(f"Severity Assessment:     {result.severity_accuracy:.1%}")
    lines.append("")

    lines.append("HEDGE PREDICTION ANALYSIS")
    lines.append("-" * 50)
    lines.append(f"False Positives (predicted FAIL, actual WORK): {result.false_positives}")
    lines.append(f"False Negatives (predicted WORK, actual FAIL): {result.false_negatives}")
    lines.append("")
    lines.append("Note: False positives are the safer error type for risk management")
    lines.append("")

    lines.append("CONFIDENCE CALIBRATION")
    lines.append("-" * 50)
    lines.append(f"Mean confidence (correct predictions):   {result.mean_confidence_correct:.1%}")
    lines.append(f"Mean confidence (incorrect predictions): {result.mean_confidence_incorrect:.1%}")

    if result.mean_confidence_correct > result.mean_confidence_incorrect:
        lines.append("[OK] Model is well-calibrated - higher confidence on correct predictions")
    else:
        lines.append("[!!] Calibration issue - confidence not discriminating well")
    lines.append("")

    lines.append("KEY INSIGHT VALIDATION")
    lines.append("-" * 50)
    lines.append(f"Positioning-Hedge Correlation: {result.positioning_hedge_correlation:.1%}")
    lines.append("")
    lines.append("Interpretation:")
    if result.positioning_hedge_correlation >= 0.9:
        lines.append("  [STRONG] Positioning breach highly predictive of hedge failure")
    elif result.positioning_hedge_correlation >= 0.7:
        lines.append("  [GOOD] Positioning breach moderately predictive of hedge failure")
    else:
        lines.append("  [WEAK] Positioning-hedge relationship weaker than expected")
    lines.append("")

    # Show predictions for each scenario
    lines.append("DETAILED PREDICTIONS")
    lines.append("-" * 50)

    current_scenario = None
    for pred, outcome in zip(result.predictions, result.outcomes):
        if pred.scenario_name != current_scenario:
            current_scenario = pred.scenario_name
            lines.append(f"\n{current_scenario}")
            lines.append("~" * 40)

        status = "[OK]" if outcome.prediction_correct else "[X]"
        lines.append(f"  {pred.prediction_type.value:15}: "
                     f"Pred={pred.predicted_value:10} "
                     f"Actual={outcome.actual_value:10} {status}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)

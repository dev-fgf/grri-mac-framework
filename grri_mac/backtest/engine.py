"""Backtesting engine for MAC framework."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .scenarios import HistoricalScenario, KNOWN_EVENTS
from ..pillars.liquidity import LiquidityPillar, LiquidityIndicators
from ..pillars.valuation import ValuationPillar, ValuationIndicators
from ..pillars.positioning import PositioningPillar, PositioningIndicators
from ..pillars.volatility import VolatilityPillar, VolatilityIndicators
from ..pillars.policy import PolicyPillar, PolicyIndicators
from ..mac.composite import calculate_mac, MACResult
from ..mac.multiplier import mac_to_multiplier


@dataclass
class BacktestResult:
    """Result of a single backtest run."""

    scenario_name: str
    scenario_date: datetime
    mac_score: float
    multiplier: Optional[float]
    pillar_scores: dict[str, float]
    breach_flags: list[str]

    # Validation
    expected_mac_range: tuple[float, float]
    mac_in_range: bool
    expected_breaches: list[str]
    breaches_match: bool
    treasury_hedge_worked: bool
    hedge_prediction_correct: bool

    # Analysis
    key_insight: str = ""
    calibration_notes: list[str] = field(default_factory=list)


@dataclass
class BacktestSummary:
    """Summary of backtest run across multiple scenarios."""

    total_scenarios: int
    passed: int
    failed: int
    mac_range_accuracy: float
    breach_accuracy: float
    hedge_prediction_accuracy: float
    results: list[BacktestResult]


class BacktestEngine:
    """Engine for backtesting MAC framework against historical events."""

    def __init__(self):
        """Initialize backtest engine."""
        self.liquidity = LiquidityPillar()
        self.valuation = ValuationPillar()
        self.positioning = PositioningPillar()
        self.volatility = VolatilityPillar()
        self.policy = PolicyPillar()

    def run_scenario(self, scenario: HistoricalScenario) -> BacktestResult:
        """
        Run backtest for a single scenario.

        Args:
            scenario: Historical scenario to test

        Returns:
            BacktestResult with validation metrics
        """
        indicators = scenario.indicators

        # Build indicator objects from scenario data
        liquidity_ind = LiquidityIndicators(
            sofr_iorb_spread_bps=indicators.get("sofr_iorb_spread_bps"),
            cp_treasury_spread_bps=indicators.get("cp_treasury_spread_bps"),
            cross_currency_basis_bps=indicators.get("cross_currency_basis_bps"),
            treasury_bid_ask_32nds=indicators.get("treasury_bid_ask_32nds"),
        )

        valuation_ind = ValuationIndicators(
            term_premium_10y_bps=indicators.get("term_premium_10y_bps"),
            ig_oas_bps=indicators.get("ig_oas_bps"),
            hy_oas_bps=indicators.get("hy_oas_bps"),
        )

        positioning_ind = PositioningIndicators(
            basis_trade_size_billions=indicators.get("basis_trade_size_billions"),
            treasury_spec_net_percentile=indicators.get("treasury_spec_net_percentile"),
            svxy_aum_millions=indicators.get("svxy_aum_millions"),
        )

        volatility_ind = VolatilityIndicators(
            vix_level=indicators.get("vix_level"),
            vix_term_structure=indicators.get("vix_term_structure"),
            realized_vol=indicators.get("realized_vol"),
            implied_vol=indicators.get("vix_level"),  # Use VIX as IV proxy
        )

        policy_ind = PolicyIndicators(
            policy_room_bps=indicators.get("policy_room_bps"),
            fed_balance_sheet_gdp_pct=indicators.get("fed_balance_sheet_gdp_pct"),
            core_pce_vs_target_bps=indicators.get("core_pce_vs_target_bps"),
        )

        # Calculate pillar scores
        liquidity_scores = self.liquidity.calculate(liquidity_ind)
        valuation_scores = self.valuation.calculate(valuation_ind)
        positioning_scores = self.positioning.calculate(positioning_ind)
        volatility_scores = self.volatility.calculate(volatility_ind)
        policy_scores = self.policy.calculate(policy_ind)

        pillar_scores = {
            "liquidity": liquidity_scores.composite,
            "valuation": valuation_scores.composite,
            "positioning": positioning_scores.composite,
            "volatility": volatility_scores.composite,
            "policy": policy_scores.composite,
        }

        # Calculate MAC
        mac_result = calculate_mac(pillar_scores)
        mult_result = mac_to_multiplier(mac_result.mac_score)

        # Validate against expectations
        mac_in_range = (
            scenario.expected_mac_range[0]
            <= mac_result.mac_score
            <= scenario.expected_mac_range[1]
        )

        expected_set = set(scenario.expected_breaches)
        actual_set = set(mac_result.breach_flags)
        breaches_match = expected_set == actual_set

        # Key insight: Positioning breach predicts Treasury hedge failure
        positioning_breaching = "positioning" in mac_result.breach_flags
        hedge_prediction_correct = (
            positioning_breaching == (not scenario.treasury_hedge_worked)
        )

        # Generate calibration notes
        calibration_notes = []
        if not mac_in_range:
            diff = mac_result.mac_score - sum(scenario.expected_mac_range) / 2
            direction = "high" if diff > 0 else "low"
            calibration_notes.append(
                f"MAC {direction} by {abs(diff):.2f} - adjust thresholds"
            )

        if not breaches_match:
            missing = expected_set - actual_set
            extra = actual_set - expected_set
            if missing:
                calibration_notes.append(f"Missing breaches: {missing}")
            if extra:
                calibration_notes.append(f"Unexpected breaches: {extra}")

        # Generate key insight
        if scenario.treasury_hedge_worked:
            key_insight = "Treasury hedge worked - buffers absorbed shock"
        else:
            if positioning_breaching:
                key_insight = "Treasury hedge FAILED - positioning breach caused forced selling"
            else:
                key_insight = "Treasury hedge FAILED - other factors at play"

        return BacktestResult(
            scenario_name=scenario.name,
            scenario_date=scenario.date,
            mac_score=mac_result.mac_score,
            multiplier=mult_result.multiplier,
            pillar_scores=pillar_scores,
            breach_flags=mac_result.breach_flags,
            expected_mac_range=scenario.expected_mac_range,
            mac_in_range=mac_in_range,
            expected_breaches=scenario.expected_breaches,
            breaches_match=breaches_match,
            treasury_hedge_worked=scenario.treasury_hedge_worked,
            hedge_prediction_correct=hedge_prediction_correct,
            key_insight=key_insight,
            calibration_notes=calibration_notes,
        )

    def run_all_scenarios(
        self,
        scenarios: Optional[dict[str, HistoricalScenario]] = None,
    ) -> BacktestSummary:
        """
        Run backtest across all scenarios.

        Args:
            scenarios: Dict of scenarios (defaults to KNOWN_EVENTS)

        Returns:
            BacktestSummary with aggregate results
        """
        if scenarios is None:
            scenarios = KNOWN_EVENTS

        results = []
        passed = 0
        mac_correct = 0
        breach_correct = 0
        hedge_correct = 0

        for name, scenario in scenarios.items():
            result = self.run_scenario(scenario)
            results.append(result)

            # Count successes
            if result.mac_in_range and result.breaches_match and result.hedge_prediction_correct:
                passed += 1

            if result.mac_in_range:
                mac_correct += 1
            if result.breaches_match:
                breach_correct += 1
            if result.hedge_prediction_correct:
                hedge_correct += 1

        total = len(scenarios)

        return BacktestSummary(
            total_scenarios=total,
            passed=passed,
            failed=total - passed,
            mac_range_accuracy=mac_correct / total if total > 0 else 0,
            breach_accuracy=breach_correct / total if total > 0 else 0,
            hedge_prediction_accuracy=hedge_correct / total if total > 0 else 0,
            results=results,
        )


def format_backtest_result(result: BacktestResult) -> str:
    """Format a single backtest result."""
    lines = []
    lines.append(f"SCENARIO: {result.scenario_name} ({result.scenario_date.strftime('%Y-%m-%d')})")
    lines.append("-" * 50)

    # MAC Score
    mac_status = "PASS" if result.mac_in_range else "FAIL"
    expected_mid = sum(result.expected_mac_range) / 2
    lines.append(
        f"MAC Score:    {result.mac_score:.3f} "
        f"(expected ~{expected_mid:.2f}) [{mac_status}]"
    )

    # Multiplier
    if result.multiplier:
        lines.append(f"Multiplier:   {result.multiplier:.2f}x")
    else:
        lines.append("Multiplier:   REGIME BREAK")

    # Pillar breakdown
    lines.append("\nPillar Scores:")
    for pillar, score in result.pillar_scores.items():
        breach = " [BREACH]" if pillar in result.breach_flags else ""
        lines.append(f"  {pillar.capitalize():12} {score:.3f}{breach}")

    # Breach validation
    breach_status = "PASS" if result.breaches_match else "FAIL"
    lines.append(
        f"\nBreaches:     {result.breach_flags} "
        f"(expected {result.expected_breaches}) [{breach_status}]"
    )

    # Hedge prediction
    hedge_status = "PASS" if result.hedge_prediction_correct else "FAIL"
    hedge_outcome = "Worked" if result.treasury_hedge_worked else "FAILED"
    lines.append(f"Treasury Hedge: {hedge_outcome} [{hedge_status}]")

    # Key insight
    lines.append(f"\nInsight: {result.key_insight}")

    # Calibration notes
    if result.calibration_notes:
        lines.append("\nCalibration Notes:")
        for note in result.calibration_notes:
            lines.append(f"  - {note}")

    # Overall
    all_pass = result.mac_in_range and result.breaches_match and result.hedge_prediction_correct
    lines.append(f"\nOVERALL: {'PASS' if all_pass else 'FAIL'}")

    return "\n".join(lines)


def format_backtest_summary(summary: BacktestSummary) -> str:
    """Format backtest summary."""
    lines = []
    lines.append("=" * 70)
    lines.append("MAC FRAMEWORK BACKTEST REPORT")
    lines.append("=" * 70)

    # Individual results
    for result in summary.results:
        lines.append("")
        lines.append(format_backtest_result(result))

    # Summary
    lines.append("")
    lines.append("=" * 70)
    lines.append("SUMMARY")
    lines.append("=" * 70)
    lines.append(f"Total Scenarios:        {summary.total_scenarios}")
    lines.append(f"Passed:                 {summary.passed}")
    lines.append(f"Failed:                 {summary.failed}")
    lines.append(f"MAC Range Accuracy:     {summary.mac_range_accuracy:.1%}")
    lines.append(f"Breach Accuracy:        {summary.breach_accuracy:.1%}")
    lines.append(f"Hedge Prediction:       {summary.hedge_prediction_accuracy:.1%}")

    # Key insight validation
    lines.append("")
    lines.append("KEY INSIGHT VALIDATION")
    lines.append("-" * 50)
    lines.append("Hypothesis: Positioning breach predicts Treasury hedge failure")

    hedge_failures = [r for r in summary.results if not r.treasury_hedge_worked]
    positioning_breaches_in_failures = sum(
        1 for r in hedge_failures if "positioning" in r.breach_flags
    )
    lines.append(
        f"Treasury hedge failures: {len(hedge_failures)} events"
    )
    lines.append(
        f"With positioning breach:  {positioning_breaches_in_failures} "
        f"({positioning_breaches_in_failures/len(hedge_failures)*100:.0f}% correlation)"
        if hedge_failures else ""
    )

    lines.append("=" * 70)

    return "\n".join(lines)

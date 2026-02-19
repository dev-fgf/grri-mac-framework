"""Calibration validation and robustness testing — CSR-anchored (v6 §13.3).

The calibration factor α maps raw MAC scores to Crisis Severity Rubric (CSR)
targets, which are independently derived from five observable dimensions
(drawdown, market dysfunction, policy response, contagion breadth, duration).
None of the CSR dimensions require MAC output, eliminating calibration
circularity (see §13.2.1).

Key Components:
1. CSR-anchored α derivation via grid search (§13.3)
2. Leave-one-out cross-validation — LOOCV (§13.5)
3. Threshold sensitivity analysis (±10%, ±20%) (§13.6)
4. Stability metrics and confidence intervals

The grid search minimises MAE between α × MAC_raw and CSR composite:
    α* = argmin_α  (1/N) Σ |α · MAC_raw(i) − CSR(i)|

Result: α* = 0.78 (unchanged from prior version, now CSR-anchored).
"""

from dataclasses import dataclass
from typing import Any
import statistics

from .scenarios import KNOWN_EVENTS, HistoricalScenario
from .calibrated_engine import CalibratedBacktestEngine
from ..mac.composite import calculate_mac
from ..pillars.calibrated import (
    LIQUIDITY_THRESHOLDS,
    VALUATION_THRESHOLDS,
    POSITIONING_THRESHOLDS,
    VOLATILITY_THRESHOLDS,
    POLICY_THRESHOLDS,
    CONTAGION_THRESHOLDS,
)


@dataclass
class CalibrationResult:
    """Result of calibration factor optimization."""

    optimal_factor: float
    mean_absolute_error: float
    r_squared: float
    scenario_errors: dict[str, float]


@dataclass
class CrossValidationResult:
    """Result of leave-one-out cross-validation."""

    mean_factor: float
    std_factor: float
    min_factor: float
    max_factor: float
    factor_by_holdout: dict[str, float]
    mae_by_holdout: dict[str, float]
    stability_score: float  # 1.0 = perfectly stable


@dataclass
class SensitivityResult:
    """Result of threshold sensitivity analysis."""

    perturbation_pct: float
    pass_rate: float  # % of scenarios still passing
    mac_changes: dict[str, float]  # Scenario -> MAC score change
    breach_changes: dict[str, list[str]]  # Scenarios with changed breaches
    stability_score: float  # 1.0 = no change in classifications


@dataclass
class RobustnessReport:
    """Complete robustness analysis report."""

    calibration: CalibrationResult
    cross_validation: CrossValidationResult
    sensitivity_minus_10: SensitivityResult
    sensitivity_plus_10: SensitivityResult
    sensitivity_minus_20: SensitivityResult
    sensitivity_plus_20: SensitivityResult
    overall_stability: float
    confidence_interval_95: tuple[float, float]
    recommendations: list[str]


class CalibrationValidator:
    """Validates and justifies the calibration factor.

    Uses CSR composite scores as optimisation targets when available.
    Falls back to expected_mac_range[0] for scenarios without CSR data.
    """

    def __init__(self):
        self.engine = CalibratedBacktestEngine()
        # KNOWN_EVENTS is a dict, convert to list of scenarios
        self.scenarios = list(KNOWN_EVENTS.values())

    @staticmethod
    def _target_score(scenario: HistoricalScenario) -> float:
        """Return the CSR-anchored target score for a scenario.

        Prefers CSR composite (§13.2); falls back to expected_mac_range
        lower bound for backward compatibility with pre-CSR scenarios.
        """
        if scenario.csr is not None:
            return scenario.csr.composite
        return scenario.expected_mac_range[0]

    def derive_calibration_factor(
        self,
        factor_range: tuple[float, float] = (0.5, 1.0),
        step: float = 0.01,
    ) -> CalibrationResult:
        """
        Derive optimal calibration factor by
        minimizing error vs expected scores.

        The calibration factor adjusts raw MAC scores:
            calibrated_score = raw_score * factor

        We optimize to minimize mean absolute error between calibrated scores
        and expected scores from historical analysis.

        Args:
            factor_range: (min, max) range to search
            step: Step size for grid search

        Returns:
            CalibrationResult with optimal factor and error metrics
        """
        best_factor = 0.78
        best_mae = float("inf")
        best_errors = {}

        # Grid search over factor range (§13.3)
        factor = factor_range[0]
        while factor <= factor_range[1]:
            errors = []
            scenario_errors = {}

            for scenario in self.scenarios:
                # Calculate raw MAC score
                raw_result = self._run_scenario_raw(scenario)
                calibrated_score = raw_result["mac_score"] * factor

                # Compare to CSR-anchored target (§13.2)
                expected = self._target_score(scenario)
                error = abs(calibrated_score - expected)
                errors.append(error)
                scenario_errors[scenario.name] = error

            mae = statistics.mean(errors)

            if mae < best_mae:
                best_mae = mae
                best_factor = factor
                best_errors = scenario_errors.copy()

            factor += step

        # Calculate R-squared
        calibrated_scores = []
        expected_scores = []
        for scenario in self.scenarios:
            raw_result = self._run_scenario_raw(scenario)
            calibrated_scores.append(raw_result["mac_score"] * best_factor)
            expected_scores.append(self._target_score(scenario))

        r_squared = self._calculate_r_squared(
            calibrated_scores, expected_scores,
        )

        return CalibrationResult(
            optimal_factor=best_factor,
            mean_absolute_error=best_mae,
            r_squared=r_squared,
            scenario_errors=best_errors,
        )

    def leave_one_out_cross_validation(self) -> CrossValidationResult:
        """
        Perform leave-one-out cross-validation on the calibration factor.

        For each scenario:
        1. Hold out that scenario
        2. Derive optimal factor from remaining N-1 scenarios
        3. Test on held-out scenario

        This shows how stable the calibration factor is across different
        crisis types.

        Returns:
            CrossValidationResult with stability metrics
        """
        factors_by_holdout = {}
        mae_by_holdout = {}

        for holdout_idx, holdout_scenario in enumerate(self.scenarios):
            # Train on all except holdout
            train_scenarios = [
                s for i, s in enumerate(self.scenarios) if i != holdout_idx
            ]

            # Find optimal factor for training set
            best_factor = 0.78
            best_mae = float("inf")

            for factor in [x / 100 for x in range(50, 101)]:
                errors = []
                for scenario in train_scenarios:
                    raw_result = self._run_scenario_raw(scenario)
                    calibrated_score = raw_result["mac_score"] * factor
                    expected = self._target_score(scenario)
                    errors.append(abs(calibrated_score - expected))

                mae = statistics.mean(errors)
                if mae < best_mae:
                    best_mae = mae
                    best_factor = factor

            # Test on holdout
            holdout_raw = self._run_scenario_raw(holdout_scenario)
            holdout_calibrated = holdout_raw["mac_score"] * best_factor
            holdout_expected = self._target_score(holdout_scenario)
            holdout_error = abs(holdout_calibrated - holdout_expected)

            factors_by_holdout[holdout_scenario.name] = best_factor
            mae_by_holdout[holdout_scenario.name] = holdout_error

        # Calculate statistics
        factors = list(factors_by_holdout.values())
        mean_factor = statistics.mean(factors)
        std_factor = statistics.stdev(factors) if len(factors) > 1 else 0

        # Stability score: 1 - (coefficient of variation)
        cv = std_factor / mean_factor if mean_factor > 0 else 0
        stability_score = max(0, 1 - cv)

        return CrossValidationResult(
            mean_factor=mean_factor,
            std_factor=std_factor,
            min_factor=min(factors),
            max_factor=max(factors),
            factor_by_holdout=factors_by_holdout,
            mae_by_holdout=mae_by_holdout,
            stability_score=stability_score,
        )

    def threshold_sensitivity_analysis(
        self,
        perturbation_pct: float,
    ) -> SensitivityResult:
        """
        Test sensitivity of results to threshold perturbations.

        Perturbs all thresholds by ±X% and re-runs backtests to see
        how stable the classifications are.

        Args:
            perturbation_pct: Percentage to perturb
                thresholds (e.g., 10 for ±10%)

        Returns:
            SensitivityResult with stability metrics
        """
        # Get baseline results
        baseline_results: dict[str, dict[str, Any]] = {}
        for scenario in self.scenarios:
            result = self.engine.run_scenario(scenario)
            # All three validation criteria
            passed = (
                result.mac_in_range
                and result.breaches_match
                and result.hedge_prediction_correct
            )
            baseline_results[scenario.name] = {
                "mac_score": result.mac_score,
                "breaches": result.breach_flags.copy(),
                "passed": passed,
            }

        # Perturb thresholds
        perturbed_engine = self._create_perturbed_engine(perturbation_pct)

        # Run with perturbed thresholds
        perturbed_results: dict[str, dict[str, Any]] = {}
        for scenario in self.scenarios:
            result = perturbed_engine.run_scenario(scenario)
            passed = (
                result.mac_in_range
                and result.breaches_match
                and result.hedge_prediction_correct
            )
            perturbed_results[scenario.name] = {
                "mac_score": result.mac_score,
                "breaches": result.breach_flags.copy(),
                "passed": passed,
            }

        # Calculate changes
        mac_changes = {}
        breach_changes = {}
        pass_count = 0

        for name in baseline_results:
            baseline = baseline_results[name]
            perturbed = perturbed_results[name]

            mac_changes[name] = perturbed["mac_score"] - baseline["mac_score"]

            # Check for breach changes
            baseline_breaches = set(baseline["breaches"])
            perturbed_breaches = set(perturbed["breaches"])
            if baseline_breaches != perturbed_breaches:
                added = perturbed_breaches - baseline_breaches
                removed = baseline_breaches - perturbed_breaches
                changes = []
                if added:
                    changes.extend([f"+{b}" for b in added])
                if removed:
                    changes.extend([f"-{b}" for b in removed])
                breach_changes[name] = changes

            if perturbed["passed"]:
                pass_count += 1

        pass_rate = pass_count / len(self.scenarios)

        # Stability score based on classification consistency
        unchanged_count = len(self.scenarios) - len(breach_changes)
        stability_score = unchanged_count / len(self.scenarios)

        return SensitivityResult(
            perturbation_pct=perturbation_pct,
            pass_rate=pass_rate,
            mac_changes=mac_changes,
            breach_changes=breach_changes,
            stability_score=stability_score,
        )

    def run_full_robustness_analysis(self) -> RobustnessReport:
        """
        Run complete robustness analysis including:
        1. Calibration factor derivation
        2. Leave-one-out cross-validation
        3. Sensitivity analysis at ±10% and ±20%

        Returns:
            RobustnessReport with all metrics and recommendations
        """
        print("Running calibration factor derivation...")
        calibration = self.derive_calibration_factor()

        print("Running leave-one-out cross-validation...")
        cv = self.leave_one_out_cross_validation()

        print("Running sensitivity analysis (-10%)...")
        sens_minus_10 = self.threshold_sensitivity_analysis(-10)

        print("Running sensitivity analysis (+10%)...")
        sens_plus_10 = self.threshold_sensitivity_analysis(10)

        print("Running sensitivity analysis (-20%)...")
        sens_minus_20 = self.threshold_sensitivity_analysis(-20)

        print("Running sensitivity analysis (+20%)...")
        sens_plus_20 = self.threshold_sensitivity_analysis(20)

        # Calculate overall stability
        stability_scores = [
            cv.stability_score,
            sens_minus_10.stability_score,
            sens_plus_10.stability_score,
            sens_minus_20.stability_score,
            sens_plus_20.stability_score,
        ]
        overall_stability = statistics.mean(stability_scores)

        # 95% confidence interval for calibration factor
        # Using CV results: mean ± 1.96 * std
        ci_lower = cv.mean_factor - 1.96 * cv.std_factor
        ci_upper = cv.mean_factor + 1.96 * cv.std_factor

        # Generate recommendations
        recommendations = self._generate_recommendations(
            calibration, cv, sens_minus_10, sens_plus_10
        )

        return RobustnessReport(
            calibration=calibration,
            cross_validation=cv,
            sensitivity_minus_10=sens_minus_10,
            sensitivity_plus_10=sens_plus_10,
            sensitivity_minus_20=sens_minus_20,
            sensitivity_plus_20=sens_plus_20,
            overall_stability=overall_stability,
            confidence_interval_95=(ci_lower, ci_upper),
            recommendations=recommendations,
        )

    def _run_scenario_raw(self, scenario: HistoricalScenario) -> dict:
        """Run scenario and return raw (uncalibrated) MAC score."""
        # Score each pillar
        liq = self.engine.score_liquidity(scenario.indicators)
        val = self.engine.score_valuation(scenario.indicators)
        pos = self.engine.score_positioning(scenario.indicators)
        vol = self.engine.score_volatility(scenario.indicators)
        pol = self.engine.score_policy(scenario.indicators)
        con = self.engine.score_contagion(scenario.indicators)

        pillars = {
            "liquidity": liq,
            "valuation": val,
            "positioning": pos,
            "volatility": vol,
            "policy": pol,
            "contagion": con,
        }

        result = calculate_mac(pillars)

        return {
            "mac_score": result.mac_score,
            "pillar_scores": pillars,
            "breach_flags": result.breach_flags,
        }

    def _create_perturbed_engine(
        self, perturbation_pct: float,
    ) -> CalibratedBacktestEngine:
        """Create engine with perturbed thresholds."""
        engine = CalibratedBacktestEngine()

        # Perturb all numeric thresholds
        multiplier = 1 + (perturbation_pct / 100)
        pt = self._perturb_thresholds

        engine.liq = pt(LIQUIDITY_THRESHOLDS, multiplier)
        engine.val = pt(VALUATION_THRESHOLDS, multiplier)
        engine.pos = pt(
            POSITIONING_THRESHOLDS, multiplier,
        )
        engine.vol = pt(
            VOLATILITY_THRESHOLDS, multiplier,
        )
        engine.pol = pt(POLICY_THRESHOLDS, multiplier)
        engine.con = pt(
            CONTAGION_THRESHOLDS, multiplier,
        )

        return engine

    def _perturb_thresholds(
        self, thresholds: dict, multiplier: float,
    ) -> dict[str, Any]:
        """Multiply all numeric values in threshold dict."""
        result: dict[str, Any] = {}
        for key, value in thresholds.items():
            if isinstance(value, dict):
                result[key] = self._perturb_thresholds(
                    value, multiplier,
                )
            elif isinstance(value, (int, float)):
                result[key] = value * multiplier
            else:
                result[key] = value
        return result

    def _calculate_r_squared(self, predicted: list, actual: list) -> float:
        """Calculate R-squared between predicted and actual values."""
        if len(predicted) != len(actual) or len(predicted) < 2:
            return 0.0

        mean_actual = statistics.mean(actual)

        ss_tot = sum((a - mean_actual) ** 2 for a in actual)
        ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))

        if ss_tot == 0:
            return 1.0 if ss_res == 0 else 0.0

        return 1 - (ss_res / ss_tot)

    def _generate_recommendations(
        self,
        calibration: CalibrationResult,
        cv: CrossValidationResult,
        sens_minus: SensitivityResult,
        sens_plus: SensitivityResult,
    ) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Calibration factor stability
        ci_lo = cv.mean_factor - 1.96 * cv.std_factor
        ci_hi = cv.mean_factor + 1.96 * cv.std_factor
        if cv.std_factor < 0.02:
            recommendations.append(
                "[OK] Calibration factor highly "
                "stable "
                f"(std={cv.std_factor:.3f}). "
                f"95% CI: [{ci_lo:.2f}, "
                f"{ci_hi:.2f}]"
            )
        elif cv.std_factor < 0.05:
            recommendations.append(
                "[!!] Calibration factor "
                "moderately stable "
                f"(std={cv.std_factor:.3f}). "
                "Consider additional scenarios."
            )
        else:
            recommendations.append(
                "[!!] Calibration factor shows "
                "variability "
                f"(std={cv.std_factor:.3f}). "
                "Results may be sensitive to "
                "crisis type."
            )

        # Sensitivity analysis
        avg_stability = (
            sens_minus.stability_score
            + sens_plus.stability_score
        ) / 2
        if avg_stability > 0.9:
            recommendations.append(
                f"[OK] Results robust to +/-10% threshold changes "
                f"(stability={avg_stability:.1%})"
            )
        elif avg_stability > 0.7:
            recommendations.append(
                f"[!!] Results moderately sensitive to threshold changes "
                f"(stability={avg_stability:.1%})"
            )
        else:
            recommendations.append(
                f"[!!] Results sensitive to threshold changes "
                f"(stability={avg_stability:.1%}). Consider threshold review."
            )

        # R-squared
        r2 = calibration.r_squared
        if r2 > 0.8:
            recommendations.append(
                "[OK] Strong fit to historical "
                f"data (R^2={r2:.3f})"
            )
        elif r2 > 0.6:
            recommendations.append(
                "[!!] Moderate fit to historical "
                f"data (R^2={r2:.3f})"
            )
        else:
            recommendations.append(
                "[!!] Weak fit to historical "
                f"data (R^2={r2:.3f}). "
                "Consider threshold "
                "recalibration."
            )

        # Specific outliers
        worst_scenario = max(
            calibration.scenario_errors,
            key=lambda k: calibration.scenario_errors[k],
        )
        worst_error = calibration.scenario_errors[
            worst_scenario
        ]
        if worst_error > 0.15:
            recommendations.append(
                "Note: Largest error on "
                f"{worst_scenario} "
                f"(error={worst_error:.3f})"
            )

        return recommendations


def format_robustness_report(report: RobustnessReport) -> str:
    """Format robustness report for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("CALIBRATION FACTOR ROBUSTNESS ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    # Calibration factor derivation
    lines.append("1. CALIBRATION FACTOR DERIVATION")
    lines.append("-" * 50)
    opt = report.calibration.optimal_factor
    lines.append(
        f"   Optimal Factor:     {opt:.3f}"
    )
    cal_mae = report.calibration.mean_absolute_error
    lines.append(
        f"   Mean Absolute Error: {cal_mae:.4f}"
    )
    lines.append(f"   R-squared:          {report.calibration.r_squared:.3f}")
    lines.append("")
    lines.append("   Scenario Errors:")
    sorted_errs = sorted(
        report.calibration.scenario_errors.items(),
        key=lambda x: -x[1],
    )
    for name, error in sorted_errs:
        lines.append(f"      {name:30} {error:.4f}")
    lines.append("")

    # Cross-validation
    lines.append("2. LEAVE-ONE-OUT CROSS-VALIDATION")
    lines.append("-" * 50)
    cv = report.cross_validation
    ci = report.confidence_interval_95
    lines.append(
        f"   Mean Factor:        {cv.mean_factor:.3f}"
    )
    lines.append(
        f"   Std Deviation:      {cv.std_factor:.4f}"
    )
    lines.append(
        f"   Range:              "
        f"[{cv.min_factor:.3f}, "
        f"{cv.max_factor:.3f}]"
    )
    lines.append(
        f"   95% Confidence:     "
        f"[{ci[0]:.3f}, {ci[1]:.3f}]"
    )
    cv_stab = report.cross_validation.stability_score
    lines.append(
        f"   Stability Score:    {cv_stab:.1%}"
    )
    lines.append("")
    lines.append("   Factor by Holdout Scenario:")
    for name, factor in sorted(
        cv.factor_by_holdout.items(),
    ):
        mae = cv.mae_by_holdout[name]
        lines.append(f"      {name:30} factor={factor:.3f}  MAE={mae:.4f}")
    lines.append("")

    # Sensitivity analysis
    lines.append("3. THRESHOLD SENSITIVITY ANALYSIS")
    lines.append("-" * 50)

    for sens, label in [
        (report.sensitivity_minus_20, "-20%"),
        (report.sensitivity_minus_10, "-10%"),
        (report.sensitivity_plus_10, "+10%"),
        (report.sensitivity_plus_20, "+20%"),
    ]:
        lines.append(f"   Perturbation: {label}")
        lines.append(f"      Pass Rate:       {sens.pass_rate:.1%}")
        lines.append(f"      Stability Score: {sens.stability_score:.1%}")
        if sens.breach_changes:
            n_affected = len(sens.breach_changes)
            lines.append(
                "      Breach Changes:  "
                f"{n_affected} scenarios affected"
            )
            for name, bc in sens.breach_changes.items():
                lines.append(
                    f"         {name}: {', '.join(bc)}"
                )
        else:
            lines.append("      Breach Changes:  None")

        # MAC score changes summary
        mac_deltas = list(sens.mac_changes.values())
        avg_change = statistics.mean(mac_deltas)
        max_change = max(abs(c) for c in mac_deltas)
        lines.append(f"      Avg MAC Change:  {avg_change:+.4f}")
        lines.append(f"      Max MAC Change:  {max_change:.4f}")
        lines.append("")

    # Overall summary
    lines.append("4. SUMMARY")
    lines.append("-" * 50)
    lines.append(f"   Overall Stability:  {report.overall_stability:.1%}")
    cal_f = report.calibration.optimal_factor
    ci95 = report.confidence_interval_95
    lines.append(
        f"   Calibration Factor: {cal_f:.2f} "
        f"(95% CI: {ci95[0]:.2f}-{ci95[1]:.2f})"
    )
    lines.append("")

    lines.append("5. RECOMMENDATIONS")
    lines.append("-" * 50)
    for rec in report.recommendations:
        lines.append(f"   {rec}")
    lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def run_robustness_analysis():
    """Run and print full robustness analysis."""
    validator = CalibrationValidator()
    report = validator.run_full_robustness_analysis()
    print(format_robustness_report(report))
    return report


if __name__ == "__main__":
    run_robustness_analysis()

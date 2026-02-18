"""Thematic Holdout Validation — v6 §13.4.

Tests whether the calibration factor α is stable when *entire categories*
of crisis are removed from the training set.  Standard LOOCV (§13.5) tests
individual-scenario sensitivity; thematic holdout tests structural-category
sensitivity — i.e., "Does α depend on having seen a banking crisis?"

Five pre-specified holdout sets (A–E) each remove 3–4 scenarios sharing a
common crisis mechanism and re-derive α on the remaining training set.

Acceptance criteria (§13.4.6):
  1. Δα_k < 0.05 for every holdout k
  2. OOS MAE_k < 0.15 for every holdout k
  3. max(α_k) − min(α_k) < 0.08 across all k
  4. mean(OOS MAE) < 0.12 across all k

All four must pass simultaneously.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from .calibration import CalibrationValidator
from .scenarios import KNOWN_EVENTS, HistoricalScenario


# ---------------------------------------------------------------------------
# Holdout set definitions (§13.4.3)
# ---------------------------------------------------------------------------

HOLDOUT_SETS: dict[str, dict] = {
    "A": {
        "theme": "Positioning / Hedge Failure",
        "thesis": (
            "α is stable when all three hedge-failure episodes are removed. "
            "Tests whether α depends on the high-information-content "
            "positioning crises that dominate the ML weight structure."
        ),
        "held_out": [
            "volmageddon_2018",
            "covid_crash_2020",
            "april_tariffs_2025",
        ],
    },
    "B": {
        "theme": "Systemic Credit / Banking",
        "thesis": (
            "α is stable when the major banking and credit crises are removed. "
            "Tests whether α requires GFC-type events to be accurate."
        ),
        "held_out": [
            "bear_stearns_2008",
            "lehman_2008",
            "svb_crisis_2023",
        ],
    },
    "C": {
        "theme": "Exogenous / Geopolitical Shock",
        "thesis": (
            "α is stable when truly exogenous (non-financial-origin) shocks "
            "are removed.  Tests the framework's ability to measure "
            "absorption of externally imposed stress."
        ),
        "held_out": [
            "sept11_2001",
            "covid_crash_2020",
            "ukraine_invasion_2022",
        ],
    },
    "D": {
        "theme": "Extreme Severity",
        "thesis": (
            "α is stable when the three most severe events (CSR < 0.40) "
            "are removed.  Tests whether α is anchored to tail events "
            "that dominate the MAE objective."
        ),
        "held_out": [
            "ltcm_crisis_1998",
            "lehman_2008",
            "covid_crash_2020",
        ],
    },
    "E": {
        "theme": "Moderate / Low-Impact",
        "thesis": (
            "α is stable when the mildest events are removed.  Tests "
            "whether α is pulled toward the centre by moderate events "
            "and loses discrimination at the tails."
        ),
        "held_out": [
            "dotcom_peak_2000",
            "flash_crash_2010",
            "volmageddon_2018",
            "ukraine_invasion_2022",
        ],
    },
}

# Scenarios that never appear in any holdout set — stability anchors
ANCHOR_SCENARIOS = {"dotcom_bottom_2002", "us_downgrade_2011", "repo_spike_2019"}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HoldoutResult:
    """Result for a single thematic holdout set."""

    holdout_key: str          # "A", "B", …
    theme: str
    n_train: int
    n_test: int
    alpha_train: float        # α* derived on training set
    delta_alpha: float        # |α_train − α_full|
    in_sample_mae: float
    oos_mae: float
    oos_errors: dict[str, float]  # scenario_key → error
    passed: bool              # Both Δα < 0.05 and OOS MAE < 0.15


@dataclass
class ThematicHoldoutReport:
    """Full thematic holdout validation report."""

    alpha_full: float                     # Full-sample α*
    holdout_results: dict[str, HoldoutResult]  # key → result
    alpha_range: float                    # max(α_k) − min(α_k)
    mean_oos_mae: float
    all_passed: bool                      # All four acceptance criteria
    acceptance: dict[str, bool]           # criterion → pass/fail
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Acceptance thresholds (§13.4.6)
# ---------------------------------------------------------------------------

MAX_DELTA_ALPHA = 0.05
MAX_OOS_MAE = 0.15
MAX_ALPHA_RANGE = 0.08
MAX_MEAN_OOS_MAE = 0.12


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

def run_thematic_holdout_validation(
    full_alpha: Optional[float] = None,
) -> ThematicHoldoutReport:
    """Execute full thematic holdout validation (§13.4.5).

    For each holdout set:
      1. Partition scenarios into train / test
      2. Re-derive α on the training set via grid search
      3. Compute in-sample and out-of-sample MAE
      4. Check per-holdout acceptance criteria

    Args:
        full_alpha: Full-sample α*.  If None, derived automatically.

    Returns:
        ThematicHoldoutReport with per-holdout and aggregate results.
    """
    validator = CalibrationValidator()

    # Step 0 — derive full-sample α* if not provided
    if full_alpha is None:
        cal = validator.derive_calibration_factor()
        full_alpha = cal.optimal_factor

    all_scenarios = {
        s.name: (key, s)
        for key, s in KNOWN_EVENTS.items()
    }
    # Also index by scenario key for holdout lookup
    scenarios_by_key: dict[str, HistoricalScenario] = dict(KNOWN_EVENTS)

    holdout_results: dict[str, HoldoutResult] = {}

    for hk, hdef in HOLDOUT_SETS.items():
        held_out_keys = set(hdef["held_out"])
        train_scenarios = [
            s for k, s in scenarios_by_key.items()
            if k not in held_out_keys
        ]
        test_scenarios = [
            scenarios_by_key[k] for k in hdef["held_out"]
        ]

        # Step 1 — re-derive α on training set
        alpha_k, train_mae = _derive_alpha_on_subset(
            validator, train_scenarios
        )

        # Step 2 — compute OOS MAE
        oos_errors: dict[str, float] = {}
        for scenario in test_scenarios:
            raw = validator._run_scenario_raw(scenario)
            calibrated = raw["mac_score"] * alpha_k
            target = validator._target_score(scenario)
            oos_errors[scenario.name] = abs(calibrated - target)

        oos_mae = statistics.mean(oos_errors.values()) if oos_errors else 0.0
        delta_alpha = abs(alpha_k - full_alpha)

        passed = (delta_alpha < MAX_DELTA_ALPHA) and (oos_mae < MAX_OOS_MAE)

        holdout_results[hk] = HoldoutResult(
            holdout_key=hk,
            theme=hdef["theme"],
            n_train=len(train_scenarios),
            n_test=len(test_scenarios),
            alpha_train=alpha_k,
            delta_alpha=delta_alpha,
            in_sample_mae=train_mae,
            oos_mae=oos_mae,
            oos_errors=oos_errors,
            passed=passed,
        )

    # Aggregate acceptance criteria (§13.4.6)
    alphas = [r.alpha_train for r in holdout_results.values()]
    alpha_range = max(alphas) - min(alphas) if alphas else 0.0
    mean_oos = statistics.mean(
        [r.oos_mae for r in holdout_results.values()]
    )

    acceptance = {
        "delta_alpha_all_below_0.05": all(
            r.delta_alpha < MAX_DELTA_ALPHA for r in holdout_results.values()
        ),
        "oos_mae_all_below_0.15": all(
            r.oos_mae < MAX_OOS_MAE for r in holdout_results.values()
        ),
        "alpha_range_below_0.08": alpha_range < MAX_ALPHA_RANGE,
        "mean_oos_mae_below_0.12": mean_oos < MAX_MEAN_OOS_MAE,
    }
    all_passed = all(acceptance.values())

    recommendations = _generate_recommendations(
        holdout_results, acceptance, full_alpha
    )

    return ThematicHoldoutReport(
        alpha_full=full_alpha,
        holdout_results=holdout_results,
        alpha_range=alpha_range,
        mean_oos_mae=mean_oos,
        all_passed=all_passed,
        acceptance=acceptance,
        recommendations=recommendations,
    )


def _derive_alpha_on_subset(
    validator: CalibrationValidator,
    scenarios: list[HistoricalScenario],
    factor_range: tuple[float, float] = (0.50, 1.00),
    step: float = 0.01,
) -> tuple[float, float]:
    """Derive α* on a subset of scenarios.

    Returns:
        (optimal_alpha, in_sample_mae)
    """
    best_factor = 0.78
    best_mae = float("inf")

    factor = factor_range[0]
    while factor <= factor_range[1]:
        errors = []
        for scenario in scenarios:
            raw = validator._run_scenario_raw(scenario)
            calibrated = raw["mac_score"] * factor
            target = validator._target_score(scenario)
            errors.append(abs(calibrated - target))

        mae = statistics.mean(errors)
        if mae < best_mae:
            best_mae = mae
            best_factor = factor

        factor += step

    return best_factor, best_mae


# ---------------------------------------------------------------------------
# Diagnostic protocol (§13.4.8)
# ---------------------------------------------------------------------------

def diagnose_holdout_failure(
    report: ThematicHoldoutReport,
) -> list[str]:
    """Apply diagnostic protocol for holdout failures (§13.4.8).

    Returns a list of diagnostic findings.
    """
    findings: list[str] = []

    failed = [
        r for r in report.holdout_results.values() if not r.passed
    ]
    if not failed:
        findings.append("All holdout sets passed.  No diagnostic action required.")
        return findings

    # Case 1: Single holdout failure
    if len(failed) == 1:
        r = failed[0]
        findings.append(
            f"Case 1 — Single holdout failure: Set {r.holdout_key} "
            f"({r.theme}).  Δα={r.delta_alpha:.3f}, OOS MAE={r.oos_mae:.3f}."
        )
        worst = max(r.oos_errors, key=r.oos_errors.get)
        findings.append(
            f"  Largest OOS error: {worst} (error={r.oos_errors[worst]:.3f}).  "
            "Investigate data quality or declare structural outlier (§17)."
        )

    # Case 2: Multiple failures with consistent direction
    elif all(
        r.alpha_train > report.alpha_full for r in failed
    ):
        findings.append(
            "Case 2 — Multiple failures, consistent upward direction.  "
            "Full-sample α is being pulled down by extreme events.  "
            "Consider severity-conditional α (§13.4.8 Case 2)."
        )
    elif all(
        r.alpha_train < report.alpha_full for r in failed
    ):
        findings.append(
            "Case 2 — Multiple failures, consistent downward direction.  "
            "Full-sample α is being pulled up by moderate events.  "
            "Consider severity-conditional α (§13.4.8 Case 2)."
        )
    else:
        findings.append(
            f"Case 3 — {len(failed)} holdout failures with mixed direction.  "
            "Investigate per-theme pillar coverage."
        )

    # Check for high OOS MAE despite stable α (Case 3)
    for r in report.holdout_results.values():
        if r.delta_alpha < MAX_DELTA_ALPHA and r.oos_mae >= MAX_OOS_MAE:
            findings.append(
                f"Case 3 — Set {r.holdout_key} ({r.theme}): α stable "
                f"(Δα={r.delta_alpha:.3f}), but OOS MAE high "
                f"({r.oos_mae:.3f}).  Pillar coverage gap — framework "
                "indicators may not capture this crisis channel."
            )

    return findings


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _generate_recommendations(
    results: dict[str, HoldoutResult],
    acceptance: dict[str, bool],
    full_alpha: float,
) -> list[str]:
    """Generate human-readable recommendations."""
    recs: list[str] = []

    if all(acceptance.values()):
        recs.append(
            "[OK] All thematic holdout acceptance criteria satisfied.  "
            "Calibration generalises across crisis types."
        )
    else:
        for criterion, passed in acceptance.items():
            if not passed:
                recs.append(f"[!!] Failed: {criterion}")

    # Per-holdout notes
    for hk, r in sorted(results.items()):
        status = "PASS" if r.passed else "FAIL"
        recs.append(
            f"  [{status}] {hk} ({r.theme}): "
            f"α={r.alpha_train:.3f}, Δα={r.delta_alpha:.3f}, "
            f"OOS MAE={r.oos_mae:.3f}"
        )

    return recs


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_holdout_report(report: ThematicHoldoutReport) -> str:
    """Format thematic holdout report for display."""
    lines: list[str] = []

    lines.append("=" * 70)
    lines.append("THEMATIC HOLDOUT VALIDATION (v6 §13.4)")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Full-sample α*: {report.alpha_full:.3f}")
    lines.append("")

    # Per-holdout results
    lines.append("PER-HOLDOUT RESULTS")
    lines.append("-" * 70)
    lines.append(
        f"{'Set':<4} {'Theme':<32} {'N_tr':>4} {'N_te':>4} "
        f"{'α_k':>6} {'Δα':>6} {'IS MAE':>7} {'OOS MAE':>8} {'Pass':>5}"
    )
    lines.append("-" * 70)
    for hk in sorted(report.holdout_results):
        r = report.holdout_results[hk]
        status = "YES" if r.passed else "NO"
        lines.append(
            f"{hk:<4} {r.theme:<32} {r.n_train:>4} {r.n_test:>4} "
            f"{r.alpha_train:>6.3f} {r.delta_alpha:>6.3f} "
            f"{r.in_sample_mae:>7.4f} {r.oos_mae:>8.4f} {status:>5}"
        )
    lines.append("")

    # OOS errors per scenario
    lines.append("OUT-OF-SAMPLE ERRORS BY SCENARIO")
    lines.append("-" * 50)
    for hk in sorted(report.holdout_results):
        r = report.holdout_results[hk]
        lines.append(f"  Holdout {hk} ({r.theme}):")
        for name, err in sorted(r.oos_errors.items(), key=lambda x: -x[1]):
            lines.append(f"    {name:<30} {err:.4f}")
    lines.append("")

    # Acceptance criteria
    lines.append("ACCEPTANCE CRITERIA (§13.4.6)")
    lines.append("-" * 50)
    for criterion, passed in report.acceptance.items():
        status = "PASS" if passed else "FAIL"
        lines.append(f"  [{status}] {criterion}")
    lines.append("")
    lines.append(f"  α range: {report.alpha_range:.3f} (threshold < {MAX_ALPHA_RANGE})")
    lines.append(f"  Mean OOS MAE: {report.mean_oos_mae:.4f} (threshold < {MAX_MEAN_OOS_MAE})")
    overall = "PASS" if report.all_passed else "FAIL"
    lines.append(f"  Overall: {overall}")
    lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 50)
        for rec in report.recommendations:
            lines.append(f"  {rec}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def run_thematic_holdout_analysis() -> ThematicHoldoutReport:
    """Run and print full thematic holdout validation."""
    report = run_thematic_holdout_validation()
    print(format_holdout_report(report))

    diagnostics = diagnose_holdout_failure(report)
    if diagnostics:
        print("\nDIAGNOSTICS")
        print("-" * 50)
        for d in diagnostics:
            print(f"  {d}")

    return report


if __name__ == "__main__":
    run_thematic_holdout_analysis()

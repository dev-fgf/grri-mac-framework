"""Precision-Recall Framework for MAC Backtest Validation (v6 §15.6–15.7).

Quantifies false positive behaviour with the same rigour applied to true
positives.  Implements:

* Full precision-recall curve (τ = 0.10 … 0.80, step 0.01 → 71 points)
* Fβ objective with four client archetypes (SWF, central bank, HF, pension)
* False-positive taxonomy (near-miss, regime-artefact, genuine)
* Per-era FPR computation
* Five standard operating points (Conservative … Maximum-recall)
* Client-configurable alert threshold
* JSON artefact export
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants from v6 §15.6
# ---------------------------------------------------------------------------

CRISIS_WINDOW_WEEKS = 6          # ±6 weeks around each event date
LEAD_TIME_WEEKS = 8              # Early signal up to 8 weeks before = TP
TAU_MIN = 0.10
TAU_MAX = 0.80
TAU_STEP = 0.01
TOTAL_CRISIS_EVENTS = 56         # Full event catalogue 1907–2025 (v7)

# Standard operating points (v6 §15.6.9)
STANDARD_OPERATING_POINTS: Dict[str, float] = {
    "Conservative": 0.30,
    "Moderate": 0.40,
    "Default": 0.50,
    "Sensitive": 0.60,
    "Maximum recall": 0.70,
}

# ERA boundaries for per-era FPR (v6 §15.6.4)
ERA_BOUNDARIES: List[Tuple[str, int, int]] = [
    ("Pre-Fed", 1907, 1913),
    ("Early Fed / WWI", 1913, 1919),
    ("Interwar / Depression", 1920, 1934),
    ("New Deal / WWII", 1934, 1954),
    ("Post-War / Bretton Woods", 1954, 1971),
    ("Post-Bretton Woods", 1971, 1990),
    ("Modern", 1990, 2026),
]


# ---------------------------------------------------------------------------
# Client archetypes (v6 §15.6.6)
# ---------------------------------------------------------------------------

class ClientArchetype(Enum):
    """Client types with associated Fβ parameter."""
    SOVEREIGN_WEALTH_FUND = ("Sovereign wealth fund", 2.0)
    CENTRAL_BANK = ("Central bank", 1.0)
    MACRO_HEDGE_FUND = ("Macro hedge fund", 0.5)
    INSURANCE_PENSION = ("Insurance / pension", 1.5)

    def __init__(self, label: str, beta: float):
        self.label = label
        self.beta = beta


# ---------------------------------------------------------------------------
# False-positive taxonomy (v6 §15.6.8)
# ---------------------------------------------------------------------------

class FPCategory(Enum):
    """Classification of false positives."""
    NEAR_MISS = "near_miss"           # Genuine stress that didn't escalate
    REGIME_ARTEFACT = "regime_artefact"  # Structural era effect (pre-1971)
    GENUINE = "genuine"                # True model failure


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CrisisWindow:
    """Time window around a crisis event."""
    event_name: str
    event_date: datetime
    window_start: datetime   # event_date − 6 weeks
    window_end: datetime     # event_date + 6 weeks
    lead_start: datetime     # event_date − 8 weeks (early TP boundary)


@dataclass
class PRPoint:
    """A single point on the precision-recall curve."""
    tau: float
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    f05: float
    f2: float
    signal_weeks: int
    fp_per_year: float


@dataclass
class OperatingPointReport:
    """Formatted report for a named operating point."""
    name: str
    tau: float
    recall: float
    precision: float
    f1: float
    f05: float
    f2: float
    fp_per_year: float
    signal_weeks: int


@dataclass
class FPClassification:
    """A classified false-positive signal."""
    date: datetime
    mac_score: float
    category: FPCategory
    reason: str


@dataclass
class EraFPR:
    """FPR statistics for a single era."""
    era_name: str
    start_year: int
    end_year: int
    non_crisis_weeks: int
    false_signals: int
    fpr: float


@dataclass
class PrecisionRecallReport:
    """Complete precision-recall analysis output."""
    curve: List[PRPoint]
    operating_points: List[OperatingPointReport]
    optimal_tau_by_beta: Dict[str, Tuple[float, float]]
    era_fpr: List[EraFPR]
    fp_classifications: List[FPClassification]
    total_weeks: int
    crisis_weeks: int
    non_crisis_weeks: int
    total_crises: int
    sample_years: float


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------

def _f_beta(precision: float, recall: float, beta: float) -> float:
    """Compute Fβ score.  Returns 0.0 when both precision and recall are 0."""
    if precision + recall == 0:
        return 0.0
    return (
        (1.0 + beta ** 2) * precision * recall
        / (beta ** 2 * precision + recall)
    )


def build_crisis_windows(
    crisis_events: List[Tuple[str, datetime]],
) -> List[CrisisWindow]:
    """Build crisis windows with lead-time allowance.

    Args:
        crisis_events: List of (event_name, event_date) tuples.

    Returns:
        List of CrisisWindow objects.
    """
    windows: List[CrisisWindow] = []
    for name, date in crisis_events:
        windows.append(CrisisWindow(
            event_name=name,
            event_date=date,
            window_start=date - timedelta(weeks=CRISIS_WINDOW_WEEKS),
            window_end=date + timedelta(weeks=CRISIS_WINDOW_WEEKS),
            lead_start=date - timedelta(weeks=LEAD_TIME_WEEKS),
        ))
    return windows


def _is_in_any_window(
    date: datetime,
    windows: List[CrisisWindow],
    *,
    include_lead: bool = True,
) -> bool:
    """Check whether *date* falls inside any crisis/lead-time window."""
    for w in windows:
        start = w.lead_start if include_lead else w.window_start
        if start <= date <= w.window_end:
            return True
    return False


def _classify_fp(
    date: datetime,
    mac_score: float,
    near_miss_dates: Optional[List[Tuple[datetime, datetime, str]]] = None,
) -> FPClassification:
    """Classify a single false-positive week (v6 §15.6.8).

    Args:
        date: Date of the false-positive signal.
        mac_score: MAC score for the week.
        near_miss_dates: Optional list of (start, end, description) tuples for
            known near-miss stress periods that aren't formal crises.

    Returns:
        FPClassification with category and reason.
    """
    # Category 2: Regime-artefact (pre-1971)
    if date < datetime(1971, 2, 15):
        return FPClassification(
            date=date,
            mac_score=mac_score,
            category=FPCategory.REGIME_ARTEFACT,
            reason="Pre-1971 structurally wide spreads / Schwert volatility",
        )

    # Category 1: Near-miss
    if near_miss_dates:
        for start, end, desc in near_miss_dates:
            if start <= date <= end:
                return FPClassification(
                    date=date,
                    mac_score=mac_score,
                    category=FPCategory.NEAR_MISS,
                    reason=f"Near-miss: {desc}",
                )

    # Heuristic: MAC between 0.35 and 0.50 outside crisis windows may be
    # a contained stress episode → near-miss
    if 0.35 <= mac_score < 0.50:
        return FPClassification(
            date=date,
            mac_score=mac_score,
            category=FPCategory.NEAR_MISS,
            reason="MAC in cautious range without formal crisis catalogued",
        )

    # Category 3: Genuine false positive
    return FPClassification(
        date=date,
        mac_score=mac_score,
        category=FPCategory.GENUINE,
        reason=(
            "No identifiable stress event, "
            "near-miss, or structural artefact"
        ),
    )


# ---------------------------------------------------------------------------
# Main precision-recall curve builder
# ---------------------------------------------------------------------------

def compute_precision_recall_curve(
    weekly_data: List[Dict],
    crisis_events: List[Tuple[str, datetime]],
    *,
    near_miss_dates: Optional[List[Tuple[datetime, datetime, str]]] = None,
    tau_min: float = TAU_MIN,
    tau_max: float = TAU_MAX,
    tau_step: float = TAU_STEP,
) -> PrecisionRecallReport:
    """Compute the full precision-recall curve and associated analytics.

    Args:
        weekly_data: List of dicts, each with keys ``date`` (datetime),
            ``mac_score`` (float), and optionally ``mac_status`` (str) and
            ``is_deteriorating`` (bool).
        crisis_events: List of ``(event_name, event_date)`` tuples for the
            41 catalogue events.
        near_miss_dates: Optional near-miss stress periods for FP taxonomy.
        tau_min/tau_max/tau_step: Threshold sweep parameters.

    Returns:
        PrecisionRecallReport with full curve, operating points, and taxonomy.
    """
    if not weekly_data:
        raise ValueError("weekly_data must be non-empty")

    windows = build_crisis_windows(crisis_events)
    total_crises = len(crisis_events)

    # Determine sample span
    dates = [d["date"] for d in weekly_data]
    min_date, max_date = min(dates), max(dates)
    sample_years = (max_date - min_date).days / 365.25

    # Pre-classify weeks as crisis/non-crisis
    crisis_week_flags = [
        _is_in_any_window(d["date"], windows)
        for d in weekly_data
    ]
    total_weeks = len(weekly_data)
    crisis_weeks = sum(crisis_week_flags)
    non_crisis_weeks = total_weeks - crisis_weeks

    # --- Sweep τ and build PR curve ---
    curve: List[PRPoint] = []

    tau = tau_min
    while tau <= tau_max + 1e-9:
        tau_r = round(tau, 2)

        # Signal definition: MAC < τ  OR  momentum DETERIORATING+
        signal_flags = []
        for d in weekly_data:
            below_tau = d["mac_score"] < tau_r
            momentum_signal = d.get("is_deteriorating", False) or d.get(
                "mac_status", ""
            ) in ("DETERIORATING", "STRETCHED", "CRITICAL")
            signal_flags.append(below_tau or momentum_signal)

        # Count TP: crisis events with at least one signal in their window
        tp = 0
        for w in windows:
            for d, sig in zip(weekly_data, signal_flags):
                if not sig:
                    continue
                # TP if signal fires within window or within lead-time
                if w.lead_start <= d["date"] <= w.window_end:
                    tp += 1
                    break  # one TP per crisis event

        fn = total_crises - tp

        # Count FP: signals in non-crisis weeks
        fp = sum(
            1 for f_c, f_s in zip(crisis_week_flags, signal_flags)
            if not f_c and f_s
        )

        signal_weeks = sum(signal_flags)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / total_crises if total_crises > 0 else 0.0
        fp_per_year = fp / sample_years if sample_years > 0 else 0.0

        curve.append(PRPoint(
            tau=tau_r,
            tp=tp,
            fp=fp,
            fn=fn,
            precision=precision,
            recall=recall,
            f1=_f_beta(precision, recall, 1.0),
            f05=_f_beta(precision, recall, 0.5),
            f2=_f_beta(precision, recall, 2.0),
            signal_weeks=signal_weeks,
            fp_per_year=fp_per_year,
        ))

        tau += tau_step

    # --- Standard operating points ---
    ops: List[OperatingPointReport] = []
    for name, t in STANDARD_OPERATING_POINTS.items():
        pt = _find_tau_point(curve, t)
        if pt:
            ops.append(OperatingPointReport(
                name=name,
                tau=pt.tau,
                recall=pt.recall,
                precision=pt.precision,
                f1=pt.f1,
                f05=pt.f05,
                f2=pt.f2,
                fp_per_year=pt.fp_per_year,
                signal_weeks=pt.signal_weeks,
            ))

    # --- Optimal τ* by client archetype ---
    optimal_by_beta: Dict[str, Tuple[float, float]] = {}
    for arch in ClientArchetype:
        best_tau = 0.0
        best_fb = -1.0
        for pt in curve:
            fb = _f_beta(pt.precision, pt.recall, arch.beta)
            if fb > best_fb:
                best_fb = fb
                best_tau = pt.tau
        optimal_by_beta[arch.label] = (best_tau, round(best_fb, 4))

    # --- Per-era FPR (at default τ = 0.50) ---
    era_fpr = _compute_era_fpr(weekly_data, windows, tau=0.50)

    # --- FP taxonomy (at default τ = 0.50) ---
    fp_classifications = _classify_all_fps(
        weekly_data, windows, tau=0.50, near_miss_dates=near_miss_dates,
    )

    return PrecisionRecallReport(
        curve=curve,
        operating_points=ops,
        optimal_tau_by_beta=optimal_by_beta,
        era_fpr=era_fpr,
        fp_classifications=fp_classifications,
        total_weeks=total_weeks,
        crisis_weeks=crisis_weeks,
        non_crisis_weeks=non_crisis_weeks,
        total_crises=total_crises,
        sample_years=sample_years,
    )


def _find_tau_point(curve: List[PRPoint], tau: float) -> Optional[PRPoint]:
    """Return the PRPoint closest to the requested τ."""
    best = None
    best_diff = float("inf")
    for pt in curve:
        diff = abs(pt.tau - tau)
        if diff < best_diff:
            best_diff = diff
            best = pt
    return best


# ---------------------------------------------------------------------------
# Per-era FPR
# ---------------------------------------------------------------------------

def _compute_era_fpr(
    weekly_data: List[Dict],
    windows: List[CrisisWindow],
    tau: float,
) -> List[EraFPR]:
    """Compute FPR separately for each era (v6 §15.6.4)."""
    results: List[EraFPR] = []
    for era_name, start_year, end_year in ERA_BOUNDARIES:
        era_start = datetime(start_year, 1, 1)
        era_end = datetime(end_year, 1, 1)
        non_crisis = 0
        false_signals = 0
        for d in weekly_data:
            date = d["date"]
            if not (era_start <= date < era_end):
                continue
            in_window = _is_in_any_window(date, windows)
            if in_window:
                continue  # crisis week — skip
            non_crisis += 1
            signal = (
                d["mac_score"] < tau
                or d.get("is_deteriorating", False)
                or d.get("mac_status", "") in (
                    "DETERIORATING", "STRETCHED", "CRITICAL",
                )
            )
            if signal:
                false_signals += 1
        fpr = false_signals / non_crisis if non_crisis > 0 else 0.0
        results.append(EraFPR(
            era_name=era_name,
            start_year=start_year,
            end_year=end_year,
            non_crisis_weeks=non_crisis,
            false_signals=false_signals,
            fpr=fpr,
        ))
    return results


# ---------------------------------------------------------------------------
# FP classification
# ---------------------------------------------------------------------------

def _classify_all_fps(
    weekly_data: List[Dict],
    windows: List[CrisisWindow],
    tau: float,
    near_miss_dates: Optional[List[Tuple[datetime, datetime, str]]] = None,
) -> List[FPClassification]:
    """Classify every false-positive week at the given τ."""
    fps: List[FPClassification] = []
    for d in weekly_data:
        date = d["date"]
        in_window = _is_in_any_window(date, windows)
        if in_window:
            continue
        signal = (
            d["mac_score"] < tau
            or d.get("is_deteriorating", False)
            or d.get("mac_status", "") in (
                "DETERIORATING", "STRETCHED", "CRITICAL",
            )
        )
        if not signal:
            continue
        fps.append(_classify_fp(date, d["mac_score"], near_miss_dates))
    return fps


# ---------------------------------------------------------------------------
# Client-configurable operating point helper
# ---------------------------------------------------------------------------

def optimal_threshold_for_beta(
    curve: List[PRPoint],
    beta: float,
) -> Tuple[float, float]:
    """Return ``(τ*, Fβ*)`` that maximises Fβ over the PR curve.

    Args:
        curve: List of PRPoint from compute_precision_recall_curve().
        beta: Weight parameter (β > 1 penalises FN; β < 1 penalises FP).

    Returns:
        (optimal_tau, max_f_beta)
    """
    best_tau = 0.0
    best_fb = -1.0
    for pt in curve:
        fb = _f_beta(pt.precision, pt.recall, beta)
        if fb > best_fb:
            best_fb = fb
            best_tau = pt.tau
    return best_tau, round(best_fb, 4)


def breakeven_precision(cost_fp_bps: float, cost_fn_bps: float) -> float:
    """Compute breakeven precision from v6 §15.7.3.

    precision_breakeven = cost_FP / (cost_FP + cost_FN)

    Example: cost_FP=30 bps, cost_FN=1500 bps → 0.020.
    """
    if cost_fp_bps + cost_fn_bps == 0:
        return 0.0
    return cost_fp_bps / (cost_fp_bps + cost_fn_bps)


# ---------------------------------------------------------------------------
# Reporting / export
# ---------------------------------------------------------------------------

def format_precision_recall_report(report: PrecisionRecallReport) -> str:
    """Format human-readable summary of the PR analysis."""
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("  PRECISION-RECALL ANALYSIS  (v6 §15.6)")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"  Sample: {report.total_weeks:,} weekly observations "
                 f"({report.sample_years:.1f} years)")
    lines.append(f"  Crisis events: {report.total_crises}")
    lines.append(f"  Crisis weeks (±6w window): {report.crisis_weeks:,}")
    lines.append(f"  Non-crisis weeks: {report.non_crisis_weeks:,}")
    lines.append("")

    # Operating points table
    lines.append("  STANDARD OPERATING POINTS")
    lines.append("  " + "-" * 74)
    lines.append(
        f"  {'Point':<16} {'τ':>4} {'Recall':>7} {'Precis.':>7} "
        f"{'F1':>6} {'F0.5':>6} {'F2':>6} {'FP/yr':>6} {'Signals':>7}"
    )
    lines.append("  " + "-" * 74)
    for op in report.operating_points:
        lines.append(
            f"  {op.name:<16} {op.tau:>4.2f} {op.recall:>7.3f} "
            f"{op.precision:>7.3f} {op.f1:>6.3f} {op.f05:>6.3f} "
            f"{op.f2:>6.3f} {op.fp_per_year:>6.1f} {op.signal_weeks:>7d}"
        )
    lines.append("")

    # Optimal thresholds by archetype
    lines.append("  OPTIMAL τ* BY CLIENT ARCHETYPE")
    lines.append("  " + "-" * 50)
    for label, (tau_star, fb_star) in report.optimal_tau_by_beta.items():
        lines.append(f"  {label:<26} τ*={tau_star:.2f}  Fβ*={fb_star:.4f}")
    lines.append("")

    # Per-era FPR
    lines.append("  FALSE POSITIVE RATE BY ERA (τ=0.50)")
    lines.append("  " + "-" * 60)
    lines.append(f"  {'Era':<28} {'Non-crisis wks':>14} {'FP':>5} {'FPR':>7}")
    lines.append("  " + "-" * 60)
    for era in report.era_fpr:
        lines.append(
            f"  {era.era_name:<28} {era.non_crisis_weeks:>14,} "
            f"{era.false_signals:>5} {era.fpr:>7.3f}"
        )
    lines.append("")

    # FP taxonomy summary
    cat_counts: Dict[str, int] = {}
    for fp in report.fp_classifications:
        key = fp.category.value
        cat_counts[key] = cat_counts.get(key, 0) + 1
    total_fp = sum(cat_counts.values())
    lines.append(f"  FALSE POSITIVE TAXONOMY (τ=0.50, total FP={total_fp})")
    lines.append("  " + "-" * 50)
    for cat in FPCategory:
        n = cat_counts.get(cat.value, 0)
        pct = n / total_fp * 100 if total_fp > 0 else 0.0
        lines.append(f"  {cat.value:<20} {n:>5}  ({pct:>5.1f}%)")
    lines.append("")

    # Breakeven precision example
    be = breakeven_precision(30, 1500)
    lines.append(
        "  Breakeven precision "
        f"(30 bps FP cost, 1500 bps FN cost): {be:.3f}"
    )
    lines.append("  → Framework adds expected value at any operating point "
                 "with precision > 2%.")
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines)


def export_precision_recall_json(
    report: PrecisionRecallReport,
    filepath: Optional[str] = None,
) -> str:
    """Export the full PR curve as a JSON artefact (71 data points).

    Args:
        report: PrecisionRecallReport output.
        filepath: If provided, write to file; otherwise return JSON string.

    Returns:
        JSON string.
    """
    payload = {
        "meta": {
            "total_weeks": report.total_weeks,
            "crisis_weeks": report.crisis_weeks,
            "non_crisis_weeks": report.non_crisis_weeks,
            "total_crises": report.total_crises,
            "sample_years": round(report.sample_years, 2),
        },
        "curve": [
            {
                "tau": pt.tau,
                "precision": round(pt.precision, 4),
                "recall": round(pt.recall, 4),
                "f1": round(pt.f1, 4),
                "f05": round(pt.f05, 4),
                "f2": round(pt.f2, 4),
                "tp": pt.tp,
                "fp": pt.fp,
                "fn": pt.fn,
                "signal_weeks": pt.signal_weeks,
                "fp_per_year": round(pt.fp_per_year, 2),
            }
            for pt in report.curve
        ],
        "operating_points": [
            {
                "name": op.name,
                "tau": op.tau,
                "recall": round(op.recall, 4),
                "precision": round(op.precision, 4),
                "f1": round(op.f1, 4),
                "f05": round(op.f05, 4),
                "f2": round(op.f2, 4),
                "fp_per_year": round(op.fp_per_year, 2),
                "signal_weeks": op.signal_weeks,
            }
            for op in report.operating_points
        ],
        "optimal_by_archetype": {
            label: {"tau_star": t, "f_beta_star": fb}
            for label, (t, fb) in report.optimal_tau_by_beta.items()
        },
        "era_fpr": [
            {
                "era": era.era_name,
                "start_year": era.start_year,
                "end_year": era.end_year,
                "non_crisis_weeks": era.non_crisis_weeks,
                "false_signals": era.false_signals,
                "fpr": round(era.fpr, 4),
            }
            for era in report.era_fpr
        ],
        "fp_taxonomy": {
            cat.value: sum(
                1 for f in report.fp_classifications if f.category == cat
            )
            for cat in FPCategory
        },
    }
    json_str = json.dumps(payload, indent=2)
    if filepath:
        with open(filepath, "w") as fh:
            fh.write(json_str)
    return json_str

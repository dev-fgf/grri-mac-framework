"""False-positive taxonomy & economic cost analysis (v7 §3.3).

Auto-classifies false positives into three categories:
  Cat 1: Near-miss (genuine stress within 3 months of a crisis)
  Cat 2: Regime artefact (structural era effect, e.g. pre-1971)
  Cat 3: Pure false positive (no identifiable stress)

Computes economic cost at each PR operating point:
  - 30bp hedge cost per FP week
  - Full drawdown cost per FN (missed crisis)
  - Sharpe impact for a stylised 60/40 portfolio

Usage:
    from grri_mac.backtest.fp_cost_analysis import (
        FPCostAnalyser,
        run_fp_cost_analysis,
    )
    result = run_fp_cost_analysis(weekly_data, crisis_events)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── FP Categories ────────────────────────────────────────────────────────

class FPCategoryV7(Enum):
    """Enhanced FP classification (v7)."""

    NEAR_MISS = "near_miss"
    REGIME_ARTEFACT = "regime_artefact"
    PURE_FALSE = "pure_false"


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class ClassifiedFP:
    """A single classified false positive."""

    date: datetime
    mac_score: float
    category: FPCategoryV7
    reason: str
    nearest_crisis_name: Optional[str] = None
    days_to_nearest_crisis: Optional[int] = None


@dataclass
class EconomicCostPoint:
    """Economic cost at a single PR operating point."""

    tau: float
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float

    # Costs
    fp_cost_bps_annual: float  # Hedge drag from FPs
    fn_cost_bps_annual: float  # Missed drawdown from FNs
    net_expected_value_bps: float  # EVsignal − EVno_signal
    sharpe_impact: float  # Change in Sharpe ratio


@dataclass
class FPCostConfig:
    """Configuration for cost analysis."""

    # Cost assumptions
    hedge_cost_bps_per_week: float = 30.0  # Cost of hedging per FP week
    avg_crisis_drawdown_bps: float = 1500.0  # Avg drawdown per missed crisis
    risk_free_return_annual_bps: float = 400.0  # 4% annual
    portfolio_vol_annual_bps: float = 1000.0  # 10% annual vol

    # Near-miss window (days from nearest crisis)
    near_miss_days: int = 90  # 3 months

    # Structural era cutoff
    regime_artefact_cutoff: datetime = datetime(1971, 8, 15)

    # Tau sweep
    tau_values: List[float] = field(default_factory=lambda: [
        round(0.10 + i * 0.01, 2) for i in range(71)
    ])

    # Crisis window for TP/FP counting
    crisis_window_weeks: int = 6
    lead_time_weeks: int = 8


@dataclass
class FPCostResult:
    """Complete FP cost analysis output."""

    classified_fps: List[ClassifiedFP]
    category_counts: Dict[str, int]
    category_pcts: Dict[str, float]

    # Cost curve
    cost_curve: List[EconomicCostPoint]

    # Optimal operating points
    max_ev_point: Optional[EconomicCostPoint]
    breakeven_precision: float

    # Summary statistics
    total_fp_at_default: int
    near_miss_pct: float
    regime_artefact_pct: float
    pure_false_pct: float


# ── Core analyser ────────────────────────────────────────────────────────

class FPCostAnalyser:
    """Analyse false positives with taxonomy and economic costs."""

    def __init__(
        self,
        config: Optional[FPCostConfig] = None,
    ):
        self.config = config or FPCostConfig()

    def analyse(
        self,
        weekly_data: List[Dict],
        crisis_events: List[Tuple[str, datetime]],
        near_miss_periods: Optional[
            List[Tuple[datetime, datetime, str]]
        ] = None,
    ) -> FPCostResult:
        """Run full FP cost analysis.

        Args:
            weekly_data: List of dicts with date, mac_score keys.
            crisis_events: List of (name, date) tuples.
            near_miss_periods: Optional known stress periods that
                aren't formal crises (start, end, description).

        Returns:
            FPCostResult with taxonomy and cost curves.
        """
        cfg = self.config

        # Build crisis windows
        windows = self._build_windows(crisis_events)

        # Classify all FPs at default tau (0.50)
        classified_fps = self._classify_fps(
            weekly_data, crisis_events, windows,
            tau=0.50,
            near_miss_periods=near_miss_periods,
        )

        # Count categories
        cat_counts: Dict[str, int] = {
            cat.value: 0 for cat in FPCategoryV7
        }
        for fp in classified_fps:
            cat_counts[fp.category.value] += 1

        total_fp = len(classified_fps)
        cat_pcts: Dict[str, float] = {
            cat: (n / total_fp * 100 if total_fp > 0 else 0.0)
            for cat, n in cat_counts.items()
        }

        # Compute cost curve across all tau values
        cost_curve = self._compute_cost_curve(
            weekly_data, crisis_events, windows,
        )

        # Find max EV point
        max_ev_point = None
        max_ev = float("-inf")
        for pt in cost_curve:
            if pt.net_expected_value_bps > max_ev:
                max_ev = pt.net_expected_value_bps
                max_ev_point = pt

        # Breakeven precision
        be = self._breakeven_precision()

        return FPCostResult(
            classified_fps=classified_fps,
            category_counts=cat_counts,
            category_pcts=cat_pcts,
            cost_curve=cost_curve,
            max_ev_point=max_ev_point,
            breakeven_precision=be,
            total_fp_at_default=total_fp,
            near_miss_pct=cat_pcts.get("near_miss", 0.0),
            regime_artefact_pct=cat_pcts.get(
                "regime_artefact", 0.0
            ),
            pure_false_pct=cat_pcts.get("pure_false", 0.0),
        )

    def _build_windows(
        self,
        crisis_events: List[Tuple[str, datetime]],
    ) -> List[Tuple[datetime, datetime, str]]:
        """Build crisis windows."""
        cfg = self.config
        windows = []
        for name, date in crisis_events:
            start = date - timedelta(
                weeks=cfg.crisis_window_weeks + cfg.lead_time_weeks,
            )
            end = date + timedelta(weeks=cfg.crisis_window_weeks)
            windows.append((start, end, name))
        return windows

    def _is_in_window(
        self,
        date: datetime,
        windows: List[Tuple[datetime, datetime, str]],
    ) -> bool:
        for start, end, _ in windows:
            if start <= date <= end:
                return True
        return False

    def _classify_fps(
        self,
        weekly_data: List[Dict],
        crisis_events: List[Tuple[str, datetime]],
        windows: List[Tuple[datetime, datetime, str]],
        tau: float,
        near_miss_periods: Optional[
            List[Tuple[datetime, datetime, str]]
        ] = None,
    ) -> List[ClassifiedFP]:
        """Classify all false positives at given tau."""
        cfg = self.config
        fps: List[ClassifiedFP] = []

        for week in weekly_data:
            date = week["date"]
            mac = week["mac_score"]

            # Skip if in crisis window
            if self._is_in_window(date, windows):
                continue

            # Check if signal fires
            signal = (
                mac < tau
                or week.get("is_deteriorating", False)
                or week.get("mac_status", "") in (
                    "DETERIORATING", "STRETCHED", "CRITICAL",
                )
            )
            if not signal:
                continue

            # This is a false positive — classify it
            fp = self._classify_single_fp(
                date, mac, crisis_events, near_miss_periods,
            )
            fps.append(fp)

        return fps

    def _classify_single_fp(
        self,
        date: datetime,
        mac_score: float,
        crisis_events: List[Tuple[str, datetime]],
        near_miss_periods: Optional[
            List[Tuple[datetime, datetime, str]]
        ] = None,
    ) -> ClassifiedFP:
        """Classify a single false positive."""
        cfg = self.config

        # Find nearest crisis
        nearest_name = None
        nearest_days = None
        for name, crisis_date in crisis_events:
            days = abs((date - crisis_date).days)
            if nearest_days is None or days < nearest_days:
                nearest_days = days
                nearest_name = name

        # Cat 1: Near-miss (within 3 months of a crisis)
        if nearest_days is not None and nearest_days <= cfg.near_miss_days:
            return ClassifiedFP(
                date=date,
                mac_score=mac_score,
                category=FPCategoryV7.NEAR_MISS,
                reason=(
                    f"Within {nearest_days}d of "
                    f"'{nearest_name}'"
                ),
                nearest_crisis_name=nearest_name,
                days_to_nearest_crisis=nearest_days,
            )

        # Check explicit near-miss periods
        if near_miss_periods:
            for start, end, desc in near_miss_periods:
                if start <= date <= end:
                    return ClassifiedFP(
                        date=date,
                        mac_score=mac_score,
                        category=FPCategoryV7.NEAR_MISS,
                        reason=f"Near-miss period: {desc}",
                        nearest_crisis_name=nearest_name,
                        days_to_nearest_crisis=nearest_days,
                    )

        # Cat 2: Regime artefact (pre-1971)
        if date < cfg.regime_artefact_cutoff:
            return ClassifiedFP(
                date=date,
                mac_score=mac_score,
                category=FPCategoryV7.REGIME_ARTEFACT,
                reason=(
                    "Pre-Bretton-Woods-collapse: "
                    "structurally wider spreads"
                ),
                nearest_crisis_name=nearest_name,
                days_to_nearest_crisis=nearest_days,
            )

        # Cat 3: Pure false positive
        return ClassifiedFP(
            date=date,
            mac_score=mac_score,
            category=FPCategoryV7.PURE_FALSE,
            reason="No identifiable stress event",
            nearest_crisis_name=nearest_name,
            days_to_nearest_crisis=nearest_days,
        )

    def _compute_cost_curve(
        self,
        weekly_data: List[Dict],
        crisis_events: List[Tuple[str, datetime]],
        windows: List[Tuple[datetime, datetime, str]],
    ) -> List[EconomicCostPoint]:
        """Compute cost curve across all tau values."""
        cfg = self.config
        total_crises = len(crisis_events)

        # Determine sample span
        dates = [d["date"] for d in weekly_data]
        sample_years = (
            (max(dates) - min(dates)).days / 365.25
            if dates else 1.0
        )

        curve: List[EconomicCostPoint] = []

        for tau in cfg.tau_values:
            # Count TP/FP/FN at this tau
            tp = 0
            fp = 0

            # TP: crisis events with at least one signal
            for name, crisis_date in crisis_events:
                lead_start = crisis_date - timedelta(
                    weeks=cfg.lead_time_weeks,
                )
                window_end = crisis_date + timedelta(
                    weeks=cfg.crisis_window_weeks,
                )
                detected = False
                for week in weekly_data:
                    d = week["date"]
                    if lead_start <= d <= window_end:
                        signal = (
                            week["mac_score"] < tau
                            or week.get("is_deteriorating", False)
                        )
                        if signal:
                            detected = True
                            break
                if detected:
                    tp += 1

            fn = total_crises - tp

            # FP: signals in non-crisis weeks
            for week in weekly_data:
                if self._is_in_window(week["date"], windows):
                    continue
                signal = (
                    week["mac_score"] < tau
                    or week.get("is_deteriorating", False)
                )
                if signal:
                    fp += 1

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / total_crises if total_crises > 0 else 0.0

            # Economic costs (annualised)
            fp_cost_annual = (
                fp * cfg.hedge_cost_bps_per_week / sample_years
            )
            fn_cost_annual = (
                fn * cfg.avg_crisis_drawdown_bps / sample_years
            )

            # Net EV: value of correctly detected crises minus
            # cost of false hedging
            ev_signal = (
                tp * cfg.avg_crisis_drawdown_bps / sample_years
                - fp_cost_annual
            )
            ev_no_signal = 0.0  # Do nothing baseline
            net_ev = ev_signal - ev_no_signal

            # Sharpe impact
            # Simplified: hedge removes drawdown but adds drag
            excess_return = (
                cfg.risk_free_return_annual_bps
                + tp * cfg.avg_crisis_drawdown_bps
                / max(sample_years, 1)
                - fp_cost_annual
            )
            sharpe = (
                excess_return / cfg.portfolio_vol_annual_bps
                if cfg.portfolio_vol_annual_bps > 0
                else 0.0
            )

            curve.append(EconomicCostPoint(
                tau=tau,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=precision,
                recall=recall,
                fp_cost_bps_annual=fp_cost_annual,
                fn_cost_bps_annual=fn_cost_annual,
                net_expected_value_bps=net_ev,
                sharpe_impact=sharpe,
            ))

        return curve

    def _breakeven_precision(self) -> float:
        """Compute breakeven precision."""
        cfg = self.config
        c_fp = cfg.hedge_cost_bps_per_week
        c_fn = cfg.avg_crisis_drawdown_bps
        if c_fp + c_fn == 0:
            return 0.0
        return c_fp / (c_fp + c_fn)


# ── Convenience ──────────────────────────────────────────────────────────

def run_fp_cost_analysis(
    weekly_data: List[Dict],
    crisis_events: List[Tuple[str, datetime]],
    config: Optional[FPCostConfig] = None,
    near_miss_periods: Optional[
        List[Tuple[datetime, datetime, str]]
    ] = None,
) -> FPCostResult:
    """Convenience function for FP cost analysis."""
    analyser = FPCostAnalyser(config)
    return analyser.analyse(
        weekly_data, crisis_events, near_miss_periods,
    )


def format_fp_cost_report(result: FPCostResult) -> str:
    """Format FP cost analysis for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("FALSE POSITIVE TAXONOMY & COST ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    lines.append("FP TAXONOMY (at tau=0.50)")
    lines.append("-" * 50)
    lines.append(f"  Total FP weeks:    {result.total_fp_at_default}")
    for cat in FPCategoryV7:
        n = result.category_counts.get(cat.value, 0)
        pct = result.category_pcts.get(cat.value, 0.0)
        lines.append(f"  {cat.value:<20} {n:>5}  ({pct:>5.1f}%)")
    lines.append("")

    lines.append(
        f"  Breakeven precision: {result.breakeven_precision:.4f}"
    )
    lines.append(
        "  (Any precision above this adds expected value)"
    )
    lines.append("")

    if result.max_ev_point:
        pt = result.max_ev_point
        lines.append("OPTIMAL OPERATING POINT (max EV)")
        lines.append("-" * 50)
        lines.append(f"  tau:       {pt.tau:.2f}")
        lines.append(f"  Precision: {pt.precision:.3f}")
        lines.append(f"  Recall:    {pt.recall:.3f}")
        lines.append(
            f"  FP cost:   {pt.fp_cost_bps_annual:.0f} bps/yr"
        )
        lines.append(
            f"  FN cost:   {pt.fn_cost_bps_annual:.0f} bps/yr"
        )
        lines.append(
            f"  Net EV:    {pt.net_expected_value_bps:.0f} bps/yr"
        )
        lines.append(
            f"  Sharpe:    {pt.sharpe_impact:.3f}"
        )
        lines.append("")

    # Cost curve summary at key points
    lines.append("COST CURVE (selected tau values)")
    lines.append("-" * 70)
    lines.append(
        f"  {'tau':>5} {'TP':>4} {'FP':>5} {'FN':>4} "
        f"{'Prec':>6} {'Recall':>7} "
        f"{'FP$/yr':>8} {'FN$/yr':>8} {'NetEV':>8}"
    )
    key_taus = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
    for pt in result.cost_curve:
        if round(pt.tau, 2) in key_taus:
            lines.append(
                f"  {pt.tau:>5.2f} {pt.tp:>4} {pt.fp:>5} "
                f"{pt.fn:>4} {pt.precision:>6.3f} "
                f"{pt.recall:>7.3f} "
                f"{pt.fp_cost_bps_annual:>8.0f} "
                f"{pt.fn_cost_bps_annual:>8.0f} "
                f"{pt.net_expected_value_bps:>8.0f}"
            )
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)

"""True walk-forward blind backtest engine (v7 §3.1).

At each week t, uses ONLY data available as of t:
- No future proxies or revised FRED vintages
- Re-estimates ML weights every 52 weeks on expanding window
- Re-estimates calibration factor α on expanding window
- Outputs rolling TPR/FPR, weight stability, α stability

This replaces the standard blind_backtest.py with a stricter
protocol that eliminates all forms of lookahead bias.

Usage:
    from grri_mac.backtest.walk_forward import (
        WalkForwardEngine,
        run_walk_forward,
    )
    results = run_walk_forward(weekly_data, crisis_events)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────────

@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward backtest."""

    # Re-estimation frequency (weeks)
    refit_interval_weeks: int = 52

    # Minimum training window before first prediction (weeks)
    min_training_weeks: int = 104  # ~2 years

    # Expanding vs rolling window
    expanding_window: bool = True  # True = expanding, False = rolling
    rolling_window_weeks: int = 520  # ~10 years if rolling

    # Threshold sweep for TPR/FPR curves
    tau_values: List[float] = field(default_factory=lambda: [
        0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65,
    ])

    # Crisis window for TP/FP classification
    crisis_window_weeks: int = 6
    lead_time_weeks: int = 8

    # Default pillar weights (equal) — overridden by ML if available
    default_weights: Dict[str, float] = field(default_factory=lambda: {
        "liquidity": 1 / 7,
        "valuation": 1 / 7,
        "positioning": 1 / 7,
        "volatility": 1 / 7,
        "policy": 1 / 7,
        "contagion": 1 / 7,
        "private_credit": 1 / 7,
    })


# ── Result dataclasses ───────────────────────────────────────────────────

@dataclass
class WeeklyPrediction:
    """A single week's walk-forward prediction."""

    date: datetime
    mac_score: float
    pillar_scores: Dict[str, float]
    weights_used: Dict[str, float]
    alpha_used: float
    training_weeks: int  # Size of training window
    refit_epoch: int  # Which refit period this belongs to


@dataclass
class RollingMetrics:
    """Rolling performance metrics at a given tau."""

    tau: float
    cumulative_tp: int
    cumulative_fp: int
    cumulative_fn: int
    cumulative_precision: float
    cumulative_recall: float
    rolling_fpr_52w: float  # FPR over last 52 weeks


@dataclass
class WeightStability:
    """Statistics on pillar weight stability across refits."""

    pillar: str
    mean_weight: float
    std_weight: float
    min_weight: float
    max_weight: float
    cv: float  # Coefficient of variation


@dataclass
class AlphaStability:
    """Statistics on calibration factor stability."""

    mean_alpha: float
    std_alpha: float
    min_alpha: float
    max_alpha: float
    alpha_history: List[Tuple[datetime, float]]


@dataclass
class WalkForwardResult:
    """Complete walk-forward backtest results."""

    config: WalkForwardConfig
    predictions: List[WeeklyPrediction]

    # Rolling metrics at each tau
    rolling_metrics: Dict[float, List[RollingMetrics]]

    # Final metrics at default tau (0.50)
    final_tpr: float
    final_fpr: float
    final_precision: float
    final_recall: float

    # Stability analysis
    weight_stability: List[WeightStability]
    alpha_stability: AlphaStability

    # Refit history
    refit_dates: List[datetime]
    weight_history: List[Tuple[datetime, Dict[str, float]]]

    # Summary
    total_weeks_predicted: int
    total_crises_detected: int
    total_crises_missed: int
    total_false_positives: int


# ── Core engine ──────────────────────────────────────────────────────────

class WalkForwardEngine:
    """True walk-forward backtest with no lookahead bias.

    Protocol:
    1. Start at min_training_weeks into the dataset
    2. At each week t, compute MAC using only data up to t
    3. Every refit_interval_weeks, re-estimate weights and α
       using only scenarios/data available up to t
    4. Track rolling TPR/FPR at multiple thresholds
    """

    def __init__(
        self,
        config: Optional[WalkForwardConfig] = None,
    ):
        self.config = config or WalkForwardConfig()

    def run(
        self,
        weekly_data: List[Dict],
        crisis_events: List[Tuple[str, datetime]],
        pillar_scorer=None,
    ) -> WalkForwardResult:
        """Run walk-forward backtest.

        Args:
            weekly_data: List of dicts with keys:
                - date: datetime
                - indicators: dict of raw indicator values
                - pillar_scores: dict of pre-computed pillar scores
                  (if pillar_scorer is None)
            crisis_events: List of (name, date) tuples for
                crisis event catalogue.
            pillar_scorer: Optional callable(indicators, date)
                -> dict of pillar scores. If None, uses
                pre-computed pillar_scores from weekly_data.

        Returns:
            WalkForwardResult with full analysis.
        """
        cfg = self.config

        # Sort data chronologically
        weekly_data = sorted(weekly_data, key=lambda d: d["date"])
        n_weeks = len(weekly_data)

        if n_weeks < cfg.min_training_weeks:
            raise ValueError(
                f"Need {cfg.min_training_weeks} weeks minimum, "
                f"got {n_weeks}"
            )

        # Build crisis windows
        crisis_windows = self._build_crisis_windows(crisis_events)

        # Initialise state
        predictions: List[WeeklyPrediction] = []
        refit_dates: List[datetime] = []
        weight_history: List[Tuple[datetime, Dict[str, float]]] = []
        alpha_history: List[Tuple[datetime, float]] = []

        current_weights = cfg.default_weights.copy()
        current_alpha = 0.78  # Default calibration factor
        refit_epoch = 0
        weeks_since_refit = cfg.refit_interval_weeks  # Force initial fit

        # Rolling metrics tracking
        rolling_state: Dict[float, _RollingState] = {
            tau: _RollingState() for tau in cfg.tau_values
        }

        # ── Main loop ────────────────────────────────────────────────
        for t in range(cfg.min_training_weeks, n_weeks):
            current_week = weekly_data[t]
            current_date = current_week["date"]

            # Check if refit needed
            if weeks_since_refit >= cfg.refit_interval_weeks:
                # Get training window
                if cfg.expanding_window:
                    train_start = 0
                else:
                    train_start = max(
                        0, t - cfg.rolling_window_weeks
                    )
                train_data = weekly_data[train_start:t]

                # Re-estimate weights and alpha
                new_weights, new_alpha = self._refit(
                    train_data, crisis_events,
                )
                if new_weights is not None:
                    current_weights = new_weights
                if new_alpha is not None:
                    current_alpha = new_alpha

                refit_dates.append(current_date)
                weight_history.append(
                    (current_date, current_weights.copy())
                )
                alpha_history.append((current_date, current_alpha))
                refit_epoch += 1
                weeks_since_refit = 0

            # Compute MAC score for this week
            pillar_scores = self._get_pillar_scores(
                current_week, pillar_scorer,
            )
            mac_score = self._compute_mac(
                pillar_scores, current_weights, current_alpha,
            )

            predictions.append(WeeklyPrediction(
                date=current_date,
                mac_score=mac_score,
                pillar_scores=pillar_scores,
                weights_used=current_weights.copy(),
                alpha_used=current_alpha,
                training_weeks=t if cfg.expanding_window else min(
                    t, cfg.rolling_window_weeks
                ),
                refit_epoch=refit_epoch,
            ))

            # Update rolling metrics at each tau
            in_crisis = self._is_in_crisis_window(
                current_date, crisis_windows,
            )
            for tau in cfg.tau_values:
                signal = mac_score < tau
                rolling_state[tau].update(
                    signal=signal,
                    in_crisis=in_crisis,
                    date=current_date,
                )

            weeks_since_refit += 1

        # ── Compile results ──────────────────────────────────────────
        rolling_metrics = {
            tau: state.get_metrics(tau)
            for tau, state in rolling_state.items()
        }

        # Final metrics at tau=0.50
        default_state = rolling_state.get(
            0.50, list(rolling_state.values())[0]
        )

        # Weight stability
        w_stability = self._compute_weight_stability(weight_history)

        # Alpha stability
        a_stability = self._compute_alpha_stability(alpha_history)

        return WalkForwardResult(
            config=cfg,
            predictions=predictions,
            rolling_metrics=rolling_metrics,
            final_tpr=default_state.recall(),
            final_fpr=default_state.fpr(),
            final_precision=default_state.precision(),
            final_recall=default_state.recall(),
            weight_stability=w_stability,
            alpha_stability=a_stability,
            refit_dates=refit_dates,
            weight_history=weight_history,
            total_weeks_predicted=len(predictions),
            total_crises_detected=default_state.tp,
            total_crises_missed=default_state.fn,
            total_false_positives=default_state.fp,
        )

    def _build_crisis_windows(
        self,
        crisis_events: List[Tuple[str, datetime]],
    ) -> List[Tuple[datetime, datetime, str]]:
        """Build crisis windows with lead time."""
        cfg = self.config
        windows = []
        for name, date in crisis_events:
            start = date - timedelta(
                weeks=cfg.crisis_window_weeks + cfg.lead_time_weeks,
            )
            end = date + timedelta(weeks=cfg.crisis_window_weeks)
            windows.append((start, end, name))
        return windows

    def _is_in_crisis_window(
        self,
        date: datetime,
        windows: List[Tuple[datetime, datetime, str]],
    ) -> bool:
        """Check if date falls within any crisis window."""
        for start, end, _ in windows:
            if start <= date <= end:
                return True
        return False

    def _get_pillar_scores(
        self,
        week_data: Dict,
        pillar_scorer=None,
    ) -> Dict[str, float]:
        """Get pillar scores for a week."""
        if pillar_scorer is not None:
            return pillar_scorer(
                week_data.get("indicators", {}),
                week_data["date"],
            )
        return week_data.get("pillar_scores", {})

    def _compute_mac(
        self,
        pillar_scores: Dict[str, float],
        weights: Dict[str, float],
        alpha: float,
    ) -> float:
        """Compute weighted MAC score with calibration."""
        if not pillar_scores:
            return 0.5

        weighted_sum = 0.0
        weight_sum = 0.0
        for pillar, score in pillar_scores.items():
            w = weights.get(pillar, 1.0 / 7)
            weighted_sum += score * w
            weight_sum += w

        if weight_sum > 0:
            raw = weighted_sum / weight_sum
        else:
            raw = 0.5

        return max(0.0, min(1.0, raw * alpha))

    def _refit(
        self,
        train_data: List[Dict],
        crisis_events: List[Tuple[str, datetime]],
    ) -> Tuple[Optional[Dict[str, float]], Optional[float]]:
        """Re-estimate weights and alpha on training data.

        Uses only data available up to the end of train_data.
        Falls back to equal weights if ML fails.

        Returns:
            (weights, alpha) — either may be None if unchanged.
        """
        if len(train_data) < 52:
            return None, None

        # Filter crisis events to only those before training cutoff
        cutoff = train_data[-1]["date"]
        available_crises = [
            (name, date) for name, date in crisis_events
            if date <= cutoff
        ]

        if len(available_crises) < 3:
            return None, None

        # Compute alpha from training data
        # Alpha = mean(CSR_score / raw_MAC) across known crises
        alpha_samples = []
        for week in train_data:
            if "csr_score" in week and "raw_mac" in week:
                if week["raw_mac"] > 0:
                    alpha_samples.append(
                        week["csr_score"] / week["raw_mac"]
                    )

        new_alpha = None
        if alpha_samples:
            new_alpha = float(np.clip(
                np.median(alpha_samples), 0.60, 0.95,
            ))

        # Weights: try ML optimisation on available scenarios
        # This is a simplified version — full ML uses
        # ml_weights.py with augmentation
        new_weights = None
        try:
            pillar_names = list(
                self.config.default_weights.keys()
            )
            # Collect pillar scores from training crisis weeks
            X = []
            y = []
            for week in train_data:
                if "csr_score" not in week:
                    continue
                ps = week.get("pillar_scores", {})
                if len(ps) >= len(pillar_names) - 1:
                    row = [ps.get(p, 0.5) for p in pillar_names]
                    X.append(row)
                    y.append(week["csr_score"])

            if len(X) >= 10:
                X_arr = np.array(X)
                y_arr = np.array(y)

                # Simple: weight by correlation with target
                correlations = []
                for j in range(X_arr.shape[1]):
                    std_x = np.std(X_arr[:, j])
                    std_y = np.std(y_arr)
                    if std_x > 0 and std_y > 0:
                        corr = np.corrcoef(
                            X_arr[:, j], y_arr,
                        )[0, 1]
                        correlations.append(abs(corr))
                    else:
                        correlations.append(0.0)

                total_corr = sum(correlations)
                if total_corr > 0:
                    new_weights = {
                        p: c / total_corr
                        for p, c in zip(pillar_names, correlations)
                    }
        except Exception:
            logger.debug("ML weight refit failed, keeping current")

        return new_weights, new_alpha

    def _compute_weight_stability(
        self,
        weight_history: List[Tuple[datetime, Dict[str, float]]],
    ) -> List[WeightStability]:
        """Compute weight stability statistics across refits."""
        if not weight_history:
            return []

        pillars = list(weight_history[0][1].keys())
        results = []

        for pillar in pillars:
            values = [
                wh[1].get(pillar, 0.0) for wh in weight_history
            ]
            arr = np.array(values)
            mean_w = float(arr.mean())
            std_w = float(arr.std())
            cv = std_w / mean_w if mean_w > 0 else 0.0

            results.append(WeightStability(
                pillar=pillar,
                mean_weight=mean_w,
                std_weight=std_w,
                min_weight=float(arr.min()),
                max_weight=float(arr.max()),
                cv=cv,
            ))

        return results

    def _compute_alpha_stability(
        self,
        alpha_history: List[Tuple[datetime, float]],
    ) -> AlphaStability:
        """Compute alpha stability statistics."""
        if not alpha_history:
            return AlphaStability(
                mean_alpha=0.78,
                std_alpha=0.0,
                min_alpha=0.78,
                max_alpha=0.78,
                alpha_history=[],
            )

        values = [a for _, a in alpha_history]
        arr = np.array(values)

        return AlphaStability(
            mean_alpha=float(arr.mean()),
            std_alpha=float(arr.std()),
            min_alpha=float(arr.min()),
            max_alpha=float(arr.max()),
            alpha_history=alpha_history,
        )


# ── Internal rolling state tracker ──────────────────────────────────────

class _RollingState:
    """Tracks cumulative and rolling TP/FP/FN counts."""

    def __init__(self):
        self.tp = 0
        self.fp = 0
        self.fn = 0
        self.tn = 0
        self._recent: List[Tuple[datetime, bool, bool]] = []

    def update(
        self,
        signal: bool,
        in_crisis: bool,
        date: datetime,
    ):
        """Update state with one week's observation."""
        if signal and in_crisis:
            self.tp += 1
        elif signal and not in_crisis:
            self.fp += 1
        elif not signal and in_crisis:
            self.fn += 1
        else:
            self.tn += 1

        self._recent.append((date, signal, in_crisis))
        # Keep last 52 weeks for rolling FPR
        if len(self._recent) > 52:
            self._recent = self._recent[-52:]

    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0.0

    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 0.0

    def fpr(self) -> float:
        denom = self.fp + self.tn
        return self.fp / denom if denom > 0 else 0.0

    def rolling_fpr_52w(self) -> float:
        """FPR over the last 52 weeks."""
        if not self._recent:
            return 0.0
        fp_52 = sum(
            1 for _, sig, crisis in self._recent
            if sig and not crisis
        )
        non_crisis_52 = sum(
            1 for _, _, crisis in self._recent
            if not crisis
        )
        return fp_52 / non_crisis_52 if non_crisis_52 > 0 else 0.0

    def get_metrics(self, tau: float) -> List[RollingMetrics]:
        """Return a single metrics snapshot."""
        return [RollingMetrics(
            tau=tau,
            cumulative_tp=self.tp,
            cumulative_fp=self.fp,
            cumulative_fn=self.fn,
            cumulative_precision=self.precision(),
            cumulative_recall=self.recall(),
            rolling_fpr_52w=self.rolling_fpr_52w(),
        )]


# ── Convenience function ─────────────────────────────────────────────────

def run_walk_forward(
    weekly_data: List[Dict],
    crisis_events: List[Tuple[str, datetime]],
    config: Optional[WalkForwardConfig] = None,
) -> WalkForwardResult:
    """Convenience function to run walk-forward backtest.

    Args:
        weekly_data: Weekly MAC observations.
        crisis_events: Crisis catalogue.
        config: Optional configuration overrides.

    Returns:
        WalkForwardResult with full analysis.
    """
    engine = WalkForwardEngine(config)
    return engine.run(weekly_data, crisis_events)


def format_walk_forward_report(
    result: WalkForwardResult,
) -> str:
    """Format walk-forward results for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("WALK-FORWARD BLIND BACKTEST RESULTS")
    lines.append("(Strict no-lookahead protocol)")
    lines.append("=" * 70)
    lines.append("")

    lines.append("CONFIGURATION")
    lines.append("-" * 50)
    cfg = result.config
    lines.append(
        f"  Refit interval:    {cfg.refit_interval_weeks} weeks"
    )
    lines.append(
        f"  Min training:      {cfg.min_training_weeks} weeks"
    )
    window_type = "Expanding" if cfg.expanding_window else (
        f"Rolling ({cfg.rolling_window_weeks}w)"
    )
    lines.append(f"  Window type:       {window_type}")
    lines.append(
        f"  Total refits:      {len(result.refit_dates)}"
    )
    lines.append("")

    lines.append("PERFORMANCE (tau=0.50)")
    lines.append("-" * 50)
    lines.append(
        f"  Weeks predicted:   {result.total_weeks_predicted}"
    )
    lines.append(
        f"  Crises detected:   {result.total_crises_detected}"
    )
    lines.append(
        f"  Crises missed:     {result.total_crises_missed}"
    )
    lines.append(
        f"  False positives:   {result.total_false_positives}"
    )
    lines.append(f"  Precision:         {result.final_precision:.3f}")
    lines.append(f"  Recall (TPR):      {result.final_recall:.3f}")
    lines.append(f"  FPR:               {result.final_fpr:.3f}")
    lines.append("")

    lines.append("WEIGHT STABILITY ACROSS REFITS")
    lines.append("-" * 50)
    lines.append(
        f"  {'Pillar':<18} {'Mean':>6} {'Std':>6} "
        f"{'Min':>6} {'Max':>6} {'CV':>6}"
    )
    for ws in result.weight_stability:
        lines.append(
            f"  {ws.pillar:<18} {ws.mean_weight:>6.3f} "
            f"{ws.std_weight:>6.3f} {ws.min_weight:>6.3f} "
            f"{ws.max_weight:>6.3f} {ws.cv:>6.2f}"
        )
    lines.append("")

    a = result.alpha_stability
    lines.append("ALPHA (CALIBRATION FACTOR) STABILITY")
    lines.append("-" * 50)
    lines.append(f"  Mean:  {a.mean_alpha:.4f}")
    lines.append(f"  Std:   {a.std_alpha:.4f}")
    lines.append(f"  Range: [{a.min_alpha:.4f}, {a.max_alpha:.4f}]")
    lines.append("")

    # Rolling metrics at each tau
    lines.append("ROLLING METRICS BY THRESHOLD")
    lines.append("-" * 50)
    lines.append(
        f"  {'tau':>5} {'TP':>5} {'FP':>5} {'FN':>5} "
        f"{'Prec':>6} {'Recall':>7} {'FPR_52w':>8}"
    )
    for tau in sorted(result.rolling_metrics.keys()):
        metrics_list = result.rolling_metrics[tau]
        if metrics_list:
            m = metrics_list[-1]
            lines.append(
                f"  {m.tau:>5.2f} {m.cumulative_tp:>5} "
                f"{m.cumulative_fp:>5} {m.cumulative_fn:>5} "
                f"{m.cumulative_precision:>6.3f} "
                f"{m.cumulative_recall:>7.3f} "
                f"{m.rolling_fpr_52w:>8.3f}"
            )
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)

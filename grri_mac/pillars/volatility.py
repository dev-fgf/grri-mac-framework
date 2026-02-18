"""Volatility pillar scoring.

Question: Is the vol regime stable?

Indicators:
- VIX level
- VIX term structure (M2/M1)
- Realized vs implied volatility gap
- Time-varying Volatility Risk Premium (VRP) multiplier (v6 §4.4.5)

VRP Architecture (v6 §4.4.5):
  VRP_t = 1.05 + 0.015 × σ(vol-of-vol)_{12m}
  Clipped to [1.05, 1.55]
  
  Dual computation: both with and without VRP applied.
  Quality flag raised when |MAC_with_VRP − MAC_without_VRP| > 0.05.
"""

from dataclasses import dataclass
from typing import Optional
import math
import logging

from ..mac.scorer import score_indicator_range

logger = logging.getLogger(__name__)

# ── VRP constants (v6 §4.4.5) ───────────────────────────────────────────
VRP_BASE = 1.05          # Minimum premium (long-run average ~5%)
VRP_SENSITIVITY = 0.015  # Coefficient on vol-of-vol σ
VRP_FLOOR = 1.05         # Minimum VRP multiplier
VRP_CEILING = 1.55       # Maximum VRP multiplier
VRP_QUALITY_THRESHOLD = 0.05  # MAC divergence that triggers quality flag


@dataclass
class VolatilityIndicators:
    """Raw volatility indicator values."""

    vix_level: Optional[float] = None
    vix_term_structure: Optional[float] = None  # M2/M1 ratio
    realized_vol: Optional[float] = None
    implied_vol: Optional[float] = None
    vix_history: Optional[list[float]] = None  # For persistence + VRP calc


@dataclass
class VRPResult:
    """Time-varying Volatility Risk Premium calculation result."""

    vrp_multiplier: float = VRP_BASE    # The VRP_t value
    vol_of_vol_12m: Optional[float] = None  # σ(vol-of-vol) used
    data_quality: str = "good"          # "good", "insufficient", "stale"
    score_with_vrp: float = 0.5
    score_without_vrp: float = 0.5
    divergence: float = 0.0             # |with - without|
    quality_flag: bool = False          # True if divergence > threshold


@dataclass
class VolatilityScores:
    """Scored volatility indicators."""

    vix_level: float = 0.5
    term_structure: float = 0.5
    rv_iv_gap: float = 0.5
    composite: float = 0.5
    vrp: Optional[VRPResult] = None     # VRP dual computation result


class VolatilityPillar:
    """Volatility pillar calculator."""

    # Thresholds from specification
    THRESHOLDS = {
        "vix_level": {
            # VIX 15-20 is ample (stable)
            # < 12 or 20-35 is thin
            # < 10 or > 35 is breaching
            "ample_low": 15,
            "ample_high": 20,
            "thin_low": 12,
            "thin_high": 35,
            "breach_low": 10,
            "breach_high": 50,
        },
        "term_structure": {
            # M2/M1 ratio of 1.00-1.05 is ample (normal contango)
            # < 0.95 or > 1.08 is thin
            # < 0.90 or > 1.10 is breaching
            "ample_low": 1.00,
            "ample_high": 1.05,
            "thin_low": 0.95,
            "thin_high": 1.08,
            "breach_low": 0.90,
            "breach_high": 1.10,
        },
        "rv_iv_gap": {
            # RV within 20% of IV is ample
            # 20-40% gap is thin
            # > 40% gap is breaching
            "ample": 20,
            "thin": 40,
            "breach": 60,
        },
    }

    def __init__(self, fred_client=None, etf_client=None):
        """
        Initialize volatility pillar.

        Args:
            fred_client: FREDClient instance for VIX data
            etf_client: ETFClient instance for term structure proxy
        """
        self.fred = fred_client
        self.etf = etf_client

    def fetch_indicators(self) -> VolatilityIndicators:
        """Fetch current volatility indicators from data sources."""
        indicators = VolatilityIndicators()

        if self.fred:
            try:
                indicators.vix_level = self.fred.get_vix()
            except Exception:
                pass

        if self.etf:
            try:
                m1, m2 = self.etf.get_vix_term_structure()
                if m1 > 0 and m2 > 0:
                    # This is a rough proxy - true term structure needs VIX futures
                    pass
            except Exception:
                pass

        return indicators

    def score_vix_level(self, vix: float) -> float:
        """Score VIX level (15-20 is optimal)."""
        t = self.THRESHOLDS["vix_level"]
        return score_indicator_range(
            vix,
            ample_range=(t["ample_low"], t["ample_high"]),
            thin_range=(t["thin_low"], t["thin_high"]),
            breach_range=(t["breach_low"], t["breach_high"]),
        )

    def score_term_structure(self, m2_m1_ratio: float) -> float:
        """Score VIX term structure (1.00-1.05 is optimal)."""
        t = self.THRESHOLDS["term_structure"]
        return score_indicator_range(
            m2_m1_ratio,
            ample_range=(t["ample_low"], t["ample_high"]),
            thin_range=(t["thin_low"], t["thin_high"]),
            breach_range=(t["breach_low"], t["breach_high"]),
        )

    def score_rv_iv_gap(self, realized_vol: float, implied_vol: float) -> float:
        """Score realized vs implied volatility gap."""
        if implied_vol == 0:
            return 0.5

        gap_pct = abs(realized_vol - implied_vol) / implied_vol * 100
        t = self.THRESHOLDS["rv_iv_gap"]

        if gap_pct <= t["ample"]:
            return 1.0
        elif gap_pct <= t["thin"]:
            return 0.5 + 0.5 * (t["thin"] - gap_pct) / (t["thin"] - t["ample"])
        elif gap_pct <= t["breach"]:
            return 0.5 * (t["breach"] - gap_pct) / (t["breach"] - t["thin"])
        else:
            return 0.0

    def calculate_vix_persistence_penalty(
        self,
        vix_history: list[float],
        lookback_days: int = 60,
        low_vol_threshold: float = 15.0,
        penalty_per_day: float = 0.003,
        max_penalty: float = 0.15,
    ) -> float:
        """
        Calculate penalty for extended periods of suppressed volatility.

        Extended low-vol periods lead to complacency and vol-selling buildup,
        creating conditions for sharp corrections (e.g., Feb 2018 Volmageddon).

        Args:
            vix_history: List of recent VIX values (most recent last)
            lookback_days: Days to look back for persistence
            low_vol_threshold: VIX level considered "suppressed"
            penalty_per_day: Score reduction per day below threshold
            max_penalty: Maximum penalty to apply

        Returns:
            Penalty factor (0.0 to max_penalty) to subtract from VIX score
        """
        if not vix_history:
            return 0.0

        # Use last N days
        recent = vix_history[-lookback_days:] if len(vix_history) > lookback_days \
            else vix_history

        # Count consecutive days below threshold (from most recent)
        low_vol_days = 0
        for vix in reversed(recent):
            if vix < low_vol_threshold:
                low_vol_days += 1
            else:
                break  # Stop at first day above threshold

        # Calculate penalty
        penalty = low_vol_days * penalty_per_day
        return min(penalty, max_penalty)

    def calculate_realized_vol(self, returns: list[float], annualize: bool = True) -> float:
        """
        Calculate realized volatility from returns.

        Args:
            returns: List of daily returns
            annualize: Whether to annualize (multiply by sqrt(252))

        Returns:
            Realized volatility
        """
        if not returns:
            return 0.0

        n = len(returns)
        mean = sum(returns) / n
        variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
        std = math.sqrt(variance)

        if annualize:
            return std * math.sqrt(252) * 100  # Annualized, in percent
        return std * 100

    def calculate_vol_of_vol(
        self,
        vix_history: list[float],
        lookback_days: int = 252,
    ) -> Optional[float]:
        """Calculate rolling standard deviation of VIX changes (vol-of-vol).

        This measures how erratic the volatility regime itself is.
        Used as the time-varying input to VRP estimation.

        Args:
            vix_history: List of VIX values (most recent last)
            lookback_days: Rolling window (default: 252 = 12 months)

        Returns:
            σ(vol-of-vol) over the lookback window, or None if insufficient data
        """
        if not vix_history or len(vix_history) < max(20, lookback_days // 2):
            return None

        # Use available history up to lookback_days
        recent = vix_history[-lookback_days:] if len(vix_history) > lookback_days \
            else vix_history

        # Daily VIX changes (not returns — VIX is already in vol space)
        changes = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        if len(changes) < 10:
            return None

        n = len(changes)
        mean_change = sum(changes) / n
        variance = sum((c - mean_change) ** 2 for c in changes) / (n - 1)
        return math.sqrt(variance)

    def calculate_vrp(
        self,
        vix_history: Optional[list[float]] = None,
        lookback_days: int = 252,
    ) -> VRPResult:
        """Calculate time-varying Volatility Risk Premium (v6 §4.4.5).

        Formula: VRP_t = 1.05 + 0.015 × σ(vol-of-vol)_{12m}
        Clipped to [1.05, 1.55].

        The VRP multiplier scales the volatility pillar score, reflecting
        that high vol-of-vol regimes carry additional risk beyond what
        the VIX level alone captures.

        Args:
            vix_history: Historical VIX values for vol-of-vol calculation
            lookback_days: Rolling window for σ calculation

        Returns:
            VRPResult with multiplier, diagnostics, and quality assessment
        """
        result = VRPResult()

        if not vix_history or len(vix_history) < 20:
            result.data_quality = "insufficient"
            return result

        vol_of_vol = self.calculate_vol_of_vol(vix_history, lookback_days)
        if vol_of_vol is None:
            result.data_quality = "insufficient"
            return result

        result.vol_of_vol_12m = vol_of_vol

        # VRP_t = 1.05 + 0.015 × σ(vol-of-vol)
        raw_vrp = VRP_BASE + VRP_SENSITIVITY * vol_of_vol
        result.vrp_multiplier = max(VRP_FLOOR, min(VRP_CEILING, raw_vrp))

        # Data quality: if we have less than half the lookback, flag it
        if len(vix_history) < lookback_days // 2:
            result.data_quality = "insufficient"
        elif len(vix_history) < lookback_days:
            result.data_quality = "partial"
        else:
            result.data_quality = "good"

        return result

    def calculate(
        self,
        indicators: Optional[VolatilityIndicators] = None,
        apply_persistence_penalty: bool = True,
        apply_vrp: bool = True,
    ) -> VolatilityScores:
        """
        Calculate volatility pillar scores.

        Dual computation (v6 §4.4.5): calculates both with and without VRP.
        Reports divergence and raises quality flag if > 0.05 threshold.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.
            apply_persistence_penalty: Apply penalty for extended low-vol
            apply_vrp: Apply time-varying VRP multiplier

        Returns:
            VolatilityScores with individual and composite scores + VRP result
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = VolatilityScores()
        scored_count = 0

        if indicators.vix_level is not None:
            scores.vix_level = self.score_vix_level(indicators.vix_level)
            scored_count += 1

        if indicators.vix_term_structure is not None:
            scores.term_structure = self.score_term_structure(
                indicators.vix_term_structure
            )
            scored_count += 1

        if indicators.realized_vol is not None and indicators.implied_vol is not None:
            scores.rv_iv_gap = self.score_rv_iv_gap(
                indicators.realized_vol, indicators.implied_vol
            )
            scored_count += 1

        # Calculate base composite (without VRP)
        base_composite = 0.5
        if scored_count > 0:
            total = 0.0
            if indicators.vix_level is not None:
                total += scores.vix_level
            if indicators.vix_term_structure is not None:
                total += scores.term_structure
            if indicators.realized_vol is not None and indicators.implied_vol is not None:
                total += scores.rv_iv_gap
            base_composite = total / scored_count

            # Apply VIX persistence penalty if enabled
            if apply_persistence_penalty and indicators.vix_history:
                persistence_penalty = self.calculate_vix_persistence_penalty(
                    indicators.vix_history
                )
                base_composite = max(0.0, base_composite - persistence_penalty)

        # ── VRP dual computation (v6 §4.4.5) ────────────────────────
        vrp_result = self.calculate_vrp(indicators.vix_history)
        vrp_result.score_without_vrp = base_composite

        if apply_vrp and vrp_result.data_quality != "insufficient":
            # VRP multiplier amplifies the distance from "safe" (1.0)
            # Higher VRP → larger penalty when composite < 1.0
            # score_with_vrp = 1.0 - (1.0 - base) × VRP_t
            gap = 1.0 - base_composite
            adjusted_gap = gap * vrp_result.vrp_multiplier
            vrp_composite = max(0.0, 1.0 - adjusted_gap)

            vrp_result.score_with_vrp = vrp_composite
            vrp_result.divergence = abs(vrp_composite - base_composite)
            vrp_result.quality_flag = vrp_result.divergence > VRP_QUALITY_THRESHOLD

            scores.composite = vrp_composite
        else:
            vrp_result.score_with_vrp = base_composite
            scores.composite = base_composite

        scores.vrp = vrp_result
        return scores

    def get_score(self) -> float:
        """Get composite volatility score."""
        return self.calculate().composite

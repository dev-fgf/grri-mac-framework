"""Volatility pillar scoring.

Question: Is the vol regime stable?

Indicators:
- VIX level
- VIX term structure (M2/M1)
- Realized vs implied volatility gap
"""

from dataclasses import dataclass
from typing import Optional
import math

from ..mac.scorer import score_indicator_range


@dataclass
class VolatilityIndicators:
    """Raw volatility indicator values."""

    vix_level: Optional[float] = None
    vix_term_structure: Optional[float] = None  # M2/M1 ratio
    realized_vol: Optional[float] = None
    implied_vol: Optional[float] = None
    vix_history: Optional[list[float]] = None  # For persistence calculation


@dataclass
class VolatilityScores:
    """Scored volatility indicators."""

    vix_level: float = 0.5
    term_structure: float = 0.5
    rv_iv_gap: float = 0.5
    composite: float = 0.5


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

    def calculate(
        self,
        indicators: Optional[VolatilityIndicators] = None,
        apply_persistence_penalty: bool = True,
    ) -> VolatilityScores:
        """
        Calculate volatility pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.
            apply_persistence_penalty: Apply penalty for extended low-vol

        Returns:
            VolatilityScores with individual and composite scores
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

        # Calculate composite
        if scored_count > 0:
            total = 0.0
            if indicators.vix_level is not None:
                total += scores.vix_level
            if indicators.vix_term_structure is not None:
                total += scores.term_structure
            if indicators.realized_vol is not None and indicators.implied_vol is not None:
                total += scores.rv_iv_gap
            scores.composite = total / scored_count

            # Apply VIX persistence penalty if enabled and history available
            if apply_persistence_penalty and indicators.vix_history:
                persistence_penalty = self.calculate_vix_persistence_penalty(
                    indicators.vix_history
                )
                scores.composite = max(0.0, scores.composite - persistence_penalty)
        else:
            scores.composite = 0.5

        return scores

    def get_score(self) -> float:
        """Get composite volatility score."""
        return self.calculate().composite

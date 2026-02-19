"""Regime-dependent adaptive valuation bands.

Replaces fixed ample/thin/breach thresholds with rolling-percentile
bands that adapt to the rate and volatility regime. In QE eras, normal
spreads are tighter; in tightening eras, normal spreads are wider.

This is opt-in: the default ValuationPillar behaviour is unchanged.

Usage:
    from grri_mac.pillars.valuation_adaptive import (
        AdaptiveValuationBands,
    )
    bands = AdaptiveValuationBands()
    score = bands.score_with_regime(
        ig_oas=95,
        history=[...],
        regime="qe",
    )
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AdaptiveBand:
    """Adaptive threshold band computed from rolling percentiles."""

    ample_low: float
    ample_high: float
    thin_low: float
    thin_high: float
    breach_low: float
    breach_high: float
    lookback_years: int
    n_observations: int


@dataclass
class AdaptiveScoreResult:
    """Result of adaptive valuation scoring."""

    score: float
    current_value: float
    band: AdaptiveBand
    regime: str
    method: str = "adaptive"  # "adaptive" or "fixed_fallback"


class AdaptiveValuationBands:
    """Compute regime-dependent valuation threshold bands.

    Uses rolling percentiles over a configurable lookback to define
    what counts as "ample", "thin", and "breach" in the current regime.

    Ample: 25th-75th percentile of historical distribution
    Thin: 10th-90th percentile
    Breach: below 5th or above 95th percentile
    """

    # Default lookback in weeks (~10 years)
    DEFAULT_LOOKBACK_WEEKS = 520

    # Regime-specific adjustments (shifts to percentile boundaries)
    REGIME_ADJUSTMENTS = {
        "qe": {
            # In QE: spreads structurally tighter, so narrow the bands
            "ample_pct": (30, 70),
            "thin_pct": (15, 85),
            "breach_pct": (5, 95),
        },
        "tightening": {
            # In tightening: spreads structurally wider, widen bands
            "ample_pct": (20, 80),
            "thin_pct": (8, 92),
            "breach_pct": (3, 97),
        },
        "neutral": {
            # Standard percentiles
            "ample_pct": (25, 75),
            "thin_pct": (10, 90),
            "breach_pct": (5, 95),
        },
    }

    def __init__(
        self,
        lookback_weeks: int = DEFAULT_LOOKBACK_WEEKS,
    ):
        self.lookback_weeks = lookback_weeks

    def compute_bands(
        self,
        history: list[float],
        regime: str = "neutral",
    ) -> Optional[AdaptiveBand]:
        """Compute adaptive bands from historical distribution.

        Args:
            history: Historical values (most recent last)
            regime: "qe", "tightening", or "neutral"

        Returns:
            AdaptiveBand or None if insufficient data
        """
        if not history or len(history) < 52:
            return None

        # Use lookback window
        window = history[-self.lookback_weeks:]
        arr = np.array(window)

        # Get regime-specific percentile boundaries
        pcts = self.REGIME_ADJUSTMENTS.get(
            regime, self.REGIME_ADJUSTMENTS["neutral"]
        )

        ample_lo, ample_hi = np.percentile(
            arr, pcts["ample_pct"]
        )
        thin_lo, thin_hi = np.percentile(
            arr, pcts["thin_pct"]
        )
        breach_lo, breach_hi = np.percentile(
            arr, pcts["breach_pct"]
        )

        return AdaptiveBand(
            ample_low=float(ample_lo),
            ample_high=float(ample_hi),
            thin_low=float(thin_lo),
            thin_high=float(thin_hi),
            breach_low=float(breach_lo),
            breach_high=float(breach_hi),
            lookback_years=len(window) // 52,
            n_observations=len(window),
        )

    def score_with_regime(
        self,
        current_value: float,
        history: list[float],
        regime: str = "neutral",
    ) -> AdaptiveScoreResult:
        """Score a valuation indicator using adaptive bands.

        Both too-tight AND too-wide spreads are penalised (range-based).

        Args:
            current_value: Current indicator value (e.g., IG OAS)
            history: Historical values for band computation
            regime: Current monetary policy regime

        Returns:
            AdaptiveScoreResult with score and band info
        """
        band = self.compute_bands(history, regime)

        if band is None:
            # Fall back to fixed scoring
            return AdaptiveScoreResult(
                score=0.5,
                current_value=current_value,
                band=AdaptiveBand(
                    ample_low=0, ample_high=0,
                    thin_low=0, thin_high=0,
                    breach_low=0, breach_high=0,
                    lookback_years=0, n_observations=0,
                ),
                regime=regime,
                method="fixed_fallback",
            )

        # Range-based scoring (both extremes are bad)
        score = self._score_range(current_value, band)

        return AdaptiveScoreResult(
            score=score,
            current_value=current_value,
            band=band,
            regime=regime,
            method="adaptive",
        )

    def _score_range(
        self, value: float, band: AdaptiveBand
    ) -> float:
        """Score a value within adaptive range bands.

        Returns 1.0 if within ample range, 0.5 if within thin,
        0.0 if outside breach range. Linear interpolation between.
        """
        # Within ample range → 1.0
        if band.ample_low <= value <= band.ample_high:
            return 1.0

        # Between ample and thin boundaries
        if band.thin_low <= value < band.ample_low:
            span = band.ample_low - band.thin_low
            if span > 0:
                return 0.5 + 0.5 * (
                    value - band.thin_low
                ) / span
            return 0.5

        if band.ample_high < value <= band.thin_high:
            span = band.thin_high - band.ample_high
            if span > 0:
                return 0.5 + 0.5 * (
                    band.thin_high - value
                ) / span
            return 0.5

        # Between thin and breach boundaries
        if band.breach_low <= value < band.thin_low:
            span = band.thin_low - band.breach_low
            if span > 0:
                return 0.5 * (
                    value - band.breach_low
                ) / span
            return 0.0

        if band.thin_high < value <= band.breach_high:
            span = band.breach_high - band.thin_high
            if span > 0:
                return 0.5 * (
                    band.breach_high - value
                ) / span
            return 0.0

        # Outside breach range → 0.0
        return 0.0

    def detect_regime(
        self,
        fed_balance_sheet_gdp_pct: Optional[float] = None,
        fed_funds_rate_change_12m: Optional[float] = None,
    ) -> str:
        """Auto-detect the current monetary policy regime.

        Args:
            fed_balance_sheet_gdp_pct: Fed B/S as % of GDP
            fed_funds_rate_change_12m: 12-month change in Fed Funds

        Returns:
            "qe", "tightening", or "neutral"
        """
        if fed_balance_sheet_gdp_pct is not None:
            if fed_balance_sheet_gdp_pct > 25:
                return "qe"

        if fed_funds_rate_change_12m is not None:
            if fed_funds_rate_change_12m > 1.0:
                return "tightening"
            elif fed_funds_rate_change_12m < -1.0:
                return "qe"

        return "neutral"

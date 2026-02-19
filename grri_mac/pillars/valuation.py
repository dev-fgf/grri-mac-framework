"""Valuation pillar scoring.

Question: Are risk premia adequate buffers?

Indicators:
- 10Y term premium
- IG OAS (Investment Grade Option-Adjusted Spread)
- HY OAS (High Yield Option-Adjusted Spread)

Scoring approach: RANGE-BASED (two-sided)
Both compressed AND extremely wide spreads indicate problems:
- Compressed = complacency / repricing risk
- Wide = crisis / distress
Only spreads in a "healthy" middle range score as ample.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ..mac.scorer import score_indicator_range

logger = logging.getLogger(__name__)

# Try to import adaptive valuation bands (v7 enhancement)
try:
    from .valuation_adaptive import AdaptiveValuationBands
    _ADAPTIVE_AVAILABLE = True
except ImportError:
    _ADAPTIVE_AVAILABLE = False


@dataclass
class ValuationIndicators:
    """Raw valuation indicator values."""

    term_premium_10y_bps: Optional[float] = None
    ig_oas_bps: Optional[float] = None
    hy_oas_bps: Optional[float] = None


@dataclass
class ValuationScores:
    """Scored valuation indicators."""

    term_premium: float = 0.5
    ig_oas: float = 0.5
    hy_oas: float = 0.5
    composite: float = 0.5


class ValuationPillar:
    """Valuation pillar calculator."""

    # Range-based thresholds: both too-tight AND too-wide = bad
    # Calibrated from historical backtest analysis
    THRESHOLDS = {
        "term_premium": {
            "ample_low": 40,       # Normal range: 40-120 bps
            "ample_high": 120,
            "thin_low": 0,         # Thin: 0-40 or 120-200
            "thin_high": 200,
            "breach_low": -50,     # Breach: < -50 (inversion) or > 250 (panic)
            "breach_high": 250,
        },
        "ig_oas": {
            "ample_low": 100,      # Normal range: 100-180 bps
            "ample_high": 180,
            "thin_low": 75,        # Thin: 75-100 or 180-280
            "thin_high": 280,
            "breach_low": 60,      # Breach: < 60 (too tight) or > 400 (crisis)
            "breach_high": 400,
        },
        "hy_oas": {
            "ample_low": 350,      # Normal range: 350-550 bps
            "ample_high": 550,
            "thin_low": 280,       # Thin: 280-350 or 550-800
            "thin_high": 800,
            "breach_low": 200,     # Breach: < 200 (too tight) or > 1000 (crisis)
            "breach_high": 1000,
        },
    }

    def __init__(self, fred_client=None, use_adaptive_bands=True):
        """
        Initialize valuation pillar.

        Args:
            fred_client: FREDClient instance for fetching data
            use_adaptive_bands: Use regime-dependent adaptive bands (v7)
        """
        self.fred = fred_client
        self._adaptive_bands = None
        if use_adaptive_bands and _ADAPTIVE_AVAILABLE:
            self._adaptive_bands = AdaptiveValuationBands()
        # Accumulate history for adaptive scoring
        self._ig_oas_history: list[float] = []
        self._hy_oas_history: list[float] = []
        self._tp_history: list[float] = []

    def fetch_indicators(self) -> ValuationIndicators:
        """Fetch current valuation indicators from data sources."""
        indicators = ValuationIndicators()

        if self.fred:
            try:
                indicators.term_premium_10y_bps = self.fred.get_term_premium_10y()
            except Exception:
                pass

            try:
                indicators.ig_oas_bps = self.fred.get_ig_oas()
            except Exception:
                pass

            try:
                indicators.hy_oas_bps = self.fred.get_hy_oas()
            except Exception:
                pass

        return indicators

    def score_term_premium(self, tp_bps: float) -> float:
        """Score 10Y term premium (should be in healthy range)."""
        t = self.THRESHOLDS["term_premium"]
        return score_indicator_range(
            tp_bps,
            ample_range=(t["ample_low"], t["ample_high"]),
            thin_range=(t["thin_low"], t["thin_high"]),
            breach_range=(t["breach_low"], t["breach_high"]),
        )

    def score_ig_oas(self, oas_bps: float) -> float:
        """Score IG OAS (should be in healthy range; too tight or too wide = bad)."""
        t = self.THRESHOLDS["ig_oas"]
        return score_indicator_range(
            oas_bps,
            ample_range=(t["ample_low"], t["ample_high"]),
            thin_range=(t["thin_low"], t["thin_high"]),
            breach_range=(t["breach_low"], t["breach_high"]),
        )

    def score_hy_oas(self, oas_bps: float) -> float:
        """Score HY OAS (should be in healthy range; too tight or too wide = bad)."""
        t = self.THRESHOLDS["hy_oas"]
        return score_indicator_range(
            oas_bps,
            ample_range=(t["ample_low"], t["ample_high"]),
            thin_range=(t["thin_low"], t["thin_high"]),
            breach_range=(t["breach_low"], t["breach_high"]),
        )

    def calculate(
        self,
        indicators: Optional[ValuationIndicators] = None,
        regime: str = "neutral",
    ) -> ValuationScores:
        """
        Calculate valuation pillar scores.

        v7: When sufficient history is accumulated and adaptive bands
        are available, uses regime-dependent rolling percentile bands
        instead of fixed thresholds.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.
            regime: Monetary policy regime ("qe", "tightening", "neutral")

        Returns:
            ValuationScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        # Accumulate history for adaptive scoring
        if indicators.ig_oas_bps is not None:
            self._ig_oas_history.append(indicators.ig_oas_bps)
        if indicators.hy_oas_bps is not None:
            self._hy_oas_history.append(indicators.hy_oas_bps)
        if indicators.term_premium_10y_bps is not None:
            self._tp_history.append(indicators.term_premium_10y_bps)

        scores = ValuationScores()
        scored_count = 0

        # v7: Try adaptive bands if sufficient history
        use_adaptive = (
            self._adaptive_bands is not None
            and len(self._ig_oas_history) >= 52
        )

        if indicators.term_premium_10y_bps is not None:
            if use_adaptive and len(self._tp_history) >= 52:
                result = self._adaptive_bands.score_with_regime(
                    indicators.term_premium_10y_bps,
                    self._tp_history,
                    regime,
                )
                scores.term_premium = result.score
            else:
                scores.term_premium = self.score_term_premium(
                    indicators.term_premium_10y_bps
                )
            scored_count += 1

        if indicators.ig_oas_bps is not None:
            if use_adaptive:
                result = self._adaptive_bands.score_with_regime(
                    indicators.ig_oas_bps,
                    self._ig_oas_history,
                    regime,
                )
                scores.ig_oas = result.score
            else:
                scores.ig_oas = self.score_ig_oas(indicators.ig_oas_bps)
            scored_count += 1

        if indicators.hy_oas_bps is not None:
            if use_adaptive and len(self._hy_oas_history) >= 52:
                result = self._adaptive_bands.score_with_regime(
                    indicators.hy_oas_bps,
                    self._hy_oas_history,
                    regime,
                )
                scores.hy_oas = result.score
            else:
                scores.hy_oas = self.score_hy_oas(indicators.hy_oas_bps)
            scored_count += 1

        # Calculate composite
        if scored_count > 0:
            total = 0.0
            if indicators.term_premium_10y_bps is not None:
                total += scores.term_premium
            if indicators.ig_oas_bps is not None:
                total += scores.ig_oas
            if indicators.hy_oas_bps is not None:
                total += scores.hy_oas
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5

        return scores

    def get_score(self) -> float:
        """Get composite valuation score."""
        return self.calculate().composite

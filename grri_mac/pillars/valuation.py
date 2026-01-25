"""Valuation pillar scoring.

Question: Are risk premia adequate buffers?

Indicators:
- 10Y term premium
- IG OAS (Investment Grade Option-Adjusted Spread)
- HY OAS (High Yield Option-Adjusted Spread)
"""

from dataclasses import dataclass
from typing import Optional

from ..mac.scorer import score_indicator_simple


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

    # Thresholds from specification (in basis points)
    THRESHOLDS = {
        "term_premium": {
            "ample": 100,   # > 100 bps
            "thin": 0,      # 0-100 bps
            "breach": -50,  # < 0 bps (using -50 as deep breach)
        },
        "ig_oas": {
            "ample": 150,  # > 150 bps
            "thin": 80,    # 80-150 bps
            "breach": 50,  # < 80 bps (using 50 as deep breach)
        },
        "hy_oas": {
            "ample": 450,  # > 450 bps
            "thin": 300,   # 300-450 bps
            "breach": 200, # < 300 bps (using 200 as deep breach)
        },
    }

    def __init__(self, fred_client=None):
        """
        Initialize valuation pillar.

        Args:
            fred_client: FREDClient instance for fetching data
        """
        self.fred = fred_client

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
        """Score 10Y term premium (higher is better)."""
        t = self.THRESHOLDS["term_premium"]
        return score_indicator_simple(
            tp_bps,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=False,
        )

    def score_ig_oas(self, oas_bps: float) -> float:
        """Score IG OAS (higher spread = more buffer = better)."""
        t = self.THRESHOLDS["ig_oas"]
        return score_indicator_simple(
            oas_bps,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=False,
        )

    def score_hy_oas(self, oas_bps: float) -> float:
        """Score HY OAS (higher spread = more buffer = better)."""
        t = self.THRESHOLDS["hy_oas"]
        return score_indicator_simple(
            oas_bps,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=False,
        )

    def calculate(
        self,
        indicators: Optional[ValuationIndicators] = None,
    ) -> ValuationScores:
        """
        Calculate valuation pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            ValuationScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = ValuationScores()
        scored_count = 0

        if indicators.term_premium_10y_bps is not None:
            scores.term_premium = self.score_term_premium(indicators.term_premium_10y_bps)
            scored_count += 1

        if indicators.ig_oas_bps is not None:
            scores.ig_oas = self.score_ig_oas(indicators.ig_oas_bps)
            scored_count += 1

        if indicators.hy_oas_bps is not None:
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

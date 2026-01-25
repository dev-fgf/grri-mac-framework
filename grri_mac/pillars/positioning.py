"""Positioning pillar scoring.

Question: Is leverage manageable and positioning diverse?

Indicators:
- Basis trade size
- Treasury spec net (percentile)
- SVXY AUM
"""

from dataclasses import dataclass
from typing import Optional

from ..mac.scorer import score_indicator_simple, score_indicator_range


@dataclass
class PositioningIndicators:
    """Raw positioning indicator values."""

    basis_trade_size_billions: Optional[float] = None
    treasury_spec_net_percentile: Optional[float] = None
    svxy_aum_millions: Optional[float] = None


@dataclass
class PositioningScores:
    """Scored positioning indicators."""

    basis_trade: float = 0.5
    spec_net: float = 0.5
    svxy_aum: float = 0.5
    composite: float = 0.5


class PositioningPillar:
    """Positioning pillar calculator."""

    # Thresholds from specification
    THRESHOLDS = {
        "basis_trade": {
            "ample": 400,   # < $400B
            "thin": 700,    # $400-700B
            "breach": 900,  # > $700B
        },
        "spec_net_percentile": {
            # Should be in 25th-75th percentile (ample)
            # 10th-90th percentile (thin)
            # < 5th or > 95th percentile (breach)
            "ample_low": 25,
            "ample_high": 75,
            "thin_low": 10,
            "thin_high": 90,
            "breach_low": 5,
            "breach_high": 95,
        },
        "svxy_aum": {
            "ample": 500,   # < $500M
            "thin": 1000,   # $500M-1B
            "breach": 1500, # > $1B
        },
    }

    def __init__(self, cftc_client=None, etf_client=None):
        """
        Initialize positioning pillar.

        Args:
            cftc_client: CFTCClient instance for COT data
            etf_client: ETFClient instance for ETF data
        """
        self.cftc = cftc_client
        self.etf = etf_client

    def fetch_indicators(self) -> PositioningIndicators:
        """Fetch current positioning indicators from data sources."""
        indicators = PositioningIndicators()

        if self.cftc:
            try:
                indicators.treasury_spec_net_percentile = (
                    self.cftc.get_spec_net_percentile("10Y")
                )
            except Exception:
                pass

        if self.etf:
            try:
                indicators.svxy_aum_millions = self.etf.get_svxy_aum()
            except Exception:
                pass

        # Basis trade size requires Fed research data (quarterly)
        # Would need manual input or specialized data source
        return indicators

    def score_basis_trade(self, size_billions: float) -> float:
        """Score basis trade size (lower is better)."""
        t = self.THRESHOLDS["basis_trade"]
        return score_indicator_simple(
            size_billions,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_spec_net(self, percentile: float) -> float:
        """Score Treasury spec net positioning (middle is better)."""
        t = self.THRESHOLDS["spec_net_percentile"]
        return score_indicator_range(
            percentile,
            ample_range=(t["ample_low"], t["ample_high"]),
            thin_range=(t["thin_low"], t["thin_high"]),
            breach_range=(t["breach_low"], t["breach_high"]),
        )

    def score_svxy_aum(self, aum_millions: float) -> float:
        """Score SVXY AUM (lower is better - less short vol exposure)."""
        t = self.THRESHOLDS["svxy_aum"]
        return score_indicator_simple(
            aum_millions,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def calculate(
        self,
        indicators: Optional[PositioningIndicators] = None,
    ) -> PositioningScores:
        """
        Calculate positioning pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            PositioningScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = PositioningScores()
        scored_count = 0

        if indicators.basis_trade_size_billions is not None:
            scores.basis_trade = self.score_basis_trade(
                indicators.basis_trade_size_billions
            )
            scored_count += 1

        if indicators.treasury_spec_net_percentile is not None:
            scores.spec_net = self.score_spec_net(
                indicators.treasury_spec_net_percentile
            )
            scored_count += 1

        if indicators.svxy_aum_millions is not None:
            scores.svxy_aum = self.score_svxy_aum(indicators.svxy_aum_millions)
            scored_count += 1

        # Calculate composite
        if scored_count > 0:
            total = 0.0
            if indicators.basis_trade_size_billions is not None:
                total += scores.basis_trade
            if indicators.treasury_spec_net_percentile is not None:
                total += scores.spec_net
            if indicators.svxy_aum_millions is not None:
                total += scores.svxy_aum
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5

        return scores

    def get_score(self) -> float:
        """Get composite positioning score."""
        return self.calculate().composite

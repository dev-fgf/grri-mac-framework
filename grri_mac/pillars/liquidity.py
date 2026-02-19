"""Liquidity pillar scoring.

Question: Can markets transact without disorderly price impact?

Indicators:
- SOFR-IORB spread
- CP-Treasury spread
- Cross-currency basis (EUR/USD)
- Treasury bid-ask
"""

from dataclasses import dataclass
from typing import Any, Optional

from ..mac.scorer import score_indicator_simple


@dataclass
class LiquidityIndicators:
    """Raw liquidity indicator values."""

    sofr_iorb_spread_bps: Optional[float] = None
    cp_treasury_spread_bps: Optional[float] = None
    cross_currency_basis_bps: Optional[float] = None
    treasury_bid_ask_32nds: Optional[float] = None


@dataclass
class LiquidityScores:
    """Scored liquidity indicators."""

    sofr_iorb: float = 0.5
    cp_treasury: float = 0.5
    cross_currency: float = 0.5
    bid_ask: float = 0.5
    composite: float = 0.5


class LiquidityPillar:
    """Liquidity pillar calculator."""

    # Thresholds from specification (in basis points)
    THRESHOLDS: dict[str, Any] = {
        "sofr_iorb": {
            "ample": 5,    # < 5 bps
            "thin": 25,    # 5-25 bps
            "breach": 50,  # > 25 bps (using 50 as breach point)
        },
        "cp_treasury": {
            "ample": 20,   # < 20 bps
            "thin": 50,    # 20-50 bps
            "breach": 100,  # > 50 bps
        },
        "cross_currency": {
            "ample": -30,   # > -30 bps (less negative is better)
            "thin": -75,    # -30 to -75 bps
            "breach": -120,  # < -75 bps
        },
        "bid_ask": {
            "ample": 1.0,  # < 1/32
            "thin": 2.0,   # 1-2/32
            "breach": 4.0,  # > 2/32
        },
    }

    def __init__(self, fred_client=None, etf_client=None):
        """
        Initialize liquidity pillar.

        Args:
            fred_client: FREDClient instance for fetching data
            etf_client: ETFClient instance for additional data
        """
        self.fred = fred_client
        self.etf = etf_client

    def fetch_indicators(self) -> LiquidityIndicators:
        """Fetch current liquidity indicators from data sources."""
        indicators = LiquidityIndicators()

        if self.fred:
            try:
                indicators.sofr_iorb_spread_bps = self.fred.get_sofr_iorb_spread()
            except Exception:
                pass

            try:
                indicators.cp_treasury_spread_bps = self.fred.get_cp_treasury_spread()
            except Exception:
                pass

        # Cross-currency basis and bid-ask typically require Bloomberg
        # Using placeholder values that can be overridden
        return indicators

    def score_sofr_iorb(self, spread_bps: float) -> float:
        """Score SOFR-IORB spread (lower is better)."""
        t = self.THRESHOLDS["sofr_iorb"]
        return score_indicator_simple(
            spread_bps,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_cp_treasury(self, spread_bps: float) -> float:
        """Score CP-Treasury spread (lower is better)."""
        t = self.THRESHOLDS["cp_treasury"]
        return score_indicator_simple(
            spread_bps,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_cross_currency(self, basis_bps: float) -> float:
        """Score cross-currency basis (less negative is better)."""
        t = self.THRESHOLDS["cross_currency"]
        # Invert because less negative is better
        return score_indicator_simple(
            basis_bps,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=False,  # Higher (less negative) is better
        )

    def score_bid_ask(self, bid_ask_32nds: float) -> float:
        """Score Treasury bid-ask spread (lower is better)."""
        t = self.THRESHOLDS["bid_ask"]
        return score_indicator_simple(
            bid_ask_32nds,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def calculate(
        self,
        indicators: Optional[LiquidityIndicators] = None,
    ) -> LiquidityScores:
        """
        Calculate liquidity pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            LiquidityScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = LiquidityScores()
        scored_count = 0

        if indicators.sofr_iorb_spread_bps is not None:
            scores.sofr_iorb = self.score_sofr_iorb(indicators.sofr_iorb_spread_bps)
            scored_count += 1

        if indicators.cp_treasury_spread_bps is not None:
            scores.cp_treasury = self.score_cp_treasury(indicators.cp_treasury_spread_bps)
            scored_count += 1

        if indicators.cross_currency_basis_bps is not None:
            scores.cross_currency = self.score_cross_currency(
                indicators.cross_currency_basis_bps
            )
            scored_count += 1

        if indicators.treasury_bid_ask_32nds is not None:
            scores.bid_ask = self.score_bid_ask(indicators.treasury_bid_ask_32nds)
            scored_count += 1

        # Calculate composite (average of available scores)
        if scored_count > 0:
            total = 0.0
            if indicators.sofr_iorb_spread_bps is not None:
                total += scores.sofr_iorb
            if indicators.cp_treasury_spread_bps is not None:
                total += scores.cp_treasury
            if indicators.cross_currency_basis_bps is not None:
                total += scores.cross_currency
            if indicators.treasury_bid_ask_32nds is not None:
                total += scores.bid_ask
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5  # Default neutral

        return scores

    def get_score(self) -> float:
        """Get composite liquidity score."""
        return self.calculate().composite

"""Positioning pillar scoring.

Question: Is leverage manageable and positioning diverse?

Indicators:
- Basis trade size (estimated from Treasury futures open interest)
- Treasury spec net (percentile)
- SVXY AUM

Basis Trade Estimation Methodology:
-----------------------------------
The Treasury cash-futures basis trade involves hedge funds going long cash
Treasuries and short Treasury futures to capture the spread. We estimate
basis trade size using CFTC Treasury futures data.

Key Fed Research References:
- "Quantifying Treasury Cash-Futures Basis Trades" (Fed, March 2024)
  https://www.federalreserve.gov/econres/notes/feds-notes/quantifying-treasury-cash-futures-basis-trades-20240308.html
  Finding: Basis trade was $260B-$574B in late 2023

- "Recent Developments in Hedge Funds' Treasury Futures and Repo Positions" (Fed, Aug 2023)
  https://www.federalreserve.gov/econres/notes/feds-notes/recent-developments-in-hedge-funds-treasury-futures-and-repo-positions-20230830.html
  Finding: Positions represent a financial stability vulnerability

- "Hedge Funds and the Treasury Cash-Futures Disconnect" (OFR, April 2021)
  https://www.financialresearch.gov/working-papers/files/OFRwp-21-01-hedge-funds-and-the-treasury-cash-futures-disconnect.pdf
  Finding: Basis trade unwind contributed to March 2020 Treasury dysfunction

Proxy Methodology:
- CFTC reports non-commercial (speculator) short positions in Treasury futures
- Leveraged hedge funds typically use ~20x leverage on basis trades
- Open interest increase indicates crowding in the trade
- Fed estimates can validate our thresholds
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ..mac.scorer import score_indicator_simple, score_indicator_range

logger = logging.getLogger(__name__)

# Try to import hedge failure detector (v7 enhancement)
try:
    from .hedge_failure_analysis import HedgeFailureDetector
    _HEDGE_FAILURE_AVAILABLE = True
except ImportError:
    _HEDGE_FAILURE_AVAILABLE = False


@dataclass
class PositioningIndicators:
    """Raw positioning indicator values."""

    basis_trade_size_billions: Optional[float] = None
    treasury_spec_net_percentile: Optional[float] = None
    svxy_aum_millions: Optional[float] = None
    # For dynamic OI-relative thresholds
    total_treasury_oi_billions: Optional[float] = None
    # v7: Hedge failure indicators
    primary_dealer_gross_leverage: Optional[float] = None
    treasury_futures_herfindahl: Optional[float] = None


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
            "breach": 1500,  # > $1B
        },
        # Dynamic OI-relative thresholds (preferred over fixed $B)
        # Adapts automatically as Treasury futures market grows
        "basis_trade_oi_relative": {
            "enabled": True,
            "ample_pct": 8,        # < 8% of total Treasury OI
            "thin_pct": 12,        # 8-12% of OI
            "breach_pct": 18,      # > 18% of OI - crowding
            "min_oi_billions": 100,  # Min OI for valid calculation
        },
    }

    def __init__(self, cftc_client=None, etf_client=None, use_hedge_failure=True):
        """
        Initialize positioning pillar.

        Args:
            cftc_client: CFTCClient instance for COT data
            etf_client: ETFClient instance for ETF data
            use_hedge_failure: Use hedge failure analysis (v7)
        """
        self.cftc = cftc_client
        self.etf = etf_client
        self._hedge_detector = None
        if use_hedge_failure and _HEDGE_FAILURE_AVAILABLE:
            self._hedge_detector = HedgeFailureDetector()

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

        # Estimate basis trade size from CFTC Treasury futures open interest
        # See docstring for Fed research references validating this approach
        if self.cftc:
            try:
                basis_estimate = self.estimate_basis_trade_from_cftc()
                if basis_estimate is not None:
                    indicators.basis_trade_size_billions = basis_estimate
            except Exception:
                pass

        return indicators

    def estimate_basis_trade_from_cftc(self) -> Optional[float]:
        """
        Estimate basis trade size from CFTC Treasury futures data.

        Methodology:
        - Get non-commercial (speculator) net short positions across Treasury futures
        - Large net shorts indicate basis trade activity (short futures, long cash)
        - Scale by typical notional values per contract

        Returns:
            Estimated basis trade size in billions USD, or None if unavailable

        References:
        - Fed (2024): Basis trade was $260B-$574B in late 2023
        - Fed (2023): By end 2024, hedge funds net short >$1T in futures
        """
        if not self.cftc:
            return None

        try:
            # Get positioning data for major Treasury contracts
            total_short_contracts = 0

            for contract in ["2Y", "5Y", "10Y", "30Y"]:
                try:
                    data = self.cftc.get_treasury_positioning(contract)
                    if data is not None and not data.empty:
                        # Get most recent spec_net (negative = net short)
                        latest = data.iloc[-1]
                        spec_net = latest.get("spec_net", 0)
                        if spec_net < 0:  # Net short position
                            total_short_contracts += abs(spec_net)
                except Exception:
                    continue

            if total_short_contracts == 0:
                return None

            # Convert contracts to notional value
            # Average contract size ~$100K face value
            # But basis trade uses leverage, so actual cash is ~$100K/20 = $5K per contract
            # Fed estimates suggest using face value for sizing
            notional_billions = (total_short_contracts * 100000) / 1e9

            return notional_billions

        except Exception:
            return None

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

    def score_basis_trade_oi_relative(
        self,
        basis_trade_billions: float,
        total_oi_billions: float,
    ) -> Optional[float]:
        """
        Score basis trade size relative to total Treasury futures OI.

        This dynamic approach automatically adapts as the market grows,
        avoiding the need to manually recalibrate fixed $B thresholds.

        Args:
            basis_trade_billions: Estimated basis trade size in $B
            total_oi_billions: Total Treasury futures OI in $B

        Returns:
            Score 0-1 (higher concentration = lower score = more risk)
        """
        t = self.THRESHOLDS.get("basis_trade_oi_relative", {})

        # Check if OI-relative scoring is enabled
        if not t.get("enabled", False):
            return None  # Fall back to absolute scoring

        # Validate minimum OI
        min_oi = t.get("min_oi_billions", 100)
        if total_oi_billions < min_oi:
            return None  # Insufficient OI for reliable calculation

        # Calculate basis trade as % of OI
        basis_pct = (basis_trade_billions / total_oi_billions) * 100

        ample = t.get("ample_pct", 8)
        thin = t.get("thin_pct", 12)
        breach = t.get("breach_pct", 18)

        return score_indicator_simple(
            basis_pct,
            ample,
            thin,
            breach,
            lower_is_better=True,
        )

    def calculate(
        self,
        indicators: Optional[PositioningIndicators] = None,
    ) -> PositioningScores:
        """
        Calculate positioning pillar scores.

        v7: Incorporates hedge failure analysis when primary dealer
        leverage or Treasury futures Herfindahl data is available.

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
            # Try OI-relative scoring first (preferred)
            if indicators.total_treasury_oi_billions is not None:
                oi_score = self.score_basis_trade_oi_relative(
                    indicators.basis_trade_size_billions,
                    indicators.total_treasury_oi_billions,
                )
                if oi_score is not None:
                    scores.basis_trade = oi_score
                    scored_count += 1
                else:
                    # Fall back to absolute scoring
                    scores.basis_trade = self.score_basis_trade(
                        indicators.basis_trade_size_billions
                    )
                    scored_count += 1
            else:
                # No OI data, use absolute scoring
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

        # v7: Hedge failure indicators (when available)
        if self._hedge_detector is not None:
            if indicators.primary_dealer_gross_leverage is not None:
                self._hedge_detector.score_primary_dealer_leverage(
                    indicators.primary_dealer_gross_leverage,
                )
                scored_count += 1

            if indicators.treasury_futures_herfindahl is not None:
                self._hedge_detector.score_herfindahl(
                    indicators.treasury_futures_herfindahl,
                )
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
            # v7: Add hedge failure indicator scores
            if (
                self._hedge_detector is not None
                and indicators.primary_dealer_gross_leverage is not None
            ):
                total += self._hedge_detector.score_primary_dealer_leverage(
                    indicators.primary_dealer_gross_leverage,
                )
            if (
                self._hedge_detector is not None
                and indicators.treasury_futures_herfindahl is not None
            ):
                total += self._hedge_detector.score_herfindahl(
                    indicators.treasury_futures_herfindahl,
                )
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5

        return scores

    def get_score(self) -> float:
        """Get composite positioning score."""
        return self.calculate().composite

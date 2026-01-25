"""Policy pillar scoring.

Question: Does the central bank have capacity to respond?

Indicators:
- Fed funds vs neutral rate
- Fed balance sheet / GDP
- Core PCE vs target
"""

from dataclasses import dataclass
from typing import Optional

from ..mac.scorer import score_indicator_simple, score_indicator_range


@dataclass
class PolicyIndicators:
    """Raw policy indicator values."""

    fed_funds_vs_neutral_bps: Optional[float] = None
    fed_balance_sheet_gdp_pct: Optional[float] = None
    core_pce_vs_target_bps: Optional[float] = None


@dataclass
class PolicyScores:
    """Scored policy indicators."""

    fed_funds: float = 0.5
    balance_sheet: float = 0.5
    inflation: float = 0.5
    composite: float = 0.5


class PolicyPillar:
    """Policy pillar calculator."""

    # Thresholds from specification
    THRESHOLDS = {
        "fed_funds_vs_neutral": {
            # Within 100 bps of neutral is ample
            # 100-200 bps away is thin
            # > 200 bps or at ELB is breaching
            "ample": 100,
            "thin": 200,
            "breach": 300,
        },
        "balance_sheet_gdp": {
            # < 25% is ample
            # 25-35% is thin
            # > 35% is breaching
            "ample": 25,
            "thin": 35,
            "breach": 45,
        },
        "core_pce_vs_target": {
            # Within 50 bps of 2% is ample
            # 50-150 bps away is thin
            # > 150 bps away is breaching
            "ample": 50,
            "thin": 150,
            "breach": 250,
        },
    }

    # Default neutral rate assumption
    NEUTRAL_RATE = 2.5

    def __init__(self, fred_client=None, neutral_rate: float = 2.5):
        """
        Initialize policy pillar.

        Args:
            fred_client: FREDClient instance for fetching data
            neutral_rate: Assumed neutral fed funds rate
        """
        self.fred = fred_client
        self.neutral_rate = neutral_rate

    def fetch_indicators(self) -> PolicyIndicators:
        """Fetch current policy indicators from data sources."""
        indicators = PolicyIndicators()

        if self.fred:
            try:
                indicators.fed_funds_vs_neutral_bps = self.fred.get_fed_funds_vs_neutral(
                    self.neutral_rate
                )
            except Exception:
                pass

            try:
                indicators.fed_balance_sheet_gdp_pct = (
                    self.fred.get_fed_balance_sheet_to_gdp()
                )
            except Exception:
                pass

            try:
                indicators.core_pce_vs_target_bps = self.fred.get_core_pce_vs_target()
            except Exception:
                pass

        return indicators

    def score_fed_funds(self, deviation_bps: float) -> float:
        """Score Fed funds deviation from neutral (closer is better)."""
        t = self.THRESHOLDS["fed_funds_vs_neutral"]
        # Use absolute value - both too high and too low are concerning
        abs_deviation = abs(deviation_bps)
        return score_indicator_simple(
            abs_deviation,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_balance_sheet(self, bs_gdp_pct: float) -> float:
        """Score Fed balance sheet as % of GDP (lower is better)."""
        t = self.THRESHOLDS["balance_sheet_gdp"]
        return score_indicator_simple(
            bs_gdp_pct,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_inflation(self, pce_vs_target_bps: float) -> float:
        """Score Core PCE deviation from target (closer is better)."""
        t = self.THRESHOLDS["core_pce_vs_target"]
        # Use absolute value
        abs_deviation = abs(pce_vs_target_bps)
        return score_indicator_simple(
            abs_deviation,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def calculate(
        self,
        indicators: Optional[PolicyIndicators] = None,
    ) -> PolicyScores:
        """
        Calculate policy pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            PolicyScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = PolicyScores()
        scored_count = 0

        if indicators.fed_funds_vs_neutral_bps is not None:
            scores.fed_funds = self.score_fed_funds(indicators.fed_funds_vs_neutral_bps)
            scored_count += 1

        if indicators.fed_balance_sheet_gdp_pct is not None:
            scores.balance_sheet = self.score_balance_sheet(
                indicators.fed_balance_sheet_gdp_pct
            )
            scored_count += 1

        if indicators.core_pce_vs_target_bps is not None:
            scores.inflation = self.score_inflation(indicators.core_pce_vs_target_bps)
            scored_count += 1

        # Calculate composite
        if scored_count > 0:
            total = 0.0
            if indicators.fed_funds_vs_neutral_bps is not None:
                total += scores.fed_funds
            if indicators.fed_balance_sheet_gdp_pct is not None:
                total += scores.balance_sheet
            if indicators.core_pce_vs_target_bps is not None:
                total += scores.inflation
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5

        return scores

    def get_score(self) -> float:
        """Get composite policy score."""
        return self.calculate().composite

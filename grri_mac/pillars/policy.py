"""Policy pillar scoring.

Question: Does the central bank have capacity to respond?

Indicators:
- Policy room (distance from ELB) - how much can the Fed cut?
- Fed balance sheet / GDP
- Core PCE vs target

Note: We use distance from Effective Lower Bound (ELB) rather than deviation
from an estimated "neutral rate" (r*). This is simpler, uses observable data,
and directly measures what matters: the Fed's operational capacity to cut rates.
"""

from dataclasses import dataclass
from typing import Optional

from ..mac.scorer import score_indicator_simple


@dataclass
class PolicyIndicators:
    """Raw policy indicator values."""

    policy_room_bps: Optional[float] = None  # fed_funds * 100
    fed_balance_sheet_gdp_pct: Optional[float] = None
    core_pce_vs_target_bps: Optional[float] = None
    debt_to_gdp_pct: Optional[float] = None  # Federal debt / GDP


@dataclass
class PolicyScores:
    """Scored policy indicators."""

    policy_room: float = 0.5
    balance_sheet: float = 0.5
    inflation: float = 0.5
    fiscal_space: float = 0.5  # Debt/GDP constraint
    composite: float = 0.5


class PolicyPillar:
    """Policy pillar calculator."""

    # Thresholds for policy capacity
    THRESHOLDS = {
        "policy_room": {
            # Distance from ELB (0%) in bps - more room is better
            # > 150 bps = ample room to cut
            # 50-150 bps = limited room
            # < 50 bps = at or near ELB, constrained
            "ample": 150,
            "thin": 50,
            "breach": 25,
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
        "fiscal_space": {
            # Federal debt / GDP - constrains fiscal policy flexibility
            # Based on Reinhart-Rogoff research and IMF sustainability
            # Lower debt = more room for fiscal stimulus if needed
            "ample": 70,    # < 70% - comfortable fiscal space
            "thin": 90,     # 70-90% - elevated but manageable
            "breach": 120,  # > 120% - constrained, limited fiscal room
        },
    }

    def __init__(self, fred_client=None):
        """Initialize policy pillar.

        Args:
            fred_client: FREDClient instance for fetching data
        """
        self.fred = fred_client

    def fetch_indicators(self) -> PolicyIndicators:
        """Fetch current policy indicators from data sources."""
        indicators = PolicyIndicators()

        if self.fred:
            try:
                fed_funds = self.fred.get_fed_funds()
                if fed_funds is not None:
                    indicators.policy_room_bps = fed_funds * 100
            except Exception:
                pass

            try:
                indicators.fed_balance_sheet_gdp_pct = (
                    self.fred.get_fed_balance_sheet_to_gdp()
                )
            except Exception:
                pass

            try:
                indicators.core_pce_vs_target_bps = (
                    self.fred.get_core_pce_vs_target()
                )
            except Exception:
                pass

        return indicators

    def score_policy_room(self, room_bps: float) -> float:
        """Score policy room - more room to cut is better."""
        t = self.THRESHOLDS["policy_room"]
        # Higher is better (more room to cut)
        if room_bps >= t["ample"]:
            return 1.0
        elif room_bps >= t["thin"]:
            # Linear interpolation between thin and ample
            return 0.5 + 0.5 * (room_bps - t["thin"]) / (t["ample"] - t["thin"])
        elif room_bps >= t["breach"]:
            # Linear interpolation between breach and thin
            return 0.5 * (room_bps - t["breach"]) / (t["thin"] - t["breach"])
        else:
            return 0.0

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
        abs_deviation = abs(pce_vs_target_bps)
        return score_indicator_simple(
            abs_deviation,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_fiscal_space(self, debt_gdp_pct: float) -> float:
        """Score fiscal space (Debt/GDP) - lower is better."""
        t = self.THRESHOLDS["fiscal_space"]
        return score_indicator_simple(
            debt_gdp_pct,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def calculate(
        self,
        indicators: Optional[PolicyIndicators] = None,
    ) -> PolicyScores:
        """Calculate policy pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            PolicyScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = PolicyScores()
        scored_count = 0

        if indicators.policy_room_bps is not None:
            scores.policy_room = self.score_policy_room(indicators.policy_room_bps)
            scored_count += 1

        if indicators.fed_balance_sheet_gdp_pct is not None:
            scores.balance_sheet = self.score_balance_sheet(
                indicators.fed_balance_sheet_gdp_pct
            )
            scored_count += 1

        if indicators.core_pce_vs_target_bps is not None:
            scores.inflation = self.score_inflation(
                indicators.core_pce_vs_target_bps
            )
            scored_count += 1

        if indicators.debt_to_gdp_pct is not None:
            scores.fiscal_space = self.score_fiscal_space(
                indicators.debt_to_gdp_pct
            )
            scored_count += 1

        # Calculate composite
        if scored_count > 0:
            total = 0.0
            if indicators.policy_room_bps is not None:
                total += scores.policy_room
            if indicators.fed_balance_sheet_gdp_pct is not None:
                total += scores.balance_sheet
            if indicators.core_pce_vs_target_bps is not None:
                total += scores.inflation
            if indicators.debt_to_gdp_pct is not None:
                total += scores.fiscal_space
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5

        return scores

    def get_score(self) -> float:
        """Get composite policy score."""
        return self.calculate().composite

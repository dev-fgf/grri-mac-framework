"""China Leverage Activation Score.

Tracks five vectors of China economic/geopolitical leverage:
1. Treasury holdings
2. Rare earth policy
3. Tariff levels
4. Taiwan tension
5. CIPS (Cross-border Interbank Payment System) growth
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ActivationLevel(Enum):
    """Activation level for China leverage vectors."""

    LATENT = 0.0
    ELEVATED = 0.5
    ACTIVATED = 1.0


@dataclass
class ChinaVectorIndicators:
    """Raw China leverage vector indicators."""

    treasury_holdings_change_billions: Optional[float] = None  # Quarterly change
    rare_earth_policy: Optional[ActivationLevel] = None
    avg_tariff_pct: Optional[float] = None
    taiwan_tension: Optional[ActivationLevel] = None
    cips_growth_yoy_pct: Optional[float] = None


@dataclass
class ChinaVectorScores:
    """Activation scores for each China vector."""

    treasury: float = 0.0
    rare_earth: float = 0.0
    tariff: float = 0.0
    taiwan: float = 0.0
    cips: float = 0.0
    composite: float = 0.0


class ChinaActivationScore:
    """Calculator for China leverage activation score."""

    # Thresholds from specification
    THRESHOLDS = {
        "treasury": {
            "latent": 0,      # Stable holdings
            "elevated": 0,    # Flat
            "activated": -50,  # Declining > $50B/qtr (negative = selling)
        },
        "tariff": {
            "latent": 10,     # < 10%
            "elevated": 25,   # 10-25%
            "activated": 25,  # > 25%
        },
        "cips": {
            "latent": 20,     # < 20% YoY
            "elevated": 50,   # 20-50% YoY
            "activated": 50,  # > 50% YoY
        },
    }

    def __init__(self):
        """Initialize China activation calculator."""

    def score_treasury(self, change_billions: float) -> float:
        """
        Score Treasury holdings change.

        Args:
            change_billions: Quarterly change in Treasury holdings (negative = selling)

        Returns:
            Activation score 0-1
        """
        t = self.THRESHOLDS["treasury"]

        if change_billions >= 0:
            # Stable or increasing - latent
            return 0.0
        elif change_billions >= t["activated"]:
            # Mild selling - interpolate between latent and activated
            return 0.5 * (-change_billions / -t["activated"])
        else:
            # Heavy selling - activated
            return 1.0

    def score_rare_earth(self, policy: ActivationLevel) -> float:
        """Score rare earth policy level."""
        return policy.value

    def score_tariff(self, tariff_pct: float) -> float:
        """
        Score average tariff level.

        Args:
            tariff_pct: Average tariff rate in percent

        Returns:
            Activation score 0-1
        """
        t = self.THRESHOLDS["tariff"]

        if tariff_pct < t["latent"]:
            return 0.0
        elif tariff_pct < t["elevated"]:
            return 0.5 * (tariff_pct - t["latent"]) / (t["elevated"] - t["latent"])
        elif tariff_pct < t["activated"]:
            return 0.5 + 0.5 * (tariff_pct - t["elevated"]) / (t["activated"] - t["elevated"])
        else:
            return 1.0

    def score_taiwan(self, tension: ActivationLevel) -> float:
        """Score Taiwan tension level."""
        return tension.value

    def score_cips(self, growth_yoy_pct: float) -> float:
        """
        Score CIPS growth rate.

        Args:
            growth_yoy_pct: Year-over-year CIPS growth in percent

        Returns:
            Activation score 0-1
        """
        t = self.THRESHOLDS["cips"]

        if growth_yoy_pct < t["latent"]:
            return 0.0
        elif growth_yoy_pct < t["elevated"]:
            return 0.5 * (growth_yoy_pct - t["latent"]) / (t["elevated"] - t["latent"])
        else:
            return min(
                1.0,
                0.5 + 0.5 * (growth_yoy_pct - t["elevated"])
                / (t["activated"] - t["elevated"])
            )

    def calculate(
        self,
        indicators: Optional[ChinaVectorIndicators] = None,
    ) -> ChinaVectorScores:
        """
        Calculate China activation scores.

        Args:
            indicators: China vector indicators

        Returns:
            ChinaVectorScores with individual and composite scores
        """
        if indicators is None:
            indicators = ChinaVectorIndicators()

        scores = ChinaVectorScores()
        scored_count = 0
        total = 0.0

        if indicators.treasury_holdings_change_billions is not None:
            scores.treasury = self.score_treasury(
                indicators.treasury_holdings_change_billions
            )
            total += scores.treasury
            scored_count += 1

        if indicators.rare_earth_policy is not None:
            scores.rare_earth = self.score_rare_earth(indicators.rare_earth_policy)
            total += scores.rare_earth
            scored_count += 1

        if indicators.avg_tariff_pct is not None:
            scores.tariff = self.score_tariff(indicators.avg_tariff_pct)
            total += scores.tariff
            scored_count += 1

        if indicators.taiwan_tension is not None:
            scores.taiwan = self.score_taiwan(indicators.taiwan_tension)
            total += scores.taiwan
            scored_count += 1

        if indicators.cips_growth_yoy_pct is not None:
            scores.cips = self.score_cips(indicators.cips_growth_yoy_pct)
            total += scores.cips
            scored_count += 1

        # Calculate composite as average
        if scored_count > 0:
            scores.composite = total / scored_count
        else:
            scores.composite = 0.0

        return scores

    def get_activation(self, indicators: ChinaVectorIndicators) -> float:
        """Get composite activation score."""
        return self.calculate(indicators).composite


def get_activation_interpretation(activation: float) -> str:
    """
    Get human-readable interpretation of activation score.

    Args:
        activation: Activation score (0-1)

    Returns:
        Interpretation string
    """
    if activation < 0.2:
        return "LATENT - China leverage vectors dormant"
    elif activation < 0.4:
        return "LOW - Minor activation, monitor"
    elif activation < 0.6:
        return "MODERATE - Notable activation, increased risk"
    elif activation < 0.8:
        return "ELEVATED - Significant leverage deployment"
    else:
        return "HIGH - Full leverage activation, maximum risk"

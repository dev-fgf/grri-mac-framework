"""MAC composite calculation."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class MACResult:
    """Result of MAC calculation."""

    mac_score: float
    pillar_scores: dict[str, float]
    breach_flags: list[str]
    adjusted_score: Optional[float] = None  # After China adjustment
    multiplier: Optional[float] = None


DEFAULT_WEIGHTS = {
    "liquidity": 0.2,
    "valuation": 0.2,
    "positioning": 0.2,
    "volatility": 0.2,
    "policy": 0.2,
}


def calculate_mac(
    pillars: dict[str, float],
    weights: Optional[dict[str, float]] = None,
    breach_threshold: float = 0.2,
) -> MACResult:
    """
    Calculate MAC composite score from pillar scores.

    Args:
        pillars: Dict mapping pillar names to scores (0-1)
        weights: Optional custom weights (must sum to 1.0)
        breach_threshold: Threshold below which a pillar is flagged as breaching

    Returns:
        MACResult with composite score, individual scores, and breach flags
    """
    if weights is None:
        weights = {p: 1.0 / len(pillars) for p in pillars}

    # Validate weights sum to 1
    weight_sum = sum(weights.get(p, 0) for p in pillars)
    if abs(weight_sum - 1.0) > 0.01:
        # Normalize weights
        weights = {p: weights.get(p, 0) / weight_sum for p in pillars}

    # Calculate weighted average
    mac_score = sum(pillars[p] * weights.get(p, 0) for p in pillars)

    # Identify breach flags
    breach_flags = [p for p, score in pillars.items() if score < breach_threshold]

    return MACResult(
        mac_score=mac_score,
        pillar_scores=pillars.copy(),
        breach_flags=breach_flags,
    )


def get_mac_interpretation(mac_score: float) -> str:
    """
    Get human-readable interpretation of MAC score.

    Args:
        mac_score: MAC composite score (0-1)

    Returns:
        Interpretation string
    """
    if mac_score >= 0.8:
        return "AMPLE - Markets have substantial buffer capacity"
    elif mac_score >= 0.6:
        return "COMFORTABLE - Markets can absorb moderate shocks"
    elif mac_score >= 0.4:
        return "THIN - Limited buffer, elevated transmission risk"
    elif mac_score >= 0.2:
        return "STRETCHED - High transmission risk, monitor closely"
    else:
        return "REGIME BREAK - Buffers exhausted, non-linear dynamics likely"


def get_pillar_status(score: float) -> str:
    """
    Get status label for a pillar score.

    Args:
        score: Pillar score (0-1)

    Returns:
        Status string
    """
    if score >= 0.8:
        return "AMPLE"
    elif score >= 0.5:
        return "THIN"
    elif score >= 0.2:
        return "STRETCHED"
    else:
        return "BREACHING"

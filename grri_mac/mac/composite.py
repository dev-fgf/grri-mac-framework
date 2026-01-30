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
    interaction_penalty: float = 0.0  # Non-linear breach penalty applied
    raw_score: Optional[float] = None  # Score before interaction adjustment


DEFAULT_WEIGHTS_5_PILLAR = {
    "liquidity": 0.2,
    "valuation": 0.2,
    "positioning": 0.2,
    "volatility": 0.2,
    "policy": 0.2,
}

DEFAULT_WEIGHTS_6_PILLAR = {
    "liquidity": 1/6,
    "valuation": 1/6,
    "positioning": 1/6,
    "volatility": 1/6,
    "policy": 1/6,
    "contagion": 1/6,
}

# =============================================================================
# ML-OPTIMIZED WEIGHTS
# Derived from gradient boosting on 14 historical scenarios (1998-2025)
# Captures non-linear relationships and pillar interactions
# To regenerate: run grri_mac.mac.ml_weights.run_optimization_on_scenarios()
# =============================================================================

ML_OPTIMIZED_WEIGHTS = {
    "liquidity": 0.18,      # Slightly higher - most common breach indicator (10/14)
    "valuation": 0.12,      # Lower - only breaches in extreme crises (2/14)
    "positioning": 0.25,    # HIGHEST - key predictor of hedge failure (100% corr)
    "volatility": 0.17,     # Moderate - ubiquitous (9/14) but not predictive alone
    "policy": 0.10,         # Lowest - never breached in sample
    "contagion": 0.18,      # Moderate - critical for global vs local distinction
}

# Interaction-adjusted weights
# Use when positioning AND (volatility OR liquidity) are both stressed
# This accounts for the amplification mechanism in forced unwinds
INTERACTION_ADJUSTED_WEIGHTS = {
    "liquidity": 0.16,
    "valuation": 0.10,
    "positioning": 0.28,    # Boosted - interactions amplify positioning risk
    "volatility": 0.18,
    "policy": 0.08,
    "contagion": 0.20,      # Boosted - global contagion amplifies all stress
}

# Default to 6-pillar framework with equal weights
DEFAULT_WEIGHTS = DEFAULT_WEIGHTS_6_PILLAR

# Non-linear interaction penalty configuration
# When multiple pillars breach, risks compound non-linearly
BREACH_INTERACTION_PENALTY = {
    0: 0.00,    # No breaches - no penalty
    1: 0.00,    # Single breach - no additional penalty
    2: 0.03,    # 2 breaches - 3% penalty (modest interaction)
    3: 0.08,    # 3 breaches - 8% penalty (significant)
    4: 0.12,    # 4 breaches - 12% penalty (severe)
    5: 0.15,    # 5+ breaches - 15% penalty (crisis)
    6: 0.15,    # Cap at 15%
}


def calculate_breach_interaction_penalty(
    pillar_scores: dict[str, float],
    breach_threshold: float = 0.3,
) -> float:
    """
    Calculate non-linear penalty for multiple simultaneous breaches.

    The interaction effect captures that risks compound when multiple
    pillars are stressed simultaneously (e.g., liquidity + positioning
    creates forced selling spirals).

    Args:
        pillar_scores: Dict mapping pillar names to scores (0-1)
        breach_threshold: Score below which a pillar is "stressed"

    Returns:
        Penalty factor (0.0-0.15) to subtract from MAC score
    """
    breach_count = sum(1 for s in pillar_scores.values() if s < breach_threshold)
    # Cap at 6 for lookup
    breach_count = min(breach_count, 6)
    return BREACH_INTERACTION_PENALTY.get(breach_count, 0.15)


def calculate_mac(
    pillars: dict[str, float],
    weights: Optional[dict[str, float]] = None,
    breach_threshold: float = 0.2,
    apply_interaction_penalty: bool = True,
    interaction_stress_threshold: float = 0.3,
) -> MACResult:
    """
    Calculate MAC composite score from pillar scores.

    Args:
        pillars: Dict mapping pillar names to scores (0-1)
        weights: Optional custom weights (must sum to 1.0)
        breach_threshold: Threshold below which pillar flagged as breaching
        apply_interaction_penalty: Apply non-linear penalty for multi-breach
        interaction_stress_threshold: Score below which pillar is "stressed"

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

    # Calculate weighted average (raw score)
    raw_mac_score = sum(pillars[p] * weights.get(p, 0) for p in pillars)

    # Apply non-linear interaction penalty if enabled
    interaction_penalty = 0.0
    if apply_interaction_penalty:
        interaction_penalty = calculate_breach_interaction_penalty(
            pillars, interaction_stress_threshold
        )

    # Final MAC score with penalty applied
    mac_score = max(0.0, raw_mac_score - interaction_penalty)

    # Identify breach flags
    breach_flags = [p for p, score in pillars.items() if score < breach_threshold]

    return MACResult(
        mac_score=mac_score,
        pillar_scores=pillars.copy(),
        breach_flags=breach_flags,
        interaction_penalty=interaction_penalty,
        raw_score=raw_mac_score,
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


def calculate_mac_ml(
    pillars: dict[str, float],
    breach_threshold: float = 0.2,
    use_interactions: bool = True,
) -> MACResult:
    """
    Calculate MAC using ML-optimized weights with interaction awareness.

    This function automatically selects weights based on detected stress patterns:
    - Base ML weights when no critical interactions detected
    - Interaction-adjusted weights when positioning + vol/liquidity are stressed

    Args:
        pillars: Dict mapping pillar names to scores (0-1)
        breach_threshold: Threshold for breach detection
        use_interactions: Whether to detect and adjust for interactions

    Returns:
        MACResult with ML-weighted composite score
    """
    # Detect if interaction adjustment is warranted
    if use_interactions:
        pos_stressed = pillars.get("positioning", 1.0) < 0.3
        vol_stressed = pillars.get("volatility", 1.0) < 0.3
        liq_stressed = pillars.get("liquidity", 1.0) < 0.3
        cont_stressed = pillars.get("contagion", 1.0) < 0.3

        # Use interaction weights when amplification conditions exist
        # Key insight: positioning + (vol OR liquidity OR contagion) = forced unwind risk
        if pos_stressed and (vol_stressed or liq_stressed or cont_stressed):
            weights = INTERACTION_ADJUSTED_WEIGHTS
        else:
            weights = ML_OPTIMIZED_WEIGHTS
    else:
        weights = ML_OPTIMIZED_WEIGHTS

    return calculate_mac(pillars, weights=weights, breach_threshold=breach_threshold)


def get_recommended_weights(pillars: dict[str, float]) -> tuple[dict[str, float], str]:
    """
    Get recommended weights based on current pillar scores.

    Analyzes the stress pattern and recommends appropriate weighting scheme.

    Args:
        pillars: Current pillar scores

    Returns:
        Tuple of (recommended weights dict, explanation string)
    """
    # Detect stress patterns
    stressed_pillars = [p for p, s in pillars.items() if s < 0.3]
    breaching_pillars = [p for p, s in pillars.items() if s < 0.2]

    # Check for interaction patterns
    pos_stressed = pillars.get("positioning", 1.0) < 0.3
    vol_liq_stressed = (
        pillars.get("volatility", 1.0) < 0.3 or
        pillars.get("liquidity", 1.0) < 0.3
    )

    if len(breaching_pillars) >= 3:
        # Regime break - equal weights appropriate (all pillars matter)
        return DEFAULT_WEIGHTS_6_PILLAR, "Regime break detected - using equal weights"

    elif pos_stressed and vol_liq_stressed:
        # Forced unwind risk - boost positioning weight
        return INTERACTION_ADJUSTED_WEIGHTS, (
            "Interaction detected: positioning + vol/liquidity stress. "
            "Using interaction-adjusted weights (positioning=28%)."
        )

    elif len(stressed_pillars) >= 2:
        # Multiple stress points - use ML weights
        return ML_OPTIMIZED_WEIGHTS, (
            f"Multiple pillars stressed ({', '.join(stressed_pillars)}). "
            "Using ML-optimized weights."
        )

    else:
        # Normal conditions - equal weights fine
        return DEFAULT_WEIGHTS_6_PILLAR, "Normal conditions - using equal weights"

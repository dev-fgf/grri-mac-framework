"""GRRI (Global Risk and Resilience Index) modifier calculation.

GRRI measures country-level resilience across four pillars:
- Political: Rule of law, governance quality, institutional strength
- Economic: GDP diversity, CB independence, fiscal space
- Social: HDI, inequality, social cohesion
- Environmental: Climate risk exposure, green transition progress

The GRRI modifier transforms resilience scores into transmission multipliers.
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class GRRIPillars:
    """GRRI pillar scores for a country."""

    political: float = 0.5
    economic: float = 0.5
    social: float = 0.5
    environmental: float = 0.5


@dataclass
class GRRIResult:
    """Result of GRRI calculation."""

    resilience: float
    modifier: float
    pillar_scores: GRRIPillars
    interpretation: str


def grri_to_modifier(
    resilience: float,
    steepness: float = 4.0,
    midpoint: float = 0.5,
) -> float:
    """
    Convert GRRI resilience score to transmission modifier.

    Uses logistic transformation:
    modifier = 2 / (1 + exp(steepness × (resilience - midpoint)))

    Properties:
    - resilience > 0.5 → modifier < 1 (compressed transmission)
    - resilience = 0.5 → modifier = 1 (neutral)
    - resilience < 0.5 → modifier > 1 (amplified transmission)

    Args:
        resilience: GRRI resilience score (0-1)
        steepness: Controls how quickly modifier changes (default 4.0)
        midpoint: Resilience level at which modifier = 1 (default 0.5)

    Returns:
        Transmission modifier

    Examples:
        - resilience 0.8 → ~0.4x (strong compression)
        - resilience 0.6 → ~0.6x (moderate compression)
        - resilience 0.5 → 1.0x (neutral)
        - resilience 0.4 → ~1.5x (moderate amplification)
        - resilience 0.2 → ~1.9x (strong amplification)
    """
    return 2 / (1 + math.exp(steepness * (resilience - midpoint)))


def calculate_grri(
    pillars: Optional[GRRIPillars] = None,
    weights: Optional[dict[str, float]] = None,
) -> GRRIResult:
    """
    Calculate GRRI score and modifier from pillar scores.

    Args:
        pillars: GRRIPillars with individual pillar scores
        weights: Optional custom weights (must sum to 1.0)

    Returns:
        GRRIResult with resilience score and modifier
    """
    if pillars is None:
        pillars = GRRIPillars()

    if weights is None:
        weights = {
            "political": 0.25,
            "economic": 0.25,
            "social": 0.25,
            "environmental": 0.25,
        }

    # Calculate weighted resilience score
    resilience = (
        pillars.political * weights.get("political", 0.25)
        + pillars.economic * weights.get("economic", 0.25)
        + pillars.social * weights.get("social", 0.25)
        + pillars.environmental * weights.get("environmental", 0.25)
    )

    # Calculate modifier
    modifier = grri_to_modifier(resilience)

    # Generate interpretation
    if modifier < 0.7:
        interpretation = f"HIGH RESILIENCE ({modifier:.2f}x): Strong shock absorption capacity"
    elif modifier < 1.0:
        interpretation = f"MODERATE RESILIENCE ({modifier:.2f}x): Partial shock compression"
    elif modifier < 1.3:
        interpretation = f"NEUTRAL ({modifier:.2f}x): Near-normal transmission"
    elif modifier < 1.7:
        interpretation = f"LOW RESILIENCE ({modifier:.2f}x): Shock amplification"
    else:
        interpretation = f"FRAGILE ({modifier:.2f}x): Significant shock amplification"

    return GRRIResult(
        resilience=resilience,
        modifier=modifier,
        pillar_scores=pillars,
        interpretation=interpretation,
    )


def calculate_full_impact(
    shock_magnitude: float,
    mac_multiplier: float,
    grri_modifier: float,
) -> float:
    """
    Calculate full market impact using the core equation.

    Market Impact = Shock × GRRI Modifier × MAC Multiplier

    Args:
        shock_magnitude: Initial shock size
        mac_multiplier: MAC transmission multiplier
        grri_modifier: GRRI country modifier

    Returns:
        Expected market impact
    """
    return shock_magnitude * grri_modifier * mac_multiplier


# Pre-defined GRRI profiles for major countries/regions
COUNTRY_PROFILES = {
    "US": GRRIPillars(political=0.75, economic=0.80, social=0.65, environmental=0.55),
    "EU": GRRIPillars(political=0.80, economic=0.70, social=0.75, environmental=0.70),
    "UK": GRRIPillars(political=0.80, economic=0.70, social=0.70, environmental=0.60),
    "Japan": GRRIPillars(political=0.75, economic=0.65, social=0.80, environmental=0.55),
    "China": GRRIPillars(political=0.55, economic=0.70, social=0.60, environmental=0.45),
    "EM_Avg": GRRIPillars(political=0.45, economic=0.45, social=0.50, environmental=0.40),
}


def get_country_modifier(country_code: str) -> float:
    """
    Get GRRI modifier for a predefined country.

    Args:
        country_code: Country code (US, EU, UK, Japan, China, EM_Avg)

    Returns:
        GRRI modifier for the country
    """
    pillars = COUNTRY_PROFILES.get(country_code)
    if pillars is None:
        raise ValueError(f"Unknown country code: {country_code}")

    result = calculate_grri(pillars)
    return result.modifier

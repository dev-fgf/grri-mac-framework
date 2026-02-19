"""MAC to transmission multiplier conversion."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class MultiplierResult:
    """Result of multiplier calculation."""

    multiplier: Optional[float]
    mac_score: float
    is_regime_break: bool
    interpretation: str


def mac_to_multiplier(
    mac: float,
    alpha: float = 2.0,
    beta: float = 1.5,
    regime_break_threshold: float = 0.2,
) -> MultiplierResult:
    """
    Convert MAC score to transmission multiplier.

    Formula: 1 + alpha * (1 - mac)^beta

    The multiplier indicates how much a shock is amplified:
    - Multiplier 1.0: Shock passes through 1:1
    - Multiplier 2.0: Shock is doubled
    - Multiplier None: Regime break, point estimates unreliable

    Args:
        mac: MAC composite score (0-1)
        alpha: Scaling parameter (default 2.0)
        beta: Curvature parameter (default 1.5)
        regime_break_threshold: MAC below this triggers regime break

    Returns:
        MultiplierResult with multiplier and interpretation

    Examples:
        - MAC 1.0 -> 1.0x (ample)
        - MAC 0.5 -> 1.6x (thin)
        - MAC 0.3 -> 2.3x (stretched)
        - MAC < 0.2 -> None (regime break)
    """
    is_regime_break = mac < regime_break_threshold

    if is_regime_break:
        return MultiplierResult(
            multiplier=None,
            mac_score=mac,
            is_regime_break=True,
            interpretation="REGIME BREAK: Point estimates unreliable. "
            "Expect non-linear dynamics and potential market dysfunction.",
        )

    multiplier = 1 + alpha * ((1 - mac) ** beta)

    # Generate interpretation
    if multiplier <= 1.2:
        interpretation = f"LOW TRANSMISSION ({multiplier:.2f}x): Shocks absorbed effectively"
    elif multiplier <= 1.6:
        interpretation = f"MODERATE TRANSMISSION ({multiplier:.2f}x): Some amplification expected"
    elif multiplier <= 2.0:
        interpretation = f"ELEVATED TRANSMISSION ({
            multiplier: .2f} x): Significant shock amplification"
    else:
        interpretation = f"HIGH TRANSMISSION ({multiplier:.2f}x): Severe amplification, use caution"

    return MultiplierResult(
        multiplier=multiplier,
        mac_score=mac,
        is_regime_break=False,
        interpretation=interpretation,
    )


def calculate_market_impact(
    shock_magnitude: float,
    mac_multiplier: float,
    grri_modifier: float = 1.0,
) -> float:
    """
    Calculate expected market impact using the core equation.

    Market Impact = Shock x GRRI Modifier x MAC Multiplier

    Args:
        shock_magnitude: Size of the initial shock (in same units as desired output)
        mac_multiplier: Transmission multiplier from mac_to_multiplier()
        grri_modifier: Country resilience modifier from GRRI framework

    Returns:
        Expected market impact
    """
    return shock_magnitude * grri_modifier * mac_multiplier


def multiplier_sensitivity(
    mac: float,
    shock_range: tuple[float, float] = (-5.0, 5.0),
    steps: int = 10,
    alpha: float = 2.0,
    beta: float = 1.5,
) -> list[tuple[float, float]]:
    """
    Calculate impact sensitivity across a range of shock sizes.

    Args:
        mac: Current MAC score
        shock_range: (min, max) shock sizes to test
        steps: Number of steps between min and max
        alpha: Multiplier alpha parameter
        beta: Multiplier beta parameter

    Returns:
        List of (shock, impact) tuples
    """
    result = mac_to_multiplier(mac, alpha, beta)

    if result.is_regime_break or result.multiplier is None:
        return []

    shock_min, shock_max = shock_range
    step_size = (shock_max - shock_min) / steps
    multiplier = result.multiplier

    return [
        (shock_min + i * step_size, (shock_min + i * step_size) * multiplier)
        for i in range(steps + 1)
    ]

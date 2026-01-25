"""MAC adjustment for China leverage activation."""

from typing import Optional
from ..mac.composite import MACResult


def adjust_mac_for_china(
    raw_mac: float,
    china_activation: float,
    adjustment_factor: float = 0.3,
) -> float:
    """
    Adjust MAC score for China leverage activation.

    China activation pre-depletes market absorption capacity.

    Formula: MAC_adjusted = MAC_raw × (1 - adjustment_factor × activation)

    Args:
        raw_mac: Raw MAC score (0-1)
        china_activation: China activation score (0-1)
        adjustment_factor: Maximum adjustment at full activation (default 0.3 = 30%)

    Returns:
        Adjusted MAC score

    Examples:
        - Activation 0.0: No adjustment
        - Activation 0.5: MAC reduced by 15%
        - Activation 0.7: MAC reduced by 21%
        - Activation 1.0: MAC reduced by 30%
    """
    adjustment = 1 - adjustment_factor * china_activation
    return raw_mac * adjustment


def adjust_mac_result_for_china(
    mac_result: MACResult,
    china_activation: float,
    adjustment_factor: float = 0.3,
) -> MACResult:
    """
    Adjust a MACResult object for China leverage.

    Args:
        mac_result: Original MACResult
        china_activation: China activation score (0-1)
        adjustment_factor: Maximum adjustment at full activation

    Returns:
        Updated MACResult with adjusted_score populated
    """
    adjusted = adjust_mac_for_china(
        mac_result.mac_score,
        china_activation,
        adjustment_factor,
    )

    # Check if adjustment creates new breach flags
    if adjusted < 0.2 and mac_result.mac_score >= 0.2:
        # China adjustment pushed MAC into regime break territory
        mac_result.breach_flags = list(mac_result.breach_flags) + ["china_adjustment"]

    mac_result.adjusted_score = adjusted
    return mac_result


def get_china_impact_summary(
    raw_mac: float,
    adjusted_mac: float,
    china_activation: float,
) -> str:
    """
    Generate summary of China impact on MAC.

    Args:
        raw_mac: Raw MAC score
        adjusted_mac: Adjusted MAC score
        china_activation: China activation score

    Returns:
        Summary string
    """
    reduction_pct = (1 - adjusted_mac / raw_mac) * 100 if raw_mac > 0 else 0

    summary = []
    summary.append(f"China Activation: {china_activation:.1%}")
    summary.append(f"Raw MAC: {raw_mac:.2f}")
    summary.append(f"Adjusted MAC: {adjusted_mac:.2f}")
    summary.append(f"Reduction: {reduction_pct:.1f}%")

    if adjusted_mac < 0.2 and raw_mac >= 0.2:
        summary.append("WARNING: China adjustment triggered regime break threshold")

    return " | ".join(summary)

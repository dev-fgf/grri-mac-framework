"""Pillar scoring logic for MAC framework."""

from typing import Optional, Union
from dataclasses import dataclass


@dataclass
class IndicatorThresholds:
    """Thresholds for scoring an indicator."""

    ample_low: Optional[float] = None
    ample_high: Optional[float] = None
    thin_low: Optional[float] = None
    thin_high: Optional[float] = None
    breach_low: Optional[float] = None
    breach_high: Optional[float] = None
    invert: bool = False  # If True, lower values are better


def score_indicator(
    value: float,
    thresholds: Union[IndicatorThresholds, dict],
) -> float:
    """
    Score an indicator from 0 to 1.

    Returns:
        - 1.0 = ample (full buffer)
        - 0.5 = thin (buffer depleted)
        - 0.0 = breaching (buffer gone)

    Interpolates linearly between thresholds.

    Args:
        value: Current indicator value
        thresholds: IndicatorThresholds or dict with threshold values

    Returns:
        Score between 0 and 1
    """
    if isinstance(thresholds, dict):
        thresholds = IndicatorThresholds(**thresholds)

    # Handle inverted indicators (where lower is better)
    if thresholds.invert:
        value = -value
        if thresholds.ample_low is not None:
            thresholds.ample_low = -thresholds.ample_low
        if thresholds.ample_high is not None:
            thresholds.ample_high = -thresholds.ample_high
        if thresholds.thin_low is not None:
            thresholds.thin_low = -thresholds.thin_low
        if thresholds.thin_high is not None:
            thresholds.thin_high = -thresholds.thin_high
        if thresholds.breach_low is not None:
            thresholds.breach_low = -thresholds.breach_low
        if thresholds.breach_high is not None:
            thresholds.breach_high = -thresholds.breach_high

    # Case 1: Single-sided thresholds (value should be above/below a threshold)
    if thresholds.ample_high is None and thresholds.ample_low is not None:
        # Higher is better (e.g., term premium > 100 bps)
        ample = thresholds.ample_low
        thin = thresholds.thin_low if thresholds.thin_low is not None else ample * 0.5
        breach = thresholds.breach_low if thresholds.breach_low is not None else 0

        if value >= ample:
            return 1.0
        elif value >= thin:
            return 0.5 + 0.5 * (value - thin) / (ample - thin)
        elif value >= breach:
            return 0.5 * (value - breach) / (thin - breach)
        else:
            return 0.0

    elif thresholds.ample_low is None and thresholds.ample_high is not None:
        # Lower is better (e.g., spread < 5 bps)
        ample = thresholds.ample_high
        thin = thresholds.thin_high if thresholds.thin_high is not None else ample * 2
        breach = thresholds.breach_high if thresholds.breach_high is not None else thin * 2

        if value <= ample:
            return 1.0
        elif value <= thin:
            return 0.5 + 0.5 * (thin - value) / (thin - ample)
        elif value <= breach:
            return 0.5 * (breach - value) / (breach - thin)
        else:
            return 0.0

    # Case 2: Two-sided thresholds (value should be in a range)
    elif thresholds.ample_low is not None and thresholds.ample_high is not None:
        (thresholds.ample_low + thresholds.ample_high) / 2
        (thresholds.ample_high - thresholds.ample_low) / 2

        thin_low = thresholds.thin_low if thresholds.thin_low else thresholds.ample_low * 0.5
        thin_high = thresholds.thin_high if thresholds.thin_high else thresholds.ample_high * 1.5
        breach_low = thresholds.breach_low if thresholds.breach_low else thin_low * 0.5
        breach_high = thresholds.breach_high if thresholds.breach_high else thin_high * 1.5

        # In ample range
        if thresholds.ample_low <= value <= thresholds.ample_high:
            return 1.0

        # Below ample range
        if value < thresholds.ample_low:
            if value >= thin_low:
                return 0.5 + 0.5 * (value - thin_low) / (thresholds.ample_low - thin_low)
            elif value >= breach_low:
                return 0.5 * (value - breach_low) / (thin_low - breach_low)
            else:
                return 0.0

        # Above ample range
        if value > thresholds.ample_high:
            if value <= thin_high:
                return 0.5 + 0.5 * (thin_high - value) / (thin_high - thresholds.ample_high)
            elif value <= breach_high:
                return 0.5 * (breach_high - value) / (breach_high - thin_high)
            else:
                return 0.0

    return 0.5  # Default fallback


def score_pillar(indicators: dict[str, float]) -> tuple[float, dict[str, float]]:
    """
    Calculate pillar score as average of indicator scores.

    Args:
        indicators: Dict mapping indicator names to their scores (0-1)

    Returns:
        Tuple of (composite score, individual scores dict)
    """
    if not indicators:
        return 0.5, {}

    scores = {name: score for name, score in indicators.items()}
    composite = sum(scores.values()) / len(scores)

    return composite, scores


def score_indicator_simple(
    value: float,
    ample_threshold: float,
    thin_threshold: float,
    breach_threshold: float,
    lower_is_better: bool = False,
) -> float:
    """
    Simplified indicator scoring for common cases.

    Args:
        value: Current indicator value
        ample_threshold: Threshold for ample (score 1.0)
        thin_threshold: Threshold for thin (score 0.5)
        breach_threshold: Threshold for breach (score 0.0)
        lower_is_better: If True, values below ample are good

    Returns:
        Score between 0 and 1
    """
    if lower_is_better:
        if value <= ample_threshold:
            return 1.0
        elif value <= thin_threshold:
            return 0.5 + 0.5 * (thin_threshold - value) / (thin_threshold - ample_threshold)
        elif value <= breach_threshold:
            return 0.5 * (breach_threshold - value) / (breach_threshold - thin_threshold)
        else:
            return 0.0
    else:
        if value >= ample_threshold:
            return 1.0
        elif value >= thin_threshold:
            return 0.5 + 0.5 * (value - thin_threshold) / (ample_threshold - thin_threshold)
        elif value >= breach_threshold:
            return 0.5 * (value - breach_threshold) / (thin_threshold - breach_threshold)
        else:
            return 0.0


def score_indicator_range(
    value: float,
    ample_range: tuple[float, float],
    thin_range: tuple[float, float],
    breach_range: tuple[float, float],
) -> float:
    """
    Score indicator that should be within a range.

    Args:
        value: Current indicator value
        ample_range: (low, high) for ample score
        thin_range: (low, high) for thin score
        breach_range: (low, high) for breach score

    Returns:
        Score between 0 and 1
    """
    ample_low, ample_high = ample_range
    thin_low, thin_high = thin_range
    breach_low, breach_high = breach_range

    # In ample range
    if ample_low <= value <= ample_high:
        return 1.0

    # Check which side we're on
    if value < ample_low:
        if value >= thin_low:
            return 0.5 + 0.5 * (value - thin_low) / (ample_low - thin_low)
        elif value >= breach_low:
            return 0.5 * (value - breach_low) / (thin_low - breach_low)
        else:
            return 0.0
    else:  # value > ample_high
        if value <= thin_high:
            return 0.5 + 0.5 * (thin_high - value) / (thin_high - ample_high)
        elif value <= breach_high:
            return 0.5 * (breach_high - value) / (breach_high - thin_high)
        else:
            return 0.0

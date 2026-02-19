"""Multi-country MAC calculator and comparative analysis tools.

This module enables cross-country MAC comparisons and regional analysis,
extending the framework's applicability beyond US markets.

Key Features:
- Calculate MAC scores using country-specific thresholds
- Compare MAC scores across regions for the same time period
- Identify divergence/convergence patterns
- Analyze contagion pathways between regions

Example Usage:
    from grri_mac.mac.multicountry import (
        MultiCountryMAC,
        compare_regions,
        analyze_contagion_pathways,
    )

    # Calculate MAC for multiple regions
    calculator = MultiCountryMAC()
    results = calculator.calculate_all_regions(indicator_data)

    # Compare US vs EU during Russia-Ukraine
    comparison = compare_regions(
        regions=["US", "EU"],
        date="2022-02-24",
        scenario_name="Russia-Ukraine",
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from .composite import calculate_mac, calculate_mac_ml
from .scorer import score_indicator_simple, score_indicator_range
from ..pillars.countries import (
    CountryProfile,
    COUNTRY_PROFILES,
    get_country_profile,
)
from ..pillars.calibrated import get_calibrated_thresholds


class ContagionDirection(Enum):
    """Direction of contagion spillover."""
    US_TO_REGION = "us_to_region"
    REGION_TO_US = "region_to_us"
    BIDIRECTIONAL = "bidirectional"
    DECOUPLED = "decoupled"


@dataclass
class RegionalMACResult:
    """MAC result for a specific region."""

    country_code: str
    country_name: str
    mac_score: float
    pillar_scores: dict[str, float]
    breach_flags: list[str]
    data_coverage: dict[str, bool]  # Which indicators had available data
    notes: list[str] = field(default_factory=list)


@dataclass
class ComparativeAnalysis:
    """Result of comparing MAC across regions."""

    date: datetime
    scenario_name: Optional[str]
    regional_results: dict[str, RegionalMACResult]
    divergence_score: float  # 0 = identical, 1 = maximum divergence
    lead_region: Optional[str]  # Region with lowest MAC (most stressed)
    lag_region: Optional[str]  # Region with highest MAC (least stressed)
    contagion_direction: ContagionDirection
    key_differentiators: list[str]  # Pillars driving divergence
    interpretation: str


@dataclass
class ContagionPathway:
    """Analysis of stress transmission between regions."""

    source_region: str
    target_region: str
    transmission_channel: str  # e.g., "banking", "currency", "equity"
    strength: float  # 0-1 scale
    indicators: list[str]  # Indicators showing transmission
    lag_days: int  # Estimated transmission lag


class MultiCountryMAC:
    """Calculator for multi-country MAC scores."""

    def __init__(self):
        """Initialize calculator with country profiles."""
        self.profiles = COUNTRY_PROFILES
        self.us_thresholds = get_calibrated_thresholds()

    def calculate_regional_mac(
        self,
        country_code: str,
        indicators: dict[str, dict[str, float]],
        use_ml_weights: bool = False,
    ) -> RegionalMACResult:
        """
        Calculate MAC for a specific region using its calibrated thresholds.

        Args:
            country_code: ISO country code (US, EU, CN, JP, UK)
            indicators: Dict of pillar -> indicator -> value
            use_ml_weights: Whether to use ML-optimized weights

        Returns:
            RegionalMACResult with MAC score and breakdown
        """
        code = country_code.upper()

        if code == "US":
            return self._calculate_us_mac(indicators, use_ml_weights)

        profile = get_country_profile(code)
        if profile is None:
            raise ValueError(f"Unsupported country code: {code}")

        return self._calculate_regional_mac_with_profile(
            profile, indicators, use_ml_weights
        )

    def _calculate_us_mac(
        self,
        indicators: dict[str, dict[str, float]],
        use_ml_weights: bool,
    ) -> RegionalMACResult:
        """Calculate MAC for US using calibrated thresholds."""
        pillar_scores = {}
        breach_flags = []
        data_coverage = {}

        # Score each pillar
        for pillar in [
            "liquidity", "valuation", "positioning",
            "volatility", "policy", "contagion",
        ]:
            if pillar not in indicators:
                pillar_scores[pillar] = 0.5  # Default neutral
                data_coverage[pillar] = False
                continue

            thresholds = self.us_thresholds.get(pillar, {})
            indicator_scores = []
            has_data = False

            for ind_name, ind_value in indicators[pillar].items():
                if ind_value is None:
                    continue
                has_data = True

                ind_thresholds = thresholds.get(ind_name, {})
                if not ind_thresholds:
                    continue

                score = self._score_indicator(ind_value, ind_thresholds)
                indicator_scores.append(score)

            if indicator_scores:
                pillar_score = sum(indicator_scores) / len(indicator_scores)
                pillar_scores[pillar] = pillar_score
                if pillar_score < 0.2:
                    breach_flags.append(pillar)
            else:
                pillar_scores[pillar] = 0.5

            data_coverage[pillar] = has_data

        # Calculate composite MAC
        if use_ml_weights:
            result = calculate_mac_ml(pillar_scores)
        else:
            result = calculate_mac(pillar_scores)

        return RegionalMACResult(
            country_code="US",
            country_name="United States",
            mac_score=result.mac_score,
            pillar_scores=pillar_scores,
            breach_flags=breach_flags,
            data_coverage=data_coverage,
            notes=["Baseline calibrated thresholds (1998-2025 validation)"],
        )

    def _calculate_regional_mac_with_profile(
        self,
        profile: CountryProfile,
        indicators: dict[str, dict[str, float]],
        use_ml_weights: bool,
    ) -> RegionalMACResult:
        """Calculate MAC for non-US region using country profile."""
        pillar_scores = {}
        breach_flags = []
        data_coverage = {}
        notes = list(profile.notes)

        # Map pillar names to profile attributes
        pillar_threshold_map = {
            "liquidity": profile.liquidity_thresholds,
            "valuation": profile.valuation_thresholds,
            "positioning": profile.positioning_thresholds,
            "volatility": profile.volatility_thresholds,
            "policy": profile.policy_thresholds,
            "contagion": profile.contagion_thresholds,
        }

        # Score each pillar
        for pillar, thresholds in pillar_threshold_map.items():
            if pillar not in indicators or not thresholds:
                pillar_scores[pillar] = 0.5  # Default neutral
                data_coverage[pillar] = False
                if not thresholds:
                    notes.append(f"{pillar}: limited data available")
                continue

            indicator_scores = []
            has_data = False

            for ind_name, ind_value in indicators[pillar].items():
                if ind_value is None:
                    continue
                has_data = True

                ind_thresholds = thresholds.get(ind_name, {})
                if not ind_thresholds:
                    continue

                score = self._score_indicator(ind_value, ind_thresholds)
                indicator_scores.append(score)

            if indicator_scores:
                pillar_score = sum(indicator_scores) / len(indicator_scores)
                pillar_scores[pillar] = pillar_score
                if pillar_score < 0.2:
                    breach_flags.append(pillar)
            else:
                pillar_scores[pillar] = 0.5

            data_coverage[pillar] = has_data

        # Calculate composite MAC
        if use_ml_weights:
            result = calculate_mac_ml(pillar_scores)
        else:
            result = calculate_mac(pillar_scores)

        return RegionalMACResult(
            country_code=profile.code,
            country_name=profile.name,
            mac_score=result.mac_score,
            pillar_scores=pillar_scores,
            breach_flags=breach_flags,
            data_coverage=data_coverage,
            notes=notes,
        )

    def _score_indicator(
        self,
        value: float,
        thresholds: dict,
    ) -> float:
        """Score an indicator using its thresholds."""
        # Check for two-sided thresholds (range-based)
        if "ample_low" in thresholds and "ample_high" in thresholds:
            return score_indicator_range(
                value,
                ample_range=(thresholds["ample_low"], thresholds["ample_high"]),
                thin_range=(
                    thresholds.get("thin_low", thresholds["ample_low"] * 0.5),
                    thresholds.get("thin_high", thresholds["ample_high"] * 1.5),
                ),
                breach_range=(
                    thresholds.get("breach_low", thresholds.get("thin_low", 0) * 0.5),
                    thresholds.get("breach_high", thresholds.get("thin_high", 0) * 1.5),
                ),
            )

        # Single-sided thresholds
        if "ample" in thresholds:
            ample = thresholds["ample"]
            thin = thresholds.get("thin", ample * 2)
            breach = thresholds.get("breach", thin * 2)

            # Determine direction: if thin > ample, lower is better
            if thin > ample:
                return score_indicator_simple(
                    value, ample, thin, breach, lower_is_better=True
                )
            else:
                return score_indicator_simple(
                    value, ample, thin, breach, lower_is_better=False
                )

        return 0.5  # Default neutral

    def calculate_all_regions(
        self,
        indicators_by_region: dict[str, dict[str, dict[str, float]]],
        use_ml_weights: bool = False,
    ) -> dict[str, RegionalMACResult]:
        """
        Calculate MAC for all regions with available data.

        Args:
            indicators_by_region: Dict of region -> pillar -> indicator -> value
            use_ml_weights: Whether to use ML-optimized weights

        Returns:
            Dict mapping region codes to RegionalMACResult
        """
        results = {}
        for region, indicators in indicators_by_region.items():
            try:
                results[region] = self.calculate_regional_mac(
                    region, indicators, use_ml_weights
                )
            except ValueError as e:
                print(f"Warning: Skipping {region}: {e}")
        return results


def compare_regions(
    regional_results: dict[str, RegionalMACResult],
    date: Optional[datetime] = None,
    scenario_name: Optional[str] = None,
) -> ComparativeAnalysis:
    """
    Compare MAC scores across regions and identify divergence patterns.

    Args:
        regional_results: Dict mapping region codes to RegionalMACResult
        date: Date of comparison (optional)
        scenario_name: Name of scenario being analyzed (optional)

    Returns:
        ComparativeAnalysis with divergence metrics and interpretation
    """
    if len(regional_results) < 2:
        raise ValueError("Need at least 2 regions for comparison")

    # Sort by MAC score to find lead/lag regions
    sorted_regions = sorted(
        regional_results.items(),
        key=lambda x: x[1].mac_score,
    )

    lead_region = sorted_regions[0][0]  # Lowest MAC = most stressed
    lag_region = sorted_regions[-1][0]  # Highest MAC = least stressed

    # Calculate divergence score
    mac_scores = [r.mac_score for r in regional_results.values()]
    max_score = max(mac_scores)
    min_score = min(mac_scores)
    divergence_score = max_score - min_score  # 0 = identical, ~1 = max divergence

    # Identify pillars driving divergence
    key_differentiators = _identify_key_differentiators(regional_results)

    # Determine contagion direction
    contagion_direction = _determine_contagion_direction(regional_results)

    # Generate interpretation
    interpretation = _generate_comparison_interpretation(
        regional_results,
        divergence_score,
        lead_region,
        lag_region,
        key_differentiators,
        contagion_direction,
        scenario_name,
    )

    return ComparativeAnalysis(
        date=date or datetime.now(),
        scenario_name=scenario_name,
        regional_results=regional_results,
        divergence_score=divergence_score,
        lead_region=lead_region,
        lag_region=lag_region,
        contagion_direction=contagion_direction,
        key_differentiators=key_differentiators,
        interpretation=interpretation,
    )


def _identify_key_differentiators(
    regional_results: dict[str, RegionalMACResult],
) -> list[str]:
    """Identify pillars with largest cross-regional variance."""
    if len(regional_results) < 2:
        return []

    pillars = ["liquidity", "valuation", "positioning", "volatility", "policy", "contagion"]
    pillar_variance = {}

    for pillar in pillars:
        scores = []
        for result in regional_results.values():
            if pillar in result.pillar_scores:
                scores.append(result.pillar_scores[pillar])

        if len(scores) >= 2:
            variance = max(scores) - min(scores)
            pillar_variance[pillar] = variance

    # Return pillars sorted by variance (highest first)
    sorted_pillars = sorted(pillar_variance.items(), key=lambda x: -x[1])
    return [p[0] for p in sorted_pillars if p[1] > 0.15]  # Threshold for significance


def _determine_contagion_direction(
    regional_results: dict[str, RegionalMACResult],
) -> ContagionDirection:
    """Determine direction of stress transmission."""
    if "US" not in regional_results:
        return ContagionDirection.DECOUPLED

    us_result = regional_results["US"]
    other_results = {k: v for k, v in regional_results.items() if k != "US"}

    if not other_results:
        return ContagionDirection.DECOUPLED

    us_mac = us_result.mac_score
    avg_other_mac = sum(r.mac_score for r in other_results.values()) / len(other_results)

    # Check contagion pillar specifically
    us_contagion = us_result.pillar_scores.get("contagion", 0.5)
    avg_other_contagion = sum(
        r.pillar_scores.get("contagion", 0.5) for r in other_results.values()
    ) / len(other_results)

    mac_diff = us_mac - avg_other_mac
    contagion_diff = us_contagion - avg_other_contagion

    # Significant divergence threshold
    if abs(mac_diff) < 0.1 and abs(contagion_diff) < 0.1:
        return ContagionDirection.BIDIRECTIONAL  # Synchronized stress

    if mac_diff < -0.15:
        # US more stressed
        if contagion_diff < 0:
            return ContagionDirection.US_TO_REGION  # US stress spreading
        else:
            return ContagionDirection.DECOUPLED

    if mac_diff > 0.15:
        # Other regions more stressed
        if contagion_diff > 0:
            return ContagionDirection.REGION_TO_US  # Regional stress spreading
        else:
            return ContagionDirection.DECOUPLED

    return ContagionDirection.BIDIRECTIONAL


def _generate_comparison_interpretation(
    regional_results: dict[str, RegionalMACResult],
    divergence_score: float,
    lead_region: str,
    lag_region: str,
    key_differentiators: list[str],
    contagion_direction: ContagionDirection,
    scenario_name: Optional[str],
) -> str:
    """Generate human-readable interpretation of comparison."""
    lines = []

    # Overall divergence assessment
    if divergence_score < 0.1:
        lines.append(
            "Regional MAC scores are closely synchronized, indicating global stress transmission.")
    elif divergence_score < 0.25:
        lines.append(
            "Moderate regional divergence suggests"
            " partial decoupling or delayed transmission."
        )
    else:
        lines.append(
            "Significant regional divergence indicates"
            " localized stress or strong policy"
            " differentiation."
        )

    # Lead/lag dynamics
    lead_result = regional_results[lead_region]
    lag_result = regional_results[lag_region]
    lines.append(
        f"\n{lead_result.country_name} (MAC: {lead_result.mac_score:.2f}) shows most stress, "
        f"while {lag_result.country_name} (MAC: {lag_result.mac_score:.2f}) has strongest buffers."
    )

    # Key differentiators
    if key_differentiators:
        lines.append(f"\nKey divergence drivers: {', '.join(key_differentiators)}")

    # Contagion direction
    direction_text = {
        ContagionDirection.US_TO_REGION: (
            "Stress appears to originate from US"
            " and spread to other regions."
        ),
        ContagionDirection.REGION_TO_US: (
            "Stress appears to originate from"
            " non-US regions and spread to US."
        ),
        ContagionDirection.BIDIRECTIONAL: (
            "Stress is synchronized across regions"
            " (global systemic event)."
        ),
        ContagionDirection.DECOUPLED: (
            "Regional stress patterns appear"
            " decoupled (localized events)."
        ),
    }
    lines.append(f"\nContagion pattern: {direction_text[contagion_direction]}")

    # Scenario-specific insights
    if scenario_name:
        lines.append(f"\n[Scenario: {scenario_name}]")

    return "\n".join(lines)


def analyze_contagion_pathways(
    regional_results: dict[str, RegionalMACResult],
    historical_results: Optional[list[dict[str, RegionalMACResult]]] = None,
) -> list[ContagionPathway]:
    """
    Analyze potential contagion pathways between regions.

    Examines pillar-level patterns to identify transmission channels:
    - Banking channel: Banking stress indicators
    - Currency channel: FX and cross-currency basis indicators
    - Equity channel: Volatility and correlation indicators
    - Sovereign channel: Policy and valuation indicators

    Args:
        regional_results: Current regional MAC results
        historical_results: Optional list of past results for lag estimation

    Returns:
        List of identified contagion pathways
    """
    pathways: list[ContagionPathway] = []

    regions = list(regional_results.keys())
    if len(regions) < 2:
        return pathways

    # Analyze each regional pair
    for i, source in enumerate(regions):
        for target in regions[i + 1:]:
            source_result = regional_results[source]
            target_result = regional_results[target]

            # Banking channel
            banking_pathway = _analyze_banking_channel(source, target, source_result, target_result)
            if banking_pathway:
                pathways.append(banking_pathway)

            # Currency channel
            currency_pathway = _analyze_currency_channel(
                source, target, source_result, target_result)
            if currency_pathway:
                pathways.append(currency_pathway)

            # Equity/volatility channel
            equity_pathway = _analyze_equity_channel(source, target, source_result, target_result)
            if equity_pathway:
                pathways.append(equity_pathway)

    return pathways


def _analyze_banking_channel(
    source: str,
    target: str,
    source_result: RegionalMACResult,
    target_result: RegionalMACResult,
) -> Optional[ContagionPathway]:
    """Analyze banking stress transmission."""
    # Check if both have contagion pillar stressed
    source_contagion = source_result.pillar_scores.get("contagion", 0.5)
    target_contagion = target_result.pillar_scores.get("contagion", 0.5)
    source_liquidity = source_result.pillar_scores.get("liquidity", 0.5)
    target_liquidity = target_result.pillar_scores.get("liquidity", 0.5)

    # Banking channel active if both contagion stressed OR both liquidity stressed
    if (source_contagion < 0.3 and target_contagion < 0.3) or \
       (source_liquidity < 0.3 and target_liquidity < 0.3):
        # Determine direction based on which is more stressed
        if source_contagion < target_contagion:
            actual_source, actual_target = source, target
        else:
            actual_source, actual_target = target, source

        return ContagionPathway(
            source_region=actual_source,
            target_region=actual_target,
            transmission_channel="banking",
            strength=max(0, 1 - min(source_contagion, target_contagion) / 0.3),
            indicators=["banking_stress", "liquidity"],
            lag_days=2,  # Banking stress typically transmits quickly
        )

    return None


def _analyze_currency_channel(
    source: str,
    target: str,
    source_result: RegionalMACResult,
    target_result: RegionalMACResult,
) -> Optional[ContagionPathway]:
    """Analyze currency/FX transmission."""
    source_contagion = source_result.pillar_scores.get("contagion", 0.5)
    target_contagion = target_result.pillar_scores.get("contagion", 0.5)
    source_liquidity = source_result.pillar_scores.get("liquidity", 0.5)
    target_liquidity = target_result.pillar_scores.get("liquidity", 0.5)

    # Currency channel: contagion + liquidity stress together
    source_fx_stress = (source_contagion < 0.4 and source_liquidity < 0.4)
    target_fx_stress = (target_contagion < 0.4 and target_liquidity < 0.4)

    if source_fx_stress or target_fx_stress:
        # Determine direction
        if source_fx_stress and not target_fx_stress:
            actual_source, actual_target = source, target
            strength = 1 - (source_contagion + source_liquidity) / 0.8
        elif target_fx_stress and not source_fx_stress:
            actual_source, actual_target = target, source
            strength = 1 - (target_contagion + target_liquidity) / 0.8
        else:
            # Both stressed - use US as source if applicable
            if source == "US":
                actual_source, actual_target = source, target
            elif target == "US":
                actual_source, actual_target = target, source
            else:
                # Non-US pair, use more stressed as source
                if source_contagion < target_contagion:
                    actual_source, actual_target = source, target
                else:
                    actual_source, actual_target = target, source
            strength = max(
                1 - (source_contagion + source_liquidity) / 0.8,
                1 - (target_contagion + target_liquidity) / 0.8,
            )

        return ContagionPathway(
            source_region=actual_source,
            target_region=actual_target,
            transmission_channel="currency",
            strength=max(0, min(1, strength)),
            indicators=["cross_currency_basis", "fx_reserves", "dxy"],
            lag_days=1,  # FX transmits very quickly
        )

    return None


def _analyze_equity_channel(
    source: str,
    target: str,
    source_result: RegionalMACResult,
    target_result: RegionalMACResult,
) -> Optional[ContagionPathway]:
    """Analyze equity/volatility transmission."""
    source_vol = source_result.pillar_scores.get("volatility", 0.5)
    target_vol = target_result.pillar_scores.get("volatility", 0.5)

    # Equity channel active if both have volatility stress
    if source_vol < 0.3 and target_vol < 0.3:
        # Determine direction based on which is more stressed
        if source_vol < target_vol:
            actual_source, actual_target = source, target
        else:
            actual_source, actual_target = target, source

        return ContagionPathway(
            source_region=actual_source,
            target_region=actual_target,
            transmission_channel="equity",
            strength=max(0, 1 - min(source_vol, target_vol) / 0.3),
            indicators=["vix", "global_equity_corr", "vstoxx"],
            lag_days=0,  # Equity vol transmits immediately
        )

    return None


# =============================================================================
# SCENARIO COMPARISON UTILITIES
# =============================================================================

def create_scenario_comparison(
    scenario_name: str,
    date: datetime,
    us_indicators: dict[str, dict[str, float]],
    regional_indicators: dict[str, dict[str, dict[str, float]]],
    use_ml_weights: bool = True,
) -> ComparativeAnalysis:
    """
    Create a complete scenario comparison across regions.

    This is a convenience function for analyzing specific historical events
    like Russia-Ukraine 2022 or COVID-19 2020.

    Args:
        scenario_name: Name of the scenario (e.g., "Russia-Ukraine 2022")
        date: Date of the scenario
        us_indicators: US indicator values by pillar
        regional_indicators: Dict of region -> pillar -> indicator -> value
        use_ml_weights: Whether to use ML-optimized weights

    Returns:
        ComparativeAnalysis with full comparison
    """
    calculator = MultiCountryMAC()

    # Calculate US MAC
    us_result = calculator.calculate_regional_mac("US", us_indicators, use_ml_weights)

    # Calculate regional MACs
    all_results = {"US": us_result}
    for region, indicators in regional_indicators.items():
        try:
            result = calculator.calculate_regional_mac(region, indicators, use_ml_weights)
            all_results[region] = result
        except ValueError as e:
            print(f"Warning: Could not calculate {region} MAC: {e}")

    return compare_regions(all_results, date, scenario_name)


def get_default_regional_thresholds_comparison() -> dict[str, dict[str, dict]]:
    """
    Get a comparison table of key thresholds across all supported regions.

    Useful for understanding how thresholds differ by region.

    Returns:
        Nested dict: region -> pillar -> indicator -> thresholds
    """
    from ..pillars.countries import get_threshold_comparison

    pillars = ["liquidity", "valuation", "positioning", "volatility", "policy", "contagion"]
    comparison = {}

    for pillar in pillars:
        comparison[pillar] = get_threshold_comparison(pillar)

    return comparison

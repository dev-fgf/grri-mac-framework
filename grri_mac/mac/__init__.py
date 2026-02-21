"""MAC calculation modules."""

from .scorer import score_indicator, score_pillar
from .composite import (
    calculate_mac,
    calculate_mac_ml,
    get_recommended_weights,
    DEFAULT_WEIGHTS_6_PILLAR,
    ML_OPTIMIZED_WEIGHTS,
    INTERACTION_ADJUSTED_WEIGHTS,
)
from .multiplier import mac_to_multiplier
from .multicountry import (
    MultiCountryMAC,
    RegionalMACResult,
    ComparativeAnalysis,
    ContagionPathway,
    ContagionDirection,
    compare_regions,
    analyze_contagion_pathways,
    create_scenario_comparison,
    get_default_regional_thresholds_comparison,
)
from .dependence import (
    PillarDependenceAnalyzer,
    DependenceReport,
    PairwiseResult,
    compute_mi,
    compute_hsic,
    compute_mic,
    compute_total_correlation,
    compute_dual_total_correlation,
)

__all__ = [
    # Core scoring
    "score_indicator",
    "score_pillar",
    "calculate_mac",
    "calculate_mac_ml",
    "get_recommended_weights",
    "mac_to_multiplier",
    # Weight configurations
    "DEFAULT_WEIGHTS_6_PILLAR",
    "ML_OPTIMIZED_WEIGHTS",
    "INTERACTION_ADJUSTED_WEIGHTS",
    # Multi-country analysis
    "MultiCountryMAC",
    "RegionalMACResult",
    "ComparativeAnalysis",
    "ContagionPathway",
    "ContagionDirection",
    "compare_regions",
    "analyze_contagion_pathways",
    "create_scenario_comparison",
    "get_default_regional_thresholds_comparison",
    # Dependence analysis
    "PillarDependenceAnalyzer",
    "DependenceReport",
    "PairwiseResult",
    "compute_mi",
    "compute_hsic",
    "compute_mic",
    "compute_total_correlation",
    "compute_dual_total_correlation",
]

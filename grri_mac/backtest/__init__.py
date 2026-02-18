"""Backtesting engine for MAC framework validation."""

from .engine import BacktestEngine, BacktestResult
from .scenarios import HistoricalScenario, CrisisSeverityScores, KNOWN_EVENTS
from .calibrated_engine import CalibratedBacktestEngine
from .calibration import (
    CalibrationValidator,
    CalibrationResult,
    CrossValidationResult,
    SensitivityResult,
    RobustnessReport,
    run_robustness_analysis,
    format_robustness_report,
)
from .crisis_severity_rubric import (
    CSRInput,
    CSRResult,
    MarketDysfunction,
    PolicyResponse,
    ContagionBreadth,
    calculate_csr,
    score_drawdown,
    score_duration,
    validate_csr_independence,
)
from .thematic_holdout import (
    ThematicHoldoutReport,
    HoldoutResult,
    HOLDOUT_SETS,
    run_thematic_holdout_validation,
    format_holdout_report,
    diagnose_holdout_failure,
)
from .precision_recall import (
    PrecisionRecallReport,
    PRPoint,
    OperatingPointReport,
    FPClassification,
    FPCategory,
    EraFPR,
    ClientArchetype,
    CrisisWindow,
    STANDARD_OPERATING_POINTS,
    compute_precision_recall_curve,
    optimal_threshold_for_beta,
    breakeven_precision,
    format_precision_recall_report,
    export_precision_recall_json,
    build_crisis_windows,
)
from .era_configs import (
    get_era,
    get_available_pillars,
    get_default_score,
    get_era_weights,
    get_era_overrides,
    ERA_BOUNDARIES,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "HistoricalScenario",
    "CrisisSeverityScores",
    "KNOWN_EVENTS",
    "CalibratedBacktestEngine",
    # Calibration validation
    "CalibrationValidator",
    "CalibrationResult",
    "CrossValidationResult",
    "SensitivityResult",
    "RobustnessReport",
    "run_robustness_analysis",
    "format_robustness_report",
    # Crisis Severity Rubric (§13.2)
    "CSRInput",
    "CSRResult",
    "MarketDysfunction",
    "PolicyResponse",
    "ContagionBreadth",
    "calculate_csr",
    "score_drawdown",
    "score_duration",
    "validate_csr_independence",
    # Thematic holdout validation (§13.4)
    "ThematicHoldoutReport",
    "HoldoutResult",
    "HOLDOUT_SETS",
    "run_thematic_holdout_validation",
    "format_holdout_report",
    "diagnose_holdout_failure",
    # Precision-recall framework (§15.6–15.7)
    "PrecisionRecallReport",
    "PRPoint",
    "OperatingPointReport",
    "FPClassification",
    "FPCategory",
    "EraFPR",
    "ClientArchetype",
    "CrisisWindow",
    "STANDARD_OPERATING_POINTS",
    "compute_precision_recall_curve",
    "optimal_threshold_for_beta",
    "breakeven_precision",
    "format_precision_recall_report",
    "export_precision_recall_json",
    "build_crisis_windows",
    # Era-specific configs
    "get_era",
    "get_available_pillars",
    "get_default_score",
    "get_era_weights",
    "get_era_overrides",
    "ERA_BOUNDARIES",
]

"""Backtesting engine for MAC framework validation."""

from .engine import BacktestEngine, BacktestResult
from .scenarios import HistoricalScenario, KNOWN_EVENTS
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
    # Era-specific configs
    "get_era",
    "get_available_pillars",
    "get_default_score",
    "get_era_weights",
    "get_era_overrides",
    "ERA_BOUNDARIES",
]

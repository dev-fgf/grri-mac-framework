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
]

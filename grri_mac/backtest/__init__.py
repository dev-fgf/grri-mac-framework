"""Backtesting engine for MAC framework validation."""

from .engine import BacktestEngine, BacktestResult
from .scenarios import HistoricalScenario, KNOWN_EVENTS

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "HistoricalScenario",
    "KNOWN_EVENTS",
]

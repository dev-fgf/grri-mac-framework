"""Predictive analytics module for MAC framework.

Includes:
- Monte Carlo simulations of shock propagation
- Regime-based impact modeling
- Blind backtesting (no lookahead bias)
- Forward-looking indicator integration
"""

from .monte_carlo import (
    MonteCarloSimulator,
    ShockScenario,
    SimulationResult,
    RegimeImpactAnalysis,
    run_regime_comparison,
)
from .blind_backtest import (
    BlindBacktester,
    BlindBacktestResult,
    run_blind_backtest,
)
from .shock_propagation import (
    ShockPropagationModel,
    PropagationResult,
    CascadeAnalysis,
)

__all__ = [
    # Monte Carlo
    "MonteCarloSimulator",
    "ShockScenario",
    "SimulationResult",
    "RegimeImpactAnalysis",
    "run_regime_comparison",
    # Blind backtesting
    "BlindBacktester",
    "BlindBacktestResult",
    "run_blind_backtest",
    # Shock propagation
    "ShockPropagationModel",
    "PropagationResult",
    "CascadeAnalysis",
]

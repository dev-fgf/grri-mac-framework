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
from .cascade_var import (
    SVAREstimate,
    RobustnessResult,
    AccelerationFactors,
    GrangerResult,
    CascadeVARReport,
    estimate_svar,
    run_svar_pipeline,
    robustness_all_orderings,
    estimate_acceleration_factors,
    granger_causality_tests,
    transmission_matrix_to_dict,
    update_interaction_matrix,
    format_svar_report,
    CHOLESKY_ORDERING,
    CRITICAL_THRESHOLDS,
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
    # SVAR cascade estimation (v6 §10.2)
    "SVAREstimate",
    "RobustnessResult",
    "AccelerationFactors",
    "GrangerResult",
    "CascadeVARReport",
    "estimate_svar",
    "run_svar_pipeline",
    "robustness_all_orderings",
    "estimate_acceleration_factors",
    "granger_causality_tests",
    "transmission_matrix_to_dict",
    "update_interaction_matrix",
    "format_svar_report",
    "CHOLESKY_ORDERING",
    "CRITICAL_THRESHOLDS",
]

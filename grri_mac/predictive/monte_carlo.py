"""Monte Carlo simulation module for shock scenario analysis.

This module provides forward-looking analysis by simulating how shocks
propagate through the financial system under different MAC regimes.

Key Insight: The same shock has vastly different impacts depending on
the current MAC state (absorption capacity).

Usage:
    from grri_mac.predictive import MonteCarloSimulator, run_regime_comparison

    simulator = MonteCarloSimulator()
    results = simulator.run_simulation(
        shock_type="liquidity",
        shock_magnitude=2.0,  # 2 standard deviations
        n_simulations=1000,
    )

    # Compare impact across regimes
    comparison = run_regime_comparison(shock_magnitude=2.0)
"""

import random
import math
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ShockType(Enum):
    """Types of exogenous shocks."""
    LIQUIDITY = "liquidity"       # Funding market stress
    VOLATILITY = "volatility"     # VIX spike
    CREDIT = "credit"             # Credit spread widening
    POSITIONING = "positioning"   # Forced deleveraging
    CONTAGION = "contagion"       # Cross-border spillover
    POLICY = "policy"             # Policy uncertainty
    COMBINED = "combined"         # Multi-factor shock


class MACRegime(Enum):
    """MAC regime states."""
    AMPLE = "ample"         # MAC > 0.65
    THIN = "thin"           # 0.50 < MAC <= 0.65
    STRETCHED = "stretched"  # 0.35 < MAC <= 0.50
    BREACH = "breach"       # MAC <= 0.35


@dataclass
class ShockScenario:
    """Definition of a shock scenario for simulation."""
    shock_type: ShockType
    magnitude_std: float  # Magnitude in standard deviations
    duration_days: int = 5
    description: str = ""


@dataclass
class SimulationResult:
    """Result of a single Monte Carlo simulation."""
    initial_mac: float
    final_mac: float
    mac_change: float
    pillar_impacts: dict[str, float]
    hedge_failure_prob: float
    regime_transition: Optional[str]
    max_drawdown_estimate: float
    recovery_days_estimate: int


@dataclass
class RegimeImpactAnalysis:
    """Analysis of shock impact across different regimes."""
    shock_scenario: ShockScenario
    n_simulations: int

    # Results by regime
    ample_results: dict = field(default_factory=dict)
    thin_results: dict = field(default_factory=dict)
    stretched_results: dict = field(default_factory=dict)
    breach_results: dict = field(default_factory=dict)

    # Key insights
    amplification_factor: float = 1.0  # How much worse in breach vs ample
    nonlinearity_score: float = 0.0    # Degree of non-linear response
    critical_threshold: float = 0.35   # MAC level where response accelerates


# Pillar correlation matrix (empirically derived from crisis data)
# Positive = shocks tend to co-occur; Negative = offsetting
PILLAR_CORRELATIONS = {
    ("liquidity", "volatility"): 0.65,
    ("liquidity", "positioning"): 0.55,
    ("liquidity", "contagion"): 0.70,
    ("volatility", "positioning"): 0.60,
    ("volatility", "valuation"): 0.45,
    ("positioning", "contagion"): 0.50,
    ("contagion", "valuation"): 0.40,
    ("policy", "volatility"): -0.20,  # Fed intervention dampens vol
}

# Shock transmission coefficients by regime
# Higher values = shock transmits more strongly
TRANSMISSION_COEFFICIENTS = {
    MACRegime.AMPLE: {
        "direct_impact": 0.3,
        "spillover": 0.1,
        "amplification": 1.0,
    },
    MACRegime.THIN: {
        "direct_impact": 0.5,
        "spillover": 0.25,
        "amplification": 1.5,
    },
    MACRegime.STRETCHED: {
        "direct_impact": 0.7,
        "spillover": 0.45,
        "amplification": 2.5,
    },
    MACRegime.BREACH: {
        "direct_impact": 0.9,
        "spillover": 0.7,
        "amplification": 4.0,
    },
}


class MonteCarloSimulator:
    """Monte Carlo simulator for MAC shock analysis.

    Simulates how exogenous shocks propagate through the financial system
    under different MAC regimes, demonstrating the non-linear amplification
    that occurs when absorption capacity is depleted.
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize simulator.

        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

        # Base volatility parameters (from historical data)
        self.pillar_volatilities = {
            "liquidity": 0.15,
            "valuation": 0.10,
            "positioning": 0.12,
            "volatility": 0.20,
            "policy": 0.05,
            "contagion": 0.18,
        }

        # Shock type to pillar mapping
        self.shock_pillar_map = {
            ShockType.LIQUIDITY: ["liquidity", "contagion"],
            ShockType.VOLATILITY: ["volatility", "positioning"],
            ShockType.CREDIT: ["valuation", "liquidity"],
            ShockType.POSITIONING: ["positioning", "liquidity"],
            ShockType.CONTAGION: ["contagion", "liquidity", "volatility"],
            ShockType.POLICY: ["policy", "volatility"],
            ShockType.COMBINED: list(self.pillar_volatilities.keys()),
        }

    def _get_regime(self, mac_score: float) -> MACRegime:
        """Determine MAC regime from score."""
        if mac_score > 0.65:
            return MACRegime.AMPLE
        elif mac_score > 0.50:
            return MACRegime.THIN
        elif mac_score > 0.35:
            return MACRegime.STRETCHED
        else:
            return MACRegime.BREACH

    def _get_correlation(self, pillar1: str, pillar2: str) -> float:
        """Get correlation between two pillars."""
        key = (pillar1, pillar2)
        if key in PILLAR_CORRELATIONS:
            return PILLAR_CORRELATIONS[key]
        key = (pillar2, pillar1)
        if key in PILLAR_CORRELATIONS:
            return PILLAR_CORRELATIONS[key]
        return 0.0

    def _simulate_single_path(
        self,
        initial_pillars: dict[str, float],
        shock_scenario: ShockScenario,
    ) -> SimulationResult:
        """Simulate a single shock path.

        Args:
            initial_pillars: Starting pillar scores
            shock_scenario: Shock to apply

        Returns:
            SimulationResult with outcomes
        """
        # Calculate initial MAC
        initial_mac = sum(initial_pillars.values()) / len(initial_pillars)
        regime = self._get_regime(initial_mac)
        coeffs = TRANSMISSION_COEFFICIENTS[regime]

        # Apply shock to primary pillars
        affected_pillars = self.shock_pillar_map[shock_scenario.shock_type]
        pillar_impacts = {}

        for pillar in initial_pillars:
            if pillar in affected_pillars:
                # Direct impact on affected pillars
                vol = self.pillar_volatilities[pillar]
                impact = (
                    shock_scenario.magnitude_std
                    * vol
                    * coeffs["direct_impact"]
                    * coeffs["amplification"]
                )
                # Add noise
                noise = random.gauss(0, vol * 0.3)
                pillar_impacts[pillar] = -impact + noise
            else:
                # Spillover to non-affected pillars
                max_spillover = 0.0
                for affected in affected_pillars:
                    corr = self._get_correlation(pillar, affected)
                    spillover = (
                        shock_scenario.magnitude_std
                        * self.pillar_volatilities[pillar]
                        * corr
                        * coeffs["spillover"]
                    )
                    max_spillover = max(max_spillover, abs(spillover))

                noise = random.gauss(0, self.pillar_volatilities[pillar] * 0.2)
                pillar_impacts[pillar] = -max_spillover + noise

        # Calculate final pillar scores (bounded 0-1)
        final_pillars = {}
        for pillar, initial in initial_pillars.items():
            final = max(0.0, min(1.0, initial + pillar_impacts[pillar]))
            final_pillars[pillar] = final

        # Calculate final MAC
        final_mac = sum(final_pillars.values()) / len(final_pillars)
        final_mac = max(0.0, min(1.0, final_mac))

        # Determine regime transition
        final_regime = self._get_regime(final_mac)
        regime_transition = None
        if final_regime != regime:
            regime_transition = f"{regime.value} -> {final_regime.value}"

        # Calculate hedge failure probability based on positioning
        pos_score = final_pillars.get("positioning", 0.5)
        if pos_score < 0.2:
            hedge_failure_prob = 0.8 + random.gauss(0, 0.1)
        elif pos_score < 0.35:
            hedge_failure_prob = 0.4 + random.gauss(0, 0.15)
        else:
            hedge_failure_prob = 0.05 + random.gauss(0, 0.03)
        hedge_failure_prob = max(0, min(1, hedge_failure_prob))

        # Estimate drawdown based on MAC level and shock
        base_drawdown = shock_scenario.magnitude_std * 5  # 5% per std dev
        drawdown_multiplier = {
            MACRegime.AMPLE: 1.0,
            MACRegime.THIN: 1.5,
            MACRegime.STRETCHED: 2.5,
            MACRegime.BREACH: 4.0,
        }[final_regime]
        max_drawdown = base_drawdown * drawdown_multiplier
        max_drawdown += random.gauss(0, base_drawdown * 0.3)

        # Estimate recovery time
        base_recovery = shock_scenario.duration_days * 3
        recovery_multiplier = {
            MACRegime.AMPLE: 1.0,
            MACRegime.THIN: 1.5,
            MACRegime.STRETCHED: 3.0,
            MACRegime.BREACH: 6.0,
        }[final_regime]
        recovery_days = int(base_recovery * recovery_multiplier)
        recovery_days += random.randint(-5, 10)

        return SimulationResult(
            initial_mac=initial_mac,
            final_mac=final_mac,
            mac_change=final_mac - initial_mac,
            pillar_impacts=pillar_impacts,
            hedge_failure_prob=hedge_failure_prob,
            regime_transition=regime_transition,
            max_drawdown_estimate=max(0, max_drawdown),
            recovery_days_estimate=max(1, recovery_days),
        )

    def run_simulation(
        self,
        initial_pillars: Optional[dict[str, float]] = None,
        shock_type: ShockType = ShockType.VOLATILITY,
        shock_magnitude: float = 2.0,
        n_simulations: int = 1000,
    ) -> dict:
        """Run Monte Carlo simulation.

        Args:
            initial_pillars: Starting pillar scores (default: moderate)
            shock_type: Type of shock to simulate
            shock_magnitude: Shock size in standard deviations
            n_simulations: Number of simulation paths

        Returns:
            Dictionary with simulation statistics
        """
        if initial_pillars is None:
            # Default moderate conditions
            initial_pillars = {
                "liquidity": 0.55,
                "valuation": 0.60,
                "positioning": 0.50,
                "volatility": 0.55,
                "policy": 0.70,
                "contagion": 0.65,
            }

        shock = ShockScenario(
            shock_type=shock_type,
            magnitude_std=shock_magnitude,
            duration_days=5,
            description=f"{shock_magnitude}std {shock_type.value} shock",
        )

        results = []
        for _ in range(n_simulations):
            result = self._simulate_single_path(initial_pillars, shock)
            results.append(result)

        # Aggregate statistics
        mac_changes = [r.mac_change for r in results]
        final_macs = [r.final_mac for r in results]
        hedge_probs = [r.hedge_failure_prob for r in results]
        drawdowns = [r.max_drawdown_estimate for r in results]
        recoveries = [r.recovery_days_estimate for r in results]

        regime_transitions = [r.regime_transition for r in results if r.regime_transition]

        return {
            "shock_scenario": shock,
            "n_simulations": n_simulations,
            "initial_mac": results[0].initial_mac,
            "statistics": {
                "mac_change": {
                    "mean": sum(mac_changes) / len(mac_changes),
                    "std": self._std(mac_changes),
                    "min": min(mac_changes),
                    "max": max(mac_changes),
                    "percentile_5": sorted(mac_changes)[int(len(mac_changes) * 0.05)],
                    "percentile_95": sorted(mac_changes)[int(len(mac_changes) * 0.95)],
                },
                "final_mac": {
                    "mean": sum(final_macs) / len(final_macs),
                    "std": self._std(final_macs),
                    "prob_breach": sum(1 for m in final_macs if m < 0.35) / len(final_macs),
                },
                "hedge_failure_prob": {
                    "mean": sum(hedge_probs) / len(hedge_probs),
                    "std": self._std(hedge_probs),
                },
                "max_drawdown_pct": {
                    "mean": sum(drawdowns) / len(drawdowns),
                    "std": self._std(drawdowns),
                    "percentile_95": sorted(drawdowns)[int(len(drawdowns) * 0.95)],
                },
                "recovery_days": {
                    "mean": sum(recoveries) / len(recoveries),
                    "std": self._std(recoveries),
                },
            },
            "regime_transition_rate": len(regime_transitions) / n_simulations,
            "regime_transitions": regime_transitions[:10],  # Sample
        }

    def _std(self, values: list) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def run_regime_comparison(
        self,
        shock_type: ShockType = ShockType.VOLATILITY,
        shock_magnitude: float = 2.0,
        n_simulations: int = 1000,
    ) -> RegimeImpactAnalysis:
        """Compare shock impact across different MAC regimes.

        This is the key analysis showing non-linear amplification:
        the same shock has vastly different impacts depending on
        current absorption capacity.

        Args:
            shock_type: Type of shock to simulate
            shock_magnitude: Shock size in standard deviations
            n_simulations: Simulations per regime

        Returns:
            RegimeImpactAnalysis with comparison across regimes
        """
        shock = ShockScenario(
            shock_type=shock_type,
            magnitude_std=shock_magnitude,
            duration_days=5,
        )

        # Define representative pillar configurations for each regime
        regime_configs = {
            "ample": {
                "liquidity": 0.75, "valuation": 0.70, "positioning": 0.72,
                "volatility": 0.68, "policy": 0.80, "contagion": 0.75,
            },
            "thin": {
                "liquidity": 0.55, "valuation": 0.58, "positioning": 0.52,
                "volatility": 0.55, "policy": 0.65, "contagion": 0.60,
            },
            "stretched": {
                "liquidity": 0.40, "valuation": 0.45, "positioning": 0.38,
                "volatility": 0.42, "policy": 0.55, "contagion": 0.48,
            },
            "breach": {
                "liquidity": 0.25, "valuation": 0.30, "positioning": 0.22,
                "volatility": 0.28, "policy": 0.40, "contagion": 0.32,
            },
        }

        analysis = RegimeImpactAnalysis(
            shock_scenario=shock,
            n_simulations=n_simulations,
        )

        # Run simulations for each regime
        for regime_name, pillars in regime_configs.items():
            results = self.run_simulation(
                initial_pillars=pillars,
                shock_type=shock_type,
                shock_magnitude=shock_magnitude,
                n_simulations=n_simulations,
            )

            regime_results = {
                "initial_mac": results["initial_mac"],
                "mean_mac_change": results["statistics"]["mac_change"]["mean"],
                "std_mac_change": results["statistics"]["mac_change"]["std"],
                "prob_breach": results["statistics"]["final_mac"]["prob_breach"],
                "mean_hedge_failure_prob": results["statistics"]["hedge_failure_prob"]["mean"],
                "mean_drawdown": results["statistics"]["max_drawdown_pct"]["mean"],
                "drawdown_95th": results["statistics"]["max_drawdown_pct"]["percentile_95"],
                "mean_recovery_days": results["statistics"]["recovery_days"]["mean"],
                "regime_transition_rate": results["regime_transition_rate"],
            }

            if regime_name == "ample":
                analysis.ample_results = regime_results
            elif regime_name == "thin":
                analysis.thin_results = regime_results
            elif regime_name == "stretched":
                analysis.stretched_results = regime_results
            elif regime_name == "breach":
                analysis.breach_results = regime_results

        # Calculate amplification factor (breach vs ample impact)
        ample_change = abs(analysis.ample_results["mean_mac_change"])
        breach_change = abs(analysis.breach_results["mean_mac_change"])
        if ample_change > 0:
            analysis.amplification_factor = breach_change / ample_change

        # Calculate nonlinearity score
        # Compare actual thin/stretched to linear interpolation
        linear_mid = (ample_change + breach_change) / 2
        actual_mid = (
            abs(analysis.thin_results["mean_mac_change"]) +
            abs(analysis.stretched_results["mean_mac_change"])
        ) / 2
        if linear_mid > 0:
            analysis.nonlinearity_score = (actual_mid - linear_mid) / linear_mid

        return analysis


def run_regime_comparison(
    shock_magnitude: float = 2.0,
    shock_type: ShockType = ShockType.VOLATILITY,
    n_simulations: int = 1000,
) -> RegimeImpactAnalysis:
    """Convenience function to run regime comparison analysis."""
    simulator = MonteCarloSimulator(seed=42)
    return simulator.run_regime_comparison(
        shock_type=shock_type,
        shock_magnitude=shock_magnitude,
        n_simulations=n_simulations,
    )


def format_regime_comparison(analysis: RegimeImpactAnalysis) -> str:
    """Format regime comparison for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("MONTE CARLO REGIME IMPACT ANALYSIS")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Shock: {analysis.shock_scenario.magnitude_std}std "
                 f"{analysis.shock_scenario.shock_type.value}")
    lines.append(f"Simulations per regime: {analysis.n_simulations}")
    lines.append("")

    lines.append("IMPACT BY REGIME")
    lines.append("-" * 70)
    lines.append(f"{'Regime':<12} {'Init MAC':>10} {'MAC Chg':>10} "
                 f"{'Drawdown':>10} {'Hedge Fail':>12} {'Recovery':>10}")
    lines.append("-" * 70)

    for regime_name, results in [
        ("AMPLE", analysis.ample_results),
        ("THIN", analysis.thin_results),
        ("STRETCHED", analysis.stretched_results),
        ("BREACH", analysis.breach_results),
    ]:
        lines.append(
            f"{regime_name:<12} "
            f"{results['initial_mac']:>10.3f} "
            f"{results['mean_mac_change']:>+10.3f} "
            f"{results['mean_drawdown']:>9.1f}% "
            f"{results['mean_hedge_failure_prob']:>11.1%} "
            f"{results['mean_recovery_days']:>9.0f}d"
        )

    lines.append("")
    lines.append("KEY INSIGHTS")
    lines.append("-" * 70)
    lines.append(f"Amplification Factor (Breach vs Ample): "
                 f"{analysis.amplification_factor:.1f}x")
    lines.append(f"Non-linearity Score: {analysis.nonlinearity_score:+.2f}")
    lines.append("")

    # Interpretation
    lines.append("INTERPRETATION")
    lines.append("-" * 70)

    amp = analysis.amplification_factor
    if amp > 3:
        lines.append(f"[CRITICAL] Same shock is {amp:.1f}x worse in breach regime")
        lines.append("           Strong case for monitoring MAC as leading indicator")
    elif amp > 2:
        lines.append(f"[WARNING] Same shock is {amp:.1f}x worse in breach regime")
        lines.append("          MAC regime matters significantly for risk sizing")
    else:
        lines.append(f"[MODERATE] Shock impact {amp:.1f}x higher in breach regime")

    lines.append("")

    # Hedge failure comparison
    ample_hf = analysis.ample_results["mean_hedge_failure_prob"]
    breach_hf = analysis.breach_results["mean_hedge_failure_prob"]
    lines.append("Hedge Failure Probability:")
    lines.append(f"  - AMPLE regime:  {ample_hf:>6.1%}")
    lines.append(f"  - BREACH regime: {breach_hf:>6.1%}")
    lines.append(f"  - Increase:      {breach_hf/ample_hf if ample_hf > 0 else 0:.1f}x")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)

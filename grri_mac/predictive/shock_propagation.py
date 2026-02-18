"""Shock propagation model for cascade analysis.

Models how shocks cascade across pillars over time, capturing the
non-linear dynamics that occur during financial stress.

Key features:
- Multi-period shock propagation
- Pillar interaction effects (amplification/dampening)
- Threshold effects (cascades accelerate below critical levels)
- Policy intervention modeling
- SVAR-estimated coefficients (v6 §10.2) replace hardcoded matrix when available

This addresses the critique that static models miss the dynamic
nature of crisis propagation.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
from enum import Enum
import math


class InterventionType(Enum):
    """Types of policy intervention."""
    NONE = "none"
    LIQUIDITY = "liquidity"      # Repo facilities, lending
    QUANTITATIVE = "qe"          # Asset purchases
    RATE_CUT = "rate_cut"        # Emergency rate cut
    COORDINATED = "coordinated"  # Multi-central bank action


@dataclass
class PropagationResult:
    """Result of shock propagation simulation."""
    periods: int
    initial_pillars: dict[str, float]
    final_pillars: dict[str, float]
    pillar_paths: dict[str, list[float]]  # Time series for each pillar
    mac_path: list[float]
    cascade_triggered: bool
    cascade_period: Optional[int]
    intervention_applied: Optional[InterventionType]
    peak_stress_period: int
    recovery_started_period: Optional[int]


@dataclass
class CascadeAnalysis:
    """Analysis of cascade dynamics."""
    critical_threshold: float  # MAC level where cascade risk spikes
    cascade_probability_by_mac: dict[str, float]
    mean_cascade_severity: float
    primary_transmission_channels: list[str]
    stabilizing_factors: list[str]


# Pillar interaction matrix
# Positive = stress in row pillar increases stress in column pillar
# Negative = stress in row reduces stress in column (stabilizing)
INTERACTION_MATRIX = {
    "liquidity": {
        "liquidity": 0.0,
        "valuation": 0.3,     # Illiquidity widens spreads
        "positioning": 0.5,   # Margin calls force deleveraging
        "volatility": 0.4,    # Illiquidity increases vol
        "policy": -0.1,       # Triggers policy response
        "contagion": 0.6,     # Funding stress spreads globally
    },
    "valuation": {
        "liquidity": 0.2,     # Wide spreads reduce market making
        "valuation": 0.0,
        "positioning": 0.3,   # Losses trigger deleveraging
        "volatility": 0.3,    # Price uncertainty increases vol
        "policy": -0.1,
        "contagion": 0.3,
    },
    "positioning": {
        "liquidity": 0.6,     # Forced selling depletes liquidity
        "valuation": 0.4,     # Fire sales widen spreads
        "positioning": 0.0,
        "volatility": 0.5,    # Deleveraging spikes vol
        "policy": 0.0,
        "contagion": 0.4,     # Coordinated unwind is global
    },
    "volatility": {
        "liquidity": 0.4,     # High vol reduces market making
        "valuation": 0.2,     # Vol widens risk premia
        "positioning": 0.3,   # Vol triggers VaR breaches
        "volatility": 0.0,
        "policy": -0.05,
        "contagion": 0.3,
    },
    "policy": {
        "liquidity": -0.4,    # Policy provides liquidity
        "valuation": -0.2,    # Backstop compresses spreads
        "positioning": -0.1,  # Confidence reduces panic
        "volatility": -0.3,   # Policy calms markets
        "policy": 0.0,
        "contagion": -0.2,    # Coordinated policy helps
    },
    "contagion": {
        "liquidity": 0.5,     # Global stress tightens funding
        "valuation": 0.3,     # Risk-off widens spreads
        "positioning": 0.4,   # Global unwind
        "volatility": 0.4,    # Global vol correlation
        "policy": 0.1,        # Constrains policy space
        "contagion": 0.0,
    },
}

# Non-linear threshold effects
# When pillar score falls below threshold, transmission accelerates
THRESHOLD_EFFECTS = {
    "liquidity": {"threshold": 0.3, "multiplier": 2.0},
    "positioning": {"threshold": 0.25, "multiplier": 2.5},
    "volatility": {"threshold": 0.2, "multiplier": 1.8},
    "contagion": {"threshold": 0.3, "multiplier": 2.2},
}


class ShockPropagationModel:
    """Models multi-period shock propagation with cascade effects.

    Captures how an initial shock in one pillar cascades to others
    over multiple time periods, with non-linear amplification when
    pillars breach critical thresholds.

    Supports two coefficient sources (v6 §10.2.7):
    - ``INTERACTION_MATRIX`` (hardcoded prior assumptions — default/fallback)
    - SVAR-estimated coefficients from ``cascade_var.run_svar_pipeline()``

    When SVAR estimates are available, they supersede the hardcoded matrix.
    """

    def __init__(
        self,
        decay_rate: float = 0.1,
        intervention_strength: float = 0.3,
        svar_transmission: Optional[Dict[str, Dict[str, float]]] = None,
        svar_acceleration: Optional["AccelerationFactors"] = None,
    ):
        """Initialize propagation model.

        Args:
            decay_rate: Natural stress decay per period (mean reversion)
            intervention_strength: Effectiveness of policy intervention
            svar_transmission: SVAR-derived transmission dict (drop-in
                replacement for ``INTERACTION_MATRIX``).  If None, falls
                back to the hardcoded prior.
            svar_acceleration: Regime-dependent acceleration factors from
                ``cascade_var.estimate_acceleration_factors()``.
        """
        self.decay_rate = decay_rate
        self.intervention_strength = intervention_strength

        # v6 §10.2.7: SVAR overrides hardcoded matrix when available
        if svar_transmission is not None:
            self.interaction_matrix = svar_transmission
            self._using_svar = True
        else:
            self.interaction_matrix = INTERACTION_MATRIX
            self._using_svar = False

        self.threshold_effects = THRESHOLD_EFFECTS
        self._svar_acceleration = svar_acceleration

    def propagate(
        self,
        initial_pillars: dict[str, float],
        shock_pillar: str,
        shock_magnitude: float,
        periods: int = 20,
        intervention: Optional[InterventionType] = None,
        intervention_period: int = 5,
    ) -> PropagationResult:
        """Propagate shock through time.

        Args:
            initial_pillars: Starting pillar scores
            shock_pillar: Pillar receiving initial shock
            shock_magnitude: Size of initial shock (positive = stress)
            periods: Number of periods to simulate
            intervention: Type of policy intervention (if any)
            intervention_period: Period when intervention occurs

        Returns:
            PropagationResult with full dynamics
        """
        # Initialize paths
        pillar_paths = {p: [v] for p, v in initial_pillars.items()}
        mac_path = [sum(initial_pillars.values()) / len(initial_pillars)]

        current_pillars = initial_pillars.copy()

        # Apply initial shock
        current_pillars[shock_pillar] = max(
            0.0,
            current_pillars[shock_pillar] - shock_magnitude
        )

        cascade_triggered = False
        cascade_period = None
        peak_stress_period = 0
        peak_stress = mac_path[0]
        recovery_started = None
        intervention_applied = None

        for period in range(1, periods + 1):
            new_pillars = {}

            # Check for intervention
            if intervention and period == intervention_period:
                intervention_applied = intervention
                intervention_effect = self._apply_intervention(
                    current_pillars, intervention
                )
                current_pillars = intervention_effect

            for pillar in current_pillars:
                # Start with current value plus natural decay toward 0.5
                current = current_pillars[pillar]
                decay = self.decay_rate * (0.5 - current)

                # Calculate spillover from other pillars
                spillover = 0.0
                for source_pillar, source_score in current_pillars.items():
                    if source_pillar == pillar:
                        continue

                    # Stress level in source (lower score = more stress)
                    source_stress = max(0, 0.5 - source_score)

                    # Base transmission
                    transmission = self.interaction_matrix[source_pillar][pillar]
                    spillover_amount = source_stress * transmission

                    # Apply threshold multiplier if source is breaching
                    if source_pillar in self.threshold_effects:
                        thresh_info = self.threshold_effects[source_pillar]
                        if source_score < thresh_info["threshold"]:
                            spillover_amount *= thresh_info["multiplier"]

                    spillover += spillover_amount

                # Apply threshold effect to receiving pillar
                if pillar in self.threshold_effects:
                    thresh_info = self.threshold_effects[pillar]
                    if current < thresh_info["threshold"]:
                        spillover *= thresh_info["multiplier"]

                # Update pillar
                new_value = current + decay - spillover * 0.1
                new_value = max(0.0, min(1.0, new_value))
                new_pillars[pillar] = new_value

            current_pillars = new_pillars

            # Record paths
            for pillar, value in current_pillars.items():
                pillar_paths[pillar].append(value)

            current_mac = sum(current_pillars.values()) / len(current_pillars)
            mac_path.append(current_mac)

            # Track cascade
            if current_mac < 0.35 and not cascade_triggered:
                cascade_triggered = True
                cascade_period = period

            # Track peak stress
            if current_mac < peak_stress:
                peak_stress = current_mac
                peak_stress_period = period

            # Track recovery
            if recovery_started is None and period > peak_stress_period:
                if current_mac > peak_stress + 0.05:
                    recovery_started = period

        return PropagationResult(
            periods=periods,
            initial_pillars=initial_pillars,
            final_pillars=current_pillars,
            pillar_paths=pillar_paths,
            mac_path=mac_path,
            cascade_triggered=cascade_triggered,
            cascade_period=cascade_period,
            intervention_applied=intervention_applied,
            peak_stress_period=peak_stress_period,
            recovery_started_period=recovery_started,
        )

    def _apply_intervention(
        self,
        pillars: dict[str, float],
        intervention: InterventionType,
    ) -> dict[str, float]:
        """Apply policy intervention effects.

        Args:
            pillars: Current pillar scores
            intervention: Type of intervention

        Returns:
            Updated pillar scores
        """
        result = pillars.copy()
        strength = self.intervention_strength

        if intervention == InterventionType.LIQUIDITY:
            result["liquidity"] = min(1.0, result["liquidity"] + strength * 0.4)
            result["volatility"] = min(1.0, result["volatility"] + strength * 0.2)

        elif intervention == InterventionType.QUANTITATIVE:
            result["liquidity"] = min(1.0, result["liquidity"] + strength * 0.3)
            result["valuation"] = min(1.0, result["valuation"] + strength * 0.3)
            result["volatility"] = min(1.0, result["volatility"] + strength * 0.2)

        elif intervention == InterventionType.RATE_CUT:
            result["policy"] = min(1.0, result["policy"] + strength * 0.4)
            result["volatility"] = min(1.0, result["volatility"] + strength * 0.1)

        elif intervention == InterventionType.COORDINATED:
            # Most powerful - affects all pillars
            for pillar in result:
                result[pillar] = min(1.0, result[pillar] + strength * 0.25)

        return result

    def analyze_cascade_dynamics(
        self,
        n_simulations: int = 100,
    ) -> CascadeAnalysis:
        """Analyze cascade probability under different conditions.

        Args:
            n_simulations: Simulations per condition

        Returns:
            CascadeAnalysis with cascade probabilities
        """
        import random

        # Test cascade probability at different MAC levels
        mac_levels = [0.70, 0.55, 0.45, 0.35, 0.25]
        cascade_by_mac = {}
        severities = []
        channels_triggered = []

        for target_mac in mac_levels:
            cascade_count = 0

            for _ in range(n_simulations):
                # Create pillars averaging to target MAC
                base = target_mac
                pillars = {
                    "liquidity": base + random.uniform(-0.1, 0.1),
                    "valuation": base + random.uniform(-0.05, 0.05),
                    "positioning": base + random.uniform(-0.1, 0.1),
                    "volatility": base + random.uniform(-0.1, 0.1),
                    "policy": base + random.uniform(0, 0.1),
                    "contagion": base + random.uniform(-0.08, 0.08),
                }
                # Normalize to target MAC
                current_mac = sum(pillars.values()) / len(pillars)
                adj = target_mac - current_mac
                pillars = {k: max(0, min(1, v + adj)) for k, v in pillars.items()}

                # Apply moderate shock to liquidity
                result = self.propagate(
                    initial_pillars=pillars,
                    shock_pillar="liquidity",
                    shock_magnitude=0.2,
                    periods=15,
                )

                if result.cascade_triggered:
                    cascade_count += 1
                    severities.append(result.mac_path[result.peak_stress_period])

                    # Track which pillars were most affected
                    for pillar, path in result.pillar_paths.items():
                        if min(path) < 0.2:
                            channels_triggered.append(pillar)

            cascade_by_mac[f"MAC={target_mac:.2f}"] = cascade_count / n_simulations

        # Count primary transmission channels
        channel_counts = {}
        for ch in channels_triggered:
            channel_counts[ch] = channel_counts.get(ch, 0) + 1

        primary_channels = sorted(
            channel_counts.keys(),
            key=lambda x: channel_counts[x],
            reverse=True
        )[:3]

        # Identify stabilizing factors (pillars that rarely breach)
        stabilizing = [p for p in ["policy", "valuation"]
                      if channel_counts.get(p, 0) < len(severities) * 0.2]

        return CascadeAnalysis(
            critical_threshold=0.45,  # MAC level where cascade prob > 50%
            cascade_probability_by_mac=cascade_by_mac,
            mean_cascade_severity=sum(severities) / len(severities) if severities else 0,
            primary_transmission_channels=primary_channels,
            stabilizing_factors=stabilizing,
        )


def format_propagation_result(result: PropagationResult) -> str:
    """Format propagation result for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("SHOCK PROPAGATION ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    # Initial and final state
    lines.append("INITIAL STATE")
    lines.append("-" * 40)
    for pillar, score in result.initial_pillars.items():
        lines.append(f"  {pillar:12}: {score:.3f}")
    lines.append(f"  {'MAC':12}: {result.mac_path[0]:.3f}")
    lines.append("")

    lines.append("FINAL STATE")
    lines.append("-" * 40)
    for pillar, score in result.final_pillars.items():
        change = score - result.initial_pillars[pillar]
        lines.append(f"  {pillar:12}: {score:.3f} ({change:+.3f})")
    lines.append(f"  {'MAC':12}: {result.mac_path[-1]:.3f}")
    lines.append("")

    # Dynamics
    lines.append("DYNAMICS")
    lines.append("-" * 40)
    lines.append(f"  Peak stress period:    {result.peak_stress_period}")
    lines.append(f"  Peak stress MAC:       {min(result.mac_path):.3f}")
    lines.append(f"  Cascade triggered:     {'YES' if result.cascade_triggered else 'No'}")
    if result.cascade_period:
        lines.append(f"  Cascade period:        {result.cascade_period}")
    if result.intervention_applied:
        lines.append(f"  Intervention:          {result.intervention_applied.value}")
    if result.recovery_started_period:
        lines.append(f"  Recovery started:      Period {result.recovery_started_period}")
    lines.append("")

    # MAC path visualization (ASCII)
    lines.append("MAC PATH (ASCII)")
    lines.append("-" * 40)
    max_width = 50
    for i, mac in enumerate(result.mac_path[::2]):  # Every other period
        bar_len = int(mac * max_width)
        bar = "#" * bar_len
        status = ""
        if mac < 0.35:
            status = " [BREACH]"
        elif mac < 0.50:
            status = " [STRETCHED]"
        lines.append(f"  t={i*2:2d} |{bar:<{max_width}}| {mac:.3f}{status}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_cascade_analysis(analysis: CascadeAnalysis) -> str:
    """Format cascade analysis for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("CASCADE DYNAMICS ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    lines.append("CASCADE PROBABILITY BY INITIAL MAC")
    lines.append("-" * 40)
    for mac_level, prob in analysis.cascade_probability_by_mac.items():
        bar_len = int(prob * 40)
        bar = "#" * bar_len
        lines.append(f"  {mac_level}: {bar:<40} {prob:.1%}")
    lines.append("")

    lines.append(f"Critical threshold: MAC < {analysis.critical_threshold}")
    lines.append(f"Mean cascade severity: {analysis.mean_cascade_severity:.3f}")
    lines.append("")

    lines.append("PRIMARY TRANSMISSION CHANNELS")
    lines.append("-" * 40)
    for i, channel in enumerate(analysis.primary_transmission_channels, 1):
        lines.append(f"  {i}. {channel}")
    lines.append("")

    lines.append("STABILIZING FACTORS")
    lines.append("-" * 40)
    for factor in analysis.stabilizing_factors:
        lines.append(f"  - {factor}")
    lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)

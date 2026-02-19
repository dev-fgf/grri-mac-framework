"""Synthetic data augmentation for small-N ML training.

Bootstraps pillar-score vectors from real scenarios with controlled noise
to increase the effective training set size while preserving the signal.

Usage:
    from grri_mac.backtest.augmentation import augment_scenarios
    augmented = augment_scenarios(real_scenarios, noise_pct=0.10, n_augmented=8)
    # effective N ≈ 35 real × 8 = 280 synthetic + 35 real = 315 total
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AugmentationConfig:
    """Configuration for synthetic augmentation."""

    noise_pct: float = 0.10        # ±10% noise on indicator values
    n_augmented: int = 8           # Number of synthetic variants per real scenario
    seed: int = 42                 # Random seed for reproducibility
    preserve_breaches: bool = True  # Keep breach/non-breach status consistent
    min_score: float = 0.0         # Floor for perturbed scores
    max_score: float = 1.0         # Ceiling for perturbed scores
    correlate_noise: bool = True   # Apply correlated noise across indicators


def augment_scenarios(
    scenarios: list[dict],
    config: Optional[AugmentationConfig] = None,
) -> list[dict]:
    """Generate synthetic augmented scenarios from real ones.

    Each real scenario produces `n_augmented` synthetic variants by
    perturbing indicator values with uniform noise in [-noise_pct, +noise_pct],
    preserving cross-indicator correlations within each scenario.

    CSR target scores are preserved (noise only on indicators, not ground truth).

    Args:
        scenarios: List of dicts with keys:
            - "pillar_scores": dict[str, float] mapping pillar names to 0-1 scores
            - "expected_mac": float target MAC score
            - "hedge_failed": bool
            - "scenario_name": str identifier
        config: Augmentation configuration. If None, uses defaults.

    Returns:
        Combined list of (real + synthetic) scenarios, each with an
        additional "is_synthetic" flag and "source_scenario" name.
    """
    if config is None:
        config = AugmentationConfig()

    rng = np.random.default_rng(config.seed)
    augmented = []

    # First, include all real scenarios unchanged
    for scenario in scenarios:
        tagged = deepcopy(scenario)
        tagged["is_synthetic"] = False
        tagged["source_scenario"] = scenario.get("scenario_name", "unknown")
        augmented.append(tagged)

    # Generate synthetic variants
    for scenario in scenarios:
        pillar_scores = scenario.get("pillar_scores", {})
        pillars = sorted(pillar_scores.keys())

        if not pillars:
            continue

        for i in range(config.n_augmented):
            synthetic = deepcopy(scenario)
            synthetic["is_synthetic"] = True
            synthetic["source_scenario"] = scenario.get("scenario_name", "unknown")
            synthetic["augmentation_index"] = i

            if config.correlate_noise:
                # Apply a shared directional noise component (±half the noise)
                # plus independent noise (±half the noise) per pillar.
                # This preserves the correlation structure.
                shared_noise = rng.uniform(
                    -config.noise_pct / 2, config.noise_pct / 2
                )
                for pillar in pillars:
                    base = pillar_scores[pillar]
                    independent_noise = rng.uniform(
                        -config.noise_pct / 2, config.noise_pct / 2
                    )
                    total_noise = shared_noise + independent_noise
                    perturbed = base * (1.0 + total_noise)
                    perturbed = max(config.min_score, min(config.max_score, perturbed))
                    synthetic["pillar_scores"][pillar] = perturbed
            else:
                # Independent noise per pillar
                for pillar in pillars:
                    base = pillar_scores[pillar]
                    noise = rng.uniform(-config.noise_pct, config.noise_pct)
                    perturbed = base * (1.0 + noise)
                    perturbed = max(config.min_score, min(config.max_score, perturbed))
                    synthetic["pillar_scores"][pillar] = perturbed

            # CSR target preserved — do NOT perturb expected_mac or hedge_failed
            augmented.append(synthetic)

    return augmented


def augment_indicator_dicts(
    indicator_dicts: list[dict],
    target_scores: list[float],
    hedge_failed: list[bool],
    scenario_names: list[str],
    config: Optional[AugmentationConfig] = None,
) -> tuple[list[dict], list[float], list[bool], list[str], list[bool]]:
    """Augment raw indicator dictionaries (for use with the ML optimizer).

    This is a convenience wrapper that works directly with the indicator
    dicts and target arrays used by MLWeightOptimizer.

    Args:
        indicator_dicts: List of raw indicator value dicts (one per scenario)
        target_scores: Target MAC scores (CSR midpoints)
        hedge_failed: Hedge failure flags
        scenario_names: Scenario identifiers
        config: Augmentation configuration

    Returns:
        Tuple of (augmented_indicators, augmented_targets, augmented_hedge,
                  augmented_names, is_synthetic_flags)
    """
    if config is None:
        config = AugmentationConfig()

    rng = np.random.default_rng(config.seed)

    aug_indicators = list(indicator_dicts)
    aug_targets = list(target_scores)
    aug_hedge = list(hedge_failed)
    aug_names = list(scenario_names)
    aug_synthetic = [False] * len(indicator_dicts)

    # Numeric indicator keys (skip string/bool values)
    numeric_keys = set()
    for d in indicator_dicts:
        for k, v in d.items():
            if isinstance(v, (int, float)):
                numeric_keys.add(k)

    for idx, (indicators, target, hedge, name) in enumerate(
        zip(indicator_dicts, target_scores, hedge_failed, scenario_names)
    ):
        for i in range(config.n_augmented):
            synthetic = dict(indicators)

            # Apply noise to numeric indicators
            shared_noise = rng.uniform(
                -config.noise_pct / 2, config.noise_pct / 2
            )
            for key in numeric_keys:
                if key in synthetic and isinstance(synthetic[key], (int, float)):
                    base = synthetic[key]
                    independent_noise = rng.uniform(
                        -config.noise_pct / 2, config.noise_pct / 2
                    )
                    total_noise = shared_noise + independent_noise
                    synthetic[key] = base * (1.0 + total_noise)

            aug_indicators.append(synthetic)
            aug_targets.append(target)  # Preserved
            aug_hedge.append(hedge)     # Preserved
            aug_names.append(f"{name}_syn{i}")
            aug_synthetic.append(True)

    return aug_indicators, aug_targets, aug_hedge, aug_names, aug_synthetic

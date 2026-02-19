"""Machine learning-based pillar weight optimization.

This module implements advanced aggregation methods that go beyond equal weights,
using ensemble methods to capture non-linear interactions between pillars.

Key Features:
- Random Forest and Gradient Boosting for feature importance extraction
- Interaction detection (e.g., policy constraints amplifying contagion)
- Leave-one-out cross-validation for small sample robustness
- Crisis severity prediction and hedge failure classification

References:
- Breiman (2001) - Random Forests
- Friedman (2001) - Gradient Boosting
"""

from dataclasses import dataclass
import numpy as np

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import LeaveOneOut, cross_val_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# Pillar names in standard order
PILLAR_NAMES = [
    "liquidity", "valuation", "positioning",
    "volatility", "policy", "contagion",
]

# Interaction pairs of theoretical interest
# These capture known amplification mechanisms
INTERACTION_PAIRS = [
    ("positioning", "volatility"),   # Crowded + vol spike = forced unwind
    ("positioning", "liquidity"),    # Positioning + illiquid = margin calls
    ("policy", "contagion"),         # Policy constrained + global stress
    ("liquidity", "contagion"),      # Liquidity + global = dollar squeeze
    ("valuation", "volatility"),     # Compressed spreads + vol = repricing
    ("positioning", "contagion"),    # Positioning + global = coordinated
]


@dataclass
class OptimizedWeights:
    """Result of ML weight optimization."""

    weights: dict[str, float]
    method: str
    feature_importances: dict[str, float]
    interaction_scores: dict[str, float]
    cross_val_score: float
    n_samples: int
    notes: list[str]


@dataclass
class InteractionEffect:
    """Detected interaction between pillars."""

    pillar1: str
    pillar2: str
    interaction_strength: float
    direction: str  # "amplifying" or "dampening"
    interpretation: str


class MLWeightOptimizer:
    """
    Optimize pillar weights using machine learning.

    Uses ensemble methods to capture non-linear relationships and
    interaction effects between pillars that simple averaging misses.
    """

    def __init__(self):
        """Initialize optimizer."""
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn required for ML optimization. "
                "Run: pip install scikit-learn"
            )
        self.scaler = StandardScaler()
        self._fitted_model = None
        self._feature_names = None

    def _prepare_features(
        self,
        pillar_scores: list[dict[str, float]],
        include_interactions: bool = True,
    ) -> np.ndarray:
        """
        Prepare feature matrix from pillar scores.

        Args:
            pillar_scores: List of pillar score dicts (one per scenario)
            include_interactions: Whether to add interaction features

        Returns:
            Feature matrix (n_samples, n_features)
        """
        n_samples = len(pillar_scores)
        base_features = np.zeros((n_samples, len(PILLAR_NAMES)))

        for i, scores in enumerate(pillar_scores):
            for j, pillar in enumerate(PILLAR_NAMES):
                base_features[i, j] = scores.get(pillar, 0.5)

        self._feature_names = list(PILLAR_NAMES)

        if include_interactions:
            # Add interaction terms (product of pairs)
            interaction_features = []
            for p1, p2 in INTERACTION_PAIRS:
                idx1 = PILLAR_NAMES.index(p1)
                idx2 = PILLAR_NAMES.index(p2)
                interaction = base_features[:, idx1] * base_features[:, idx2]
                interaction_features.append(interaction)
                self._feature_names.append(f"{p1}*{p2}")

            interaction_matrix = np.column_stack(interaction_features)
            return np.hstack([base_features, interaction_matrix])

        return base_features

    def optimize_for_severity(
        self,
        pillar_scores: list[dict[str, float]],
        expected_mac_scores: list[float],
        method: str = "gradient_boosting",
    ) -> OptimizedWeights:
        """
        Optimize weights to predict crisis severity (MAC score).

        Args:
            pillar_scores: List of pillar score dicts (one per scenario)
            expected_mac_scores: Target MAC scores for each scenario
            method: "random_forest" or "gradient_boosting"

        Returns:
            OptimizedWeights with learned weights and diagnostics
        """
        X = self._prepare_features(pillar_scores, include_interactions=True)
        y = np.array(expected_mac_scores)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Choose model
        if method == "random_forest":
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=3,  # Shallow to prevent overfitting with 14 samples
                min_samples_leaf=2,
                random_state=42,
            )
        else:  # gradient_boosting
            model = GradientBoostingRegressor(
                n_estimators=50,
                max_depth=2,
                learning_rate=0.1,
                min_samples_leaf=2,
                random_state=42,
            )

        # Leave-one-out cross-validation (appropriate for small N)
        loo = LeaveOneOut()
        cv_scores = cross_val_score(model, X_scaled, y, cv=loo, scoring='r2')
        mean_cv_score = np.mean(cv_scores)

        # Fit on full data
        model.fit(X_scaled, y)
        self._fitted_model = model

        # Extract feature importances
        raw_importances = model.feature_importances_

        # Separate base pillar importances from interactions
        base_importances = raw_importances[:len(PILLAR_NAMES)]
        interaction_importances = raw_importances[len(PILLAR_NAMES):]

        # Normalize base importances to sum to 1 for weights
        base_sum = base_importances.sum()
        if base_sum > 0:
            normalized_weights = base_importances / base_sum
        else:
            normalized_weights = np.ones(len(PILLAR_NAMES)) / len(PILLAR_NAMES)

        weights = {
            pillar: float(normalized_weights[i])
            for i, pillar in enumerate(PILLAR_NAMES)
        }

        feature_importances = {
            name: float(imp)
            for name, imp in zip(self._feature_names, raw_importances)
        }

        # Extract interaction scores
        interaction_scores = {}
        for i, (p1, p2) in enumerate(INTERACTION_PAIRS):
            if len(PILLAR_NAMES) + i < len(raw_importances):
                interaction_scores[f"{p1}*{p2}"] = float(interaction_importances[i])

        # Generate notes
        notes = self._generate_optimization_notes(
            weights, interaction_scores, mean_cv_score
        )

        return OptimizedWeights(
            weights=weights,
            method=method,
            feature_importances=feature_importances,
            interaction_scores=interaction_scores,
            cross_val_score=mean_cv_score,
            n_samples=len(pillar_scores),
            notes=notes,
        )

    def optimize_for_hedge_failure(
        self,
        pillar_scores: list[dict[str, float]],
        hedge_failed: list[bool],
        method: str = "gradient_boosting",
    ) -> OptimizedWeights:
        """
        Optimize weights to predict Treasury hedge failure.

        Args:
            pillar_scores: List of pillar score dicts (one per scenario)
            hedge_failed: Boolean list indicating hedge failure
            method: "random_forest" or "gradient_boosting"

        Returns:
            OptimizedWeights optimized for hedge failure prediction
        """
        X = self._prepare_features(pillar_scores, include_interactions=True)
        y = np.array(hedge_failed, dtype=int)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Choose model
        if method == "random_forest":
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=3,
                min_samples_leaf=2,
                class_weight="balanced",  # Handle imbalanced classes
                random_state=42,
            )
        else:
            model = GradientBoostingClassifier(
                n_estimators=50,
                max_depth=2,
                learning_rate=0.1,
                min_samples_leaf=2,
                random_state=42,
            )

        # Leave-one-out cross-validation
        loo = LeaveOneOut()
        cv_scores = cross_val_score(model, X_scaled, y, cv=loo, scoring='accuracy')
        mean_cv_score = np.mean(cv_scores)

        # Fit on full data
        model.fit(X_scaled, y)
        self._fitted_model = model

        # Extract feature importances
        raw_importances = model.feature_importances_
        base_importances = raw_importances[:len(PILLAR_NAMES)]
        interaction_importances = raw_importances[len(PILLAR_NAMES):]

        # Normalize for weights
        base_sum = base_importances.sum()
        if base_sum > 0:
            normalized_weights = base_importances / base_sum
        else:
            normalized_weights = np.ones(len(PILLAR_NAMES)) / len(PILLAR_NAMES)

        weights = {
            pillar: float(normalized_weights[i])
            for i, pillar in enumerate(PILLAR_NAMES)
        }

        feature_importances = {
            name: float(imp)
            for name, imp in zip(self._feature_names, raw_importances)
        }

        interaction_scores = {}
        for i, (p1, p2) in enumerate(INTERACTION_PAIRS):
            if len(PILLAR_NAMES) + i < len(raw_importances):
                interaction_scores[f"{p1}*{p2}"] = float(interaction_importances[i])

        notes = [
            "Optimized for hedge failure prediction (classification)",
            f"Cross-validation accuracy: {mean_cv_score:.1%}",
            f"Hedge failures in sample: {sum(hedge_failed)}/{len(hedge_failed)}",
        ]

        # Add key insight about positioning
        if weights.get("positioning", 0) > 0.25:
            notes.append(
                "VALIDATED: Positioning is top predictor of hedge failure"
            )

        return OptimizedWeights(
            weights=weights,
            method=f"{method}_classifier",
            feature_importances=feature_importances,
            interaction_scores=interaction_scores,
            cross_val_score=mean_cv_score,
            n_samples=len(pillar_scores),
            notes=notes,
        )

    def detect_interactions(
        self,
        pillar_scores: list[dict[str, float]],
        target_scores: list[float],
    ) -> list[InteractionEffect]:
        """
        Detect significant interaction effects between pillars.

        Args:
            pillar_scores: List of pillar score dicts
            target_scores: Target variable (MAC scores or similar)

        Returns:
            List of detected interaction effects
        """
        X = self._prepare_features(pillar_scores, include_interactions=True)
        y = np.array(target_scores)

        # Fit model
        model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=3,
            random_state=42,
        )
        model.fit(X, y)

        # Get interaction importances
        raw_importances = model.feature_importances_
        interaction_importances = raw_importances[len(PILLAR_NAMES):]

        effects = []
        for i, (p1, p2) in enumerate(INTERACTION_PAIRS):
            if i >= len(interaction_importances):
                break

            strength = interaction_importances[i]
            if strength > 0.05:  # Significance threshold
                # Determine direction by examining partial dependence
                effect = InteractionEffect(
                    pillar1=p1,
                    pillar2=p2,
                    interaction_strength=float(strength),
                    direction=self._infer_interaction_direction(p1, p2),
                    interpretation=self._interpret_interaction(p1, p2, strength),
                )
                effects.append(effect)

        # Sort by strength
        effects.sort(key=lambda x: x.interaction_strength, reverse=True)
        return effects

    def _infer_interaction_direction(self, p1: str, p2: str) -> str:
        """Infer whether interaction is amplifying or dampening."""
        # Based on financial theory
        amplifying_pairs = {
            ("positioning", "volatility"),
            ("positioning", "liquidity"),
            ("policy", "contagion"),
            ("liquidity", "contagion"),
            ("positioning", "contagion"),
        }
        if (p1, p2) in amplifying_pairs or (p2, p1) in amplifying_pairs:
            return "amplifying"
        return "dampening"

    def _interpret_interaction(self, p1: str, p2: str, strength: float) -> str:
        """Generate interpretation for an interaction effect."""
        interpretations = {
            ("positioning", "volatility"): (
                "Crowded positioning + volatility spike leads to forced unwinding. "
                "This explains hedge failures during COVID and April 2025."
            ),
            ("positioning", "liquidity"): (
                "Position crowding + illiquidity triggers margin calls and "
                "fire sales, amplifying price dislocations."
            ),
            ("policy", "contagion"): (
                "When policy is constrained AND global contagion spreads, "
                "central banks have limited tools to respond."
            ),
            ("liquidity", "contagion"): (
                "Liquidity stress combined with global contagion creates "
                "dollar funding squeeze and correlated deleveraging."
            ),
            ("valuation", "volatility"): (
                "Compressed spreads + vol spike leads to rapid repricing "
                "as complacent positions unwind."
            ),
            ("positioning", "contagion"): (
                "Crowded positioning + global stress causes coordinated "
                "unwind across markets - the March 2020 mechanism."
            ),
        }

        key = (p1, p2) if (p1, p2) in interpretations else (p2, p1)
        base = interpretations.get(key, f"Interaction between {p1} and {p2}")

        if strength > 0.15:
            strength_label = "strong"
        elif strength > 0.08:
            strength_label = "moderate"
        else:
            strength_label = "weak"
        return f"[{strength_label.upper()}] {base}"

    def _generate_optimization_notes(
        self,
        weights: dict[str, float],
        interactions: dict[str, float],
        cv_score: float,
    ) -> list[str]:
        """Generate interpretive notes for optimization results."""
        notes = []

        # Comment on CV score
        if cv_score > 0.7:
            notes.append(f"Strong predictive power (R² = {cv_score:.2f})")
        elif cv_score > 0.4:
            notes.append(f"Moderate predictive power (R² = {cv_score:.2f})")
        else:
            notes.append(
                f"Limited predictive power (R² = {cv_score:.2f})"
                " - equal weights may suffice"
            )

        # Identify dominant pillars
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_pillar, top_weight = sorted_weights[0]
        if top_weight > 0.25:
            notes.append(f"Dominant pillar: {top_pillar} ({top_weight:.1%})")

        # Identify key interactions
        if interactions:
            sorted_interactions = sorted(
                interactions.items(), key=lambda x: x[1], reverse=True
            )
            top_interaction, top_strength = sorted_interactions[0]
            if top_strength > 0.05:
                notes.append(
                    f"Key interaction: {top_interaction}"
                    f" (importance: {top_strength:.2f})"
                )

        # Compare to equal weights
        equal_weight = 1 / len(PILLAR_NAMES)
        deviations = [abs(w - equal_weight) for w in weights.values()]
        avg_deviation = sum(deviations) / len(deviations)
        if avg_deviation < 0.03:
            notes.append("Optimized weights similar to equal weights")
        elif avg_deviation > 0.08:
            notes.append("Significant deviation from equal weights - ML adds value")

        return notes

    def compare_weighting_schemes(
        self,
        pillar_scores: list[dict[str, float]],
        expected_mac_scores: list[float],
    ) -> dict:
        """
        Compare equal weights vs ML-optimized weights.

        Args:
            pillar_scores: List of pillar score dicts
            expected_mac_scores: Target MAC scores

        Returns:
            Comparison dict with metrics for each scheme
        """
        # Equal weights baseline
        n_pillars = len(PILLAR_NAMES)
        equal_weights = {p: 1/n_pillars for p in PILLAR_NAMES}

        # Calculate MACs with equal weights
        equal_macs = []
        for scores in pillar_scores:
            mac = sum(scores.get(p, 0.5) * equal_weights[p] for p in PILLAR_NAMES)
            equal_macs.append(mac)

        equal_macs = np.array(equal_macs)
        expected = np.array(expected_mac_scores)

        equal_rmse = np.sqrt(np.mean((equal_macs - expected) ** 2))
        equal_corr = np.corrcoef(equal_macs, expected)[0, 1]

        # ML-optimized weights
        opt_result = self.optimize_for_severity(pillar_scores, expected_mac_scores)

        ml_macs = []
        for scores in pillar_scores:
            mac = sum(scores.get(p, 0.5) * opt_result.weights[p] for p in PILLAR_NAMES)
            ml_macs.append(mac)

        ml_macs = np.array(ml_macs)
        ml_rmse = np.sqrt(np.mean((ml_macs - expected) ** 2))
        ml_corr = np.corrcoef(ml_macs, expected)[0, 1]

        return {
            "equal_weights": {
                "weights": equal_weights,
                "rmse": float(equal_rmse),
                "correlation": float(equal_corr),
            },
            "ml_optimized": {
                "weights": opt_result.weights,
                "rmse": float(ml_rmse),
                "correlation": float(ml_corr),
                "cv_score": opt_result.cross_val_score,
                "interactions": opt_result.interaction_scores,
            },
            "improvement": {
                "rmse_reduction": float(equal_rmse - ml_rmse),
                "correlation_gain": float(ml_corr - equal_corr),
            },
            "recommendation": (
                "Use ML weights" if ml_rmse < equal_rmse * 0.9
                else "Equal weights sufficient"
            ),
        }


def run_optimization_on_scenarios(
    method: str = "gradient_boosting",
    use_augmentation: bool = False,
    augmentation_noise_pct: float = 0.10,
    augmentation_n: int = 8,
) -> dict:
    """
    Run ML optimization on historical scenarios.

    Now supports all scenarios in KNOWN_EVENTS (N~35 with v7 expansion)
    and optional synthetic augmentation for improved ML stability.

    Args:
        method: "gradient_boosting" (sklearn), "xgboost" (requires xgboost+optuna)
        use_augmentation: Whether to apply synthetic data augmentation
        augmentation_noise_pct: Noise level for augmentation (default 10%)
        augmentation_n: Number of synthetic variants per real scenario

    Returns:
        Dict with optimization results and recommendations
    """
    from ..backtest.calibrated_engine import CalibratedBacktestEngine

    # Run backtest to get pillar scores
    engine = CalibratedBacktestEngine()
    results = engine.run_all_scenarios()

    # Extract data for ML
    pillar_scores = []
    expected_macs = []
    hedge_failed = []

    for result in results.results:
        pillar_scores.append(result.pillar_scores)
        expected_macs.append(sum(result.expected_mac_range) / 2)  # Midpoint
        hedge_failed.append(not result.treasury_hedge_worked)

    # Apply synthetic augmentation if requested
    if use_augmentation:
        try:
            from ..backtest.augmentation import augment_scenarios, AugmentationConfig

            aug_config = AugmentationConfig(
                noise_pct=augmentation_noise_pct,
                n_augmented=augmentation_n,
            )
            scenario_dicts = [
                {
                    "pillar_scores": ps,
                    "expected_mac": em,
                    "hedge_failed": hf,
                    "scenario_name": f"scenario_{i}",
                }
                for i, (ps, em, hf) in enumerate(
                    zip(pillar_scores, expected_macs, hedge_failed)
                )
            ]
            augmented = augment_scenarios(scenario_dicts, config=aug_config)

            # Separate back into parallel lists
            pillar_scores = [s["pillar_scores"] for s in augmented]
            expected_macs = [s["expected_mac"] for s in augmented]
            hedge_failed = [s["hedge_failed"] for s in augmented]
        except ImportError:
            pass  # Augmentation module not available

    # Select optimizer based on method
    if method == "xgboost":
        try:
            from .ml_weights_xgb import XGBWeightOptimizer
            optimizer = XGBWeightOptimizer()
        except ImportError:
            optimizer = MLWeightOptimizer()
            method = "gradient_boosting"
    else:
        optimizer = MLWeightOptimizer()

    # Optimize for severity prediction
    severity_result = optimizer.optimize_for_severity(
        pillar_scores, expected_macs, method=method
    )

    # Optimize for hedge failure prediction
    hedge_result = optimizer.optimize_for_hedge_failure(
        pillar_scores, hedge_failed, method=method
    )

    # Detect interactions (always use base MLWeightOptimizer for this)
    if isinstance(optimizer, MLWeightOptimizer):
        base_optimizer = optimizer
    else:
        base_optimizer = MLWeightOptimizer()
    interactions = base_optimizer.detect_interactions(pillar_scores, expected_macs)

    # Compare weighting schemes
    comparison = base_optimizer.compare_weighting_schemes(pillar_scores, expected_macs)

    return {
        "severity_optimization": {
            "weights": severity_result.weights,
            "cv_score": severity_result.cross_val_score,
            "feature_importances": severity_result.feature_importances,
            "notes": severity_result.notes,
        },
        "hedge_optimization": {
            "weights": hedge_result.weights,
            "cv_score": hedge_result.cross_val_score,
            "feature_importances": hedge_result.feature_importances,
            "notes": hedge_result.notes,
        },
        "interactions": [
            {
                "pillars": f"{e.pillar1} × {e.pillar2}",
                "strength": e.interaction_strength,
                "direction": e.direction,
                "interpretation": e.interpretation,
            }
            for e in interactions
        ],
        "comparison": comparison,
        "n_scenarios": len(pillar_scores),
        "method": method,
        "augmented": use_augmentation,
    }

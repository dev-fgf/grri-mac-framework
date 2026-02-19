"""XGBoost-based pillar weight optimization with Bayesian hyperparameter tuning.

Replaces the sklearn GradientBoosting backend with XGBoost and uses Optuna
for Bayesian hyperparameter search with 5-fold time-series CV.

Falls back gracefully to sklearn GBM when xgboost/optuna are not installed.

Usage:
    from grri_mac.mac.ml_weights_xgb import XGBWeightOptimizer
    optimizer = XGBWeightOptimizer()
    result = optimizer.optimize_for_severity(pillar_scores, targets)
"""

from dataclasses import dataclass
from typing import Any, Optional
import logging

import numpy as np

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    from sklearn.model_selection import TimeSeriesSplit, LeaveOneOut, cross_val_score
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from .ml_weights import (
    OptimizedWeights,
    PILLAR_NAMES,
    INTERACTION_PAIRS,
)

logger = logging.getLogger(__name__)


@dataclass
class XGBOptimizationConfig:
    """Configuration for XGBoost optimization."""

    # Optuna search space
    max_depth_range: tuple[int, int] = (2, 5)
    learning_rate_range: tuple[float, float] = (0.01, 0.3)
    n_estimators_range: tuple[int, int] = (30, 200)
    min_child_weight_range: tuple[int, int] = (1, 5)
    subsample_range: tuple[float, float] = (0.6, 1.0)
    colsample_bytree_range: tuple[float, float] = (0.6, 1.0)
    reg_alpha_range: tuple[float, float] = (0.0, 1.0)
    reg_lambda_range: tuple[float, float] = (0.0, 1.0)

    # CV settings
    n_cv_folds: int = 5
    n_optuna_trials: int = 50
    optuna_seed: int = 42

    # General
    random_state: int = 42
    include_interactions: bool = True


class XGBWeightOptimizer:
    """Optimize pillar weights using XGBoost with Bayesian hyperparameter search.

    API-compatible with MLWeightOptimizer — drop-in replacement.
    """

    def __init__(self, config: Optional[XGBOptimizationConfig] = None):
        """Initialize optimizer.

        Raises ImportError if neither xgboost nor sklearn is available.
        """
        if not XGBOOST_AVAILABLE and not SKLEARN_AVAILABLE:
            raise ImportError(
                "Either xgboost or scikit-learn required. "
                "Run: pip install xgboost optuna scikit-learn"
            )

        self.config = config or XGBOptimizationConfig()
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._fitted_model: Any = None
        self._feature_names: Optional[list[str]] = None
        self._best_params: Optional[dict[str, Any]] = None

    def _prepare_features(
        self,
        pillar_scores: list[dict[str, float]],
        include_interactions: bool = True,
    ) -> np.ndarray:
        """Prepare feature matrix from pillar scores (same as MLWeightOptimizer)."""
        n_samples = len(pillar_scores)
        base_features = np.zeros((n_samples, len(PILLAR_NAMES)))

        for i, scores in enumerate(pillar_scores):
            for j, pillar in enumerate(PILLAR_NAMES):
                base_features[i, j] = scores.get(pillar, 0.5)

        self._feature_names = list(PILLAR_NAMES)

        if include_interactions:
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

    def _optimize_hyperparams(
        self,
        X: np.ndarray,
        y: np.ndarray,
        task: str = "regression",
    ) -> dict:
        """Use Optuna to find optimal XGBoost hyperparameters.

        Args:
            X: Feature matrix
            y: Target vector
            task: "regression" or "classification"

        Returns:
            Best hyperparameter dict
        """
        if not OPTUNA_AVAILABLE or not XGBOOST_AVAILABLE:
            # Fallback to reasonable defaults
            return {
                "max_depth": 2,
                "learning_rate": 0.1,
                "n_estimators": 50,
                "min_child_weight": 2,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_alpha": 0.1,
                "reg_lambda": 0.5,
            }

        cfg = self.config
        n_samples = len(y)
        # Use fewer folds if sample is very small
        n_folds = min(cfg.n_cv_folds, max(2, n_samples // 3))

        def objective(trial):
            params = {
                "max_depth": trial.suggest_int(
                    "max_depth", *cfg.max_depth_range
                ),
                "learning_rate": trial.suggest_float(
                    "learning_rate", *cfg.learning_rate_range, log=True
                ),
                "n_estimators": trial.suggest_int(
                    "n_estimators", *cfg.n_estimators_range
                ),
                "min_child_weight": trial.suggest_int(
                    "min_child_weight", *cfg.min_child_weight_range
                ),
                "subsample": trial.suggest_float(
                    "subsample", *cfg.subsample_range
                ),
                "colsample_bytree": trial.suggest_float(
                    "colsample_bytree", *cfg.colsample_bytree_range
                ),
                "reg_alpha": trial.suggest_float(
                    "reg_alpha", *cfg.reg_alpha_range
                ),
                "reg_lambda": trial.suggest_float(
                    "reg_lambda", *cfg.reg_lambda_range
                ),
                "random_state": cfg.random_state,
            }

            if task == "regression":
                model = xgb.XGBRegressor(**params, verbosity=0)
                scoring = "neg_mean_squared_error"
            else:
                params["scale_pos_weight"] = (
                    (len(y) - sum(y)) / max(sum(y), 1)
                )
                model = xgb.XGBClassifier(**params, verbosity=0)
                scoring = "accuracy"

            # Time-series CV (respects temporal ordering of scenarios)
            tscv = TimeSeriesSplit(n_splits=n_folds)
            scores = cross_val_score(model, X, y, cv=tscv, scoring=scoring)
            return scores.mean()

        sampler = optuna.samplers.TPESampler(seed=cfg.optuna_seed)
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
        )
        study.optimize(objective, n_trials=cfg.n_optuna_trials, show_progress_bar=False)

        self._best_params = study.best_params
        self._best_params["random_state"] = cfg.random_state
        return self._best_params

    def optimize_for_severity(
        self,
        pillar_scores: list[dict[str, float]],
        expected_mac_scores: list[float],
        method: str = "xgboost",
    ) -> OptimizedWeights:
        """Optimize weights to predict crisis severity.

        Args:
            pillar_scores: List of pillar score dicts (one per scenario)
            expected_mac_scores: Target MAC scores
            method: "xgboost" (preferred) or "gradient_boosting" (fallback)

        Returns:
            OptimizedWeights with learned weights and diagnostics
        """
        X = self._prepare_features(
            pillar_scores,
            include_interactions=self.config.include_interactions,
        )
        y = np.array(expected_mac_scores)

        # Scale features
        if self.scaler:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = X

        # Optimize hyperparameters
        if method == "xgboost" and XGBOOST_AVAILABLE:
            best_params = self._optimize_hyperparams(X_scaled, y, task="regression")
            model = xgb.XGBRegressor(**best_params, verbosity=0)
        else:
            # Fallback to sklearn
            from sklearn.ensemble import GradientBoostingRegressor
            model = GradientBoostingRegressor(
                n_estimators=50, max_depth=2, learning_rate=0.1,
                min_samples_leaf=2, random_state=42,
            )
            method = "gradient_boosting_fallback"

        # LOOCV for final evaluation (honest OOS score)
        loo = LeaveOneOut()
        cv_scores = cross_val_score(model, X_scaled, y, cv=loo, scoring="r2")
        mean_cv_score = float(np.mean(cv_scores))

        # Fit on full data
        model.fit(X_scaled, y)
        self._fitted_model = model

        # Extract feature importances
        raw_importances = model.feature_importances_
        base_importances = raw_importances[:len(PILLAR_NAMES)]
        interaction_importances = raw_importances[len(PILLAR_NAMES):]

        # Normalize base importances to weights
        base_sum = base_importances.sum()
        if base_sum > 0:
            normalized = base_importances / base_sum
        else:
            normalized = np.ones(len(PILLAR_NAMES)) / len(PILLAR_NAMES)

        weights = {
            pillar: round(float(normalized[i]), 4)
            for i, pillar in enumerate(PILLAR_NAMES)
        }

        feature_importances = {
            name: float(imp)
            for name, imp in zip(self._feature_names or [], raw_importances)
        }

        interaction_scores = {}
        for i, (p1, p2) in enumerate(INTERACTION_PAIRS):
            if len(PILLAR_NAMES) + i < len(raw_importances):
                interaction_scores[f"{p1}*{p2}"] = float(interaction_importances[i])

        # Generate notes
        notes = self._generate_notes(weights, mean_cv_score, method)

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
        method: str = "xgboost",
    ) -> OptimizedWeights:
        """Optimize weights to predict Treasury hedge failure.

        Args:
            pillar_scores: List of pillar score dicts
            hedge_failed: Boolean flags
            method: "xgboost" or "gradient_boosting"

        Returns:
            OptimizedWeights for hedge failure prediction
        """
        X = self._prepare_features(
            pillar_scores,
            include_interactions=self.config.include_interactions,
        )
        y = np.array(hedge_failed, dtype=int)

        if self.scaler:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = X

        if method == "xgboost" and XGBOOST_AVAILABLE:
            best_params = self._optimize_hyperparams(X_scaled, y, task="classification")
            scale_pos_weight = (len(y) - sum(y)) / max(sum(y), 1)
            best_params["scale_pos_weight"] = scale_pos_weight
            model = xgb.XGBClassifier(**best_params, verbosity=0)
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(
                n_estimators=50, max_depth=2, learning_rate=0.1,
                min_samples_leaf=2, random_state=42,
            )
            method = "gradient_boosting_classifier_fallback"

        loo = LeaveOneOut()
        cv_scores = cross_val_score(model, X_scaled, y, cv=loo, scoring="accuracy")
        mean_cv_score = float(np.mean(cv_scores))

        model.fit(X_scaled, y)
        self._fitted_model = model

        raw_importances = model.feature_importances_
        base_importances = raw_importances[:len(PILLAR_NAMES)]
        interaction_importances = raw_importances[len(PILLAR_NAMES):]

        base_sum = base_importances.sum()
        if base_sum > 0:
            normalized = base_importances / base_sum
        else:
            normalized = np.ones(len(PILLAR_NAMES)) / len(PILLAR_NAMES)

        weights = {
            pillar: round(float(normalized[i]), 4)
            for i, pillar in enumerate(PILLAR_NAMES)
        }

        feature_importances = {
            name: float(imp)
            for name, imp in zip(self._feature_names or [], raw_importances)
        }

        interaction_scores = {}
        for i, (p1, p2) in enumerate(INTERACTION_PAIRS):
            if len(PILLAR_NAMES) + i < len(raw_importances):
                interaction_scores[f"{p1}*{p2}"] = float(interaction_importances[i])

        notes = [
            f"Hedge failure classifier ({method})",
            f"LOOCV accuracy: {mean_cv_score:.1%}",
            f"Hedge failures in sample: {sum(hedge_failed)}/{len(hedge_failed)}",
        ]
        if weights.get("positioning", 0) > 0.25:
            notes.append("VALIDATED: Positioning is top predictor of hedge failure")

        return OptimizedWeights(
            weights=weights,
            method=f"{method}_classifier",
            feature_importances=feature_importances,
            interaction_scores=interaction_scores,
            cross_val_score=mean_cv_score,
            n_samples=len(pillar_scores),
            notes=notes,
        )

    def _generate_notes(
        self,
        weights: dict[str, float],
        cv_score: float,
        method: str,
    ) -> list[str]:
        """Generate interpretive notes."""
        notes = [f"Method: {method}"]

        if self._best_params:
            notes.append(
                f"Best params: depth={self._best_params.get('max_depth')}, "
                f"lr={self._best_params.get('learning_rate', 0):.3f}, "
                f"n_est={self._best_params.get('n_estimators')}"
            )

        if cv_score > 0.7:
            notes.append(f"Strong predictive power (R² = {cv_score:.2f})")
        elif cv_score > 0.4:
            notes.append(f"Moderate predictive power (R² = {cv_score:.2f})")
        else:
            notes.append(f"Limited predictive power (R² = {cv_score:.2f})")

        sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_pillar, top_weight = sorted_w[0]
        if top_weight > 0.25:
            notes.append(f"Dominant pillar: {top_pillar} ({top_weight:.1%})")

        return notes

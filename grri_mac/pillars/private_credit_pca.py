"""5-factor rolling PCA decorrelation for private credit pillar.

Replaces the 3-factor OLS (SPX, dVIX, dHY_OAS) with a 5-factor
rolling PCA that extracts orthogonal components from:
  (SPX, dVIX, dHY_OAS, dMOVE, dXCCY_basis)

The residuals from regressing BDC returns on the top 3 PCs are
the decorrelated private-credit-specific signal.

Falls back to 3-factor OLS when insufficient data or numpy-only env.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class PCADecorrelationResult:
    """Result of PCA-based decorrelation."""

    decorrelated_score: float
    raw_score: float
    explained_variance_ratios: list[float] = field(
        default_factory=list
    )
    n_components_used: int = 3
    r_squared: float = 0.0
    residual_std: float = 0.0
    method: str = "pca"  # "pca" or "ols_fallback"
    data_quality: str = "good"


class RollingPCADecorrelator:
    """5-factor rolling PCA decorrelator for private credit.

    Methodology:
    1. Collect 5 factor time series over a rolling window
    2. Standardize and compute PCA
    3. Keep top 3 orthogonal components
    4. Regress BDC returns on these 3 PCs
    5. Use residuals as decorrelated signal

    The key advantage over OLS: PCA produces orthogonal factors,
    eliminating the collinearity between VIX, HY OAS, and MOVE
    that contaminates the 3-factor OLS residuals.
    """

    def __init__(
        self,
        window: int = 252,
        n_components: int = 3,
        min_observations: int = 60,
    ):
        """Initialize PCA decorrelator.

        Args:
            window: Rolling window in trading days (default 252 = 1Y)
            n_components: Number of principal components to retain
            min_observations: Minimum data points for valid PCA
        """
        self.window = window
        self.n_components = n_components
        self.min_observations = min_observations

    def decorrelate(
        self,
        bdc_returns: list[float],
        spx_returns: list[float],
        vix_changes: list[float],
        hy_oas_changes: list[float],
        move_changes: Optional[list[float]] = None,
        xccy_basis_changes: Optional[list[float]] = None,
    ) -> PCADecorrelationResult:
        """Run PCA decorrelation on the most recent window.

        Args:
            bdc_returns: BDC weighted index returns
            spx_returns: S&P 500 daily returns
            vix_changes: Daily VIX level changes
            hy_oas_changes: Daily HY OAS changes
            move_changes: Daily MOVE index changes (optional)
            xccy_basis_changes: Daily cross-currency basis changes
                (optional)

        Returns:
            PCADecorrelationResult with decorrelated score
        """
        # Determine available factors
        factors = [spx_returns, vix_changes, hy_oas_changes]
        factor_names = ["SPX", "dVIX", "dHY_OAS"]

        if move_changes and len(move_changes) >= self.min_observations:
            factors.append(move_changes)
            factor_names.append("dMOVE")
        if (
            xccy_basis_changes
            and len(xccy_basis_changes) >= self.min_observations
        ):
            factors.append(xccy_basis_changes)
            factor_names.append("dXCCY")

        # Align lengths
        min_len = min(len(f) for f in factors)
        min_len = min(min_len, len(bdc_returns))

        if min_len < self.min_observations:
            return PCADecorrelationResult(
                decorrelated_score=np.mean(bdc_returns[-20:])
                if len(bdc_returns) >= 20
                else 0.5,
                raw_score=0.5,
                method="insufficient_data",
                data_quality="insufficient",
            )

        # Use rolling window
        window = min(self.window, min_len)
        y = np.array(bdc_returns[-window:])
        X = np.column_stack(
            [np.array(f[-window:]) for f in factors]
        )

        # Standardize factors
        X_mean = X.mean(axis=0)
        X_std = X.std(axis=0)
        X_std[X_std == 0] = 1.0  # Avoid division by zero
        X_standardized = (X - X_mean) / X_std

        # PCA via SVD
        try:
            U, S, Vt = np.linalg.svd(
                X_standardized, full_matrices=False
            )
            total_var = np.sum(S ** 2)
            explained_ratios = (S ** 2 / total_var).tolist()

            # Keep top n_components
            n_comp = min(self.n_components, len(S))
            pc_scores = X_standardized @ Vt[:n_comp].T

            # Regress BDC returns on PCs
            # y = pc_scores @ beta + residual
            # beta = (pc_scores.T @ pc_scores)^-1 @ pc_scores.T @ y
            gram = pc_scores.T @ pc_scores
            if np.linalg.det(gram) < 1e-10:
                # Near-singular, fall back to OLS
                return self._ols_fallback(y, X)

            beta = np.linalg.solve(gram, pc_scores.T @ y)
            y_hat = pc_scores @ beta
            residuals = y - y_hat

            # R-squared
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

            # Decorrelated score: map residual to 0-1
            # Positive residual = private credit doing worse
            # than common factors explain
            recent_residual = float(residuals[-1])
            residual_std = float(np.std(residuals))

            # Score: center at 0.5, penalise negative residuals
            # (stress beyond what common factors explain)
            if residual_std > 0:
                z_score = recent_residual / residual_std
                # Map z-score to 0-1 via sigmoid-like transform
                score = 1.0 / (1.0 + np.exp(-z_score))
            else:
                score = 0.5

            return PCADecorrelationResult(
                decorrelated_score=float(np.clip(score, 0.0, 1.0)),
                raw_score=float(np.mean(y[-5:])),
                explained_variance_ratios=explained_ratios[:n_comp],
                n_components_used=n_comp,
                r_squared=float(r_squared),
                residual_std=float(residual_std),
                method="pca",
                data_quality="good",
            )

        except np.linalg.LinAlgError:
            return self._ols_fallback(y, X)

    def _ols_fallback(
        self, y: np.ndarray, X: np.ndarray
    ) -> PCADecorrelationResult:
        """Fall back to simple 3-factor OLS when PCA fails."""
        try:
            # Use first 3 factors only
            X3 = X[:, :3] if X.shape[1] > 3 else X
            X_with_intercept = np.column_stack(
                [np.ones(len(X3)), X3]
            )
            beta = np.linalg.lstsq(
                X_with_intercept, y, rcond=None
            )[0]
            y_hat = X_with_intercept @ beta
            residuals = y - y_hat

            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

            recent_resid = float(residuals[-1])
            resid_std = float(np.std(residuals))

            if resid_std > 0:
                z = recent_resid / resid_std
                score = 1.0 / (1.0 + np.exp(-z))
            else:
                score = 0.5

            return PCADecorrelationResult(
                decorrelated_score=float(np.clip(score, 0.0, 1.0)),
                raw_score=float(np.mean(y[-5:])),
                r_squared=float(r2),
                residual_std=float(resid_std),
                method="ols_fallback",
                data_quality="degraded",
            )
        except Exception:
            return PCADecorrelationResult(
                decorrelated_score=0.5,
                raw_score=0.5,
                method="failed",
                data_quality="failed",
            )

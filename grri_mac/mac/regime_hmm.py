"""Regime-switching MAC via Hidden Markov Model (v7 §4.2).

Overlays a 2-state HMM ("normal" / "fragile") on the
7-pillar observation vector. This provides:

1. Posterior P(fragile) — probability of being in fragile regime
2. Transition matrix — how likely regime switches are
3. Viterbi path — most likely regime sequence

The HMM is an OVERLAY on the existing MAC — it does not
replace the score, but provides additional regime context.

Dependencies (optional):
  - hmmlearn (for Gaussian HMM)
  - Falls back to a simple threshold-based classifier

Usage:
    from grri_mac.mac.regime_hmm import RegimeHMM
    hmm = RegimeHMM()
    hmm.fit(historical_pillar_scores)
    result = hmm.predict(current_pillar_scores)
    print(f"P(fragile) = {result.fragile_prob:.2f}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try to import hmmlearn
_HMM_AVAILABLE = None
try:
    from hmmlearn.hmm import GaussianHMM
    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False
    logger.info(
        "hmmlearn not installed. RegimeHMM will use "
        "threshold-based fallback."
    )


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class RegimeResult:
    """Result of HMM regime classification."""

    fragile_prob: float  # P(fragile state)
    regime: str  # "normal" or "fragile"
    transition_matrix: Optional[List[List[float]]] = None
    state_means: Optional[Dict[str, List[float]]] = None
    viterbi_path: Optional[List[int]] = None
    log_likelihood: Optional[float] = None
    method: str = "hmm"  # "hmm" or "threshold_fallback"
    n_training_obs: int = 0


@dataclass
class RegimeHMMConfig:
    """Configuration for HMM regime model."""

    n_states: int = 2  # 2 states: normal, fragile
    covariance_type: str = "full"  # "full", "diag", "spherical"
    n_iter: int = 100  # EM iterations
    random_state: int = 42

    # Pillar order for observation vector
    pillar_order: List[str] = field(default_factory=lambda: [
        "liquidity", "valuation", "positioning",
        "volatility", "policy", "contagion",
        "private_credit",
    ])

    # Fragile state identification:
    # The state with lower mean MAC is "fragile"
    fragile_threshold: float = 0.50

    # Minimum observations for fitting
    min_observations: int = 52  # ~1 year


# ── HMM model ───────────────────────────────────────────────────────────

class RegimeHMM:
    """2-state Hidden Markov Model for regime detection.

    States:
    - State 0 / State 1: assigned post-fitting based on
      which has lower mean pillar scores ("fragile")

    Observation:
    - 7-dimensional vector of pillar scores (0-1 each)

    The HMM captures temporal persistence of regimes
    (fragile states tend to cluster) and the joint
    distribution of pillar scores in each regime.
    """

    def __init__(
        self,
        config: Optional[RegimeHMMConfig] = None,
    ):
        self.config = config or RegimeHMMConfig()
        self._model: Any = None
        self._fragile_state_idx: Optional[int] = None
        self._fitted = False

    def fit(
        self,
        pillar_scores_history: List[Dict[str, float]],
    ) -> bool:
        """Fit HMM on historical pillar score vectors.

        Args:
            pillar_scores_history: List of dicts, each mapping
                pillar name to score (0-1). Most recent last.

        Returns:
            True if fitting succeeded.
        """
        cfg = self.config

        if len(pillar_scores_history) < cfg.min_observations:
            logger.warning(
                "Insufficient data for HMM: %d < %d",
                len(pillar_scores_history),
                cfg.min_observations,
            )
            return False

        # Convert to numpy array
        X = self._to_array(pillar_scores_history)
        if X is None:
            return False

        if _HMM_AVAILABLE:
            return self._fit_hmmlearn(X)
        else:
            return self._fit_threshold(X)

    def predict(
        self,
        current_pillar_scores: Dict[str, float],
        recent_history: Optional[
            List[Dict[str, float]]
        ] = None,
    ) -> RegimeResult:
        """Predict current regime.

        Args:
            current_pillar_scores: Current pillar scores.
            recent_history: Optional recent history for
                Viterbi path (last N weeks).

        Returns:
            RegimeResult with fragile probability.
        """
        if not self._fitted:
            # Fallback: simple threshold
            return self._predict_threshold(
                current_pillar_scores,
            )

        if _HMM_AVAILABLE and self._model is not None:
            return self._predict_hmmlearn(
                current_pillar_scores, recent_history,
            )

        return self._predict_threshold(current_pillar_scores)

    def _to_array(
        self,
        pillar_scores_list: List[Dict[str, float]],
    ) -> Optional[np.ndarray]:
        """Convert list of pillar score dicts to numpy array."""
        cfg = self.config
        rows = []
        for ps in pillar_scores_list:
            row = [ps.get(p, 0.5) for p in cfg.pillar_order]
            rows.append(row)

        arr = np.array(rows, dtype=np.float64)

        # Check for degenerate data
        if arr.std() < 1e-6:
            logger.warning("Pillar scores have near-zero variance")
            return None

        return arr

    def _fit_hmmlearn(self, X: np.ndarray) -> bool:
        """Fit using hmmlearn GaussianHMM."""
        cfg = self.config

        try:
            model = GaussianHMM(
                n_components=cfg.n_states,
                covariance_type=cfg.covariance_type,
                n_iter=cfg.n_iter,
                random_state=cfg.random_state,
            )
            model.fit(X)
            self._model = model

            # Identify fragile state: lower mean across pillars
            state_means = model.means_  # (n_states, n_features)
            mean_per_state = state_means.mean(axis=1)
            self._fragile_state_idx = int(
                np.argmin(mean_per_state)
            )

            self._fitted = True
            logger.info(
                "HMM fitted: fragile state=%d, "
                "fragile_mean=%.3f, normal_mean=%.3f",
                self._fragile_state_idx,
                mean_per_state[self._fragile_state_idx],
                mean_per_state[1 - self._fragile_state_idx],
            )
            return True

        except Exception as e:
            logger.warning("HMM fitting failed: %s", e)
            return self._fit_threshold(X)

    def _fit_threshold(self, X: np.ndarray) -> bool:
        """Simple threshold-based fallback fitting."""
        self.config

        # Compute mean MAC per observation
        mean_mac = X.mean(axis=1)

        # Store statistics for threshold prediction
        self._threshold_mean = float(mean_mac.mean())
        self._threshold_std = float(mean_mac.std())
        self._fragile_state_idx = 0

        self._fitted = True
        return True

    def _predict_hmmlearn(
        self,
        current: Dict[str, float],
        recent: Optional[List[Dict[str, float]]],
    ) -> RegimeResult:
        """Predict using fitted hmmlearn model."""
        cfg = self.config

        # Build observation sequence
        if recent:
            obs_list = recent + [current]
        else:
            obs_list = [current]

        X = self._to_array(obs_list)
        if X is None:
            return self._predict_threshold(current)

        try:
            # Get state posteriors
            log_prob, posteriors = self._model.score_samples(X)

            # Current observation posteriors
            current_posterior = posteriors[-1]
            fragile_prob = float(
                current_posterior[self._fragile_state_idx]
            )

            # Viterbi path
            _, viterbi = self._model.decode(X)

            # Get transition matrix
            trans = self._model.transmat_.tolist()

            # State means
            state_means = {}
            for i in range(cfg.n_states):
                label = (
                    "fragile" if i == self._fragile_state_idx
                    else "normal"
                )
                state_means[label] = (
                    self._model.means_[i].tolist()
                )

            regime = (
                "fragile" if fragile_prob > 0.5
                else "normal"
            )

            return RegimeResult(
                fragile_prob=fragile_prob,
                regime=regime,
                transition_matrix=trans,
                state_means=state_means,
                viterbi_path=viterbi.tolist(),
                log_likelihood=float(log_prob),
                method="hmm",
                n_training_obs=self._model.n_features_in_
                if hasattr(self._model, "n_features_in_")
                else 0,
            )

        except Exception as e:
            logger.warning("HMM prediction failed: %s", e)
            return self._predict_threshold(current)

    def _predict_threshold(
        self,
        current: Dict[str, float],
    ) -> RegimeResult:
        """Simple threshold-based regime prediction."""
        cfg = self.config

        # Mean of current pillar scores
        scores = [
            current.get(p, 0.5) for p in cfg.pillar_order
        ]
        mean_score = np.mean(scores)

        # Simple sigmoid mapping
        if hasattr(self, "_threshold_mean"):
            z = (
                (mean_score - self._threshold_mean)
                / max(self._threshold_std, 0.01)
            )
            # P(fragile) is higher when score is low
            fragile_prob = float(
                1.0 / (1.0 + np.exp(z))
            )
        else:
            # No fitted params: use raw threshold
            if mean_score < cfg.fragile_threshold:
                fragile_prob = float(0.7 + 0.3 * (
                    cfg.fragile_threshold - mean_score
                ) / cfg.fragile_threshold)
            else:
                fragile_prob = float(0.3 * (
                    1.0 - mean_score
                ) / (1.0 - cfg.fragile_threshold))

        fragile_prob = float(np.clip(fragile_prob, 0.0, 1.0))
        regime = "fragile" if fragile_prob > 0.5 else "normal"

        return RegimeResult(
            fragile_prob=fragile_prob,
            regime=regime,
            method="threshold_fallback",
        )

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def transition_matrix(self) -> Optional[np.ndarray]:
        if self._model is not None and hasattr(
            self._model, "transmat_"
        ):
            return self._model.transmat_
        return None

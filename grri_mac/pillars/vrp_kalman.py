"""Kalman filter state-space model for Volatility Risk Premium.

Replaces the simple linear VRP_t = 1.05 + 0.015 × σ(vol-of-vol)
with a state-space model that:
1. Treats VRP as a latent state following a random walk
2. Uses vol-of-vol, skew, and kurtosis as measurement inputs
3. Borrows strength from neighbouring periods for smoother estimates

Falls back to the linear formula when filterpy/pykalman unavailable.
"""

from dataclasses import dataclass
from typing import Optional
import math

import numpy as np

# Try filterpy first (lighter), then pykalman
_KALMAN_BACKEND = None
try:
    from filterpy.kalman import KalmanFilter as FilterpyKF
    _KALMAN_BACKEND = "filterpy"
except ImportError:
    try:
        from pykalman import KalmanFilter as PykalmanKF
        _KALMAN_BACKEND = "pykalman"
    except ImportError:
        pass

# Linear fallback constants
VRP_BASE = 1.05
VRP_SENSITIVITY = 0.015
VRP_FLOOR = 1.05
VRP_CEILING = 1.55


@dataclass
class KalmanVRPResult:
    """Result of Kalman-filtered VRP estimation."""

    vrp_estimate: float
    vrp_std: float           # Posterior uncertainty
    smoothed: bool           # Whether Kalman smoothing was applied
    vol_of_vol: Optional[float] = None
    skew: Optional[float] = None
    kurtosis: Optional[float] = None
    method: str = "kalman"   # "kalman" or "linear_fallback"
    n_observations: int = 0


class KalmanVRPEstimator:
    """State-space VRP estimator using Kalman filter.

    State equation:   VRP_t = VRP_{t-1} + w_t,  w_t ~ N(0, Q)
    Observation eq:   z_t = H × VRP_t + v_t,    v_t ~ N(0, R)

    Where z_t is the observed VRP proxy constructed from:
    - σ(vol-of-vol) — primary signal
    - skew of returns — VRP rises with negative skew
    - excess kurtosis — fat tails amplify risk premium

    The Kalman filter optimally combines the noisy observations
    with the random-walk prior, producing smoother estimates
    that borrow strength across time.
    """

    def __init__(
        self,
        process_noise: float = 0.001,
        measurement_noise: float = 0.01,
        initial_vrp: float = 1.10,
        initial_uncertainty: float = 0.05,
    ):
        """Initialize Kalman VRP estimator.

        Args:
            process_noise: Q — how much VRP can change per step
            measurement_noise: R — how noisy the proxy observations are
            initial_vrp: Prior mean for VRP
            initial_uncertainty: Prior std for VRP
        """
        self.Q = process_noise
        self.R = measurement_noise
        self.initial_vrp = initial_vrp
        self.initial_P = initial_uncertainty ** 2

    def estimate(
        self,
        vix_history: list[float],
        returns_history: Optional[list[float]] = None,
        lookback: int = 252,
    ) -> KalmanVRPResult:
        """Estimate current VRP using Kalman filter.

        Args:
            vix_history: VIX levels (most recent last)
            returns_history: Daily returns for skew/kurtosis
                (optional, enhances estimate)
            lookback: Window for computing input statistics

        Returns:
            KalmanVRPResult with filtered VRP estimate
        """
        if not vix_history or len(vix_history) < 20:
            return self._linear_fallback(vix_history)

        # Compute observation inputs
        recent_vix = (
            vix_history[-lookback:]
            if len(vix_history) > lookback
            else vix_history
        )

        # 1. Vol-of-vol
        changes = [
            recent_vix[i] - recent_vix[i - 1]
            for i in range(1, len(recent_vix))
        ]
        vol_of_vol = float(np.std(changes)) if changes else 1.0

        # 2. Skew of VIX changes (optional enhancement)
        skew = None
        if len(changes) > 30:
            arr = np.array(changes)
            mean_c = arr.mean()
            std_c = arr.std()
            if std_c > 0:
                skew = float(
                    np.mean(((arr - mean_c) / std_c) ** 3)
                )

        # 3. Kurtosis of returns (optional enhancement)
        kurtosis = None
        if returns_history and len(returns_history) > 30:
            ret_arr = np.array(
                returns_history[-lookback:]
                if len(returns_history) > lookback
                else returns_history
            )
            mean_r = ret_arr.mean()
            std_r = ret_arr.std()
            if std_r > 0:
                kurtosis = float(
                    np.mean(((ret_arr - mean_r) / std_r) ** 4)
                    - 3.0
                )

        # Construct observation series
        # Map inputs to VRP proxy observations
        observations = self._construct_observations(
            recent_vix, skew, kurtosis
        )

        if not observations:
            return self._linear_fallback(vix_history)

        # Run Kalman filter
        if _KALMAN_BACKEND == "filterpy":
            vrp, vrp_std = self._run_filterpy(observations)
        elif _KALMAN_BACKEND == "pykalman":
            vrp, vrp_std = self._run_pykalman(observations)
        else:
            return self._linear_fallback(vix_history)

        # Clip to valid range
        vrp = max(VRP_FLOOR, min(VRP_CEILING, vrp))

        return KalmanVRPResult(
            vrp_estimate=vrp,
            vrp_std=vrp_std,
            smoothed=True,
            vol_of_vol=vol_of_vol,
            skew=skew,
            kurtosis=kurtosis,
            method="kalman",
            n_observations=len(observations),
        )

    def _construct_observations(
        self,
        vix_history: list[float],
        skew: Optional[float],
        kurtosis: Optional[float],
    ) -> list[float]:
        """Convert raw inputs to VRP proxy observations.

        Uses rolling windows to create a time series of VRP proxies.
        """
        if len(vix_history) < 30:
            return []

        window = 21  # ~1 month rolling
        observations = []

        for i in range(window, len(vix_history)):
            segment = vix_history[i - window:i]
            changes = [
                segment[j] - segment[j - 1]
                for j in range(1, len(segment))
            ]
            local_vov = np.std(changes) if changes else 0.0

            # Base VRP proxy
            proxy = VRP_BASE + VRP_SENSITIVITY * local_vov

            # Skew adjustment (if available, apply to last obs)
            if skew is not None and i == len(vix_history) - 1:
                # Negative skew → higher VRP
                proxy += max(0, -skew) * 0.02

            # Kurtosis adjustment
            if kurtosis is not None and i == len(vix_history) - 1:
                # Excess kurtosis → higher VRP
                proxy += max(0, kurtosis) * 0.01

            observations.append(
                float(max(VRP_FLOOR, min(VRP_CEILING, proxy)))
            )

        return observations

    def _run_filterpy(
        self, observations: list[float]
    ) -> tuple[float, float]:
        """Run Kalman filter using filterpy."""
        kf = FilterpyKF(dim_x=1, dim_z=1)
        kf.x = np.array([[self.initial_vrp]])
        kf.P = np.array([[self.initial_P]])
        kf.F = np.array([[1.0]])  # State transition (random walk)
        kf.H = np.array([[1.0]])  # Observation model
        kf.Q = np.array([[self.Q]])
        kf.R = np.array([[self.R]])

        for z in observations:
            kf.predict()
            kf.update(np.array([[z]]))

        return float(kf.x[0, 0]), float(math.sqrt(kf.P[0, 0]))

    def _run_pykalman(
        self, observations: list[float]
    ) -> tuple[float, float]:
        """Run Kalman filter using pykalman."""
        kf = PykalmanKF(
            transition_matrices=np.array([[1.0]]),
            observation_matrices=np.array([[1.0]]),
            transition_covariance=np.array([[self.Q]]),
            observation_covariance=np.array([[self.R]]),
            initial_state_mean=np.array([self.initial_vrp]),
            initial_state_covariance=np.array(
                [[self.initial_P]]
            ),
        )

        obs = np.array(observations).reshape(-1, 1)
        filtered_means, filtered_covs = kf.filter(obs)

        vrp = float(filtered_means[-1, 0])
        vrp_std = float(math.sqrt(filtered_covs[-1, 0, 0]))
        return vrp, vrp_std

    def _linear_fallback(
        self, vix_history: Optional[list[float]]
    ) -> KalmanVRPResult:
        """Fall back to linear VRP formula."""
        if not vix_history or len(vix_history) < 20:
            return KalmanVRPResult(
                vrp_estimate=VRP_BASE,
                vrp_std=0.10,
                smoothed=False,
                method="linear_fallback",
            )

        changes = [
            vix_history[i] - vix_history[i - 1]
            for i in range(1, len(vix_history))
        ]
        vol_of_vol = float(np.std(changes[-252:]))
        raw_vrp = VRP_BASE + VRP_SENSITIVITY * vol_of_vol
        vrp = max(VRP_FLOOR, min(VRP_CEILING, raw_vrp))

        return KalmanVRPResult(
            vrp_estimate=vrp,
            vrp_std=0.05,  # Rough estimate
            smoothed=False,
            vol_of_vol=vol_of_vol,
            method="linear_fallback",
            n_observations=len(changes),
        )

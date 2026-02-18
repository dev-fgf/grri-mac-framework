"""Private Credit Decorrelation Engine (v6 §4.7.1–4.7.8).

Extracts the private-credit-specific stress signal by orthogonalising
raw BDC/leveraged-loan returns against common equity/credit factors.

Pipeline:
  1. Rolling 252-day OLS: raw_return_t ~ β₁·SPX_t + β₂·ΔVIX_t + β₃·ΔHY_OAS_t + ε_t
  2. Residual ε_t is the orthogonal (private-credit-specific) signal
  3. Standardise: z_t = ε_t / σ(ε)_{rolling}
  4. 12-week EWMA smoothing (λ = 0.154)
  5. Score on σ-unit thresholds

Validation cases (v6 §4.7.7):
  COVID 2020:   raw −22% → decorrelated −1.3σ
  Late 2022:    raw −8%  → decorrelated −1.8σ
  Q4 2018:      raw −12% → decorrelated −0.4σ  (equity-driven, benign PC)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────
OLS_WINDOW = 252          # Rolling OLS lookback (trading days ≈ 1 year)
EWMA_LAMBDA = 0.154       # 12-week half-life EWMA decay factor
EWMA_SPAN_DAYS = 60       # 12 weeks ≈ 60 trading days
MIN_OLS_OBS = 63          # Minimum observations for OLS (1 quarter)

# σ-unit scoring thresholds (v6 §4.7.5)
THRESHOLD_NORMAL = -0.5   # > −0.5σ → normal
THRESHOLD_ELEVATED = -1.5  # −0.5σ to −1.5σ → elevated
THRESHOLD_SEVERE = -2.0    # < −2.0σ → severe

# Composite blend (v6 §4.7.6)
DECORR_WEIGHT = 0.60      # Weight on decorrelated signal
SLOOS_WEIGHT = 0.40       # Weight retained on SLOOS


@dataclass
class DecorrelationResult:
    """Result of the decorrelation pipeline for a single date."""

    raw_return: Optional[float] = None          # Raw BDC composite return
    residual: Optional[float] = None            # OLS residual (ε_t)
    z_score: Optional[float] = None             # Standardised residual
    ewma_z: Optional[float] = None              # EWMA-smoothed z-score
    decorrelated_score: Optional[float] = None  # Score on [0, 1]
    data_quality: str = "insufficient"          # "good", "partial", "insufficient"
    r_squared: Optional[float] = None           # OLS R² for diagnostics
    beta_spx: Optional[float] = None
    beta_vix: Optional[float] = None
    beta_hy_oas: Optional[float] = None


@dataclass
class DecorrelationTimeSeries:
    """Holds the rolling arrays needed for the pipeline."""

    # Parallel arrays, same length, most recent last
    bdc_returns: list = field(default_factory=list)   # Raw BDC composite daily returns
    spx_returns: list = field(default_factory=list)   # S&P 500 daily returns
    vix_changes: list = field(default_factory=list)    # ΔVIX daily changes
    hy_oas_changes: list = field(default_factory=list) # ΔHY OAS daily changes

    # Cached EWMA state
    _ewma_z: Optional[float] = None


class PrivateCreditDecorrelator:
    """Rolling OLS decorrelation engine for private credit signals."""

    def __init__(
        self,
        ols_window: int = OLS_WINDOW,
        ewma_lambda: float = EWMA_LAMBDA,
        min_obs: int = MIN_OLS_OBS,
    ):
        self.ols_window = ols_window
        self.ewma_lambda = ewma_lambda
        self.min_obs = min_obs

    def fit_ols(
        self,
        y: list[float],
        X: list[list[float]],
    ) -> tuple[list[float], list[float], float]:
        """Fit OLS regression y ~ X using normal equations (numpy-free).

        Args:
            y: Dependent variable (length N)
            X: Independent variables (N × K, no intercept column yet)

        Returns:
            Tuple of (betas [K+1], residuals [N], R²)
        """
        n = len(y)
        k = len(X[0]) if X else 0

        if n < self.min_obs or k == 0:
            return [], list(y), 0.0

        # Add intercept column
        X_aug = [[1.0] + row for row in X]
        k_aug = k + 1

        # X'X
        XtX = [[0.0] * k_aug for _ in range(k_aug)]
        for i in range(k_aug):
            for j in range(k_aug):
                XtX[i][j] = sum(X_aug[r][i] * X_aug[r][j] for r in range(n))

        # X'y
        Xty = [sum(X_aug[r][i] * y[r] for r in range(n)) for i in range(k_aug)]

        # Solve via Cholesky (small k, numerically adequate)
        betas = self._solve_cholesky(XtX, Xty)
        if betas is None:
            # Fallback: return zero betas, residuals = y
            return [0.0] * k_aug, list(y), 0.0

        # Residuals
        residuals = [
            y[r] - sum(betas[i] * X_aug[r][i] for i in range(k_aug))
            for r in range(n)
        ]

        # R²
        y_mean = sum(y) / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum(r ** 2 for r in residuals)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return betas, residuals, max(0.0, r_squared)

    @staticmethod
    def _solve_cholesky(
        A: list[list[float]], b: list[float],
    ) -> Optional[list[float]]:
        """Solve Ax = b via Cholesky decomposition for SPD matrix A."""
        n = len(b)
        L = [[0.0] * n for _ in range(n)]

        # Decompose A = LL'
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    val = A[i][i] - s
                    if val <= 0:
                        return None  # Not positive definite
                    L[i][j] = math.sqrt(val)
                else:
                    if L[j][j] == 0:
                        return None
                    L[i][j] = (A[i][j] - s) / L[j][j]

        # Forward substitution: Ly = b
        y = [0.0] * n
        for i in range(n):
            y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]

        # Back substitution: L'x = y
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            x[i] = (y[i] - sum(L[j][i] * x[j] for j in range(i + 1, n))) / L[i][i]

        return x

    def decorrelate(
        self,
        ts: DecorrelationTimeSeries,
    ) -> DecorrelationResult:
        """Run the full decorrelation pipeline on current data.

        Args:
            ts: Time series data with aligned parallel arrays

        Returns:
            DecorrelationResult for the most recent observation
        """
        result = DecorrelationResult()
        n = len(ts.bdc_returns)

        if n < self.min_obs:
            result.data_quality = "insufficient"
            return result

        # Use last ols_window observations
        window = min(n, self.ols_window)
        y = ts.bdc_returns[-window:]
        X = [
            [
                ts.spx_returns[-window + i],
                ts.vix_changes[-window + i],
                ts.hy_oas_changes[-window + i],
            ]
            for i in range(window)
        ]

        result.raw_return = y[-1] if y else None

        # ── Step 1: Rolling OLS ──────────────────────────────────────
        betas, residuals, r_sq = self.fit_ols(y, X)
        result.r_squared = r_sq

        if betas and len(betas) >= 4:
            result.beta_spx = betas[1]
            result.beta_vix = betas[2]
            result.beta_hy_oas = betas[3]

        if not residuals:
            result.data_quality = "insufficient"
            return result

        result.residual = residuals[-1]

        # ── Step 2: Standardise residuals ────────────────────────────
        resid_mean = sum(residuals) / len(residuals)
        resid_var = sum((r - resid_mean) ** 2 for r in residuals) / (
            len(residuals) - 1
        )
        resid_std = math.sqrt(resid_var) if resid_var > 0 else 1.0

        z_scores = [(r - resid_mean) / resid_std for r in residuals]
        result.z_score = z_scores[-1]

        # ── Step 3: EWMA smoothing ──────────────────────────────────
        # λ = 0.154, applied to z-scores
        ewma = z_scores[0]
        for z in z_scores[1:]:
            ewma = self.ewma_lambda * z + (1.0 - self.ewma_lambda) * ewma
        result.ewma_z = ewma

        # ── Step 4: Score on σ-unit thresholds ──────────────────────
        result.decorrelated_score = self._score_z(ewma)

        # Data quality assessment
        if window >= self.ols_window:
            result.data_quality = "good"
        elif window >= self.ols_window // 2:
            result.data_quality = "partial"
        else:
            result.data_quality = "insufficient"

        return result

    @staticmethod
    def _score_z(z: float) -> float:
        """Convert EWMA z-score to [0, 1] score using v6 thresholds.

        Thresholds (v6 §4.7.5):
          > −0.5σ  → Normal   (score 0.7–1.0)
          −0.5 to −1.5σ → Elevated (score 0.3–0.7)
          −1.5 to −2.0σ → Severe   (score 0.1–0.3)
          < −2.0σ  → Extreme  (score 0.0–0.1)
        """
        if z > 0:
            # Above mean — positive territory
            return min(1.0, 0.8 + 0.2 * min(z, 1.0))
        elif z > THRESHOLD_NORMAL:
            # −0.5 to 0: transition from 0.7 to 0.8
            return 0.7 + 0.1 * (z - THRESHOLD_NORMAL) / (0.0 - THRESHOLD_NORMAL)
        elif z > THRESHOLD_ELEVATED:
            # −1.5 to −0.5: transition from 0.3 to 0.7
            return 0.3 + 0.4 * (z - THRESHOLD_ELEVATED) / (
                THRESHOLD_NORMAL - THRESHOLD_ELEVATED
            )
        elif z > THRESHOLD_SEVERE:
            # −2.0 to −1.5: transition from 0.1 to 0.3
            return 0.1 + 0.2 * (z - THRESHOLD_SEVERE) / (
                THRESHOLD_ELEVATED - THRESHOLD_SEVERE
            )
        else:
            # Below −2.0σ: extreme
            return max(0.0, 0.1 + 0.1 * (z - THRESHOLD_SEVERE))


def blend_decorrelated_with_sloos(
    decorr_score: Optional[float],
    sloos_score: float,
    decorr_quality: str = "good",
) -> float:
    """Blend decorrelated signal with SLOOS per v6 §4.7.6.

    Composite = 60% decorrelated + 40% SLOOS
    Falls back to 100% SLOOS if decorrelation data insufficient.

    Args:
        decorr_score: Score from decorrelation engine (0-1)
        sloos_score: Score from SLOOS analysis (0-1)
        decorr_quality: Data quality flag from decorrelation

    Returns:
        Blended composite score (0-1)
    """
    if decorr_score is None or decorr_quality == "insufficient":
        return sloos_score

    if decorr_quality == "partial":
        # Reduce decorrelation weight when data is partial
        return 0.40 * decorr_score + 0.60 * sloos_score

    return DECORR_WEIGHT * decorr_score + SLOOS_WEIGHT * sloos_score

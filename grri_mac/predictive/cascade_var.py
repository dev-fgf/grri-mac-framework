"""SVAR-Based Cascade Propagation Estimation (v6 §10.2).

Estimates the pillar-to-pillar transmission matrix from a Structural VAR on
weekly pillar-score time series, replacing the previously hard-coded
``INTERACTION_MATRIX`` in ``shock_propagation.py``.

Key components:
* BIC-selected lag order (L ∈ {1, 2, 3, 4})
* Cholesky identification with theory-motivated ordering
* Robustness across all 720 ordering permutations (median + 10/90 pct bounds)
* Generalised Impulse Response Functions (GIRFs, Pesaran & Shin 1998)
* Cumulative IRF extraction at h = 4 weeks → normalised transmission matrix
* Regime-dependent acceleration factors (normal vs stress sub-samples)
* Granger-causality tests
* Out-of-sample validation
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Constants from v6 §10.2
# ---------------------------------------------------------------------------

# Cholesky ordering (slow → fast): v6 §10.2.2
CHOLESKY_ORDERING: List[str] = [
    "policy",       # slowest – FOMC schedule
    "valuation",    # credit spreads adjust over days/weeks
    "contagion",    # cross-border operates with a lag
    "liquidity",    # funding markets respond within days
    "volatility",   # reprices continuously
    "positioning",  # fastest – margin calls within hours
]

LAG_CANDIDATES = [1, 2, 3, 4]
CIRF_HORIZON = 4  # 4-week cumulative impulse response
ESTIMATION_START_YEAR = 1997
ESTIMATION_END_YEAR = 2025

# Critical thresholds for regime-dependent acceleration (v6 §10.2.5)
CRITICAL_THRESHOLDS: Dict[str, float] = {
    "liquidity": 0.30,
    "positioning": 0.25,
    "volatility": 0.20,
    "contagion": 0.30,
    "valuation": 0.25,
    "policy": 0.20,
}

MAC_STRESS_THRESHOLD = 0.50  # MAC ≤ 0.50 → stress regime


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SVAREstimate:
    """Result of a single SVAR estimation."""
    lag_order: int
    bic: float
    coefficient_matrices: List[np.ndarray]     # A_1 … A_L (each 6×6)
    residual_covariance: np.ndarray            # Σ (6×6)
    ordering: List[str]
    cirf_matrix: np.ndarray                    # 6×6 cumulative IRF at h=4
    transmission_matrix: np.ndarray            # normalised to [-1, 1]
    pillar_names: List[str]


@dataclass
class RobustnessResult:
    """Robustness check across all ordering permutations."""
    median_cirf: np.ndarray          # 6×6
    pct10_cirf: np.ndarray           # 6×6
    pct90_cirf: np.ndarray           # 6×6
    girf_matrix: np.ndarray          # 6×6  ordering-invariant
    n_permutations_tested: int


@dataclass
class AccelerationFactors:
    """Regime-dependent acceleration factors (v6 §10.2.5)."""
    normal_matrix: np.ndarray        # 6×6 transmission (MAC > 0.50)
    stress_matrix: np.ndarray        # 6×6 transmission (MAC ≤ 0.50)
    acceleration: np.ndarray         # element-wise |stress|/|normal|
    pillar_names: List[str]


@dataclass
class GrangerResult:
    """Granger-causality test result for one pillar pair."""
    cause: str
    effect: str
    f_statistic: float
    p_value: float
    significant: bool  # at 5% level


@dataclass
class OOSValidation:
    """Out-of-sample cascade prediction validation."""
    scenario_name: str
    predicted_pillars: Dict[str, float]
    actual_pillars: Dict[str, float]
    mae: float


@dataclass
class CascadeVARReport:
    """Complete SVAR estimation report."""
    primary_estimate: SVAREstimate
    robustness: Optional[RobustnessResult]
    acceleration: Optional[AccelerationFactors]
    granger_tests: List[GrangerResult]
    oos_validations: List[OOSValidation]
    transmission_dict: Dict[str, Dict[str, float]]  # readable nested dict


# ---------------------------------------------------------------------------
# Helper: simple VAR estimation (numpy-only, no statsmodels dependency)
# ---------------------------------------------------------------------------

def _build_var_matrices(
    data: np.ndarray,     # T × K
    lag_order: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build design matrix (Y, X) for a VAR(p) estimation.

    Args:
        data: T × K array of observations.
        lag_order: Number of lags (p).

    Returns:
        Y: (T-p) × K  response matrix
        X: (T-p) × (K*p + 1)  design matrix (with intercept as last column)
    """
    T, K = data.shape
    Y = data[lag_order:]  # (T-p) × K
    X_parts = []
    for lag in range(1, lag_order + 1):
        X_parts.append(data[lag_order - lag : T - lag])  # (T-p) × K
    X = np.hstack(X_parts)  # (T-p) × (K*p)
    # Add constant
    X = np.hstack([X, np.ones((T - lag_order, 1))])
    return Y, X


def estimate_var(
    data: np.ndarray,
    lag_order: int,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Estimate reduced-form VAR(p) via OLS.

    Args:
        data: T × K array (first-differenced pillar scores).
        lag_order: p.

    Returns:
        B: (K*p+1) × K coefficient matrix
        Sigma: K × K residual covariance
        bic: BIC value
    """
    T, K = data.shape
    Y, X = _build_var_matrices(data, lag_order)
    n = Y.shape[0]  # effective observations

    # OLS: B = (X'X)^{-1} X'Y
    XtX = X.T @ X
    # Regularise for numerical stability
    XtX += np.eye(XtX.shape[0]) * 1e-8
    B = np.linalg.solve(XtX, X.T @ Y)  # (K*p+1) × K

    residuals = Y - X @ B
    Sigma = (residuals.T @ residuals) / n

    # BIC = n * ln|Σ| + (K^2 * p + K) * ln(n)
    sign, logdet = np.linalg.slogdet(Sigma)
    if sign <= 0:
        logdet = 1e6  # degenerate
    n_params = K * K * lag_order + K  # including intercepts
    bic = n * logdet + n_params * math.log(n)

    return B, Sigma, bic


def select_lag_order(
    data: np.ndarray,
    candidates: List[int] = None,
) -> Tuple[int, float]:
    """Select optimal lag order by BIC.

    Returns:
        (best_lag, best_bic)
    """
    if candidates is None:
        candidates = LAG_CANDIDATES
    best_lag = candidates[0]
    best_bic = float("inf")
    for lag in candidates:
        if lag >= data.shape[0] - 10:
            continue  # not enough data
        _, _, bic = estimate_var(data, lag)
        if bic < best_bic:
            best_bic = bic
            best_lag = lag
    return best_lag, best_bic


# ---------------------------------------------------------------------------
# IRF computation
# ---------------------------------------------------------------------------

def _extract_coefficient_matrices(
    B: np.ndarray,
    K: int,
    lag_order: int,
) -> List[np.ndarray]:
    """Extract A_1 … A_p from the stacked coefficient matrix B."""
    matrices = []
    for i in range(lag_order):
        A_i = B[i * K : (i + 1) * K, :].T  # K × K  (note transpose: B is X cols × K)
        matrices.append(A_i)
    return matrices


def compute_irf(
    A_matrices: List[np.ndarray],
    Sigma: np.ndarray,
    ordering: List[str],
    pillar_names: List[str],
    horizon: int = CIRF_HORIZON,
) -> np.ndarray:
    """Compute Cholesky-identified cumulative impulse responses at horizon h.

    Args:
        A_matrices: List of K×K coefficient matrices [A_1, …, A_p].
        Sigma: K×K residual covariance.
        ordering: Cholesky ordering (list of pillar names).
        pillar_names: Original pillar name order in data.
        horizon: Cumulative horizon.

    Returns:
        CIRF: K×K matrix where CIRF[i,j] = cumulative response of pillar i
        to a 1-SD structural shock to pillar j, over *horizon* periods.
    """
    K = Sigma.shape[0]
    p = len(A_matrices)

    # Reorder to match Cholesky ordering
    idx = [pillar_names.index(name) for name in ordering]
    A_reordered = [A[np.ix_(idx, idx)] for A in A_matrices]
    Sigma_reordered = Sigma[np.ix_(idx, idx)]

    # Cholesky decomposition: lower triangular
    try:
        P = np.linalg.cholesky(Sigma_reordered)
    except np.linalg.LinAlgError:
        # Fall back: add tiny diagonal
        P = np.linalg.cholesky(Sigma_reordered + np.eye(K) * 1e-8)

    # Compute structural MA representation: Φ_0 = P, Φ_s from recursion
    Phi = [P.copy()]  # Φ_0 = P
    for s in range(1, horizon + 1):
        Phi_s = np.zeros((K, K))
        for j in range(min(s, p)):
            Phi_s += A_reordered[j] @ Phi[s - 1 - j]
        Phi.append(Phi_s)

    # Cumulative IRF: sum Φ_0 … Φ_h
    CIRF = np.zeros((K, K))
    for Phi_s in Phi:
        CIRF += Phi_s

    # Map back to original ordering
    inv_idx = [ordering.index(name) for name in pillar_names]
    CIRF_orig = CIRF[np.ix_(inv_idx, inv_idx)]

    return CIRF_orig


def compute_girf(
    A_matrices: List[np.ndarray],
    Sigma: np.ndarray,
    horizon: int = CIRF_HORIZON,
) -> np.ndarray:
    """Compute Generalised IRFs (Pesaran & Shin 1998) — ordering-invariant.

    GIRF_{ij}(h) = cumulative response of variable i to a shock in variable j,
    integrating over the distribution of other shocks.

    Returns:
        K×K GIRF matrix.
    """
    K = Sigma.shape[0]

    # Compute MA coefficients (reduced form)
    p = len(A_matrices)
    Psi = [np.eye(K)]  # Ψ_0 = I
    for s in range(1, horizon + 1):
        Psi_s = np.zeros((K, K))
        for j in range(min(s, p)):
            Psi_s += A_matrices[j] @ Psi[s - 1 - j]
        Psi.append(Psi_s)

    # Cumulative MA: C(h) = Σ_{s=0}^{h} Ψ_s
    C = np.zeros((K, K))
    for Psi_s in Psi:
        C += Psi_s

    # GIRF: scale by σ_jj^{-1/2} * Σ column j
    GIRF = np.zeros((K, K))
    for j in range(K):
        sigma_jj = Sigma[j, j]
        if sigma_jj > 0:
            GIRF[:, j] = C @ Sigma[:, j] / math.sqrt(sigma_jj)

    return GIRF


def normalise_matrix(M: np.ndarray) -> np.ndarray:
    """Normalise a matrix to [-1, 1] range."""
    max_abs = np.max(np.abs(M))
    if max_abs > 0:
        return M / max_abs
    return M.copy()


# ---------------------------------------------------------------------------
# Full SVAR estimation pipeline
# ---------------------------------------------------------------------------

def estimate_svar(
    pillar_series: Dict[str, List[float]],
    *,
    pillar_names: Optional[List[str]] = None,
    ordering: Optional[List[str]] = None,
    lag_candidates: Optional[List[int]] = None,
) -> SVAREstimate:
    """Run the full SVAR estimation pipeline.

    Args:
        pillar_series: Dict mapping pillar name → weekly score time series.
            All series must have the same length.
        pillar_names: Override pillar order (default: CHOLESKY_ORDERING).
        ordering: Cholesky identification ordering.
        lag_candidates: Lag orders to test (default: [1,2,3,4]).

    Returns:
        SVAREstimate with transmission coefficients.
    """
    if pillar_names is None:
        pillar_names = [p for p in CHOLESKY_ORDERING if p in pillar_series]
    if ordering is None:
        ordering = CHOLESKY_ORDERING
    if lag_candidates is None:
        lag_candidates = LAG_CANDIDATES

    K = len(pillar_names)
    T = len(next(iter(pillar_series.values())))

    # Stack into T × K array
    raw = np.column_stack([np.array(pillar_series[p]) for p in pillar_names])

    # First-difference (ΔP_t)
    diff = np.diff(raw, axis=0)  # (T-1) × K

    # Select lag order
    best_lag, best_bic = select_lag_order(diff, lag_candidates)

    # Estimate VAR
    B, Sigma, _ = estimate_var(diff, best_lag)
    A_matrices = _extract_coefficient_matrices(B, K, best_lag)

    # Compute CIRF
    cirf = compute_irf(A_matrices, Sigma, ordering, pillar_names)
    transmission = normalise_matrix(cirf)

    return SVAREstimate(
        lag_order=best_lag,
        bic=best_bic,
        coefficient_matrices=A_matrices,
        residual_covariance=Sigma,
        ordering=ordering,
        cirf_matrix=cirf,
        transmission_matrix=transmission,
        pillar_names=pillar_names,
    )


# ---------------------------------------------------------------------------
# Robustness: all 720 orderings
# ---------------------------------------------------------------------------

def robustness_all_orderings(
    pillar_series: Dict[str, List[float]],
    *,
    lag_order: Optional[int] = None,
    max_permutations: int = 720,
) -> RobustnessResult:
    """Test all permutations of the 6-pillar Cholesky ordering.

    Reports median CIRF with 10th/90th percentile bounds, plus GIRFs
    as an ordering-invariant cross-check.

    Args:
        pillar_series: Same as ``estimate_svar``.
        lag_order: If None, selected by BIC first.
        max_permutations: Cap (720 = 6!).

    Returns:
        RobustnessResult.
    """
    pillar_names = [p for p in CHOLESKY_ORDERING if p in pillar_series]
    K = len(pillar_names)

    # Prepare data
    raw = np.column_stack([np.array(pillar_series[p]) for p in pillar_names])
    diff = np.diff(raw, axis=0)

    if lag_order is None:
        lag_order, _ = select_lag_order(diff)

    B, Sigma, _ = estimate_var(diff, lag_order)
    A_matrices = _extract_coefficient_matrices(B, K, lag_order)

    # Collect CIRFs across all permutations
    all_perms = list(itertools.permutations(pillar_names))
    if len(all_perms) > max_permutations:
        all_perms = all_perms[:max_permutations]

    cirf_stack = []
    for perm in all_perms:
        cirf = compute_irf(A_matrices, Sigma, list(perm), pillar_names)
        cirf_stack.append(cirf)

    cirf_array = np.array(cirf_stack)  # N × K × K

    median_cirf = np.median(cirf_array, axis=0)
    pct10 = np.percentile(cirf_array, 10, axis=0)
    pct90 = np.percentile(cirf_array, 90, axis=0)

    # GIRF (ordering-invariant)
    girf = compute_girf(A_matrices, Sigma)

    return RobustnessResult(
        median_cirf=median_cirf,
        pct10_cirf=pct10,
        pct90_cirf=pct90,
        girf_matrix=girf,
        n_permutations_tested=len(all_perms),
    )


# ---------------------------------------------------------------------------
# Regime-dependent acceleration (v6 §10.2.5)
# ---------------------------------------------------------------------------

def estimate_acceleration_factors(
    pillar_series: Dict[str, List[float]],
    mac_series: List[float],
    *,
    ordering: Optional[List[str]] = None,
) -> AccelerationFactors:
    """Estimate acceleration factors from normal vs stress sub-samples.

    Args:
        pillar_series: Pillar score time series (weekly).
        mac_series: Composite MAC time series (same length).
        ordering: Cholesky ordering.

    Returns:
        AccelerationFactors with normal, stress, and ratio matrices.
    """
    pillar_names = [p for p in CHOLESKY_ORDERING if p in pillar_series]
    if ordering is None:
        ordering = CHOLESKY_ORDERING

    raw = np.column_stack([np.array(pillar_series[p]) for p in pillar_names])
    mac = np.array(mac_series)
    diff = np.diff(raw, axis=0)
    mac_aligned = mac[1:]  # align with first-differenced data

    # Split into normal / stress
    normal_mask = mac_aligned > MAC_STRESS_THRESHOLD
    stress_mask = ~normal_mask

    def _safe_estimate(mask: np.ndarray) -> np.ndarray:
        sub = diff[mask]
        if sub.shape[0] < 30:
            # Not enough data — return zeros
            return np.zeros((len(pillar_names), len(pillar_names)))
        lag, _ = select_lag_order(sub)
        B, Sigma, _ = estimate_var(sub, lag)
        K = len(pillar_names)
        A_mats = _extract_coefficient_matrices(B, K, lag)
        cirf = compute_irf(A_mats, Sigma, ordering, pillar_names)
        return normalise_matrix(cirf)

    normal_mat = _safe_estimate(normal_mask)
    stress_mat = _safe_estimate(stress_mask)

    # Acceleration = |stress| / |normal|  (element-wise; cap at 5×)
    with np.errstate(divide="ignore", invalid="ignore"):
        accel = np.where(
            np.abs(normal_mat) > 1e-6,
            np.abs(stress_mat) / np.abs(normal_mat),
            1.0,
        )
    accel = np.clip(accel, 0.0, 5.0)

    return AccelerationFactors(
        normal_matrix=normal_mat,
        stress_matrix=stress_mat,
        acceleration=accel,
        pillar_names=pillar_names,
    )


# ---------------------------------------------------------------------------
# Granger-causality tests
# ---------------------------------------------------------------------------

def granger_causality_tests(
    pillar_series: Dict[str, List[float]],
    lag_order: Optional[int] = None,
    significance: float = 0.05,
) -> List[GrangerResult]:
    """Bivariate Granger-causality tests for all pillar pairs.

    Uses a simple F-test comparing restricted (univariate AR) vs unrestricted
    (bivariate VAR) model for each directional pair.

    Returns:
        List of GrangerResult (one per directed pair, 30 total for 6 pillars).
    """
    pillar_names = [p for p in CHOLESKY_ORDERING if p in pillar_series]
    raw = {p: np.diff(np.array(pillar_series[p])) for p in pillar_names}
    results: List[GrangerResult] = []

    for cause in pillar_names:
        for effect in pillar_names:
            if cause == effect:
                continue
            y = raw[effect]
            x = raw[cause]
            T = len(y)
            if lag_order is None:
                p = 2
            else:
                p = lag_order
            if T <= 2 * p + 5:
                results.append(GrangerResult(cause, effect, 0.0, 1.0, False))
                continue

            # Restricted model: y_t ~ c + Σ y_{t-k}
            Y_r = y[p:]
            X_r = np.column_stack(
                [y[p - k : T - k] for k in range(1, p + 1)]
                + [np.ones(T - p)]
            )
            beta_r = np.linalg.lstsq(X_r, Y_r, rcond=None)[0]
            rss_r = np.sum((Y_r - X_r @ beta_r) ** 2)

            # Unrestricted: y_t ~ c + Σ y_{t-k} + Σ x_{t-k}
            X_u = np.column_stack(
                [y[p - k : T - k] for k in range(1, p + 1)]
                + [x[p - k : T - k] for k in range(1, p + 1)]
                + [np.ones(T - p)]
            )
            beta_u = np.linalg.lstsq(X_u, Y_r, rcond=None)[0]
            rss_u = np.sum((Y_r - X_u @ beta_u) ** 2)

            n = T - p
            q = p  # additional parameters
            k_u = X_u.shape[1]

            if rss_u <= 0 or n <= k_u:
                f_stat = 0.0
                p_val = 1.0
            else:
                f_stat = ((rss_r - rss_u) / q) / (rss_u / (n - k_u))
                # Approximate p-value using F distribution CDF
                # (scipy-free approximation from incomplete beta)
                p_val = _f_test_p_value(f_stat, q, n - k_u)

            results.append(GrangerResult(
                cause=cause,
                effect=effect,
                f_statistic=round(f_stat, 3),
                p_value=round(p_val, 4),
                significant=p_val < significance,
            ))

    return results


def _f_test_p_value(f_stat: float, df1: int, df2: int) -> float:
    """Approximate upper-tail p-value for F distribution.

    Uses a Gaussian approximation for simplicity (avoids scipy dependency).
    For production use, ``scipy.stats.f.sf`` is preferred.
    """
    if f_stat <= 0 or df1 <= 0 or df2 <= 0:
        return 1.0
    # Wilson–Hilferty approximation
    a = df1 * f_stat / df2
    nu1, nu2 = float(df1), float(df2)
    # z ≈ [(a)^{1/3} (1 - 2/(9 nu2)) - (1 - 2/(9 nu1))] / sqrt(...)
    try:
        z = (
            (a ** (1 / 3)) * (1 - 2 / (9 * nu2)) - (1 - 2 / (9 * nu1))
        ) / math.sqrt(2 / (9 * nu1) + (a ** (2 / 3)) * 2 / (9 * nu2))
    except (ValueError, ZeroDivisionError):
        return 0.5
    # Standard normal CDF approximation
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return max(0.0, min(1.0, p))


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def transmission_matrix_to_dict(
    matrix: np.ndarray,
    pillar_names: List[str],
) -> Dict[str, Dict[str, float]]:
    """Convert a K×K numpy transmission matrix to a nested dict.

    The dict has the same structure as ``shock_propagation.INTERACTION_MATRIX``:
    ``{source: {target: coefficient}}``.
    """
    d: Dict[str, Dict[str, float]] = {}
    K = len(pillar_names)
    for j in range(K):
        source = pillar_names[j]
        d[source] = {}
        for i in range(K):
            target = pillar_names[i]
            if i == j:
                d[source][target] = 0.0
            else:
                # CIRF convention: response of i to shock in j
                # INTERACTION_MATRIX convention: positive = stress propagation
                d[source][target] = round(float(matrix[i, j]), 4)
    return d


def update_interaction_matrix(
    svar_result: SVAREstimate,
) -> Dict[str, Dict[str, float]]:
    """Produce an updated INTERACTION_MATRIX from SVAR estimates.

    The returned dict is a drop-in replacement for
    ``shock_propagation.INTERACTION_MATRIX``.
    """
    return transmission_matrix_to_dict(
        svar_result.transmission_matrix,
        svar_result.pillar_names,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_svar_report(report: CascadeVARReport) -> str:
    """Format a human-readable summary of the SVAR estimation."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  SVAR CASCADE ESTIMATION REPORT  (v6 §10.2)")
    lines.append("=" * 70)
    lines.append("")

    est = report.primary_estimate
    lines.append(f"  Lag order (BIC): {est.lag_order}")
    lines.append(f"  BIC value: {est.bic:.1f}")
    lines.append(f"  Cholesky ordering: {' → '.join(est.ordering)}")
    lines.append(f"  Pillars: {', '.join(est.pillar_names)}")
    lines.append("")

    # Transmission matrix
    K = len(est.pillar_names)
    lines.append("  NORMALISED TRANSMISSION MATRIX (CIRF h=4)")
    lines.append("  Shock origin →")
    header = "  " + " " * 14 + "".join(f"{p[:6]:>8}" for p in est.pillar_names)
    lines.append(header)
    lines.append("  " + "-" * (14 + 8 * K))
    for i, target in enumerate(est.pillar_names):
        row_vals = "".join(
            f"{est.transmission_matrix[i, j]:>8.3f}" for j in range(K)
        )
        lines.append(f"  → {target:<10}" + row_vals)
    lines.append("")

    # Robustness summary
    if report.robustness:
        r = report.robustness
        lines.append(f"  ROBUSTNESS: {r.n_permutations_tested} orderings tested")
        lines.append("  Median CIRF and GIRF matrices available in report object.")
        lines.append("")

    # Acceleration factors
    if report.acceleration:
        a = report.acceleration
        lines.append("  ACCELERATION FACTORS (stress / normal)")
        lines.append("  " + "-" * (14 + 8 * K))
        header2 = "  " + " " * 14 + "".join(
            f"{p[:6]:>8}" for p in a.pillar_names
        )
        lines.append(header2)
        for i, target in enumerate(a.pillar_names):
            row_vals = "".join(
                f"{a.acceleration[i, j]:>8.2f}" for j in range(K)
            )
            lines.append(f"  → {target:<10}" + row_vals)
        lines.append("")

    # Granger causality
    sig_tests = [g for g in report.granger_tests if g.significant]
    lines.append(f"  GRANGER CAUSALITY: {len(sig_tests)} significant pairs (p<0.05)")
    for g in sig_tests:
        lines.append(f"    {g.cause} → {g.effect}  F={g.f_statistic:.2f}  p={g.p_value:.4f}")
    lines.append("")

    # OOS validation
    if report.oos_validations:
        lines.append("  OUT-OF-SAMPLE VALIDATION")
        for v in report.oos_validations:
            lines.append(f"    {v.scenario_name}: MAE={v.mae:.4f}")
        avg_mae = sum(v.mae for v in report.oos_validations) / len(report.oos_validations)
        lines.append(f"    Average MAE: {avg_mae:.4f} (target < 0.10)")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# High-level pipeline
# ---------------------------------------------------------------------------

def run_svar_pipeline(
    pillar_series: Dict[str, List[float]],
    mac_series: Optional[List[float]] = None,
    *,
    run_robustness: bool = True,
    run_acceleration: bool = True,
    run_granger: bool = True,
    max_permutations: int = 720,
) -> CascadeVARReport:
    """Run the complete SVAR estimation, robustness, and validation pipeline.

    Args:
        pillar_series: Weekly pillar score time series (all same length).
        mac_series: Composite MAC time series (needed for acceleration).
        run_robustness: Compute all 720 ordering permutations.
        run_acceleration: Estimate regime-dependent acceleration factors.
        run_granger: Run Granger-causality tests.
        max_permutations: Cap on permutations for robustness.

    Returns:
        CascadeVARReport with all results.
    """
    # Primary estimate
    est = estimate_svar(pillar_series)

    # Robustness
    robustness = None
    if run_robustness:
        robustness = robustness_all_orderings(
            pillar_series,
            lag_order=est.lag_order,
            max_permutations=max_permutations,
        )

    # Acceleration
    acceleration = None
    if run_acceleration and mac_series is not None:
        acceleration = estimate_acceleration_factors(
            pillar_series, mac_series,
        )

    # Granger causality
    granger: List[GrangerResult] = []
    if run_granger:
        granger = granger_causality_tests(pillar_series, lag_order=est.lag_order)

    # Build readable dict
    tx_dict = transmission_matrix_to_dict(
        est.transmission_matrix, est.pillar_names,
    )

    return CascadeVARReport(
        primary_estimate=est,
        robustness=robustness,
        acceleration=acceleration,
        granger_tests=granger,
        oos_validations=[],  # populated externally after scenario replays
        transmission_dict=tx_dict,
    )

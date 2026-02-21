"""Pillar independence and dependence analysis for MAC.

Quantifies statistical dependence between MAC pillars using three
complementary metrics that capture different aspects of non-linear
and non-monotone relationships:

1. **Mutual Information (MI)** — model-free, entropy-based dependence
2. **HSIC (Hilbert–Schmidt Independence Criterion)** — kernel-based,
   powerful for complex non-linear dependencies
3. **MIC (Maximal Information Coefficient)** — equitable explorer of
   functional and non-functional associations

These go beyond Pearson correlation (which only captures linear
dependence) and the hardcoded `PILLAR_CORRELATIONS` in
`grri_mac.predictive.monte_carlo`.

Usage:
    from grri_mac.mac.dependence import (
        PillarDependenceAnalyzer,
        compute_mi,
        compute_hsic,
        compute_mic,
    )

    analyzer = PillarDependenceAnalyzer()
    report = analyzer.full_analysis(pillar_history)
    # report.mi_matrix, report.hsic_matrix, report.mic_matrix
    # report.significant_pairs, report.redundancy_bits

References:
    Kraskov et al. (2004) — k-NN MI estimator
    Gretton et al. (2005) — HSIC
    Reshef et al. (2011) — MIC
    Watanabe (1960) — Total correlation
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from itertools import combinations
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# MAC pillar order (must match ml_weights.PILLAR_NAMES)
PILLAR_NAMES_7 = [
    "liquidity", "valuation", "positioning",
    "volatility", "policy", "contagion", "private_credit",
]


# ═══════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class PairwiseResult:
    """Dependence result for a single pillar pair."""

    pillar_a: str
    pillar_b: str
    mi: float               # Mutual information (bits)
    nmi: float              # Normalised MI ∈ [0, 1]
    hsic: float             # HSIC statistic
    hsic_p_value: float     # Permutation p-value for HSIC
    mic: float              # Maximal Information Coefficient ∈ [0, 1]
    pearson: float          # Linear correlation for comparison
    significant: bool       # True if HSIC p < 0.05

    @property
    def label(self) -> str:
        return f"{self.pillar_a}–{self.pillar_b}"


@dataclass
class DependenceReport:
    """Full dependence analysis report across all pillar pairs."""

    n_observations: int
    pillar_names: list[str]
    pairs: list[PairwiseResult]

    # Matrices (pillar × pillar) — symmetric, diagonal = 0
    mi_matrix: dict[tuple[str, str], float] = field(default_factory=dict)
    nmi_matrix: dict[tuple[str, str], float] = field(default_factory=dict)
    hsic_matrix: dict[tuple[str, str], float] = field(default_factory=dict)
    mic_matrix: dict[tuple[str, str], float] = field(default_factory=dict)
    pearson_matrix: dict[tuple[str, str], float] = field(default_factory=dict)

    # Significance summary
    significant_pairs: list[str] = field(default_factory=list)
    n_significant: int = 0

    # Entropy-based redundancy (total correlation, bits)
    total_correlation: float = 0.0
    dual_total_correlation: float = 0.0

    def format_report(self) -> str:
        """Format a human-readable report."""
        lines = []
        lines.append("=" * 78)
        lines.append("MAC PILLAR DEPENDENCE ANALYSIS")
        lines.append("=" * 78)
        lines.append(f"Observations: {self.n_observations}")
        lines.append(f"Pillars: {len(self.pillar_names)}")
        lines.append(f"Pairs tested: {len(self.pairs)}")
        lines.append(f"Significant (HSIC p < 0.05): {self.n_significant}")
        lines.append("")

        # Header
        lines.append(
            f"{'Pair':<30} {'Pearson':>8} {'NMI':>8} {'HSIC':>8} "
            f"{'HSIC p':>8} {'MIC':>8} {'Sig?':>5}"
        )
        lines.append("-" * 78)

        for p in sorted(self.pairs, key=lambda x: x.nmi, reverse=True):
            sig = "***" if p.significant else ""
            lines.append(
                f"{p.label:<30} {p.pearson:>+8.3f} {p.nmi:>8.3f} "
                f"{p.hsic:>8.4f} {p.hsic_p_value:>8.3f} "
                f"{p.mic:>8.3f} {sig:>5}"
            )

        lines.append("")
        lines.append("REDUNDANCY ANALYSIS")
        lines.append("-" * 78)
        lines.append(
            f"Total correlation (Watanabe):     {self.total_correlation:.3f} bits"
        )
        lines.append(
            f"Dual total correlation (Han):     {self.dual_total_correlation:.3f} bits"
        )
        lines.append("")

        if self.significant_pairs:
            lines.append("SIGNIFICANT DEPENDENCIES (candidates for decorrelation):")
            for sp in self.significant_pairs:
                lines.append(f"  - {sp}")
        else:
            lines.append("No significant non-linear dependencies detected.")

        lines.append("")
        lines.append("=" * 78)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Core metric implementations
# ═══════════════════════════════════════════════════════════════════════


def _entropy_discrete(x: np.ndarray, n_bins: int) -> float:
    """Compute Shannon entropy of a discretised 1-D array (bits)."""
    hist, _ = np.histogram(x, bins=n_bins)
    probs = hist / hist.sum()
    probs = probs[probs > 0]
    return -float(np.sum(probs * np.log2(probs)))


def _joint_entropy_discrete(
    x: np.ndarray, y: np.ndarray, n_bins: int,
) -> float:
    """Compute joint entropy H(X, Y) via 2-D histogram (bits)."""
    hist, _, _ = np.histogram2d(x, y, bins=n_bins)
    probs = hist / hist.sum()
    probs = probs[probs > 0]
    return -float(np.sum(probs * np.log2(probs)))


def compute_mi(
    x: np.ndarray,
    y: np.ndarray,
    n_bins: Optional[int] = None,
) -> tuple[float, float]:
    """Compute Mutual Information and Normalised MI.

    Uses equiprobable binning (Scott's rule for bin count).

    Args:
        x: 1-D array of pillar scores
        y: 1-D array of pillar scores (same length)
        n_bins: Number of bins (default: ceil(N^(1/3)))

    Returns:
        Tuple of (MI in bits, NMI ∈ [0, 1])
    """
    n = len(x)
    if n_bins is None:
        n_bins = max(3, int(math.ceil(n ** (1.0 / 3.0))))

    hx = _entropy_discrete(x, n_bins)
    hy = _entropy_discrete(y, n_bins)
    hxy = _joint_entropy_discrete(x, y, n_bins)

    mi = max(0.0, hx + hy - hxy)

    denom = hx + hy
    nmi = (2.0 * mi / denom) if denom > 0 else 0.0
    nmi = min(1.0, max(0.0, nmi))

    return mi, nmi


def _rbf_kernel_matrix(
    x: np.ndarray, sigma: Optional[float] = None,
) -> np.ndarray:
    """Compute RBF kernel matrix K_ij = exp(-||x_i - x_j||² / 2σ²).

    Uses the median heuristic for bandwidth if sigma is None.
    """
    x = x.reshape(-1, 1) if x.ndim == 1 else x
    # Pairwise squared distances
    dists_sq = np.sum((x[:, None, :] - x[None, :, :]) ** 2, axis=-1)

    if sigma is None:
        # Median heuristic: σ = median of pairwise distances
        triu_idx = np.triu_indices_from(dists_sq, k=1)
        dists = np.sqrt(dists_sq[triu_idx])
        sigma = float(np.median(dists)) if len(dists) > 0 else 1.0
        sigma = max(sigma, 1e-10)

    return np.exp(-dists_sq / (2.0 * sigma ** 2))


def compute_hsic(
    x: np.ndarray,
    y: np.ndarray,
    sigma_x: Optional[float] = None,
    sigma_y: Optional[float] = None,
    n_permutations: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute HSIC statistic with permutation p-value.

    HSIC(X, Y) = (1/(n-1)²) · tr(K_X H K_Y H)

    where H = I - (1/n)·11ᵀ is the centering matrix.

    Args:
        x: 1-D array of pillar scores
        y: 1-D array of pillar scores
        sigma_x: RBF bandwidth for x (default: median heuristic)
        sigma_y: RBF bandwidth for y (default: median heuristic)
        n_permutations: Number of permutations for p-value
        seed: Random seed

    Returns:
        Tuple of (HSIC statistic, permutation p-value)
    """
    n = len(x)
    if n < 5:
        return 0.0, 1.0

    K_x = _rbf_kernel_matrix(x, sigma_x)
    K_y = _rbf_kernel_matrix(y, sigma_y)

    # Centering matrix H = I - (1/n)·11ᵀ
    H = np.eye(n) - np.ones((n, n)) / n

    # HSIC = (1/(n-1)²) · tr(K_x H K_y H)
    HK_x = H @ K_x
    HK_y = H @ K_y
    hsic_observed = float(np.trace(HK_x @ HK_y)) / ((n - 1) ** 2)

    # Permutation test
    rng = np.random.default_rng(seed)
    count_greater = 0

    for _ in range(n_permutations):
        perm = rng.permutation(n)
        K_y_perm = K_y[np.ix_(perm, perm)]
        HK_y_perm = H @ K_y_perm
        hsic_perm = float(np.trace(HK_x @ HK_y_perm)) / ((n - 1) ** 2)
        if hsic_perm >= hsic_observed:
            count_greater += 1

    p_value = (count_greater + 1) / (n_permutations + 1)

    return hsic_observed, p_value


def compute_mic(
    x: np.ndarray,
    y: np.ndarray,
    alpha: float = 0.6,
    c: float = 15.0,
) -> float:
    """Compute Maximal Information Coefficient (MIC).

    Approximates MIC by searching over 2-D grids of varying resolution,
    finding the grid that maximises the normalised mutual information.

    Uses a pure-numpy implementation (no minepy dependency).

    Args:
        x: 1-D array
        y: 1-D array
        alpha: Exponent for max grid size B(n) = n^alpha
        c: Clamp constant (not used in classic MIC)

    Returns:
        MIC ∈ [0, 1]
    """
    n = len(x)
    if n < 5:
        return 0.0

    max_bins = max(2, int(n ** alpha))
    max_bins = min(max_bins, 30)  # Computational cap

    best_mic = 0.0

    for nx in range(2, max_bins + 1):
        for ny in range(2, max_bins + 1):
            if nx * ny > max_bins:
                break

            # Compute MI on this grid
            hist, _, _ = np.histogram2d(x, y, bins=[nx, ny])
            probs = hist / hist.sum()
            probs_flat = probs[probs > 0]

            # Joint entropy
            h_xy = -float(np.sum(probs_flat * np.log2(probs_flat)))

            # Marginal entropies
            px = probs.sum(axis=1)
            px = px[px > 0]
            h_x = -float(np.sum(px * np.log2(px)))

            py = probs.sum(axis=0)
            py = py[py > 0]
            h_y = -float(np.sum(py * np.log2(py)))

            mi = max(0.0, h_x + h_y - h_xy)

            # Normalise by log of the smaller grid dimension
            log_min = math.log2(min(nx, ny))
            if log_min > 0:
                normalised = mi / log_min
            else:
                normalised = 0.0

            best_mic = max(best_mic, normalised)

    return min(1.0, best_mic)


def compute_total_correlation(
    pillar_matrix: np.ndarray,
    n_bins: Optional[int] = None,
) -> float:
    """Compute Watanabe total correlation C(X₁, ..., X_p).

    C = Σᵢ H(Xᵢ) - H(X₁, ..., X_p)

    Measures total redundancy in the multivariate system (bits).
    C = 0 implies joint independence.

    Args:
        pillar_matrix: (n_obs, n_pillars) array of pillar scores
        n_bins: Bins per dimension

    Returns:
        Total correlation in bits (≥ 0)
    """
    n_obs, n_pillars = pillar_matrix.shape
    if n_bins is None:
        n_bins = max(3, int(math.ceil(n_obs ** (1.0 / 3.0))))

    # Sum of marginal entropies
    sum_marginal = sum(
        _entropy_discrete(pillar_matrix[:, j], n_bins)
        for j in range(n_pillars)
    )

    # Joint entropy via multi-dimensional histogram
    # For tractability with 7 pillars, use 3 bins per dimension
    joint_bins = min(n_bins, 3)
    hist, _ = np.histogramdd(pillar_matrix, bins=joint_bins)
    probs = hist / hist.sum()
    probs_flat = probs.flatten()
    probs_flat = probs_flat[probs_flat > 0]
    h_joint = -float(np.sum(probs_flat * np.log2(probs_flat)))

    return max(0.0, sum_marginal - h_joint)


def compute_dual_total_correlation(
    pillar_matrix: np.ndarray,
    n_bins: Optional[int] = None,
) -> float:
    """Compute Han dual total correlation D(X₁, ..., X_p).

    D = H(X₁, ..., X_p) - Σᵢ H(Xᵢ | X_{¬i})

    Measures synergistic (higher-order) interactions beyond pairwise.

    Note: This is computationally expensive for many pillars because it
    requires estimating conditional entropies. We use the identity:
    D = H(X₁,...,X_p) - Σᵢ [H(X₁,...,X_p) - H(X_{¬i})]
      = (1 - p)·H(X₁,...,X_p) + Σᵢ H(X_{¬i})

    Args:
        pillar_matrix: (n_obs, n_pillars) array
        n_bins: Bins per dimension

    Returns:
        Dual total correlation in bits (≥ 0)
    """
    n_obs, n_pillars = pillar_matrix.shape
    if n_bins is None:
        n_bins = max(3, int(math.ceil(n_obs ** (1.0 / 3.0))))

    joint_bins = min(n_bins, 3)

    # Joint entropy H(X₁,...,X_p)
    hist, _ = np.histogramdd(pillar_matrix, bins=joint_bins)
    probs = hist / hist.sum()
    probs_flat = probs.flatten()
    probs_flat = probs_flat[probs_flat > 0]
    h_joint = -float(np.sum(probs_flat * np.log2(probs_flat)))

    # Sum of leave-one-out joint entropies H(X_{¬i})
    sum_loo = 0.0
    for j in range(n_pillars):
        cols = [c for c in range(n_pillars) if c != j]
        sub_matrix = pillar_matrix[:, cols]
        hist_sub, _ = np.histogramdd(sub_matrix, bins=joint_bins)
        probs_sub = hist_sub / hist_sub.sum()
        probs_sub_flat = probs_sub.flatten()
        probs_sub_flat = probs_sub_flat[probs_sub_flat > 0]
        h_sub = -float(np.sum(probs_sub_flat * np.log2(probs_sub_flat)))
        sum_loo += h_sub

    return max(0.0, (1 - n_pillars) * h_joint + sum_loo)


# ═══════════════════════════════════════════════════════════════════════
# Analyzer class
# ═══════════════════════════════════════════════════════════════════════


class PillarDependenceAnalyzer:
    """Analyze dependence structure across MAC pillar scores.

    Computes MI, HSIC, MIC, and Pearson correlation for all pillar
    pairs, plus Watanabe total correlation and Han dual total
    correlation for the full system.

    Example:
        # From backtest results
        pillar_history = {
            "liquidity": [0.6, 0.5, ...],
            "valuation": [0.7, 0.4, ...],
            ...
        }
        analyzer = PillarDependenceAnalyzer()
        report = analyzer.full_analysis(pillar_history)
        print(report.format_report())
    """

    def __init__(
        self,
        pillar_names: Optional[list[str]] = None,
        n_permutations: int = 1000,
        significance_level: float = 0.05,
        seed: int = 42,
    ):
        """Initialize analyzer.

        Args:
            pillar_names: Pillar names (default: 7-pillar MAC)
            n_permutations: Number of HSIC permutations
            significance_level: p-value threshold for significance
            seed: Random seed for reproducibility
        """
        self.pillar_names = pillar_names or PILLAR_NAMES_7
        self.n_permutations = n_permutations
        self.significance_level = significance_level
        self.seed = seed

    def full_analysis(
        self,
        pillar_history: dict[str, list[float]],
    ) -> DependenceReport:
        """Run full dependence analysis on pillar score history.

        Args:
            pillar_history: Dict mapping pillar name → list of scores
                            over time. All lists must have the same length.

        Returns:
            DependenceReport with all metrics
        """
        # Determine active pillars (those present in data)
        active_pillars = [
            p for p in self.pillar_names if p in pillar_history
        ]
        if len(active_pillars) < 2:
            raise ValueError(
                f"Need at least 2 pillars, got {len(active_pillars)}"
            )

        # Build matrix
        n_obs = len(pillar_history[active_pillars[0]])
        matrix = np.zeros((n_obs, len(active_pillars)))
        for j, p in enumerate(active_pillars):
            arr = np.array(pillar_history[p], dtype=float)
            if len(arr) != n_obs:
                raise ValueError(
                    f"Pillar '{p}' has {len(arr)} obs, expected {n_obs}"
                )
            matrix[:, j] = arr

        # Pairwise analysis
        pairs: list[PairwiseResult] = []
        mi_matrix: dict[tuple[str, str], float] = {}
        nmi_matrix: dict[tuple[str, str], float] = {}
        hsic_matrix: dict[tuple[str, str], float] = {}
        mic_matrix: dict[tuple[str, str], float] = {}
        pearson_matrix: dict[tuple[str, str], float] = {}

        for i, j in combinations(range(len(active_pillars)), 2):
            pa = active_pillars[i]
            pb = active_pillars[j]
            x = matrix[:, i]
            y = matrix[:, j]

            # MI
            mi_val, nmi_val = compute_mi(x, y)

            # HSIC
            hsic_val, hsic_p = compute_hsic(
                x, y,
                n_permutations=self.n_permutations,
                seed=self.seed,
            )

            # MIC
            mic_val = compute_mic(x, y)

            # Pearson
            pearson_val = float(np.corrcoef(x, y)[0, 1])

            sig = hsic_p < self.significance_level

            result = PairwiseResult(
                pillar_a=pa,
                pillar_b=pb,
                mi=mi_val,
                nmi=nmi_val,
                hsic=hsic_val,
                hsic_p_value=hsic_p,
                mic=mic_val,
                pearson=pearson_val,
                significant=sig,
            )
            pairs.append(result)

            # Store in matrices (both directions)
            for key in [(pa, pb), (pb, pa)]:
                mi_matrix[key] = mi_val
                nmi_matrix[key] = nmi_val
                hsic_matrix[key] = hsic_val
                mic_matrix[key] = mic_val
                pearson_matrix[key] = pearson_val

        # Redundancy metrics
        tc = compute_total_correlation(matrix)
        dtc = compute_dual_total_correlation(matrix)

        significant_pairs = [p.label for p in pairs if p.significant]

        report = DependenceReport(
            n_observations=n_obs,
            pillar_names=active_pillars,
            pairs=pairs,
            mi_matrix=mi_matrix,
            nmi_matrix=nmi_matrix,
            hsic_matrix=hsic_matrix,
            mic_matrix=mic_matrix,
            pearson_matrix=pearson_matrix,
            significant_pairs=significant_pairs,
            n_significant=len(significant_pairs),
            total_correlation=tc,
            dual_total_correlation=dtc,
        )

        logger.info(
            "Dependence analysis: %d pairs, %d significant, "
            "TC=%.3f bits",
            len(pairs), len(significant_pairs), tc,
        )

        return report

    def rolling_analysis(
        self,
        pillar_history: dict[str, list[float]],
        window_size: int = 52,
    ) -> list[DependenceReport]:
        """Run rolling-window dependence analysis.

        Useful for detecting time-varying dependence structure
        (e.g., dependencies increasing during crises).

        Args:
            pillar_history: Pillar score time series
            window_size: Rolling window size (observations)

        Returns:
            List of DependenceReport, one per window position
        """
        active_pillars = [
            p for p in self.pillar_names if p in pillar_history
        ]
        n_obs = len(pillar_history[active_pillars[0]])

        if n_obs < window_size:
            raise ValueError(
                f"Need at least {window_size} obs, got {n_obs}"
            )

        reports = []
        # Use fewer permutations for rolling (computational efficiency)
        saved_perms = self.n_permutations
        self.n_permutations = min(200, self.n_permutations)

        for start in range(0, n_obs - window_size + 1, max(1, window_size // 4)):
            end = start + window_size
            window_data = {
                p: pillar_history[p][start:end]
                for p in active_pillars
            }
            report = self.full_analysis(window_data)
            reports.append(report)

        self.n_permutations = saved_perms
        return reports

    def compare_to_hardcoded(
        self,
        pillar_history: dict[str, list[float]],
    ) -> dict[str, dict]:
        """Compare empirical dependence to hardcoded PILLAR_CORRELATIONS.

        The monte_carlo module uses hardcoded correlations.  This method
        checks whether those are consistent with the data.

        Returns:
            Dict mapping pair label → {hardcoded, empirical_pearson,
            empirical_nmi, empirical_mic, gap}
        """
        from ..predictive.monte_carlo import PILLAR_CORRELATIONS

        report = self.full_analysis(pillar_history)
        comparison = {}

        for (p1, p2), hardcoded_corr in PILLAR_CORRELATIONS.items():
            key_fwd = (p1, p2)
            key_rev = (p2, p1)

            pearson = report.pearson_matrix.get(
                key_fwd, report.pearson_matrix.get(key_rev, None)
            )
            nmi = report.nmi_matrix.get(
                key_fwd, report.nmi_matrix.get(key_rev, None)
            )
            mic = report.mic_matrix.get(
                key_fwd, report.mic_matrix.get(key_rev, None)
            )

            if pearson is not None:
                comparison[f"{p1}–{p2}"] = {
                    "hardcoded": hardcoded_corr,
                    "empirical_pearson": pearson,
                    "empirical_nmi": nmi,
                    "empirical_mic": mic,
                    "gap": abs(hardcoded_corr - pearson),
                    "needs_update": abs(hardcoded_corr - pearson) > 0.15,
                }

        return comparison


def run_dependence_analysis_on_backtest() -> DependenceReport:
    """Convenience: run dependence analysis on backtest results.

    Loads backtest pillar scores and computes full dependence analysis.

    Returns:
        DependenceReport
    """
    from ..backtest.calibrated_engine import CalibratedBacktestEngine

    engine = CalibratedBacktestEngine()
    results = engine.run_all_scenarios()

    # Collect pillar scores from all scenarios
    pillar_history: dict[str, list[float]] = {}
    for result in results.results:
        for pillar, score in result.pillar_scores.items():
            if pillar not in pillar_history:
                pillar_history[pillar] = []
            pillar_history[pillar].append(score)

    analyzer = PillarDependenceAnalyzer()
    return analyzer.full_analysis(pillar_history)

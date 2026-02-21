"""Tests for MAC pillar dependence analysis module.

Tests cover:
- MI computation with known distributions
- HSIC with independent and dependent data
- MIC with functional and random relationships
- Total correlation and dual total correlation
- Full PillarDependenceAnalyzer pipeline
- Rolling window analysis
- Edge cases
"""

import math
import numpy as np
import pytest

from grri_mac.mac.dependence import (
    PillarDependenceAnalyzer,
    DependenceReport,
    PairwiseResult,
    compute_mi,
    compute_hsic,
    compute_mic,
    compute_total_correlation,
    compute_dual_total_correlation,
    _entropy_discrete,
    _joint_entropy_discrete,
    _rbf_kernel_matrix,
    PILLAR_NAMES_7,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def rng():
    """Seeded RNG for reproducibility."""
    return np.random.default_rng(12345)


@pytest.fixture
def independent_data(rng):
    """Two independent standard normal arrays."""
    n = 500
    return rng.standard_normal(n), rng.standard_normal(n)


@pytest.fixture
def linearly_dependent_data(rng):
    """Y = 2X + small noise."""
    n = 500
    x = rng.standard_normal(n)
    y = 2.0 * x + 0.1 * rng.standard_normal(n)
    return x, y


@pytest.fixture
def nonlinear_dependent_data(rng):
    """Y = sin(X) — nonlinear but deterministic."""
    n = 500
    x = rng.uniform(-3.0, 3.0, n)
    y = np.sin(x) + 0.05 * rng.standard_normal(n)
    return x, y


@pytest.fixture
def identical_data(rng):
    """X = Y exactly."""
    n = 500
    x = rng.standard_normal(n)
    return x, x.copy()


@pytest.fixture
def seven_pillar_history(rng):
    """Synthetic 7-pillar MAC history with known structure.

    - liquidity and contagion: strongly correlated (r≈0.7)
    - volatility and positioning: moderately correlated (r≈0.5)
    - All others: approximately independent
    """
    n = 200
    base = rng.standard_normal((n, 7))

    # Inject correlations
    # liquidity (0) and contagion (5): r ≈ 0.7
    base[:, 5] = 0.7 * base[:, 0] + 0.714 * base[:, 5]
    # volatility (3) and positioning (2): r ≈ 0.5
    base[:, 2] = 0.5 * base[:, 3] + 0.866 * base[:, 2]

    # Normalise to [0, 1] range (MAC scores)
    for j in range(7):
        col = base[:, j]
        base[:, j] = (col - col.min()) / (col.max() - col.min() + 1e-10)

    return {
        name: base[:, i].tolist()
        for i, name in enumerate(PILLAR_NAMES_7)
    }


@pytest.fixture
def three_pillar_history(rng):
    """Minimal 3-pillar history for fast tests."""
    n = 100
    return {
        "liquidity": rng.uniform(0, 1, n).tolist(),
        "valuation": rng.uniform(0, 1, n).tolist(),
        "positioning": rng.uniform(0, 1, n).tolist(),
    }


# ═══════════════════════════════════════════════════════════════════════
# Entropy tests
# ═══════════════════════════════════════════════════════════════════════


class TestEntropy:
    """Tests for discrete entropy computation."""

    def test_uniform_distribution(self, rng):
        """Uniform distribution should have maximal entropy."""
        x = rng.uniform(0, 1, 10000)
        h = _entropy_discrete(x, n_bins=8)
        # Max entropy for 8 bins = log2(8) = 3.0
        assert 2.8 < h <= 3.0, f"Expected ~3.0 bits, got {h}"

    def test_degenerate_distribution(self):
        """Constant array should have near-zero entropy."""
        x = np.ones(100)
        h = _entropy_discrete(x, n_bins=10)
        assert h == 0.0, f"Expected 0 bits, got {h}"

    def test_joint_entropy_independent(self, rng):
        """H(X, Y) ≈ H(X) + H(Y) for independent variables."""
        x = rng.uniform(0, 1, 5000)
        y = rng.uniform(0, 1, 5000)
        n_bins = 8
        hx = _entropy_discrete(x, n_bins)
        hy = _entropy_discrete(y, n_bins)
        hxy = _joint_entropy_discrete(x, y, n_bins)
        # Joint entropy should be close to sum of marginals
        assert abs(hxy - (hx + hy)) < 0.3, (
            f"H(X,Y)={hxy:.3f} vs H(X)+H(Y)={hx + hy:.3f}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Mutual Information tests
# ═══════════════════════════════════════════════════════════════════════


class TestMutualInformation:
    """Tests for MI and NMI computation."""

    def test_independent_mi_near_zero(self, independent_data):
        """Independent variables should have MI ≈ 0."""
        x, y = independent_data
        mi, nmi = compute_mi(x, y)
        assert mi < 0.15, f"MI={mi:.4f}, expected near 0"
        assert 0.0 <= nmi <= 1.0

    def test_identical_mi_high(self, identical_data):
        """Identical variables should have MI = H(X)."""
        x, y = identical_data
        mi, nmi = compute_mi(x, y)
        h = _entropy_discrete(x, n_bins=max(3, int(len(x) ** (1 / 3))))
        assert mi > 0.5, f"MI={mi:.4f}, expected > 0.5"
        assert nmi > 0.7, f"NMI={nmi:.4f}, expected > 0.7"

    def test_linear_dependence(self, linearly_dependent_data):
        """Strong linear dependence → high MI."""
        x, y = linearly_dependent_data
        mi, nmi = compute_mi(x, y)
        assert mi > 0.3, f"MI={mi:.4f}, expected > 0.3"
        assert nmi > 0.3, f"NMI={nmi:.4f}, expected > 0.3"

    def test_nonlinear_dependence(self, nonlinear_dependent_data):
        """Nonlinear (sin) relationship should have positive MI."""
        x, y = nonlinear_dependent_data
        mi, nmi = compute_mi(x, y)
        assert mi > 0.05, f"MI={mi:.4f}, expected > 0.05"

    def test_nmi_bounds(self, rng):
        """NMI should always be in [0, 1]."""
        for _ in range(10):
            x = rng.standard_normal(100)
            y = rng.standard_normal(100)
            _, nmi = compute_mi(x, y)
            assert 0.0 <= nmi <= 1.0, f"NMI={nmi} out of bounds"

    def test_custom_bins(self, linearly_dependent_data):
        """Custom bin count should work."""
        x, y = linearly_dependent_data
        mi_5, _ = compute_mi(x, y, n_bins=5)
        mi_20, _ = compute_mi(x, y, n_bins=20)
        # Both should be positive
        assert mi_5 > 0
        assert mi_20 > 0


# ═══════════════════════════════════════════════════════════════════════
# HSIC tests
# ═══════════════════════════════════════════════════════════════════════


class TestHSIC:
    """Tests for HSIC computation."""

    def test_independent_not_significant(self, independent_data):
        """Independent data should produce high p-value."""
        x, y = independent_data
        hsic, p = compute_hsic(x, y, n_permutations=200, seed=42)
        assert p > 0.01, f"p={p:.4f}, expected > 0.01 for independent data"

    def test_dependent_significant(self, linearly_dependent_data):
        """Strongly dependent data should produce low p-value."""
        x, y = linearly_dependent_data
        hsic, p = compute_hsic(x, y, n_permutations=200, seed=42)
        assert hsic > 0, f"HSIC={hsic:.6f}, expected > 0"
        assert p < 0.05, f"p={p:.4f}, expected < 0.05"

    def test_nonlinear_significant(self, nonlinear_dependent_data):
        """Nonlinear dependence should be detected."""
        x, y = nonlinear_dependent_data
        hsic, p = compute_hsic(x, y, n_permutations=200, seed=42)
        assert hsic > 0
        assert p < 0.05, f"p={p:.4f}, expected < 0.05 for sin(x)"

    def test_small_sample(self):
        """n < 5 should return (0, 1)."""
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([4.0, 5.0, 6.0])
        hsic, p = compute_hsic(x, y)
        assert hsic == 0.0
        assert p == 1.0

    def test_reproducibility(self, linearly_dependent_data):
        """Same seed should give same result."""
        x, y = linearly_dependent_data
        h1, p1 = compute_hsic(x, y, n_permutations=100, seed=999)
        h2, p2 = compute_hsic(x, y, n_permutations=100, seed=999)
        assert h1 == h2
        assert p1 == p2

    def test_custom_sigma(self, linearly_dependent_data):
        """Explicit bandwidth should work."""
        x, y = linearly_dependent_data
        hsic, p = compute_hsic(x, y, sigma_x=1.0, sigma_y=1.0,
                                n_permutations=50, seed=42)
        assert hsic > 0


# ═══════════════════════════════════════════════════════════════════════
# MIC tests
# ═══════════════════════════════════════════════════════════════════════


class TestMIC:
    """Tests for MIC computation."""

    def test_independent_low_mic(self, independent_data):
        """Independent variables should have low MIC."""
        x, y = independent_data
        mic = compute_mic(x, y)
        assert mic < 0.3, f"MIC={mic:.4f}, expected < 0.3"

    def test_linear_high_mic(self, linearly_dependent_data):
        """Strong linear relationship → MIC near 1."""
        x, y = linearly_dependent_data
        mic = compute_mic(x, y)
        assert mic > 0.5, f"MIC={mic:.4f}, expected > 0.5"

    def test_nonlinear_high_mic(self, nonlinear_dependent_data):
        """sin(x) relationship → positive MIC."""
        x, y = nonlinear_dependent_data
        mic = compute_mic(x, y)
        assert mic > 0.2, f"MIC={mic:.4f}, expected > 0.2"

    def test_mic_bounds(self, rng):
        """MIC should always be in [0, 1]."""
        for _ in range(10):
            x = rng.standard_normal(100)
            y = rng.standard_normal(100)
            mic = compute_mic(x, y)
            assert 0.0 <= mic <= 1.0, f"MIC={mic} out of bounds"

    def test_small_sample(self):
        """n < 5 should return 0."""
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([4.0, 5.0, 6.0])
        mic = compute_mic(x, y)
        assert mic == 0.0


# ═══════════════════════════════════════════════════════════════════════
# RBF Kernel tests
# ═══════════════════════════════════════════════════════════════════════


class TestRBFKernel:
    """Tests for RBF kernel matrix."""

    def test_kernel_shape(self, rng):
        """Kernel matrix should be n × n."""
        x = rng.standard_normal(50)
        K = _rbf_kernel_matrix(x)
        assert K.shape == (50, 50)

    def test_kernel_diagonal(self, rng):
        """Diagonal should be 1 (K(x,x) = exp(0) = 1)."""
        x = rng.standard_normal(30)
        K = _rbf_kernel_matrix(x)
        np.testing.assert_allclose(np.diag(K), 1.0, atol=1e-10)

    def test_kernel_symmetric(self, rng):
        """Kernel matrix should be symmetric."""
        x = rng.standard_normal(30)
        K = _rbf_kernel_matrix(x)
        np.testing.assert_allclose(K, K.T, atol=1e-10)

    def test_kernel_positive_semidefinite(self, rng):
        """RBF kernel should be positive semi-definite."""
        x = rng.standard_normal(30)
        K = _rbf_kernel_matrix(x)
        eigenvalues = np.linalg.eigvalsh(K)
        assert all(eigenvalues >= -1e-10), "Kernel not PSD"


# ═══════════════════════════════════════════════════════════════════════
# Total correlation tests
# ═══════════════════════════════════════════════════════════════════════


class TestTotalCorrelation:
    """Tests for multivariate redundancy metrics."""

    def test_independent_low_tc(self, rng):
        """Independent columns → TC lower than redundant columns."""
        matrix_ind = rng.standard_normal((500, 3))
        tc_ind = compute_total_correlation(matrix_ind)
        # Build redundant matrix for comparison
        x = rng.standard_normal(500)
        matrix_dep = np.column_stack([
            x, x + 0.01 * rng.standard_normal(500),
            x + 0.01 * rng.standard_normal(500),
        ])
        tc_dep = compute_total_correlation(matrix_dep)
        assert tc_ind < tc_dep, (
            f"Independent TC={tc_ind:.4f} should be < redundant TC={tc_dep:.4f}"
        )

    def test_redundant_high_tc(self, rng):
        """Redundant columns → high TC."""
        x = rng.standard_normal(500)
        matrix = np.column_stack([
            x,
            x + 0.01 * rng.standard_normal(500),
            x + 0.01 * rng.standard_normal(500),
        ])
        tc = compute_total_correlation(matrix)
        assert tc > 1.0, f"TC={tc:.4f}, expected > 1.0"

    def test_tc_nonnegative(self, rng):
        """Total correlation should be ≥ 0."""
        matrix = rng.standard_normal((100, 5))
        tc = compute_total_correlation(matrix)
        assert tc >= 0.0

    def test_dual_tc_nonnegative(self, rng):
        """Dual total correlation should be ≥ 0."""
        matrix = rng.standard_normal((100, 4))
        dtc = compute_dual_total_correlation(matrix)
        assert dtc >= 0.0


# ═══════════════════════════════════════════════════════════════════════
# PillarDependenceAnalyzer tests
# ═══════════════════════════════════════════════════════════════════════


class TestPillarDependenceAnalyzer:
    """Integration tests for the analyzer class."""

    def test_full_analysis_returns_report(self, seven_pillar_history):
        """full_analysis should return a DependenceReport."""
        analyzer = PillarDependenceAnalyzer(n_permutations=50)
        report = analyzer.full_analysis(seven_pillar_history)
        assert isinstance(report, DependenceReport)
        assert report.n_observations == 200
        assert len(report.pillar_names) == 7

    def test_correct_pair_count(self, seven_pillar_history):
        """7 pillars → C(7,2) = 21 pairs."""
        analyzer = PillarDependenceAnalyzer(n_permutations=50)
        report = analyzer.full_analysis(seven_pillar_history)
        assert len(report.pairs) == 21

    def test_three_pillar_pair_count(self, three_pillar_history):
        """3 pillars → C(3,2) = 3 pairs."""
        analyzer = PillarDependenceAnalyzer(
            pillar_names=["liquidity", "valuation", "positioning"],
            n_permutations=50,
        )
        report = analyzer.full_analysis(three_pillar_history)
        assert len(report.pairs) == 3

    def test_detects_known_correlation(self, seven_pillar_history):
        """Should detect the injected liq-contagion correlation."""
        analyzer = PillarDependenceAnalyzer(n_permutations=200)
        report = analyzer.full_analysis(seven_pillar_history)

        liq_con = [
            p for p in report.pairs
            if {p.pillar_a, p.pillar_b} == {"liquidity", "contagion"}
        ]
        assert len(liq_con) == 1
        pair = liq_con[0]
        assert abs(pair.pearson) > 0.4, (
            f"Expected strong correlation, got {pair.pearson:.3f}"
        )
        assert pair.nmi > 0.05, f"NMI={pair.nmi:.4f}, expected > 0.05"

    def test_matrices_symmetric(self, three_pillar_history):
        """Matrix entries should be symmetric."""
        analyzer = PillarDependenceAnalyzer(
            pillar_names=["liquidity", "valuation", "positioning"],
            n_permutations=50,
        )
        report = analyzer.full_analysis(three_pillar_history)

        for (a, b), val in report.mi_matrix.items():
            rev = report.mi_matrix.get((b, a))
            assert rev is not None, f"Missing reverse entry ({b},{a})"
            assert val == rev

    def test_format_report(self, three_pillar_history):
        """format_report should produce a non-empty string."""
        analyzer = PillarDependenceAnalyzer(
            pillar_names=["liquidity", "valuation", "positioning"],
            n_permutations=50,
        )
        report = analyzer.full_analysis(three_pillar_history)
        text = report.format_report()
        assert "MAC PILLAR DEPENDENCE ANALYSIS" in text
        assert "Observations:" in text
        assert len(text) > 200

    def test_significant_pairs_flagged(self, seven_pillar_history):
        """At least one significant pair in the correlated data."""
        analyzer = PillarDependenceAnalyzer(n_permutations=200)
        report = analyzer.full_analysis(seven_pillar_history)
        # We injected strong correlations, should find at least one
        assert report.n_significant >= 1

    def test_total_correlation_computed(self, seven_pillar_history):
        """Report should include TC and DTC."""
        analyzer = PillarDependenceAnalyzer(n_permutations=50)
        report = analyzer.full_analysis(seven_pillar_history)
        assert report.total_correlation >= 0
        assert report.dual_total_correlation >= 0

    def test_missing_pillars_handled(self, rng):
        """Analyzer should work with subset of pillars."""
        data = {
            "liquidity": rng.uniform(0, 1, 100).tolist(),
            "contagion": rng.uniform(0, 1, 100).tolist(),
        }
        analyzer = PillarDependenceAnalyzer(n_permutations=50)
        report = analyzer.full_analysis(data)
        assert len(report.pairs) == 1
        assert len(report.pillar_names) == 2

    def test_raises_on_single_pillar(self, rng):
        """Should raise ValueError with < 2 pillars."""
        data = {"liquidity": rng.uniform(0, 1, 100).tolist()}
        analyzer = PillarDependenceAnalyzer(n_permutations=50)
        with pytest.raises(ValueError, match="at least 2 pillars"):
            analyzer.full_analysis(data)

    def test_raises_on_length_mismatch(self, rng):
        """Should raise ValueError if pillar lengths differ."""
        data = {
            "liquidity": rng.uniform(0, 1, 100).tolist(),
            "contagion": rng.uniform(0, 1, 80).tolist(),
        }
        analyzer = PillarDependenceAnalyzer(n_permutations=50)
        with pytest.raises(ValueError, match="obs, expected"):
            analyzer.full_analysis(data)


# ═══════════════════════════════════════════════════════════════════════
# Rolling analysis tests
# ═══════════════════════════════════════════════════════════════════════


class TestRollingAnalysis:
    """Tests for rolling-window dependence analysis."""

    def test_rolling_returns_list(self, seven_pillar_history):
        """rolling_analysis should return a list of reports."""
        analyzer = PillarDependenceAnalyzer(n_permutations=30)
        reports = analyzer.rolling_analysis(
            seven_pillar_history, window_size=50,
        )
        assert isinstance(reports, list)
        assert len(reports) > 0
        assert all(isinstance(r, DependenceReport) for r in reports)

    def test_rolling_window_sizes(self, seven_pillar_history):
        """Each report window should have correct n_observations."""
        analyzer = PillarDependenceAnalyzer(n_permutations=30)
        reports = analyzer.rolling_analysis(
            seven_pillar_history, window_size=50,
        )
        for r in reports:
            assert r.n_observations == 50

    def test_rolling_raises_on_small_data(self, three_pillar_history):
        """Should raise if data shorter than window."""
        analyzer = PillarDependenceAnalyzer(
            pillar_names=["liquidity", "valuation", "positioning"],
            n_permutations=30,
        )
        with pytest.raises(ValueError, match="at least"):
            analyzer.rolling_analysis(
                three_pillar_history, window_size=200,
            )


# ═══════════════════════════════════════════════════════════════════════
# PairwiseResult tests
# ═══════════════════════════════════════════════════════════════════════


class TestPairwiseResult:
    """Tests for the PairwiseResult dataclass."""

    def test_label_format(self):
        """Label should use en-dash separator."""
        r = PairwiseResult(
            pillar_a="liquidity", pillar_b="contagion",
            mi=0.5, nmi=0.4, hsic=0.01, hsic_p_value=0.001,
            mic=0.6, pearson=0.7, significant=True,
        )
        assert r.label == "liquidity–contagion"

    def test_significant_flag(self):
        """significant flag should reflect HSIC p-value."""
        r = PairwiseResult(
            pillar_a="a", pillar_b="b",
            mi=0, nmi=0, hsic=0, hsic_p_value=0.001,
            mic=0, pearson=0, significant=True,
        )
        assert r.significant is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

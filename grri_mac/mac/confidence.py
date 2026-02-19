"""Bootstrap and conformal prediction bands for MAC scores.

Provides uncertainty quantification by bootstrapping three sources of error:
1. Indicator measurement error (proxy uncertainty)
2. Pillar weight uncertainty (ML model instability)
3. Calibration factor α uncertainty (LOOCV residual variance)

Usage:
    from grri_mac.mac.confidence import bootstrap_mac_ci, conformal_band
    ci = bootstrap_mac_ci(pillar_scores, weights, n_bootstrap=1000)
    # ci.ci_80 = (0.35, 0.52), ci.ci_90 = (0.32, 0.55)
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ConfidenceResult:
    """Result of bootstrap confidence interval calculation."""

    point_estimate: float
    ci_80: tuple[float, float]  # 10th and 90th percentiles
    ci_90: tuple[float, float]  # 5th and 95th percentiles
    ci_95: tuple[float, float]  # 2.5th and 97.5th percentiles
    bootstrap_std: float
    bootstrap_mean: float
    n_bootstrap: int
    percentiles: dict[int, float] = field(default_factory=dict)


@dataclass
class ProxyUncertainty:
    """Measurement error scale for each indicator proxy."""

    # Relative noise std (fraction of value) by indicator quality tier
    TIER_NOISE = {
        "native": 0.01,      # Direct FRED series (e.g., VIXCLS)
        "computed": 0.03,     # Derived from FRED (e.g., SOFR-IORB spread)
        "proxy_modern": 0.05,  # Modern proxy (e.g., Moody's → OAS)
        "proxy_historical": 0.10,  # Historical proxy (e.g., realised vol → VIX)
        "estimated": 0.15,    # Expert estimate (e.g., basis trade size)
    }

    # Map indicator keys to quality tiers
    INDICATOR_TIERS = {
        "vix_level": "native",
        "sofr_iorb_spread_bps": "computed",
        "cp_treasury_spread_bps": "computed",
        "ig_oas_bps": "native",
        "hy_oas_bps": "native",
        "term_premium_10y_bps": "computed",
        "policy_room_bps": "native",
        "fed_balance_sheet_gdp_pct": "native",
        "core_pce_vs_target_bps": "computed",
        "basis_trade_size_billions": "estimated",
        "treasury_spec_net_percentile": "proxy_modern",
        "svxy_aum_millions": "native",
        "cross_currency_basis_bps": "computed",
        "em_flow_pct_weekly": "estimated",
        "gsib_cds_avg_bps": "proxy_modern",
        "dxy_3m_change_pct": "native",
        "embi_spread_bps": "native",
        "global_equity_corr": "computed",
        "vix_term_structure": "proxy_modern",
        "rv_iv_gap_pct": "computed",
    }

    @classmethod
    def get_noise_std(cls, indicator_key: str) -> float:
        """Get the noise standard deviation for a given indicator."""
        tier = cls.INDICATOR_TIERS.get(indicator_key, "proxy_modern")
        return cls.TIER_NOISE[tier]


def bootstrap_mac_ci(
    pillar_scores: dict[str, float],
    weights: dict[str, float],
    n_bootstrap: int = 1000,
    indicator_noise: bool = True,
    weight_noise_std: float = 0.03,
    alpha_mean: float = 0.78,
    alpha_std: float = 0.05,
    interaction_penalty: float = 0.0,
    seed: int = 42,
) -> ConfidenceResult:
    """Bootstrap MAC score confidence intervals.

    Perturbs three sources of uncertainty simultaneously:
    1. Indicator → pillar score measurement error
    2. Pillar weight instability (from ML resampling)
    3. Calibration factor α (from LOOCV variance)

    Args:
        pillar_scores: Current pillar scores (0-1)
        weights: Pillar weights (sum to 1)
        n_bootstrap: Number of bootstrap iterations
        indicator_noise: Whether to perturb pillar scores
        weight_noise_std: Std of weight perturbation (Gaussian)
        alpha_mean: Mean calibration factor
        alpha_std: Std of calibration factor (from LOOCV)
        interaction_penalty: Current breach interaction penalty
        seed: Random seed

    Returns:
        ConfidenceResult with CIs and diagnostics
    """
    rng = np.random.default_rng(seed)
    pillars = sorted(pillar_scores.keys())
    n_pillars = len(pillars)

    # Base scores and weights as arrays
    base_scores = np.array([pillar_scores[p] for p in pillars])
    base_weights = np.array([weights.get(p, 1.0 / n_pillars) for p in pillars])

    # Point estimate
    raw_point = float(np.dot(base_scores, base_weights))
    point_estimate = max(0.0, raw_point - interaction_penalty)

    # Bootstrap
    mac_samples = np.zeros(n_bootstrap)

    for b in range(n_bootstrap):
        # 1. Perturb pillar scores (measurement error)
        if indicator_noise:
            noise = rng.normal(0, 0.03, size=n_pillars)  # ~3% noise on pillar scores
            perturbed_scores = np.clip(base_scores + noise, 0.0, 1.0)
        else:
            perturbed_scores = base_scores.copy()

        # 2. Perturb weights (ML instability)
        weight_noise = rng.normal(0, weight_noise_std, size=n_pillars)
        perturbed_weights = base_weights + weight_noise
        perturbed_weights = np.maximum(perturbed_weights, 0.01)  # Floor at 1%
        perturbed_weights /= perturbed_weights.sum()  # Re-normalize

        # 3. Perturb calibration factor
        alpha = rng.normal(alpha_mean, alpha_std)
        alpha = max(0.5, min(1.0, alpha))

        # Calculate bootstrapped MAC
        raw_mac = float(np.dot(perturbed_scores, perturbed_weights))
        # Apply interaction penalty (could also be bootstrapped, but keep fixed)
        adjusted_mac = max(0.0, raw_mac - interaction_penalty)
        # Apply calibration factor
        calibrated_mac = adjusted_mac * alpha
        mac_samples[b] = max(0.0, min(1.0, calibrated_mac))

    # Calculate percentiles
    percentiles = {
        2: float(np.percentile(mac_samples, 2.5)),
        5: float(np.percentile(mac_samples, 5)),
        10: float(np.percentile(mac_samples, 10)),
        25: float(np.percentile(mac_samples, 25)),
        50: float(np.percentile(mac_samples, 50)),
        75: float(np.percentile(mac_samples, 75)),
        90: float(np.percentile(mac_samples, 90)),
        95: float(np.percentile(mac_samples, 95)),
        97: float(np.percentile(mac_samples, 97.5)),
    }

    return ConfidenceResult(
        point_estimate=point_estimate,
        ci_80=(percentiles[10], percentiles[90]),
        ci_90=(percentiles[5], percentiles[95]),
        ci_95=(percentiles[2], percentiles[97]),
        bootstrap_std=float(np.std(mac_samples)),
        bootstrap_mean=float(np.mean(mac_samples)),
        n_bootstrap=n_bootstrap,
        percentiles=percentiles,
    )


def conformal_prediction_band(
    mac_score: float,
    calibration_residuals: list[float],
    alpha: float = 0.10,
) -> tuple[float, float]:
    """Compute conformal prediction band using LOOCV residuals.

    Uses the split conformal prediction framework: the prediction interval
    is mac_score ± q_{1-alpha}(|residuals|).

    Args:
        mac_score: Point estimate MAC score
        calibration_residuals: Absolute residuals from LOOCV holdouts
        alpha: Significance level (0.10 → 90% band)

    Returns:
        (lower, upper) bounds of the conformal prediction band
    """
    if not calibration_residuals:
        # No calibration data — return wide band
        return (max(0.0, mac_score - 0.15), min(1.0, mac_score + 0.15))

    abs_residuals = sorted([abs(r) for r in calibration_residuals])
    n = len(abs_residuals)

    # Conformal quantile: ceil((n+1)(1-alpha)) / n
    quantile_index = int(np.ceil((n + 1) * (1 - alpha))) - 1
    quantile_index = min(quantile_index, n - 1)
    q = abs_residuals[quantile_index]

    lower = max(0.0, mac_score - q)
    upper = min(1.0, mac_score + q)

    return (lower, upper)

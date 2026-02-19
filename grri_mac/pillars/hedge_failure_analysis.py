"""Formal hedge failure analysis for the positioning pillar.

Provides:
1. Formal definition of Treasury hedge failure
2. Historical hedge failure catalogue (expanded to 8-10 episodes)
3. New indicators: primary dealer leverage, Treasury futures Herfindahl
4. Bayesian posterior updates with expanded sample

Usage:
    from grri_mac.pillars.hedge_failure_analysis import (
        HedgeFailureDetector,
        HEDGE_FAILURE_EPISODES,
    )
    detector = HedgeFailureDetector()
    is_failure = detector.is_hedge_failure(
        ten_year_return=-0.025, sp500_return=-0.04
    )
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np


@dataclass
class HedgeFailureEpisode:
    """A documented Treasury hedge failure episode."""

    date: datetime
    name: str
    ten_year_return: float     # Daily 10Y Treasury total return
    sp500_return: float        # Daily S&P 500 return
    description: str
    positioning_breached: bool  # Was positioning pillar in breach?
    basis_trade_unwind: bool   # Was basis trade unwind a factor?
    severity: str              # "mild", "moderate", "severe"


# Expanded hedge failure catalogue (back to 1994)
# A hedge failure occurs when Treasuries fail to rally during
# a significant equity selloff — i.e., the traditional
# 60/40 diversification breaks down.
HEDGE_FAILURE_EPISODES = [
    HedgeFailureEpisode(
        date=datetime(1994, 2, 4),
        name="1994 Bond Massacre onset",
        ten_year_return=-0.018,
        sp500_return=-0.027,
        description=(
            "Greenspan surprise hike. Bonds sold off alongside "
            "equities as rate shock repriced everything."
        ),
        positioning_breached=True,
        basis_trade_unwind=False,
        severity="moderate",
    ),
    HedgeFailureEpisode(
        date=datetime(1999, 6, 30),
        name="1999 Rate Scare",
        ten_year_return=-0.012,
        sp500_return=-0.015,
        description=(
            "Fed hiking cycle + Y2K fears. Brief period of "
            "bond-equity correlation flip."
        ),
        positioning_breached=False,
        basis_trade_unwind=False,
        severity="mild",
    ),
    HedgeFailureEpisode(
        date=datetime(2003, 7, 10),
        name="2003 Bond Tantrum",
        ten_year_return=-0.025,
        sp500_return=-0.010,
        description=(
            "Yields surged from 3.1% to 4.6% in 8 weeks. "
            "Mortgage convexity selling amplified."
        ),
        positioning_breached=True,
        basis_trade_unwind=False,
        severity="moderate",
    ),
    HedgeFailureEpisode(
        date=datetime(2013, 6, 19),
        name="Taper Tantrum",
        ten_year_return=-0.020,
        sp500_return=-0.014,
        description=(
            "Bernanke signalled QE tapering. 10Y yield surged "
            "from 1.6% to 3.0%. Bonds were the source of stress."
        ),
        positioning_breached=True,
        basis_trade_unwind=False,
        severity="moderate",
    ),
    HedgeFailureEpisode(
        date=datetime(2016, 11, 9),
        name="Trump Election Reflation",
        ten_year_return=-0.022,
        sp500_return=0.011,
        description=(
            "Equities rallied but bonds crashed on inflation/"
            "fiscal expansion expectations. Correlation flip."
        ),
        positioning_breached=False,
        basis_trade_unwind=False,
        severity="mild",
    ),
    HedgeFailureEpisode(
        date=datetime(2018, 2, 2),
        name="Volmageddon Rate Scare",
        ten_year_return=-0.010,
        sp500_return=-0.022,
        description=(
            "Strong jobs data + wage growth scare. Bonds and "
            "equities sold off together briefly."
        ),
        positioning_breached=True,
        basis_trade_unwind=False,
        severity="mild",
    ),
    HedgeFailureEpisode(
        date=datetime(2020, 3, 12),
        name="COVID Dash-for-Cash",
        ten_year_return=-0.030,
        sp500_return=-0.095,
        description=(
            "Margin calls forced liquidation of everything "
            "including Treasuries. Basis trade unwind. "
            "Fed launched unlimited QE to stabilise."
        ),
        positioning_breached=True,
        basis_trade_unwind=True,
        severity="severe",
    ),
    HedgeFailureEpisode(
        date=datetime(2022, 9, 26),
        name="UK LDI Gilt Spillover",
        ten_year_return=-0.012,
        sp500_return=-0.018,
        description=(
            "UK pension crisis spillover. Brief correlation "
            "flip in US Treasuries as global rate fears spiked."
        ),
        positioning_breached=False,
        basis_trade_unwind=False,
        severity="mild",
    ),
    HedgeFailureEpisode(
        date=datetime(2025, 4, 3),
        name="Tariff Shock Basis Unwind",
        ten_year_return=-0.025,
        sp500_return=-0.048,
        description=(
            "Tariff shock triggered basis trade unwind. "
            "Treasuries sold off WITH equities due to extreme "
            "positioning crowding."
        ),
        positioning_breached=True,
        basis_trade_unwind=True,
        severity="severe",
    ),
]


@dataclass
class HedgeFailureIndicators:
    """Extended positioning indicators for hedge failure analysis."""

    # Standard positioning indicators
    basis_trade_size_billions: Optional[float] = None
    treasury_spec_net_percentile: Optional[float] = None
    svxy_aum_millions: Optional[float] = None

    # New indicators (v7)
    primary_dealer_gross_leverage: Optional[float] = None
    treasury_futures_herfindahl: Optional[float] = None

    # Context
    ten_year_daily_return: Optional[float] = None
    sp500_daily_return: Optional[float] = None


class HedgeFailureDetector:
    """Detect and analyse Treasury hedge failure conditions."""

    # Formal hedge failure definition thresholds
    BOND_LOSS_THRESHOLD = -0.02   # 10Y return < -2%
    EQUITY_LOSS_THRESHOLD = -0.03  # S&P 500 < -3%

    # New indicator thresholds
    DEALER_LEVERAGE_THRESHOLDS = {
        "ample": 15,    # Gross leverage < 15×
        "thin": 25,     # 15-25×
        "breach": 35,   # > 35×
    }

    HERFINDAHL_THRESHOLDS = {
        "ample": 0.10,   # Low concentration
        "thin": 0.20,    # Moderate concentration
        "breach": 0.35,  # High concentration
    }

    def is_hedge_failure(
        self,
        ten_year_return: float,
        sp500_return: float,
    ) -> bool:
        """Formal hedge failure test.

        A hedge failure occurs when:
        - 10Y Treasury total return < -2% (bonds lose money)
        - AND S&P 500 return < -3% (equities also lose money)

        This captures the breakdown of the traditional
        bond-equity diversification benefit.

        Args:
            ten_year_return: Daily 10Y Treasury total return
            sp500_return: Daily S&P 500 return

        Returns:
            True if hedge failure conditions are met
        """
        return (
            ten_year_return < self.BOND_LOSS_THRESHOLD
            and sp500_return < self.EQUITY_LOSS_THRESHOLD
        )

    def score_primary_dealer_leverage(
        self, leverage: float
    ) -> float:
        """Score primary dealer gross leverage (lower = better).

        NY Fed publishes this data from 2008+; proxy earlier.
        """
        t = self.DEALER_LEVERAGE_THRESHOLDS
        if leverage <= t["ample"]:
            return 1.0
        elif leverage <= t["thin"]:
            return 0.5 + 0.5 * (
                t["thin"] - leverage
            ) / (t["thin"] - t["ample"])
        elif leverage <= t["breach"]:
            return 0.5 * (
                t["breach"] - leverage
            ) / (t["breach"] - t["thin"])
        else:
            return 0.0

    def score_herfindahl(self, hhi: float) -> float:
        """Score Treasury futures concentration (lower = better).

        Herfindahl-Hirschman Index of top trader positions
        in Treasury futures. High concentration = crowding risk.
        """
        t = self.HERFINDAHL_THRESHOLDS
        if hhi <= t["ample"]:
            return 1.0
        elif hhi <= t["thin"]:
            return 0.5 + 0.5 * (
                t["thin"] - hhi
            ) / (t["thin"] - t["ample"])
        elif hhi <= t["breach"]:
            return 0.5 * (
                t["breach"] - hhi
            ) / (t["breach"] - t["thin"])
        else:
            return 0.0

    def bayesian_posterior(
        self,
        positioning_breached: bool = True,
    ) -> dict:
        """Compute Bayesian posterior P(hedge_fail | positioning).

        Updated with the expanded sample (N=9 episodes).

        Uses a Beta-Binomial conjugate model:
        Prior: Beta(1, 1) (uninformative)
        Likelihood: Binomial (positioning_breached, hedge_fail)

        Returns:
            Dict with posterior mean, 90% CI, and sample stats
        """
        # Count from expanded catalogue
        n_total = len(HEDGE_FAILURE_EPISODES)
        n_pos_breach = sum(
            1 for e in HEDGE_FAILURE_EPISODES
            if e.positioning_breached
        )
        n_pos_breach_and_severe = sum(
            1 for e in HEDGE_FAILURE_EPISODES
            if e.positioning_breached and e.severity == "severe"
        )

        # Beta posterior
        # P(hedge_fail | positioning_breach)
        alpha_post = 1 + n_pos_breach_and_severe  # Prior + successes
        beta_post = 1 + (n_pos_breach - n_pos_breach_and_severe)

        mean_post = alpha_post / (alpha_post + beta_post)

        # 90% CI via Beta quantiles
        try:
            from scipy.stats import beta as beta_dist
            ci_low = float(
                beta_dist.ppf(0.05, alpha_post, beta_post)
            )
            ci_high = float(
                beta_dist.ppf(0.95, alpha_post, beta_post)
            )
        except ImportError:
            # Rough approximation
            std = np.sqrt(
                alpha_post * beta_post
                / ((alpha_post + beta_post) ** 2
                   * (alpha_post + beta_post + 1))
            )
            ci_low = max(0, mean_post - 1.645 * std)
            ci_high = min(1, mean_post + 1.645 * std)

        return {
            "posterior_mean": mean_post,
            "ci_90": (ci_low, ci_high),
            "alpha": alpha_post,
            "beta": beta_post,
            "n_episodes": n_total,
            "n_positioning_breached": n_pos_breach,
            "n_severe_with_breach": n_pos_breach_and_severe,
            "interpretation": (
                "Positioning breach is a NECESSARY but not "
                "sufficient condition for severe hedge failure. "
                f"P(severe | breach) ≈ {mean_post:.2f} "
                f"(90% CI: [{ci_low:.2f}, {ci_high:.2f}])"
            ),
        }

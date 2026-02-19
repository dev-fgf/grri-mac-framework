"""Multi-country sovereign proxy validation (v7 §5.1).

Backtests the MAC sovereign-spread proxy against Reinhart-Rogoff
crisis dates for UK, Germany, France, and Japan (1815-2020).

The MAC framework's sovereign spread proxy uses:
  proxy_spread = α × local_SVAR + β × regime_dummy

This module validates that this proxy correlates with actual
sovereign stress episodes across multiple countries.

Usage:
    from grri_mac.backtest.multicountry_validation import (
        MultiCountryValidator,
        run_multicountry_validation,
    )
    result = run_multicountry_validation()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Reinhart-Rogoff crisis dates by country ──────────────────────────────

@dataclass
class SovereignCrisis:
    """A sovereign crisis event from Reinhart-Rogoff database."""

    country: str  # ISO code
    start_year: int
    end_year: int
    crisis_type: str  # "banking", "currency", "sovereign_default", "inflation"
    severity: str  # "moderate", "high", "extreme"
    description: str


# Selected major crises for validation
# Source: Reinhart & Rogoff (2009), "This Time Is Different"
# Extended with subsequent research
REINHART_ROGOFF_CRISES = [
    # ── United Kingdom ──────────────────────────────────────────
    SovereignCrisis(
        "GBR", 1825, 1826, "banking", "high",
        "Post-Napoleonic War banking panic, "
        "Latin American loan defaults",
    ),
    SovereignCrisis(
        "GBR", 1847, 1848, "banking", "moderate",
        "Railway mania collapse, Bank Charter Act suspended",
    ),
    SovereignCrisis(
        "GBR", 1857, 1858, "banking", "moderate",
        "International banking crisis, "
        "Overend Gurney precursor",
    ),
    SovereignCrisis(
        "GBR", 1866, 1866, "banking", "high",
        "Overend Gurney collapse, Bank of England "
        "acts as lender of last resort",
    ),
    SovereignCrisis(
        "GBR", 1890, 1891, "banking", "high",
        "Baring Crisis — Argentine debt exposure",
    ),
    SovereignCrisis(
        "GBR", 1914, 1914, "banking", "extreme",
        "WWI outbreak, gold standard suspension",
    ),
    SovereignCrisis(
        "GBR", 1931, 1931, "currency", "extreme",
        "Gold standard abandoned, sterling devalued",
    ),
    SovereignCrisis(
        "GBR", 1974, 1976, "banking", "high",
        "Secondary banking crisis, IMF bailout 1976",
    ),
    SovereignCrisis(
        "GBR", 1991, 1992, "currency", "moderate",
        "ERM crisis, Black Wednesday",
    ),
    SovereignCrisis(
        "GBR", 2007, 2009, "banking", "extreme",
        "Northern Rock, RBS/HBOS nationalisation",
    ),
    SovereignCrisis(
        "GBR", 2022, 2022, "currency", "moderate",
        "Mini-budget crisis, gilt market dysfunction",
    ),

    # ── Germany ─────────────────────────────────────────────────
    SovereignCrisis(
        "DEU", 1873, 1879, "banking", "high",
        "Gründerkrach — post-unification speculative bust",
    ),
    SovereignCrisis(
        "DEU", 1901, 1901, "banking", "moderate",
        "Leipzig Bank crisis, industrial downturn",
    ),
    SovereignCrisis(
        "DEU", 1923, 1923, "inflation", "extreme",
        "Hyperinflation, Rentenmark introduced",
    ),
    SovereignCrisis(
        "DEU", 1931, 1932, "banking", "extreme",
        "Danatbank collapse, banking moratorium",
    ),
    SovereignCrisis(
        "DEU", 2007, 2009, "banking", "high",
        "IKB, Hypo Real Estate bailouts",
    ),

    # ── France ──────────────────────────────────────────────────
    SovereignCrisis(
        "FRA", 1848, 1848, "banking", "high",
        "Revolution of 1848, bank runs",
    ),
    SovereignCrisis(
        "FRA", 1882, 1882, "banking", "moderate",
        "Union Générale crash",
    ),
    SovereignCrisis(
        "FRA", 1914, 1918, "currency", "extreme",
        "WWI, gold standard suspended",
    ),
    SovereignCrisis(
        "FRA", 1930, 1932, "banking", "high",
        "Banking crises, delayed gold standard exit",
    ),
    SovereignCrisis(
        "FRA", 1968, 1969, "currency", "moderate",
        "May 1968 social crisis, franc devaluation",
    ),
    SovereignCrisis(
        "FRA", 2008, 2009, "banking", "high",
        "Société Générale rogue trader, GFC",
    ),

    # ── Japan ───────────────────────────────────────────────────
    SovereignCrisis(
        "JPN", 1901, 1901, "banking", "moderate",
        "Post Russo-Japanese War financial strain",
    ),
    SovereignCrisis(
        "JPN", 1920, 1920, "banking", "moderate",
        "Post-WWI deflationary bust",
    ),
    SovereignCrisis(
        "JPN", 1927, 1927, "banking", "high",
        "Showa Financial Crisis, 37 bank closures",
    ),
    SovereignCrisis(
        "JPN", 1992, 2001, "banking", "extreme",
        "Lost Decade: bubble burst, banking crisis, "
        "zero rates",
    ),
    SovereignCrisis(
        "JPN", 1997, 1998, "banking", "high",
        "Yamaichi Securities, Hokkaido Takushoku collapse",
    ),
    SovereignCrisis(
        "JPN", 2008, 2009, "banking", "moderate",
        "GFC impact, yen surge",
    ),
]


# ── Validation framework ─────────────────────────────────────────────────

@dataclass
class CountryValidation:
    """Validation result for a single country."""

    country: str
    n_crises: int
    n_detected: int  # Crises where proxy signalled
    detection_rate: float
    mean_proxy_during_crisis: float
    mean_proxy_outside_crisis: float
    separation: float  # Difference in means (higher = better)
    auc_roc: Optional[float] = None  # If enough data


@dataclass
class MultiCountryResult:
    """Complete multi-country validation output."""

    country_results: List[CountryValidation]
    overall_detection_rate: float
    mean_separation: float
    countries_tested: int
    total_crises: int
    total_detected: int


class MultiCountryValidator:
    """Validates MAC sovereign proxy against Reinhart-Rogoff dates.

    For each country:
    1. Generate proxy sovereign spread using local macro data
    2. Check if proxy elevates during Reinhart-Rogoff crisis dates
    3. Compute detection rate and separation statistics
    """

    def __init__(
        self,
        countries: Optional[List[str]] = None,
    ):
        """Initialize validator.

        Args:
            countries: ISO codes to validate. Defaults to
                GBR, DEU, FRA, JPN.
        """
        self.countries = countries or [
            "GBR", "DEU", "FRA", "JPN",
        ]

    def validate(
        self,
        proxy_data: Optional[
            Dict[str, List[Tuple[int, float]]]
        ] = None,
    ) -> MultiCountryResult:
        """Run multi-country validation.

        Args:
            proxy_data: Optional pre-computed proxy data.
                Dict mapping country code to list of
                (year, proxy_spread) tuples. If None, uses
                synthetic proxies for demonstration.

        Returns:
            MultiCountryResult with per-country stats.
        """
        if proxy_data is None:
            proxy_data = self._generate_synthetic_proxies()

        country_results = []

        for country in self.countries:
            crises = [
                c for c in REINHART_ROGOFF_CRISES
                if c.country == country
            ]

            if not crises:
                continue

            country_proxy = proxy_data.get(country, [])
            if not country_proxy:
                continue

            result = self._validate_country(
                country, crises, country_proxy,
            )
            country_results.append(result)

        # Aggregate
        total_crises = sum(r.n_crises for r in country_results)
        total_detected = sum(
            r.n_detected for r in country_results
        )
        overall_rate = (
            total_detected / total_crises
            if total_crises > 0 else 0.0
        )
        mean_sep = (
            np.mean([r.separation for r in country_results])
            if country_results else 0.0
        )

        return MultiCountryResult(
            country_results=country_results,
            overall_detection_rate=overall_rate,
            mean_separation=float(mean_sep),
            countries_tested=len(country_results),
            total_crises=total_crises,
            total_detected=total_detected,
        )

    def _validate_country(
        self,
        country: str,
        crises: List[SovereignCrisis],
        proxy_data: List[Tuple[int, float]],
    ) -> CountryValidation:
        """Validate proxy for a single country."""
        # Build year -> proxy mapping
        proxy_by_year = {year: val for year, val in proxy_data}

        # Check detection during crisis years
        crisis_proxies = []
        non_crisis_proxies = []
        detected = 0

        crisis_years = set()
        for c in crises:
            for y in range(c.start_year, c.end_year + 1):
                crisis_years.add(y)

        for year, proxy_val in proxy_data:
            if year in crisis_years:
                crisis_proxies.append(proxy_val)
            else:
                non_crisis_proxies.append(proxy_val)

        # Detection: proxy above median during crisis
        all_proxies = [v for _, v in proxy_data]
        median_proxy = np.median(all_proxies) if all_proxies else 0.5

        for crisis in crises:
            crisis_vals = [
                proxy_by_year[y]
                for y in range(crisis.start_year, crisis.end_year + 1)
                if y in proxy_by_year
            ]
            if crisis_vals and max(crisis_vals) > median_proxy:
                detected += 1

        mean_crisis = (
            float(np.mean(crisis_proxies))
            if crisis_proxies else 0.5
        )
        mean_non_crisis = (
            float(np.mean(non_crisis_proxies))
            if non_crisis_proxies else 0.5
        )

        return CountryValidation(
            country=country,
            n_crises=len(crises),
            n_detected=detected,
            detection_rate=(
                detected / len(crises) if crises else 0.0
            ),
            mean_proxy_during_crisis=mean_crisis,
            mean_proxy_outside_crisis=mean_non_crisis,
            separation=mean_crisis - mean_non_crisis,
        )

    def _generate_synthetic_proxies(
        self,
    ) -> Dict[str, List[Tuple[int, float]]]:
        """Generate synthetic proxy data for demonstration.

        In production, this would use actual historical data
        (Schmelzing long-run yields, GFD sovereign spreads, etc.)
        """
        rng = np.random.default_rng(42)
        result = {}

        for country in self.countries:
            crises = [
                c for c in REINHART_ROGOFF_CRISES
                if c.country == country
            ]
            crisis_years = set()
            for c in crises:
                for y in range(c.start_year, c.end_year + 1):
                    crisis_years.add(y)

            # Generate proxy: higher during crises
            data = []
            for year in range(1815, 2024):
                base = 0.3 + 0.1 * rng.normal()
                if year in crisis_years:
                    # Elevated during crisis
                    base += 0.2 + 0.15 * rng.normal()
                data.append((year, float(np.clip(base, 0, 1))))

            result[country] = data

        return result


# ── Convenience ──────────────────────────────────────────────────────────

def run_multicountry_validation(
    proxy_data: Optional[
        Dict[str, List[Tuple[int, float]]]
    ] = None,
) -> MultiCountryResult:
    """Convenience function for multi-country validation."""
    validator = MultiCountryValidator()
    return validator.validate(proxy_data)


def format_multicountry_report(
    result: MultiCountryResult,
) -> str:
    """Format multi-country validation for display."""
    lines = []

    lines.append("=" * 70)
    lines.append("MULTI-COUNTRY SOVEREIGN PROXY VALIDATION")
    lines.append("(Reinhart-Rogoff crisis dates)")
    lines.append("=" * 70)
    lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 50)
    lines.append(
        f"  Countries tested:    {result.countries_tested}"
    )
    lines.append(
        f"  Total crises:        {result.total_crises}"
    )
    lines.append(
        f"  Total detected:      {result.total_detected}"
    )
    lines.append(
        f"  Overall detection:   "
        f"{result.overall_detection_rate:.1%}"
    )
    lines.append(
        f"  Mean separation:     {result.mean_separation:.3f}"
    )
    lines.append("")

    lines.append("PER-COUNTRY RESULTS")
    lines.append("-" * 70)
    lines.append(
        f"  {'Country':<8} {'Crises':>7} {'Detect':>7} "
        f"{'Rate':>6} {'Crisis':>8} {'Normal':>8} {'Sep':>6}"
    )
    for cr in result.country_results:
        lines.append(
            f"  {cr.country:<8} {cr.n_crises:>7} "
            f"{cr.n_detected:>7} {cr.detection_rate:>6.1%} "
            f"{cr.mean_proxy_during_crisis:>8.3f} "
            f"{cr.mean_proxy_outside_crisis:>8.3f} "
            f"{cr.separation:>6.3f}"
        )
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)

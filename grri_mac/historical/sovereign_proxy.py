"""Sovereign Bond Proxy for Historical Multi-Country MAC (v6 §16.2).

Constructs approximate aggregate MAC scores for non-US economies (and
pre-1945 US) using sovereign bond spreads as a single-asset-class proxy.

Architecture:
* Era-dependent benchmark: UK Consol (1815–1913), blend (1914–1944),
  US 10Y (1945+)
* Quadratic mapping: MAC_proxy = a − b·SS + c·SS²  (per-country)
* Overlap calibration (1990–2025) where full pillar MAC is available
* 80% confidence bands from regression residual SE

Starting with UK as proof-of-concept (deepest historical data: Consols
from ~1729, Bank Rate from 1694).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class BenchmarkEra(Enum):
    """Era-dependent risk-free benchmark (v6 §16.2.3)."""
    UK_CONSOL = ("UK Consol yield", 1815, 1913)
    BLEND = ("UK gilt 50% + US Treasury 50%", 1914, 1944)
    US_TREASURY = ("US 10Y Treasury yield", 1945, 2100)

    def __init__(self, description: str, start_year: int, end_year: int):
        self.description = description
        self.start_year = start_year
        self.end_year = end_year


def get_benchmark_era(year: int) -> BenchmarkEra:
    """Return the appropriate benchmark era for a given year."""
    if year < 1914:
        return BenchmarkEra.UK_CONSOL
    elif year < 1945:
        return BenchmarkEra.BLEND
    else:
        return BenchmarkEra.US_TREASURY


# ---------------------------------------------------------------------------
# Data sources catalogue (v6 §16.2.2)
# ---------------------------------------------------------------------------

@dataclass
class DataSourceInfo:
    """Documentation of a historical data source."""
    name: str
    coverage: str
    period: str
    frequency: str
    key_series: str


DATA_SOURCES: List[DataSourceInfo] = [
    DataSourceInfo(
        "Bank of England Millennium of Macroeconomic Data",
        "UK", "1694–2016", "Annual (some monthly)",
        "Consol yields (~1729), Bank Rate (1694), gilt yields, inflation, GDP",
    ),
    DataSourceInfo(
        "Shiller (Yale Online Data)",
        "US", "1871–present", "Monthly",
        "Long-term government bond yield, S&P composite, CPI, earnings",
    ),
    DataSourceInfo(
        "NBER Macrohistory Database",
        "US, UK", "1857–1968", "Monthly",
        "Railroad bond yields, government bond yields, call money rates",
    ),
    DataSourceInfo(
        "Homer & Sylla (2005)",
        "Global", "Antiquity–2005", "Varies",
        "Sovereign yields for UK, France, Netherlands, Germany, Italy, Japan",
    ),
    DataSourceInfo(
        "Meyer, Reinhart & Trebesch (2019)",
        "91 countries", "1815–2016", "Annual/monthly",
        "Sovereign bond prices, yields, total returns, haircuts, defaults",
    ),
    DataSourceInfo(
        "IMF IFS",
        "180+ countries", "1948–present", "Monthly/quarterly",
        "Government bond yields, CPI, reserves, exchange rates",
    ),
]


# ---------------------------------------------------------------------------
# Country-specific stress episodes for calibration (v6 §16.2.5)
# ---------------------------------------------------------------------------

@dataclass
class HistoricalStressEpisode:
    """Known stress episode for calibrating the sovereign proxy."""
    name: str
    year: int
    expected_mac_range: Tuple[float, float]
    notes: str


UK_STRESS_EPISODES: List[HistoricalStressEpisode] = [
    HistoricalStressEpisode("South Sea Bubble", 1720, (0.05, 0.20),
                            "Extreme spike in Consol yield"),
    HistoricalStressEpisode("Napoleonic Wars peak", 1797, (0.25, 0.40),
                            "War premium on gilts"),
    HistoricalStressEpisode("Barings Crisis", 1890, (0.30, 0.45),
                            "Sharp spike in sovereign spread"),
    HistoricalStressEpisode("WWI outbreak", 1914, (0.15, 0.30),
                            "Exchange closure; yield spike"),
    HistoricalStressEpisode("Sterling crisis", 1931, (0.20, 0.35),
                            "Gold standard exit; yield spike"),
    HistoricalStressEpisode("Suez Crisis", 1956, (0.40, 0.55),
                            "Sterling pressure; yield spike"),
    HistoricalStressEpisode("IMF bailout", 1976, (0.20, 0.35),
                            "Extreme yield; sterling collapse"),
    HistoricalStressEpisode("ERM exit", 1992, (0.30, 0.45),
                            "Sharp yield spike"),
    HistoricalStressEpisode("Gilt crisis (LDI)", 2022, (0.15, 0.30),
                            "Extreme yield spike; BoE intervention"),
]


# ---------------------------------------------------------------------------
# Quadratic mapping: SS → MAC proxy (v6 §16.2.4)
# ---------------------------------------------------------------------------

@dataclass
class QuadraticCoefficients:
    """Per-country quadratic mapping coefficients.

    MAC_proxy = a − b·SS + c·SS²

    where SS is the sovereign stress spread in percentage points.
    """
    a: float   # intercept (MAC at zero spread)
    b: float   # linear term (higher spread → lower MAC)
    c: float   # quadratic term (captures non-linearity at extremes)
    residual_se: float = 0.10   # residual standard error for confidence bands


# Default coefficients (to be updated via overlap calibration)
# These are structurally reasonable priors
DEFAULT_COEFFICIENTS: Dict[str, QuadraticCoefficients] = {
    "UK": QuadraticCoefficients(a=0.75, b=0.12, c=0.005, residual_se=0.10),
    "DE": QuadraticCoefficients(a=0.78, b=0.15, c=0.006, residual_se=0.09),
    "FR": QuadraticCoefficients(a=0.74, b=0.13, c=0.005, residual_se=0.11),
    "IT": QuadraticCoefficients(a=0.70, b=0.10, c=0.004, residual_se=0.12),
    "JP": QuadraticCoefficients(a=0.72, b=0.18, c=0.008, residual_se=0.11),
}


# ---------------------------------------------------------------------------
# Sovereign spread data structures
# ---------------------------------------------------------------------------

@dataclass
class SovereignSpreadObservation:
    """A single observation of sovereign stress spread."""
    date: datetime
    country_code: str
    gov_yield_pct: float            # y_gov    (percentage points)
    benchmark_yield_pct: float      # y_bench  (percentage points)
    spread_pct: float               # SS = y_gov − y_bench
    benchmark_era: BenchmarkEra
    data_quality: str = "good"      # excellent, good, fair, poor


@dataclass
class SovereignProxyMAC:
    """MAC proxy score derived from sovereign bond spread."""
    date: datetime
    country_code: str
    mac_proxy: float                # point estimate
    confidence_80_low: float        # 80% CI lower bound
    confidence_80_high: float       # 80% CI upper bound
    spread_pct: float               # input sovereign spread
    benchmark_era: BenchmarkEra
    data_quality: str
    is_aggregate_only: bool = True  # no pillar decomposition available


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_sovereign_spread(
    gov_yield: float,
    benchmark_yield: float,
) -> float:
    """Compute sovereign stress spread: SS = y_gov − y_bench."""
    return gov_yield - benchmark_yield


def map_spread_to_mac(
    spread_pct: float,
    coefficients: QuadraticCoefficients,
) -> Tuple[float, float, float]:
    """Map sovereign stress spread to MAC proxy score.

    Args:
        spread_pct: Sovereign stress spread in percentage points.
        coefficients: Quadratic mapping coefficients for this country.

    Returns:
        (mac_proxy, ci_80_low, ci_80_high) — point estimate and 80% CIs.
    """
    ss = spread_pct
    mac = coefficients.a - coefficients.b * ss + coefficients.c * ss ** 2
    mac = max(0.0, min(1.0, mac))

    # 80% CI: ±1.28 × residual SE  (z_{0.10} = 1.28)
    half_width = 1.28 * coefficients.residual_se
    ci_low = max(0.0, mac - half_width)
    ci_high = min(1.0, mac + half_width)

    return mac, ci_low, ci_high


def compute_proxy_mac(
    observation: SovereignSpreadObservation,
    coefficients: Optional[QuadraticCoefficients] = None,
) -> SovereignProxyMAC:
    """Compute a proxy MAC score from a sovereign spread observation.

    Args:
        observation: Sovereign spread data point.
        coefficients: Country-specific mapping coefficients.  If None,
            falls back to ``DEFAULT_COEFFICIENTS``.

    Returns:
        SovereignProxyMAC with point estimate and confidence bands.
    """
    if coefficients is None:
        coefficients = DEFAULT_COEFFICIENTS.get(
            observation.country_code,
            QuadraticCoefficients(a=0.73, b=0.12, c=0.005),
        )

    mac, ci_low, ci_high = map_spread_to_mac(
        observation.spread_pct, coefficients,
    )

    return SovereignProxyMAC(
        date=observation.date,
        country_code=observation.country_code,
        mac_proxy=round(mac, 4),
        confidence_80_low=round(ci_low, 4),
        confidence_80_high=round(ci_high, 4),
        spread_pct=observation.spread_pct,
        benchmark_era=observation.benchmark_era,
        data_quality=observation.data_quality,
    )


# ---------------------------------------------------------------------------
# Overlap calibration (v6 §16.2.4 Step 1)
# ---------------------------------------------------------------------------

def calibrate_coefficients(
    overlap_spreads: List[float],
    overlap_macs: List[float],
) -> QuadraticCoefficients:
    """Estimate quadratic mapping from overlap period data.

    Fits MAC = a − b·SS + c·SS² via least-squares.

    Args:
        overlap_spreads: Sovereign spreads (pct) in overlap period.
        overlap_macs: Full-pillar MAC scores in overlap period.

    Returns:
        QuadraticCoefficients with fitted a, b, c and residual SE.
    """
    n = len(overlap_spreads)
    if n < 10:
        raise ValueError(f"Need at least 10 overlap observations, got {n}")

    # Design matrix: [1, -SS, SS²]
    X = []
    for ss in overlap_spreads:
        X.append([1.0, -ss, ss ** 2])

    # Solve via normal equations
    # X'X β = X'y
    XtX = [[0.0] * 3 for _ in range(3)]
    Xty = [0.0] * 3
    for i in range(n):
        for j in range(3):
            Xty[j] += X[i][j] * overlap_macs[i]
            for k in range(3):
                XtX[j][k] += X[i][j] * X[i][k]

    # Simple 3×3 solve (Cramer's rule or manual)
    beta = _solve_3x3(XtX, Xty)

    # Residual SE
    rss = 0.0
    for i in range(n):
        fitted = sum(beta[j] * X[i][j] for j in range(3))
        rss += (overlap_macs[i] - fitted) ** 2
    residual_se = math.sqrt(rss / max(n - 3, 1))

    return QuadraticCoefficients(
        a=round(beta[0], 4),
        b=round(beta[1], 4),  # design matrix already has -SS, so beta[1] = b directly
        c=round(beta[2], 6),
        residual_se=round(residual_se, 4),
    )


def _solve_3x3(A: List[List[float]], b: List[float]) -> List[float]:
    """Solve 3×3 linear system Ax = b via Gaussian elimination."""
    # Make augmented matrix
    M = [row[:] + [b[i]] for i, row in enumerate(A)]

    # Forward elimination
    for col in range(3):
        # Partial pivoting
        max_row = col
        for row in range(col + 1, 3):
            if abs(M[row][col]) > abs(M[max_row][col]):
                max_row = row
        M[col], M[max_row] = M[max_row], M[col]

        pivot = M[col][col]
        if abs(pivot) < 1e-12:
            raise ValueError("Singular matrix in calibration")

        for row in range(col + 1, 3):
            factor = M[row][col] / pivot
            for j in range(col, 4):
                M[row][j] -= factor * M[col][j]

    # Back substitution
    x = [0.0] * 3
    for i in range(2, -1, -1):
        x[i] = M[i][3]
        for j in range(i + 1, 3):
            x[i] -= M[i][j] * x[j]
        x[i] /= M[i][i]

    return x


# ---------------------------------------------------------------------------
# Historical time-series builder
# ---------------------------------------------------------------------------

def build_proxy_mac_series(
    spread_series: List[SovereignSpreadObservation],
    coefficients: Optional[QuadraticCoefficients] = None,
) -> List[SovereignProxyMAC]:
    """Build a complete proxy MAC time series from spread observations.

    Args:
        spread_series: Chronologically ordered spread observations.
        coefficients: Country-specific quadratic coefficients.

    Returns:
        List of SovereignProxyMAC scores.
    """
    return [compute_proxy_mac(obs, coefficients) for obs in spread_series]


# ---------------------------------------------------------------------------
# Limitations documentation (v6 §16.2.6)
# ---------------------------------------------------------------------------

PROXY_LIMITATIONS: List[Dict[str, str]] = [
    {
        "limitation": "Single-indicator aggregation loses pillar decomposition",
        "impact": "Cannot identify which buffer is depleted",
        "mitigation": "Proxy MAC flagged as aggregate-only; no pillar attribution",
    },
    {
        "limitation": "Sovereign spreads include FX risk",
        "impact": "Pre-euro European spreads conflate credit and currency risk",
        "mitigation": "Separate calibration by FX regime era",
    },
    {
        "limitation": "Benchmark choice affects levels",
        "impact": "UK Consol vs US Treasury produces different spread levels",
        "mitigation": "Era-specific benchmark with overlap validation",
    },
    {
        "limitation": "Illiquid historical markets",
        "impact": "18th/19th-century markets had wider bid-ask",
        "mitigation": "Widen confidence bands for pre-1900 data",
    },
    {
        "limitation": "War distortions",
        "impact": "Capital controls, forced lending, yield caps distort signals",
        "mitigation": "Flag wartime periods with data quality warnings",
    },
    {
        "limitation": "Japanese zero-rate trap",
        "impact": "Near-zero JGB yields provide little signal post-1995",
        "mitigation": "Supplement with direct indicators for modern Japan",
    },
]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_proxy_mac_report(
    series: List[SovereignProxyMAC],
    country_name: str,
    stress_episodes: Optional[List[HistoricalStressEpisode]] = None,
) -> str:
    """Format a human-readable summary of proxy MAC results."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append(f"  SOVEREIGN BOND PROXY MAC — {country_name.upper()}")
    lines.append(f"  (v6 §16.2)")
    lines.append("=" * 70)
    lines.append("")

    if not series:
        lines.append("  No observations available.")
        return "\n".join(lines)

    lines.append(f"  Observations: {len(series)}")
    lines.append(f"  Date range: {series[0].date.date()} to {series[-1].date.date()}")
    lines.append(f"  Country: {series[0].country_code}")
    lines.append("")

    # Summary statistics
    macs = [s.mac_proxy for s in series]
    lines.append(f"  MAC proxy: min={min(macs):.3f}  avg={sum(macs)/len(macs):.3f}"
                 f"  max={max(macs):.3f}")
    lines.append(f"  Avg CI width: "
                 f"{sum(s.confidence_80_high - s.confidence_80_low for s in series)/len(series):.3f}")
    lines.append("")

    # Stress episode validation
    if stress_episodes:
        lines.append("  STRESS EPISODE VALIDATION")
        lines.append("  " + "-" * 55)
        for ep in stress_episodes:
            # Find closest observation
            closest = min(series, key=lambda s: abs(s.date.year - ep.year))
            in_range = ep.expected_mac_range[0] <= closest.mac_proxy <= ep.expected_mac_range[1]
            marker = "✓" if in_range else "✗"
            lines.append(
                f"  {marker} {ep.name} ({ep.year}): proxy={closest.mac_proxy:.3f}"
                f"  expected=[{ep.expected_mac_range[0]:.2f}, {ep.expected_mac_range[1]:.2f}]"
            )
        lines.append("")

    lines.append("  Note: Proxy MAC is aggregate-only (no pillar decomposition).")
    lines.append("=" * 70)
    return "\n".join(lines)

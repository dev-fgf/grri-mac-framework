"""Historical inflation proxy chain (1850–present).

Provides a continuous inflation series for the policy pillar's
binding constraint architecture across all historical eras.

Proxy chain (most recent first):
- Core PCE (1959+)          — FRED PCEPILFE
- CPI-U (1947–1959)         — FRED CPIAUCSL
- CPI NSA (1913–1947)       — FRED CPIAUCNS
- Rees Cost of Living (1890–1913)  — External CSV (Rees 1961)
- Warren-Pearson WPI × 1/1.5 (1850–1890)  — External CSV

Reference: MAC Methodology v6.0 §4.5.3
"""

import os
import csv
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Data directory for external CSV files
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ── Pre-CPI data (annual, hardcoded from published sources) ──────────────

# Rees (1961) "Real Wages in Manufacturing, 1890–1914"
# Consumer cost-of-living index, base 1914 = 100
# YoY percentage change derived from index levels
REES_COST_OF_LIVING_YOY = {
    1890: 0.0,   # Base estimate
    1891: 0.2,
    1892: -0.5,
    1893: -1.2,
    1894: -3.1,
    1895: -1.8,
    1896: -1.5,
    1897: 0.2,
    1898: 0.8,
    1899: 1.2,
    1900: 2.5,
    1901: 1.8,
    1902: 2.6,
    1903: 1.5,
    1904: 0.8,
    1905: 0.5,
    1906: 2.0,
    1907: 4.2,
    1908: -1.2,
    1909: 0.5,
    1910: 4.6,
    1911: 0.0,
    1912: 2.1,
    1913: 1.9,
}

# Warren-Pearson Wholesale Price Index (1850–1890)
# Scaled by 1/1.5 to approximate consumer prices per v6 methodology.
# Raw WPI YoY change × (1/1.5) conversion factor.
WARREN_PEARSON_WPI_YOY_SCALED = {
    1850: 0.0,
    1851: -1.3,
    1852: 2.0,
    1853: 1.3,
    1854: 7.3,
    1855: 2.0,
    1856: -1.3,
    1857: 2.7,
    1858: -6.7,
    1859: 0.7,
    1860: -0.7,
    1861: 2.0,
    1862: 9.3,   # Civil War inflation
    1863: 15.3,
    1864: 17.3,
    1865: -2.0,
    1866: -5.3,
    1867: -5.3,
    1868: -2.7,
    1869: -2.7,
    1870: -3.3,
    1871: -4.0,
    1872: 1.3,
    1873: -0.7,
    1874: -4.7,
    1875: -3.3,
    1876: -4.0,
    1877: -2.7,
    1878: -4.0,  # Long deflation
    1879: -0.7,
    1880: 5.3,
    1881: 0.7,
    1882: 1.3,
    1883: -2.7,
    1884: -4.7,
    1885: -2.0,
    1886: -2.7,
    1887: 0.7,
    1888: 0.7,
    1889: -2.7,
    1890: 0.0,
}


def get_inflation_for_date(
    date: datetime,
    fred_client=None,
    target_pct: float = 2.0,
) -> Optional[float]:
    """Get inflation deviation from target for a given date.

    Returns Core PCE vs 2% target deviation in basis points.
    Falls through proxy chains for historical dates.

    Args:
        date: Observation date
        fred_client: Optional FREDClient for fetching FRED data
        target_pct: Inflation target (default 2.0%)

    Returns:
        Deviation from target in basis points (e.g., +150 means 3.5% inflation
        against 2% target). Positive = above target, negative = below.
        Returns None if no data available.
    """
    year = date.year

    # ── Era 1: Core PCE (1959+) ──────────────────────────────────
    if year >= 1959 and fred_client:
        try:
            # Try Core PCE first
            val = fred_client.get_series_value("PCEPILFE", date)
            if val is not None:
                return (val - target_pct) * 100  # Convert to bps
        except Exception:
            pass
        # Fallback to CPI-U even in this era
        try:
            val = fred_client.get_series_value("CPIAUCSL", date)
            if val is not None:
                yoy = _get_yoy_from_index(fred_client, "CPIAUCSL", date)
                if yoy is not None:
                    return (yoy - target_pct) * 100
        except Exception:
            pass

    # ── Era 2: CPI-U (1947–1959) ────────────────────────────────
    if 1947 <= year < 1959 and fred_client:
        try:
            yoy = _get_yoy_from_index(fred_client, "CPIAUCSL", date)
            if yoy is not None:
                return (yoy - target_pct) * 100
        except Exception:
            pass

    # ── Era 3: CPI NSA (1913–1947) ──────────────────────────────
    if 1913 <= year < 1947 and fred_client:
        try:
            yoy = _get_yoy_from_index(fred_client, "CPIAUCNS", date)
            if yoy is not None:
                return (yoy - target_pct) * 100
        except Exception:
            pass

    # ── Era 4: Rees Cost of Living (1890–1913) ──────────────────
    if 1890 <= year <= 1913:
        yoy = REES_COST_OF_LIVING_YOY.get(year)
        if yoy is not None:
            return (yoy - target_pct) * 100

    # ── Era 5: Warren-Pearson WPI × 1/1.5 (1850–1890) ──────────
    if 1850 <= year <= 1890:
        yoy = WARREN_PEARSON_WPI_YOY_SCALED.get(year)
        if yoy is not None:
            return (yoy - target_pct) * 100

    return None


def get_inflation_proxy_chain_name(date: datetime) -> str:
    """Return the name of the inflation proxy used for a given date."""
    year = date.year
    if year >= 1959:
        return "Core PCE (PCEPILFE)"
    elif year >= 1947:
        return "CPI-U (CPIAUCSL)"
    elif year >= 1913:
        return "CPI NSA (CPIAUCNS)"
    elif year >= 1890:
        return "Rees Cost of Living Index (1890-1914)"
    elif year >= 1850:
        return "Warren-Pearson WPI × 1/1.5"
    else:
        return "No proxy available"


def _get_yoy_from_index(
    fred_client,
    series_id: str,
    date: datetime,
) -> Optional[float]:
    """Calculate year-over-year percentage change from a price index.

    Args:
        fred_client: Client with get_series_value(series_id, date) method
        series_id: FRED series ID for a price index
        date: Target date

    Returns:
        YoY percentage change, or None if data unavailable
    """
    from datetime import timedelta

    try:
        current = fred_client.get_series_value(series_id, date)
        year_ago_date = datetime(date.year - 1, date.month, date.day)
        previous = fred_client.get_series_value(series_id, year_ago_date)

        if current is not None and previous is not None and previous > 0:
            return ((current / previous) - 1.0) * 100
    except Exception:
        pass

    return None

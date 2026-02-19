"""CBOE VIX term structure client for 0DTE/gamma risk proxy.

Fetches VIX9D, VIX, VIX3M, and VVIX from CBOE's public CDN to compute
gamma concentration metrics. No API key needed.

Key ratios:
- VIX9D/VIX > 1.0 → near-term gamma elevated (0DTE-driven)
- VIX/VIX3M > 1.0 → term structure in backwardation (stress regime)
- VVIX > 100 → dealer gamma hedging is intense
"""

import logging
from io import StringIO
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

CBOE_CDN = "https://cdn.cboe.com/api/global/us_indices/daily_prices"

# CBOE index CSV files (all publicly available, no auth)
CBOE_INDICES = {
    "VIX9D": f"{CBOE_CDN}/VIX9D_History.csv",
    "VIX3M": f"{CBOE_CDN}/VIX3M_History.csv",
    "VVIX": f"{CBOE_CDN}/VVIX_History.csv",
}


def _fetch_latest_close(url: str) -> Optional[float]:
    """Fetch the most recent close value from a CBOE history CSV.

    Args:
        url: CBOE CDN CSV URL

    Returns:
        Most recent close value, or None on failure
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        df = pd.read_csv(StringIO(resp.text))

        # CBOE CSVs use DATE column with MM/DD/YYYY format
        # VVIX CSV has only DATE,VVIX columns (no OPEN/HIGH/LOW/CLOSE)
        if "CLOSE" in df.columns:
            value_col = "CLOSE"
        elif "VVIX" in df.columns:
            value_col = "VVIX"
        else:
            # Use last numeric column
            value_col = df.columns[-1]

        df["DATE"] = pd.to_datetime(df["DATE"], format="mixed")
        df = df.sort_values("DATE")

        # Get most recent non-null value
        valid = df[df[value_col].notna()]
        if valid.empty:
            return None

        return float(valid.iloc[-1][value_col])
    except Exception as e:
        logger.warning("Failed to fetch CBOE data from %s: %s", url, e)
        return None


def get_gamma_indicators(vix_level: Optional[float] = None) -> dict:
    """Fetch VIX term structure indicators from CBOE.

    Args:
        vix_level: Current VIX level (if already known from FRED).
                   If None, uses VIX3M and VIX9D alone.

    Returns:
        Dict with available gamma proxy indicators:
        - vix9d: 9-day VIX level
        - vix3m: 3-month VIX level
        - vvix: Vol-of-vol level
        - gamma_ratio: VIX9D/VIX (>1 = near-term gamma elevated)
        - term_slope: VIX/VIX3M (>1 = backwardation)
    """
    result = {}

    vix9d = _fetch_latest_close(CBOE_INDICES["VIX9D"])
    vix3m = _fetch_latest_close(CBOE_INDICES["VIX3M"])
    vvix = _fetch_latest_close(CBOE_INDICES["VVIX"])

    if vix9d is not None:
        result["vix9d"] = round(vix9d, 2)

    if vix3m is not None:
        result["vix3m"] = round(vix3m, 2)

    if vvix is not None:
        result["vvix"] = round(vvix, 2)

    # Compute gamma ratio (VIX9D / VIX)
    # When > 1.0, near-term vol is elevated relative to 30-day
    # Indicates 0DTE and short-dated gamma concentration
    if vix9d is not None and vix_level is not None and vix_level > 0:
        result["gamma_ratio"] = round(vix9d / vix_level, 3)

    # Compute term structure slope (VIX / VIX3M)
    # When > 1.0 (backwardation), market prices near-term risk > medium-term
    if vix_level is not None and vix3m is not None and vix3m > 0:
        result["term_slope"] = round(vix_level / vix3m, 3)

    return result

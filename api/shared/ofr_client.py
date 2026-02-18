"""OFR Hedge Fund Monitor client for prime brokerage leverage.

Fetches aggregate qualifying hedge fund (QHF) leverage ratios from
the Office of Financial Research Hedge Fund Monitor API. Based on
SEC Form PF aggregate data. No API key needed.

Data: Quarterly, ~3-month lag. GAV-weighted mean leverage ratio for
large QHFs (>$500M NAV). Latest values are typically 15-20x.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OFR_HFM_URL = "https://data.financialresearch.gov/hf/v1/series/timeseries/"

# Form PF mnemonics for hedge fund leverage
# GAV-weighted mean leverage ratio for large QHFs (>$500M NAV)
LEVERAGE_MNEMONIC = "FPF-ALLQHF_GAVN10_LEVERAGERATIO_AVERAGE"


def _fetch_ofr_series(mnemonic: str) -> list:
    """Fetch time series from OFR Hedge Fund Monitor API.

    Args:
        mnemonic: OFR series mnemonic code

    Returns:
        List of [date_str, value] pairs, or empty list on failure
    """
    try:
        resp = requests.get(
            OFR_HFM_URL,
            params={"mnemonic": mnemonic},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.warning("Failed to fetch OFR series %s: %s", mnemonic, e)
        return []


def get_hf_leverage_ratio() -> Optional[float]:
    """Get latest aggregate hedge fund leverage ratio from OFR.

    Returns the GAV-weighted mean leverage ratio for large qualifying
    hedge funds (>$500M NAV). Sourced from SEC Form PF aggregates.

    Returns:
        Leverage ratio (e.g. 18.0 = 18x), or None on failure
    """
    series = _fetch_ofr_series(LEVERAGE_MNEMONIC)
    if not series:
        return None

    try:
        # Last entry is the most recent quarter
        latest = series[-1]
        value = float(latest[1])
        return round(value, 2)
    except (IndexError, TypeError, ValueError) as e:
        logger.warning("Failed to parse OFR leverage data: %s", e)
        return None

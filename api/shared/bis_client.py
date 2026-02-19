"""BIS OTC Derivatives Statistics client.

Fetches credit and equity-linked OTC derivatives notional outstanding
from the Bank for International Settlements public data portal.
No API key needed. Semi-annual data, ~6-month lag.

- Credit derivatives notional → CLO/structured credit proxy
- Equity derivatives notional → Total return swap (TRS) proxy
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BIS_BASE = "https://data.bis.org/topics/OTC_DER/BIS,WS_OTC_DERIV2,1.0"

# BIS SDMX keys for OTC derivatives notional outstanding (net-net basis)
# Format: FREQ.TYPE.INSTR.RISK.REP_CTY.SECTOR_CPY.CPC.SECTOR_UDL.CURR1.CURR2.MAT.RATING.METHOD.BASIS
BIS_KEYS = {
    # Credit derivatives (CDS, CLO proxy) — DER_RISK=U
    "credit": "H.A.A.U.5J.A.5J.A.TO1.TO1.A.A.3.C",
    # Equity-linked derivatives (TRS proxy) — DER_RISK=E
    "equity": "H.A.A.E.5J.A.5J.A.TO1.TO1.A.A.3.C",
}


def _fetch_bis_latest(key: str) -> Optional[float]:
    """Fetch latest notional outstanding value from BIS CSV endpoint.

    Args:
        key: BIS SDMX timeseries key

    Returns:
        Latest notional in millions USD, or None on failure
    """
    url = f"{BIS_BASE}/{key}"
    params = {"file_format": "csv", "format": "long"}

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()

        # BIS CSV has metadata header rows followed by data rows
        # Data rows start with "BIS,WS_OTC_DERIV2"
        lines = resp.text.splitlines()
        data_lines = [line for line in lines if line.startswith('"BIS,WS_OTC_DERIV2')]

        if not data_lines:
            logger.warning("No data rows in BIS response for key %s", key)
            return None

        # Last data line is the most recent period
        # OBS_VALUE is the last CSV field
        last_line = data_lines[-1]
        # Split on comma, but respect quoted fields
        fields = []
        in_quote = False
        current = ""
        for ch in last_line:
            if ch == '"':
                in_quote = not in_quote
            elif ch == ',' and not in_quote:
                fields.append(current)
                current = ""
            else:
                current += ch
        fields.append(current)

        # OBS_VALUE is the last field
        value_str = fields[-1].strip()
        return float(value_str)
    except Exception as e:
        logger.warning("Failed to fetch BIS data for key %s: %s", key, e)
        return None


def get_otc_derivatives_indicators() -> dict:
    """Fetch OTC derivatives notional outstanding from BIS.

    Returns:
        Dict with available indicators:
        - credit_deriv_notional_trillions: Credit derivatives notional ($T)
        - equity_deriv_notional_trillions: Equity derivatives notional ($T)
    """
    result = {}

    credit_millions = _fetch_bis_latest(BIS_KEYS["credit"])
    if credit_millions is not None:
        result["credit_deriv_notional_trillions"] = round(
            credit_millions / 1_000_000, 2
        )

    equity_millions = _fetch_bis_latest(BIS_KEYS["equity"])
    if equity_millions is not None:
        result["equity_deriv_notional_trillions"] = round(
            equity_millions / 1_000_000, 2
        )

    return result

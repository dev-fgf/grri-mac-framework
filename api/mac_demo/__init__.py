import json
import sys
import os
from datetime import datetime
import azure.functions as func

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Get current MAC calculation with live data."""

    # Try to fetch live data
    client = FREDClient()
    indicators = client.get_all_indicators()

    is_live = bool(indicators)

    if not indicators:
        # Fallback to demo data
        indicators = {
            "sofr_iorb_spread_bps": 5,
            "cp_treasury_spread_bps": 25,
            "term_premium_10y_bps": 45,
            "ig_oas_bps": 95,
            "hy_oas_bps": 320,
            "vix_level": 18.5,
            "fed_funds_vs_neutral_bps": 175,
            "fed_balance_sheet_gdp_pct": 28,
            "core_pce_vs_target_bps": 65,
        }

    # Calculate MAC
    result = calculate_mac(indicators)

    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "is_live": is_live,
        "data_source": "FRED API" if is_live else "Demo Data",
        **result,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

import json
import sys
import os
from datetime import datetime
import azure.functions as func
import traceback

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.fred_client import FREDClient
    from shared.mac_scorer import calculate_mac
    from shared.database import get_database
    IMPORTS_OK = True
    IMPORT_ERROR = None
except Exception as e:
    IMPORTS_OK = False
    IMPORT_ERROR = str(e)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Get current MAC calculation with live data."""
    
    # Check imports first
    if not IMPORTS_OK:
        return func.HttpResponse(
            json.dumps({"error": "Import failed", "details": IMPORT_ERROR}),
            status_code=500,
            mimetype="application/json"
        )
    
    try:
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
                "policy_room_bps": 433,  # 4.33% fed funds
                "fed_balance_sheet_gdp_pct": 28,
                "core_pce_vs_target_bps": 65,
            }

        # Calculate MAC
        result = calculate_mac(indicators)
        result["is_live"] = is_live

        # Save snapshot to database
        db = get_database()
        saved = db.save_snapshot(result)

        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": is_live,
            "data_source": "FRED API" if is_live else "Demo Data",
            "saved_to_db": saved,
            "db_connected": db.connected,
            **result,
        }

        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json"
        )
    
    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": "Runtime error",
                "details": str(e),
                "traceback": traceback.format_exc()
            }),
            status_code=500,
            mimetype="application/json"
        )

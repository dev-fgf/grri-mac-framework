"""Refresh market data from FRED and CFTC, store in Azure Table Storage."""

import json
import sys
import os
from datetime import datetime
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.database import get_database


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Fetch latest market data from FRED and store in Azure Table.
    
    This endpoint should be called periodically (e.g., daily via GitHub Actions)
    to keep the indicator cache fresh. The main MAC endpoint then reads from
    the cache instead of fetching live data.
    """
    db = get_database()
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "sources": {},
        "success": True,
    }
    
    # === FRED Data ===
    try:
        client = FREDClient()
        indicators = client.get_all_indicators()
        
        if indicators:
            saved = db.save_indicators(indicators, source="FRED")
            results["sources"]["FRED"] = {
                "status": "success" if saved else "save_failed",
                "indicator_count": len(indicators),
                "indicators": indicators,
            }
        else:
            results["sources"]["FRED"] = {
                "status": "no_data",
                "error": "FRED API returned no data (check API key)",
            }
            results["success"] = False
    except Exception as e:
        results["sources"]["FRED"] = {
            "status": "error",
            "error": str(e),
        }
        results["success"] = False
    
    # === CFTC Data ===
    try:
        from shared.cftc_client import get_cftc_client, COT_REPORTS_AVAILABLE
        
        if COT_REPORTS_AVAILABLE:
            cftc_client = get_cftc_client()
            positioning_data = cftc_client.get_positioning_indicators(lookback_weeks=52)
            
            if positioning_data:
                # Convert positioning data to flat indicators
                cftc_indicators = {}
                for contract_key, data in positioning_data.items():
                    cftc_indicators[f"{contract_key}_percentile"] = data.get("percentile")
                    cftc_indicators[f"{contract_key}_signal"] = data.get("signal")
                    cftc_indicators[f"{contract_key}_net_position"] = data.get("net_position")
                
                # Get aggregate score
                score, status = cftc_client.get_aggregate_positioning_score(lookback_weeks=52)
                cftc_indicators["positioning_score"] = score
                cftc_indicators["positioning_status"] = status
                
                saved = db.save_indicators(cftc_indicators, source="CFTC")
                results["sources"]["CFTC"] = {
                    "status": "success" if saved else "save_failed",
                    "indicator_count": len(cftc_indicators),
                    "contracts": list(positioning_data.keys()),
                    "aggregate_score": score,
                    "aggregate_status": status,
                }
            else:
                results["sources"]["CFTC"] = {
                    "status": "no_data",
                    "error": "CFTC fetch returned no data",
                }
        else:
            results["sources"]["CFTC"] = {
                "status": "unavailable",
                "error": "cot-reports package not installed",
            }
    except Exception as e:
        results["sources"]["CFTC"] = {
            "status": "error",
            "error": str(e),
        }
    
    # Summary
    results["db_connected"] = db.connected
    
    status_code = 200 if results["success"] else 207  # 207 = partial success
    
    return func.HttpResponse(
        json.dumps(results, indent=2),
        status_code=status_code,
        mimetype="application/json"
    )

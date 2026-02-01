"""Refresh market data from FRED and CFTC, store in Azure Table Storage."""

import json
import sys
import os
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.database import get_database

# Key FRED series to keep updated in Azure Tables
FRED_SERIES_TO_CACHE = [
    "VIXCLS",      # VIX (volatility)
    "DGS10",       # 10Y Treasury
    "DGS2",        # 2Y Treasury  
    "DTB3",        # 3M Treasury Bill
    "DFF",         # Daily Fed Funds
    "SOFR",        # SOFR rate
    "IORB",        # Interest on Reserve Balances
    "BAMLC0A0CM",  # IG OAS
    "BAMLH0A0HYM2",# HY OAS
    "AAA",         # Moody's Aaa yield
    "BAA",         # Moody's Baa yield
]


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
    
    # === Update FRED Series Cache (incremental - last 30 days) ===
    if db.connected and results["sources"].get("FRED", {}).get("status") == "success":
        try:
            series_updated = update_fred_series_cache(client, db)
            results["fred_series_update"] = {
                "status": "success",
                "series_updated": series_updated,
            }
        except Exception as e:
            results["fred_series_update"] = {
                "status": "error",
                "error": str(e),
            }
    
    status_code = 200 if results["success"] else 207  # 207 = partial success
    
    return func.HttpResponse(
        json.dumps(results, indent=2),
        status_code=status_code,
        mimetype="application/json"
    )


def update_fred_series_cache(client: FREDClient, db) -> int:
    """
    Update FRED series in Azure Tables with recent data.
    
    Fetches the last 30 days of data for key series and appends
    to existing cached series. This keeps the Azure Tables current
    without re-fetching the entire historical dataset.
    
    Returns count of series updated.
    """
    updated = 0
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    for series_id in FRED_SERIES_TO_CACHE:
        try:
            # Get existing series from Azure
            existing = db.get_fred_series(series_id)
            
            # Fetch recent data from FRED
            observations = client.get_series(
                series_id, 
                start_date=start_date,
                end_date=end_date,
                limit=100
            )
            
            if not observations:
                continue
            
            # Convert to lists
            new_dates = []
            new_values = []
            for obs in observations:
                if obs.get("value") and obs["value"] != ".":
                    new_dates.append(obs["date"])
                    try:
                        new_values.append(float(obs["value"]))
                    except ValueError:
                        continue
            
            if not new_dates:
                continue
            
            # Merge with existing data
            if existing:
                # Combine existing + new, remove duplicates
                all_dates = existing.get("dates", []) + new_dates
                all_values = existing.get("values", []) + new_values
                
                # Deduplicate by date (keep first occurrence = existing data)
                seen = set()
                merged_dates = []
                merged_values = []
                for d, v in zip(all_dates, all_values):
                    if d not in seen:
                        seen.add(d)
                        merged_dates.append(d)
                        merged_values.append(v)
                
                # Sort by date
                sorted_pairs = sorted(zip(merged_dates, merged_values))
                merged_dates = [p[0] for p in sorted_pairs]
                merged_values = [p[1] for p in sorted_pairs]
            else:
                merged_dates = new_dates
                merged_values = new_values
            
            # Save back to Azure
            success = db.save_fred_series(series_id, {
                "dates": merged_dates,
                "values": merged_values,
            })
            
            if success:
                updated += 1
                
        except Exception:
            continue
    
    return updated

"""Accept and store pre-computed backtest results."""

import json
import sys
import os
from datetime import datetime
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Store pre-computed backtest results sent from external process.
    
    Expects JSON body with the full backtest response structure.
    """
    
    db = get_database()
    
    if not db.connected:
        return func.HttpResponse(
            json.dumps({"error": "Database not connected"}),
            status_code=500,
            mimetype="application/json"
        )
    
    # Parse request body
    try:
        backtest_data = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json"
        )
    
    if not backtest_data:
        return func.HttpResponse(
            json.dumps({"error": "Empty request body"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Validate required fields
    required_fields = ["parameters", "summary", "time_series"]
    missing = [f for f in required_fields if f not in backtest_data]
    if missing:
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {missing}"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Get cache key from parameters
    params = backtest_data.get("parameters", {})
    start_date = params.get("start_date", "2006-01-01")
    end_date = params.get("end_date", datetime.now().strftime("%Y-%m-%d"))
    interval = params.get("interval_days", 7)
    
    cache_key = f"{start_date}_{end_date}_{interval}"
    
    # Add upload metadata
    backtest_data["uploaded_at"] = datetime.utcnow().isoformat()
    backtest_data["data_source"] = "Pre-computed (uploaded)"
    
    # Save to cache
    cache_saved = db.save_backtest_cache(backtest_data, cache_key)
    default_saved = db.save_backtest_cache(backtest_data, "default")
    
    data_points = len(backtest_data.get("time_series", []))
    
    return func.HttpResponse(
        json.dumps({
            "status": "success",
            "message": "Backtest results uploaded and cached",
            "data_points": data_points,
            "cache_key": cache_key,
            "saved": {
                "specific": cache_saved,
                "default": default_saved
            },
            "uploaded_at": backtest_data["uploaded_at"]
        }),
        mimetype="application/json"
    )

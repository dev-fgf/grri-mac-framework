"""Pre-compute and store historical backtest data from FRED."""

import json
import sys
import os
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database


def get_status(mac_score: float) -> str:
    """Get status label from MAC score."""
    if mac_score >= 0.65:
        return "COMFORTABLE"
    elif mac_score >= 0.50:
        return "CAUTIOUS"
    elif mac_score >= 0.35:
        return "STRETCHED"
    else:
        return "CRITICAL"


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch historical data from FRED and store in Table Storage."""

    client = FREDClient()
    db = get_database()

    if not client.api_key:
        return func.HttpResponse(
            json.dumps({"error": "FRED_API_KEY not configured"}),
            status_code=500,
            mimetype="application/json"
        )

    if not db.connected:
        return func.HttpResponse(
            json.dumps({"error": "Database not connected"}),
            status_code=500,
            mimetype="application/json"
        )

    # Parameters
    start_date_str = req.params.get('start', '2006-01-01')
    end_date_str = req.params.get('end', datetime.now().strftime('%Y-%m-%d'))
    interval_days = int(req.params.get('interval', '7'))

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid date format"}),
            status_code=400,
            mimetype="application/json"
        )

    # Fetch all FRED series in bulk
    bulk_data = client.get_all_bulk_series(start_date, end_date)

    if not bulk_data:
        return func.HttpResponse(
            json.dumps({"error": "Failed to fetch FRED data"}),
            status_code=500,
            mimetype="application/json"
        )

    # Generate and store data points
    points_to_save = []
    current_date = start_date
    skipped = 0

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        indicators = client.calculate_indicators_from_bulk(bulk_data, date_str)

        if indicators and len(indicators) >= 3:
            mac_result = calculate_mac(indicators)
            mac_score = mac_result.get("mac_score", 0)
            pillars = mac_result.get("pillar_scores", {})

            point = {
                "date": date_str,
                "mac_score": round(mac_score, 4),
                "status": get_status(mac_score),
                "multiplier": mac_result.get("multiplier"),
                "pillar_scores": {
                    "liquidity": round(pillars.get("liquidity", {}).get("score", 0), 4),
                    "valuation": round(pillars.get("valuation", {}).get("score", 0), 4),
                    "positioning": round(pillars.get("positioning", {}).get("score", 0), 4),
                    "volatility": round(pillars.get("volatility", {}).get("score", 0), 4),
                    "policy": round(pillars.get("policy", {}).get("score", 0), 4),
                },
                "breach_flags": mac_result.get("breach_flags", []),
                "indicators": {
                    k: round(v, 2) if isinstance(v, float) else v
                    for k, v in indicators.items()
                },
            }
            points_to_save.append(point)
        else:
            skipped += 1

        current_date += timedelta(days=interval_days)

    # Save to database
    saved_count = db.save_backtest_batch(points_to_save)

    return func.HttpResponse(
        json.dumps({
            "success": True,
            "message": f"Seeded {saved_count} backtest points",
            "parameters": {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "interval_days": interval_days,
            },
            "stats": {
                "total_dates": len(points_to_save) + skipped,
                "saved": saved_count,
                "skipped_no_data": skipped,
            }
        }),
        mimetype="application/json"
    )

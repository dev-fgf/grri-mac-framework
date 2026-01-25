"""Pre-compute and store historical MAC data from FRED for the history chart."""

import json
import sys
import os
import uuid
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch historical data from FRED and store in machistory Table Storage."""

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

    # Parameters - default to 2 years of daily data
    days_param = req.params.get('days', '730')
    try:
        days = min(int(days_param), 2000)  # Max ~5.5 years
    except ValueError:
        days = 730

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Fetch all FRED series in bulk
    bulk_data = client.get_all_bulk_series(start_date, end_date)

    if not bulk_data:
        return func.HttpResponse(
            json.dumps({"error": "Failed to fetch FRED data"}),
            status_code=500,
            mimetype="application/json"
        )

    # Generate and store data points
    saved_count = 0
    skipped = 0
    errors = []

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")

        try:
            indicators = client.calculate_indicators_from_bulk(bulk_data, date_str)

            if indicators and len(indicators) >= 3:
                mac_result = calculate_mac(indicators)
                mac_score = mac_result.get("mac_score", 0)
                pillars = mac_result.get("pillar_scores", {})

                # Create entity for machistory table
                partition_key = date_str
                row_key = current_date.strftime("%H%M%S") + "_" + str(uuid.uuid4())[:8]

                entity = {
                    "PartitionKey": partition_key,
                    "RowKey": row_key,
                    "timestamp": current_date.isoformat(),
                    "mac_score": round(mac_score, 4),
                    "liquidity_score": round(pillars.get("liquidity", {}).get("score", 0), 4),
                    "valuation_score": round(pillars.get("valuation", {}).get("score", 0), 4),
                    "positioning_score": round(pillars.get("positioning", {}).get("score", 0), 4),
                    "volatility_score": round(pillars.get("volatility", {}).get("score", 0), 4),
                    "policy_score": round(pillars.get("policy", {}).get("score", 0), 4),
                    "multiplier": mac_result.get("multiplier"),
                    "breach_flags": json.dumps(mac_result.get("breach_flags", [])),
                    "is_live": False,
                    "indicators": json.dumps({
                        k: round(v, 2) if isinstance(v, float) else v
                        for k, v in indicators.items()
                    }),
                }

                # Upsert to handle existing data
                db._table_client.upsert_entity(entity)
                saved_count += 1
            else:
                skipped += 1

        except Exception as e:
            errors.append(f"{date_str}: {str(e)}")
            skipped += 1

        current_date += timedelta(days=1)

    return func.HttpResponse(
        json.dumps({
            "success": True,
            "message": f"Seeded {saved_count} historical MAC records from FRED",
            "parameters": {
                "days_requested": days,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
            "stats": {
                "saved": saved_count,
                "skipped_no_data": skipped,
                "errors": len(errors),
            },
            "sample_errors": errors[:5] if errors else [],
        }),
        mimetype="application/json"
    )

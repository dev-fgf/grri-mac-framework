import json
import sys
import os
import random
from datetime import datetime, timedelta
import azure.functions as func

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database
from shared.mac_scorer import calculate_mac


def generate_historical_indicators(days_ago: int, seed: int = 42) -> dict:
    """Generate realistic historical indicators with some randomness."""
    random.seed(seed + days_ago)

    # Base values that evolve over time
    base_sofr_spread = 3 + random.uniform(-2, 5)
    base_cp_spread = 20 + random.uniform(-10, 30)
    base_term_premium = 40 + random.uniform(-20, 60)
    base_ig_oas = 90 + random.uniform(-20, 50)
    base_hy_oas = 300 + random.uniform(-100, 200)
    base_vix = 16 + random.uniform(-4, 15)
    base_fed_vs_neutral = 150 + random.uniform(-50, 100)

    return {
        "sofr_iorb_spread_bps": round(base_sofr_spread, 2),
        "cp_treasury_spread_bps": round(base_cp_spread, 2),
        "term_premium_10y_bps": round(base_term_premium, 2),
        "ig_oas_bps": round(base_ig_oas, 2),
        "hy_oas_bps": round(base_hy_oas, 2),
        "vix_level": round(base_vix, 2),
        "fed_funds_vs_neutral_bps": round(base_fed_vs_neutral, 2),
    }


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Seed historical MAC data into Table Storage."""

    # Get days parameter (default 90)
    days_param = req.params.get('days', '90')
    try:
        days = min(int(days_param), 365)  # Max 1 year
    except ValueError:
        days = 90

    db = get_database()

    if not db.connected:
        return func.HttpResponse(
            json.dumps({"error": "Database not connected", "db_connected": False}),
            status_code=500,
            mimetype="application/json"
        )

    seeded_count = 0
    errors = []

    # Generate data for each day
    for i in range(days, 0, -1):
        try:
            # Generate indicators for this day
            indicators = generate_historical_indicators(i, seed=42)

            # Calculate MAC score
            result = calculate_mac(indicators)
            result["is_live"] = False  # Mark as historical/seeded
            result["indicators"] = indicators

            # Override the timestamp to be in the past
            target_date = datetime.utcnow() - timedelta(days=i)

            # Save directly to table with custom timestamp
            pillars = result.get("pillar_scores", {})

            import uuid
            partition_key = target_date.strftime("%Y-%m-%d")
            row_key = target_date.strftime("%H%M%S") + "_" + str(uuid.uuid4())[:8]

            entity = {
                "PartitionKey": partition_key,
                "RowKey": row_key,
                "timestamp": target_date.isoformat(),
                "mac_score": result.get("mac_score"),
                "liquidity_score": pillars.get("liquidity", {}).get("score"),
                "valuation_score": pillars.get("valuation", {}).get("score"),
                "positioning_score": pillars.get("positioning", {}).get("score"),
                "volatility_score": pillars.get("volatility", {}).get("score"),
                "policy_score": pillars.get("policy", {}).get("score"),
                "multiplier": result.get("multiplier"),
                "breach_flags": json.dumps(result.get("breach_flags", [])),
                "is_live": False,
                "indicators": json.dumps(indicators),
            }

            db._table_client.create_entity(entity)
            seeded_count += 1

        except Exception as e:
            errors.append(f"Day {i}: {str(e)}")

    response = {
        "success": True,
        "days_requested": days,
        "records_seeded": seeded_count,
        "errors": errors[:10] if errors else [],  # First 10 errors only
        "message": f"Seeded {seeded_count} historical records"
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

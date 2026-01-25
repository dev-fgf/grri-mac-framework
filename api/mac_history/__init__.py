import json
import sys
import os
from datetime import datetime, timedelta
import azure.functions as func

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database


def generate_demo_history(days: int) -> list:
    """Generate demo historical data when database is not available."""
    import random
    random.seed(42)  # Consistent demo data

    data = []
    now = datetime.utcnow()

    # Base values
    mac = 0.58
    liquidity = 0.72
    valuation = 0.55
    positioning = 0.48
    volatility = 0.62
    policy = 0.52

    for i in range(days, -1, -1):
        date = now - timedelta(days=i)

        # Random walk with mean reversion
        def evolve(val, target, volatility=0.04):
            change = (random.random() - 0.5) * volatility
            reversion = (target - val) * 0.02
            return max(0.15, min(0.85, val + change + reversion))

        liquidity = evolve(liquidity, 0.65, 0.05)
        valuation = evolve(valuation, 0.55, 0.04)
        positioning = evolve(positioning, 0.50, 0.06)
        volatility = evolve(volatility, 0.60, 0.05)
        policy = evolve(policy, 0.52, 0.03)

        mac = (liquidity + valuation + positioning + volatility + policy) / 5

        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "timestamp": date.isoformat(),
            "mac": round(mac, 4),
            "liquidity": round(liquidity, 4),
            "valuation": round(valuation, 4),
            "positioning": round(positioning, 4),
            "volatility": round(volatility, 4),
            "policy": round(policy, 4),
            "is_live": False,
        })

    return data


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Get MAC history for charting."""

    # Get days parameter (default 30)
    days_param = req.params.get('days', '30')
    try:
        days = min(int(days_param), 365)  # Max 1 year
    except ValueError:
        days = 30

    # Try database first
    db = get_database()
    history = db.get_history(days)

    # Use demo data if database is empty
    if not history:
        history = generate_demo_history(days)
        source = "demo"
    else:
        source = "database"

    response = {
        "days": days,
        "count": len(history),
        "source": source,
        "data": history,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

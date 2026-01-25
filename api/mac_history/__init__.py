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
    import math
    random.seed(42)  # Consistent demo data

    data = []
    now = datetime.utcnow()

    # Stress episodes (days ago, duration, severity)
    stress_episodes = [
        {"start": 1800, "duration": 30, "severity": 0.30},
        {"start": 1500, "duration": 25, "severity": 0.22},
        {"start": 1200, "duration": 20, "severity": 0.18},
        {"start": 900, "duration": 35, "severity": 0.35},
        {"start": 700, "duration": 15, "severity": 0.20},
        {"start": 500, "duration": 20, "severity": 0.25},
        {"start": 350, "duration": 18, "severity": 0.22},
        {"start": 150, "duration": 20, "severity": 0.25},
        {"start": 90, "duration": 10, "severity": 0.15},
        {"start": 45, "duration": 8, "severity": 0.20},
        {"start": 15, "duration": 5, "severity": 0.12},
    ]

    # Base values - MAC scores (high = good capacity)
    liquidity = 0.68
    valuation = 0.62
    positioning = 0.55
    volatility_score = 0.58
    policy = 0.60

    for i in range(days, -1, -1):
        date = now - timedelta(days=i)

        # Calculate stress boost from episodes
        stress_boost = 0
        for ep in stress_episodes:
            if ep["start"] >= i > ep["start"] - ep["duration"]:
                progress = (ep["start"] - i) / ep["duration"]
                stress_shape = math.sin(progress * math.pi)  # Bell curve
                stress_boost = max(stress_boost, ep["severity"] * stress_shape)

        # Random walk with larger steps and weaker mean reversion
        base_vol = 0.06
        stress_vol = stress_boost * 0.12

        def evolve(val, target, vol_mult=1.0):
            change = (random.random() - 0.5) * (base_vol + stress_vol) * vol_mult
            reversion = (target - val) * 0.005
            stress_impact = stress_boost * 0.25 * vol_mult
            return max(0.15, min(0.92, val + change + reversion - stress_impact))

        liquidity = evolve(liquidity, 0.65, 1.0)
        valuation = evolve(valuation, 0.60, 0.9)
        positioning = evolve(positioning, 0.55, 1.2)
        volatility_score = evolve(volatility_score, 0.58, 1.3)
        policy = evolve(policy, 0.60, 0.5)

        mac = (liquidity + valuation + positioning + volatility_score + policy) / 5

        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "timestamp": date.isoformat(),
            "mac": round(mac, 4),
            "liquidity": round(liquidity, 4),
            "valuation": round(valuation, 4),
            "positioning": round(positioning, 4),
            "volatility": round(volatility_score, 4),
            "policy": round(policy, 4),
            "is_live": False,
        })

    return data


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Get MAC history for charting."""

    # Get days parameter (default 30)
    days_param = req.params.get('days', '30')
    try:
        days = min(int(days_param), 2000)  # Max ~5.5 years
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

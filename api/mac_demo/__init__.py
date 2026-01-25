import json
from datetime import datetime
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    # Demo pillar scores
    pillar_scores = {
        "liquidity": {"score": 0.72, "status": "THIN"},
        "valuation": {"score": 0.58, "status": "THIN"},
        "positioning": {"score": 0.45, "status": "THIN"},
        "volatility": {"score": 0.65, "status": "THIN"},
        "policy": {"score": 0.55, "status": "THIN"},
    }

    mac_score = sum(p["score"] for p in pillar_scores.values()) / 5

    # Determine interpretation
    if mac_score >= 0.8:
        interpretation = "AMPLE - Markets have substantial buffer capacity"
    elif mac_score >= 0.6:
        interpretation = "COMFORTABLE - Markets can absorb moderate shocks"
    elif mac_score >= 0.4:
        interpretation = "THIN - Limited buffer, elevated transmission risk"
    elif mac_score >= 0.2:
        interpretation = "STRETCHED - High transmission risk, monitor closely"
    else:
        interpretation = "REGIME BREAK - Buffers exhausted, non-linear dynamics likely"

    # Calculate multiplier
    if mac_score >= 0.8:
        multiplier, tier = 1.0, "Minimal"
    elif mac_score >= 0.6:
        multiplier, tier = 1.5, "Low"
    elif mac_score >= 0.4:
        multiplier, tier = 2.0, "Elevated"
    elif mac_score >= 0.2:
        multiplier, tier = 3.0, "High"
    else:
        multiplier, tier = 5.0, "Critical"

    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "mac_score": round(mac_score, 3),
        "interpretation": interpretation,
        "multiplier": round(multiplier, 2),
        "multiplier_tier": tier,
        "pillar_scores": pillar_scores,
        "breach_flags": [],
        "is_demo": True,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

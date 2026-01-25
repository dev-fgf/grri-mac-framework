import json
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    shock = body.get("shock_magnitude", 1.0)
    grri = body.get("grri_modifier", 1.0)
    mac_score = body.get("mac_score", 0.5)

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

    impact = shock * grri * multiplier

    response = {
        "shock_magnitude": shock,
        "grri_modifier": grri,
        "mac_score": round(mac_score, 3),
        "mac_multiplier": round(multiplier, 2),
        "market_impact": round(impact, 3),
        "risk_tier": tier,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

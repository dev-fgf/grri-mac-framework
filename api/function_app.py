"""Azure Functions API for GRRI-MAC Framework."""

import json
import logging
import os
import sys
from datetime import datetime

import azure.functions as func

# Add parent directory to path for grri_mac imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grri_mac.mac.composite import calculate_mac, get_mac_interpretation, get_pillar_status
from grri_mac.mac.multiplier import mac_to_multiplier
from grri_mac.backtest.scenarios import KNOWN_EVENTS
from grri_mac.backtest.calibrated_engine import CalibratedBacktestEngine
from grri_mac.pillars.calibrated import (
    LIQUIDITY_THRESHOLDS,
    VALUATION_THRESHOLDS,
    POSITIONING_THRESHOLDS,
    VOLATILITY_THRESHOLDS,
    POLICY_THRESHOLDS,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }),
        mimetype="application/json"
    )


@app.route(route="mac/demo", methods=["GET"])
def mac_demo(req: func.HttpRequest) -> func.HttpResponse:
    """Get demo MAC calculation with sample data."""
    # Sample current market conditions (simulated)
    demo_pillars = {
        "liquidity": 0.72,
        "valuation": 0.58,
        "positioning": 0.45,
        "volatility": 0.65,
        "policy": 0.55,
    }

    mac_result = calculate_mac(demo_pillars)
    mult_result = mac_to_multiplier(mac_result.mac_score)

    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "mac_score": round(mac_result.mac_score, 3),
        "interpretation": get_mac_interpretation(mac_result.mac_score),
        "multiplier": round(mult_result.multiplier, 2),
        "multiplier_tier": mult_result.tier,
        "pillar_scores": {
            name: {
                "score": round(score, 3),
                "status": get_pillar_status(score)
            }
            for name, score in mac_result.pillar_scores.items()
        },
        "breach_flags": mac_result.breach_flags,
        "is_demo": True,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )


@app.route(route="mac/calculate", methods=["POST"])
def mac_calculate(req: func.HttpRequest) -> func.HttpResponse:
    """Calculate MAC from provided pillar scores."""
    try:
        body = req.get_json()
        pillars = body.get("pillars", {})

        if not pillars:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'pillars' in request body"}),
                status_code=400,
                mimetype="application/json"
            )

        mac_result = calculate_mac(pillars)
        mult_result = mac_to_multiplier(mac_result.mac_score)

        response = {
            "mac_score": round(mac_result.mac_score, 3),
            "interpretation": get_mac_interpretation(mac_result.mac_score),
            "multiplier": round(mult_result.multiplier, 2),
            "multiplier_tier": mult_result.tier,
            "pillar_scores": {
                name: {
                    "score": round(score, 3),
                    "status": get_pillar_status(score)
                }
                for name, score in mac_result.pillar_scores.items()
            },
            "breach_flags": mac_result.breach_flags,
        }

        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json"
        )

    except ValueError as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )


@app.route(route="backtest/scenarios", methods=["GET"])
def backtest_scenarios(req: func.HttpRequest) -> func.HttpResponse:
    """List available backtest scenarios."""
    scenarios = []
    for name, scenario in KNOWN_EVENTS.items():
        scenarios.append({
            "id": name,
            "name": scenario.name,
            "date": scenario.date.isoformat(),
            "expected_mac_range": scenario.expected_mac_range,
            "expected_breaches": scenario.expected_breaches,
            "treasury_hedge_worked": scenario.treasury_hedge_worked,
        })

    return func.HttpResponse(
        json.dumps({"scenarios": scenarios}),
        mimetype="application/json"
    )


@app.route(route="backtest/run", methods=["GET", "POST"])
def backtest_run(req: func.HttpRequest) -> func.HttpResponse:
    """Run backtest across all scenarios."""
    engine = CalibratedBacktestEngine()
    summary = engine.run_all_scenarios()

    results = []
    for r in summary.results:
        results.append({
            "scenario_name": r.scenario_name,
            "scenario_date": r.scenario_date.isoformat(),
            "mac_score": round(r.mac_score, 3),
            "multiplier": round(r.multiplier, 2),
            "pillar_scores": {k: round(v, 3) for k, v in r.pillar_scores.items()},
            "breach_flags": r.breach_flags,
            "expected_mac_range": r.expected_mac_range,
            "mac_in_range": r.mac_in_range,
            "expected_breaches": r.expected_breaches,
            "breaches_match": r.breaches_match,
            "treasury_hedge_worked": r.treasury_hedge_worked,
            "hedge_prediction_correct": r.hedge_prediction_correct,
            "key_insight": r.key_insight,
            "calibration_notes": r.calibration_notes,
        })

    response = {
        "summary": {
            "total_scenarios": summary.total_scenarios,
            "passed": summary.passed,
            "failed": summary.failed,
            "mac_range_accuracy": round(summary.mac_range_accuracy * 100, 1),
            "breach_accuracy": round(summary.breach_accuracy * 100, 1),
            "hedge_prediction_accuracy": round(summary.hedge_prediction_accuracy * 100, 1),
        },
        "results": results,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )


@app.route(route="thresholds", methods=["GET"])
def get_thresholds(req: func.HttpRequest) -> func.HttpResponse:
    """Get calibrated thresholds for all pillars."""
    response = {
        "liquidity": LIQUIDITY_THRESHOLDS,
        "valuation": VALUATION_THRESHOLDS,
        "positioning": POSITIONING_THRESHOLDS,
        "volatility": VOLATILITY_THRESHOLDS,
        "policy": POLICY_THRESHOLDS,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )


@app.route(route="simulate", methods=["POST"])
def simulate_shock(req: func.HttpRequest) -> func.HttpResponse:
    """Simulate market impact of a shock given MAC conditions."""
    try:
        body = req.get_json()
        shock_magnitude = body.get("shock_magnitude", 1.0)
        grri_modifier = body.get("grri_modifier", 1.0)
        pillars = body.get("pillars")

        if pillars:
            mac_result = calculate_mac(pillars)
            mac_score = mac_result.mac_score
        else:
            mac_score = body.get("mac_score", 0.5)

        mult_result = mac_to_multiplier(mac_score)

        # Core equation: Market Impact = Shock × GRRI Modifier × MAC Multiplier
        market_impact = shock_magnitude * grri_modifier * mult_result.multiplier

        response = {
            "shock_magnitude": shock_magnitude,
            "grri_modifier": grri_modifier,
            "mac_score": round(mac_score, 3),
            "mac_multiplier": round(mult_result.multiplier, 2),
            "market_impact": round(market_impact, 3),
            "interpretation": get_mac_interpretation(mac_score),
            "risk_tier": mult_result.tier,
        }

        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json"
        )

    except ValueError as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )

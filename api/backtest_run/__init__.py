import json
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    # Demo backtest results
    results = [
        {
            "scenario_name": "Pre-COVID (Jan 2020)",
            "scenario_date": "2020-01-15",
            "mac_score": 0.78,
            "multiplier": 1.1,
            "pillar_scores": {"liquidity": 0.85, "valuation": 0.72, "positioning": 0.75, "volatility": 0.80, "policy": 0.78},
            "breach_flags": [],
            "expected_mac_range": [0.70, 0.85],
            "mac_in_range": True,
            "expected_breaches": [],
            "breaches_match": True,
            "treasury_hedge_worked": True,
            "hedge_prediction_correct": True,
            "key_insight": "Treasury hedge worked - buffers held",
            "calibration_notes": []
        },
        {
            "scenario_name": "COVID Peak (Mar 2020)",
            "scenario_date": "2020-03-16",
            "mac_score": 0.12,
            "multiplier": 5.0,
            "pillar_scores": {"liquidity": 0.08, "valuation": 0.15, "positioning": 0.10, "volatility": 0.05, "policy": 0.22},
            "breach_flags": ["liquidity", "positioning", "volatility"],
            "expected_mac_range": [0.05, 0.20],
            "mac_in_range": True,
            "expected_breaches": ["liquidity", "positioning", "volatility"],
            "breaches_match": True,
            "treasury_hedge_worked": False,
            "hedge_prediction_correct": True,
            "key_insight": "CORRECT: Positioning breach predicted hedge failure",
            "calibration_notes": []
        },
        {
            "scenario_name": "Post-COVID (Jun 2020)",
            "scenario_date": "2020-06-15",
            "mac_score": 0.58,
            "multiplier": 1.8,
            "pillar_scores": {"liquidity": 0.65, "valuation": 0.52, "positioning": 0.55, "volatility": 0.58, "policy": 0.60},
            "breach_flags": [],
            "expected_mac_range": [0.50, 0.65],
            "mac_in_range": True,
            "expected_breaches": [],
            "breaches_match": True,
            "treasury_hedge_worked": True,
            "hedge_prediction_correct": True,
            "key_insight": "Treasury hedge worked - buffers held",
            "calibration_notes": []
        },
        {
            "scenario_name": "2022 Rate Hikes",
            "scenario_date": "2022-09-15",
            "mac_score": 0.42,
            "multiplier": 2.2,
            "pillar_scores": {"liquidity": 0.55, "valuation": 0.38, "positioning": 0.45, "volatility": 0.40, "policy": 0.32},
            "breach_flags": ["policy"],
            "expected_mac_range": [0.35, 0.50],
            "mac_in_range": True,
            "expected_breaches": ["policy"],
            "breaches_match": True,
            "treasury_hedge_worked": True,
            "hedge_prediction_correct": True,
            "key_insight": "Treasury hedge worked - buffers held",
            "calibration_notes": []
        },
        {
            "scenario_name": "SVB Crisis (Mar 2023)",
            "scenario_date": "2023-03-10",
            "mac_score": 0.35,
            "multiplier": 2.5,
            "pillar_scores": {"liquidity": 0.18, "valuation": 0.42, "positioning": 0.38, "volatility": 0.35, "policy": 0.42},
            "breach_flags": ["liquidity"],
            "expected_mac_range": [0.28, 0.42],
            "mac_in_range": True,
            "expected_breaches": ["liquidity"],
            "breaches_match": True,
            "treasury_hedge_worked": True,
            "hedge_prediction_correct": True,
            "key_insight": "Treasury hedge worked - buffers held",
            "calibration_notes": []
        },
        {
            "scenario_name": "April 2025 Crisis",
            "scenario_date": "2025-04-07",
            "mac_score": 0.18,
            "multiplier": 4.5,
            "pillar_scores": {"liquidity": 0.25, "valuation": 0.22, "positioning": 0.12, "volatility": 0.15, "policy": 0.18},
            "breach_flags": ["positioning", "volatility"],
            "expected_mac_range": [0.12, 0.25],
            "mac_in_range": True,
            "expected_breaches": ["positioning", "volatility"],
            "breaches_match": True,
            "treasury_hedge_worked": False,
            "hedge_prediction_correct": True,
            "key_insight": "CORRECT: Positioning breach predicted hedge failure",
            "calibration_notes": []
        }
    ]

    response = {
        "summary": {
            "total_scenarios": 6,
            "passed": 6,
            "failed": 0,
            "mac_range_accuracy": 100.0,
            "breach_accuracy": 100.0,
            "hedge_prediction_accuracy": 100.0,
        },
        "results": results,
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

"""Backtest endpoint - returns historical MAC data from storage or FRED."""

import json
import sys
import os
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database


# Define historical crisis events for annotation
CRISIS_EVENTS = {
    # Pre-GFC
    "2007-08-09": {"name": "BNP Paribas", "description": "Subprime contagion begins"},
    "2008-03-16": {"name": "Bear Stearns", "description": "Bear Stearns collapse/rescue"},
    "2008-09-15": {"name": "Lehman Brothers", "description": "Lehman bankruptcy, GFC peak"},
    # Post-GFC
    "2010-05-06": {"name": "Flash Crash", "description": "Dow drops 1000 pts intraday"},
    "2011-08-08": {"name": "US Downgrade", "description": "S&P downgrades US debt"},
    "2015-08-24": {"name": "China Deval", "description": "Yuan devaluation, EM selloff"},
    "2018-12-24": {"name": "Fed Pivot", "description": "Q4 2018 selloff, Powell pivot"},
    # Recent
    "2020-03-16": {"name": "COVID-19 Peak", "description": "Pandemic selloff, VIX 82"},
    "2022-09-30": {"name": "2022 Rate Shock", "description": "Fed hikes, UK pension crisis"},
    "2023-03-10": {"name": "SVB Crisis", "description": "Regional banking stress"},
    "2024-08-05": {"name": "Yen Carry Unwind", "description": "BoJ rate hike"},
    "2025-04-07": {"name": "April 2025 Tariff", "description": "Trade war escalation"},
}


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


def add_crisis_events(time_series: list) -> list:
    """Add crisis event annotations to time series data."""
    for point in time_series:
        point_date = datetime.strptime(point["date"], "%Y-%m-%d")
        for event_date, event_info in CRISIS_EVENTS.items():
            event_dt = datetime.strptime(event_date, "%Y-%m-%d")
            if abs((point_date - event_dt).days) <= 3:
                point["crisis_event"] = {
                    "name": event_info["name"],
                    "description": event_info["description"],
                    "event_date": event_date
                }
                break
    return time_series


def calculate_crisis_analysis(time_series: list, start_date, end_date) -> list:
    """Calculate crisis prediction analysis."""
    crisis_analysis = []

    for event_date, event_info in CRISIS_EVENTS.items():
        event_dt = datetime.strptime(event_date, "%Y-%m-%d")
        if event_dt < start_date or event_dt > end_date:
            continue

        pre_event_points = [
            p for p in time_series
            if datetime.strptime(p["date"], "%Y-%m-%d") <= event_dt
            and datetime.strptime(p["date"], "%Y-%m-%d") >= event_dt - timedelta(days=90)
        ]

        if pre_event_points:
            first_warning = None
            first_stretched = None
            for p in pre_event_points:
                if p["status"] != "COMFORTABLE" and first_warning is None:
                    first_warning = p
                if p["status"] in ["STRETCHED", "CRITICAL"] and first_stretched is None:
                    first_stretched = p

            event_point = pre_event_points[-1] if pre_event_points else None

            crisis_analysis.append({
                "event": event_info["name"],
                "event_date": event_date,
                "mac_at_event": event_point["mac_score"] if event_point else None,
                "status_at_event": event_point["status"] if event_point else None,
                "first_warning_date": first_warning["date"] if first_warning else None,
                "days_of_warning": (
                    event_dt - datetime.strptime(first_warning["date"], "%Y-%m-%d")
                ).days if first_warning else 0,
                "first_stretched_date": first_stretched["date"] if first_stretched else None,
                "days_stretched": (
                    event_dt - datetime.strptime(first_stretched["date"], "%Y-%m-%d")
                ).days if first_stretched else 0,
            })

    return crisis_analysis


def fetch_from_fred(client, start_date, end_date, interval_days) -> list:
    """Fetch data from FRED API (fallback when no stored data)."""
    bulk_data = client.get_all_bulk_series(start_date, end_date)
    if not bulk_data:
        return []

    time_series = []
    current_date = start_date

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
            time_series.append(point)

        current_date += timedelta(days=interval_days)

    return time_series


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Return historical MAC time series - from cache first, storage second, FRED last."""

    # Get parameters
    start_date_str = req.params.get('start', '2006-01-01')
    end_date_str = req.params.get('end', datetime.now().strftime('%Y-%m-%d'))
    interval_days = int(req.params.get('interval', '7'))
    
    # Generate cache key from parameters
    cache_key = f"{start_date_str}_{end_date_str}_{interval_days}"

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"}),
            status_code=400,
            mimetype="application/json"
        )

    db = get_database()
    
    # === PRIORITY 1: Try chunked cache (uploaded from local) ===
    if db.connected:
        cached = db.get_backtest_cache_chunked()
        if cached and cached.get("time_series"):
            # Filter time series by date range if needed
            time_series = cached["time_series"]
            
            # Apply date filtering
            filtered = [
                p for p in time_series
                if start_date_str <= p["date"] <= end_date_str
            ]
            
            # Apply interval filtering
            if interval_days > 1 and filtered:
                spaced = []
                last_date = None
                for point in filtered:
                    if last_date is None:
                        spaced.append(point)
                        last_date = datetime.strptime(point["date"], "%Y-%m-%d")
                    else:
                        current = datetime.strptime(point["date"], "%Y-%m-%d")
                        if (current - last_date).days >= interval_days:
                            spaced.append(point)
                            last_date = current
                filtered = spaced
            
            # Add crisis annotations if missing
            filtered = add_crisis_events(filtered)
            
            # Recalculate summary for filtered data
            if filtered:
                mac_scores = [p["mac_score"] for p in filtered]
                crisis_analysis = calculate_crisis_analysis(filtered, start_date, end_date)
                
                total_crises = len(crisis_analysis)
                crises_stretched = sum(1 for c in crisis_analysis if c["days_stretched"] > 0)
                prediction_accuracy = (crises_stretched / total_crises * 100) if total_crises > 0 else 0
                
                response = {
                    "data_source": "Cached (Azure Table)",
                    "cache_age_seconds": cached.get("cache_age_seconds", 0),
                    "parameters": {
                        "start_date": start_date_str,
                        "end_date": end_date_str,
                        "interval_days": interval_days,
                        "data_points": len(filtered)
                    },
                    "summary": {
                        "data_points": len(filtered),
                        "min_mac": round(min(mac_scores), 4),
                        "max_mac": round(max(mac_scores), 4),
                        "avg_mac": round(sum(mac_scores) / len(mac_scores), 4),
                        "current_mac": filtered[-1]["mac_score"],
                        "current_status": filtered[-1]["status"],
                        "prediction_accuracy": f"{prediction_accuracy:.0f}%",
                        "periods_in_comfortable": sum(1 for p in filtered if p["status"] == "COMFORTABLE"),
                        "periods_in_cautious": sum(1 for p in filtered if p["status"] == "CAUTIOUS"),
                        "periods_in_stretched": sum(1 for p in filtered if p["status"] == "STRETCHED"),
                        "periods_in_critical": sum(1 for p in filtered if p["status"] == "CRITICAL"),
                    },
                    "crisis_prediction_analysis": crisis_analysis,
                    "time_series": filtered,
                    "crisis_events": CRISIS_EVENTS,
                    "interpretation_guide": cached.get("interpretation_guide", {}),
                }
                
                return func.HttpResponse(
                    json.dumps(response),
                    mimetype="application/json"
                )

    # === PRIORITY 2: Try stored historical data points ===
    time_series = []
    data_source = "Unknown"

    if db.connected:
        stored_data = db.get_backtest_history(start_date_str, end_date_str)
        if stored_data:
            # Filter by interval
            if interval_days > 1:
                filtered = []
                last_date = None
                for point in stored_data:
                    if last_date is None:
                        filtered.append(point)
                        last_date = datetime.strptime(point["date"], "%Y-%m-%d")
                    else:
                        current = datetime.strptime(point["date"], "%Y-%m-%d")
                        if (current - last_date).days >= interval_days:
                            filtered.append(point)
                            last_date = current
                time_series = filtered
            else:
                time_series = stored_data
            data_source = "Pre-computed (Azure Table Storage)"

    # === PRIORITY 3: Fall back to FRED (slow) ===
    if not time_series:
        client = FREDClient()
        if not client.api_key:
            return func.HttpResponse(
                json.dumps({
                    "error": "No cached data and FRED_API_KEY not configured",
                    "message": "Run POST /api/backtest/seed to precompute data, or POST /api/refresh/backtest to cache"
                }),
                status_code=500,
                mimetype="application/json"
            )
                    "error": "No stored data and FRED_API_KEY not configured",
                    "message": "Run POST /api/backtest/seed to precompute data"
                }),
                status_code=500,
                mimetype="application/json"
            )

        time_series = fetch_from_fred(client, start_date, end_date, interval_days)
        data_source = "FRED API (Real-time)"

    if not time_series:
        return func.HttpResponse(
            json.dumps({
                "error": "No data available",
                "message": "Run POST /api/backtest/seed to precompute historical data"
            }),
            status_code=500,
            mimetype="application/json"
        )

    # Add crisis event annotations
    time_series = add_crisis_events(time_series)

    # Calculate statistics
    mac_scores = [p["mac_score"] for p in time_series]
    crisis_analysis = calculate_crisis_analysis(time_series, start_date, end_date)

    # Calculate prediction metrics from crisis analysis
    total_crises = len(crisis_analysis)
    crises_with_warning = sum(1 for c in crisis_analysis if c["days_of_warning"] > 0)
    crises_stretched = sum(1 for c in crisis_analysis if c["days_stretched"] > 0)

    avg_lead_time = 0
    avg_days_stretched = 0
    if total_crises > 0:
        avg_lead_time = sum(c["days_of_warning"] for c in crisis_analysis) / total_crises
        avg_days_stretched = sum(c["days_stretched"] for c in crisis_analysis) / total_crises

    warning_rate = (crises_with_warning / total_crises * 100) if total_crises > 0 else 0
    prediction_accuracy = (crises_stretched / total_crises * 100) if total_crises > 0 else 0

    response = {
        "data_source": data_source,
        "parameters": {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "interval_days": interval_days,
            "data_points": len(time_series)
        },
        "summary": {
            "data_points": len(time_series),
            "average_lead_time_days": round(avg_lead_time, 1),
            "average_days_stretched_before_event": round(avg_days_stretched, 1),
            "warning_rate": f"{warning_rate:.0f}%",
            "prediction_accuracy": f"{prediction_accuracy:.0f}%",
            "min_mac": round(min(mac_scores), 4),
            "max_mac": round(max(mac_scores), 4),
            "avg_mac": round(sum(mac_scores) / len(mac_scores), 4),
            "current_mac": time_series[-1]["mac_score"] if time_series else None,
            "current_status": time_series[-1]["status"] if time_series else None,
            "periods_in_comfortable": sum(1 for p in time_series if p["status"] == "COMFORTABLE"),
            "periods_in_cautious": sum(1 for p in time_series if p["status"] == "CAUTIOUS"),
            "periods_in_stretched": sum(1 for p in time_series if p["status"] == "STRETCHED"),
            "periods_in_critical": sum(1 for p in time_series if p["status"] == "CRITICAL"),
        },
        "crisis_prediction_analysis": crisis_analysis,
        "time_series": time_series,
        "crisis_events": CRISIS_EVENTS,
        "interpretation_guide": {
            "status_levels": {
                "COMFORTABLE": "MAC > 0.65 - Markets can absorb shocks",
                "CAUTIOUS": "MAC 0.50-0.65 - Elevated vigilance recommended",
                "STRETCHED": "MAC 0.35-0.50 - Reduced shock absorption capacity",
                "CRITICAL": "MAC < 0.35 - High vulnerability to cascading selloffs"
            }
        }
    }

    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json"
    )

"""Backtest endpoint - returns historical MAC data from cache, storage, or FRED."""

import json
import sys
import os
import logging
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database

logger = logging.getLogger(__name__)


# Define historical crisis events for annotation
CRISIS_EVENTS = {
    "2007-08-09": {"name": "BNP Paribas", "description": "Subprime contagion begins"},
    "2008-03-16": {"name": "Bear Stearns", "description": "Bear Stearns collapse/rescue"},
    "2008-09-15": {"name": "Lehman Brothers", "description": "Lehman bankruptcy, GFC peak"},
    "2010-05-06": {"name": "Flash Crash", "description": "Dow drops 1000 pts intraday"},
    "2011-08-08": {"name": "US Downgrade", "description": "S&P downgrades US debt"},
    "2015-08-24": {"name": "China Deval", "description": "Yuan devaluation, EM selloff"},
    "2018-12-24": {"name": "Fed Pivot", "description": "Q4 2018 selloff, Powell pivot"},
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


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Return historical MAC time series - from cache first, then fallbacks."""
    
    try:
        # Get parameters
        start_date_str = req.params.get('start', '2006-01-01')
        end_date_str = req.params.get('end', datetime.now().strftime('%Y-%m-%d'))
        interval_days = int(req.params.get('interval', '7'))

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
                logger.info(f"Found cached backtest with {len(cached['time_series'])} points")
                
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
                
                if filtered:
                    # Add crisis annotations
                    filtered = add_crisis_events(filtered)
                    
                    # Calculate stats
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

        # === PRIORITY 2: Try stored historical data points ===
        if db.connected:
            stored_data = db.get_backtest_history(start_date_str, end_date_str)
            if stored_data:
                logger.info(f"Found {len(stored_data)} stored backtest points")
                
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
                
                if time_series:
                    time_series = add_crisis_events(time_series)
                    mac_scores = [p["mac_score"] for p in time_series]
                    crisis_analysis = calculate_crisis_analysis(time_series, start_date, end_date)
                    
                    total_crises = len(crisis_analysis)
                    crises_stretched = sum(1 for c in crisis_analysis if c["days_stretched"] > 0)
                    prediction_accuracy = (crises_stretched / total_crises * 100) if total_crises > 0 else 0
                    
                    return func.HttpResponse(
                        json.dumps({
                            "data_source": "Pre-computed (Azure Table Storage)",
                            "parameters": {
                                "start_date": start_date_str,
                                "end_date": end_date_str,
                                "interval_days": interval_days,
                                "data_points": len(time_series)
                            },
                            "summary": {
                                "data_points": len(time_series),
                                "min_mac": round(min(mac_scores), 4),
                                "max_mac": round(max(mac_scores), 4),
                                "avg_mac": round(sum(mac_scores) / len(mac_scores), 4),
                                "current_mac": time_series[-1]["mac_score"],
                                "current_status": time_series[-1]["status"],
                                "prediction_accuracy": f"{prediction_accuracy:.0f}%",
                            },
                            "crisis_prediction_analysis": crisis_analysis,
                            "time_series": time_series,
                            "crisis_events": CRISIS_EVENTS,
                        }),
                        mimetype="application/json"
                    )

        # === No cached data available ===
        return func.HttpResponse(
            json.dumps({
                "error": "No cached backtest data available",
                "message": "Run the upload_backtest_to_azure.py script to populate cache",
                "db_connected": db.connected if db else False
            }),
            status_code=500,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Backtest endpoint error")
        return func.HttpResponse(
            json.dumps({
                "error": str(e),
                "type": type(e).__name__
            }),
            status_code=500,
            mimetype="application/json"
        )

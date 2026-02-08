"""Incremental backtest update - appends recent data to existing cache."""

import json
import sys
import os
import logging
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database
from shared.mac_scorer import calculate_mac

logger = logging.getLogger(__name__)

# Crisis events for annotation
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


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Incrementally update backtest cache with current MAC score.
    
    Reads the latest MAC from indicator cache and appends to backtest time series.
    Much faster than full refresh - only adds today's data point.
    """
    start_time = datetime.utcnow()
    
    db = get_database()
    if not db.connected:
        return func.HttpResponse(
            json.dumps({"error": "Database not connected"}),
            status_code=500,
            mimetype="application/json"
        )
    
    try:
        # Get existing cache
        existing_cache = db.get_backtest_cache_chunked()
        
        if not existing_cache or "time_series" not in existing_cache:
            return func.HttpResponse(
                json.dumps({
                    "error": "No existing backtest cache found",
                    "hint": "Initial cache must be uploaded using upload script"
                }),
                status_code=404,
                mimetype="application/json"
            )
        
        existing_series = existing_cache["time_series"]
        
        # Get the latest cached indicators
        cached_indicators = db.get_cached_indicators()
        
        if not cached_indicators:
            return func.HttpResponse(
                json.dumps({
                    "error": "No cached indicators found",
                    "hint": "Run /api/refresh first to populate indicator cache"
                }),
                status_code=404,
                mimetype="application/json"
            )
        
        # Get today's date (use weekly alignment - nearest Thursday)
        today = datetime.utcnow()
        # Find nearest Thursday (weekday 3)
        days_since_thursday = (today.weekday() - 3) % 7
        aligned_date = today - timedelta(days=days_since_thursday)
        date_str = aligned_date.strftime("%Y-%m-%d")
        
        # Check if we already have this date
        existing_dates = {p["date"] for p in existing_series}
        
        if date_str in existing_dates:
            # Update existing point instead of adding
            logger.info(f"Updating existing point for {date_str}")
        
        # Score all 7 pillars using the real MAC scorer
        mac_result = calculate_mac(cached_indicators)
        mac_score = mac_result["mac_score"]
        pillar_scores = {
            name: data["score"]
            for name, data in mac_result["pillar_scores"].items()
        }
        status = get_status(mac_score)
        multiplier = mac_result.get("multiplier", 2 - mac_score)
        
        new_point = {
            "date": date_str,
            "mac_score": round(mac_score, 4),
            "status": status,
            "multiplier": round(multiplier, 6),
            "pillar_scores": {k: round(v, 4) for k, v in pillar_scores.items()},
            "breach_flags": mac_result.get("breach_flags", []),
            "indicators": {}
        }
        
        # Check for crisis event
        for event_date, event_info in CRISIS_EVENTS.items():
            event_dt = datetime.strptime(event_date, "%Y-%m-%d")
            if abs((aligned_date - event_dt).days) <= 3:
                new_point["crisis_event"] = {
                    "name": event_info["name"],
                    "description": event_info["description"],
                    "event_date": event_date
                }
                break
        
        # Merge with existing data
        merged_dict = {p["date"]: p for p in existing_series}
        merged_dict[date_str] = new_point  # Add/update
        
        # Sort by date
        merged_series = sorted(merged_dict.values(), key=lambda x: x["date"])
        
        # Recalculate crisis analysis
        crisis_analysis = calculate_crisis_analysis(
            merged_series,
            datetime.strptime(merged_series[0]["date"], "%Y-%m-%d"),
            datetime.strptime(merged_series[-1]["date"], "%Y-%m-%d")
        )
        
        # Calculate summary
        mac_scores = [p["mac_score"] for p in merged_series]
        total_crises = len(crisis_analysis)
        crises_with_warning = sum(1 for c in crisis_analysis if c["days_of_warning"] > 0)
        warning_rate = f"{(crises_with_warning / total_crises * 100):.0f}%" if total_crises > 0 else "N/A"
        avg_lead = sum(c["days_of_warning"] for c in crisis_analysis) / total_crises if total_crises > 0 else 0
        avg_stretched = sum(c["days_stretched"] for c in crisis_analysis) / total_crises if total_crises > 0 else 0
        
        # Build updated cache
        updated_cache = {
            "parameters": {
                "start_date": merged_series[0]["date"],
                "end_date": merged_series[-1]["date"],
                "interval_days": 7,
            },
            "summary": {
                "data_points": len(merged_series),
                "min_mac": round(min(mac_scores), 4),
                "max_mac": round(max(mac_scores), 4),
                "avg_mac": round(sum(mac_scores) / len(mac_scores), 4),
                "crises_analyzed": total_crises,
                "average_lead_time_days": round(avg_lead, 1),
                "average_days_stretched_before_event": round(avg_stretched, 1),
                "warning_rate": warning_rate,
                "prediction_accuracy": warning_rate,
            },
            "crisis_prediction_analysis": crisis_analysis,
            "time_series": merged_series,
            "crisis_events": CRISIS_EVENTS,
        }
        
        # Save to cache using chunked storage
        success = db.save_backtest_cache_chunked(updated_cache)
        
        if not success:
            return func.HttpResponse(
                json.dumps({"error": "Failed to save updated cache"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Also save to backtesthistory table for individual record access
        backtest_record = {
            "date": date_str,
            "mac_score": new_point["mac_score"],
            "mac_status": new_point["status"],
            "liquidity": pillar_scores.get("liquidity", 0),
            "valuation": pillar_scores.get("valuation", 0),
            "positioning": pillar_scores.get("positioning", 0),
            "volatility": pillar_scores.get("volatility", 0),
            "policy": pillar_scores.get("policy", 0),
            "contagion": pillar_scores.get("contagion", 0),
            "private_credit": pillar_scores.get("private_credit", 0),
        }
        db.save_backtest_results_batch([backtest_record])
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "update_type": "incremental",
                "date_added": date_str,
                "mac_score": new_point["mac_score"],
                "mac_status": new_point["status"],
                "total_points": len(merged_series),
                "date_range": {
                    "start": merged_series[0]["date"],
                    "end": merged_series[-1]["date"]
                },
                "crises_analyzed": total_crises,
                "elapsed_seconds": round(elapsed, 2)
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.exception("Incremental backtest update failed")
        return func.HttpResponse(
            json.dumps({
                "error": str(e),
                "type": type(e).__name__
            }),
            status_code=500,
            mimetype="application/json"
        )


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


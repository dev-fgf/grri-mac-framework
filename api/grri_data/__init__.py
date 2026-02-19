"""
GRRI Data API Endpoint - Retrieve GRRI/GRS data from Azure Tables.

Routes:
- GET /api/grri - Get all current GRRI scores
- GET /api/grri?country=USA - Get data for specific country
- GET /api/grri?year=2024 - Get data for specific year
- GET /api/grri/summary - Get summary with rankings
- GET /api/grri/refresh - Trigger data refresh (POST)
"""

import json
import sys
import os
from datetime import datetime
import azure.functions as func
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database

logger = logging.getLogger(__name__)

# Country names mapping
COUNTRY_NAMES = {
    "ARG": "Argentina", "AUS": "Australia", "BRA": "Brazil", "CAN": "Canada",
    "CHN": "China", "FRA": "France", "DEU": "Germany", "IND": "India",
    "IDN": "Indonesia", "ITA": "Italy", "JPN": "Japan", "MEX": "Mexico",
    "RUS": "Russia", "SAU": "Saudi Arabia", "ZAF": "South Africa",
    "KOR": "South Korea", "TUR": "Turkey", "GBR": "United Kingdom", "USA": "United States",
    "EGY": "Egypt", "NGA": "Nigeria", "POL": "Poland", "THA": "Thailand",
    "VNM": "Vietnam", "ARE": "UAE", "MYS": "Malaysia", "PHL": "Philippines",
}


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handle GRRI data requests."""

    db = get_database()
    action = req.route_params.get('action', '')

    # Query parameters
    country = req.params.get('country')
    year = req.params.get('year')
    quarter = req.params.get('quarter')

    # Route handling
    if action == 'summary':
        return get_summary(db)
    elif action == 'refresh':
        # Redirect to refresh endpoint (POST only)
        return func.HttpResponse(
            json.dumps({"error": "Use POST /api/grri/refresh to trigger refresh"}),
            status_code=405,
            mimetype="application/json"
        )
    elif country:
        return get_country_data(db, country)
    elif year:
        return get_year_data(db, int(year), quarter)
    else:
        return get_all_current(db)


def get_country_data(db, country_code: str) -> func.HttpResponse:
    """Get GRRI data for a specific country."""
    country_code = country_code.upper()

    data = db.get_grri_by_country(country_code)

    return func.HttpResponse(
        json.dumps({
            "country_code": country_code,
            "country_name": COUNTRY_NAMES.get(country_code, country_code),
            "data": data,
            "count": len(data),
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2),
        status_code=200,
        mimetype="application/json"
    )


def get_year_data(db, year: int, quarter: str = None) -> func.HttpResponse:
    """Get GRRI data for all countries in a specific year."""

    data = db.get_grri_by_year(year, quarter)

    return func.HttpResponse(
        json.dumps({
            "year": year,
            "quarter": quarter,
            "data": data,
            "count": len(data),
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2),
        status_code=200,
        mimetype="application/json"
    )


def get_all_current(db) -> func.HttpResponse:
    """Get current GRRI data for all G20 countries."""

    current_year = datetime.now().year - 1  # Most recent complete year
    data = db.get_grri_by_year(current_year)

    # If no data for last year, try current year
    if not data:
        data = db.get_grri_by_year(datetime.now().year)

    return func.HttpResponse(
        json.dumps({
            "year": current_year,
            "data": data,
            "count": len(data),
            "db_connected": db.connected,
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2),
        status_code=200,
        mimetype="application/json"
    )


def get_summary(db) -> func.HttpResponse:
    """Get GRRI summary with rankings and pillar breakdowns."""

    current_year = datetime.now().year - 1
    data = db.get_grri_by_year(current_year)

    if not data:
        data = db.get_grri_by_year(datetime.now().year)

    # Calculate rankings
    rankings = sorted(
        [d for d in data if d.get("composite_score") is not None],
        key=lambda x: x.get("composite_score", 0),
        reverse=True
    )

    # Pillar averages
    pillar_avgs = {}
    for pillar in ["political", "economic", "social", "environmental"]:
        scores = [d.get(f"{pillar}_score") for d in data if d.get(f"{pillar}_score") is not None]
        if scores:
            pillar_avgs[pillar] = round(sum(scores) / len(scores), 2)

    # Top risk countries
    top_risk = rankings[:5] if rankings else []

    # Lowest risk countries
    lowest_risk = rankings[-5:][::-1] if len(rankings) >= 5 else rankings[::-1]

    return func.HttpResponse(
        json.dumps({
            "year": current_year,
            "total_countries": len(data),
            "rankings": rankings,
            "pillar_averages": pillar_avgs,
            "top_risk": top_risk,
            "lowest_risk": lowest_risk,
            "methodology": {
                "pillars": ["political", "economic", "social", "environmental"],
                "weights": [0.25, 0.25, 0.25, 0.25],
                "scale": "0-100 (higher = higher risk)"
            },
            "data_sources": [
                "IMF World Economic Outlook",
                "World Bank Governance Indicators",
                "UNDP Human Development Index",
                "V-Dem Democracy Indices"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2),
        status_code=200,
        mimetype="application/json"
    )

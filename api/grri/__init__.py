"""GRRI API endpoint - retrieve G20 Global Risk and Resilience Index data."""

import json
import sys
import os
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database
from shared.grri_client import G20_COUNTRIES, GRRI_PILLARS


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get GRRI data.

    GET /api/grri
    Query params:
        country: ISO 3166-1 alpha-3 code (e.g., USA, GBR, CHN)
        year: Year (e.g., 2024)
        quarter: Quarter (e.g., Q2) - optional with year
        latest: If "true", get most recent data for all countries
    """
    country = req.params.get("country")
    year = req.params.get("year")
    quarter = req.params.get("quarter")
    latest = req.params.get("latest", "false").lower() == "true"

    db = get_database()

    # Check database connection
    if not db.connected:
        # Return demo data if not connected
        return func.HttpResponse(
            json.dumps({
                "data": get_demo_data(),
                "data_source": "Demo Data",
                "message": "Database not connected - showing demo data"
            }, indent=2),
            mimetype="application/json"
        )

    try:
        if country:
            # Get data for specific country
            country = country.upper()
            if country not in G20_COUNTRIES:
                return func.HttpResponse(
                    json.dumps({
                        "error": f"Invalid country code: {country}",
                        "valid_codes": list(G20_COUNTRIES.keys())
                    }),
                    status_code=400,
                    mimetype="application/json"
                )

            data = db.get_grri_by_country(country)
            response = {
                "country": country,
                "country_name": G20_COUNTRIES.get(country, ""),
                "data": data,
                "count": len(data),
            }

        elif year:
            # Get data for specific year
            try:
                year_int = int(year)
            except ValueError:
                return func.HttpResponse(
                    json.dumps({"error": "Invalid year format"}),
                    status_code=400,
                    mimetype="application/json"
                )

            data = db.get_grri_by_year(year_int, quarter)

            # Add rankings
            for i, record in enumerate(data):
                record["rank"] = i + 1

            response = {
                "year": year_int,
                "quarter": quarter,
                "rankings": data,
                "count": len(data),
            }

        elif latest:
            # Get latest data for all countries
            data = db.get_grri_latest()

            # Add rankings
            for i, record in enumerate(data):
                record["rank"] = i + 1

            response = {
                "latest": True,
                "rankings": data,
                "count": len(data),
            }

        else:
            # Return metadata/summary
            count = db.get_grri_count()
            latest_data = db.get_grri_latest()

            response = {
                "description": "GRRI - Global Risk and Resilience Index",
                "coverage": {
                    "countries": list(G20_COUNTRIES.keys()),
                    "country_count": len(G20_COUNTRIES),
                },
                "pillars": {
                    name: info["name"]
                    for name, info in GRRI_PILLARS.items()
                },
                "stored_records": count,
                "endpoints": {
                    "by_country": "/api/grri?country=USA",
                    "by_year": "/api/grri?year=2024",
                    "by_year_quarter": "/api/grri?year=2024&quarter=Q2",
                    "latest": "/api/grri?latest=true",
                    "seed_data": "POST /api/grri/seed",
                },
                "sample_rankings": latest_data[:5] if latest_data else None,
            }

        return func.HttpResponse(
            json.dumps(response, indent=2),
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


def get_demo_data() -> list:
    """Return demo GRRI data when database is not connected."""
    return [
        {
            "country_code": "JPN",
            "country_name": "Japan",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.78,
            "political_score": 0.82,
            "economic_score": 0.71,
            "social_score": 0.85,
            "environmental_score": 0.74,
            "rank": 1,
        },
        {
            "country_code": "DEU",
            "country_name": "Germany",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.76,
            "political_score": 0.80,
            "economic_score": 0.68,
            "social_score": 0.82,
            "environmental_score": 0.73,
            "rank": 2,
        },
        {
            "country_code": "CAN",
            "country_name": "Canada",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.74,
            "political_score": 0.78,
            "economic_score": 0.70,
            "social_score": 0.80,
            "environmental_score": 0.68,
            "rank": 3,
        },
        {
            "country_code": "GBR",
            "country_name": "United Kingdom",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.72,
            "political_score": 0.74,
            "economic_score": 0.66,
            "social_score": 0.78,
            "environmental_score": 0.70,
            "rank": 4,
        },
        {
            "country_code": "USA",
            "country_name": "United States",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.68,
            "political_score": 0.62,
            "economic_score": 0.72,
            "social_score": 0.65,
            "environmental_score": 0.73,
            "rank": 5,
        },
        {
            "country_code": "CHN",
            "country_name": "China",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.58,
            "political_score": 0.45,
            "economic_score": 0.72,
            "social_score": 0.55,
            "environmental_score": 0.60,
            "rank": 6,
        },
        {
            "country_code": "IND",
            "country_name": "India",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.52,
            "political_score": 0.58,
            "economic_score": 0.55,
            "social_score": 0.42,
            "environmental_score": 0.53,
            "rank": 7,
        },
        {
            "country_code": "BRA",
            "country_name": "Brazil",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.48,
            "political_score": 0.52,
            "economic_score": 0.45,
            "social_score": 0.44,
            "environmental_score": 0.51,
            "rank": 8,
        },
        {
            "country_code": "RUS",
            "country_name": "Russia",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.38,
            "political_score": 0.28,
            "economic_score": 0.45,
            "social_score": 0.42,
            "environmental_score": 0.37,
            "rank": 9,
        },
        {
            "country_code": "TUR",
            "country_name": "Turkey",
            "year": 2024,
            "quarter": "Q4",
            "composite_score": 0.35,
            "political_score": 0.32,
            "economic_score": 0.28,
            "social_score": 0.40,
            "environmental_score": 0.40,
            "rank": 10,
        },
    ]

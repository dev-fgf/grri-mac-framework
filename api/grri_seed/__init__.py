"""GRRI Seed endpoint - fetches G20 resilience data and stores in Azure Table Storage."""

import json
import sys
import os
import logging
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.grri_client import get_grri_client, G20_COUNTRIES
from shared.database import get_database

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Fetch GRRI data from World Bank and store in Azure Table Storage.

    POST /api/grri/seed
    Query params:
        start_year: Start year (default 2015)
        end_year: End year (default 2025)
    """
    logger.info("Starting GRRI data ingestion")

    # Get parameters
    try:
        start_year = int(req.params.get("start_year", "2015"))
        end_year = int(req.params.get("end_year", "2025"))
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid year parameters"}),
            status_code=400,
            mimetype="application/json"
        )

    # Check database connection
    db = get_database()
    if not db.connected:
        return func.HttpResponse(
            json.dumps({
                "error": "Database not connected",
                "message": "AZURE_STORAGE_CONNECTION_STRING not configured"
            }),
            status_code=500,
            mimetype="application/json"
        )

    try:
        # Fetch data from World Bank
        client = get_grri_client()
        dataset = client.build_grri_dataset(start_year, end_year)

        if not dataset:
            return func.HttpResponse(
                json.dumps({
                    "error": "No data fetched",
                    "message": "World Bank API returned no data for the specified range"
                }),
                status_code=500,
                mimetype="application/json"
            )

        # Save to database
        saved_count = db.save_grri_batch(dataset)

        # Calculate summary statistics
        countries_with_data = len(set(r["country_code"] for r in dataset))
        years_with_data = len(set(r["year"] for r in dataset))

        # Get score ranges
        scores = [r["composite_score"] for r in dataset if r["composite_score"]]
        if scores:
            min_score = min(scores)
            max_score = max(scores)
            avg_score = sum(scores) / len(scores)
        else:
            min_score = max_score = avg_score = None

        response = {
            "status": "success",
            "message": f"Ingested {saved_count} GRRI records",
            "parameters": {
                "start_year": start_year,
                "end_year": end_year,
            },
            "summary": {
                "total_records": len(dataset),
                "saved_records": saved_count,
                "countries": countries_with_data,
                "years": years_with_data,
                "score_range": {
                    "min": round(min_score, 4) if min_score else None,
                    "max": round(max_score, 4) if max_score else None,
                    "avg": round(avg_score, 4) if avg_score else None,
                },
            },
            "countries_covered": list(G20_COUNTRIES.keys()),
        }

        return func.HttpResponse(
            json.dumps(response, indent=2),
            mimetype="application/json"
        )

    except Exception as e:
        logger.error(f"GRRI ingestion failed: {e}")
        return func.HttpResponse(
            json.dumps({
                "error": "Ingestion failed",
                "message": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )

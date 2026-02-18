"""Data source health endpoint.

Returns per-source health status including schema validation results,
value range checks, and staleness detection. Used by the frontend
admin banner and for manual monitoring via /api/health.
"""

import json
import sys
import os
from datetime import datetime
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.database import get_database
    from shared.health_registry import get_detailed_health
    IMPORTS_OK = True
except Exception:
    IMPORTS_OK = False


def main(req: func.HttpRequest) -> func.HttpResponse:
    if not IMPORTS_OK:
        return func.HttpResponse(
            json.dumps({
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0.0",
                "note": "Health monitoring imports unavailable",
            }),
            mimetype="application/json"
        )

    # Belt-and-braces auth check (SWA route also enforces)
    user = req.headers.get("x-ms-client-principal-name")
    if not user:
        return func.HttpResponse(
            json.dumps({"error": "Authentication required"}),
            status_code=401,
            mimetype="application/json"
        )

    try:
        db = get_database()
        health = get_detailed_health(db)
        health["version"] = "2.0.0"
        health["authenticated_user"] = user

        return func.HttpResponse(
            json.dumps(health, indent=2),
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
            }),
            status_code=500,
            mimetype="application/json"
        )

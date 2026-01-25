"""Azure Table Storage client for MAC history storage."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import json
import uuid

logger = logging.getLogger(__name__)

# Check if azure-data-tables is available
try:
    from azure.data.tables import TableServiceClient, TableClient
    from azure.core.exceptions import ResourceExistsError
    TABLE_STORAGE_AVAILABLE = True
except ImportError:
    TABLE_STORAGE_AVAILABLE = False
    logger.warning("azure-data-tables not available - using in-memory storage")


class MACDatabase:
    """Database client for storing and retrieving MAC history."""

    TABLE_NAME = "machistory"

    def __init__(self):
        self.connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.connected = False
        self._memory_store = []  # Fallback in-memory storage
        self._table_client = None

        if self.connection_string and TABLE_STORAGE_AVAILABLE:
            try:
                self._init_table()
                self.connected = True
            except Exception as e:
                logger.error(f"Table Storage connection failed: {e}")

    def _init_table(self):
        """Initialize Table Storage table if needed."""
        service_client = TableServiceClient.from_connection_string(self.connection_string)

        # Create table if it doesn't exist
        try:
            service_client.create_table(self.TABLE_NAME)
            logger.info(f"Created table: {self.TABLE_NAME}")
        except ResourceExistsError:
            pass  # Table already exists

        self._table_client = service_client.get_table_client(self.TABLE_NAME)

    def save_snapshot(self, mac_data: dict) -> bool:
        """Save a MAC snapshot to the database."""
        try:
            if self.connected and self._table_client:
                return self._save_to_table(mac_data)
            else:
                return self._save_to_memory(mac_data)
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return False

    def _save_to_table(self, mac_data: dict) -> bool:
        """Save to Azure Table Storage."""
        pillars = mac_data.get("pillar_scores", {})
        now = datetime.utcnow()

        # PartitionKey: date (YYYY-MM-DD) for efficient date range queries
        # RowKey: timestamp + unique ID for ordering and uniqueness
        partition_key = now.strftime("%Y-%m-%d")
        row_key = now.strftime("%H%M%S") + "_" + str(uuid.uuid4())[:8]

        entity = {
            "PartitionKey": partition_key,
            "RowKey": row_key,
            "timestamp": now.isoformat(),
            "mac_score": mac_data.get("mac_score"),
            "liquidity_score": pillars.get("liquidity", {}).get("score"),
            "valuation_score": pillars.get("valuation", {}).get("score"),
            "positioning_score": pillars.get("positioning", {}).get("score"),
            "volatility_score": pillars.get("volatility", {}).get("score"),
            "policy_score": pillars.get("policy", {}).get("score"),
            "multiplier": mac_data.get("multiplier"),
            "breach_flags": json.dumps(mac_data.get("breach_flags", [])),
            "is_live": mac_data.get("is_live", False),
            "indicators": json.dumps(mac_data.get("indicators", {})),
        }

        self._table_client.create_entity(entity)
        return True

    def _save_to_memory(self, mac_data: dict) -> bool:
        """Save to in-memory storage (fallback)."""
        pillars = mac_data.get("pillar_scores", {})

        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "mac_score": mac_data.get("mac_score"),
            "liquidity": pillars.get("liquidity", {}).get("score"),
            "valuation": pillars.get("valuation", {}).get("score"),
            "positioning": pillars.get("positioning", {}).get("score"),
            "volatility": pillars.get("volatility", {}).get("score"),
            "policy": pillars.get("policy", {}).get("score"),
            "is_live": mac_data.get("is_live", False),
        }

        self._memory_store.append(record)

        # Keep only last 90 days worth
        if len(self._memory_store) > 90:
            self._memory_store = self._memory_store[-90:]

        return True

    def get_history(self, days: int = 30) -> list:
        """Get MAC history for the specified number of days."""
        try:
            if self.connected and self._table_client:
                return self._get_from_table(days)
            else:
                return self._get_from_memory(days)
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    def _get_from_table(self, days: int) -> list:
        """Get history from Azure Table Storage."""
        # Generate partition keys for the date range
        results = []
        today = datetime.utcnow()

        for i in range(days + 1):
            date = today - timedelta(days=i)
            partition_key = date.strftime("%Y-%m-%d")

            try:
                # Query entities for this partition
                filter_query = f"PartitionKey eq '{partition_key}'"
                entities = self._table_client.query_entities(filter_query)

                for entity in entities:
                    results.append({
                        "date": entity["PartitionKey"],
                        "timestamp": entity.get("timestamp", ""),
                        "mac": entity.get("mac_score"),
                        "liquidity": entity.get("liquidity_score"),
                        "valuation": entity.get("valuation_score"),
                        "positioning": entity.get("positioning_score"),
                        "volatility": entity.get("volatility_score"),
                        "policy": entity.get("policy_score"),
                        "is_live": entity.get("is_live", False),
                    })
            except Exception as e:
                logger.warning(f"Error querying partition {partition_key}: {e}")
                continue

        # Sort by timestamp ascending
        results.sort(key=lambda x: x.get("timestamp", ""))
        return results

    def _get_from_memory(self, days: int) -> list:
        """Get history from in-memory storage."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        return [
            record for record in self._memory_store
            if datetime.fromisoformat(record["timestamp"]) >= cutoff
        ]

    def get_latest(self) -> Optional[dict]:
        """Get the most recent MAC snapshot."""
        try:
            if self.connected and self._table_client:
                # Get today's partition first
                today = datetime.utcnow().strftime("%Y-%m-%d")
                filter_query = f"PartitionKey eq '{today}'"
                entities = list(self._table_client.query_entities(filter_query))

                if not entities:
                    # Try yesterday if today has no data
                    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
                    filter_query = f"PartitionKey eq '{yesterday}'"
                    entities = list(self._table_client.query_entities(filter_query))

                if entities:
                    # Get the most recent (last RowKey when sorted)
                    entities.sort(key=lambda x: x["RowKey"], reverse=True)
                    entity = entities[0]

                    return {
                        "timestamp": entity.get("timestamp"),
                        "mac_score": entity.get("mac_score"),
                        "pillar_scores": {
                            "liquidity": {"score": entity.get("liquidity_score")},
                            "valuation": {"score": entity.get("valuation_score")},
                            "positioning": {"score": entity.get("positioning_score")},
                            "volatility": {"score": entity.get("volatility_score")},
                            "policy": {"score": entity.get("policy_score")},
                        },
                        "multiplier": entity.get("multiplier"),
                        "breach_flags": json.loads(entity.get("breach_flags", "[]")),
                        "is_live": entity.get("is_live", False),
                    }
            else:
                if self._memory_store:
                    return self._memory_store[-1]
        except Exception as e:
            logger.error(f"Failed to get latest: {e}")

        return None


# Singleton instance
_db_instance = None


def get_database() -> MACDatabase:
    """Get database singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = MACDatabase()
    return _db_instance

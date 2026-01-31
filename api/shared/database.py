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
    BACKTEST_TABLE_NAME = "backtesthistory"
    GRRI_TABLE_NAME = "grridata"
    INDICATORS_TABLE_NAME = "macindicators"  # Raw market data cache

    def __init__(self):
        self.connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.connected = False
        self._memory_store = []  # Fallback in-memory storage
        self._indicators_cache = {}  # In-memory indicator cache
        self._table_client = None
        self._indicators_table = None

        if self.connection_string and TABLE_STORAGE_AVAILABLE:
            try:
                self._init_table()
                self.connected = True
            except Exception as e:
                logger.error(f"Table Storage connection failed: {e}")

    def _init_table(self):
        """Initialize Table Storage table if needed."""
        service_client = TableServiceClient.from_connection_string(self.connection_string)

        # Create tables if they don't exist
        for table_name in [self.TABLE_NAME, self.INDICATORS_TABLE_NAME]:
            try:
                service_client.create_table(table_name)
                logger.info(f"Created table: {table_name}")
            except ResourceExistsError:
                pass  # Table already exists

        self._table_client = service_client.get_table_client(self.TABLE_NAME)
        self._indicators_table = service_client.get_table_client(self.INDICATORS_TABLE_NAME)

    # ==================== RAW INDICATORS STORAGE ====================

    def save_indicators(self, indicators: dict, source: str = "FRED") -> bool:
        """Save raw market indicators to the cache table.
        
        Args:
            indicators: Dict of indicator name -> value
            source: Data source name (FRED, CFTC, etc.)
        
        Returns:
            True if saved successfully
        """
        if not self.connected or not self._indicators_table:
            # Fallback to memory
            self._indicators_cache = {
                "timestamp": datetime.utcnow().isoformat(),
                "source": source,
                **indicators
            }
            return True
        
        try:
            now = datetime.utcnow()
            # Use "CURRENT" partition for latest data, date partition for history
            entity = {
                "PartitionKey": "CURRENT",
                "RowKey": source,
                "timestamp": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            
            # Add each indicator as a column
            for key, value in indicators.items():
                if value is not None:
                    entity[key] = float(value) if isinstance(value, (int, float)) else str(value)
            
            # Upsert (create or update)
            self._indicators_table.upsert_entity(entity, mode="replace")
            
            # Also save to historical partition
            hist_entity = entity.copy()
            hist_entity["PartitionKey"] = now.strftime("%Y-%m-%d")
            hist_entity["RowKey"] = f"{source}_{now.strftime('%H%M%S')}"
            self._indicators_table.upsert_entity(hist_entity, mode="replace")
            
            logger.info(f"Saved {len(indicators)} indicators from {source}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save indicators: {e}")
            return False

    def get_cached_indicators(self, source: str = "FRED") -> Optional[dict]:
        """Get the most recent cached indicators.
        
        Returns:
            Dict with indicators and metadata, or None if not available
        """
        if not self.connected or not self._indicators_table:
            # Return from memory cache
            if self._indicators_cache:
                return self._indicators_cache
            return None
        
        try:
            # Get from CURRENT partition
            entity = self._indicators_table.get_entity("CURRENT", source)
            
            # Extract indicators (exclude metadata columns)
            metadata_keys = {"PartitionKey", "RowKey", "timestamp", "updated_at", "etag"}
            indicators = {
                k: v for k, v in entity.items() 
                if k not in metadata_keys and not k.startswith("odata")
            }
            
            return {
                "timestamp": entity.get("timestamp"),
                "source": source,
                "indicators": indicators,
                "age_seconds": (datetime.utcnow() - datetime.fromisoformat(entity.get("timestamp", datetime.utcnow().isoformat()))).total_seconds()
            }
            
        except Exception as e:
            logger.warning(f"No cached indicators for {source}: {e}")
            return None

    def get_all_cached_indicators(self) -> dict:
        """Get all cached indicators from all sources combined."""
        result = {
            "timestamp": None,
            "indicators": {},
            "sources": {},
        }
        
        for source in ["FRED", "CFTC"]:
            cached = self.get_cached_indicators(source)
            if cached:
                result["indicators"].update(cached.get("indicators", {}))
                result["sources"][source] = {
                    "timestamp": cached.get("timestamp"),
                    "age_seconds": cached.get("age_seconds"),
                }
                # Use most recent timestamp
                if not result["timestamp"] or cached.get("timestamp", "") > result["timestamp"]:
                    result["timestamp"] = cached.get("timestamp")
        
        return result if result["indicators"] else None

    def is_cache_fresh(self, source: str = "FRED", max_age_hours: int = 6) -> bool:
        """Check if cached data is fresh enough."""
        cached = self.get_cached_indicators(source)
        if not cached:
            return False
        
        age_seconds = cached.get("age_seconds", float("inf"))
        return age_seconds < (max_age_hours * 3600)

    # ==================== EXISTING MAC HISTORY METHODS ====================

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

    # ==================== BACKTEST HISTORY METHODS ====================

    def _get_backtest_table(self):
        """Get or create the backtest history table client."""
        if not self.connected or not self.connection_string:
            return None

        try:
            service_client = TableServiceClient.from_connection_string(
                self.connection_string
            )
            try:
                service_client.create_table(self.BACKTEST_TABLE_NAME)
                logger.info(f"Created table: {self.BACKTEST_TABLE_NAME}")
            except ResourceExistsError:
                pass
            return service_client.get_table_client(self.BACKTEST_TABLE_NAME)
        except Exception as e:
            logger.error(f"Failed to get backtest table: {e}")
            return None

    def save_backtest_point(self, date_str: str, data: dict) -> bool:
        """Save a single backtest data point."""
        table = self._get_backtest_table()
        if not table:
            return False

        try:
            # PartitionKey: year for efficient range queries
            # RowKey: full date for uniqueness
            year = date_str[:4]
            pillars = data.get("pillar_scores", {})

            entity = {
                "PartitionKey": year,
                "RowKey": date_str,
                "mac_score": data.get("mac_score"),
                "status": data.get("status"),
                "multiplier": data.get("multiplier"),
                "liquidity": pillars.get("liquidity", 0),
                "valuation": pillars.get("valuation", 0),
                "positioning": pillars.get("positioning", 0),
                "volatility": pillars.get("volatility", 0),
                "policy": pillars.get("policy", 0),
                "breach_flags": json.dumps(data.get("breach_flags", [])),
                "indicators": json.dumps(data.get("indicators", {})),
            }

            # Upsert to handle updates
            table.upsert_entity(entity)
            return True
        except Exception as e:
            logger.error(f"Failed to save backtest point {date_str}: {e}")
            return False

    def save_backtest_batch(self, points: list) -> int:
        """Save multiple backtest points. Returns count saved."""
        saved = 0
        for point in points:
            if self.save_backtest_point(point["date"], point):
                saved += 1
        return saved

    def get_backtest_history(
        self, start_date: str, end_date: str
    ) -> list:
        """Get stored backtest history for a date range."""
        table = self._get_backtest_table()
        if not table:
            return []

        try:
            results = []
            start_year = int(start_date[:4])
            end_year = int(end_date[:4])

            # Query each year partition
            for year in range(start_year, end_year + 1):
                filter_query = (
                    f"PartitionKey eq '{year}' and "
                    f"RowKey ge '{start_date}' and RowKey le '{end_date}'"
                )
                entities = table.query_entities(filter_query)

                for entity in entities:
                    results.append({
                        "date": entity["RowKey"],
                        "mac_score": entity.get("mac_score"),
                        "status": entity.get("status"),
                        "multiplier": entity.get("multiplier"),
                        "pillar_scores": {
                            "liquidity": entity.get("liquidity", 0),
                            "valuation": entity.get("valuation", 0),
                            "positioning": entity.get("positioning", 0),
                            "volatility": entity.get("volatility", 0),
                            "policy": entity.get("policy", 0),
                        },
                        "breach_flags": json.loads(
                            entity.get("breach_flags", "[]")
                        ),
                        "indicators": json.loads(
                            entity.get("indicators", "{}")
                        ),
                    })

            # Sort by date
            results.sort(key=lambda x: x["date"])
            return results
        except Exception as e:
            logger.error(f"Failed to get backtest history: {e}")
            return []

    def get_backtest_count(self) -> int:
        """Get count of stored backtest points."""
        table = self._get_backtest_table()
        if not table:
            return 0

        try:
            count = 0
            entities = table.query_entities(select=["PartitionKey"])
            for _ in entities:
                count += 1
            return count
        except Exception as e:
            logger.error(f"Failed to count backtest: {e}")
            return 0

    # ==================== GRRI DATA METHODS ====================

    def _get_grri_table(self):
        """Get or create the GRRI data table client."""
        if not self.connected or not self.connection_string:
            return None

        try:
            service_client = TableServiceClient.from_connection_string(
                self.connection_string
            )
            try:
                service_client.create_table(self.GRRI_TABLE_NAME)
                logger.info(f"Created table: {self.GRRI_TABLE_NAME}")
            except ResourceExistsError:
                pass
            return service_client.get_table_client(self.GRRI_TABLE_NAME)
        except Exception as e:
            logger.error(f"Failed to get GRRI table: {e}")
            return None

    def save_grri_record(self, record: dict) -> bool:
        """Save a single GRRI data record (country-year-quarter)."""
        table = self._get_grri_table()
        if not table:
            return False

        try:
            # PartitionKey: country code for efficient country queries
            # RowKey: year-quarter for ordering (e.g., "2024-Q2")
            country = record.get("country_code", "UNK")
            year = record.get("year", 2024)
            quarter = record.get("quarter", "Q4")
            row_key = f"{year}-{quarter}"

            entity = {
                "PartitionKey": country,
                "RowKey": row_key,
                "country_name": record.get("country_name", ""),
                "year": year,
                "quarter": quarter,
                "composite_score": record.get("composite_score"),
                "political_score": record.get("political_score"),
                "economic_score": record.get("economic_score"),
                "social_score": record.get("social_score"),
                "environmental_score": record.get("environmental_score"),
                "data_source": record.get("data_source", ""),
                "timestamp": record.get("timestamp", datetime.utcnow().isoformat()),
            }

            # Upsert to handle updates
            table.upsert_entity(entity)
            return True
        except Exception as e:
            logger.error(f"Failed to save GRRI record: {e}")
            return False

    def save_grri_batch(self, records: list) -> int:
        """Save multiple GRRI records. Returns count saved."""
        saved = 0
        for record in records:
            if self.save_grri_record(record):
                saved += 1
        return saved

    def get_grri_by_country(self, country_code: str) -> list:
        """Get all GRRI data for a specific country."""
        table = self._get_grri_table()
        if not table:
            return []

        try:
            filter_query = f"PartitionKey eq '{country_code}'"
            entities = table.query_entities(filter_query)

            results = []
            for entity in entities:
                results.append({
                    "country_code": entity["PartitionKey"],
                    "country_name": entity.get("country_name", ""),
                    "year": entity.get("year"),
                    "quarter": entity.get("quarter"),
                    "composite_score": entity.get("composite_score"),
                    "political_score": entity.get("political_score"),
                    "economic_score": entity.get("economic_score"),
                    "social_score": entity.get("social_score"),
                    "environmental_score": entity.get("environmental_score"),
                    "data_source": entity.get("data_source", ""),
                })

            # Sort by year-quarter descending (most recent first)
            results.sort(key=lambda x: x["RowKey"] if "RowKey" in x else f"{x['year']}-{x['quarter']}", reverse=True)
            return results
        except Exception as e:
            logger.error(f"Failed to get GRRI for {country_code}: {e}")
            return []

    def get_grri_by_year(self, year: int, quarter: str = None) -> list:
        """Get GRRI data for all countries in a specific year/quarter."""
        table = self._get_grri_table()
        if not table:
            return []

        try:
            # Query all entities and filter by year
            results = []
            entities = table.query_entities("")

            for entity in entities:
                entity_year = entity.get("year")
                entity_quarter = entity.get("quarter")

                if entity_year == year:
                    if quarter is None or entity_quarter == quarter:
                        results.append({
                            "country_code": entity["PartitionKey"],
                            "country_name": entity.get("country_name", ""),
                            "year": entity_year,
                            "quarter": entity_quarter,
                            "composite_score": entity.get("composite_score"),
                            "political_score": entity.get("political_score"),
                            "economic_score": entity.get("economic_score"),
                            "social_score": entity.get("social_score"),
                            "environmental_score": entity.get("environmental_score"),
                        })

            # Sort by composite score descending (rankings)
            results.sort(key=lambda x: x.get("composite_score") or 0, reverse=True)
            return results
        except Exception as e:
            logger.error(f"Failed to get GRRI for year {year}: {e}")
            return []

    def get_grri_latest(self) -> list:
        """Get the most recent GRRI data for all countries."""
        table = self._get_grri_table()
        if not table:
            return []

        try:
            # Get all data and find latest per country
            latest_by_country = {}
            entities = table.query_entities("")

            for entity in entities:
                country = entity["PartitionKey"]
                row_key = entity["RowKey"]

                if country not in latest_by_country:
                    latest_by_country[country] = entity
                else:
                    # Compare row keys to find most recent
                    if row_key > latest_by_country[country]["RowKey"]:
                        latest_by_country[country] = entity

            results = []
            for country, entity in latest_by_country.items():
                results.append({
                    "country_code": country,
                    "country_name": entity.get("country_name", ""),
                    "year": entity.get("year"),
                    "quarter": entity.get("quarter"),
                    "composite_score": entity.get("composite_score"),
                    "political_score": entity.get("political_score"),
                    "economic_score": entity.get("economic_score"),
                    "social_score": entity.get("social_score"),
                    "environmental_score": entity.get("environmental_score"),
                })

            # Sort by composite score descending
            results.sort(key=lambda x: x.get("composite_score") or 0, reverse=True)
            return results
        except Exception as e:
            logger.error(f"Failed to get latest GRRI: {e}")
            return []

    def get_grri_count(self) -> int:
        """Get count of stored GRRI records."""
        table = self._get_grri_table()
        if not table:
            return 0

        try:
            count = 0
            entities = table.query_entities(select=["PartitionKey"])
            for _ in entities:
                count += 1
            return count
        except Exception as e:
            logger.error(f"Failed to count GRRI: {e}")
            return 0

    # ==================== CACHED BACKTEST RESULTS ====================

    BACKTEST_CACHE_TABLE = "backtestcache"

    def _get_backtest_cache_table(self):
        """Get or create the backtest cache table client."""
        if not self.connected or not self.connection_string:
            return None

        try:
            service_client = TableServiceClient.from_connection_string(
                self.connection_string
            )
            try:
                service_client.create_table(self.BACKTEST_CACHE_TABLE)
                logger.info(f"Created table: {self.BACKTEST_CACHE_TABLE}")
            except ResourceExistsError:
                pass
            return service_client.get_table_client(self.BACKTEST_CACHE_TABLE)
        except Exception as e:
            logger.error(f"Failed to get backtest cache table: {e}")
            return None

    def save_backtest_cache(self, backtest_response: dict, cache_key: str = "default") -> bool:
        """Save pre-computed backtest results to cache.
        
        Args:
            backtest_response: Full backtest API response to cache
            cache_key: Cache identifier (e.g., "default", "2006-2026")
        
        Returns:
            True if saved successfully
        """
        table = self._get_backtest_cache_table()
        if not table:
            return False

        try:
            now = datetime.utcnow()
            
            # Store as JSON since response is complex
            entity = {
                "PartitionKey": "CACHE",
                "RowKey": cache_key,
                "timestamp": now.isoformat(),
                "updated_at": now.isoformat(),
                "response_json": json.dumps(backtest_response),
                "data_points": backtest_response.get("parameters", {}).get("data_points", 0),
                "start_date": backtest_response.get("parameters", {}).get("start_date", ""),
                "end_date": backtest_response.get("parameters", {}).get("end_date", ""),
            }

            table.upsert_entity(entity, mode="replace")
            logger.info(f"Saved backtest cache: {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save backtest cache: {e}")
            return False

    def get_backtest_cache(self, cache_key: str = "default") -> Optional[dict]:
        """Get cached backtest results.
        
        Returns:
            Dict with cached response and metadata, or None if not available
        """
        table = self._get_backtest_cache_table()
        if not table:
            return None

        try:
            entity = table.get_entity("CACHE", cache_key)
            
            response_json = entity.get("response_json", "{}")
            timestamp = entity.get("timestamp", datetime.utcnow().isoformat())
            
            age_seconds = (datetime.utcnow() - datetime.fromisoformat(timestamp)).total_seconds()
            
            return {
                "timestamp": timestamp,
                "age_seconds": age_seconds,
                "cached_response": json.loads(response_json),
            }
        except Exception as e:
            logger.warning(f"No backtest cache for {cache_key}: {e}")
            return None

    def is_backtest_cache_fresh(self, cache_key: str = "default", max_age_hours: int = 24) -> bool:
        """Check if backtest cache is fresh enough."""
        cached = self.get_backtest_cache(cache_key)
        if not cached:
            return False
        
        return cached.get("age_seconds", float("inf")) < (max_age_hours * 3600)

    def save_backtest_cache_chunked(self, backtest_data: dict) -> bool:
        """Save backtest results using chunked storage pattern.
        
        Stores summary in CACHE/summary and time_series in TIMESERIES/chunk_* partitions.
        Uses 100 points per chunk to stay under Azure Table 64KB entity limit.
        
        Args:
            backtest_data: Full backtest response dict with time_series
            
        Returns:
            True if save succeeded, False otherwise
        """
        table = self._get_backtest_cache_table()
        if not table:
            return False
            
        try:
            # Extract time series for chunked storage
            time_series = backtest_data.pop("time_series", [])
            
            # 1. Save summary (without time_series)
            summary_entity = {
                "PartitionKey": "CACHE",
                "RowKey": "summary",
                "response_json": json.dumps(backtest_data),
                "timestamp": datetime.utcnow().isoformat(),
                "data_points": len(time_series),
                "chunks": (len(time_series) + 99) // 100  # Ceiling division
            }
            table.upsert_entity(summary_entity)
            
            # 2. Delete old chunks first
            old_chunks = list(table.query_entities("PartitionKey eq 'TIMESERIES'"))
            for chunk in old_chunks:
                table.delete_entity(chunk["PartitionKey"], chunk["RowKey"])
            
            # 3. Save new chunks (100 points each)
            chunk_size = 100
            for i in range(0, len(time_series), chunk_size):
                chunk_data = time_series[i:i + chunk_size]
                chunk_index = i // chunk_size
                
                chunk_entity = {
                    "PartitionKey": "TIMESERIES",
                    "RowKey": f"chunk_{chunk_index:04d}",
                    "chunk_index": chunk_index,
                    "data_json": json.dumps(chunk_data),
                    "points": len(chunk_data),
                    "timestamp": datetime.utcnow().isoformat()
                }
                table.upsert_entity(chunk_entity)
            
            # Restore time_series to original dict
            backtest_data["time_series"] = time_series
            
            logger.info(f"Saved backtest cache: {len(time_series)} points in {(len(time_series) + 99) // 100} chunks")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to save chunked backtest cache: {e}")
            return False

    def get_backtest_cache_chunked(self) -> Optional[dict]:
        """Get cached backtest results stored in chunked format.
        
        Reads summary from CACHE/summary and time_series from TIMESERIES/chunk_* partitions.
        
        Returns:
            Full backtest response dict or None if not available
        """
        table = self._get_backtest_cache_table()
        if not table:
            return None

        try:
            # 1. Get summary
            summary_entity = table.get_entity("CACHE", "summary")
            summary_json = summary_entity.get("response_json", "{}")
            response = json.loads(summary_json)
            
            timestamp = summary_entity.get("timestamp", datetime.utcnow().isoformat())
            age_seconds = (datetime.utcnow() - datetime.fromisoformat(timestamp)).total_seconds()
            
            # 2. Get time series chunks
            time_series = []
            chunk_entities = list(table.query_entities("PartitionKey eq 'TIMESERIES'"))
            
            # Sort by chunk index
            chunk_entities.sort(key=lambda x: x.get("chunk_index", 0))
            
            for chunk_entity in chunk_entities:
                chunk_data = json.loads(chunk_entity.get("data_json", "[]"))
                time_series.extend(chunk_data)
            
            # 3. Combine
            response["time_series"] = time_series
            response["data_source"] = "Cached (Azure Table)"
            response["cache_age_seconds"] = age_seconds
            
            logger.info(f"Loaded backtest cache: {len(time_series)} points from {len(chunk_entities)} chunks")
            return response
            
        except Exception as e:
            logger.warning(f"Failed to get chunked backtest cache: {e}")
            return None


# Singleton instance
_db_instance = None


def get_database() -> MACDatabase:
    """Get database singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = MACDatabase()
    return _db_instance

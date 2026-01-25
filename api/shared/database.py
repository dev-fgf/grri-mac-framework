"""Azure SQL Database client for MAC history storage."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import json

logger = logging.getLogger(__name__)

# Check if pyodbc is available (for Azure SQL)
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    logger.warning("pyodbc not available - using in-memory storage")


class MACDatabase:
    """Database client for storing and retrieving MAC history."""

    def __init__(self):
        self.connection_string = os.environ.get("SQL_CONNECTION_STRING")
        self.connected = False
        self._memory_store = []  # Fallback in-memory storage

        if self.connection_string and PYODBC_AVAILABLE:
            try:
                self._init_db()
                self.connected = True
            except Exception as e:
                logger.error(f"Database connection failed: {e}")

    def _get_connection(self):
        """Get database connection."""
        if not self.connection_string or not PYODBC_AVAILABLE:
            return None
        return pyodbc.connect(self.connection_string)

    def _init_db(self):
        """Initialize database schema if needed."""
        conn = self._get_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='mac_history' AND xtype='U')
            CREATE TABLE mac_history (
                id INT IDENTITY(1,1) PRIMARY KEY,
                timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
                mac_score FLOAT NOT NULL,
                liquidity_score FLOAT,
                valuation_score FLOAT,
                positioning_score FLOAT,
                volatility_score FLOAT,
                policy_score FLOAT,
                multiplier FLOAT,
                breach_flags NVARCHAR(500),
                is_live BIT DEFAULT 0,
                indicators NVARCHAR(MAX),
                INDEX idx_timestamp (timestamp)
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()

    def save_snapshot(self, mac_data: dict) -> bool:
        """Save a MAC snapshot to the database."""
        try:
            if self.connected:
                return self._save_to_sql(mac_data)
            else:
                return self._save_to_memory(mac_data)
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return False

    def _save_to_sql(self, mac_data: dict) -> bool:
        """Save to Azure SQL Database."""
        conn = self._get_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        pillars = mac_data.get("pillar_scores", {})

        cursor.execute("""
            INSERT INTO mac_history (
                mac_score, liquidity_score, valuation_score,
                positioning_score, volatility_score, policy_score,
                multiplier, breach_flags, is_live, indicators
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mac_data.get("mac_score"),
            pillars.get("liquidity", {}).get("score"),
            pillars.get("valuation", {}).get("score"),
            pillars.get("positioning", {}).get("score"),
            pillars.get("volatility", {}).get("score"),
            pillars.get("policy", {}).get("score"),
            mac_data.get("multiplier"),
            json.dumps(mac_data.get("breach_flags", [])),
            mac_data.get("is_live", False),
            json.dumps(mac_data.get("indicators", {})),
        ))

        conn.commit()
        cursor.close()
        conn.close()
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
            if self.connected:
                return self._get_from_sql(days)
            else:
                return self._get_from_memory(days)
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    def _get_from_sql(self, days: int) -> list:
        """Get history from Azure SQL Database."""
        conn = self._get_connection()
        if not conn:
            return []

        cursor = conn.cursor()

        cursor.execute("""
            SELECT timestamp, mac_score, liquidity_score, valuation_score,
                   positioning_score, volatility_score, policy_score, is_live
            FROM mac_history
            WHERE timestamp >= DATEADD(day, -?, GETUTCDATE())
            ORDER BY timestamp ASC
        """, (days,))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [
            {
                "date": row[0].strftime("%Y-%m-%d"),
                "timestamp": row[0].isoformat(),
                "mac": row[1],
                "liquidity": row[2],
                "valuation": row[3],
                "positioning": row[4],
                "volatility": row[5],
                "policy": row[6],
                "is_live": bool(row[7]),
            }
            for row in rows
        ]

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
            if self.connected:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT TOP 1 timestamp, mac_score, liquidity_score,
                           valuation_score, positioning_score, volatility_score,
                           policy_score, multiplier, breach_flags, is_live
                    FROM mac_history
                    ORDER BY timestamp DESC
                """)
                row = cursor.fetchone()
                cursor.close()
                conn.close()

                if row:
                    return {
                        "timestamp": row[0].isoformat(),
                        "mac_score": row[1],
                        "pillar_scores": {
                            "liquidity": {"score": row[2]},
                            "valuation": {"score": row[3]},
                            "positioning": {"score": row[4]},
                            "volatility": {"score": row[5]},
                            "policy": {"score": row[6]},
                        },
                        "multiplier": row[7],
                        "breach_flags": json.loads(row[8]) if row[8] else [],
                        "is_live": bool(row[9]),
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

"""Database connection management."""

import os
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "mac.db"


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
                     If None, uses MAC_DB_PATH env var or default.
        """
        if db_path is None:
            db_path = os.environ.get("MAC_DB_PATH", str(DEFAULT_DB_PATH))

        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")

        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL statement."""
        return self.connect().execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute SQL statement with multiple parameter sets."""
        return self.connect().executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute and fetch one result."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute and fetch all results."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def init_schema(self):
        """Initialize database schema."""
        schema = """
        -- MAC Snapshots (main table)
        CREATE TABLE IF NOT EXISTS mac_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            mac_score REAL NOT NULL,
            mac_adjusted REAL,
            multiplier REAL,
            is_regime_break INTEGER NOT NULL DEFAULT 0,
            interpretation TEXT,
            liquidity_score REAL NOT NULL DEFAULT 0.5,
            valuation_score REAL NOT NULL DEFAULT 0.5,
            positioning_score REAL NOT NULL DEFAULT 0.5,
            volatility_score REAL NOT NULL DEFAULT 0.5,
            policy_score REAL NOT NULL DEFAULT 0.5,
            breach_flags TEXT,
            china_activation REAL,
            data_source TEXT DEFAULT 'live',
            notes TEXT
        );

        -- Index for time-based queries
        CREATE INDEX IF NOT EXISTS idx_mac_snapshots_timestamp
        ON mac_snapshots(timestamp DESC);

        -- Pillar scores (detailed breakdown)
        CREATE TABLE IF NOT EXISTS pillar_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            pillar_name TEXT NOT NULL,
            score REAL NOT NULL,
            status TEXT,
            is_breaching INTEGER NOT NULL DEFAULT 0,
            indicators_json TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES mac_snapshots(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_pillar_scores_snapshot
        ON pillar_scores(snapshot_id);

        -- China snapshots
        CREATE TABLE IF NOT EXISTS china_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            treasury_score REAL NOT NULL DEFAULT 0,
            rare_earth_score REAL NOT NULL DEFAULT 0,
            tariff_score REAL NOT NULL DEFAULT 0,
            taiwan_score REAL NOT NULL DEFAULT 0,
            cips_score REAL NOT NULL DEFAULT 0,
            composite_score REAL NOT NULL DEFAULT 0,
            treasury_change_billions REAL,
            avg_tariff_pct REAL,
            cips_growth_pct REAL,
            FOREIGN KEY (snapshot_id) REFERENCES mac_snapshots(id) ON DELETE CASCADE
        );

        -- Alerts
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            snapshot_id INTEGER,
            alert_type TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            pillar TEXT,
            current_value REAL,
            threshold REAL,
            acknowledged INTEGER NOT NULL DEFAULT 0,
            acknowledged_at TIMESTAMP,
            FOREIGN KEY (snapshot_id) REFERENCES mac_snapshots(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
        ON alerts(timestamp DESC);

        CREATE INDEX IF NOT EXISTS idx_alerts_level
        ON alerts(level);

        -- Raw indicator values (time-series storage)
        CREATE TABLE IF NOT EXISTS indicator_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            indicator_name TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT,
            series_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_indicator_values_name_time
        ON indicator_values(indicator_name, timestamp DESC);

        -- Metadata table for tracking
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Insert schema version
        INSERT OR REPLACE INTO metadata (key, value, updated_at)
        VALUES ('schema_version', '1.0', CURRENT_TIMESTAMP);
        """

        # Execute schema creation
        self.connect().executescript(schema)
        self.connect().commit()

    def get_schema_version(self) -> Optional[str]:
        """Get current schema version."""
        try:
            row = self.fetchone(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            )
            return row["value"] if row else None
        except sqlite3.OperationalError:
            return None


# Global database instance
_db_instance: Optional[Database] = None


def get_db(db_path: Optional[str] = None) -> Database:
    """Get or create global database instance."""
    global _db_instance

    if _db_instance is None:
        _db_instance = Database(db_path)
        _db_instance.init_schema()

    return _db_instance


def reset_db():
    """Reset global database instance (for testing)."""
    global _db_instance
    if _db_instance is not None:
        _db_instance.close()
        _db_instance = None

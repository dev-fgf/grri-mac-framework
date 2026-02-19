"""Data access repository for MAC database operations."""

from datetime import datetime, timedelta
from typing import Any, Optional

from .connection import Database, get_db
from .models import MACSnapshot, PillarScore, Alert, ChinaSnapshot, IndicatorValue


class MACRepository:
    """Repository for MAC data operations."""

    def __init__(self, db: Optional[Database] = None):
        """
        Initialize repository.

        Args:
            db: Database instance. If None, uses global instance.
        """
        self.db = db or get_db()

    # ==================== MAC Snapshots ====================

    def save_snapshot(self, snapshot: MACSnapshot) -> int:
        """
        Save a MAC snapshot.

        Args:
            snapshot: MACSnapshot to save

        Returns:
            ID of saved snapshot
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO mac_snapshots (
                    timestamp, mac_score, mac_adjusted, multiplier,
                    is_regime_break, interpretation,
                    liquidity_score, valuation_score, positioning_score,
                    volatility_score, policy_score,
                    breach_flags, china_activation, data_source, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.timestamp,
                    snapshot.mac_score,
                    snapshot.mac_adjusted,
                    snapshot.multiplier,
                    1 if snapshot.is_regime_break else 0,
                    snapshot.interpretation,
                    snapshot.liquidity_score,
                    snapshot.valuation_score,
                    snapshot.positioning_score,
                    snapshot.volatility_score,
                    snapshot.policy_score,
                    snapshot.breach_flags,
                    snapshot.china_activation,
                    snapshot.data_source,
                    snapshot.notes,
                ),
            )
            return cursor.lastrowid

    def get_snapshot(self, snapshot_id: int) -> Optional[MACSnapshot]:
        """Get a snapshot by ID."""
        row = self.db.fetchone(
            "SELECT * FROM mac_snapshots WHERE id = ?", (snapshot_id,)
        )
        return self._row_to_snapshot(row) if row else None

    def get_latest_snapshot(self) -> Optional[MACSnapshot]:
        """Get the most recent snapshot."""
        row = self.db.fetchone(
            "SELECT * FROM mac_snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        return self._row_to_snapshot(row) if row else None

    def get_snapshots(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MACSnapshot]:
        """
        Get snapshots within date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            limit: Maximum results
            offset: Result offset for pagination

        Returns:
            List of MACSnapshot objects
        """
        sql = "SELECT * FROM mac_snapshots WHERE 1=1"
        params: list[Any] = []

        if start_date:
            sql += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND timestamp <= ?"
            params.append(end_date)

        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetchall(sql, tuple(params))
        return [self._row_to_snapshot(row) for row in rows]

    def get_daily_snapshots(self, days: int = 30) -> list[MACSnapshot]:
        """Get one snapshot per day for the last N days."""
        start_date = datetime.now() - timedelta(days=days)
        rows = self.db.fetchall(
            """
            SELECT * FROM mac_snapshots
            WHERE timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY timestamp DESC
            """,
            (start_date,),
        )
        return [self._row_to_snapshot(row) for row in rows]

    def _row_to_snapshot(self, row) -> MACSnapshot:
        """Convert database row to MACSnapshot."""
        return MACSnapshot(
            id=row["id"],
            timestamp=row["timestamp"],
            mac_score=row["mac_score"],
            mac_adjusted=row["mac_adjusted"],
            multiplier=row["multiplier"],
            is_regime_break=bool(row["is_regime_break"]),
            interpretation=row["interpretation"] or "",
            liquidity_score=row["liquidity_score"],
            valuation_score=row["valuation_score"],
            positioning_score=row["positioning_score"],
            volatility_score=row["volatility_score"],
            policy_score=row["policy_score"],
            breach_flags=row["breach_flags"] or "",
            china_activation=row["china_activation"],
            data_source=row["data_source"] or "live",
            notes=row["notes"] or "",
        )

    # ==================== Pillar Scores ====================

    def save_pillar_scores(
        self,
        snapshot_id: int,
        scores: list[PillarScore],
    ) -> list[int]:
        """
        Save pillar scores for a snapshot.

        Args:
            snapshot_id: Parent snapshot ID
            scores: List of PillarScore objects

        Returns:
            List of saved score IDs
        """
        ids = []
        with self.db.transaction() as conn:
            for score in scores:
                cursor = conn.execute(
                    """
                    INSERT INTO pillar_scores (
                        snapshot_id, pillar_name, score, status,
                        is_breaching, indicators_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        score.pillar_name,
                        score.score,
                        score.status,
                        1 if score.is_breaching else 0,
                        score.indicators_json,
                    ),
                )
                ids.append(cursor.lastrowid)
        return ids

    def get_pillar_scores(self, snapshot_id: int) -> list[PillarScore]:
        """Get pillar scores for a snapshot."""
        rows = self.db.fetchall(
            "SELECT * FROM pillar_scores WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        return [
            PillarScore(
                id=row["id"],
                snapshot_id=row["snapshot_id"],
                pillar_name=row["pillar_name"],
                score=row["score"],
                status=row["status"] or "",
                is_breaching=bool(row["is_breaching"]),
                indicators_json=row["indicators_json"] or "{}",
            )
            for row in rows
        ]

    # ==================== China Snapshots ====================

    def save_china_snapshot(self, snapshot: ChinaSnapshot) -> int:
        """Save a China activation snapshot."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO china_snapshots (
                    snapshot_id, timestamp,
                    treasury_score, rare_earth_score, tariff_score,
                    taiwan_score, cips_score, composite_score,
                    treasury_change_billions, avg_tariff_pct, cips_growth_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.timestamp,
                    snapshot.treasury_score,
                    snapshot.rare_earth_score,
                    snapshot.tariff_score,
                    snapshot.taiwan_score,
                    snapshot.cips_score,
                    snapshot.composite_score,
                    snapshot.treasury_change_billions,
                    snapshot.avg_tariff_pct,
                    snapshot.cips_growth_pct,
                ),
            )
            return cursor.lastrowid

    def get_china_snapshot(self, snapshot_id: int) -> Optional[ChinaSnapshot]:
        """Get China snapshot linked to a MAC snapshot."""
        row = self.db.fetchone(
            "SELECT * FROM china_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        if not row:
            return None

        return ChinaSnapshot(
            id=row["id"],
            snapshot_id=row["snapshot_id"],
            timestamp=row["timestamp"],
            treasury_score=row["treasury_score"],
            rare_earth_score=row["rare_earth_score"],
            tariff_score=row["tariff_score"],
            taiwan_score=row["taiwan_score"],
            cips_score=row["cips_score"],
            composite_score=row["composite_score"],
            treasury_change_billions=row["treasury_change_billions"],
            avg_tariff_pct=row["avg_tariff_pct"],
            cips_growth_pct=row["cips_growth_pct"],
        )

    # ==================== Alerts ====================

    def save_alert(self, alert: Alert) -> int:
        """Save an alert."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO alerts (
                    timestamp, snapshot_id, alert_type, level, message,
                    pillar, current_value, threshold, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.timestamp,
                    alert.snapshot_id,
                    alert.alert_type,
                    alert.level,
                    alert.message,
                    alert.pillar,
                    alert.current_value,
                    alert.threshold,
                    1 if alert.acknowledged else 0,
                ),
            )
            return cursor.lastrowid

    def save_alerts(self, alerts: list[Alert]) -> list[int]:
        """Save multiple alerts."""
        return [self.save_alert(a) for a in alerts]

    def get_alerts(
        self,
        level: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 100,
    ) -> list[Alert]:
        """Get alerts with optional filters."""
        sql = "SELECT * FROM alerts WHERE 1=1"
        params: list[Any] = []

        if level:
            sql += " AND level = ?"
            params.append(level)
        if acknowledged is not None:
            sql += " AND acknowledged = ?"
            params.append(1 if acknowledged else 0)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetchall(sql, tuple(params))
        return [self._row_to_alert(row) for row in rows]

    def get_unacknowledged_alerts(self) -> list[Alert]:
        """Get all unacknowledged alerts."""
        return self.get_alerts(acknowledged=False)

    def acknowledge_alert(self, alert_id: int) -> bool:
        """Acknowledge an alert."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE alerts
                SET acknowledged = 1, acknowledged_at = ?
                WHERE id = ?
                """,
                (datetime.now(), alert_id),
            )
            return cursor.rowcount > 0

    def _row_to_alert(self, row) -> Alert:
        """Convert database row to Alert."""
        return Alert(
            id=row["id"],
            timestamp=row["timestamp"],
            snapshot_id=row["snapshot_id"],
            alert_type=row["alert_type"],
            level=row["level"],
            message=row["message"],
            pillar=row["pillar"],
            current_value=row["current_value"],
            threshold=row["threshold"],
            acknowledged=bool(row["acknowledged"]),
            acknowledged_at=row["acknowledged_at"],
        )

    # ==================== Indicator Values ====================

    def save_indicator(self, indicator: IndicatorValue) -> int:
        """Save a raw indicator value."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO indicator_values (
                    timestamp, indicator_name, value, source, series_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    indicator.timestamp,
                    indicator.indicator_name,
                    indicator.value,
                    indicator.source,
                    indicator.series_id,
                ),
            )
            return cursor.lastrowid

    def save_indicators(self, indicators: list[IndicatorValue]) -> list[int]:
        """Save multiple indicator values."""
        return [self.save_indicator(i) for i in indicators]

    def get_indicator_history(
        self,
        indicator_name: str,
        days: int = 30,
    ) -> list[IndicatorValue]:
        """Get indicator value history."""
        start_date = datetime.now() - timedelta(days=days)
        rows = self.db.fetchall(
            """
            SELECT * FROM indicator_values
            WHERE indicator_name = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (indicator_name, start_date),
        )
        return [
            IndicatorValue(
                id=row["id"],
                timestamp=row["timestamp"],
                indicator_name=row["indicator_name"],
                value=row["value"],
                source=row["source"] or "",
                series_id=row["series_id"] or "",
            )
            for row in rows
        ]

    def get_latest_indicator(self, indicator_name: str) -> Optional[IndicatorValue]:
        """Get latest value for an indicator."""
        row = self.db.fetchone(
            """
            SELECT * FROM indicator_values
            WHERE indicator_name = ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (indicator_name,),
        )
        if not row:
            return None

        return IndicatorValue(
            id=row["id"],
            timestamp=row["timestamp"],
            indicator_name=row["indicator_name"],
            value=row["value"],
            source=row["source"] or "",
            series_id=row["series_id"] or "",
        )

    # ==================== Analytics ====================

    def get_mac_statistics(self, days: int = 30) -> dict:
        """Get MAC score statistics for the period."""
        start_date = datetime.now() - timedelta(days=days)
        row = self.db.fetchone(
            """
            SELECT
                COUNT(*) as count,
                AVG(mac_score) as avg_score,
                MIN(mac_score) as min_score,
                MAX(mac_score) as max_score,
                AVG(multiplier) as avg_multiplier
            FROM mac_snapshots
            WHERE timestamp >= ?
            """,
            (start_date,),
        )

        if not row or row["count"] == 0:
            return {
                "count": 0,
                "avg_score": None,
                "min_score": None,
                "max_score": None,
                "avg_multiplier": None,
            }

        return {
            "count": row["count"],
            "avg_score": row["avg_score"],
            "min_score": row["min_score"],
            "max_score": row["max_score"],
            "avg_multiplier": row["avg_multiplier"],
        }

    def get_breach_frequency(self, days: int = 30) -> dict[str, int]:
        """Get count of breaches by pillar for the period."""
        start_date = datetime.now() - timedelta(days=days)
        rows = self.db.fetchall(
            """
            SELECT breach_flags FROM mac_snapshots
            WHERE timestamp >= ? AND breach_flags != ''
            """,
            (start_date,),
        )

        counts = {
            "liquidity": 0,
            "valuation": 0,
            "positioning": 0,
            "volatility": 0,
            "policy": 0,
        }

        for row in rows:
            flags = row["breach_flags"].split(",")
            for flag in flags:
                flag = flag.strip()
                if flag in counts:
                    counts[flag] += 1

        return counts

    def get_mac_percentile(self, mac_score: float, days: int = 365) -> float:
        """Get percentile rank of a MAC score against historical data."""
        start_date = datetime.now() - timedelta(days=days)
        row = self.db.fetchone(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN mac_score <= ? THEN 1 ELSE 0 END) as below
            FROM mac_snapshots
            WHERE timestamp >= ?
            """,
            (mac_score, start_date),
        )

        if not row or row["total"] == 0:
            return 50.0  # Default to median if no data

        return (row["below"] / row["total"]) * 100

    # ==================== Maintenance ====================

    def cleanup_old_data(self, days_to_keep: int = 365):
        """Delete data older than specified days."""
        cutoff = datetime.now() - timedelta(days=days_to_keep)

        with self.db.transaction() as conn:
            # Cascading deletes handle pillar_scores and china_snapshots
            conn.execute(
                "DELETE FROM mac_snapshots WHERE timestamp < ?",
                (cutoff,),
            )
            conn.execute(
                "DELETE FROM alerts WHERE timestamp < ?",
                (cutoff,),
            )
            conn.execute(
                "DELETE FROM indicator_values WHERE timestamp < ?",
                (cutoff,),
            )

    def vacuum(self):
        """Compact the database."""
        self.db.execute("VACUUM")

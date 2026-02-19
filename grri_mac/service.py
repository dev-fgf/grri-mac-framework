"""MAC Service - Integrates calculation, storage, and alerting."""

from datetime import datetime
from typing import Optional

from .mac.composite import calculate_mac, MACResult
from .mac.multiplier import mac_to_multiplier
from .china.activation import ChinaActivationScore, ChinaVectorIndicators, ChinaVectorScores
from .china.adjustment import adjust_mac_for_china
from .dashboard.daily import DailyDashboard, DashboardReport
from .dashboard.alerts import AlertSystem, Alert
from .db import get_db, MACRepository, MACSnapshot, ChinaSnapshot
from .db.models import Alert as AlertModel


class MACService:
    """
    High-level service for MAC operations.

    Coordinates:
    - Data fetching
    - MAC calculation
    - Database storage
    - Alerting
    """

    def __init__(
        self,
        fred_client=None,
        cftc_client=None,
        etf_client=None,
        db_path: Optional[str] = None,
        auto_save: bool = True,
    ):
        """
        Initialize MAC service.

        Args:
            fred_client: FREDClient for data fetching
            cftc_client: CFTCClient for positioning data
            etf_client: ETFClient for ETF data
            db_path: Optional database path
            auto_save: Whether to auto-save snapshots to database
        """
        self.fred = fred_client
        self.cftc = cftc_client
        self.etf = etf_client
        self.auto_save = auto_save

        # Initialize database
        self.db = get_db(db_path)
        self.repo = MACRepository(self.db)

        # Initialize components
        self.dashboard = DailyDashboard(fred_client, cftc_client, etf_client)
        self.alert_system = AlertSystem()
        self.china_calc = ChinaActivationScore()

    def calculate_mac(
        self,
        pillar_scores: Optional[dict[str, float]] = None,
        china_indicators: Optional[ChinaVectorIndicators] = None,
        save: Optional[bool] = None,
        data_source: str = "live",
        notes: str = "",
    ) -> tuple[MACResult, Optional[ChinaVectorScores], list[Alert]]:
        """
        Calculate MAC score with optional China adjustment.

        Args:
            pillar_scores: Pre-calculated pillar scores (or will fetch)
            china_indicators: China leverage indicators (optional)
            save: Whether to save to database (defaults to auto_save)
            data_source: Data source label
            notes: Optional notes

        Returns:
            Tuple of (MACResult, ChinaVectorScores or None, list of Alerts)
        """
        # Calculate or use provided pillar scores
        if pillar_scores is None:
            pillar_scores = self._fetch_pillar_scores()

        # Calculate MAC
        mac_result = calculate_mac(pillar_scores)

        # Calculate China adjustment if indicators provided
        china_scores = None
        if china_indicators:
            china_scores = self.china_calc.calculate(china_indicators)
            mac_result.adjusted_score = adjust_mac_for_china(
                mac_result.mac_score,
                china_scores.composite,
            )

        # Calculate multiplier
        mult_result = mac_to_multiplier(
            mac_result.adjusted_score or mac_result.mac_score
        )
        mac_result.multiplier = mult_result.multiplier

        # Check alerts
        alerts = self.alert_system.check_all(
            mac_result,
            china_activation=china_scores.composite if china_scores else None,
            multiplier=mult_result.multiplier,
        )

        # Save to database
        should_save = save if save is not None else self.auto_save
        if should_save:
            self._save_snapshot(mac_result, china_scores, alerts, data_source, notes)

        return mac_result, china_scores, alerts

    def _fetch_pillar_scores(self) -> dict[str, float]:
        """Fetch pillar scores from data sources."""
        from .pillars import (
            LiquidityPillar,
            ValuationPillar,
            PositioningPillar,
            VolatilityPillar,
            PolicyPillar,
        )

        return {
            "liquidity": LiquidityPillar(self.fred, self.etf).get_score(),
            "valuation": ValuationPillar(self.fred).get_score(),
            "positioning": PositioningPillar(self.cftc, self.etf).get_score(),
            "volatility": VolatilityPillar(self.fred, self.etf).get_score(),
            "policy": PolicyPillar(self.fred).get_score(),
        }

    def _save_snapshot(
        self,
        mac_result: MACResult,
        china_scores: Optional[ChinaVectorScores],
        alerts: list[Alert],
        data_source: str,
        notes: str,
    ):
        """Save calculation results to database."""
        # Create MAC snapshot
        snapshot = MACSnapshot(
            timestamp=datetime.now(),
            mac_score=mac_result.mac_score,
            mac_adjusted=mac_result.adjusted_score,
            multiplier=mac_result.multiplier,
            is_regime_break=mac_result.multiplier is None,
            interpretation=self._get_interpretation(mac_result),
            liquidity_score=mac_result.pillar_scores.get("liquidity", 0.5),
            valuation_score=mac_result.pillar_scores.get("valuation", 0.5),
            positioning_score=mac_result.pillar_scores.get("positioning", 0.5),
            volatility_score=mac_result.pillar_scores.get("volatility", 0.5),
            policy_score=mac_result.pillar_scores.get("policy", 0.5),
            breach_flags=",".join(mac_result.breach_flags),
            china_activation=china_scores.composite if china_scores else None,
            data_source=data_source,
            notes=notes,
        )

        snapshot_id = self.repo.save_snapshot(snapshot)

        # Save China snapshot if available
        if china_scores:
            china_snap = ChinaSnapshot(
                snapshot_id=snapshot_id,
                timestamp=datetime.now(),
                treasury_score=china_scores.treasury,
                rare_earth_score=china_scores.rare_earth,
                tariff_score=china_scores.tariff,
                taiwan_score=china_scores.taiwan,
                cips_score=china_scores.cips,
                composite_score=china_scores.composite,
            )
            self.repo.save_china_snapshot(china_snap)

        # Save alerts
        for alert in alerts:
            alert_model = AlertModel(
                timestamp=alert.timestamp,
                snapshot_id=snapshot_id,
                alert_type=alert.alert_type.value,
                level=alert.level.value,
                message=alert.message,
                pillar=alert.pillar,
                current_value=alert.current_value,
                threshold=alert.threshold,
            )
            self.repo.save_alert(alert_model)

    def _get_interpretation(self, mac_result: MACResult) -> str:
        """Get interpretation text for MAC result."""
        from .mac.composite import get_mac_interpretation
        score = mac_result.adjusted_score or mac_result.mac_score
        return get_mac_interpretation(score)

    def generate_report(
        self,
        china_indicators: Optional[ChinaVectorIndicators] = None,
        save: Optional[bool] = None,
    ) -> DashboardReport:
        """
        Generate a full dashboard report.

        Args:
            china_indicators: Optional China leverage indicators
            save: Whether to save to database

        Returns:
            DashboardReport
        """
        mac_result, china_scores, alerts = self.calculate_mac(
            china_indicators=china_indicators,
            save=save,
        )

        return self.dashboard.generate(mac_result, china_scores)

    def get_historical_data(self, days: int = 30) -> list[MACSnapshot]:
        """Get historical MAC snapshots."""
        return self.repo.get_daily_snapshots(days)

    def get_statistics(self, days: int = 30) -> dict:
        """Get MAC statistics for the period."""
        stats = self.repo.get_mac_statistics(days)

        # Add current percentile if we have a latest snapshot
        latest = self.repo.get_latest_snapshot()
        if latest:
            stats["current_score"] = latest.mac_score
            stats["current_percentile"] = self.repo.get_mac_percentile(
                latest.mac_score
            )

        # Add breach frequency
        stats["breach_frequency"] = self.repo.get_breach_frequency(days)

        return stats

    def get_unacknowledged_alerts(self) -> list[AlertModel]:
        """Get all unacknowledged alerts."""
        return self.repo.get_unacknowledged_alerts()

    def acknowledge_alert(self, alert_id: int) -> bool:
        """Acknowledge an alert."""
        return self.repo.acknowledge_alert(alert_id)

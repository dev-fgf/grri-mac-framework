"""Alert system for MAC threshold monitoring."""

from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

from ..mac.composite import MACResult


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    """Types of alerts."""

    PILLAR_AMPLE_TO_THIN = "pillar_ample_to_thin"
    PILLAR_THIN_TO_BREACH = "pillar_thin_to_breach"
    MAC_BELOW_THRESHOLD = "mac_below_threshold"
    MAC_REGIME_BREAK = "mac_regime_break"
    CHINA_ACTIVATION_HIGH = "china_activation_high"
    MULTIPLIER_ELEVATED = "multiplier_elevated"


@dataclass
class Alert:
    """Alert data structure."""

    timestamp: datetime
    alert_type: AlertType
    level: AlertLevel
    message: str
    pillar: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None


class AlertSystem:
    """MAC alert monitoring system."""

    # Default thresholds
    THRESHOLDS = {
        "pillar_thin": 0.5,
        "pillar_breach": 0.2,
        "mac_warning": 0.4,
        "mac_critical": 0.2,
        "china_warning": 0.5,
        "china_critical": 0.8,
        "multiplier_warning": 2.0,
        "multiplier_critical": 3.0,
    }

    def __init__(self, thresholds: Optional[dict] = None):
        """
        Initialize alert system.

        Args:
            thresholds: Optional custom thresholds
        """
        self.thresholds = {**self.THRESHOLDS, **(thresholds or {})}
        self._previous_state: Optional[dict] = None
        self._callbacks: list[Callable[[Alert], None]] = []

    def register_callback(self, callback: Callable[[Alert], None]):
        """Register a callback for when alerts are triggered."""
        self._callbacks.append(callback)

    def _trigger_alert(self, alert: Alert):
        """Trigger an alert and notify callbacks."""
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception:
                pass  # Don't let callback errors break alerting

    def check_pillar_transitions(
        self,
        current_scores: dict[str, float],
        previous_scores: Optional[dict[str, float]] = None,
    ) -> list[Alert]:
        """
        Check for pillar state transitions.

        Args:
            current_scores: Current pillar scores
            previous_scores: Previous pillar scores (for transition detection)

        Returns:
            List of alerts for any transitions
        """
        alerts = []

        if previous_scores is None:
            previous_scores = self._previous_state or {}

        thin_threshold = self.thresholds["pillar_thin"]
        breach_threshold = self.thresholds["pillar_breach"]

        for pillar, current in current_scores.items():
            previous = previous_scores.get(pillar)

            if previous is None:
                continue

            # Check Ample -> Thin transition
            if previous >= thin_threshold and current < thin_threshold:
                alert = Alert(
                    timestamp=datetime.now(),
                    alert_type=AlertType.PILLAR_AMPLE_TO_THIN,
                    level=AlertLevel.WARNING,
                    message=f"{pillar.upper()} pillar crossed from AMPLE to THIN",
                    pillar=pillar,
                    current_value=current,
                    threshold=thin_threshold,
                )
                alerts.append(alert)
                self._trigger_alert(alert)

            # Check Thin -> Breach transition
            if previous >= breach_threshold and current < breach_threshold:
                alert = Alert(
                    timestamp=datetime.now(),
                    alert_type=AlertType.PILLAR_THIN_TO_BREACH,
                    level=AlertLevel.CRITICAL,
                    message=f"{pillar.upper()} pillar crossed from THIN to BREACHING",
                    pillar=pillar,
                    current_value=current,
                    threshold=breach_threshold,
                )
                alerts.append(alert)
                self._trigger_alert(alert)

        # Store current state for next check
        self._previous_state = current_scores.copy()

        return alerts

    def check_mac_level(self, mac_score: float) -> list[Alert]:
        """
        Check MAC level against thresholds.

        Args:
            mac_score: Current MAC score

        Returns:
            List of alerts
        """
        alerts = []

        # Check regime break
        if mac_score < self.thresholds["mac_critical"]:
            alert = Alert(
                timestamp=datetime.now(),
                alert_type=AlertType.MAC_REGIME_BREAK,
                level=AlertLevel.CRITICAL,
                message=f"MAC at {mac_score:.3f} - REGIME BREAK WARNING",
                current_value=mac_score,
                threshold=self.thresholds["mac_critical"],
            )
            alerts.append(alert)
            self._trigger_alert(alert)

        # Check warning level
        elif mac_score < self.thresholds["mac_warning"]:
            alert = Alert(
                timestamp=datetime.now(),
                alert_type=AlertType.MAC_BELOW_THRESHOLD,
                level=AlertLevel.WARNING,
                message=f"MAC at {mac_score:.3f} - Below warning threshold",
                current_value=mac_score,
                threshold=self.thresholds["mac_warning"],
            )
            alerts.append(alert)
            self._trigger_alert(alert)

        return alerts

    def check_china_activation(self, activation: float) -> list[Alert]:
        """
        Check China activation level.

        Args:
            activation: China activation score

        Returns:
            List of alerts
        """
        alerts = []

        if activation >= self.thresholds["china_critical"]:
            alert = Alert(
                timestamp=datetime.now(),
                alert_type=AlertType.CHINA_ACTIVATION_HIGH,
                level=AlertLevel.CRITICAL,
                message=f"China activation at {activation:.1%} - CRITICAL LEVEL",
                current_value=activation,
                threshold=self.thresholds["china_critical"],
            )
            alerts.append(alert)
            self._trigger_alert(alert)

        elif activation >= self.thresholds["china_warning"]:
            alert = Alert(
                timestamp=datetime.now(),
                alert_type=AlertType.CHINA_ACTIVATION_HIGH,
                level=AlertLevel.WARNING,
                message=f"China activation at {activation:.1%} - Elevated",
                current_value=activation,
                threshold=self.thresholds["china_warning"],
            )
            alerts.append(alert)
            self._trigger_alert(alert)

        return alerts

    def check_multiplier(self, multiplier: Optional[float]) -> list[Alert]:
        """
        Check transmission multiplier level.

        Args:
            multiplier: Current transmission multiplier

        Returns:
            List of alerts
        """
        alerts: list[Alert] = []

        if multiplier is None:
            return alerts  # Regime break handled elsewhere

        if multiplier >= self.thresholds["multiplier_critical"]:
            alert = Alert(
                timestamp=datetime.now(),
                alert_type=AlertType.MULTIPLIER_ELEVATED,
                level=AlertLevel.CRITICAL,
                message=f"Transmission multiplier at {multiplier:.2f}x - EXTREME",
                current_value=multiplier,
                threshold=self.thresholds["multiplier_critical"],
            )
            alerts.append(alert)
            self._trigger_alert(alert)

        elif multiplier >= self.thresholds["multiplier_warning"]:
            alert = Alert(
                timestamp=datetime.now(),
                alert_type=AlertType.MULTIPLIER_ELEVATED,
                level=AlertLevel.WARNING,
                message=f"Transmission multiplier at {multiplier:.2f}x - Elevated",
                current_value=multiplier,
                threshold=self.thresholds["multiplier_warning"],
            )
            alerts.append(alert)
            self._trigger_alert(alert)

        return alerts

    def check_all(
        self,
        mac_result: MACResult,
        china_activation: Optional[float] = None,
        multiplier: Optional[float] = None,
    ) -> list[Alert]:
        """
        Run all alert checks.

        Args:
            mac_result: Current MAC result
            china_activation: Optional China activation score
            multiplier: Optional transmission multiplier

        Returns:
            List of all triggered alerts
        """
        alerts = []

        # Check pillar transitions
        alerts.extend(self.check_pillar_transitions(mac_result.pillar_scores))

        # Check MAC level
        mac_to_check = mac_result.adjusted_score or mac_result.mac_score
        alerts.extend(self.check_mac_level(mac_to_check))

        # Check China if provided
        if china_activation is not None:
            alerts.extend(self.check_china_activation(china_activation))

        # Check multiplier if provided
        if multiplier is not None:
            alerts.extend(self.check_multiplier(multiplier))

        return alerts

    def format_alerts(self, alerts: list[Alert]) -> str:
        """Format alerts as text."""
        if not alerts:
            return "No alerts"

        lines = []
        for alert in alerts:
            prefix = {
                AlertLevel.INFO: "[INFO]",
                AlertLevel.WARNING: "[WARN]",
                AlertLevel.CRITICAL: "[CRIT]",
            }.get(alert.level, "[????]")

            lines.append(f"{prefix} {alert.timestamp.strftime('%H:%M:%S')} - {alert.message}")

        return "\n".join(lines)

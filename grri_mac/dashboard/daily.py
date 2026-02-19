"""Daily MAC Dashboard."""

from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from ..mac.composite import MACResult, get_mac_interpretation, get_pillar_status
from ..mac.multiplier import mac_to_multiplier
from ..china.activation import ChinaVectorScores


@dataclass
class DashboardReport:
    """Daily dashboard report."""

    timestamp: datetime
    mac_score: float
    mac_adjusted: Optional[float]
    multiplier: Optional[float]
    pillar_scores: dict[str, float]
    pillar_status: dict[str, str]
    breach_flags: list[str]
    china_activation: Optional[float]
    interpretation: str
    warnings: list[str] = field(default_factory=list)


class DailyDashboard:
    """Daily MAC dashboard generator."""

    def __init__(
        self,
        fred_client=None,
        cftc_client=None,
        etf_client=None,
    ):
        """
        Initialize dashboard.

        Args:
            fred_client: FREDClient for data
            cftc_client: CFTCClient for positioning data
            etf_client: ETFClient for ETF data
        """
        self.fred = fred_client
        self.cftc = cftc_client
        self.etf = etf_client

    def generate(
        self,
        mac_result: Optional[MACResult] = None,
        china_scores: Optional[ChinaVectorScores] = None,
    ) -> DashboardReport:
        """
        Generate daily dashboard report.

        Args:
            mac_result: Pre-calculated MAC result (or will calculate)
            china_scores: Pre-calculated China scores (optional)

        Returns:
            DashboardReport with all metrics
        """
        if mac_result is None:
            # Calculate MAC from scratch
            mac_result = self._calculate_mac()

        # Get multiplier
        mult_result = mac_to_multiplier(
            mac_result.adjusted_score or mac_result.mac_score
        )

        # Generate pillar status
        pillar_status = {
            name: get_pillar_status(score)
            for name, score in mac_result.pillar_scores.items()
        }

        # Generate warnings
        warnings = []
        if mac_result.breach_flags:
            warnings.append(
                f"BREACH WARNING: {', '.join(mac_result.breach_flags)} pillar(s) breaching"
            )
        if mult_result.is_regime_break:
            warnings.append("REGIME BREAK: Point estimates unreliable")
        if mac_result.mac_score < 0.4:
            warnings.append("LOW MAC: Elevated transmission risk")

        return DashboardReport(
            timestamp=datetime.now(),
            mac_score=mac_result.mac_score,
            mac_adjusted=mac_result.adjusted_score,
            multiplier=mult_result.multiplier,
            pillar_scores=mac_result.pillar_scores,
            pillar_status=pillar_status,
            breach_flags=mac_result.breach_flags,
            china_activation=china_scores.composite if china_scores else None,
            interpretation=get_mac_interpretation(
                mac_result.adjusted_score or mac_result.mac_score
            ),
            warnings=warnings,
        )

    def _calculate_mac(self) -> MACResult:
        """Calculate MAC from data sources."""
        from ..pillars import (
            LiquidityPillar,
            ValuationPillar,
            PositioningPillar,
            VolatilityPillar,
            PolicyPillar,
        )
        from ..mac.composite import calculate_mac

        # Calculate each pillar
        liquidity = LiquidityPillar(self.fred, self.etf).get_score()
        valuation = ValuationPillar(self.fred).get_score()
        positioning = PositioningPillar(self.cftc, self.etf).get_score()
        volatility = VolatilityPillar(self.fred, self.etf).get_score()
        policy = PolicyPillar(self.fred).get_score()

        pillars = {
            "liquidity": liquidity,
            "valuation": valuation,
            "positioning": positioning,
            "volatility": volatility,
            "policy": policy,
        }

        return calculate_mac(pillars)

    def format_text_report(self, report: DashboardReport) -> str:
        """
        Format dashboard as text report.

        Args:
            report: DashboardReport to format

        Returns:
            Formatted text string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("MAC DAILY DASHBOARD")
        lines.append(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        lines.append("")

        # Overall MAC
        lines.append("MARKET ABSORPTION CAPACITY")
        lines.append("-" * 30)
        lines.append(f"MAC Score:     {report.mac_score:.3f}")
        if report.mac_adjusted:
            lines.append(f"MAC Adjusted:  {report.mac_adjusted:.3f} (China-adjusted)")
        if report.multiplier:
            lines.append(f"Multiplier:    {report.multiplier:.2f}x")
        else:
            lines.append("Multiplier:    N/A (Regime Break)")
        lines.append("")
        lines.append(f"Status: {report.interpretation}")
        lines.append("")

        # Pillar breakdown
        lines.append("PILLAR BREAKDOWN")
        lines.append("-" * 30)
        for name, score in report.pillar_scores.items():
            status = report.pillar_status.get(name, "")
            flag = " [BREACH]" if name in report.breach_flags else ""
            lines.append(f"{name.capitalize():12} {score:.3f}  {status}{flag}")
        lines.append("")

        # China adjustment
        if report.china_activation is not None:
            lines.append("CHINA ADJUSTMENT")
            lines.append("-" * 30)
            lines.append(f"Activation:    {report.china_activation:.1%}")
            lines.append("")

        # Warnings
        if report.warnings:
            lines.append("WARNINGS")
            lines.append("-" * 30)
            for warning in report.warnings:
                lines.append(f"! {warning}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def format_json_report(self, report: DashboardReport) -> dict:
        """
        Format dashboard as JSON-serializable dict.

        Args:
            report: DashboardReport to format

        Returns:
            Dictionary representation
        """
        return {
            "timestamp": report.timestamp.isoformat(),
            "mac": {
                "score": report.mac_score,
                "adjusted": report.mac_adjusted,
                "multiplier": report.multiplier,
                "interpretation": report.interpretation,
            },
            "pillars": {
                name: {
                    "score": score,
                    "status": report.pillar_status.get(name),
                    "breaching": name in report.breach_flags,
                }
                for name, score in report.pillar_scores.items()
            },
            "china": {
                "activation": report.china_activation,
            }
            if report.china_activation is not None
            else None,
            "warnings": report.warnings,
        }

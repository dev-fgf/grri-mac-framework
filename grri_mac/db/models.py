"""Data models for database storage."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class PillarScore:
    """Individual pillar score record."""

    id: Optional[int] = None
    snapshot_id: Optional[int] = None
    pillar_name: str = ""
    score: float = 0.0
    status: str = ""
    is_breaching: bool = False

    # Raw indicator values (JSON)
    indicators_json: str = "{}"

    @property
    def indicators(self) -> dict:
        return json.loads(self.indicators_json)

    @indicators.setter
    def indicators(self, value: dict):
        self.indicators_json = json.dumps(value)


@dataclass
class MACSnapshot:
    """MAC calculation snapshot at a point in time."""

    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    mac_score: float = 0.0
    mac_adjusted: Optional[float] = None
    multiplier: Optional[float] = None
    is_regime_break: bool = False
    interpretation: str = ""

    # Pillar composite scores
    liquidity_score: float = 0.5
    valuation_score: float = 0.5
    positioning_score: float = 0.5
    volatility_score: float = 0.5
    policy_score: float = 0.5

    # Breach flags (comma-separated)
    breach_flags: str = ""

    # China adjustment
    china_activation: Optional[float] = None

    # Metadata
    data_source: str = "live"  # live, manual, backtest
    notes: str = ""

    def get_pillar_scores(self) -> dict[str, float]:
        return {
            "liquidity": self.liquidity_score,
            "valuation": self.valuation_score,
            "positioning": self.positioning_score,
            "volatility": self.volatility_score,
            "policy": self.policy_score,
        }

    def get_breach_list(self) -> list[str]:
        if not self.breach_flags:
            return []
        return [b.strip() for b in self.breach_flags.split(",") if b.strip()]


@dataclass
class ChinaSnapshot:
    """China leverage activation snapshot."""

    id: Optional[int] = None
    snapshot_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

    treasury_score: float = 0.0
    rare_earth_score: float = 0.0
    tariff_score: float = 0.0
    taiwan_score: float = 0.0
    cips_score: float = 0.0
    composite_score: float = 0.0

    # Raw indicator values
    treasury_change_billions: Optional[float] = None
    avg_tariff_pct: Optional[float] = None
    cips_growth_pct: Optional[float] = None


@dataclass
class Alert:
    """Alert record."""

    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    snapshot_id: Optional[int] = None
    alert_type: str = ""
    level: str = ""  # INFO, WARNING, CRITICAL
    message: str = ""
    pillar: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None


@dataclass
class IndicatorValue:
    """Raw indicator value record for time-series storage."""

    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    indicator_name: str = ""
    value: float = 0.0
    source: str = ""  # FRED, CFTC, ETF, manual
    series_id: str = ""  # Original series ID (e.g., VIXCLS, SOFR)

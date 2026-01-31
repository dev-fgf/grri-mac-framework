"""Historical MAC Scorer - Simplified 3-pillar model for pre-1973 data.

This module calculates a historical Market Absorption Capacity score
using only indicators available before modern data sources.

Modern MAC (6 pillars):      Historical MAC (3 pillars):
- Liquidity                  - [Limited - use credit spread proxy]
- Valuation                  - Credit Stress (BAA-AAA spread)
- Positioning                - Leverage (Margin Debt / Market Cap)
- Volatility                 - Volatility (Realized from returns)
- Policy                     - Policy Room (Fed Funds or Discount Rate)
- Contagion                  - [Limited - embedded in credit spread]

The historical MAC uses z-score normalization to compare across eras.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

from .regime_analysis import (
    get_regime_for_date,
    get_regime_thresholds,
    calculate_z_score,
    get_reg_t_margin_at_date,
)

logger = logging.getLogger(__name__)


@dataclass
class HistoricalMACResult:
    """Result of historical MAC calculation."""
    
    date: datetime
    mac_score: float  # 0-1 scale (1 = ample capacity, 0 = breach)
    status: str  # COMFORTABLE, CAUTIOUS, STRETCHED, CRITICAL
    
    # Component scores (0-1)
    credit_stress_score: float
    leverage_score: float
    volatility_score: float
    policy_score: float
    
    # Raw values
    credit_spread: Optional[float]  # BAA-AAA in %
    margin_debt_ratio: Optional[float]  # Margin/MarketCap %
    realized_vol: Optional[float]  # Annualized %
    policy_rate: Optional[float]  # Fed funds or discount rate
    
    # Context
    regime: str
    reg_t_margin: int


# Thresholds for z-score based scoring
# These are regime-invariant because z-scores self-normalize
ZSCORE_THRESHOLDS = {
    # Credit spread z-score thresholds
    # Higher z-score = wider spread = more stress
    "credit_stress": {
        "ample": -0.5,    # Tighter than average
        "cautious": 0.5,  # Slightly wider
        "stretched": 1.5, # Notably wider
        "breach": 2.5,    # Extreme widening
    },
    
    # Leverage z-score thresholds
    # Higher z-score = more leverage = more risk
    "leverage": {
        "ample": -0.5,
        "cautious": 0.5,
        "stretched": 1.5,
        "breach": 2.5,
    },
    
    # Volatility z-score thresholds
    # Higher z-score = more vol = less absorption capacity
    "volatility": {
        "ample": -0.5,
        "cautious": 0.5,
        "stretched": 1.5,
        "breach": 2.5,
    },
    
    # Policy room (inverted - lower rate = less room)
    # This one uses level, not z-score
    "policy_room_bps": {
        "ample": 400,     # 4%+ rate = ample room to cut
        "cautious": 200,  # 2% = some room
        "stretched": 100, # 1% = limited
        "breach": 50,     # 0.5% = near ZLB
    },
}


def score_from_zscore(
    zscore: float,
    thresholds: Dict[str, float],
    higher_is_worse: bool = True,
) -> float:
    """Convert z-score to 0-1 MAC score.
    
    Args:
        zscore: Standardized score
        thresholds: Dict with ample/cautious/stretched/breach levels
        higher_is_worse: If True, higher z-score = lower MAC score
        
    Returns:
        Score between 0 (breach) and 1 (ample)
    """
    if higher_is_worse:
        if zscore <= thresholds["ample"]:
            return 1.0
        elif zscore <= thresholds["cautious"]:
            # Interpolate between 1.0 and 0.65
            t = (zscore - thresholds["ample"]) / (thresholds["cautious"] - thresholds["ample"])
            return 1.0 - t * 0.35
        elif zscore <= thresholds["stretched"]:
            # Interpolate between 0.65 and 0.35
            t = (zscore - thresholds["cautious"]) / (thresholds["stretched"] - thresholds["cautious"])
            return 0.65 - t * 0.30
        elif zscore <= thresholds["breach"]:
            # Interpolate between 0.35 and 0
            t = (zscore - thresholds["stretched"]) / (thresholds["breach"] - thresholds["stretched"])
            return 0.35 - t * 0.35
        else:
            return 0.0
    else:
        # Higher is better - invert the logic
        if zscore >= thresholds["ample"]:
            return 1.0
        elif zscore >= thresholds["cautious"]:
            t = (thresholds["ample"] - zscore) / (thresholds["ample"] - thresholds["cautious"])
            return 1.0 - t * 0.35
        elif zscore >= thresholds["stretched"]:
            t = (thresholds["cautious"] - zscore) / (thresholds["cautious"] - thresholds["stretched"])
            return 0.65 - t * 0.30
        elif zscore >= thresholds["breach"]:
            t = (thresholds["stretched"] - zscore) / (thresholds["stretched"] - thresholds["breach"])
            return 0.35 - t * 0.35
        else:
            return 0.0


def score_policy_room(rate_pct: float) -> float:
    """Score policy room based on current rate level.
    
    Higher rates = more room to cut = more ammunition.
    """
    rate_bps = rate_pct * 100
    thresholds = ZSCORE_THRESHOLDS["policy_room_bps"]
    
    if rate_bps >= thresholds["ample"]:
        return 1.0
    elif rate_bps >= thresholds["cautious"]:
        t = (thresholds["ample"] - rate_bps) / (thresholds["ample"] - thresholds["cautious"])
        return 1.0 - t * 0.35
    elif rate_bps >= thresholds["stretched"]:
        t = (thresholds["cautious"] - rate_bps) / (thresholds["cautious"] - thresholds["stretched"])
        return 0.65 - t * 0.30
    elif rate_bps >= thresholds["breach"]:
        t = (thresholds["stretched"] - rate_bps) / (thresholds["stretched"] - thresholds["breach"])
        return 0.35 - t * 0.35
    else:
        return 0.0


def get_status(mac_score: float) -> str:
    """Get status label from MAC score."""
    if mac_score >= 0.65:
        return "COMFORTABLE"
    elif mac_score >= 0.50:
        return "CAUTIOUS"
    elif mac_score >= 0.35:
        return "STRETCHED"
    else:
        return "CRITICAL"


class MACHistorical:
    """Historical MAC calculator with regime-aware scoring."""
    
    def __init__(self):
        self._credit_spread_history: List[float] = []
        self._leverage_history: List[float] = []
        self._vol_history: List[float] = []
        self._lookback_periods = 104  # ~2 years of weekly data for z-score
        
    def add_observation(
        self,
        credit_spread: Optional[float] = None,
        margin_debt_ratio: Optional[float] = None,
        realized_vol: Optional[float] = None,
    ):
        """Add historical observation for z-score calculation."""
        if credit_spread is not None:
            self._credit_spread_history.append(credit_spread)
            if len(self._credit_spread_history) > self._lookback_periods * 2:
                self._credit_spread_history = self._credit_spread_history[-self._lookback_periods * 2:]
                
        if margin_debt_ratio is not None:
            self._leverage_history.append(margin_debt_ratio)
            if len(self._leverage_history) > self._lookback_periods * 2:
                self._leverage_history = self._leverage_history[-self._lookback_periods * 2:]
                
        if realized_vol is not None:
            self._vol_history.append(realized_vol)
            if len(self._vol_history) > self._lookback_periods * 2:
                self._vol_history = self._vol_history[-self._lookback_periods * 2:]
    
    def calculate(
        self,
        date: datetime,
        credit_spread: Optional[float] = None,
        margin_debt_ratio: Optional[float] = None,
        realized_vol: Optional[float] = None,
        policy_rate: Optional[float] = None,
    ) -> HistoricalMACResult:
        """Calculate historical MAC score for a given date.
        
        Args:
            date: Date of observation
            credit_spread: BAA-AAA yield spread (%)
            margin_debt_ratio: Margin debt / Market cap (%)
            realized_vol: Annualized realized volatility (%)
            policy_rate: Fed funds or discount rate (%)
            
        Returns:
            HistoricalMACResult with scores and context
        """
        # Add to history for z-score calculation
        self.add_observation(credit_spread, margin_debt_ratio, realized_vol)
        
        # Get regime context
        regime = get_regime_for_date(date)
        regime_name = regime.name if regime else "Unknown"
        reg_t = get_reg_t_margin_at_date(date)
        
        # Calculate component scores
        scores = []
        
        # 1. Credit Stress Score
        if credit_spread is not None and len(self._credit_spread_history) >= 52:
            credit_zscore = calculate_z_score(
                credit_spread,
                self._credit_spread_history,
                window=self._lookback_periods
            )
            credit_stress_score = score_from_zscore(
                credit_zscore,
                ZSCORE_THRESHOLDS["credit_stress"],
                higher_is_worse=True
            )
        else:
            credit_stress_score = 0.5  # Neutral if insufficient data
        scores.append(("credit", credit_stress_score))
        
        # 2. Leverage Score
        if margin_debt_ratio is not None and len(self._leverage_history) >= 52:
            leverage_zscore = calculate_z_score(
                margin_debt_ratio,
                self._leverage_history,
                window=self._lookback_periods
            )
            leverage_score = score_from_zscore(
                leverage_zscore,
                ZSCORE_THRESHOLDS["leverage"],
                higher_is_worse=True
            )
        else:
            leverage_score = 0.5
        scores.append(("leverage", leverage_score))
        
        # 3. Volatility Score
        if realized_vol is not None and len(self._vol_history) >= 52:
            vol_zscore = calculate_z_score(
                realized_vol,
                self._vol_history,
                window=self._lookback_periods
            )
            volatility_score = score_from_zscore(
                vol_zscore,
                ZSCORE_THRESHOLDS["volatility"],
                higher_is_worse=True
            )
        else:
            volatility_score = 0.5
        scores.append(("volatility", volatility_score))
        
        # 4. Policy Room Score
        if policy_rate is not None:
            policy_score = score_policy_room(policy_rate)
        else:
            policy_score = 0.5
        scores.append(("policy", policy_score))
        
        # Weighted average (equal weights for simplicity)
        # Could adjust weights based on data availability
        available_scores = [s[1] for s in scores]
        mac_score = sum(available_scores) / len(available_scores)
        
        return HistoricalMACResult(
            date=date,
            mac_score=round(mac_score, 4),
            status=get_status(mac_score),
            credit_stress_score=round(credit_stress_score, 4),
            leverage_score=round(leverage_score, 4),
            volatility_score=round(volatility_score, 4),
            policy_score=round(policy_score, 4),
            credit_spread=credit_spread,
            margin_debt_ratio=margin_debt_ratio,
            realized_vol=realized_vol,
            policy_rate=policy_rate,
            regime=regime_name,
            reg_t_margin=reg_t,
        )


def run_historical_backtest(
    indicators: Dict[str, List[dict]],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[HistoricalMACResult]:
    """Run MAC calculation over historical indicator data.
    
    Args:
        indicators: Dict from FREDHistoricalClient.get_all_historical_indicators()
        start_date: Start of backtest (default: earliest available)
        end_date: End of backtest (default: latest available)
        
    Returns:
        List of HistoricalMACResult for each period
    """
    mac = MACHistorical()
    results = []
    
    # Build lookups by date
    credit = {d["date"]: d["spread_pct"] for d in indicators.get("credit_spread", [])}
    leverage = {d["date"]: d["ratio_pct"] for d in indicators.get("margin_debt_ratio", [])}
    vol = {d["date"]: d["realized_vol_annualized"] for d in indicators.get("realized_volatility", [])}
    policy = {d["date"]: d["rate"] for d in indicators.get("policy_rate", [])}
    
    # Get all dates
    all_dates = sorted(set(credit.keys()) | set(leverage.keys()) | set(vol.keys()) | set(policy.keys()))
    
    for date_str in all_dates:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        
        if start_date and date < start_date:
            continue
        if end_date and date > end_date:
            continue
            
        result = mac.calculate(
            date=date,
            credit_spread=credit.get(date_str),
            margin_debt_ratio=leverage.get(date_str),
            realized_vol=vol.get(date_str),
            policy_rate=policy.get(date_str),
        )
        results.append(result)
        
    return results

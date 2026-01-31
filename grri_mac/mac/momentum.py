"""
MAC Momentum Analysis - Enhanced Detection via Rate-of-Change
=============================================================

This module adds momentum/trend tracking to MAC scores to improve
early warning detection. Key insight: a declining MAC from 0.65→0.50
is more actionable than a static MAC of 0.52.

New status levels:
- COMFORTABLE (MAC > 0.65)
- CAUTIOUS (MAC 0.50-0.65)
- DETERIORATING (MAC 0.50-0.65 AND declining > 0.05 over 4 weeks) - NEW
- STRETCHED (MAC 0.35-0.50)
- CRITICAL (MAC < 0.35)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from enum import Enum


class MACStatus(Enum):
    """Enhanced MAC status with momentum awareness."""
    COMFORTABLE = "COMFORTABLE"
    CAUTIOUS = "CAUTIOUS"
    DETERIORATING = "DETERIORATING"  # NEW: Trend-based warning
    STRETCHED = "STRETCHED"
    CRITICAL = "CRITICAL"


@dataclass
class MACMomentum:
    """MAC momentum analysis result."""
    current_mac: float
    mac_1w_ago: Optional[float]
    mac_2w_ago: Optional[float]
    mac_4w_ago: Optional[float]
    
    momentum_1w: Optional[float]  # Change over 1 week
    momentum_2w: Optional[float]  # Change over 2 weeks
    momentum_4w: Optional[float]  # Change over 4 weeks
    
    status: MACStatus
    is_deteriorating: bool
    trend_direction: str  # "improving", "stable", "declining", "rapidly_declining"
    
    warning_message: Optional[str]


def calculate_momentum(
    current_mac: float,
    historical_macs: List[Dict],  # [{date: str, mac_score: float}, ...]
    current_date: Optional[datetime] = None,
) -> MACMomentum:
    """
    Calculate MAC momentum from historical data.
    
    Args:
        current_mac: Current MAC score
        historical_macs: List of historical MAC scores with dates
        current_date: Current date (defaults to now)
        
    Returns:
        MACMomentum with trend analysis
    """
    if current_date is None:
        current_date = datetime.now()
    
    # Build date lookup
    mac_lookup = {}
    for entry in historical_macs:
        if isinstance(entry.get("date"), str):
            d = datetime.strptime(entry["date"], "%Y-%m-%d")
        else:
            d = entry["date"]
        mac_lookup[d.strftime("%Y-%m-%d")] = entry["mac_score"]
    
    # Find MAC scores at different lookback periods
    def find_mac_near_date(target_date: datetime, max_diff: int = 7) -> Optional[float]:
        for delta in range(max_diff + 1):
            for sign in [0, -1, 1]:
                check_date = target_date + timedelta(days=sign * delta)
                key = check_date.strftime("%Y-%m-%d")
                if key in mac_lookup:
                    return mac_lookup[key]
        return None
    
    mac_1w_ago = find_mac_near_date(current_date - timedelta(weeks=1))
    mac_2w_ago = find_mac_near_date(current_date - timedelta(weeks=2))
    mac_4w_ago = find_mac_near_date(current_date - timedelta(weeks=4))
    
    # Calculate momentum (change over period)
    momentum_1w = current_mac - mac_1w_ago if mac_1w_ago else None
    momentum_2w = current_mac - mac_2w_ago if mac_2w_ago else None
    momentum_4w = current_mac - mac_4w_ago if mac_4w_ago else None
    
    # Determine trend direction
    if momentum_4w is not None:
        if momentum_4w < -0.10:
            trend_direction = "rapidly_declining"
        elif momentum_4w < -0.03:
            trend_direction = "declining"
        elif momentum_4w > 0.05:
            trend_direction = "improving"
        else:
            trend_direction = "stable"
    elif momentum_2w is not None:
        if momentum_2w < -0.05:
            trend_direction = "rapidly_declining"
        elif momentum_2w < -0.02:
            trend_direction = "declining"
        elif momentum_2w > 0.03:
            trend_direction = "improving"
        else:
            trend_direction = "stable"
    else:
        trend_direction = "unknown"
    
    # Determine if deteriorating (key new signal)
    is_deteriorating = (
        momentum_4w is not None and 
        momentum_4w < -0.05 and 
        current_mac < 0.65
    )
    
    # Calculate enhanced status
    status = calculate_enhanced_status(current_mac, momentum_4w)
    
    # Generate warning message
    warning_message = None
    if is_deteriorating:
        warning_message = (
            f"⚠️ DETERIORATING: MAC declined {abs(momentum_4w):.2f} over 4 weeks "
            f"({mac_4w_ago:.3f} → {current_mac:.3f}). "
            f"Consider reducing risk exposure."
        )
    elif status == MACStatus.STRETCHED:
        warning_message = (
            f"🔴 STRETCHED: MAC at {current_mac:.3f}. "
            f"Significant absorption capacity depletion."
        )
    elif status == MACStatus.CRITICAL:
        warning_message = (
            f"🚨 CRITICAL: MAC at {current_mac:.3f}. "
            f"Regime break risk elevated. Defensive positioning recommended."
        )
    
    return MACMomentum(
        current_mac=current_mac,
        mac_1w_ago=mac_1w_ago,
        mac_2w_ago=mac_2w_ago,
        mac_4w_ago=mac_4w_ago,
        momentum_1w=momentum_1w,
        momentum_2w=momentum_2w,
        momentum_4w=momentum_4w,
        status=status,
        is_deteriorating=is_deteriorating,
        trend_direction=trend_direction,
        warning_message=warning_message,
    )


def calculate_enhanced_status(
    mac_score: float,
    momentum_4w: Optional[float] = None,
) -> MACStatus:
    """
    Calculate enhanced MAC status with momentum awareness.
    
    Traditional thresholds:
    - COMFORTABLE: MAC > 0.65
    - CAUTIOUS: MAC 0.50-0.65
    - STRETCHED: MAC 0.35-0.50
    - CRITICAL: MAC < 0.35
    
    Enhanced: DETERIORATING added when MAC 0.50-0.65 but declining fast
    """
    if mac_score < 0.35:
        return MACStatus.CRITICAL
    elif mac_score < 0.50:
        return MACStatus.STRETCHED
    elif mac_score < 0.65:
        # Check for deteriorating trend
        if momentum_4w is not None and momentum_4w < -0.05:
            return MACStatus.DETERIORATING
        return MACStatus.CAUTIOUS
    else:
        return MACStatus.COMFORTABLE


def get_status_color(status: MACStatus) -> str:
    """Get display color for status."""
    colors = {
        MACStatus.COMFORTABLE: "#22c55e",    # green
        MACStatus.CAUTIOUS: "#eab308",       # yellow
        MACStatus.DETERIORATING: "#f97316",  # orange (NEW)
        MACStatus.STRETCHED: "#ef4444",      # red
        MACStatus.CRITICAL: "#7f1d1d",       # dark red
    }
    return colors.get(status, "#6b7280")


def get_status_action(status: MACStatus) -> str:
    """Get recommended action for status."""
    actions = {
        MACStatus.COMFORTABLE: "Maintain strategic allocation",
        MACStatus.CAUTIOUS: "Review portfolio risk, prepare contingencies",
        MACStatus.DETERIORATING: "⚠️ Reduce equity beta, increase cash buffer",
        MACStatus.STRETCHED: "🔴 Defensive positioning, hedge tail risk",
        MACStatus.CRITICAL: "🚨 Maximum defense, preserve capital",
    }
    return actions.get(status, "Monitor closely")


def analyze_momentum_around_crises(
    backtest_data: List[Dict],
    crisis_dates: List[Tuple[str, str]],  # [(date, name), ...]
) -> Dict:
    """
    Analyze momentum signals around known crises.
    
    Returns detection statistics for momentum-enhanced MAC.
    """
    results = {
        "crises_analyzed": 0,
        "level_warnings": 0,      # MAC < 0.50 at crisis
        "trend_warnings": 0,      # Declining > 0.05 in 4 weeks before
        "enhanced_warnings": 0,   # Either level or trend
        "details": [],
    }
    
    # Build lookup
    mac_lookup = {d["date"]: d["mac_score"] for d in backtest_data}
    
    for crisis_date_str, crisis_name in crisis_dates:
        crisis_date = datetime.strptime(crisis_date_str, "%Y-%m-%d")
        
        # Find MAC at crisis
        mac_at = None
        for delta in range(14):
            for sign in [0, -1, 1]:
                check = (crisis_date + timedelta(days=sign * delta)).strftime("%Y-%m-%d")
                if check in mac_lookup:
                    mac_at = mac_lookup[check]
                    break
            if mac_at:
                break
        
        # Find MAC 4 weeks before
        date_4w = (crisis_date - timedelta(weeks=4)).strftime("%Y-%m-%d")
        mac_4w = None
        for delta in range(14):
            check = (datetime.strptime(date_4w, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
            if check in mac_lookup:
                mac_4w = mac_lookup[check]
                break
        
        if mac_at is None:
            continue
            
        results["crises_analyzed"] += 1
        
        # Check warnings
        level_warning = mac_at < 0.50
        trend_warning = mac_4w is not None and (mac_4w - mac_at) > 0.05
        enhanced_warning = level_warning or trend_warning
        
        if level_warning:
            results["level_warnings"] += 1
        if trend_warning:
            results["trend_warnings"] += 1
        if enhanced_warning:
            results["enhanced_warnings"] += 1
        
        momentum = mac_at - mac_4w if mac_4w else None
        
        results["details"].append({
            "date": crisis_date_str,
            "name": crisis_name,
            "mac_at_crisis": mac_at,
            "mac_4w_before": mac_4w,
            "momentum_4w": momentum,
            "level_warning": level_warning,
            "trend_warning": trend_warning,
            "enhanced_warning": enhanced_warning,
        })
    
    # Calculate rates
    n = results["crises_analyzed"]
    if n > 0:
        results["level_rate"] = results["level_warnings"] / n
        results["trend_rate"] = results["trend_warnings"] / n
        results["enhanced_rate"] = results["enhanced_warnings"] / n
    
    return results


def print_momentum_analysis(momentum: MACMomentum):
    """Pretty print momentum analysis."""
    print(f"\n{'='*50}")
    print(f"  MAC MOMENTUM ANALYSIS")
    print(f"{'='*50}")
    print(f"  Current MAC: {momentum.current_mac:.3f}")
    print(f"  Status: {momentum.status.value}")
    print(f"  Trend: {momentum.trend_direction}")
    print()
    
    if momentum.mac_1w_ago:
        print(f"  1-week momentum: {momentum.momentum_1w:+.3f}")
    if momentum.mac_2w_ago:
        print(f"  2-week momentum: {momentum.momentum_2w:+.3f}")
    if momentum.mac_4w_ago:
        print(f"  4-week momentum: {momentum.momentum_4w:+.3f}")
    
    if momentum.warning_message:
        print()
        print(f"  {momentum.warning_message}")
    
    print()
    print(f"  Recommended Action: {get_status_action(momentum.status)}")


if __name__ == "__main__":
    # Demo with sample data
    import csv
    
    print("Loading backtest data...")
    backtest_data = []
    try:
        with open("backtest_results.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                backtest_data.append({
                    "date": row["date"],
                    "mac_score": float(row["mac_score"]),
                })
        print(f"Loaded {len(backtest_data)} observations")
    except FileNotFoundError:
        print("backtest_results.csv not found")
        exit(1)
    
    # Analyze around crises
    crises = [
        ("2008-03-16", "Bear Stearns"),
        ("2008-09-15", "Lehman Brothers"),
        ("2010-05-06", "Flash Crash"),
        ("2011-08-05", "US Downgrade"),
        ("2015-08-24", "China Black Monday"),
        ("2018-02-05", "Volmageddon"),
        ("2018-12-24", "Fed Tantrum"),
        ("2020-03-16", "COVID Crash"),
        ("2022-06-13", "Crypto/Rate Crisis"),
        ("2023-03-10", "SVB Collapse"),
    ]
    
    print("\n" + "="*70)
    print("  MOMENTUM-ENHANCED CRISIS DETECTION")
    print("="*70)
    
    results = analyze_momentum_around_crises(backtest_data, crises)
    
    print(f"\n  Crises Analyzed: {results['crises_analyzed']}")
    print(f"\n  Detection Rates:")
    print(f"    Level-based (MAC < 0.50):     {results['level_warnings']}/{results['crises_analyzed']} ({results.get('level_rate', 0)*100:.0f}%)")
    print(f"    Trend-based (declining >0.05): {results['trend_warnings']}/{results['crises_analyzed']} ({results.get('trend_rate', 0)*100:.0f}%)")
    print(f"    Enhanced (either):             {results['enhanced_warnings']}/{results['crises_analyzed']} ({results.get('enhanced_rate', 0)*100:.0f}%)")
    
    print(f"\n  Detail by Crisis:")
    print(f"  {'-'*70}")
    for d in results["details"]:
        mac_4w = f"{d['mac_4w_before']:.3f}" if d['mac_4w_before'] else "N/A"
        mom = f"{d['momentum_4w']:+.3f}" if d['momentum_4w'] else "N/A"
        warning = "✓" if d["enhanced_warning"] else "✗"
        print(f"  {d['date']} | {d['name']:20s} | MAC: {d['mac_at_crisis']:.3f} | 4w: {mac_4w} | Δ: {mom:>7s} | {warning}")

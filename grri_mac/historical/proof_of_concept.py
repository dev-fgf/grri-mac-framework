"""
Historical MAC Proof of Concept
===============================

This script fetches historical FRED data back to 1945 and calculates
a simplified MAC score to validate the framework against known crises.

Usage:
    python -m grri_mac.historical.proof_of_concept

Requires:
    FRED_API_KEY environment variable
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from grri_mac.historical.fred_historical import FREDHistoricalClient, get_data_availability
from grri_mac.historical.regime_analysis import (
    REGIME_PERIODS,
    get_crisis_events_in_range,
    REG_T_HISTORY,
)
from grri_mac.historical.mac_historical import MACHistorical, run_historical_backtest


def print_header(title: str):
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_data_availability():
    """Print data availability summary."""
    print_header("DATA AVAILABILITY")
    
    availability = get_data_availability()
    for name, info in sorted(availability.items(), key=lambda x: x[1]["start"]):
        print(f"  {name:20s} {info['start']:12s} {info['frequency']:10s} - {info['description']}")


def print_regime_summary():
    """Print market regime summary."""
    print_header("MARKET REGIMES (1945-Present)")
    
    for regime in REGIME_PERIODS:
        end = regime.end_date.strftime("%Y-%m") if regime.end_date else "Present"
        print(f"\n  {regime.name}")
        print(f"  {'-'*40}")
        print(f"  Period: {regime.start_date.strftime('%Y-%m')} to {end}")
        print(f"  Reg T Margin: {regime.reg_t_margin}")
        print(f"  Baseline Margin Debt/MktCap: {regime.margin_debt_baseline}%")
        print(f"  Baseline Credit Spread: {regime.credit_spread_baseline}%")
        print(f"  Baseline Volatility: {regime.vol_baseline}%")
        print(f"  Crises: {len(regime.crises)}")
        for crisis in regime.crises:
            print(f"    - {crisis['date']}: {crisis['name']} ({crisis['severity']})")


def print_reg_t_history():
    """Print Regulation T margin history."""
    print_header("REGULATION T MARGIN REQUIREMENTS (1934-1974)")
    
    print("  Date          Margin%  Notes")
    print("  " + "-"*50)
    for change in REG_T_HISTORY:
        print(f"  {change['date']}    {change['margin']:3d}%     {change['note']}")
    print("\n  Note: Margin has remained at 50% since January 1974")


def fetch_and_analyze(api_key: str = None):
    """Fetch historical data and calculate MAC scores."""
    print_header("FETCHING HISTORICAL DATA FROM FRED")
    
    client = FREDHistoricalClient(api_key)
    
    # Fetch all indicators
    print("  Fetching margin debt ratio...")
    margin_data = client.get_margin_debt_ratio()
    print(f"    Retrieved {len(margin_data)} observations")
    if margin_data:
        print(f"    Range: {margin_data[0]['date']} to {margin_data[-1]['date']}")
        
        # Show some stats
        ratios = [d["ratio_pct"] for d in margin_data]
        print(f"    Min: {min(ratios):.2f}%  Max: {max(ratios):.2f}%  Avg: {sum(ratios)/len(ratios):.2f}%")
    
    print("\n  Fetching credit spread (BAA-AAA)...")
    credit_data = client.get_credit_spread()
    print(f"    Retrieved {len(credit_data)} observations")
    if credit_data:
        print(f"    Range: {credit_data[0]['date']} to {credit_data[-1]['date']}")
        
        spreads = [d["spread_pct"] for d in credit_data]
        print(f"    Min: {min(spreads):.2f}%  Max: {max(spreads):.2f}%  Avg: {sum(spreads)/len(spreads):.2f}%")
    
    print("\n  Fetching yield curve (10Y-3M)...")
    yield_curve = client.get_yield_curve()
    print(f"    Retrieved {len(yield_curve)} observations")
    if yield_curve:
        print(f"    Range: {yield_curve[0]['date']} to {yield_curve[-1]['date']}")
        
        slopes = [d["slope_pct"] for d in yield_curve]
        inversions = sum(1 for s in slopes if s < 0)
        print(f"    Inversions: {inversions} observations ({inversions/len(slopes)*100:.1f}%)")
    
    print("\n  Fetching policy rate...")
    policy_data = client.get_policy_rate()
    print(f"    Retrieved {len(policy_data)} observations")
    if policy_data:
        print(f"    Range: {policy_data[0]['date']} to {policy_data[-1]['date']}")
        
        rates = [d["rate"] for d in policy_data]
        print(f"    Min: {min(rates):.2f}%  Max: {max(rates):.2f}%  Avg: {sum(rates)/len(rates):.2f}%")
    
    print("\n  Fetching realized volatility...")
    vol_data = client.get_realized_volatility()
    print(f"    Retrieved {len(vol_data)} observations")
    if vol_data:
        print(f"    Range: {vol_data[0]['date']} to {vol_data[-1]['date']}")
        
        vols = [d["realized_vol_annualized"] for d in vol_data]
        print(f"    Min: {min(vols):.1f}%  Max: {max(vols):.1f}%  Avg: {sum(vols)/len(vols):.1f}%")
    
    return {
        "margin_debt_ratio": margin_data,
        "credit_spread": credit_data,
        "yield_curve": yield_curve,
        "policy_rate": policy_data,
        "realized_volatility": vol_data,
    }


def analyze_crisis_periods(indicators: Dict, results: List):
    """Analyze MAC scores around known crisis events."""
    print_header("CRISIS ANALYSIS")
    
    if not results:
        print("  No results to analyze")
        return
        
    # Build lookup
    result_lookup = {r.date.strftime("%Y-%m-%d"): r for r in results}
    
    # Get all crises
    start = datetime(1945, 1, 1)
    end = datetime(2026, 1, 1)
    crises = get_crisis_events_in_range(start, end)
    
    print(f"  Analyzing {len(crises)} crisis events:\n")
    
    warnings_detected = 0
    total_with_data = 0
    
    for crisis in crises:
        crisis_date = crisis["date"]
        crisis_str = crisis_date.strftime("%Y-%m-%d")
        
        # Find nearest data point
        nearest_result = None
        min_diff = float("inf")
        
        for result in results:
            diff = abs((result.date - crisis_date).days)
            if diff < min_diff:
                min_diff = diff
                nearest_result = result
        
        if nearest_result and min_diff <= 90:  # Within 90 days
            total_with_data += 1
            mac = nearest_result.mac_score
            status = nearest_result.status
            
            # Did we have a warning?
            warning = "✓ WARNING" if status in ["STRETCHED", "CRITICAL"] else "  -"
            if status in ["STRETCHED", "CRITICAL"]:
                warnings_detected += 1
            
            print(f"  {crisis['date'].strftime('%Y-%m')} | {crisis['name']:30s} | MAC: {mac:.2f} ({status:11s}) | {warning}")
            print(f"           | Severity: {crisis['severity']:8s} | Regime: {nearest_result.regime}")
            if crisis.get("description"):
                print(f"           | {crisis['description'][:60]}")
            print()
        else:
            print(f"  {crisis['date'].strftime('%Y-%m')} | {crisis['name']:30s} | No data available")
            print()
    
    if total_with_data > 0:
        warning_rate = warnings_detected / total_with_data * 100
        print(f"\n  Summary: {warnings_detected}/{total_with_data} crises had prior warning ({warning_rate:.0f}%)")


def run_backtest_analysis(indicators: Dict):
    """Run full backtest and analyze results."""
    print_header("RUNNING HISTORICAL BACKTEST")
    
    # Run backtest
    results = run_historical_backtest(indicators)
    
    print(f"  Generated {len(results)} MAC calculations")
    
    if results:
        # Stats by regime
        print("\n  Results by Regime:")
        print("  " + "-"*50)
        
        regime_stats = {}
        for r in results:
            if r.regime not in regime_stats:
                regime_stats[r.regime] = []
            regime_stats[r.regime].append(r.mac_score)
        
        for regime, scores in regime_stats.items():
            avg = sum(scores) / len(scores)
            stretched_pct = sum(1 for s in scores if s < 0.5) / len(scores) * 100
            print(f"    {regime:30s}: Avg MAC {avg:.2f}, {stretched_pct:.0f}% in stress")
        
        # Status distribution
        print("\n  Overall Status Distribution:")
        print("  " + "-"*50)
        
        status_counts = {}
        for r in results:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
        
        for status in ["COMFORTABLE", "CAUTIOUS", "STRETCHED", "CRITICAL"]:
            count = status_counts.get(status, 0)
            pct = count / len(results) * 100
            bar = "█" * int(pct / 2)
            print(f"    {status:12s}: {count:5d} ({pct:5.1f}%) {bar}")
    
    return results


def save_results(indicators: Dict, results: List, output_dir: str = "data"):
    """Save results to files for further analysis."""
    print_header("SAVING RESULTS")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Save raw indicators
    indicators_file = os.path.join(output_dir, "historical_indicators.json")
    with open(indicators_file, "w") as f:
        json.dump(indicators, f, indent=2)
    print(f"  Saved indicators to {indicators_file}")
    
    # Save MAC results
    if results:
        results_data = [
            {
                "date": r.date.strftime("%Y-%m-%d"),
                "mac_score": r.mac_score,
                "status": r.status,
                "credit_stress_score": r.credit_stress_score,
                "leverage_score": r.leverage_score,
                "volatility_score": r.volatility_score,
                "policy_score": r.policy_score,
                "credit_spread": r.credit_spread,
                "margin_debt_ratio": r.margin_debt_ratio,
                "realized_vol": r.realized_vol,
                "policy_rate": r.policy_rate,
                "regime": r.regime,
                "reg_t_margin": r.reg_t_margin,
            }
            for r in results
        ]
        
        results_file = os.path.join(output_dir, "historical_mac_results.json")
        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)
        print(f"  Saved {len(results)} MAC results to {results_file}")


def main():
    """Run the proof of concept."""
    print("\n" + "="*60)
    print("  HISTORICAL MAC FRAMEWORK - PROOF OF CONCEPT")
    print("  Extending Market Absorption Capacity Analysis to 1945")
    print("="*60)
    
    # Print documentation
    print_data_availability()
    print_regime_summary()
    print_reg_t_history()
    
    # Check for API key
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print_header("API KEY REQUIRED")
        print("  To fetch live FRED data, set the FRED_API_KEY environment variable:")
        print("    export FRED_API_KEY=your_api_key_here")
        print("\n  Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        print("\n  Skipping data fetch...")
        return
    
    # Fetch data
    indicators = fetch_and_analyze(api_key)
    
    # Run backtest
    results = run_backtest_analysis(indicators)
    
    # Analyze crisis periods
    analyze_crisis_periods(indicators, results)
    
    # Save results
    save_results(indicators, results)
    
    print_header("COMPLETE")
    print("  Historical MAC analysis complete!")
    print("  See data/ directory for full results.")


if __name__ == "__main__":
    main()

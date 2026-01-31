"""
Private Credit Stress Analysis
==============================

Demonstrates how to monitor the $1.7T private credit market that operates
in opaque structures where traditional indicators miss warning signs.

This script:
1. Fetches SLOOS data from FRED (lending standards)
2. Simulates BDC and market data (would need real API)
3. Shows how stress signals propagate

Run: python analyze_private_credit.py
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from grri_mac.pillars.private_credit import (
    PrivateCreditPillar,
    PrivateCreditIndicators,
    SLOOSData,
    BDCData,
    LeveragedLoanData,
    PEFirmData,
    analyze_private_credit_exposure,
    get_private_credit_fred_series,
    get_bdc_tickers,
    get_pe_firm_tickers,
)


def fetch_sloos_from_fred() -> SLOOSData:
    """
    Fetch real SLOOS data from FRED API.
    """
    import requests
    
    # FRED API (free, no key needed for basic access)
    base_url = "https://api.stlouisfed.org/fred/series/observations"
    
    # You can get a free API key at https://fred.stlouisfed.org/docs/api/api_key.html
    # For demo, using public endpoint with limited access
    
    series_map = {
        "ci_standards_large": "DRTSCILM",
        "ci_standards_small": "DRTSCIS",
        "spreads_large": "DRISCFLM",
        "spreads_small": "DRISCFS",
    }
    
    sloos = SLOOSData(observation_date=datetime.now())
    
    for attr, series_id in series_map.items():
        try:
            # Public FRED JSON endpoint (no API key needed)
            url = f"https://fred.stlouisfed.org/graph/fredgraph.json?id={series_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Get latest observation
                if "data" in data and len(data["data"]) > 0:
                    latest = data["data"][-1]
                    value = float(latest.get("value", 0))
                    setattr(sloos, attr, value)
                    print(f"  {series_id}: {value:.1f}%")
        except Exception as e:
            print(f"  {series_id}: Error - {e}")
    
    return sloos


def create_sample_bdc_data() -> BDCData:
    """
    Create sample BDC data.
    
    In production, this would fetch from a market data API.
    Current values would represent hypothetical current state.
    """
    # Example: Normal conditions
    # BDCs typically trade at slight discounts (-2% to +5%)
    
    # Stress scenario would show deeper discounts
    # (these are illustrative - would need real API)
    return BDCData(
        arcc_discount=-3.5,   # Ares Capital: 3.5% discount
        main_discount=2.1,    # Main Street: 2.1% premium
        fsk_discount=-8.2,    # FS KKR: 8.2% discount (stress signal!)
        psec_discount=-12.5,  # Prospect: 12.5% discount (elevated risk)
        gbdc_discount=-1.8,   # Golub: 1.8% discount
        observation_date=datetime.now(),
    )


def create_sample_leveraged_loan_data() -> LeveragedLoanData:
    """
    Create sample leveraged loan ETF data.
    
    BKLN and SRLN are liquid proxies for leveraged loan market health.
    """
    return LeveragedLoanData(
        bkln_price_change_30d=-1.2,   # -1.2% in last 30 days (normal)
        srln_price_change_30d=-0.8,   # -0.8% (normal)
        clo_aaa_spread=120,           # bps over SOFR
        clo_bbb_spread=450,           # bps over SOFR
        observation_date=datetime.now(),
    )


def create_sample_pe_firm_data() -> PEFirmData:
    """
    Create sample PE firm stock data.
    """
    return PEFirmData(
        kkr_change_30d=-2.5,    # KKR down 2.5%
        bx_change_30d=-3.1,     # Blackstone down 3.1%
        apo_change_30d=-4.2,    # Apollo down 4.2%
        cg_change_30d=-1.8,     # Carlyle down 1.8%
        observation_date=datetime.now(),
    )


def create_stress_scenario() -> PrivateCreditIndicators:
    """
    Create a stress scenario showing what private credit distress looks like.
    
    This simulates conditions similar to late 2022 or early 2020.
    """
    return PrivateCreditIndicators(
        sloos=SLOOSData(
            ci_standards_large=45.0,    # 45% net tightening (severe)
            ci_standards_small=55.0,    # 55% net tightening (crisis-level)
            spreads_large=35.0,         # 35% widening spreads
            spreads_small=48.0,         # 48% widening (very high)
        ),
        bdc=BDCData(
            arcc_discount=-18.5,    # Deep discount
            main_discount=-12.0,
            fsk_discount=-28.5,     # Severe
            psec_discount=-35.0,    # Distress
            gbdc_discount=-15.5,
        ),
        leveraged_loans=LeveragedLoanData(
            bkln_price_change_30d=-8.5,   # Sharp selloff
            srln_price_change_30d=-9.2,
            clo_aaa_spread=250,           # Elevated
            clo_bbb_spread=850,           # Stressed
        ),
        pe_firms=PEFirmData(
            kkr_change_30d=-18.5,
            bx_change_30d=-22.0,
            apo_change_30d=-25.5,
            cg_change_30d=-20.0,
        ),
    )


def main():
    """Run private credit stress analysis."""
    
    print("=" * 70)
    print("PRIVATE CREDIT STRESS ANALYSIS")
    print("Monitoring the $1.7T Opaque Credit Market")
    print("=" * 70)
    print()
    
    # Document the problem
    print("1. THE PRIVATE CREDIT BLINDSPOT")
    print("-" * 40)
    analysis = analyze_private_credit_exposure()
    
    print(f"Market Size: {analysis['market_size']}")
    print(f"Growth: {analysis['growth_rate']}")
    print()
    print("Why traditional indicators miss private credit stress:")
    for reason in analysis["why_invisible"]:
        print(f"  • {reason}")
    print()
    
    # Show our proxies
    print("2. OUR INDIRECT MONITORING APPROACH")
    print("-" * 40)
    print(f"Most Reliable: {analysis['our_proxies']['most_reliable']}")
    print(f"Leading Indicator: {analysis['our_proxies']['leading_indicator']}")
    print("Corroborating signals:")
    for signal in analysis["our_proxies"]["corroborating"]:
        print(f"  • {signal}")
    print()
    
    # List FRED series we use
    print("3. FRED SERIES FOR PRIVATE CREDIT")
    print("-" * 40)
    fred_series = get_private_credit_fred_series()
    for series_id, description in fred_series.items():
        print(f"  {series_id}: {description}")
    print()
    
    # List BDCs we monitor
    print("4. BDC UNIVERSE (Real-Time Credit Canaries)")
    print("-" * 40)
    for bdc in get_bdc_tickers():
        print(f"  {bdc['ticker']}: {bdc['name']} ({bdc['weight']*100:.0f}% weight)")
        print(f"         {bdc['note']}")
    print()
    
    # List PE firms
    print("5. PE FIRM STOCKS (Alternative Credit Exposure)")
    print("-" * 40)
    for pe in get_pe_firm_tickers():
        print(f"  {pe['ticker']}: {pe['name']}")
        print(f"         {pe['note']}")
    print()
    
    # Fetch live SLOOS data
    print("6. LIVE SLOOS DATA (Lending Standards)")
    print("-" * 40)
    print("Fetching from FRED...")
    try:
        sloos = fetch_sloos_from_fred()
        print("  Latest SLOOS observations:")
        if sloos.ci_standards_small:
            print(f"    Small firm tightening: {sloos.ci_standards_small:.1f}%")
        if sloos.ci_standards_large:
            print(f"    Large firm tightening: {sloos.ci_standards_large:.1f}%")
    except Exception as e:
        print(f"  Could not fetch SLOOS: {e}")
        sloos = SLOOSData(
            ci_standards_small=25.0,
            ci_standards_large=20.0,
            spreads_small=18.0,
            spreads_large=15.0,
        )
    print()
    
    # Calculate current state score
    print("7. CURRENT STATE ANALYSIS")
    print("-" * 40)
    
    pillar = PrivateCreditPillar()
    
    # Use real SLOOS + sample market data
    current_indicators = PrivateCreditIndicators(
        sloos=sloos,
        bdc=create_sample_bdc_data(),
        leveraged_loans=create_sample_leveraged_loan_data(),
        pe_firms=create_sample_pe_firm_data(),
    )
    
    scores = pillar.calculate_scores(current_indicators)
    
    print(f"Composite Score: {scores.composite:.2f}")
    print(f"Stress Level: {scores.stress_level.value.upper()}")
    print()
    print("Component Scores:")
    print(f"  SLOOS (Fed survey):     {scores.sloos_score:.2f}")
    print(f"  BDC (market signal):    {scores.bdc_score:.2f}")
    print(f"  Leveraged Loans:        {scores.leveraged_loan_score:.2f}")
    print(f"  PE Firms:               {scores.pe_firm_score:.2f}")
    print()
    
    if scores.warning_signals:
        print("Warning Signals:")
        for warning in scores.warning_signals:
            print(f"  ⚠ {warning}")
    else:
        print("No warning signals detected.")
    print()
    
    # Run stress scenario
    print("8. STRESS SCENARIO (What Distress Looks Like)")
    print("-" * 40)
    
    stress_indicators = create_stress_scenario()
    stress_scores = pillar.calculate_scores(stress_indicators)
    
    print(f"Stress Composite Score: {stress_scores.composite:.2f}")
    print(f"Stress Level: {stress_scores.stress_level.value.upper()}")
    print()
    print("Component Scores in Stress:")
    print(f"  SLOOS:          {stress_scores.sloos_score:.2f}")
    print(f"  BDC:            {stress_scores.bdc_score:.2f}")
    print(f"  Leveraged Loans: {stress_scores.leveraged_loan_score:.2f}")
    print(f"  PE Firms:       {stress_scores.pe_firm_score:.2f}")
    print()
    
    print("Stress Scenario Warning Signals:")
    for warning in stress_scores.warning_signals:
        print(f"  🚨 {warning}")
    print()
    
    # Integration guidance
    print("9. MAC FRAMEWORK INTEGRATION")
    print("-" * 40)
    print("""
    Recommended integration:
    
    Option A: New 7th Pillar
    - Weight: 10-15% of total MAC
    - Best for users focused on credit risk
    
    Option B: Enhance Credit Pillar
    - Combine with existing credit spreads
    - BDC data as leading indicator sub-component
    
    Key insight: Private credit stress leads public markets by 3-6 months.
    When BDC discounts widen sharply, position defensively BEFORE
    high-yield spreads blow out.
    """)
    
    # Save results
    print("10. SAVING RESULTS")
    print("-" * 40)
    
    results = {
        "analysis_date": datetime.now().isoformat(),
        "market_context": analysis,
        "current_state": {
            "composite_score": scores.composite,
            "stress_level": scores.stress_level.value,
            "sloos_score": scores.sloos_score,
            "bdc_score": scores.bdc_score,
            "leveraged_loan_score": scores.leveraged_loan_score,
            "pe_firm_score": scores.pe_firm_score,
            "warnings": scores.warning_signals,
        },
        "stress_scenario": {
            "composite_score": stress_scores.composite,
            "stress_level": stress_scores.stress_level.value,
            "warnings": stress_scores.warning_signals,
        },
        "data_sources": {
            "fred_series": fred_series,
            "bdc_tickers": [b["ticker"] for b in get_bdc_tickers()],
            "pe_tickers": [p["ticker"] for p in get_pe_firm_tickers()],
        },
    }
    
    output_path = Path(__file__).parent / "data" / "private_credit_analysis.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"Results saved to: {output_path}")
    print()
    print("=" * 70)
    print("Analysis complete. Private credit monitoring framework established.")
    print("=" * 70)


if __name__ == "__main__":
    main()

"""
Private Credit Stress Analysis
==============================

Demonstrates how to monitor the $1.7T private credit market that operates
in opaque structures where traditional indicators miss warning signs.

This script:
1. Fetches SLOOS data from FRED (lending standards)
2. Fetches LIVE BDC/ETF/PE data from Yahoo Finance
3. Shows how stress signals propagate

Run: python analyze_private_credit.py

Requirements: pip install yfinance requests
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

# Try to import Yahoo Finance client
try:
    from grri_mac.data.yahoo_client import (
        YahooFinanceClient,
        format_bdc_report,
        calculate_weighted_bdc_discount,
    )
    YAHOO_AVAILABLE = True
except ImportError:
    YAHOO_AVAILABLE = False
    print("Note: yfinance not installed. Using sample data.")


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
    Create sample BDC data (fallback if Yahoo Finance unavailable).
    """
    return BDCData(
        arcc_discount=-3.5,
        main_discount=2.1,
        fsk_discount=-8.2,
        psec_discount=-12.5,
        gbdc_discount=-1.8,
        observation_date=datetime.now(),
    )


def create_sample_leveraged_loan_data() -> LeveragedLoanData:
    """
    Create sample leveraged loan ETF data (fallback).
    """
    return LeveragedLoanData(
        bkln_price_change_30d=-1.2,
        srln_price_change_30d=-0.8,
        clo_aaa_spread=120,
        clo_bbb_spread=450,
        observation_date=datetime.now(),
    )


def create_sample_pe_firm_data() -> PEFirmData:
    """
    Create sample PE firm stock data (fallback).
    """
    return PEFirmData(
        kkr_change_30d=-2.5,
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
    
    # Fetch LIVE market data from Yahoo Finance
    print("6b. LIVE MARKET DATA (Yahoo Finance)")
    print("-" * 40)
    
    bdc_data = None
    ll_data = None
    pe_data = None
    
    if YAHOO_AVAILABLE:
        try:
            print("Fetching BDC, ETF, and PE firm data...")
            client = YahooFinanceClient()
            
            # Get BDC data
            bdc_quotes = client.get_bdc_data()
            if bdc_quotes:
                print("\n" + format_bdc_report(bdc_quotes))
                
                # Convert to our BDCData format
                bdc_data = BDCData(
                    arcc_discount=bdc_quotes.get("ARCC", {}).discount_premium if "ARCC" in bdc_quotes else None,
                    main_discount=bdc_quotes.get("MAIN", {}).discount_premium if "MAIN" in bdc_quotes else None,
                    fsk_discount=bdc_quotes.get("FSK", {}).discount_premium if "FSK" in bdc_quotes else None,
                    psec_discount=bdc_quotes.get("PSEC", {}).discount_premium if "PSEC" in bdc_quotes else None,
                    gbdc_discount=bdc_quotes.get("GBDC", {}).discount_premium if "GBDC" in bdc_quotes else None,
                    observation_date=datetime.now(),
                )
            
            # Get ETF data
            etf_quotes = client.get_leveraged_loan_etf_data()
            if etf_quotes:
                print("\nLeveraged Loan ETFs:")
                for ticker, quote in etf_quotes.items():
                    change_str = f"{quote.change_30d_pct:+.1f}%" if quote.change_30d_pct else "N/A"
                    print(f"  {ticker}: ${quote.price:.2f} | 30d: {change_str}")
                
                ll_data = LeveragedLoanData(
                    bkln_price_change_30d=etf_quotes.get("BKLN", {}).change_30d_pct if "BKLN" in etf_quotes else None,
                    srln_price_change_30d=etf_quotes.get("SRLN", {}).change_30d_pct if "SRLN" in etf_quotes else None,
                    observation_date=datetime.now(),
                )
            
            # Get PE firm data
            pe_quotes = client.get_pe_firm_data()
            if pe_quotes:
                print("\nPE Firm Stocks:")
                for ticker, quote in pe_quotes.items():
                    change_str = f"{quote.change_30d_pct:+.1f}%" if quote.change_30d_pct else "N/A"
                    print(f"  {ticker}: ${quote.price:.2f} | 30d: {change_str}")
                
                pe_data = PEFirmData(
                    kkr_change_30d=pe_quotes.get("KKR", {}).change_30d_pct if "KKR" in pe_quotes else None,
                    bx_change_30d=pe_quotes.get("BX", {}).change_30d_pct if "BX" in pe_quotes else None,
                    apo_change_30d=pe_quotes.get("APO", {}).change_30d_pct if "APO" in pe_quotes else None,
                    cg_change_30d=pe_quotes.get("CG", {}).change_30d_pct if "CG" in pe_quotes else None,
                    observation_date=datetime.now(),
                )
                
        except Exception as e:
            print(f"  Error fetching Yahoo Finance data: {e}")
            print("  Using sample data instead.")
    else:
        print("  yfinance not installed. Run: pip install yfinance")
        print("  Using sample data instead.")
    
    # Use fallbacks if needed
    if bdc_data is None:
        bdc_data = create_sample_bdc_data()
    if ll_data is None:
        ll_data = create_sample_leveraged_loan_data()
    if pe_data is None:
        pe_data = create_sample_pe_firm_data()
    
    print()
    
    # Calculate current state score
    print("7. CURRENT STATE ANALYSIS")
    print("-" * 40)
    
    pillar = PrivateCreditPillar()
    
    # Use real SLOOS + real or sample market data
    current_indicators = PrivateCreditIndicators(
        sloos=sloos,
        bdc=bdc_data,
        leveraged_loans=ll_data,
        pe_firms=pe_data,
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

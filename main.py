#!/usr/bin/env python3
"""
GRRI-MAC Framework Main Entry Point

Usage:
    python main.py                    # Run dashboard with live data
    python main.py --backtest         # Run historical backtests
    python main.py --demo             # Run with demo data
    python main.py --db-demo          # Run demo with database storage
    python main.py --history          # Show historical data from database
    python main.py --help             # Show help
"""

import argparse
import sys
from datetime import datetime, timedelta


def run_demo():
    """Run framework with demo data."""
    from grri_mac.mac.composite import calculate_mac, get_mac_interpretation
    from grri_mac.mac.multiplier import mac_to_multiplier
    from grri_mac.china.activation import ChinaActivationScore, ChinaVectorIndicators, ActivationLevel
    from grri_mac.china.adjustment import adjust_mac_for_china
    from grri_mac.grri.modifier import calculate_grri, GRRIPillars, calculate_full_impact
    from grri_mac.dashboard.daily import DailyDashboard, DashboardReport
    from grri_mac.dashboard.alerts import AlertSystem

    print("=" * 60)
    print("GRRI-MAC FRAMEWORK DEMO")
    print("=" * 60)
    print()

    # Demo pillar scores (simulating current market conditions)
    pillar_scores = {
        "liquidity": 0.72,
        "valuation": 0.45,
        "positioning": 0.38,
        "volatility": 0.65,
        "policy": 0.55,
    }

    print("PILLAR SCORES (Demo Data)")
    print("-" * 40)
    for pillar, score in pillar_scores.items():
        status = "AMPLE" if score >= 0.8 else "THIN" if score >= 0.5 else "STRETCHED" if score >= 0.2 else "BREACH"
        print(f"  {pillar.capitalize():12} {score:.3f}  [{status}]")
    print()

    # Calculate MAC
    mac_result = calculate_mac(pillar_scores)
    print("MAC CALCULATION")
    print("-" * 40)
    print(f"  MAC Score:     {mac_result.mac_score:.3f}")
    print(f"  Interpretation: {get_mac_interpretation(mac_result.mac_score)}")
    if mac_result.breach_flags:
        print(f"  Breach Flags:  {', '.join(mac_result.breach_flags)}")
    print()

    # Calculate multiplier
    mult_result = mac_to_multiplier(mac_result.mac_score)
    print("TRANSMISSION MULTIPLIER")
    print("-" * 40)
    if mult_result.multiplier:
        print(f"  Multiplier:    {mult_result.multiplier:.2f}x")
    else:
        print("  Multiplier:    N/A (Regime Break)")
    print(f"  {mult_result.interpretation}")
    print()

    # Demo China activation
    china_indicators = ChinaVectorIndicators(
        treasury_holdings_change_billions=-30,
        rare_earth_policy=ActivationLevel.ELEVATED,
        avg_tariff_pct=18,
        taiwan_tension=ActivationLevel.LATENT,
        cips_growth_yoy_pct=35,
    )
    china_calc = ChinaActivationScore()
    china_scores = china_calc.calculate(china_indicators)

    print("CHINA LEVERAGE ACTIVATION")
    print("-" * 40)
    print(f"  Treasury:      {china_scores.treasury:.2f}")
    print(f"  Rare Earth:    {china_scores.rare_earth:.2f}")
    print(f"  Tariffs:       {china_scores.tariff:.2f}")
    print(f"  Taiwan:        {china_scores.taiwan:.2f}")
    print(f"  CIPS:          {china_scores.cips:.2f}")
    print(f"  Composite:     {china_scores.composite:.2f}")
    print()

    # Adjust MAC for China
    adjusted_mac = adjust_mac_for_china(mac_result.mac_score, china_scores.composite)
    print("CHINA-ADJUSTED MAC")
    print("-" * 40)
    print(f"  Raw MAC:       {mac_result.mac_score:.3f}")
    print(f"  Adjusted MAC:  {adjusted_mac:.3f}")
    print(f"  Reduction:     {(1 - adjusted_mac / mac_result.mac_score) * 100:.1f}%")
    print()

    # Demo GRRI calculation
    grri_pillars = GRRIPillars(
        political=0.75,
        economic=0.70,
        social=0.65,
        environmental=0.55,
    )
    grri_result = calculate_grri(grri_pillars)

    print("GRRI (Country Resilience)")
    print("-" * 40)
    print(f"  Political:     {grri_pillars.political:.2f}")
    print(f"  Economic:      {grri_pillars.economic:.2f}")
    print(f"  Social:        {grri_pillars.social:.2f}")
    print(f"  Environmental: {grri_pillars.environmental:.2f}")
    print(f"  Resilience:    {grri_result.resilience:.3f}")
    print(f"  Modifier:      {grri_result.modifier:.2f}x")
    print(f"  {grri_result.interpretation}")
    print()

    # Full impact calculation
    shock_size = 10.0  # 10% shock
    adjusted_mult = mac_to_multiplier(adjusted_mac)
    if adjusted_mult.multiplier:
        full_impact = calculate_full_impact(
            shock_size,
            adjusted_mult.multiplier,
            grri_result.modifier,
        )

        print("FULL IMPACT CALCULATION")
        print("-" * 40)
        print(f"  Shock Size:        {shock_size:.1f}%")
        print(f"  × MAC Multiplier:  {adjusted_mult.multiplier:.2f}x")
        print(f"  × GRRI Modifier:   {grri_result.modifier:.2f}x")
        print(f"  = Expected Impact: {full_impact:.1f}%")
        print()

    # Check alerts
    alert_system = AlertSystem()
    alerts = alert_system.check_all(
        mac_result,
        china_activation=china_scores.composite,
        multiplier=adjusted_mult.multiplier if adjusted_mult.multiplier else None,
    )

    if alerts:
        print("ALERTS")
        print("-" * 40)
        print(alert_system.format_alerts(alerts))
        print()

    print("=" * 60)
    print("Demo complete. For live data, configure FRED API key.")
    print("=" * 60)


def run_db_demo():
    """Run demo with database storage."""
    from grri_mac.service import MACService
    from grri_mac.china.activation import ChinaVectorIndicators, ActivationLevel
    from grri_mac.db import get_db, MACRepository

    print("=" * 60)
    print("GRRI-MAC DATABASE DEMO")
    print("=" * 60)
    print()

    # Initialize service (auto-creates database)
    service = MACService(auto_save=True)
    print(f"Database: {service.db.db_path}")
    print()

    # Demo pillar scores
    pillar_scores = {
        "liquidity": 0.72,
        "valuation": 0.45,
        "positioning": 0.38,
        "volatility": 0.65,
        "policy": 0.55,
    }

    # Demo China indicators
    china_indicators = ChinaVectorIndicators(
        treasury_holdings_change_billions=-30,
        rare_earth_policy=ActivationLevel.ELEVATED,
        avg_tariff_pct=18,
        taiwan_tension=ActivationLevel.LATENT,
        cips_growth_yoy_pct=35,
    )

    print("Calculating MAC and saving to database...")
    mac_result, china_scores, alerts = service.calculate_mac(
        pillar_scores=pillar_scores,
        china_indicators=china_indicators,
        data_source="demo",
        notes="Demo calculation",
    )

    print()
    print("MAC RESULT")
    print("-" * 40)
    print(f"  MAC Score:     {mac_result.mac_score:.3f}")
    print(f"  Adjusted:      {mac_result.adjusted_score:.3f}")
    print(f"  Multiplier:    {mac_result.multiplier:.2f}x")
    if mac_result.breach_flags:
        print(f"  Breaches:      {', '.join(mac_result.breach_flags)}")
    print()

    if alerts:
        print("ALERTS GENERATED")
        print("-" * 40)
        for alert in alerts:
            print(f"  [{alert.level.value}] {alert.message}")
        print()

    # Show database statistics
    print("DATABASE STATISTICS")
    print("-" * 40)
    stats = service.get_statistics(days=30)
    print(f"  Snapshots (30d):  {stats.get('count', 0)}")
    if stats.get('avg_score'):
        print(f"  Avg MAC Score:    {stats['avg_score']:.3f}")
        print(f"  Min MAC Score:    {stats['min_score']:.3f}")
        print(f"  Max MAC Score:    {stats['max_score']:.3f}")
    print()

    # Retrieve from database
    print("RETRIEVING FROM DATABASE")
    print("-" * 40)
    latest = service.repo.get_latest_snapshot()
    if latest:
        print(f"  Latest Snapshot ID: {latest.id}")
        print(f"  Timestamp:          {latest.timestamp}")
        print(f"  MAC Score:          {latest.mac_score:.3f}")
        print(f"  Data Source:        {latest.data_source}")
    print()

    print("=" * 60)
    print("Data saved to database. Use --history to view historical data.")
    print("=" * 60)


def run_history():
    """Show historical data from database."""
    from grri_mac.db import get_db, MACRepository

    print("=" * 60)
    print("MAC HISTORICAL DATA")
    print("=" * 60)
    print()

    repo = MACRepository()

    # Get statistics
    stats = repo.get_mac_statistics(days=30)
    print("STATISTICS (Last 30 Days)")
    print("-" * 40)
    print(f"  Total Snapshots:  {stats['count']}")
    if stats['count'] > 0:
        print(f"  Avg MAC Score:    {stats['avg_score']:.3f}")
        print(f"  Min MAC Score:    {stats['min_score']:.3f}")
        print(f"  Max MAC Score:    {stats['max_score']:.3f}")
        if stats['avg_multiplier']:
            print(f"  Avg Multiplier:   {stats['avg_multiplier']:.2f}x")
    print()

    # Get breach frequency
    breaches = repo.get_breach_frequency(days=30)
    print("BREACH FREQUENCY (Last 30 Days)")
    print("-" * 40)
    for pillar, count in breaches.items():
        print(f"  {pillar.capitalize():12} {count}")
    print()

    # Get recent snapshots
    snapshots = repo.get_snapshots(limit=10)
    if snapshots:
        print("RECENT SNAPSHOTS")
        print("-" * 40)
        print(f"  {'Timestamp':<20} {'MAC':>6} {'Adj':>6} {'Mult':>6} {'Source':<10}")
        print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*6} {'-'*10}")
        for snap in snapshots:
            ts = snap.timestamp.strftime("%Y-%m-%d %H:%M")
            adj = f"{snap.mac_adjusted:.3f}" if snap.mac_adjusted else "N/A"
            mult = f"{snap.multiplier:.2f}x" if snap.multiplier else "N/A"
            print(f"  {ts:<20} {snap.mac_score:>6.3f} {adj:>6} {mult:>6} {snap.data_source:<10}")
    else:
        print("No snapshots found. Run --db-demo to create some.")
    print()

    # Get unacknowledged alerts
    alerts = repo.get_unacknowledged_alerts()
    if alerts:
        print(f"UNACKNOWLEDGED ALERTS ({len(alerts)})")
        print("-" * 40)
        for alert in alerts[:5]:
            print(f"  [{alert.level}] {alert.message}")
        if len(alerts) > 5:
            print(f"  ... and {len(alerts) - 5} more")
    print()

    print("=" * 60)


def run_backtest():
    """Run historical backtests with calibrated engine."""
    from grri_mac.backtest.calibrated_engine import CalibratedBacktestEngine
    from grri_mac.backtest.engine import format_backtest_summary

    print("Running calibrated historical backtests...")
    print()

    engine = CalibratedBacktestEngine()
    summary = engine.run_all_scenarios()
    print(format_backtest_summary(summary))


def run_robustness():
    """Run calibration robustness analysis."""
    from grri_mac.backtest.calibration import run_robustness_analysis

    print("Running calibration robustness analysis...")
    print("(This validates the 0.78 calibration factor)")
    print()

    run_robustness_analysis()


def run_import():
    """Import data from all sources."""
    from grri_mac.data.importer import DataImporter, print_import_results

    print("=" * 60)
    print("DATA IMPORT")
    print("=" * 60)
    print()

    importer = DataImporter()

    if importer.fred is None:
        print("Warning: FRED API key not configured.")
        print("Set FRED_API_KEY in .env file for full data import.")
        print()

    results = importer.import_all(include_sec=False)  # SEC is slow
    print_import_results(results)


def run_dashboard():
    """Run live dashboard (requires API keys)."""
    print("=" * 60)
    print("GRRI-MAC LIVE DASHBOARD")
    print("=" * 60)
    print()
    print("To run the live dashboard, you need to configure:")
    print("  1. FRED API key (export FRED_API_KEY=your_key)")
    print("  2. Install dependencies: pip install -r requirements.txt")
    print()
    print("Then you can initialize the dashboard like this:")
    print()
    print("  from grri_mac.data import FREDClient, CFTCClient, ETFClient")
    print("  from grri_mac.dashboard import DailyDashboard")
    print()
    print("  fred = FREDClient(api_key='your_key')")
    print("  cftc = CFTCClient()")
    print("  etf = ETFClient()")
    print()
    print("  dashboard = DailyDashboard(fred, cftc, etf)")
    print("  report = dashboard.generate()")
    print("  print(dashboard.format_text_report(report))")
    print()
    print("For now, running demo mode instead...")
    print()
    run_demo()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="GRRI-MAC Framework - Market Absorption Capacity Analysis"
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run historical backtests against known events",
    )
    parser.add_argument(
        "--robustness",
        action="store_true",
        help="Run calibration robustness analysis (cross-validation, sensitivity)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with demo data (no database)",
    )
    parser.add_argument(
        "--db-demo",
        action="store_true",
        help="Run demo with database storage",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show historical data from database",
    )
    parser.add_argument(
        "--import-data",
        action="store_true",
        help="Import data from all sources (FRED, CFTC, ETF, Treasury)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version",
    )

    args = parser.parse_args()

    if args.version:
        from grri_mac import __version__
        print(f"GRRI-MAC Framework v{__version__}")
        return

    if args.backtest:
        run_backtest()
    elif args.robustness:
        run_robustness()
    elif args.demo:
        run_demo()
    elif args.db_demo:
        run_db_demo()
    elif args.history:
        run_history()
    elif args.import_data:
        run_import()
    else:
        run_dashboard()


if __name__ == "__main__":
    main()

"""Pull real historical data for backtest scenarios.

This module fetches actual market data from FRED, CFTC, and yfinance
to replace estimated values in the backtest scenarios.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Comprehensive FRED series mapping
FRED_SERIES = {
    # Liquidity
    "SOFR": "SOFR",                    # Secured Overnight Financing Rate (2018+)
    "IORB": "IORB",                    # Interest on Reserve Balances (Jul 2021+)
    "IOER": "IOER",                    # Interest on Excess Reserves (Oct 2008 - Jul 2021)
    "FED_FUNDS": "DFF",                # Daily Fed Funds Effective Rate
    "CP_3M_NONFINANCIAL": "DCPN3M",    # 3-Month AA Nonfinancial CP Rate
    "CP_3M_FINANCIAL": "DCPF3M",       # 3-Month AA Financial CP Rate
    "TREASURY_3M": "DTB3",             # 3-Month Treasury Bill
    "TREASURY_1M": "DTB4WK",           # 4-Week Treasury Bill
    "TED_SPREAD": "TEDRATE",           # TED Spread (LIBOR - T-Bill, 1986-2022)

    # Valuation / Credit Spreads
    "TREASURY_10Y": "DGS10",           # 10-Year Treasury Constant Maturity
    "TREASURY_2Y": "DGS2",             # 2-Year Treasury
    "TREASURY_30Y": "DGS30",           # 30-Year Treasury
    "IG_OAS": "BAMLC0A0CM",            # ICE BofA US Corp Master OAS
    "HY_OAS": "BAMLH0A0HYM2",          # ICE BofA US HY Master II OAS
    "BBB_OAS": "BAMLC0A4CBBB",         # ICE BofA BBB US Corp OAS
    "AAA_OAS": "BAMLC0A1CAAA",         # ICE BofA AAA US Corp OAS
    "BAA_YIELD": "DBAA",               # Moody's Baa Corporate Bond Yield
    "AAA_YIELD": "DAAA",               # Moody's Aaa Corporate Bond Yield

    # Volatility
    "VIX": "VIXCLS",                   # CBOE VIX (1990+)

    # Policy
    "FED_FUNDS_TARGET": "DFEDTARU",    # Fed Funds Target Rate Upper (2008+)
    "FED_BALANCE_SHEET": "WALCL",      # Fed Total Assets (Weekly)
    "GDP": "GDP",                      # Nominal GDP (Quarterly)
    "CORE_PCE": "PCEPILFE",            # Core PCE Price Index (Monthly)
    "CPI": "CPIAUCSL",                 # CPI All Urban Consumers

    # Contagion / International
    "DXY": "DTWEXBGS",                 # Trade Weighted Dollar Index Broad
    "EMBI_PROXY": "BAMLEMCBPIOAS",     # ICE BofA EM Corporate OAS (proxy for EMBI)
    "EM_HY": "BAMLEMHBHYCRPIOAS",      # ICE BofA EM HY Corporate OAS
}

# Scenario dates for data pull
SCENARIO_DATES = {
    "ltcm_crisis_1998": datetime(1998, 9, 23),
    "dotcom_peak_2000": datetime(2000, 3, 10),
    "911_attacks_2001": datetime(2001, 9, 17),
    "dotcom_bottom_2002": datetime(2002, 10, 9),
    "bear_stearns_2008": datetime(2008, 3, 16),
    "lehman_2008": datetime(2008, 9, 15),
    "flash_crash_2010": datetime(2010, 5, 6),
    "us_downgrade_2011": datetime(2011, 8, 8),
    "volmageddon_2018": datetime(2018, 2, 5),
    "repo_spike_2019": datetime(2019, 9, 17),
    "covid_crash_2020": datetime(2020, 3, 16),
    "russia_ukraine_2022": datetime(2022, 2, 24),
    "svb_crisis_2023": datetime(2023, 3, 10),
    "april_tariffs_2025": datetime(2025, 4, 2),
}


class HistoricalDataPuller:
    """Pull real historical data from FRED API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED_API_KEY required. Set environment variable or pass api_key.")

    def get_value_on_date(
        self,
        series_id: str,
        target_date: datetime,
        lookback_days: int = 7
    ) -> Optional[float]:
        """Get the value of a series on or near a specific date.

        Args:
            series_id: FRED series ID
            target_date: Target date to get value for
            lookback_days: How many days back to search if exact date unavailable

        Returns:
            Value on or closest to target date, or None if unavailable
        """
        start_date = target_date - timedelta(days=lookback_days)
        end_date = target_date + timedelta(days=1)  # Include target date

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
            "sort_order": "desc",
        }

        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            observations = data.get("observations", [])

            # Find the closest observation to target date
            for obs in observations:
                if obs.get("value") and obs["value"] != ".":
                    try:
                        return float(obs["value"])
                    except ValueError:
                        continue
            return None

        except Exception as e:
            logger.error(f"FRED API error for {series_id} on {target_date}: {e}")
            return None

    def pull_scenario_data(self, scenario_name: str) -> dict:
        """Pull all available real data for a scenario.

        Returns dict with:
            - real_values: Dict of indicator -> value (from FRED)
            - availability: Dict of indicator -> bool (whether data exists)
            - notes: List of data quality notes
        """
        if scenario_name not in SCENARIO_DATES:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        target_date = SCENARIO_DATES[scenario_name]
        results = {
            "scenario": scenario_name,
            "date": target_date.strftime("%Y-%m-%d"),
            "real_values": {},
            "availability": {},
            "notes": [],
        }

        # Pull each series
        for name, series_id in FRED_SERIES.items():
            value = self.get_value_on_date(series_id, target_date)
            results["real_values"][name] = value
            results["availability"][name] = value is not None

            if value is None:
                results["notes"].append(f"{name} ({series_id}): No data for {target_date.date()}")

        # Calculate derived indicators
        self._calculate_derived_indicators(results)

        return results

    def _calculate_derived_indicators(self, results: dict):
        """Calculate derived indicators from raw series."""
        rv = results["real_values"]

        # SOFR-IORB spread (or fallback)
        if rv.get("SOFR") and rv.get("IORB"):
            rv["sofr_iorb_spread_bps"] = (rv["SOFR"] - rv["IORB"]) * 100
        elif rv.get("SOFR") and rv.get("IOER"):
            rv["sofr_iorb_spread_bps"] = (rv["SOFR"] - rv["IOER"]) * 100
            results["notes"].append("Using IOER (pre-Jul 2021) instead of IORB")
        elif rv.get("TED_SPREAD"):
            rv["sofr_iorb_spread_bps"] = rv["TED_SPREAD"] * 100
            results["notes"].append("Using TED spread as proxy (pre-2018)")

        # CP-Treasury spread
        cp_rate = rv.get("CP_3M_NONFINANCIAL") or rv.get("CP_3M_FINANCIAL")
        tbill = rv.get("TREASURY_3M")
        if cp_rate and tbill:
            rv["cp_treasury_spread_bps"] = (cp_rate - tbill) * 100

        # Credit spreads (already in OAS form from FRED)
        if rv.get("IG_OAS"):
            rv["ig_oas_bps"] = rv["IG_OAS"] * 100  # Convert to bps
        if rv.get("HY_OAS"):
            rv["hy_oas_bps"] = rv["HY_OAS"] * 100
        if rv.get("BBB_OAS"):
            rv["bbb_oas_bps"] = rv["BBB_OAS"] * 100

        # VIX (already in correct units)
        if rv.get("VIX"):
            rv["vix_level"] = rv["VIX"]

        # DXY 3-month change would require historical lookback
        # (simplified - just note current level)
        if rv.get("DXY"):
            rv["dxy_level"] = rv["DXY"]
            results["notes"].append("DXY 3M change requires additional calculation")

        # EMBI proxy
        if rv.get("EMBI_PROXY"):
            rv["embi_spread_bps"] = rv["EMBI_PROXY"] * 100

    def pull_all_scenarios(self) -> dict:
        """Pull data for all scenarios."""
        all_results = {}
        for scenario_name in SCENARIO_DATES:
            print(f"Pulling data for {scenario_name}...")
            try:
                all_results[scenario_name] = self.pull_scenario_data(scenario_name)
            except Exception as e:
                print(f"  Error: {e}")
                all_results[scenario_name] = {"error": str(e)}
        return all_results

    def generate_availability_report(self) -> str:
        """Generate a report of data availability across all scenarios."""
        all_data = self.pull_all_scenarios()

        lines = ["# Real Data Availability Report", ""]
        lines.append("| Scenario | Date | VIX | IG OAS | HY OAS | TED/SOFR | DXY | Notes |")
        lines.append("|----------|------|-----|--------|--------|----------|-----|-------|")

        for scenario, data in all_data.items():
            if "error" in data:
                lines.append(f"| {scenario} | ERROR | - | - | - | - | - | {data['error']} |")
                continue

            rv = data["real_values"]
            date = data["date"]
            vix = "Y" if rv.get("VIX") else "N"
            ig = "Y" if rv.get("IG_OAS") else "N"
            hy = "Y" if rv.get("HY_OAS") else "N"
            sofr = "Y" if rv.get("sofr_iorb_spread_bps") or rv.get("TED_SPREAD") else "N"
            dxy = "Y" if rv.get("DXY") else "N"
            notes = len(data.get("notes", []))

            lines.append(f"| {scenario} | {date} | {vix} | {ig} | {hy} | {sofr} | {dxy} | {notes} notes |")

        return "\n".join(lines)


def load_env():
    """Load environment variables from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    """Run data pull and generate report."""
    import sys

    # Try to load from .env file
    load_env()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("ERROR: FRED_API_KEY environment variable not set")
        print("Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        sys.exit(1)

    puller = HistoricalDataPuller(api_key)

    print("=" * 60)
    print("PULLING REAL HISTORICAL DATA FOR BACKTEST SCENARIOS")
    print("=" * 60)
    print()

    # Pull data for each scenario
    for scenario_name, target_date in SCENARIO_DATES.items():
        print(f"\n{scenario_name} ({target_date.date()})")
        print("-" * 40)

        try:
            data = puller.pull_scenario_data(scenario_name)
            rv = data["real_values"]

            # Print key indicators
            print(f"  VIX:              {rv.get('VIX', 'N/A')}")
            print(f"  IG OAS (bps):     {rv.get('ig_oas_bps', 'N/A')}")
            print(f"  HY OAS (bps):     {rv.get('hy_oas_bps', 'N/A')}")
            print(f"  SOFR spread:      {rv.get('sofr_iorb_spread_bps', 'N/A')}")
            print(f"  TED Spread:       {rv.get('TED_SPREAD', 'N/A')}")
            print(f"  DXY:              {rv.get('DXY', 'N/A')}")
            print(f"  Fed Funds:        {rv.get('FED_FUNDS', 'N/A')}")

            if data["notes"]:
                print(f"  Notes: {len(data['notes'])} data quality issues")

        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(puller.generate_availability_report())


if __name__ == "__main__":
    main()

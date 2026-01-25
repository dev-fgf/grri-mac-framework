"""FRED API client for fetching market data."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Key FRED series for MAC indicators
FRED_SERIES = {
    # Liquidity indicators
    "SOFR": "SOFR",  # Secured Overnight Financing Rate (started 2018)
    "IORB": "IORB",  # Interest on Reserve Balances (started July 2021)
    "IOER": "IOER",  # Interest on Excess Reserves (Oct 2008 - July 2021, predecessor to IORB)
    "CP_3M": "DCPN3M",  # 3-Month AA Nonfinancial Commercial Paper Rate
    "TREASURY_3M": "DTB3",  # 3-Month Treasury Bill

    # Valuation indicators
    "TREASURY_10Y": "DGS10",  # 10-Year Treasury
    "TREASURY_2Y": "DGS2",  # 2-Year Treasury
    "BAA_SPREAD": "BAA10Y",  # Moody's Baa Corporate Bond Spread
    "AAA_SPREAD": "AAA10Y",  # Moody's Aaa Corporate Bond Spread

    # Policy indicators
    "FED_FUNDS": "FEDFUNDS",  # Effective Federal Funds Rate
    "FED_BALANCE_SHEET": "WALCL",  # Fed Total Assets
    "GDP": "GDP",  # Gross Domestic Product
    "CORE_PCE": "PCEPILFE",  # Core PCE Price Index

    # Volatility proxy
    "VIX": "VIXCLS",  # CBOE Volatility Index
}


class FREDClient:
    """Client for FRED API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            logger.warning("FRED_API_KEY not set - using demo data")

    def get_series(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Fetch time series data from FRED."""
        if not self.api_key:
            return []

        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
            "sort_order": "desc",
            "limit": limit,
        }

        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("observations", [])
        except Exception as e:
            logger.error(f"FRED API error for {series_id}: {e}")
            return []

    def get_latest_value(self, series_id: str) -> Optional[float]:
        """Get the most recent value for a series."""
        observations = self.get_series(series_id, limit=5)
        for obs in observations:
            if obs.get("value") and obs["value"] != ".":
                try:
                    return float(obs["value"])
                except ValueError:
                    continue
        return None

    def get_liquidity_indicators(self) -> dict:
        """Fetch liquidity-related indicators."""
        sofr = self.get_latest_value(FRED_SERIES["SOFR"])
        iorb = self.get_latest_value(FRED_SERIES["IORB"])
        cp_rate = self.get_latest_value(FRED_SERIES["CP_3M"])
        treasury_3m = self.get_latest_value(FRED_SERIES["TREASURY_3M"])

        indicators = {}

        # SOFR-IORB spread (in bps)
        if sofr is not None and iorb is not None:
            indicators["sofr_iorb_spread_bps"] = (sofr - iorb) * 100

        # CP-Treasury spread (in bps)
        if cp_rate is not None and treasury_3m is not None:
            indicators["cp_treasury_spread_bps"] = (cp_rate - treasury_3m) * 100

        return indicators

    def get_valuation_indicators(self) -> dict:
        """Fetch valuation-related indicators."""
        treasury_10y = self.get_latest_value(FRED_SERIES["TREASURY_10Y"])
        treasury_2y = self.get_latest_value(FRED_SERIES["TREASURY_2Y"])
        baa_spread = self.get_latest_value(FRED_SERIES["BAA_SPREAD"])
        aaa_spread = self.get_latest_value(FRED_SERIES["AAA_SPREAD"])

        indicators = {}

        # Term premium proxy (10Y - 2Y spread in bps)
        if treasury_10y is not None and treasury_2y is not None:
            indicators["term_premium_10y_bps"] = (treasury_10y - treasury_2y) * 100

        # IG OAS proxy (Aaa spread in bps)
        if aaa_spread is not None:
            indicators["ig_oas_bps"] = aaa_spread * 100

        # HY OAS proxy (Baa spread in bps)
        if baa_spread is not None:
            indicators["hy_oas_bps"] = baa_spread * 100

        return indicators

    def get_policy_indicators(self) -> dict:
        """Fetch policy-related indicators."""
        fed_funds = self.get_latest_value(FRED_SERIES["FED_FUNDS"])
        fed_assets = self.get_latest_value(FRED_SERIES["FED_BALANCE_SHEET"])
        gdp = self.get_latest_value(FRED_SERIES["GDP"])
        core_pce = self.get_latest_value(FRED_SERIES["CORE_PCE"])

        indicators = {}

        # Fed funds vs neutral (assuming 2.5% neutral)
        if fed_funds is not None:
            neutral_rate = 2.5
            indicators["fed_funds_vs_neutral_bps"] = (fed_funds - neutral_rate) * 100

        # Fed balance sheet as % of GDP
        if fed_assets is not None and gdp is not None:
            # Fed assets in millions, GDP in billions
            indicators["fed_balance_sheet_gdp_pct"] = (fed_assets / 1000) / gdp * 100

        # Core PCE vs 2% target
        if core_pce is not None:
            # PCE is YoY % change, target is 2%
            indicators["core_pce_vs_target_bps"] = (core_pce - 2.0) * 100

        return indicators

    def get_volatility_indicators(self) -> dict:
        """Fetch volatility-related indicators."""
        vix = self.get_latest_value(FRED_SERIES["VIX"])

        indicators = {}

        if vix is not None:
            indicators["vix_level"] = vix

        return indicators

    def get_all_indicators(self) -> dict:
        """Fetch all available indicators."""
        indicators = {}
        indicators.update(self.get_liquidity_indicators())
        indicators.update(self.get_valuation_indicators())
        indicators.update(self.get_policy_indicators())
        indicators.update(self.get_volatility_indicators())
        return indicators

    def get_value_at_date(self, series_id: str, target_date: datetime) -> Optional[float]:
        """Get the value for a series at or near a specific date."""
        # Fetch a window around the target date (some series update weekly/monthly)
        start = target_date - timedelta(days=14)
        end = target_date + timedelta(days=7)

        observations = self.get_series(series_id, start_date=start, end_date=end, limit=30)

        # Find closest observation on or before target date
        best_obs = None
        best_date = None

        for obs in observations:
            if obs.get("value") and obs["value"] != ".":
                try:
                    obs_date = datetime.strptime(obs["date"], "%Y-%m-%d")
                    if obs_date <= target_date:
                        if best_date is None or obs_date > best_date:
                            best_obs = float(obs["value"])
                            best_date = obs_date
                except (ValueError, KeyError):
                    continue

        return best_obs

    def get_indicators_at_date(self, target_date: datetime) -> dict:
        """Fetch all indicators for a specific historical date."""
        if not self.api_key:
            return {}

        indicators = {}

        # Liquidity
        sofr = self.get_value_at_date(FRED_SERIES["SOFR"], target_date)
        iorb = self.get_value_at_date(FRED_SERIES["IORB"], target_date)
        cp_rate = self.get_value_at_date(FRED_SERIES["CP_3M"], target_date)
        treasury_3m = self.get_value_at_date(FRED_SERIES["TREASURY_3M"], target_date)

        if sofr is not None and iorb is not None:
            indicators["sofr_iorb_spread_bps"] = (sofr - iorb) * 100
        if cp_rate is not None and treasury_3m is not None:
            indicators["cp_treasury_spread_bps"] = (cp_rate - treasury_3m) * 100

        # Valuation
        treasury_10y = self.get_value_at_date(FRED_SERIES["TREASURY_10Y"], target_date)
        treasury_2y = self.get_value_at_date(FRED_SERIES["TREASURY_2Y"], target_date)
        baa_spread = self.get_value_at_date(FRED_SERIES["BAA_SPREAD"], target_date)
        aaa_spread = self.get_value_at_date(FRED_SERIES["AAA_SPREAD"], target_date)

        if treasury_10y is not None and treasury_2y is not None:
            indicators["term_premium_10y_bps"] = (treasury_10y - treasury_2y) * 100
        if aaa_spread is not None:
            indicators["ig_oas_bps"] = aaa_spread * 100
        if baa_spread is not None:
            indicators["hy_oas_bps"] = baa_spread * 100

        # Policy
        fed_funds = self.get_value_at_date(FRED_SERIES["FED_FUNDS"], target_date)
        if fed_funds is not None:
            indicators["fed_funds_vs_neutral_bps"] = (fed_funds - 2.5) * 100

        # Volatility
        vix = self.get_value_at_date(FRED_SERIES["VIX"], target_date)
        if vix is not None:
            indicators["vix_level"] = vix

        return indicators

    def get_bulk_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Fetch entire time series and return as date->value dict."""
        if not self.api_key:
            return {}

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
            "sort_order": "asc",
            "limit": 10000,  # Get all observations
        }

        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = {}
            for obs in data.get("observations", []):
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result[obs["date"]] = float(obs["value"])
                    except ValueError:
                        continue
            return result
        except Exception as e:
            logger.error(f"FRED bulk API error for {series_id}: {e}")
            return {}

    def get_all_bulk_series(self, start_date: datetime, end_date: datetime) -> dict:
        """Fetch all indicator series in bulk (one API call per series)."""
        if not self.api_key:
            return {}

        series_to_fetch = [
            "SOFR", "IORB", "IOER", "CP_3M", "TREASURY_3M",
            "TREASURY_10Y", "TREASURY_2Y", "BAA_SPREAD", "AAA_SPREAD",
            "FED_FUNDS", "VIX"
        ]

        bulk_data = {}
        for series_name in series_to_fetch:
            series_id = FRED_SERIES.get(series_name)
            if series_id:
                logger.info(f"Fetching bulk data for {series_name} ({series_id})")
                bulk_data[series_name] = self.get_bulk_series(series_id, start_date, end_date)

        return bulk_data

    def interpolate_value(self, series_data: dict, target_date: str) -> Optional[float]:
        """Get value for target date, using most recent available if exact date missing."""
        if target_date in series_data:
            return series_data[target_date]

        # Find most recent date before target
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        best_value = None
        best_date = None

        for date_str, value in series_data.items():
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt <= target_dt:
                    if best_date is None or dt > best_date:
                        best_date = dt
                        best_value = value
            except ValueError:
                continue

        return best_value

    def calculate_indicators_from_bulk(self, bulk_data: dict, target_date: str) -> dict:
        """Calculate MAC indicators for a specific date using bulk-fetched data."""
        indicators = {}

        # Get values using interpolation
        sofr = self.interpolate_value(bulk_data.get("SOFR", {}), target_date)
        iorb = self.interpolate_value(bulk_data.get("IORB", {}), target_date)
        ioer = self.interpolate_value(bulk_data.get("IOER", {}), target_date)
        cp_rate = self.interpolate_value(bulk_data.get("CP_3M", {}), target_date)
        treasury_3m = self.interpolate_value(bulk_data.get("TREASURY_3M", {}), target_date)
        treasury_10y = self.interpolate_value(bulk_data.get("TREASURY_10Y", {}), target_date)
        treasury_2y = self.interpolate_value(bulk_data.get("TREASURY_2Y", {}), target_date)
        baa_spread = self.interpolate_value(bulk_data.get("BAA_SPREAD", {}), target_date)
        aaa_spread = self.interpolate_value(bulk_data.get("AAA_SPREAD", {}), target_date)
        fed_funds = self.interpolate_value(bulk_data.get("FED_FUNDS", {}), target_date)
        vix = self.interpolate_value(bulk_data.get("VIX", {}), target_date)

        # Use IORB if available, otherwise fall back to IOER (pre-July 2021)
        reserve_rate = iorb if iorb is not None else ioer

        # Liquidity - use SOFR spread if available, otherwise Fed Funds spread (pre-2018)
        if sofr is not None and reserve_rate is not None:
            # Post-2018: SOFR - IORB/IOER spread
            indicators["sofr_iorb_spread_bps"] = (sofr - reserve_rate) * 100
        elif fed_funds is not None and treasury_3m is not None:
            # Pre-2018 fallback: Fed Funds - T-Bill spread (classic funding stress indicator)
            indicators["sofr_iorb_spread_bps"] = (fed_funds - treasury_3m) * 100
        if cp_rate is not None and treasury_3m is not None:
            indicators["cp_treasury_spread_bps"] = (cp_rate - treasury_3m) * 100

        # Valuation
        if treasury_10y is not None and treasury_2y is not None:
            indicators["term_premium_10y_bps"] = (treasury_10y - treasury_2y) * 100
        if aaa_spread is not None:
            indicators["ig_oas_bps"] = aaa_spread * 100
        if baa_spread is not None:
            indicators["hy_oas_bps"] = baa_spread * 100

        # Policy
        if fed_funds is not None:
            indicators["fed_funds_vs_neutral_bps"] = (fed_funds - 2.5) * 100

        # Volatility
        if vix is not None:
            indicators["vix_level"] = vix

        return indicators

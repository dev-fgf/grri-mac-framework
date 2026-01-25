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
    "SOFR": "SOFR",  # Secured Overnight Financing Rate
    "IORB": "IORB",  # Interest on Reserve Balances
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

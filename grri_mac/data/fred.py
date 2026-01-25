"""FRED API wrapper for fetching financial data."""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

try:
    from fredapi import Fred
except ImportError:
    Fred = None


class FREDClient:
    """Client for fetching data from FRED (Federal Reserve Economic Data)."""

    # Key FRED series IDs used in MAC framework
    SERIES = {
        # Funding rates
        "SOFR": "SOFR",
        "IORB": "IORB",
        "EFFR": "EFFR",
        # Treasury yields
        "DGS1MO": "DGS1MO",
        "DGS3MO": "DGS3MO",
        "DGS6MO": "DGS6MO",
        "DGS1": "DGS1",
        "DGS2": "DGS2",
        "DGS5": "DGS5",
        "DGS10": "DGS10",
        "DGS30": "DGS30",
        # Commercial paper
        "DCPF3M": "DCPF3M",  # 3-month AA financial CP rate
        # Credit spreads
        "IG_OAS": "BAMLC0A0CM",  # ICE BofA US Corp Index OAS
        "HY_OAS": "BAMLH0A0HYM2",  # ICE BofA US HY Index OAS
        # Volatility
        "VIX": "VIXCLS",
        # Term premium
        "TERM_PREMIUM_10Y": "THREEFYTP10",  # ACM 10-year term premium
        # Macro
        "GDP": "GDP",
        "CORE_PCE": "PCEPILFE",  # Core PCE price index
        "FED_BALANCE_SHEET": "WALCL",  # Fed total assets
        "FED_FUNDS_TARGET": "DFEDTARU",  # Fed funds target upper
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FRED client.

        Args:
            api_key: FRED API key. If not provided, will look for FRED_API_KEY env var.
        """
        if Fred is None:
            raise ImportError("fredapi package not installed. Run: pip install fredapi")

        self.fred = Fred(api_key=api_key) if api_key else Fred()
        self._cache: dict[str, pd.Series] = {}

    def get_series(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_cache: bool = True,
    ) -> pd.Series:
        """
        Fetch a data series from FRED.

        Args:
            series_id: FRED series ID or alias from SERIES dict
            start_date: Start date for data
            end_date: End date for data
            use_cache: Whether to use cached data

        Returns:
            pandas Series with the data
        """
        # Resolve alias to actual series ID
        actual_id = self.SERIES.get(series_id, series_id)

        cache_key = f"{actual_id}_{start_date}_{end_date}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        data = self.fred.get_series(
            actual_id,
            observation_start=start_date,
            observation_end=end_date,
        )

        if use_cache:
            self._cache[cache_key] = data

        return data

    def get_latest(self, series_id: str) -> tuple[datetime, float]:
        """
        Get the latest value for a series.

        Args:
            series_id: FRED series ID or alias

        Returns:
            Tuple of (date, value)
        """
        data = self.get_series(series_id)
        data = data.dropna()
        if data.empty:
            raise ValueError(f"No data available for {series_id}")
        return data.index[-1], data.iloc[-1]

    def get_sofr_iorb_spread(self) -> float:
        """Get current SOFR-IORB spread in basis points."""
        _, sofr = self.get_latest("SOFR")
        _, iorb = self.get_latest("IORB")
        return (sofr - iorb) * 100  # Convert to bps

    def get_cp_treasury_spread(self) -> float:
        """Get current CP-Treasury spread in basis points."""
        _, cp = self.get_latest("DCPF3M")
        _, treasury = self.get_latest("DGS3MO")
        return (cp - treasury) * 100  # Convert to bps

    def get_term_premium_10y(self) -> float:
        """Get 10-year term premium in basis points."""
        _, tp = self.get_latest("TERM_PREMIUM_10Y")
        return tp * 100  # Convert to bps

    def get_ig_oas(self) -> float:
        """Get Investment Grade OAS in basis points."""
        _, oas = self.get_latest("IG_OAS")
        return oas * 100  # Already in bps from FRED

    def get_hy_oas(self) -> float:
        """Get High Yield OAS in basis points."""
        _, oas = self.get_latest("HY_OAS")
        return oas * 100  # Already in bps from FRED

    def get_vix(self) -> float:
        """Get current VIX level."""
        _, vix = self.get_latest("VIX")
        return vix

    def get_fed_funds_vs_neutral(self, neutral_rate: float = 2.5) -> float:
        """Get Fed funds rate deviation from neutral in basis points."""
        _, ff = self.get_latest("FED_FUNDS_TARGET")
        return (ff - neutral_rate) * 100

    def get_fed_balance_sheet_to_gdp(self) -> float:
        """Get Fed balance sheet as percentage of GDP."""
        _, bs = self.get_latest("FED_BALANCE_SHEET")
        _, gdp = self.get_latest("GDP")
        # WALCL is in millions, GDP is in billions
        return (bs / 1000) / gdp * 100

    def get_core_pce_vs_target(self, target: float = 2.0) -> float:
        """Get Core PCE deviation from target in basis points."""
        _, pce = self.get_latest("CORE_PCE")
        # PCEPILFE is an index, need YoY change
        data = self.get_series("CORE_PCE")
        if len(data) < 13:
            raise ValueError("Insufficient data for YoY calculation")
        yoy = (data.iloc[-1] / data.iloc[-13] - 1) * 100
        return abs(yoy - target) * 100

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()

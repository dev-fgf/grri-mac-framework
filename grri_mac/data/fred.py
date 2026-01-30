"""FRED API wrapper for fetching financial data."""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import time

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
        "IOER": "IOER",  # Pre-July 2021 version of IORB
        "EFFR": "EFFR",
        "DFF": "DFF",  # Daily federal funds rate
        # Historical LIBOR (discontinued 2023)
        "USD3MTD156N": "USD3MTD156N",  # 3-month USD LIBOR
        "USDONTD156N": "USDONTD156N",  # Overnight USD LIBOR
        # Treasury yields
        "DGS1MO": "DGS1MO",
        "DGS3MO": "DGS3MO",
        "DGS6MO": "DGS6MO",
        "DGS1": "DGS1",
        "DGS2": "DGS2",
        "DGS5": "DGS5",
        "DGS10": "DGS10",
        "DGS30": "DGS30",
        "DTB3": "DTB3",  # 3-month Treasury bill
        # Commercial paper
        "DCPF3M": "DCPF3M",  # 3-month AA financial CP rate
        "DCPN3M": "DCPN3M",  # 3-month AA nonfinancial CP rate
        # Credit spreads
        "IG_OAS": "BAMLC0A0CM",  # ICE BofA US Corp Index OAS
        "HY_OAS": "BAMLH0A0HYM2",  # ICE BofA US HY Index OAS
        "AAA10Y": "AAA10Y",  # Moody's Aaa corporate spread
        "BAA10Y": "BAA10Y",  # Moody's Baa corporate spread
        # Volatility
        "VIX": "VIXCLS",
        # Term premium
        "TERM_PREMIUM_10Y": "THREEFYTP10",  # ACM 10-year term premium
        # Macro
        "GDP": "GDP",
        "CORE_PCE": "PCEPILFE",  # Core PCE price index
        "FED_BALANCE_SHEET": "WALCL",  # Fed total assets
        "FED_FUNDS_TARGET": "DFEDTARU",  # Fed funds target upper
        "FED_FUNDS_RATE": "FEDFUNDS",  # Effective federal funds rate (monthly average)
    }

    # Historical cutoff dates for indicator transitions
    SOFR_START_DATE = datetime(2018, 4, 3)  # SOFR launch date
    IORB_START_DATE = datetime(2021, 7, 29)  # IORB replaced IOER
    LIBOR_END_DATE = datetime(2023, 6, 30)  # LIBOR discontinued

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
        self._last_request_time = 0.0
        self._min_request_interval = 0.5  # 0.5 seconds = 120 requests/minute

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

        # Rate limiting: ensure minimum time between requests
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)

        data = self.fred.get_series(
            actual_id,
            observation_start=start_date,
            observation_end=end_date,
        )

        self._last_request_time = time.time()

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

    def get_value_for_date(
        self,
        series_id: str,
        date: datetime,
        lookback_days: int = 5
    ) -> Optional[float]:
        """
        Get value for a specific date with forward-fill for weekends/holidays.

        Args:
            series_id: FRED series ID or alias
            date: Target date
            lookback_days: Maximum days to look back for data (default 5 for weekends)

        Returns:
            Value for date, or most recent value within lookback window, or None
        """
        start = date - timedelta(days=lookback_days)
        data = self.get_series(series_id, start, date)
        data = data.dropna()

        if data.empty:
            return None

        # Find closest date <= target date
        valid_dates = data.index[data.index <= date]
        if len(valid_dates) == 0:
            return None

        return data.loc[valid_dates[-1]]

    def get_sofr_iorb_spread(self, date: Optional[datetime] = None) -> float:
        """Get SOFR-IORB spread in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        if date >= self.IORB_START_DATE:
            # Use SOFR-IORB (July 2021+)
            sofr_data = self.get_series("SOFR", date, date)
            iorb_data = self.get_series("IORB", date, date)
        elif date >= self.SOFR_START_DATE:
            # Use SOFR-IOER (April 2018 - July 2021)
            sofr_data = self.get_series("SOFR", date, date)
            iorb_data = self.get_series("IOER", date, date)
        else:
            # Pre-SOFR: use LIBOR-OIS spread instead
            return self.get_libor_ois_spread(date)

        if sofr_data.empty or iorb_data.empty:
            raise ValueError(f"No data available for date {date}")

        return (sofr_data.iloc[-1] - iorb_data.iloc[-1]) * 100  # Convert to bps

    def get_libor_ois_spread(self, date: Optional[datetime] = None) -> float:
        """
        Get LIBOR-OIS spread in basis points (historical alternative to SOFR-IORB).

        Uses 3-month USD LIBOR minus Effective Federal Funds Rate as OIS proxy.
        This is the canonical measure of bank funding stress during the GFC period.
        """
        if date is None:
            date = datetime.now()

        # Get 3-month LIBOR with lookback for weekends/holidays
        start_date = date - timedelta(days=10)
        libor_data = self.get_series("USD3MTD156N", start_date, date)
        libor_data = libor_data.dropna()

        # Get EFFR as OIS proxy (DFF as fallback for older dates)
        try:
            effr_data = self.get_series("EFFR", start_date, date)
            effr_data = effr_data.dropna()
            if effr_data.empty:
                raise ValueError("EFFR empty")
        except:
            # EFFR not available, use DFF (daily federal funds)
            effr_data = self.get_series("DFF", start_date, date)
            effr_data = effr_data.dropna()

        if libor_data.empty or effr_data.empty:
            raise ValueError(f"No LIBOR-OIS data for date {date}")

        # Get most recent values <= target date
        libor_dates = libor_data.index[libor_data.index <= date]
        effr_dates = effr_data.index[effr_data.index <= date]

        if len(libor_dates) == 0 or len(effr_dates) == 0:
            raise ValueError(f"No LIBOR-OIS data for date {date}")

        libor_value = libor_data.loc[libor_dates[-1]]
        effr_value = effr_data.loc[effr_dates[-1]]

        return (libor_value - effr_value) * 100  # Convert to bps

    def get_liquidity_spread(self, date: Optional[datetime] = None) -> float:
        """
        Get appropriate liquidity spread for any date (date-aware).

        Returns SOFR-IORB for dates >= April 2018, LIBOR-OIS for earlier dates.
        This enables backtesting from 2004-2024 with appropriate historical indicators.
        """
        if date is None:
            date = datetime.now()

        if date >= self.SOFR_START_DATE:
            return self.get_sofr_iorb_spread(date)
        else:
            return self.get_libor_ois_spread(date)

    def get_cp_treasury_spread(self, date: Optional[datetime] = None) -> float:
        """Get CP-Treasury spread in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        # Use lookback for weekend/holiday handling
        cp_value = self.get_value_for_date("DCPN3M", date, lookback_days=10)
        treasury_value = self.get_value_for_date("DTB3", date, lookback_days=10)

        if cp_value is None or treasury_value is None:
            raise ValueError(f"No CP-Treasury data available for date {date}")

        return (cp_value - treasury_value) * 100  # Convert to bps

    def get_term_premium_10y(self, date: Optional[datetime] = None) -> float:
        """Get 10-year term premium in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        value = self.get_value_for_date("TERM_PREMIUM_10Y", date, lookback_days=10)

        if value is None:
            raise ValueError(f"No term premium data available for date {date}")

        return value * 100  # Convert to bps

    def get_ig_oas(self, date: Optional[datetime] = None) -> float:
        """Get Investment Grade OAS in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        value = self.get_value_for_date("IG_OAS", date, lookback_days=10)

        if value is None:
            raise ValueError(f"No IG OAS data available for date {date}")

        return value  # Already in bps from FRED

    def get_hy_oas(self, date: Optional[datetime] = None) -> float:
        """Get High Yield OAS in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        value = self.get_value_for_date("HY_OAS", date, lookback_days=10)

        if value is None:
            raise ValueError(f"No HY OAS data available for date {date}")

        return value  # Already in bps from FRED

    def get_vix(self, date: Optional[datetime] = None) -> float:
        """Get VIX level for a specific date."""
        if date is None:
            date = datetime.now()

        value = self.get_value_for_date("VIX", date, lookback_days=10)

        if value is None:
            raise ValueError(f"No VIX data available for date {date}")

        return value

    def get_fed_funds(self, date: Optional[datetime] = None) -> Optional[float]:
        """Get Fed funds rate for a specific date."""
        if date is None:
            date = datetime.now()

        # Try target rate first (available 2008+)
        value = self.get_value_for_date("FED_FUNDS_TARGET", date, lookback_days=10)
        if value is not None:
            return value

        # Fallback to effective rate
        value = self.get_value_for_date("FEDFUNDS", date, lookback_days=10)
        return value

    def get_policy_room(self, date: Optional[datetime] = None) -> Optional[float]:
        """Get policy room (distance from ELB) in basis points.

        Policy room = fed_funds * 100 (distance from 0%).
        This measures the Fed's operational capacity to cut rates.
        """
        fed_funds = self.get_fed_funds(date)
        if fed_funds is None:
            return None
        return fed_funds * 100

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

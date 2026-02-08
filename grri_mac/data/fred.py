"""FRED API wrapper for fetching financial data."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd
import pickle
import time

try:
    from fredapi import Fred
except ImportError:
    Fred = None

# Default cache file location
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "fred_cache"
CACHE_FILE = CACHE_DIR / "fred_series_cache.pkl"


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
        "TEDRATE": "TEDRATE",  # TED spread (1986-2022) - 3M LIBOR - 3M TBill
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
        "TB3MS": "TB3MS",  # 3-month T-Bill secondary market (monthly, from 1934)
        # Commercial paper
        "DCPF3M": "DCPF3M",  # 3-month AA financial CP rate
        "DCPN3M": "DCPN3M",  # 3-month AA nonfinancial CP rate
        # Credit spreads - Modern (ICE BofA, from 1996)
        "IG_OAS": "BAMLC0A0CM",  # ICE BofA US Corp Index OAS
        "HY_OAS": "BAMLH0A0HYM2",  # ICE BofA US HY Index OAS
        # Credit spreads - Historical (Moody's, from 1919)
        "AAA": "AAA",  # Moody's Aaa corporate yield (1919+)
        "BAA": "BAA",  # Moody's Baa corporate yield (1919+)
        "AAA10Y": "AAA10Y",  # Moody's Aaa corporate spread vs 10Y
        "BAA10Y": "BAA10Y",  # Moody's Baa corporate spread vs 10Y
        # Volatility
        "VIX": "VIXCLS",  # VIX (1990+)
        "VXOCLS": "VXOCLS",  # VXO / Old VIX (1986-2021) - historical proxy
        # Equity indices for realized volatility (pre-1986)
        "NASDAQCOM": "NASDAQCOM",  # NASDAQ Composite (1971+)
        "SP500_OECD": "SPASTT01USM661N",  # S&P 500 total return (OECD, 1957+, monthly)
        # Term premium
        "TERM_PREMIUM_10Y": "THREEFYTP10",  # ACM 10-year term premium
        # Macro
        "GDP": "GDP",
        "CORE_PCE": "PCEPILFE",  # Core PCE price index
        "FED_BALANCE_SHEET": "WALCL",  # Fed total assets
        "BOGMBASE": "BOGMBASE",  # Monetary Base (1959+) - for pre-2002 Fed balance sheet
        "M2SL": "M2SL",  # M2 Money Supply (1959+)
        "FED_FUNDS_TARGET": "DFEDTARU",  # Fed funds target upper
        "FED_FUNDS_RATE": "FEDFUNDS",  # Effective federal funds rate (monthly average)
        # Extended historical series for 1907+ backtest
        "INTDSRUSM193N": "INTDSRUSM193N",  # Fed Discount Rate (1913+, monthly)
        "IRLTLT01USM156N": "IRLTLT01USM156N",  # Long-Term Govt Bond Yield (1920+)
        "GDPA": "GDPA",  # Nominal GDP Annual (1929+)
    }

    # Historical cutoff dates for indicator transitions
    SOFR_START_DATE = datetime(2018, 4, 3)  # SOFR launch date
    IORB_START_DATE = datetime(2021, 7, 29)  # IORB replaced IOER
    LIBOR_END_DATE = datetime(2023, 6, 30)  # LIBOR discontinued

    # Extended historical boundaries for 1907+ backtest
    MOODYS_START = datetime(1919, 1, 1)       # Moody's Aaa/Baa yields
    DISCOUNT_RATE_START = datetime(1948, 1, 1) # Fed discount rate (FRED starts 1948)
    NBER_DATA_START = datetime(1907, 1, 1)     # NBER Macrohistory coverage
    TB3MS_START = datetime(1934, 1, 1)         # 3-month T-Bill monthly

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
        self._bulk_cache: dict[str, pd.Series] = {}  # For prefetched full series
        self._last_request_time = 0.0
        self._min_request_interval = 0.5  # 0.5 seconds = 120 requests/minute
        self._backtest_mode = False  # When True, only use cached data (no API calls)

        # Lazy-loaded historical data provider for pre-1954 data
        self._historical_provider = None
        
        # Load persisted cache from disk
        self._load_cache_from_disk()

    def set_backtest_mode(self, enabled: bool = True) -> None:
        """
        Enable or disable backtest mode.
        
        In backtest mode, the client only uses cached data and returns None
        for missing series instead of making API calls. This prevents rate
        limiting during long historical backtests.
        """
        self._backtest_mode = enabled

    def _load_cache_from_disk(self) -> None:
        """Load cached series from disk if available."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "rb") as f:
                    saved_cache = pickle.load(f)
                    # Validate cache structure
                    if isinstance(saved_cache, dict):
                        valid_count = 0
                        for key, value in saved_cache.items():
                            if isinstance(value, pd.Series) and len(value) > 0:
                                valid_count += 1
                        self._bulk_cache = saved_cache
                        print(f"Loaded {valid_count} cached series from disk")
                    else:
                        print("Warning: Invalid cache format, starting fresh")
                        self._bulk_cache = {}
            except Exception as e:
                print(f"Warning: Could not load cache from disk: {e}")
                self._bulk_cache = {}

    def _save_cache_to_disk(self) -> None:
        """Persist cached series to disk."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(self._bulk_cache, f)
            print(f"Saved {len(self._bulk_cache)} series to disk cache")
        except Exception as e:
            print(f"Warning: Could not save cache to disk: {e}")

    def _merge_series(self, existing: pd.Series, new_data: pd.Series) -> pd.Series:
        """
        Merge new data into existing series, extending date range.
        
        IMPORTANT: For overlapping dates, we keep the EXISTING (cached) value
        to maintain data consistency. FRED data is immutable for historical dates,
        so cached values should always match new fetches for the same dates.
        """
        if existing is None or len(existing) == 0:
            return new_data
        if new_data is None or len(new_data) == 0:
            return existing
        
        # Combine and remove duplicates, keeping FIRST value (existing/cached)
        # This ensures we don't accidentally overwrite good data
        combined = pd.concat([existing, new_data])
        combined = combined[~combined.index.duplicated(keep='first')]
        combined = combined.sort_index()
        return combined

    def prefetch_series(
        self,
        series_ids: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """
        Pre-fetch multiple series for a date range into bulk cache.
        Merges with existing cached data to extend date coverage.
        
        Args:
            series_ids: List of FRED series IDs or aliases
            start_date: Start date for data
            end_date: End date for data
        """
        # Normalize dates to remove time component for comparison
        start_date_norm = datetime(start_date.year, start_date.month, start_date.day)
        end_date_norm = datetime(end_date.year, end_date.month, end_date.day)
        
        # Check which series need fetching or extending
        # Use dict to avoid duplicates: actual_id -> (fetch_start, fetch_end)
        series_to_fetch = {}
        already_cached = 0
        
        for series_id in series_ids:
            actual_id = self.SERIES.get(series_id, series_id)
            
            if actual_id in series_to_fetch:
                # Already queued for fetch
                continue
                
            if actual_id not in self._bulk_cache:
                # Not cached at all
                series_to_fetch[actual_id] = (start_date, end_date)
            else:
                # Check if we need to extend the date range
                cached = self._bulk_cache[actual_id]
                if len(cached) > 0:
                    # Normalize cached dates for comparison
                    cached_start = cached.index.min()
                    cached_end = cached.index.max()
                    cached_start_norm = datetime(cached_start.year, cached_start.month, cached_start.day)
                    cached_end_norm = datetime(cached_end.year, cached_end.month, cached_end.day)
                    
                    # Only fetch if cache doesn't cover the requested range
                    needs_earlier = start_date_norm < cached_start_norm
                    needs_later = end_date_norm > cached_end_norm
                    
                    if needs_earlier or needs_later:
                        # Fetch full range to fill gaps
                        series_to_fetch[actual_id] = (start_date, end_date)
                    else:
                        already_cached += 1
                else:
                    series_to_fetch[actual_id] = (start_date, end_date)
        
        if not series_to_fetch:
            print(f"All {len(series_ids)} series already cached for requested date range. No API calls needed.")
            return
        
        if already_cached > 0:
            print(f"{already_cached} series already cached. Fetching {len(series_to_fetch)} series from FRED...")
        else:
            print(f"Fetching {len(series_to_fetch)} series from FRED...")
        
        fetched_count = 0
        for actual_id, (fetch_start, fetch_end) in series_to_fetch.items():
            try:
                # Rate limiting
                current_time = time.time()
                time_since_last = current_time - self._last_request_time
                if time_since_last < self._min_request_interval:
                    time.sleep(self._min_request_interval - time_since_last)
                
                data = self.fred.get_series(
                    actual_id,
                    observation_start=fetch_start,
                    observation_end=fetch_end,
                )
                self._last_request_time = time.time()
                
                # Merge with existing data
                if actual_id in self._bulk_cache:
                    self._bulk_cache[actual_id] = self._merge_series(
                        self._bulk_cache[actual_id], data
                    )
                    print(f"  ✓ {actual_id}: extended to {len(self._bulk_cache[actual_id])} observations")
                else:
                    self._bulk_cache[actual_id] = data
                    print(f"  ✓ {actual_id}: {len(data)} observations")
                fetched_count += 1
            except Exception as e:
                print(f"  ✗ {actual_id}: {e}")
        
        # Save to disk after fetching
        if fetched_count > 0:
            self._save_cache_to_disk()
        
        print(f"Pre-fetch complete. {len(self._bulk_cache)} series cached.")

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
        Uses bulk cache if available (for backtesting), otherwise fetches from API.

        Args:
            series_id: FRED series ID or alias
            date: Target date
            lookback_days: Maximum days to look back for data (default 5 for weekends)

        Returns:
            Value for date, or most recent value within lookback window, or None
        """
        actual_id = self.SERIES.get(series_id, series_id)
        
        # Check bulk cache first (for backtesting efficiency)
        if actual_id in self._bulk_cache:
            data = self._bulk_cache[actual_id]
            data = data.dropna()
            if not data.empty:
                # Filter to lookback window
                start = date - timedelta(days=lookback_days)
                mask = (data.index >= start) & (data.index <= date)
                filtered = data[mask]
                if not filtered.empty:
                    valid_dates = filtered.index[filtered.index <= date]
                    if len(valid_dates) > 0:
                        return filtered.loc[valid_dates[-1]]
            return None
        
        # In backtest mode, don't hit the API for missing series
        if self._backtest_mode:
            return None
        
        # Fallback to API fetch (original behavior)
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
            sofr = self.get_value_for_date("SOFR", date, lookback_days=10)
            iorb = self.get_value_for_date("IORB", date, lookback_days=10)
            if sofr is None or iorb is None:
                raise ValueError(f"No SOFR/IORB data for date {date}")
            return (sofr - iorb) * 100  # Convert to bps
        elif date >= self.SOFR_START_DATE:
            # Use SOFR-IOER (April 2018 - July 2021)
            sofr = self.get_value_for_date("SOFR", date, lookback_days=10)
            ioer = self.get_value_for_date("IOER", date, lookback_days=10)
            if sofr is None or ioer is None:
                raise ValueError(f"No SOFR/IOER data for date {date}")
            return (sofr - ioer) * 100  # Convert to bps
        else:
            # Pre-SOFR: use LIBOR-OIS spread instead
            return self.get_libor_ois_spread(date)

    def get_libor_ois_spread(self, date: Optional[datetime] = None) -> float:
        """
        Get funding stress spread in basis points (historical alternative to SOFR-IORB).

        Uses TED spread (3-month LIBOR minus T-Bill) for historical periods.
        TED spread was the canonical measure of bank funding stress during the GFC.
        Note: LIBOR series USD3MTD156N was discontinued; TEDRATE provides pre-calculated spread.
        """
        if date is None:
            date = datetime.now()

        # Get TED spread (already in percentage points)
        ted_value = self.get_value_for_date("TEDRATE", date, lookback_days=10)
        if ted_value is not None:
            return ted_value * 100  # Convert percentage to bps
        
        # Fallback: use Fed Funds - T-Bill spread (use cache)
        ff_value = self.get_value_for_date("DFF", date, lookback_days=10)
        if ff_value is None:
            ff_value = self.get_value_for_date("FEDFUNDS", date, lookback_days=35)
        
        tb_value = self.get_value_for_date("DTB3", date, lookback_days=10)
        if tb_value is None:
            tb_value = self.get_value_for_date("TB3MS", date, lookback_days=35)
        
        if ff_value is None or tb_value is None:
            raise ValueError(f"No funding spread data for {date}")
        
        return (ff_value - tb_value) * 100  # Convert to bps

    def get_liquidity_spread(self, date: Optional[datetime] = None) -> float:
        """
        Get appropriate liquidity spread for any date (date-aware).

        Returns SOFR-IORB for dates >= April 2018, TED spread for 1986-2018,
        and Fed Funds - T-Bill spread for 1954-1986.
        This enables backtesting from 1954-2024 with appropriate historical indicators.
        """
        if date is None:
            date = datetime.now()

        if date >= self.SOFR_START_DATE:
            return self.get_sofr_iorb_spread(date)
        elif date >= self.VXO_START:  # 1986+: TED spread available
            return self.get_libor_ois_spread(date)
        elif date >= self.FED_FUNDS_START:  # 1954+: Use FF-TBill
            return self._get_ff_tbill_spread(date)
        elif date >= self.TB3MS_START:  # 1934+: Use discount rate - TBill
            return self._get_discount_tbill_spread(date)
        elif date >= self.NBER_DATA_START:  # 1907+: Use NBER call money - govt rate
            return self._get_historical_funding_spread(date)
        else:
            raise ValueError(f"No funding spread data available before 1907 for date {date}")

    def _get_ff_tbill_spread(self, date: datetime) -> float:
        """
        Get Fed Funds - T-Bill spread for pre-1986 periods.
        
        The spread between Fed Funds and T-Bills measures bank funding stress,
        similar conceptually to the TED spread. During normal times, banks can
        borrow near the Fed Funds rate; during stress, they pay a premium.
        
        Uses bulk cache for efficiency during backtesting.
        """
        # Try daily Fed Funds first, then monthly
        ff_value = self.get_value_for_date("DFF", date, lookback_days=35)
        if ff_value is None:
            ff_value = self.get_value_for_date("FEDFUNDS", date, lookback_days=35)
        
        # Try daily T-Bill first, then monthly
        tb_value = self.get_value_for_date("DTB3", date, lookback_days=35)
        if tb_value is None:
            tb_value = self.get_value_for_date("TB3MS", date, lookback_days=35)
        
        if ff_value is None or tb_value is None:
            raise ValueError(f"No funding spread data for date {date}")
        
        return (ff_value - tb_value) * 100  # Convert to bps

    def _get_historical_provider(self):
        """Lazy-load HistoricalDataProvider for pre-1954 data."""
        if self._historical_provider is None:
            from .historical_sources import HistoricalDataProvider
            self._historical_provider = HistoricalDataProvider()
        return self._historical_provider

    def _get_discount_tbill_spread(self, date: datetime) -> float:
        """
        Get discount rate - T-Bill spread for 1934-1954 period.
        
        Uses Fed discount rate (INTDSRUSM193N, 1913+) and 3M T-Bill (TB3MS, 1934+).
        """
        discount = self.get_value_for_date("INTDSRUSM193N", date, lookback_days=35)
        tbill = self.get_value_for_date("TB3MS", date, lookback_days=35)
        
        if discount is not None and tbill is not None:
            return (discount - tbill) * 100  # Convert to bps
        
        # Fallback: just use discount rate level as stress indicator
        if discount is not None:
            return discount * 20  # Scale: 5% rate → 100bps equiv
        
        raise ValueError(f"No funding spread data for {date}")

    def _get_historical_funding_spread(self, date: datetime) -> float:
        """
        Get funding stress spread for pre-1934 dates using NBER data.
        
        Uses Call Money Rate - Short-Term Govt Rate from NBER Macrohistory.
        Analogous to TED spread / SOFR-IORB spread.
        """
        provider = self._get_historical_provider()
        spread = provider.get_funding_stress_spread(date)
        if spread is not None:
            return spread
        raise ValueError(f"No historical funding spread for {date}")

    def get_cp_treasury_spread(self, date: Optional[datetime] = None) -> float:
        """Get CP-Treasury spread in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        # Modern era: use CP rate series
        if date >= datetime(1997, 1, 2):
            cp_value = self.get_value_for_date("DCPN3M", date, lookback_days=10)
            treasury_value = self.get_value_for_date("DTB3", date, lookback_days=10)

            if cp_value is not None and treasury_value is not None:
                return (cp_value - treasury_value) * 100  # Convert to bps

        # Pre-1997: use NBER commercial paper rate
        if date >= self.NBER_DATA_START:
            provider = self._get_historical_provider()
            spread = provider.get_cp_spread(date)
            if spread is not None:
                return spread

        raise ValueError(f"No CP-Treasury data available for date {date}")

    def get_term_premium_10y(self, date: Optional[datetime] = None) -> float:
        """Get 10-year term premium in basis points for a specific date."""
        if date is None:
            date = datetime.now()

        value = self.get_value_for_date("TERM_PREMIUM_10Y", date, lookback_days=10)

        if value is None:
            raise ValueError(f"No term premium data available for date {date}")

        return value * 100  # Convert to bps

    # Historical data availability boundaries
    ICE_CREDIT_START = datetime(1996, 12, 31)  # ICE BofA indices start
    VIX_START = datetime(1990, 1, 2)  # VIX (VIXCLS) starts
    VXO_START = datetime(1986, 1, 2)  # VXO available as proxy
    NASDAQ_START = datetime(1971, 2, 5)  # NASDAQ Composite starts
    SP500_OECD_START = datetime(1957, 1, 1)  # OECD S&P 500 starts (monthly)
    FED_FUNDS_START = datetime(1954, 7, 1)  # Fed Funds rate starts
    DGS10_START = datetime(1962, 1, 2)  # 10-Year Treasury starts

    def get_ig_oas(self, date: Optional[datetime] = None) -> float:
        """
        Get Investment Grade OAS in basis points for a specific date.
        
        Note: ICE BofA series (BAMLC0A0CM) returns values in percentage format (e.g., 1.26 = 126bps).
        For dates before Dec 1996, uses Moody's Baa-10Y Treasury spread as proxy.
        Calibration: Baa-Treasury spread is ~40bps wider than IG OAS on average.
        """
        if date is None:
            date = datetime.now()

        if date >= self.ICE_CREDIT_START:
            # Use native ICE BofA series
            value = self.get_value_for_date("IG_OAS", date, lookback_days=10)
            if value is not None:
                # ICE BofA returns percentage (1.26 = 1.26%), convert to bps
                return value * 100  # Convert to bps
        
        # 1919-1997: Use Moody's Baa - 10Y Treasury as proxy
        # Use 35-day lookback for monthly data
        baa_yield = self.get_value_for_date("BAA", date, lookback_days=35)
        treasury_10y = self.get_value_for_date("DGS10", date, lookback_days=35)
        
        if baa_yield is not None and treasury_10y is not None:
            baa_spread = baa_yield - treasury_10y
            # Baa-Treasury is ~40bps wider than IG OAS on average
            ig_proxy = baa_spread * 100 - 40
            return max(ig_proxy, 50)  # Floor at 50bps

        # Try Moody's Baa - long-term govt yield (pre-DGS10)
        lt_govt = self.get_value_for_date("IRLTLT01USM156N", date, lookback_days=35)
        if baa_yield is not None and lt_govt is not None:
            ig_proxy = (baa_yield - lt_govt) * 100 - 40
            return max(ig_proxy, 50)

        # Pre-1919: Use NBER railroad bond spreads
        if date >= self.NBER_DATA_START:
            provider = self._get_historical_provider()
            spread = provider.get_ig_oas_proxy(date)
            if spread is not None:
                return max(spread, 50)

        raise ValueError(f"No IG OAS data available for date {date}")

    def get_hy_oas(self, date: Optional[datetime] = None) -> float:
        """
        Get High Yield OAS in basis points for a specific date.
        
        Note: ICE BofA series (BAMLH0A0HYM2) returns values in percentage format (e.g., 5.72 = 572bps).
        For dates before Dec 1996, uses scaled Baa-Aaa spread as proxy.
        Calibration: Baa-Aaa spread scaled by 4.5x approximates HY OAS levels.
        """
        if date is None:
            date = datetime.now()

        if date >= self.ICE_CREDIT_START:
            # Use native ICE BofA series
            value = self.get_value_for_date("HY_OAS", date, lookback_days=10)
            if value is not None:
                # ICE BofA returns percentage (5.72 = 5.72%), convert to bps
                return value * 100  # Convert to bps
        
        # 1919-1997: Use Baa-Aaa spread scaled up as proxy
        # Use 35-day lookback for monthly data
        baa = self.get_value_for_date("BAA", date, lookback_days=35)
        aaa = self.get_value_for_date("AAA", date, lookback_days=35)
        
        if baa is not None and aaa is not None:
            # Baa-Aaa spread, scaled by 4.5x to approximate HY OAS
            baa_aaa_spread = (baa - aaa) * 100  # Convert to bps
            hy_proxy = baa_aaa_spread * 4.5
            return max(hy_proxy, 250)  # Floor at 250bps

        # Pre-1919: Use NBER railroad bond spread × 3.75
        if date >= self.NBER_DATA_START:
            provider = self._get_historical_provider()
            hy_proxy = provider.get_hy_oas_proxy(date)
            if hy_proxy is not None:
                return max(hy_proxy, 250)

        raise ValueError(f"No HY OAS data available for date {date}")

    def get_vix(self, date: Optional[datetime] = None) -> float:
        """
        Get VIX level for a specific date.
        
        For dates before Jan 1990, uses VXO (old VIX based on S&P 100) as proxy.
        VXO runs from 1986-2021 and is highly correlated with VIX (r > 0.95).
        """
        if date is None:
            date = datetime.now()

        if date >= self.VIX_START:
            # Use native VIX series
            value = self.get_value_for_date("VIX", date, lookback_days=10)
            if value is not None:
                return value
        
        # Pre-1990: Use VXO as proxy
        if date >= self.VXO_START:
            try:
                vxo = self.get_value_for_date("VXOCLS", date, lookback_days=10)
                if vxo is not None:
                    # VXO is typically ~5% higher than VIX
                    return vxo * 0.95
            except Exception:
                pass
        
        # Pre-1986: Use realized volatility from equity returns
        if date >= self.NASDAQ_START:
            try:
                realized_vol = self._compute_realized_volatility(date)
                if realized_vol is not None:
                    return realized_vol
            except Exception:
                pass

        # Pre-1971: Use Shiller monthly prices for realised vol
        if date >= datetime(1871, 1, 1):
            try:
                provider = self._get_historical_provider()
                # Try Schwert volatility series first (1802-1987)
                vix_equiv = provider.get_vix_proxy(date)
                if vix_equiv is not None:
                    return vix_equiv
                # Fallback: Shiller monthly realised vol × 1.3 VRP
                rv = provider.get_realised_vol_from_shiller(date)
                if rv is not None:
                    return rv * 1.3  # Variance risk premium
            except Exception:
                pass

        raise ValueError(f"No VIX data available for date {date}")

    def _compute_realized_volatility(
        self, 
        date: datetime, 
        window_days: int = 21,
        annualize: bool = True
    ) -> Optional[float]:
        """
        Compute realized volatility from NASDAQ returns as VIX proxy for pre-1986.
        
        Realized volatility (standard deviation of returns) is the historical equivalent
        of implied volatility (VIX). The VIX represents market expectations of future
        volatility; realized vol measures actual past volatility. For backtesting,
        we use a 21-day rolling window (~1 month) of daily returns, annualized.
        
        Calibration: VIX tends to be ~15-20% higher than realized vol on average
        (the "variance risk premium"). We scale realized vol by 1.2 to approximate VIX.
        
        References:
        - Carr & Wu (2009): "Variance Risk Premiums", Review of Financial Studies
        - Whaley (2000, 2009): VIX methodology papers
        
        Args:
            date: Target date for volatility estimate
            window_days: Rolling window for returns (default 21 trading days)
            annualize: Whether to annualize volatility (default True)
            
        Returns:
            Estimated VIX-equivalent volatility level
        """
        import numpy as np
        
        # Get NASDAQ series from bulk cache or fetch
        series_id = "NASDAQCOM"
        actual_id = self.SERIES.get(series_id, series_id)
        
        # Check bulk cache first
        if actual_id in self._bulk_cache:
            data = self._bulk_cache[actual_id]
        else:
            # Fetch with buffer for computing returns
            start = date - timedelta(days=window_days * 3)
            data = self.get_series(series_id, start_date=start, end_date=date)
        
        if data is None or len(data) < window_days + 1:
            return None
        
        # Filter to dates up to target date
        data = data[data.index <= pd.Timestamp(date)]
        if len(data) < window_days + 1:
            return None
        
        # Compute daily returns (fill_method=None to avoid deprecation warning)
        returns = data.pct_change(fill_method=None).dropna()
        
        # Get last N days of returns
        recent_returns = returns.tail(window_days)
        if len(recent_returns) < window_days // 2:  # Need at least half the window
            return None
        
        # Compute standard deviation of returns
        daily_vol = recent_returns.std()
        
        # Annualize (252 trading days)
        if annualize:
            annual_vol = daily_vol * np.sqrt(252)
        else:
            annual_vol = daily_vol
        
        # Convert to VIX-like scale (percentage points)
        # Apply variance risk premium adjustment (VIX ~ 1.2x realized vol)
        vix_equivalent = annual_vol * 100 * 1.2
        
        return vix_equivalent

    def get_fed_funds(self, date: Optional[datetime] = None) -> Optional[float]:
        """Get Fed funds rate for a specific date."""
        if date is None:
            date = datetime.now()

        # Try target rate first (available 2008+)
        value = self.get_value_for_date("FED_FUNDS_TARGET", date, lookback_days=10)
        if value is not None:
            return value

        # Fallback to effective rate (1954+)
        value = self.get_value_for_date("FEDFUNDS", date, lookback_days=35)
        if value is not None:
            return value

        # 1913-1954: Use Fed discount rate as policy rate proxy
        if date >= self.DISCOUNT_RATE_START:
            value = self.get_value_for_date("INTDSRUSM193N", date, lookback_days=35)
            if value is not None:
                return value

        # Pre-1913: No central bank — return a synthetic low rate
        # reflecting absence of lender-of-last-resort capacity.
        # Per data spec: policy pillar gets structural penalty of 0.15-0.25.
        # Return a low rate so policy_room_bps is small → low policy score.
        if date >= self.NBER_DATA_START:
            return 0.25  # Effectively near-zero policy room

        return None

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

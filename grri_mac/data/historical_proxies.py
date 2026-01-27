"""Historical proxy data for pre-1998 coverage.

This module provides proxy series to extend MAC framework coverage back to 1996,
enabling analysis of the LTCM crisis (September 1998) and earlier events.

IMPORTANT CAVEATS:
==================
1. These are PROXIES, not the actual series. Use with caution.
2. Pre-1999 Eurozone data uses German DEM equivalents (not EUR).
3. Implied volatility indices are approximated with realized volatility.
4. Some series have gaps that require interpolation or assumptions.

Toggle Usage:
=============
All functions accept `use_historical_proxies=True` to enable proxy fallback.
Default is False to ensure users explicitly opt-in to approximations.

Coverage Summary:
=================
| Region | Native Start | With Proxies |
|--------|--------------|--------------|
| US     | 1996         | 1996 (no change) |
| EU     | 1999         | 1996 (via DEM) |
| JP     | 1985         | 1985 (native) |
| UK     | 1997         | 1996 (via Bank Rate) |

Data Sources:
=============
- FRED: Government bond yields, interbank rates
- Yahoo Finance: Equity indices for realized vol calculation
- Bundesbank: German overnight rates (pre-ECB)
- BoE: SONIA (from Mar 1997), Bank Rate (full history)
- BoJ: Call money rates (from 1985)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Union
import numpy as np

# Try to import data fetching libraries
try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


@dataclass
class ProxyConfig:
    """Configuration for a historical proxy series."""

    target_series: str          # What we're trying to approximate
    proxy_series: str           # The proxy we're using
    source: str                 # Data source (FRED, Yahoo, etc.)
    start_date: str             # Proxy coverage start (YYYY-MM-DD)
    end_date: Optional[str]     # When native series takes over (None = still active)
    transformation: str         # How to transform proxy to target
    correlation_estimate: float # Estimated correlation with target during overlap
    notes: str                  # Caveats and warnings


# =============================================================================
# PROXY DEFINITIONS
# =============================================================================

EUROZONE_PROXIES = {
    # €STR proxy: German Frankfurt Overnight Rate (pre-1999)
    "estr": ProxyConfig(
        target_series="€STR",
        proxy_series="German Frankfurt O/N (FIBOR O/N)",
        source="Bundesbank / FRED IR3TIB01DEM156N",
        start_date="1960-01-01",
        end_date="1998-12-31",
        transformation="direct",
        correlation_estimate=0.95,
        notes="Pre-1999: DEM overnight rate. Conceptually equivalent but different currency.",
    ),

    # €STR-DFR spread proxy: German O/N minus Bundesbank Repo
    "estr_dfr_spread": ProxyConfig(
        target_series="€STR-DFR Spread",
        proxy_series="Frankfurt O/N - Bundesbank Repo Rate",
        source="FRED: IR3TIB01DEM156N - INTDSRDEM193N",
        start_date="1960-01-01",
        end_date="1998-12-31",
        transformation="spread_calculation",
        correlation_estimate=0.90,
        notes="Repo rate = ECB refi predecessor. Spread dynamics similar.",
    ),

    # BTP-Bund spread: Native FRED series available from 1991
    "btp_bund_spread": ProxyConfig(
        target_series="Italy-Germany 10Y Spread",
        proxy_series="FRED: IRLTLT01ITM156N - IRLTLT01DEM156N",
        source="FRED",
        start_date="1991-01-01",
        end_date=None,  # Still valid
        transformation="spread_calculation",
        correlation_estimate=1.0,  # This IS the actual spread
        notes="Native series - no approximation needed. Covers full LTCM period.",
    ),

    # VSTOXX proxy: DAX 30-day realized volatility
    "vstoxx": ProxyConfig(
        target_series="VSTOXX",
        proxy_series="DAX 30-day Realized Volatility",
        source="Yahoo Finance: ^GDAXI",
        start_date="1988-01-01",
        end_date="1999-01-01",  # VSTOXX launched ~2005, but VDAX from 1992
        transformation="realized_vol",
        correlation_estimate=0.85,
        notes="Realized vol proxy. Correlation 0.8-0.9 with implied during stress.",
    ),
}

UK_PROXIES = {
    # SONIA: Native from Mar 1997, Bank Rate fill for Jan-Feb 1996
    "sonia": ProxyConfig(
        target_series="SONIA",
        proxy_series="BoE Bank Rate",
        source="FRED / BoE",
        start_date="1694-01-01",  # Bank Rate has very long history
        end_date="1997-03-01",
        transformation="direct",
        correlation_estimate=0.95,
        notes="SONIA starts Mar 1997. Use Bank Rate for Jan-Feb 1996 gap.",
    ),

    # SONIA-Bank Rate spread: Assume 0 before Mar 1997
    "sonia_bank_rate_spread": ProxyConfig(
        target_series="SONIA-Bank Rate Spread",
        proxy_series="Assumed zero",
        source="Assumption",
        start_date="1996-01-01",
        end_date="1997-03-01",
        transformation="constant_zero",
        correlation_estimate=0.70,
        notes="Before SONIA existed, spread assumed 0. Conservative assumption.",
    ),

    # Gilt spreads: UK 10Y - DE 10Y available from 1960
    "gilt_spread": ProxyConfig(
        target_series="UK-Germany 10Y Spread",
        proxy_series="FRED: IRLTLT01GBM156N - IRLTLT01DEM156N",
        source="FRED",
        start_date="1960-01-01",
        end_date=None,
        transformation="spread_calculation",
        correlation_estimate=1.0,
        notes="Native series - no approximation needed.",
    ),

    # VFTSE proxy: FTSE 100 30-day realized volatility
    "vftse": ProxyConfig(
        target_series="VFTSE",
        proxy_series="FTSE 100 30-day Realized Volatility",
        source="Yahoo Finance: ^FTSE",
        start_date="1984-01-01",
        end_date="2000-01-01",  # VFTSE launched later
        transformation="realized_vol",
        correlation_estimate=0.85,
        notes="Realized vol proxy for implied vol index.",
    ),
}

JAPAN_PROXIES = {
    # TONAR: Native from Jul 1985
    "tonar": ProxyConfig(
        target_series="TONAR",
        proxy_series="BoJ Call Money Rate",
        source="FRED: IRSTCI01JPM156N",
        start_date="1960-01-01",
        end_date=None,  # Native series
        transformation="direct",
        correlation_estimate=1.0,
        notes="Native series available - no proxy needed.",
    ),

    # JGB 10Y: Native from 1989
    "jgb_10y": ProxyConfig(
        target_series="JGB 10Y Yield",
        proxy_series="FRED: IRLTLT01JPM156N",
        source="FRED",
        start_date="1989-01-01",
        end_date=None,
        transformation="direct",
        correlation_estimate=1.0,
        notes="Native series available from 1989.",
    ),

    # Nikkei VI proxy: Nikkei 225 30-day realized volatility
    "nikkei_vi": ProxyConfig(
        target_series="Nikkei VI",
        proxy_series="Nikkei 225 30-day Realized Volatility",
        source="Yahoo Finance: ^N225",
        start_date="1949-01-01",  # Very long history
        end_date="2000-01-01",
        transformation="realized_vol",
        correlation_estimate=0.85,
        notes="Realized vol proxy. Nikkei 225 has data from 1949.",
    ),
}


# FRED series codes for direct fetching
FRED_SERIES = {
    # Government Bond Yields (10Y)
    "germany_10y": "IRLTLT01DEM156N",      # Apr 1953+
    "italy_10y": "IRLTLT01ITM156N",         # Jan 1991+
    "uk_10y": "IRLTLT01GBM156N",             # Jan 1960+
    "japan_10y": "IRLTLT01JPM156N",          # Jan 1989+

    # Interbank / Overnight Rates
    "germany_3m_interbank": "IR3TIB01DEM156N",  # Jan 1960+
    "germany_discount": "INTDSRDEM193N",        # Jan 1950 - Dec 1998
    "japan_call_money": "IRSTCI01JPM156N",      # Jan 1960+

    # US (for reference)
    "us_10y": "DGS10",                          # Apr 1953+
    "us_3m_tbill": "DTB3",                      # Jan 1954+
}

YAHOO_TICKERS = {
    "dax": "^GDAXI",       # German DAX (1988+)
    "ftse": "^FTSE",       # UK FTSE 100 (1984+)
    "nikkei": "^N225",     # Japan Nikkei 225 (1949+)
    "eurostoxx": "^STOXX50E",  # Euro STOXX 50 (1987+)
}


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

class HistoricalProxyClient:
    """Client for fetching historical proxy data with toggle control."""

    def __init__(
        self,
        fred_api_key: Optional[str] = None,
        use_historical_proxies: bool = False,
    ):
        """
        Initialize the historical proxy client.

        Args:
            fred_api_key: FRED API key (optional, uses env var if not provided)
            use_historical_proxies: Whether to enable proxy fallback.
                                   Default False - must explicitly opt-in.
        """
        self.use_proxies = use_historical_proxies
        self._fred = None
        self._fred_api_key = fred_api_key

        if not self.use_proxies:
            print(
                "WARNING: Historical proxies DISABLED. "
                "Set use_historical_proxies=True to enable pre-1998 coverage."
            )

    @property
    def fred(self):
        """Lazy-load FRED client."""
        if self._fred is None:
            if not FRED_AVAILABLE:
                raise ImportError("fredapi not installed. Run: pip install fredapi")
            import os
            api_key = self._fred_api_key or os.environ.get("FRED_API_KEY")
            if not api_key:
                raise ValueError("FRED API key required. Set FRED_API_KEY env var.")
            self._fred = Fred(api_key=api_key)
        return self._fred

    def get_proxy_config(self, region: str, indicator: str) -> Optional[ProxyConfig]:
        """Get proxy configuration for a region/indicator pair."""
        proxy_maps = {
            "EU": EUROZONE_PROXIES,
            "UK": UK_PROXIES,
            "JP": JAPAN_PROXIES,
        }
        region_proxies = proxy_maps.get(region.upper(), {})
        return region_proxies.get(indicator.lower())

    def get_spread_from_fred(
        self,
        series1: str,
        series2: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Calculate spread between two FRED series.

        Args:
            series1: FRED series code for first yield
            series2: FRED series code for second yield
            start_date: Start date for data
            end_date: End date for data

        Returns:
            Dict with dates as keys, spread values (series1 - series2) as values
        """
        data1 = self.fred.get_series(series1, start_date, end_date)
        data2 = self.fred.get_series(series2, start_date, end_date)

        # Align dates
        common_dates = data1.index.intersection(data2.index)
        spread = data1.loc[common_dates] - data2.loc[common_dates]

        return spread.to_dict()

    def get_btp_bund_spread(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get Italy-Germany 10Y spread (basis points).

        Native FRED series available from Jan 1991 - covers LTCM period.

        Args:
            date: Date for spread (default: latest)

        Returns:
            Spread in basis points, or None if unavailable
        """
        try:
            italy = self.fred.get_series(
                FRED_SERIES["italy_10y"],
                observation_start=date - timedelta(days=7) if date else None,
                observation_end=date,
            )
            germany = self.fred.get_series(
                FRED_SERIES["germany_10y"],
                observation_start=date - timedelta(days=7) if date else None,
                observation_end=date,
            )

            if italy.empty or germany.empty:
                return None

            # Get most recent values
            spread_pct = italy.iloc[-1] - germany.iloc[-1]
            return spread_pct * 100  # Convert to bps

        except Exception as e:
            print(f"Error fetching BTP-Bund spread: {e}")
            return None

    def get_gilt_bund_spread(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get UK-Germany 10Y spread (basis points).

        Native FRED series available from Jan 1960.

        Args:
            date: Date for spread (default: latest)

        Returns:
            Spread in basis points, or None if unavailable
        """
        try:
            uk = self.fred.get_series(
                FRED_SERIES["uk_10y"],
                observation_start=date - timedelta(days=7) if date else None,
                observation_end=date,
            )
            germany = self.fred.get_series(
                FRED_SERIES["germany_10y"],
                observation_start=date - timedelta(days=7) if date else None,
                observation_end=date,
            )

            if uk.empty or germany.empty:
                return None

            spread_pct = uk.iloc[-1] - germany.iloc[-1]
            return spread_pct * 100  # Convert to bps

        except Exception as e:
            print(f"Error fetching Gilt-Bund spread: {e}")
            return None

    def calculate_realized_volatility(
        self,
        ticker: str,
        date: Optional[datetime] = None,
        window_days: int = 30,
        annualize: bool = True,
    ) -> Optional[float]:
        """
        Calculate realized volatility from price data.

        This is used as a proxy for implied volatility indices
        (VSTOXX, VFTSE, Nikkei VI) before they existed.

        Args:
            ticker: Yahoo Finance ticker symbol
            date: End date for calculation (default: latest)
            window_days: Rolling window for vol calculation
            annualize: Whether to annualize (multiply by √252)

        Returns:
            Realized volatility (annualized if requested), or None
        """
        if not YFINANCE_AVAILABLE:
            raise ImportError("yfinance not installed. Run: pip install yfinance")

        if not self.use_proxies:
            print("Historical proxies disabled. Enable with use_historical_proxies=True")
            return None

        try:
            # Fetch price data
            end = date or datetime.now()
            start = end - timedelta(days=window_days + 60)  # Extra buffer

            data = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
            )

            if data.empty or len(data) < window_days:
                return None

            # Calculate log returns
            prices = data["Adj Close"]
            log_returns = np.log(prices / prices.shift(1)).dropna()

            # Rolling standard deviation
            rolling_std = log_returns.rolling(window=window_days).std()

            # Get value at target date
            vol = rolling_std.iloc[-1]

            if annualize:
                vol = vol * np.sqrt(252)

            # Convert to percentage points (VIX-like scale)
            return vol * 100

        except Exception as e:
            print(f"Error calculating realized vol for {ticker}: {e}")
            return None

    def get_vstoxx_proxy(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get VSTOXX proxy using DAX 30-day realized volatility.

        CAVEAT: This is a PROXY. Correlation with actual VSTOXX ~0.85 during stress.

        Args:
            date: Date for calculation

        Returns:
            Realized vol as VSTOXX proxy, or None
        """
        proxy = self.calculate_realized_volatility(
            YAHOO_TICKERS["dax"],
            date=date,
            window_days=30,
        )

        if proxy is not None:
            print(
                f"WARNING: VSTOXX proxy (DAX realized vol) = {proxy:.1f}. "
                "This is an approximation, not actual implied vol."
            )

        return proxy

    def get_vftse_proxy(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get VFTSE proxy using FTSE 100 30-day realized volatility.

        CAVEAT: This is a PROXY. Correlation with actual VFTSE ~0.85 during stress.
        """
        proxy = self.calculate_realized_volatility(
            YAHOO_TICKERS["ftse"],
            date=date,
            window_days=30,
        )

        if proxy is not None:
            print(
                f"WARNING: VFTSE proxy (FTSE realized vol) = {proxy:.1f}. "
                "This is an approximation, not actual implied vol."
            )

        return proxy

    def get_nikkei_vi_proxy(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get Nikkei VI proxy using Nikkei 225 30-day realized volatility.

        CAVEAT: This is a PROXY. Correlation with actual Nikkei VI ~0.85.
        """
        proxy = self.calculate_realized_volatility(
            YAHOO_TICKERS["nikkei"],
            date=date,
            window_days=30,
        )

        if proxy is not None:
            print(
                f"WARNING: Nikkei VI proxy (Nikkei realized vol) = {proxy:.1f}. "
                "This is an approximation, not actual implied vol."
            )

        return proxy

    def get_japan_call_money_rate(
        self,
        date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        Get Japan call money rate (TONAR equivalent).

        Native FRED series from 1960 - no proxy needed.
        """
        try:
            data = self.fred.get_series(
                FRED_SERIES["japan_call_money"],
                observation_start=date - timedelta(days=7) if date else None,
                observation_end=date,
            )

            if data.empty:
                return None

            return data.iloc[-1]

        except Exception as e:
            print(f"Error fetching Japan call money rate: {e}")
            return None

    def get_coverage_summary(self) -> dict:
        """
        Get summary of data coverage with and without proxies.

        Returns:
            Dict with coverage information by region
        """
        return {
            "US": {
                "native_start": "1996",
                "with_proxies": "1996",
                "notes": "No proxies needed - full FRED coverage",
            },
            "EU": {
                "native_start": "1999 (€STR), 2005 (VSTOXX)",
                "with_proxies": "1991 (BTP-Bund), 1988 (DAX vol proxy)",
                "notes": "Pre-1999 uses German DEM equivalents",
                "caveats": [
                    "€STR proxy: German O/N rate (different currency)",
                    "VSTOXX proxy: DAX realized vol (correlation ~0.85)",
                    "TARGET2: No equivalent pre-1999",
                ],
            },
            "UK": {
                "native_start": "1997 (SONIA)",
                "with_proxies": "1960 (Gilt spreads), 1984 (FTSE vol)",
                "notes": "SONIA gap Jan-Feb 1996 filled with Bank Rate",
                "caveats": [
                    "VFTSE proxy: FTSE realized vol (correlation ~0.85)",
                    "SONIA-Bank Rate spread: assumed 0 before Mar 1997",
                ],
            },
            "JP": {
                "native_start": "1985 (TONAR), 1989 (JGB 10Y)",
                "with_proxies": "1960 (call money), 1949 (Nikkei vol)",
                "notes": "Best historical coverage of non-US regions",
                "caveats": [
                    "Nikkei VI proxy: Nikkei realized vol (correlation ~0.85)",
                ],
            },
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def list_available_proxies() -> dict:
    """List all available historical proxies by region."""
    return {
        "EU": list(EUROZONE_PROXIES.keys()),
        "UK": list(UK_PROXIES.keys()),
        "JP": list(JAPAN_PROXIES.keys()),
    }


def get_proxy_warnings(region: str) -> list[str]:
    """Get list of caveats/warnings for using proxies in a region."""
    warnings = {
        "EU": [
            "Pre-1999 €STR uses German DEM overnight rate - different currency",
            "VSTOXX proxy (DAX realized vol) correlation ~0.85 with actual implied",
            "TARGET2 has no equivalent before 1999 - omit from pre-1999 analysis",
            "BTP-Bund spread is NATIVE from 1991 - no approximation needed",
        ],
        "UK": [
            "SONIA only starts Mar 1997 - Jan-Feb 1996 uses Bank Rate assumption",
            "VFTSE proxy (FTSE realized vol) correlation ~0.85 with actual implied",
            "Gilt spreads are NATIVE from 1960 - no approximation needed",
        ],
        "JP": [
            "Nikkei VI proxy (Nikkei realized vol) correlation ~0.85 with actual",
            "Call money rate and JGB yields are NATIVE - good historical coverage",
            "Japan has best non-US historical data availability",
        ],
    }
    return warnings.get(region.upper(), [])

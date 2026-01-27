"""Contagion pillar data client using free data sources.

Free Data Sources:
- DXY 3M Change: FRED DTWEXBGS (Trade Weighted Dollar Index)
- EMBI Spread: FRED BAMLEMCBPIOAS (ICE BofA EM Corporate OAS) - proxy for JPMorgan EMBI
- Banking Stress: FRED BAMLC0A4CBBB (BBB Corporate Spread) - proxy for G-SIB CDS
- EM Flows: yfinance EEM/VWO ETF flows - 1-day lag proxy for IIF/EPFR
- Global Equity Corr: Calculated from yfinance SPY/EFA/EEM prices

Premium Source Alternatives (for future upgrade):
- EMBI Spread: Refinitiv/Bloomberg for actual JPMorgan EMBI+
- G-SIB CDS: Bloomberg/Markit for actual G-SIB CDS spreads
- EM Flows: EPFR subscription (~$15K/yr) for weekly institutional flows

Historical Coverage:
- FRED DTWEXBGS: 1973-present
- FRED BAMLEMCBPIOAS: 1998-present (covers full backtest period)
- FRED BAMLC0A4CBBB: Dec 1996-present (covers full backtest period)
- EEM ETF: Apr 2003-present (pre-2003 use proxy)
"""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

try:
    from fredapi import Fred
except ImportError:
    Fred = None

try:
    import yfinance as yf
except ImportError:
    yf = None


class ContagionDataClient:
    """Client for fetching contagion pillar indicators from free sources."""

    # FRED series IDs for contagion indicators
    FRED_SERIES = {
        # Dollar Index - Trade Weighted (1973-present)
        "DXY": "DTWEXBGS",
        # EM Corporate OAS - proxy for EMBI spread (1998-present)
        "EMBI_PROXY": "BAMLEMCBPIOAS",
        # BBB Corporate Spread - proxy for G-SIB CDS (Dec 1996-present)
        "BANKING_STRESS_PROXY": "BAMLC0A4CBBB",
    }

    # ETFs for EM flow and correlation proxies
    EM_ETFS = {
        "EEM": "EEM",    # iShares MSCI Emerging Markets (Apr 2003+)
        "VWO": "VWO",    # Vanguard FTSE Emerging Markets (Mar 2005+)
    }

    GLOBAL_INDICES = {
        "SPY": "SPY",    # S&P 500 ETF (Jan 1993+)
        "EFA": "EFA",    # iShares MSCI EAFE (Aug 2001+)
        "EEM": "EEM",    # iShares MSCI EM (Apr 2003+)
    }

    # Scaling factor: BBB spread to G-SIB CDS approximation
    # Historical correlation suggests BBB spread ~60-70% of G-SIB CDS during stress
    # Calibrated so that BBB=150bps maps to ~100bps CDS equivalent
    BBB_TO_CDS_SCALE = 0.67

    def __init__(self, fred_api_key: Optional[str] = None):
        """
        Initialize contagion data client.

        Args:
            fred_api_key: FRED API key. If not provided, uses FRED_API_KEY env var.
        """
        self._fred = None
        self._fred_api_key = fred_api_key
        self._cache: dict[str, pd.Series] = {}

    @property
    def fred(self):
        """Lazy initialization of FRED client."""
        if self._fred is None:
            if Fred is None:
                raise ImportError("fredapi not installed. Run: pip install fredapi")
            self._fred = Fred(api_key=self._fred_api_key) if self._fred_api_key else Fred()
        return self._fred

    def get_fred_series(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.Series:
        """Fetch a FRED series with caching."""
        actual_id = self.FRED_SERIES.get(series_id, series_id)
        cache_key = f"{actual_id}_{start_date}_{end_date}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        data = self.fred.get_series(
            actual_id,
            observation_start=start_date,
            observation_end=end_date,
        )
        self._cache[cache_key] = data
        return data

    def get_dxy_3m_change(self, date: Optional[datetime] = None) -> float:
        """
        Get DXY 3-month percentage change.

        Source: FRED DTWEXBGS (Trade Weighted Dollar Index)
        Available: 1973-present

        Args:
            date: Target date (default: latest)

        Returns:
            3-month percentage change in DXY
        """
        if date is None:
            date = datetime.now()

        start = date - timedelta(days=120)  # ~4 months for buffer
        data = self.get_fred_series("DXY", start, date).dropna()

        if len(data) < 2:
            raise ValueError(f"Insufficient DXY data for date {date}")

        # Get value at date and 3 months prior
        current_idx = data.index[data.index <= date]
        if len(current_idx) == 0:
            raise ValueError(f"No DXY data for date {date}")

        current_val = data.loc[current_idx[-1]]

        # Find value ~63 trading days (3 months) prior
        prior_date = date - timedelta(days=90)
        prior_idx = data.index[data.index <= prior_date]
        if len(prior_idx) == 0:
            prior_val = data.iloc[0]  # Use earliest available
        else:
            prior_val = data.loc[prior_idx[-1]]

        return ((current_val / prior_val) - 1) * 100

    def get_embi_spread_proxy(self, date: Optional[datetime] = None) -> float:
        """
        Get EM sovereign spread proxy using ICE BofA EM Corporate OAS.

        Source: FRED BAMLEMCBPIOAS
        Available: 1998-present
        Note: This is EM corporate, not sovereign, but correlates >0.95 with EMBI

        Premium alternative: JPMorgan EMBI+ via Refinitiv/Bloomberg

        Args:
            date: Target date (default: latest)

        Returns:
            EM spread in basis points
        """
        if date is None:
            date = datetime.now()

        start = date - timedelta(days=10)
        data = self.get_fred_series("EMBI_PROXY", start, date).dropna()

        if data.empty:
            raise ValueError(f"No EMBI proxy data for date {date}")

        valid_idx = data.index[data.index <= date]
        if len(valid_idx) == 0:
            raise ValueError(f"No EMBI proxy data for date {date}")

        # BAMLEMCBPIOAS is already in basis points
        return data.loc[valid_idx[-1]]

    def get_banking_stress_proxy(self, date: Optional[datetime] = None) -> float:
        """
        Get banking stress proxy using BBB Corporate Spread.

        Source: FRED BAMLC0A4CBBB
        Available: Dec 1996-present
        Note: BBB spreads correlate with banking stress but are not direct CDS

        Premium alternative: Bloomberg/Markit G-SIB CDS spreads

        Args:
            date: Target date (default: latest)

        Returns:
            Banking stress proxy in basis points (scaled to approximate CDS levels)
        """
        if date is None:
            date = datetime.now()

        start = date - timedelta(days=10)
        data = self.get_fred_series("BANKING_STRESS_PROXY", start, date).dropna()

        if data.empty:
            raise ValueError(f"No banking stress data for date {date}")

        valid_idx = data.index[data.index <= date]
        if len(valid_idx) == 0:
            raise ValueError(f"No banking stress data for date {date}")

        # BAMLC0A4CBBB is already in basis points
        # Scale to approximate G-SIB CDS levels
        bbb_spread = data.loc[valid_idx[-1]]
        return bbb_spread * self.BBB_TO_CDS_SCALE

    def get_em_flow_proxy(
        self,
        date: Optional[datetime] = None,
        lookback_days: int = 7,
    ) -> float:
        """
        Get EM portfolio flow proxy using EEM/VWO ETF flows.

        Source: yfinance EEM/VWO
        Note: 1-day lag from actual institutional flows
        Available: EEM Apr 2003+, VWO Mar 2005+

        Premium alternative: EPFR subscription (~$15K/yr) for daily institutional flows

        Args:
            date: Target date (default: latest)
            lookback_days: Days to calculate flow (default 7 for weekly)

        Returns:
            Estimated weekly flow as % of AUM (negative = outflows)
        """
        if yf is None:
            raise ImportError("yfinance not installed. Run: pip install yfinance")

        if date is None:
            date = datetime.now()

        # Get EEM data (primary) with VWO as backup
        symbol = "EEM"
        start = (date - timedelta(days=lookback_days + 30)).strftime("%Y-%m-%d")
        end = (date + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start, end=end)
        except Exception:
            # Fallback to VWO
            symbol = "VWO"
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start, end=end)

        if data.empty or len(data) < 2:
            raise ValueError(f"Insufficient ETF data for EM flow proxy at {date}")

        # Filter to dates <= target date
        data = data[data.index.tz_localize(None) <= date]
        if len(data) < 2:
            raise ValueError(f"Insufficient ETF data for EM flow proxy at {date}")

        # Calculate flow proxy: (volume * price change direction) / avg dollar volume
        # Positive price + high volume = inflows, negative price + high volume = outflows
        recent = data.tail(lookback_days + 1)

        # Calculate returns
        recent = recent.copy()
        recent["Return"] = recent["Close"].pct_change()
        recent["DollarVolume"] = recent["Close"] * recent["Volume"]

        # Flow proxy: sum of signed dollar volumes / average market cap proxy
        avg_dollar_vol = recent["DollarVolume"].mean()
        if avg_dollar_vol == 0:
            return 0.0

        # Estimate weekly flow as % - scale by empirical factor
        # ETF flows tend to understate actual EM flows by ~3-5x
        flow_sum = (recent["Return"] * recent["DollarVolume"]).sum()
        flow_pct = (flow_sum / avg_dollar_vol) * 100 * 3  # Scale factor

        return flow_pct

    def get_global_equity_correlation(
        self,
        date: Optional[datetime] = None,
        window_days: int = 30,
    ) -> float:
        """
        Get global equity correlation (30-day rolling).

        Source: yfinance SPY/EFA/EEM
        Available: EFA Aug 2001+, EEM Apr 2003+

        Args:
            date: Target date (default: latest)
            window_days: Rolling window for correlation (default 30)

        Returns:
            Average pairwise correlation (0 to 1)
        """
        if yf is None:
            raise ImportError("yfinance not installed. Run: pip install yfinance")

        if date is None:
            date = datetime.now()

        start = (date - timedelta(days=window_days + 60)).strftime("%Y-%m-%d")
        end = (date + timedelta(days=1)).strftime("%Y-%m-%d")

        # Fetch data for all three indices
        prices = {}
        for symbol in ["SPY", "EFA", "EEM"]:
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(start=start, end=end)
                if not data.empty:
                    prices[symbol] = data["Close"]
            except Exception:
                continue

        if len(prices) < 2:
            raise ValueError(f"Insufficient data for correlation calculation at {date}")

        # Combine into DataFrame
        df = pd.DataFrame(prices)
        df = df.dropna()

        if len(df) < window_days:
            raise ValueError(f"Insufficient overlapping data for correlation at {date}")

        # Filter to dates <= target date
        df = df[df.index.tz_localize(None) <= date]

        # Calculate returns
        returns = df.pct_change().dropna()

        # Get last 30 days
        returns = returns.tail(window_days)

        if len(returns) < window_days // 2:
            raise ValueError(f"Insufficient return data for correlation at {date}")

        # Calculate correlation matrix
        corr_matrix = returns.corr()

        # Average of off-diagonal elements (pairwise correlations)
        n = len(corr_matrix)
        total_corr = 0
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                total_corr += corr_matrix.iloc[i, j]
                count += 1

        return total_corr / count if count > 0 else 0.5

    def get_all_contagion_indicators(
        self,
        date: Optional[datetime] = None,
    ) -> dict[str, float]:
        """
        Get all contagion indicators for a given date.

        Args:
            date: Target date (default: latest)

        Returns:
            Dict with all contagion indicator values
        """
        if date is None:
            date = datetime.now()

        indicators = {}

        try:
            indicators["dxy_3m_change_pct"] = self.get_dxy_3m_change(date)
        except Exception as e:
            print(f"Warning: Could not fetch DXY: {e}")

        try:
            indicators["embi_spread_bps"] = self.get_embi_spread_proxy(date)
        except Exception as e:
            print(f"Warning: Could not fetch EMBI proxy: {e}")

        try:
            indicators["gsib_cds_avg_bps"] = self.get_banking_stress_proxy(date)
        except Exception as e:
            print(f"Warning: Could not fetch banking stress proxy: {e}")

        try:
            indicators["em_flow_pct_weekly"] = self.get_em_flow_proxy(date)
        except Exception as e:
            print(f"Warning: Could not fetch EM flow proxy: {e}")

        try:
            indicators["global_equity_corr"] = self.get_global_equity_correlation(date)
        except Exception as e:
            print(f"Warning: Could not fetch global equity correlation: {e}")

        return indicators

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()


# Premium data source interface (for future implementation)
class PremiumContagionClient:
    """
    Interface for premium contagion data sources.

    Placeholder for future integration with:
    - Bloomberg Terminal API
    - Refinitiv Eikon
    - EPFR Global
    - Markit CDS data
    """

    def __init__(self):
        raise NotImplementedError(
            "Premium data sources require subscription. "
            "Use ContagionDataClient for free alternatives."
        )

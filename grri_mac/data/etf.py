"""ETF data client for volatility and positioning proxies."""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None


class ETFClient:
    """Client for fetching ETF data as positioning proxies."""

    # Key ETFs for MAC positioning indicators
    ETFS = {
        # Volatility products
        "SVXY": "SVXY",  # Short VIX futures
        "UVXY": "UVXY",  # 1.5x Long VIX futures
        "VXX": "VXX",  # VIX short-term futures
        # Leveraged equity
        "TQQQ": "TQQQ",  # 3x Long Nasdaq
        "SQQQ": "SQQQ",  # 3x Short Nasdaq
        "SPXL": "SPXL",  # 3x Long S&P 500
        "SPXS": "SPXS",  # 3x Short S&P 500
        # Credit
        "LQD": "LQD",  # iShares IG Corp Bond
        "HYG": "HYG",  # iShares HY Corp Bond
        "JNK": "JNK",  # SPDR HY Bond
        # Treasury
        "TLT": "TLT",  # iShares 20+ Year Treasury
        "IEF": "IEF",  # iShares 7-10 Year Treasury
        "SHY": "SHY",  # iShares 1-3 Year Treasury
    }

    def __init__(self):
        """Initialize ETF client."""
        if yf is None:
            raise ImportError("yfinance package not installed. Run: pip install yfinance")
        self._cache: dict[str, pd.DataFrame] = {}

    def get_etf_data(
        self,
        symbol: str,
        period: str = "1y",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch ETF historical data.

        Args:
            symbol: ETF ticker symbol
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with OHLCV data
        """
        actual_symbol = self.ETFS.get(symbol, symbol)

        cache_key = f"{actual_symbol}_{period}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        ticker = yf.Ticker(actual_symbol)
        data = ticker.history(period=period)

        if use_cache and not data.empty:
            self._cache[cache_key] = data

        return data

    def get_aum_estimate(self, symbol: str) -> float:
        """
        Estimate ETF AUM based on shares outstanding and price.

        Args:
            symbol: ETF ticker symbol

        Returns:
            Estimated AUM in billions USD
        """
        actual_symbol = self.ETFS.get(symbol, symbol)
        ticker = yf.Ticker(actual_symbol)

        info = ticker.info
        shares_outstanding = info.get("sharesOutstanding", 0)
        price = info.get("regularMarketPrice", info.get("previousClose", 0))

        if shares_outstanding and price:
            return (shares_outstanding * price) / 1e9  # Convert to billions

        # Fallback: use recent volume as proxy
        data = self.get_etf_data(symbol, period="5d")
        if not data.empty:
            avg_volume = data["Volume"].mean()
            avg_price = data["Close"].mean()
            # Rough proxy: assume volume is ~1% of shares
            return (avg_volume * 100 * avg_price) / 1e9

        return 0.0

    def get_svxy_aum(self) -> float:
        """Get SVXY AUM estimate in millions USD."""
        return self.get_aum_estimate("SVXY") * 1000  # Convert to millions

    def get_etf_flows(
        self,
        symbol: str,
        lookback_days: int = 30,
    ) -> pd.DataFrame:
        """
        Estimate ETF flows based on volume and price changes.

        Note: True flows require subscription data. This is a rough proxy.

        Args:
            symbol: ETF ticker symbol
            lookback_days: Days to look back

        Returns:
            DataFrame with estimated flows
        """
        data = self.get_etf_data(symbol, period="3mo")

        if data.empty:
            return pd.DataFrame()

        # Filter to lookback period
        cutoff = datetime.now() - timedelta(days=lookback_days)
        data = data[data.index >= cutoff.strftime("%Y-%m-%d")]

        # Calculate dollar volume as flow proxy
        data["DollarVolume"] = data["Close"] * data["Volume"]

        # Calculate cumulative flow proxy (signed by price direction)
        data["PriceChange"] = data["Close"].pct_change()
        data["FlowProxy"] = data["DollarVolume"] * data["PriceChange"].apply(
            lambda x: 1 if x > 0 else -1 if x < 0 else 0
        )
        data["CumulativeFlow"] = data["FlowProxy"].cumsum()

        return data[["Close", "Volume", "DollarVolume", "FlowProxy", "CumulativeFlow"]]

    def get_vix_term_structure(self) -> tuple[float, float]:
        """
        Get VIX term structure from VIX futures ETFs.

        Returns:
            Tuple of (front month proxy, second month proxy)
        """
        # Use ETF prices as term structure proxy
        try:
            vxx = self.get_etf_data("VXX", period="5d")
            if not vxx.empty:
                m1_proxy = vxx["Close"].iloc[-1]
                m1_prev = vxx["Close"].iloc[-2] if len(vxx) > 1 else m1_proxy
                return m1_proxy, m1_prev
        except Exception:
            pass

        return 0.0, 0.0

    def get_credit_etf_spread_proxy(self) -> dict[str, float]:
        """
        Get credit ETF discount/premium as spread proxy.

        Returns:
            Dict with LQD and HYG discount/premium percentages
        """
        result = {}

        for symbol in ["LQD", "HYG"]:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                nav = info.get("navPrice", 0)
                price = info.get("regularMarketPrice", info.get("previousClose", 0))

                if nav and price:
                    result[symbol] = ((price - nav) / nav) * 100
                else:
                    result[symbol] = 0.0
            except Exception:
                result[symbol] = 0.0

        return result

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()

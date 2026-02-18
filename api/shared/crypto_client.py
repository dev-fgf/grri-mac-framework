"""Lightweight crypto-equity correlation client.

Fetches BTC-USD and SPY daily prices from Yahoo Finance's public chart API
and computes 60-day rolling correlation. No yfinance dependency needed.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import requests

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"


def _fetch_daily_closes(symbol: str, days: int = 90) -> pd.Series:
    """Fetch daily close prices from Yahoo Finance chart API.

    Args:
        symbol: Ticker symbol (e.g. 'BTC-USD', 'SPY')
        days: Number of calendar days of history

    Returns:
        pd.Series indexed by date with close prices
    """
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=days)).timestamp())

    params = {
        "period1": start,
        "period2": end,
        "interval": "1d",
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params=params,
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]

    dates = [datetime.utcfromtimestamp(ts).date() for ts in timestamps]
    series = pd.Series(closes, index=pd.DatetimeIndex(dates), name=symbol)
    return series.dropna()


def get_btc_spy_correlation(window: int = 60) -> float | None:
    """Compute rolling BTC-SPY daily-return correlation.

    Args:
        window: Rolling window in trading days (default 60)

    Returns:
        Latest correlation value, or None on failure
    """
    try:
        btc = _fetch_daily_closes("BTC-USD", days=window + 40)
        spy = _fetch_daily_closes("SPY", days=window + 40)

        # Align on common dates and compute daily returns
        df = pd.DataFrame({"btc": btc, "spy": spy}).dropna()
        if len(df) < window:
            logger.warning(
                "Insufficient data for %d-day correlation (got %d rows)",
                window, len(df),
            )
            return None

        returns = df.pct_change().dropna()
        corr = returns["btc"].rolling(window).corr(returns["spy"]).iloc[-1]
        if pd.isna(corr):
            return None
        return round(float(corr), 4)
    except Exception as e:
        logger.warning("Failed to fetch BTC-SPY correlation: %s", e)
        return None

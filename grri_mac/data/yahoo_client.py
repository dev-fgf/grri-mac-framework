"""
Yahoo Finance Client for Private Credit Monitoring.

Fetches BDC, ETF, and PE firm data using yfinance library.
Free, no API key required.

Usage:
    client = YahooFinanceClient()
    bdc_data = await client.get_bdc_data()
    etf_data = await client.get_leveraged_loan_etf_data()
"""

from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# BDC tickers with weights for composite
BDC_TICKERS: Dict[str, Dict[str, Any]] = {
    "ARCC": {"name": "Ares Capital", "weight": 0.25},
    "MAIN": {"name": "Main Street Capital", "weight": 0.20},
    "FSK": {"name": "FS KKR Capital", "weight": 0.20},
    "PSEC": {"name": "Prospect Capital", "weight": 0.15},
    "GBDC": {"name": "Golub Capital BDC", "weight": 0.20},
}

# Leveraged loan ETFs
LEVERAGED_LOAN_ETFS: Dict[str, Dict[str, Any]] = {
    "BKLN": {"name": "Invesco Senior Loan ETF"},
    "SRLN": {"name": "SPDR Blackstone Senior Loan ETF"},
}

# PE firm stocks
PE_FIRM_TICKERS: Dict[str, Dict[str, Any]] = {
    "KKR": {"name": "KKR & Co"},
    "BX": {"name": "Blackstone"},
    "APO": {"name": "Apollo Global"},
    "CG": {"name": "Carlyle Group"},
}


@dataclass
class BDCQuote:
    """BDC price and NAV data."""
    ticker: str
    name: str
    price: float
    book_value_per_share: Optional[float]  # Proxy for NAV
    discount_premium: Optional[float]  # Negative = discount
    change_30d_pct: Optional[float]
    timestamp: datetime


@dataclass
class ETFQuote:
    """ETF price data."""
    ticker: str
    name: str
    price: float
    change_30d_pct: Optional[float]
    timestamp: datetime


@dataclass
class StockQuote:
    """Stock price data."""
    ticker: str
    name: str
    price: float
    change_30d_pct: Optional[float]
    timestamp: datetime


class YahooFinanceClient:
    """
    Client for fetching market data from Yahoo Finance.

    Uses yfinance library (pip install yfinance).
    """

    def __init__(self):
        """Initialize the client."""
        self._yf = None

    def _get_yfinance(self):
        """Lazy load yfinance to avoid import errors if not installed."""
        if self._yf is None:
            try:
                import yfinance as yf
                self._yf = yf
            except ImportError:
                raise ImportError(
                    "yfinance not installed. Run: pip install yfinance"
                )
        return self._yf

    def get_bdc_data(self) -> Dict[str, BDCQuote]:
        """
        Fetch BDC price and book value data.

        Returns:
            Dict mapping ticker to BDCQuote
        """
        yf = self._get_yfinance()
        results = {}

        tickers_str = " ".join(BDC_TICKERS.keys())

        try:
            # Fetch all BDC data at once
            data = yf.Tickers(tickers_str)

            for ticker, info in BDC_TICKERS.items():
                try:
                    stock = data.tickers[ticker]
                    stock_info = stock.info

                    price = (
                        stock_info.get("currentPrice")
                        or stock_info.get("regularMarketPrice", 0)
                    )
                    book_value = stock_info.get("bookValue")

                    # Calculate discount/premium
                    discount = None
                    if price and book_value and book_value > 0:
                        discount = ((price - book_value) / book_value) * 100

                    # Get 30-day price change
                    change_30d = self._get_30d_change(stock)

                    results[ticker] = BDCQuote(
                        ticker=ticker,
                        name=info["name"],
                        price=price or 0,
                        book_value_per_share=book_value,
                        discount_premium=discount,
                        change_30d_pct=change_30d,
                        timestamp=datetime.now(),
                    )

                except Exception as e:
                    logger.warning(f"Error fetching {ticker}: {e}")

        except Exception as e:
            logger.error(f"Error fetching BDC data: {e}")

        return results

    def get_leveraged_loan_etf_data(self) -> Dict[str, ETFQuote]:
        """
        Fetch leveraged loan ETF data.

        Returns:
            Dict mapping ticker to ETFQuote
        """
        yf = self._get_yfinance()
        results = {}

        tickers_str = " ".join(LEVERAGED_LOAN_ETFS.keys())

        try:
            data = yf.Tickers(tickers_str)

            for ticker, info in LEVERAGED_LOAN_ETFS.items():
                try:
                    stock = data.tickers[ticker]
                    stock_info = stock.info

                    price = (
                        stock_info.get("currentPrice")
                        or stock_info.get("regularMarketPrice", 0)
                    )
                    change_30d = self._get_30d_change(stock)

                    results[ticker] = ETFQuote(
                        ticker=ticker,
                        name=info["name"],
                        price=price or 0,
                        change_30d_pct=change_30d,
                        timestamp=datetime.now(),
                    )

                except Exception as e:
                    logger.warning(f"Error fetching {ticker}: {e}")

        except Exception as e:
            logger.error(f"Error fetching ETF data: {e}")

        return results

    def get_pe_firm_data(self) -> Dict[str, StockQuote]:
        """
        Fetch PE firm stock data.

        Returns:
            Dict mapping ticker to StockQuote
        """
        yf = self._get_yfinance()
        results = {}

        tickers_str = " ".join(PE_FIRM_TICKERS.keys())

        try:
            data = yf.Tickers(tickers_str)

            for ticker, info in PE_FIRM_TICKERS.items():
                try:
                    stock = data.tickers[ticker]
                    stock_info = stock.info

                    price = (
                        stock_info.get("currentPrice")
                        or stock_info.get("regularMarketPrice", 0)
                    )
                    change_30d = self._get_30d_change(stock)

                    results[ticker] = StockQuote(
                        ticker=ticker,
                        name=info["name"],
                        price=price or 0,
                        change_30d_pct=change_30d,
                        timestamp=datetime.now(),
                    )

                except Exception as e:
                    logger.warning(f"Error fetching {ticker}: {e}")

        except Exception as e:
            logger.error(f"Error fetching PE firm data: {e}")

        return results

    def _get_30d_change(self, stock) -> Optional[float]:
        """
        Calculate 30-day price change percentage.

        Args:
            stock: yfinance Ticker object

        Returns:
            Percentage change over 30 days, or None if unavailable
        """
        try:
            # Get 35 days of history to ensure we have 30 trading days
            hist = stock.history(period="35d")

            if len(hist) >= 2:
                start_price = hist["Close"].iloc[0]
                end_price = hist["Close"].iloc[-1]

                if start_price > 0:
                    return ((end_price - start_price) / start_price) * 100

        except Exception as e:
            logger.debug(f"Could not calculate 30d change: {e}")

        return None

    def get_all_private_credit_data(self) -> Dict:
        """
        Fetch all data needed for private credit stress monitoring.

        Returns:
            Dict with 'bdc', 'etf', 'pe' keys containing respective data
        """
        return {
            "bdc": self.get_bdc_data(),
            "etf": self.get_leveraged_loan_etf_data(),
            "pe": self.get_pe_firm_data(),
            "timestamp": datetime.now().isoformat(),
        }


def calculate_weighted_bdc_discount(bdc_data: Dict[str, BDCQuote]) -> Optional[float]:
    """
    Calculate weighted average BDC discount/premium.

    Args:
        bdc_data: Dict of BDC quotes

    Returns:
        Weighted average discount (negative) or premium (positive)
    """
    total_weight = 0
    weighted_sum = 0

    for ticker, quote in bdc_data.items():
        if quote.discount_premium is not None:
            weight = BDC_TICKERS.get(ticker, {}).get("weight", 0.2)
            weighted_sum += quote.discount_premium * weight
            total_weight += weight

    if total_weight > 0:
        return weighted_sum / total_weight

    return None


def format_bdc_report(bdc_data: Dict[str, BDCQuote]) -> str:
    """
    Format BDC data as a readable report.

    Args:
        bdc_data: Dict of BDC quotes

    Returns:
        Formatted string report
    """
    lines = ["BDC Price/NAV Report", "=" * 50]

    for ticker, quote in sorted(bdc_data.items()):
        discount_str = f"{quote.discount_premium:+.1f}%" if quote.discount_premium else "N/A"
        change_str = f"{quote.change_30d_pct:+.1f}%" if quote.change_30d_pct else "N/A"

        lines.append(
            f"{ticker:6} ${quote.price:7.2f} | "
            f"Book: ${quote.book_value_per_share or 0:7.2f} | "
            f"Disc: {discount_str:8} | "
            f"30d: {change_str:8}"
        )

    weighted = calculate_weighted_bdc_discount(bdc_data)
    if weighted:
        lines.append("-" * 50)
        lines.append(f"Weighted Avg Discount: {weighted:+.1f}%")

        # Interpretation
        if weighted < -20:
            lines.append("⚠️  SEVERE: Market pricing major credit losses")
        elif weighted < -10:
            lines.append("⚠️  ELEVATED: Private credit stress emerging")
        elif weighted < -5:
            lines.append("⚡ CAUTIOUS: Slight discount, monitoring")
        else:
            lines.append("✅ NORMAL: BDC sector healthy")

    return "\n".join(lines)

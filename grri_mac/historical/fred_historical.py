"""FRED Historical Data Client - Extended series for pre-1973 analysis.

This module fetches long-history FRED series that enable MAC analysis
back to 1945, when Flow of Funds data begins.

Key Series and Their History:
-----------------------------
BOGZ1FL663067003Q - Margin Loans (Q4 1945+)
NCBEILQ027S       - Corporate Equity Market Value (Q4 1945+)
BAA               - Moody's Baa Corporate Yield (1919+)
AAA               - Moody's Aaa Corporate Yield (1919+)
GS10              - 10-Year Treasury (1953+, monthly; 1962+ daily)
TB3MS             - 3-Month T-Bill (1934+)
FEDFUNDS          - Fed Funds Rate (1954+)
DISCOUNT          - Fed Discount Rate (1914+)
SP500             - S&P 500 Index (1957+, for realized vol)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import requests

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Historical FRED series - all with long history
HISTORICAL_SERIES = {
    # Positioning / Leverage (both start Q4 1945)
    "MARGIN_DEBT": "BOGZ1FL663067003Q",  # Broker-dealer margin loans
    "MARKET_CAP": "NCBEILQ027S",          # Corporate equities market value
    
    # Credit Stress (both start 1919!)
    "BAA_YIELD": "BAA",                   # Moody's Baa (lower quality IG)
    "AAA_YIELD": "AAA",                   # Moody's Aaa (highest quality)
    
    # Interest Rates
    "TREASURY_10Y": "GS10",               # 10Y Treasury (1953+)
    "TREASURY_3M": "TB3MS",               # 3M T-Bill (1934+)
    "FED_FUNDS": "FEDFUNDS",              # Fed Funds (1954+)
    "DISCOUNT_RATE": "DISCOUNT",          # Discount Rate (1914+)
    
    # For realized volatility calculation
    "SP500": "SP500",                     # S&P 500 (1957+)
    
    # Additional context
    "GDP": "GDP",                         # GDP for normalization (1947+)
    "CPI": "CPIAUCSL",                    # CPI for real returns (1947+)
    "UNRATE": "UNRATE",                   # Unemployment (1948+)
}


class FREDHistoricalClient:
    """Client for fetching long-history FRED data."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self._cache: Dict[str, List[dict]] = {}
        
    def get_series(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Fetch complete time series from FRED.
        
        Args:
            series_id: FRED series identifier
            start_date: Start of range (default: earliest available)
            end_date: End of range (default: latest available)
            
        Returns:
            List of {date, value} observations
        """
        if not self.api_key:
            logger.warning("FRED_API_KEY not set")
            return []
            
        cache_key = f"{series_id}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "asc",
        }
        
        if start_date:
            params["observation_start"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["observation_end"] = end_date.strftime("%Y-%m-%d")
            
        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            observations = data.get("observations", [])
            
            # Parse and clean
            result = []
            for obs in observations:
                if obs.get("value") and obs["value"] != ".":
                    try:
                        result.append({
                            "date": obs["date"],
                            "value": float(obs["value"])
                        })
                    except (ValueError, KeyError):
                        continue
                        
            self._cache[cache_key] = result
            logger.info(f"Fetched {len(result)} observations for {series_id}")
            return result
            
        except Exception as e:
            logger.error(f"FRED API error for {series_id}: {e}")
            return []
    
    def get_margin_debt_ratio(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Calculate margin debt as percentage of market cap.
        
        This is the key positioning indicator for historical analysis.
        Higher values = more leverage = more risk.
        
        Returns:
            List of {date, margin_debt, market_cap, ratio_pct} observations
        """
        margin = self.get_series(
            HISTORICAL_SERIES["MARGIN_DEBT"],
            start_date, end_date
        )
        market_cap = self.get_series(
            HISTORICAL_SERIES["MARKET_CAP"],
            start_date, end_date
        )
        
        if not margin or not market_cap:
            return []
            
        # Create lookup by date
        cap_lookup = {m["date"]: m["value"] for m in market_cap}
        
        result = []
        for m in margin:
            date = m["date"]
            if date in cap_lookup and cap_lookup[date] > 0:
                ratio = (m["value"] / cap_lookup[date]) * 100
                result.append({
                    "date": date,
                    "margin_debt_millions": m["value"],
                    "market_cap_millions": cap_lookup[date],
                    "ratio_pct": round(ratio, 4)
                })
                
        return result
    
    def get_credit_spread(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Calculate BAA-AAA credit spread (credit stress indicator).
        
        Higher spread = more credit stress = flight to quality.
        
        Returns:
            List of {date, baa_yield, aaa_yield, spread_pct} observations
        """
        baa = self.get_series(HISTORICAL_SERIES["BAA_YIELD"], start_date, end_date)
        aaa = self.get_series(HISTORICAL_SERIES["AAA_YIELD"], start_date, end_date)
        
        if not baa or not aaa:
            return []
            
        aaa_lookup = {a["date"]: a["value"] for a in aaa}
        
        result = []
        for b in baa:
            date = b["date"]
            if date in aaa_lookup:
                spread = b["value"] - aaa_lookup[date]
                result.append({
                    "date": date,
                    "baa_yield": b["value"],
                    "aaa_yield": aaa_lookup[date],
                    "spread_pct": round(spread, 4)
                })
                
        return result
    
    def get_yield_curve(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Calculate yield curve slope (10Y - 3M).
        
        Inverted curve (negative) historically precedes recessions.
        
        Returns:
            List of {date, treasury_10y, treasury_3m, slope_pct} observations
        """
        t10y = self.get_series(HISTORICAL_SERIES["TREASURY_10Y"], start_date, end_date)
        t3m = self.get_series(HISTORICAL_SERIES["TREASURY_3M"], start_date, end_date)
        
        if not t10y or not t3m:
            return []
            
        t3m_lookup = {t["date"]: t["value"] for t in t3m}
        
        result = []
        for t in t10y:
            date = t["date"]
            if date in t3m_lookup:
                slope = t["value"] - t3m_lookup[date]
                result.append({
                    "date": date,
                    "treasury_10y": t["value"],
                    "treasury_3m": t3m_lookup[date],
                    "slope_pct": round(slope, 4)
                })
                
        return result
    
    def get_policy_rate(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Get policy rate (Fed Funds or Discount Rate for earlier periods).
        
        Returns:
            List of {date, rate, source} observations
        """
        # Try Fed Funds first (more relevant, 1954+)
        fed_funds = self.get_series(HISTORICAL_SERIES["FED_FUNDS"], start_date, end_date)
        
        # Fall back to discount rate for earlier periods
        discount = self.get_series(HISTORICAL_SERIES["DISCOUNT_RATE"], start_date, end_date)
        
        ff_lookup = {f["date"]: f["value"] for f in fed_funds}
        
        result = []
        for d in discount:
            date = d["date"]
            if date in ff_lookup:
                result.append({
                    "date": date,
                    "rate": ff_lookup[date],
                    "source": "FEDFUNDS"
                })
            else:
                result.append({
                    "date": date,
                    "rate": d["value"],
                    "source": "DISCOUNT"
                })
                
        return result
    
    def get_realized_volatility(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        window_days: int = 21,
    ) -> List[dict]:
        """Calculate realized volatility from S&P 500 returns.
        
        For periods before VIX (pre-1990), we must calculate volatility
        from actual price movements.
        
        Args:
            window_days: Rolling window for volatility calculation
            
        Returns:
            List of {date, realized_vol_annualized} observations
        """
        sp500 = self.get_series(HISTORICAL_SERIES["SP500"], start_date, end_date)
        
        if len(sp500) < window_days + 1:
            return []
            
        # Calculate daily returns
        returns = []
        for i in range(1, len(sp500)):
            prev_val = sp500[i-1]["value"]
            curr_val = sp500[i]["value"]
            if prev_val > 0:
                ret = (curr_val - prev_val) / prev_val
                returns.append({
                    "date": sp500[i]["date"],
                    "return": ret
                })
        
        # Calculate rolling volatility
        result = []
        for i in range(window_days, len(returns)):
            window = returns[i-window_days:i]
            window_returns = [r["return"] for r in window]
            
            # Standard deviation of returns
            mean_ret = sum(window_returns) / len(window_returns)
            variance = sum((r - mean_ret) ** 2 for r in window_returns) / len(window_returns)
            daily_vol = variance ** 0.5
            
            # Annualize (252 trading days)
            annual_vol = daily_vol * (252 ** 0.5) * 100
            
            result.append({
                "date": returns[i]["date"],
                "realized_vol_annualized": round(annual_vol, 2)
            })
            
        return result
    
    def get_all_historical_indicators(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, List[dict]]:
        """Fetch all historical indicators for MAC analysis.
        
        Returns:
            Dictionary with all indicator time series
        """
        return {
            "margin_debt_ratio": self.get_margin_debt_ratio(start_date, end_date),
            "credit_spread": self.get_credit_spread(start_date, end_date),
            "yield_curve": self.get_yield_curve(start_date, end_date),
            "policy_rate": self.get_policy_rate(start_date, end_date),
            "realized_volatility": self.get_realized_volatility(start_date, end_date),
        }


def get_data_availability() -> Dict[str, Dict]:
    """Document data availability for each series."""
    return {
        "MARGIN_DEBT": {
            "series_id": "BOGZ1FL663067003Q",
            "start": "1945-Q4",
            "frequency": "Quarterly",
            "description": "Broker-dealer margin loans to customers"
        },
        "MARKET_CAP": {
            "series_id": "NCBEILQ027S",
            "start": "1945-Q4", 
            "frequency": "Quarterly",
            "description": "Total corporate equities market value"
        },
        "BAA_YIELD": {
            "series_id": "BAA",
            "start": "1919-01",
            "frequency": "Monthly",
            "description": "Moody's Baa corporate bond yield"
        },
        "AAA_YIELD": {
            "series_id": "AAA",
            "start": "1919-01",
            "frequency": "Monthly", 
            "description": "Moody's Aaa corporate bond yield"
        },
        "TREASURY_10Y": {
            "series_id": "GS10",
            "start": "1953-04",
            "frequency": "Monthly",
            "description": "10-Year Treasury constant maturity"
        },
        "TREASURY_3M": {
            "series_id": "TB3MS",
            "start": "1934-01",
            "frequency": "Monthly",
            "description": "3-Month Treasury bill rate"
        },
        "FED_FUNDS": {
            "series_id": "FEDFUNDS",
            "start": "1954-07",
            "frequency": "Monthly",
            "description": "Effective federal funds rate"
        },
        "DISCOUNT_RATE": {
            "series_id": "DISCOUNT",
            "start": "1914-11",
            "frequency": "Monthly",
            "description": "Federal Reserve discount rate"
        },
        "SP500": {
            "series_id": "SP500",
            "start": "1957-01",
            "frequency": "Daily",
            "description": "S&P 500 index level"
        },
    }

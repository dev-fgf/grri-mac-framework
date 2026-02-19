"""Historical data sources for 1907-1954 backtest extension.

Provides data loaders for pre-FRED era data:
- NBER Macrohistory Database (interest rates, gold stocks, from 1890)
- Shiller CAPE/equity/CPI dataset (from 1871)
- Schwert (1989) stock volatility series (from 1802)
- Bank of England Research Database (GBP/USD from 1791, Bank Rate from 1694)
- MeasuringWorth GDP series (from 1790)
- FINRA/NYSE margin debt (from 1918)

Data files are expected in data/historical/ directory as CSV/Excel.
Run download_historical_data.py to fetch publicly available datasets.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Base directory for historical data files
HISTORICAL_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "historical"


# =============================================================================
# NBER Macrohistory Database Loader
# Series from Chapter 13 (Interest Rates) and Chapter 14 (Money & Banking)
# URL: https://www.nber.org/research/data/nber-macrohistory-database
# =============================================================================

NBER_SERIES = {
    # Chapter 13: Interest Rates
    "m13001": {
        "name": "Call Money Rate",
        "start": 1890,
        "freq": "monthly",
        "description": "New York call money rate (broker loans)",
    },
    "m13039": {
        "name": "Commercial Paper Rate",
        "start": 1890,
        "freq": "monthly",
        "description": "4-6 month prime commercial paper rate",
    },
    "m13041": {
        "name": "Short-Term Govt Rate",
        "start": 1890,
        "freq": "monthly",
        "description": "Short-term US government bond yield",
    },
    "m13020": {
        "name": "Railroad Bond Yield (High Grade)",
        "start": 1857,
        "freq": "monthly",
        "description": "High-grade railroad bond yields (pre-Moody's corporate proxy)",
    },
    "m13028": {
        "name": "Railroad Bond Yield (Lower Grade)",
        "start": 1857,
        "freq": "monthly",
        "description": "Lower-grade railroad bond yields",
    },
    "m13033": {
        "name": "US Govt Bond Yield (Long-Term)",
        "start": 1857,
        "freq": "monthly",
        "description": "US government long-term bond yield",
    },
    "m13034": {
        "name": "US Govt Bond Yield (Short-Term)",
        "start": 1857,
        "freq": "monthly",
        "description": "US government short-term bond yield",
    },
    # Chapter 14: Money and Banking
    "m14076": {
        "name": "US Gold Stock",
        "start": 1878,
        "freq": "monthly",
        "description": "US Treasury gold stock (monetary gold)",
    },
}


def load_nber_series(series_id: str) -> Optional[pd.Series]:
    """
    Load an NBER Macrohistory series from local CSV file.

    Expected file format: CSV with columns 'date' and 'value'.
    Files should be placed in data/historical/nber/

    Args:
        series_id: NBER series identifier (e.g., 'm13001')

    Returns:
        pandas Series indexed by datetime, or None if file not found
    """
    nber_dir = HISTORICAL_DATA_DIR / "nber"
    filepath = nber_dir / f"{series_id}.csv"

    if not filepath.exists():
        logger.warning(f"NBER series {series_id} not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
        series = pd.Series(df["value"].values, index=df["date"])
        series = series.dropna().sort_index()
        logger.info(
            f"Loaded NBER {series_id}: {len(series)} obs, "
            f"{series.index[0].date()} to {series.index[-1].date()}"
        )
        return series
    except Exception as e:
        logger.error(f"Error loading NBER {series_id}: {e}")
        return None


# =============================================================================
# Shiller Dataset Loader
# Robert Shiller's "Irrational Exuberance" dataset
# Contains: S&P Composite, Earnings, CPI, GS10, CAPE from 1871
# URL: http://www.econ.yale.edu/~shiller/data.htm
# =============================================================================

def load_shiller_dataset() -> Optional[pd.DataFrame]:
    """
    Load Shiller's U.S. Stock Markets dataset.

    Expected file: data/historical/shiller/ie_data.csv
    (Converted from Excel, or downloaded as CSV)

    Returns DataFrame with columns:
        - price: S&P Composite Price
        - dividend: Dividends
        - earnings: Earnings
        - cpi: Consumer Price Index
        - gs10: Long-term interest rate (10Y equivalent)
        - cape: Cyclically Adjusted P/E ratio
        - earnings_yield: 1/CAPE
    """
    shiller_dir = HISTORICAL_DATA_DIR / "shiller"

    # Try CSV first, then Excel
    csv_path = shiller_dir / "ie_data.csv"
    xls_path = shiller_dir / "ie_data.xls"
    xlsx_path = shiller_dir / "ie_data.xlsx"

    df = None
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Error reading Shiller CSV: {e}")
    elif xls_path.exists() or xlsx_path.exists():
        path = xls_path if xls_path.exists() else xlsx_path
        try:
            df = pd.read_excel(path, sheet_name="Data", skiprows=7)
        except Exception as e:
            logger.error(f"Error reading Shiller Excel: {e}")

    if df is None:
        logger.warning("Shiller dataset not found in data/historical/shiller/")
        return None

    try:
        # Standardise column names (Shiller format varies)
        df.columns = [c.strip().lower() for c in df.columns]  # type: ignore[assignment]

        # Parse the fractional year date column (e.g., 1871.01 = Jan 1871)
        if "date" in df.columns:
            date_col = "date"
        else:
            date_col = df.columns[0]

        dates: list[Any] = []
        for val in df[date_col]:
            try:
                year = int(val)
                month = round((val - year) * 12) + 1
                month = max(1, min(12, month))
                dates.append(datetime(year, month, 1))
            except (ValueError, TypeError):
                dates.append(pd.NaT)

        df.index = pd.DatetimeIndex(dates)
        df = df.dropna(subset=[df.columns[1]])  # Drop rows where price is NaN

        # Rename to standard columns
        col_map = {}
        for c in df.columns:
            cl = c.lower().strip()
            if cl in ("p", "price", "real price"):
                col_map[c] = "price"
            elif cl in ("d", "dividend", "dividends"):
                col_map[c] = "dividend"
            elif cl in ("e", "earnings"):
                col_map[c] = "earnings"
            elif cl in ("cpi",):
                col_map[c] = "cpi"
            elif cl in ("rate gs10", "rate_gs10", "gs10", "long interest rate"):
                col_map[c] = "gs10"
            elif cl in ("cape", "cape ratio", "p/e10", "cyclically adjusted p/e"):
                col_map[c] = "cape"

        df = df.rename(columns=col_map)

        # Calculate earnings yield
        if "cape" in df.columns:
            df["earnings_yield"] = 1.0 / df["cape"].replace(0, np.nan)

        logger.info(
            f"Loaded Shiller dataset: {len(df)} months, "
            f"{df.index[0].date()} to {df.index[-1].date()}"
        )
        return df

    except Exception as e:
        logger.error(f"Error processing Shiller dataset: {e}")
        return None


def get_shiller_equity_prices() -> Optional[pd.Series]:
    """Get S&P Composite monthly prices from Shiller (1871+)."""
    df = load_shiller_dataset()
    if df is not None and "price" in df.columns:
        return df["price"].dropna()
    return None


def get_shiller_long_rate() -> Optional[pd.Series]:
    """Get long-term interest rate from Shiller (1871+)."""
    df = load_shiller_dataset()
    if df is not None and "gs10" in df.columns:
        return df["gs10"].dropna()
    return None


def get_shiller_cpi() -> Optional[pd.Series]:
    """Get CPI from Shiller (1871+)."""
    df = load_shiller_dataset()
    if df is not None and "cpi" in df.columns:
        return df["cpi"].dropna()
    return None


def get_shiller_cape() -> Optional[pd.Series]:
    """Get CAPE ratio from Shiller (1871+)."""
    df = load_shiller_dataset()
    if df is not None and "cape" in df.columns:
        return df["cape"].dropna()
    return None


# =============================================================================
# Schwert (1989) Volatility Series
# Monthly US stock return volatility, 1802-1987
# Source: Journal of Finance 44(5), 1989, pp. 1115-1153
# Data: http://schwert.ssb.rochester.edu/volatility.htm
# =============================================================================

def load_schwert_volatility() -> Optional[pd.Series]:
    """
    Load Schwert's monthly stock return volatility series.

    Expected file: data/historical/schwert/schwert_volatility.csv
    Format: CSV with columns 'date' and 'volatility' (annualised %)

    For VIX-equivalent conversion, apply 1.3x variance risk premium multiplier.
    Reference: Schwert's 1907 reading ~45% annualised → VIX-equiv ~58.

    Returns:
        pandas Series of monthly annualised volatility (%)
    """
    schwert_dir = HISTORICAL_DATA_DIR / "schwert"
    filepath = schwert_dir / "schwert_volatility.csv"

    if not filepath.exists():
        logger.warning(f"Schwert volatility data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
        series = pd.Series(df["volatility"].values, index=df["date"])
        series = series.dropna().sort_index()
        logger.info(
            f"Loaded Schwert volatility: {len(series)} months, "
            f"{series.index[0].date()} to {series.index[-1].date()}"
        )
        return series
    except Exception as e:
        logger.error(f"Error loading Schwert volatility: {e}")
        return None


def get_vix_equivalent_from_schwert(date: datetime) -> Optional[float]:
    """
    Get VIX-equivalent volatility for a pre-1928 date using Schwert data.

    Applies 1.3x variance risk premium multiplier to convert
    realised volatility to implied volatility equivalent.

    Args:
        date: Target date

    Returns:
        VIX-equivalent level, or None if data unavailable
    """
    schwert = load_schwert_volatility()
    if schwert is None:
        return None

    # Find nearest date (monthly data)
    mask = schwert.index <= pd.Timestamp(date)
    if not mask.any():
        return None

    nearest_val = schwert[mask].iloc[-1]
    # Apply variance risk premium: VIX ≈ 1.3 × realised vol
    return nearest_val * 1.3


# =============================================================================
# Bank of England Research Database
# "A millennium of macroeconomic data" spreadsheet
# Contains: GBP/USD exchange rate (daily, 1791+), Bank Rate (1694+)
# URL: https://www.bankofengland.co.uk/statistics/research-datasets
# =============================================================================

def load_boe_exchange_rate() -> Optional[pd.Series]:
    """
    Load GBP/USD exchange rate from Bank of England research dataset.

    Expected file: data/historical/boe/gbp_usd.csv
    Format: CSV with columns 'date' and 'rate'

    For gold standard era, deviations >2% from official parity indicate
    cross-border funding stress.
    """
    boe_dir = HISTORICAL_DATA_DIR / "boe"
    filepath = boe_dir / "gbp_usd.csv"

    if not filepath.exists():
        logger.warning(f"BoE exchange rate not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
        series = pd.Series(df["rate"].values, index=df["date"])
        series = series.dropna().sort_index()
        logger.info(f"Loaded BoE GBP/USD: {len(series)} obs")
        return series
    except Exception as e:
        logger.error(f"Error loading BoE exchange rate: {e}")
        return None


def load_boe_bank_rate() -> Optional[pd.Series]:
    """
    Load Bank of England official Bank Rate (1694+).

    Expected file: data/historical/boe/bank_rate.csv
    """
    boe_dir = HISTORICAL_DATA_DIR / "boe"
    filepath = boe_dir / "bank_rate.csv"

    if not filepath.exists():
        logger.warning(f"BoE Bank Rate not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
        series = pd.Series(df["rate"].values, index=df["date"])
        series = series.dropna().sort_index()
        logger.info(f"Loaded BoE Bank Rate: {len(series)} obs")
        return series
    except Exception as e:
        logger.error(f"Error loading BoE Bank Rate: {e}")
        return None


# =============================================================================
# MeasuringWorth GDP Series
# Annual US GDP from 1790
# URL: https://www.measuringworth.com/datasets/usgdp/
# =============================================================================

def load_measuringworth_gdp() -> Optional[pd.Series]:
    """
    Load annual US GDP from MeasuringWorth (1790+).

    Expected file: data/historical/measuringworth/us_gdp.csv
    Format: CSV with columns 'year' and 'gdp' (nominal, billions)
    """
    mw_dir = HISTORICAL_DATA_DIR / "measuringworth"
    filepath = mw_dir / "us_gdp.csv"

    if not filepath.exists():
        logger.warning(f"MeasuringWorth GDP not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath)
        dates = [datetime(int(y), 1, 1) for y in df["year"]]
        series = pd.Series(df["gdp"].values, index=dates)
        series = series.dropna().sort_index()
        logger.info(f"Loaded MeasuringWorth GDP: {len(series)} years")
        return series
    except Exception as e:
        logger.error(f"Error loading MeasuringWorth GDP: {e}")
        return None


# =============================================================================
# FINRA / NYSE Margin Debt
# Monthly margin debt from 1918 (NYSE reports) / 1959 (FINRA)
# URL: https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics
# =============================================================================

def load_margin_debt() -> Optional[pd.Series]:
    """
    Load NYSE margin debt series.

    Expected file: data/historical/finra/margin_debt.csv
    Format: CSV with columns 'date' and 'margin_debt' (millions USD)
    """
    finra_dir = HISTORICAL_DATA_DIR / "finra"
    filepath = finra_dir / "margin_debt.csv"

    if not filepath.exists():
        logger.warning(f"FINRA margin debt not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
        series = pd.Series(df["margin_debt"].values, index=df["date"])
        series = series.dropna().sort_index()
        logger.info(f"Loaded margin debt: {len(series)} months")
        return series
    except Exception as e:
        logger.error(f"Error loading margin debt: {e}")
        return None


# =============================================================================
# Composite Historical Data Provider
# Unified interface for all historical sources
# =============================================================================

class HistoricalDataProvider:
    """
    Unified provider for pre-1954 historical data.

    Loads and caches data from NBER, Shiller, Schwert, BoE, and
    MeasuringWorth sources. Provides proxy chain resolution for
    each MAC pillar indicator.
    """

    def __init__(self):
        """Initialize and lazy-load data sources."""
        self._cache: Dict[str, pd.Series] = {}
        self._shiller_df: Optional[pd.DataFrame] = None

    def _get_or_load(self, key: str, loader) -> Optional[pd.Series]:
        """Cache-aware loader."""
        if key not in self._cache:
            result = loader()
            if result is not None:
                self._cache[key] = result
        return self._cache.get(key)

    @property
    def shiller(self) -> Optional[pd.DataFrame]:
        """Lazy-load Shiller dataset."""
        if self._shiller_df is None:
            self._shiller_df = load_shiller_dataset()
        return self._shiller_df

    # --- Liquidity Pillar Proxies ---

    def get_call_money_rate(self, date: datetime) -> Optional[float]:
        """
        Get call money rate for pre-1954 liquidity proxy.

        Call money rate was the overnight lending rate for broker loans,
        functionally equivalent to the repo rate / fed funds rate.
        Available from 1890 via NBER m13001.
        """
        series = self._get_or_load("call_money", lambda: load_nber_series("m13001"))
        return self._lookup(series, date, lookback_days=35)

    def get_commercial_paper_rate(self, date: datetime) -> Optional[float]:
        """Get commercial paper rate (NBER m13039, 1890+)."""
        series = self._get_or_load("cp_rate", lambda: load_nber_series("m13039"))
        return self._lookup(series, date, lookback_days=35)

    def get_short_term_govt_rate(self, date: datetime) -> Optional[float]:
        """Get short-term government bond rate (NBER m13041, 1890+)."""
        series = self._get_or_load("govt_short", lambda: load_nber_series("m13041"))
        return self._lookup(series, date, lookback_days=35)

    def get_funding_stress_spread(self, date: datetime) -> Optional[float]:
        """
        Get funding stress spread for pre-1954 dates in basis points.

        Proxy: Call Money Rate - Short-Term Govt Rate
        This measures the premium for short-term bank/broker funding
        vs risk-free rate, analogous to TED spread / SOFR-IORB spread.
        """
        call_rate = self.get_call_money_rate(date)
        govt_rate = self.get_short_term_govt_rate(date)
        if call_rate is not None and govt_rate is not None:
            return (call_rate - govt_rate) * 100  # Convert to bps
        return None

    def get_cp_spread(self, date: datetime) -> Optional[float]:
        """
        Get CP-Treasury spread for pre-1954 dates in basis points.

        Proxy: Commercial Paper Rate - Short-Term Govt Rate
        """
        cp_rate = self.get_commercial_paper_rate(date)
        govt_rate = self.get_short_term_govt_rate(date)
        if cp_rate is not None and govt_rate is not None:
            return (cp_rate - govt_rate) * 100  # Convert to bps
        return None

    # --- Valuation Pillar Proxies ---

    def get_credit_spread(self, date: datetime) -> Optional[float]:
        """
        Get corporate-government credit spread for pre-1919 dates in bps.

        Proxy: Railroad bond yield - Government bond yield
        Railroad bonds were the dominant corporate credit instrument pre-1919.
        Per Hickman (1958), default rates comparable to modern BBB.
        """
        rr_yield = self._get_or_load("rr_high", lambda: load_nber_series("m13020"))
        govt_yield = self._get_or_load("govt_long", lambda: load_nber_series("m13033"))

        rr = self._lookup(rr_yield, date, lookback_days=35)
        govt = self._lookup(govt_yield, date, lookback_days=35)

        if rr is not None and govt is not None:
            return (rr - govt) * 100  # Convert to bps
        return None

    def get_hy_oas_proxy(self, date: datetime) -> Optional[float]:
        """
        Get HY OAS equivalent for pre-1919 dates.

        Railroad spread × 3.5-4.0 ≈ HY OAS equivalent.
        Per Hickman (1958) and Homer & Sylla (2005).
        """
        credit_spread = self.get_credit_spread(date)
        if credit_spread is not None:
            return credit_spread * 3.75  # Midpoint of 3.5-4.0 scaling
        return None

    def get_ig_oas_proxy(self, date: datetime) -> Optional[float]:
        """
        Get IG OAS equivalent for pre-1919 dates.

        Railroad high-grade spread ≈ IG OAS (direct).
        """
        return self.get_credit_spread(date)

    def get_long_term_govt_yield(self, date: datetime) -> Optional[float]:
        """Get long-term government bond yield (from Shiller or NBER)."""
        # Try Shiller first (available from 1871)
        if self.shiller is not None and "gs10" in self.shiller.columns:
            val = self._lookup_df(self.shiller, "gs10", date, lookback_days=35)
            if val is not None:
                return val

        # Fallback to NBER
        series = self._get_or_load("govt_long", lambda: load_nber_series("m13033"))
        return self._lookup(series, date, lookback_days=35)

    def get_equity_risk_premium(self, date: datetime) -> Optional[float]:
        """
        Get equity risk premium from Shiller CAPE (1871+).

        ERP = (1 / CAPE) - GS10 / 100
        """
        if self.shiller is None:
            return None

        cape = self._lookup_df(self.shiller, "cape", date, lookback_days=35)
        gs10 = self._lookup_df(self.shiller, "gs10", date, lookback_days=35)

        if cape is not None and gs10 is not None and cape > 0:
            return (1.0 / cape) - (gs10 / 100)
        return None

    # --- Volatility Pillar Proxies ---

    def get_vix_proxy(self, date: datetime) -> Optional[float]:
        """
        Get VIX-equivalent volatility for any pre-1928 date.

        Uses Schwert (1989) monthly volatility × 1.3 VRP multiplier.
        For pre-1802 dates (before Schwert), returns None.
        """
        return get_vix_equivalent_from_schwert(date)

    def get_realised_vol_from_shiller(self, date: datetime, window: int = 12) -> Optional[float]:
        """
        Compute realised volatility from Shiller monthly equity prices.

        Args:
            date: Target date
            window: Number of months for rolling window

        Returns:
            Annualised volatility (%), or None
        """
        if self.shiller is None or "price" not in self.shiller.columns:
            return None

        prices = self.shiller["price"].dropna()
        mask = prices.index <= pd.Timestamp(date)
        if mask.sum() < window + 1:
            return None

        subset = prices[mask].tail(window + 1)
        returns = subset.pct_change().dropna()
        if len(returns) < window // 2:
            return None

        monthly_vol = returns.std()
        annual_vol = monthly_vol * np.sqrt(12) * 100
        return annual_vol

    # --- Policy Pillar Proxies ---

    def get_discount_rate(self, date: datetime) -> Optional[float]:
        """
        Get Fed discount rate for 1913-1954.

        The discount rate was the primary policy instrument before
        active use of open market operations (post-1930s).
        Available from FRED INTDSRUSM193N (1913+).
        """
        # This should be fetched via FRED, but we provide NBER fallback
        return None  # Handled by FREDClient with INTDSRUSM193N

    def get_gold_reserve_ratio(self, date: datetime) -> Optional[float]:
        """
        Get gold reserve ratio for pre-Fed policy capacity (1878+).

        Gold Reserve Ratio = Gold Stock / (estimated monetary base)
        Ratio below 40% indicates constrained policy capacity.

        Per Friedman & Schwartz (1963), the gold constraint was the
        binding policy limitation during 1907 and other pre-Fed crises.
        """
        gold = self._get_or_load("gold_stock", lambda: load_nber_series("m14076"))
        gold_val = self._lookup(gold, date, lookback_days=35)

        if gold_val is None:
            return None

        # Estimate monetary base from GDP proxy
        gdp_series = self._get_or_load("mw_gdp", load_measuringworth_gdp)
        if gdp_series is not None:
            gdp_val = self._lookup(gdp_series, date, lookback_days=400)  # Annual data
            if gdp_val is not None and gdp_val > 0:
                # Rough proxy: monetary base ≈ 10-15% of GDP in gold standard era
                est_base = gdp_val * 0.12
                return (gold_val / est_base) * 100 if est_base > 0 else None

        return None

    # --- Contagion Pillar Proxies ---

    def get_gbp_usd_deviation(self, date: datetime) -> Optional[float]:
        """
        Get GBP/USD deviation from gold parity for pre-1973 contagion proxy.

        Under the gold standard, the official parity was ~$4.86/£.
        Deviations >2% indicate cross-border funding stress.
        Under Bretton Woods (1944-1971), parity was $2.80/£ until 1967,
        then $2.40/£.

        Returns: Deviation from parity in percentage points
        """
        gbp = self._get_or_load("gbp_usd", load_boe_exchange_rate)
        if gbp is None:
            return None

        rate = self._lookup(gbp, date, lookback_days=35)
        if rate is None:
            return None

        # Determine parity based on era
        if date < datetime(1914, 8, 1):
            parity = 4.8665  # Classical gold standard
        elif date < datetime(1925, 4, 28):
            parity = 4.8665  # Suspended but same reference
        elif date < datetime(1931, 9, 21):
            parity = 4.8665  # Restored gold standard
        elif date < datetime(1944, 7, 22):
            parity = None  # Floating
        elif date < datetime(1967, 11, 18):
            parity = 2.80  # Bretton Woods
        elif date < datetime(1971, 8, 15):
            parity = 2.40  # Post-devaluation
        else:
            parity = None  # Floating

        if parity is None:
            return None

        deviation_pct = abs(rate - parity) / parity * 100
        return deviation_pct

    def get_london_bank_rate(self, date: datetime) -> Optional[float]:
        """Get Bank of England Bank Rate (1694+)."""
        bank_rate = self._get_or_load("boe_rate", load_boe_bank_rate)
        return self._lookup(bank_rate, date, lookback_days=35)

    # --- Positioning Pillar Proxies ---

    def get_margin_debt_to_gdp(self, date: datetime) -> Optional[float]:
        """
        Get margin debt / GDP ratio for pre-1986 leverage proxy.

        NYSE margin debt provides qualitative context for 1929 era
        but is not directly comparable to modern basis trade dynamics.
        Available from 1918.

        Returns: Margin debt as % of GDP, or None
        """
        margin = self._get_or_load("margin_debt", load_margin_debt)
        gdp = self._get_or_load("mw_gdp", load_measuringworth_gdp)

        if margin is None or gdp is None:
            return None

        margin_val = self._lookup(margin, date, lookback_days=35)
        gdp_val = self._lookup(gdp, date, lookback_days=400)

        if margin_val is not None and gdp_val is not None and gdp_val > 0:
            # margin_debt in millions, GDP in billions
            return (margin_val / 1e6) / gdp_val * 100
        return None

    # --- Helper Methods ---

    def _lookup(
        self,
        series: Optional[pd.Series],
        date: datetime,
        lookback_days: int = 35,
    ) -> Optional[float]:
        """Look up value for a date with forward-fill."""
        if series is None or len(series) == 0:
            return None

        ts = pd.Timestamp(date)
        start = ts - pd.Timedelta(days=lookback_days)
        mask = (series.index >= start) & (series.index <= ts)
        filtered = series[mask]

        if filtered.empty:
            return None

        return float(filtered.iloc[-1])

    def _lookup_df(
        self,
        df: pd.DataFrame,
        column: str,
        date: datetime,
        lookback_days: int = 35,
    ) -> Optional[float]:
        """Look up value in a DataFrame column for a date."""
        if df is None or column not in df.columns:
            return None

        series = df[column].dropna()
        return self._lookup(series, date, lookback_days)

    def get_data_availability_summary(self) -> Dict[str, Dict]:
        """
        Report which historical data sources are available on disk.

        Returns dict of {source_name: {available, path, series_count}}.
        """
        summary = {}

        # NBER
        nber_dir = HISTORICAL_DATA_DIR / "nber"
        nber_files = list(nber_dir.glob("m*.csv")) if nber_dir.exists() else []
        summary["nber"] = {
            "available": len(nber_files) > 0,
            "path": str(nber_dir),
            "series_count": len(nber_files),
            "required": list(NBER_SERIES.keys()),
        }

        # Shiller
        shiller_dir = HISTORICAL_DATA_DIR / "shiller"
        shiller_exists = (
            (shiller_dir / "ie_data.csv").exists() or
            (shiller_dir / "ie_data.xls").exists() or
            (shiller_dir / "ie_data.xlsx").exists()
        )
        summary["shiller"] = {
            "available": shiller_exists,
            "path": str(shiller_dir),
        }

        # Schwert
        schwert_dir = HISTORICAL_DATA_DIR / "schwert"
        summary["schwert"] = {
            "available": (schwert_dir / "schwert_volatility.csv").exists(),
            "path": str(schwert_dir),
        }

        # BoE
        boe_dir = HISTORICAL_DATA_DIR / "boe"
        summary["boe"] = {
            "available": (boe_dir / "gbp_usd.csv").exists() or (boe_dir / "bank_rate.csv").exists(),
            "path": str(boe_dir),
        }

        # MeasuringWorth
        mw_dir = HISTORICAL_DATA_DIR / "measuringworth"
        summary["measuringworth"] = {
            "available": (mw_dir / "us_gdp.csv").exists(),
            "path": str(mw_dir),
        }

        # FINRA
        finra_dir = HISTORICAL_DATA_DIR / "finra"
        summary["finra"] = {
            "available": (finra_dir / "margin_debt.csv").exists(),
            "path": str(finra_dir),
        }

        return summary

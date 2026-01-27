"""CFTC Commitments of Traders (COT) data parser using cot-reports package."""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Try to import cot_reports
try:
    from cot_reports.cot_reports import cot_year, cot_all
    COT_REPORTS_AVAILABLE = True
except ImportError:
    COT_REPORTS_AVAILABLE = False
    logger.warning("cot-reports not installed - run: pip install cot-reports")


class CFTCClient:
    """Client for fetching CFTC Commitments of Traders data."""

    # Treasury futures market names as they appear in COT reports (cot-reports format)
    TREASURY_CONTRACTS = {
        "2Y": "UST 2Y NOTE",
        "5Y": "UST 5Y NOTE",
        "10Y": "UST 10Y NOTE",
        "30Y": "UST BOND",
        "ULTRA": "ULTRA UST BOND",
    }

    def __init__(self):
        """Initialize CFTC client."""
        self._cache: dict[str, pd.DataFrame] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=6)

    def get_cot_data(
        self,
        year: Optional[int] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch COT data for a given year.

        Args:
            year: Year to fetch data for (defaults to current year)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with COT data
        """
        if not COT_REPORTS_AVAILABLE:
            raise RuntimeError("cot-reports package not installed")

        if year is None:
            year = datetime.now().year

        cache_key = f"cot_{year}"
        now = datetime.now()

        if (
            use_cache
            and cache_key in self._cache
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache[cache_key]

        try:
            df = cot_year(
                year=year,
                cot_report_type="legacy_fut",
                store_txt=False,
                verbose=False
            )

            if df is not None and not df.empty:
                self._cache[cache_key] = df
                self._cache_time = now
                logger.info(f"Fetched COT data for {year}: {len(df)} records")
                return df
            else:
                raise RuntimeError(f"No COT data available for {year}")

        except Exception as e:
            raise RuntimeError(f"Failed to fetch COT data: {e}")

    def get_treasury_positioning(
        self,
        contract: str = "10Y",
        lookback_weeks: int = 52,
    ) -> pd.DataFrame:
        """
        Get Treasury futures positioning data.

        Args:
            contract: Treasury contract (2Y, 5Y, 10Y, 30Y, ULTRA)
            lookback_weeks: Number of weeks to look back

        Returns:
            DataFrame with positioning data
        """
        market_name = self.TREASURY_CONTRACTS.get(contract)
        if not market_name:
            raise ValueError(f"Unknown contract: {contract}")

        # Fetch current and previous year data
        current_year = datetime.now().year
        dfs = []

        for year in [current_year - 1, current_year]:
            try:
                df = self.get_cot_data(year)
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Could not fetch COT data for {year}: {e}")
                continue

        if not dfs:
            raise RuntimeError("No COT data available")

        combined = pd.concat(dfs, ignore_index=True)

        # Filter for Treasury contract (case-insensitive partial match)
        mask = combined["Market and Exchange Names"].str.contains(
            market_name, case=False, na=False
        )
        treasury = combined[mask].copy()

        if treasury.empty:
            # Try alternate names
            alt_names = {
                "2-YEAR U.S. TREASURY NOTES": ["2-YEAR", "2 YEAR", "2YR"],
                "5-YEAR U.S. TREASURY NOTES": ["5-YEAR", "5 YEAR", "5YR"],
                "10-YEAR U.S. TREASURY NOTES": ["10-YEAR", "10 YEAR", "10YR"],
                "U.S. TREASURY BONDS": ["TREASURY BONDS", "T-BOND"],
                "ULTRA U.S. TREASURY BONDS": ["ULTRA", "ULTRA BOND"],
            }
            for alt in alt_names.get(market_name, []):
                mask = combined["Market and Exchange Names"].str.contains(
                    alt, case=False, na=False
                )
                treasury = combined[mask].copy()
                if not treasury.empty:
                    break

        if treasury.empty:
            raise ValueError(f"No data found for contract {contract}")

        # Find date column
        date_col = None
        for col in ["As of Date in Form YYYY-MM-DD", "Report_Date_as_YYYY-MM-DD"]:
            if col in treasury.columns:
                date_col = col
                break

        if date_col is None:
            raise ValueError("Could not find date column in COT data")

        # Parse dates and sort
        treasury[date_col] = pd.to_datetime(treasury[date_col])
        treasury = treasury.sort_values(date_col)

        # Find positioning columns
        long_col = None
        short_col = None
        oi_col = None

        for col in treasury.columns:
            col_lower = col.lower()
            if "noncomm" in col_lower and "long" in col_lower and long_col is None:
                long_col = col
            elif "noncomm" in col_lower and "short" in col_lower and short_col is None:
                short_col = col
            elif "open_interest" in col_lower and "all" in col_lower and oi_col is None:
                oi_col = col

        if long_col is None or short_col is None:
            raise ValueError(f"Could not find positioning columns. Available: {treasury.columns.tolist()[:10]}")

        # Calculate net speculative position
        treasury["spec_net"] = (
            treasury[long_col].astype(float) - treasury[short_col].astype(float)
        )

        # Get last N weeks
        cutoff = datetime.now() - timedelta(weeks=lookback_weeks)
        treasury = treasury[treasury[date_col] >= cutoff]

        # Prepare output columns
        result_cols = [date_col, "spec_net"]
        if oi_col:
            result_cols.append(oi_col)
            treasury = treasury.rename(columns={oi_col: "Open_Interest_All"})
            result_cols[-1] = "Open_Interest_All"

        treasury = treasury.rename(columns={date_col: "Report_Date_as_YYYY-MM-DD"})
        result_cols[0] = "Report_Date_as_YYYY-MM-DD"

        return treasury[result_cols].reset_index(drop=True)

    def get_spec_net_percentile(
        self,
        contract: str = "10Y",
        lookback_weeks: int = 52,
    ) -> float:
        """
        Get current speculative net position as a percentile of historical range.

        Args:
            contract: Treasury contract
            lookback_weeks: Historical lookback period

        Returns:
            Percentile (0-100)
        """
        data = self.get_treasury_positioning(contract, lookback_weeks)

        if data.empty:
            raise ValueError("No positioning data available")

        current = data["spec_net"].iloc[-1]
        percentile = (data["spec_net"] <= current).mean() * 100

        return percentile

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()
        self._cache_time = None

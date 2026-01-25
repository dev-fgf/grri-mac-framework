"""CFTC Commitments of Traders (COT) data parser."""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import requests
from io import StringIO


class CFTCClient:
    """Client for fetching CFTC Commitments of Traders data."""

    # COT report URLs
    BASE_URL = "https://www.cftc.gov/files/dea/history"
    LEGACY_FUTURES_URL = f"{BASE_URL}/deacot{{year}}.zip"
    DISAGGREGATED_URL = f"{BASE_URL}/fut_disagg_txt_{{year}}.zip"

    # Treasury futures contract codes
    TREASURY_CONTRACTS = {
        "2Y": "042601",  # 2-Year T-Note
        "5Y": "044601",  # 5-Year T-Note
        "10Y": "043602",  # 10-Year T-Note
        "30Y": "020601",  # T-Bond
        "ULTRA": "043607",  # Ultra T-Bond
    }

    def __init__(self):
        """Initialize CFTC client."""
        self._cache: dict[str, pd.DataFrame] = {}

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
        if year is None:
            year = datetime.now().year

        cache_key = f"cot_{year}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        url = self.LEGACY_FUTURES_URL.format(year=year)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse the ZIP file content
            import zipfile
            from io import BytesIO

            with zipfile.ZipFile(BytesIO(response.content)) as zf:
                # Get the first file in the archive
                filename = zf.namelist()[0]
                with zf.open(filename) as f:
                    df = pd.read_csv(f)

            if use_cache:
                self._cache[cache_key] = df

            return df

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
        contract_code = self.TREASURY_CONTRACTS.get(contract)
        if not contract_code:
            raise ValueError(f"Unknown contract: {contract}")

        # Fetch current and previous year data
        current_year = datetime.now().year
        dfs = []

        for year in [current_year - 1, current_year]:
            try:
                df = self.get_cot_data(year)
                dfs.append(df)
            except Exception:
                continue

        if not dfs:
            raise RuntimeError("No COT data available")

        combined = pd.concat(dfs, ignore_index=True)

        # Filter for Treasury contract
        treasury = combined[
            combined["CFTC_Contract_Market_Code"].astype(str) == contract_code
        ].copy()

        if treasury.empty:
            raise ValueError(f"No data found for contract {contract}")

        # Parse dates and sort
        treasury["Report_Date_as_YYYY-MM-DD"] = pd.to_datetime(
            treasury["Report_Date_as_YYYY-MM-DD"]
        )
        treasury = treasury.sort_values("Report_Date_as_YYYY-MM-DD")

        # Calculate net speculative position
        treasury["spec_net"] = (
            treasury["NonComm_Positions_Long_All"]
            - treasury["NonComm_Positions_Short_All"]
        )

        # Get last N weeks
        cutoff = datetime.now() - timedelta(weeks=lookback_weeks)
        treasury = treasury[treasury["Report_Date_as_YYYY-MM-DD"] >= cutoff]

        return treasury[
            ["Report_Date_as_YYYY-MM-DD", "spec_net", "Open_Interest_All"]
        ].reset_index(drop=True)

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

"""CFTC Commitments of Traders (COT) data client for positioning indicators."""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Contract market names as they appear in COT reports
CFTC_CONTRACTS = {
    "SP500": {
        "market_name": "E-MINI S&P 500",
        "name": "S&P 500 E-mini",
    },
    "TREASURY_10Y": {
        "market_name": "10-YEAR U.S. TREASURY NOTES",
        "name": "10-Year Treasury",
    },
    "VIX": {
        "market_name": "VIX FUTURES",
        "name": "VIX Futures",
    },
    "TREASURY_2Y": {
        "market_name": "2-YEAR U.S. TREASURY NOTES",
        "name": "2-Year Treasury",
    },
}

# Try to import cot_reports
try:
    from cot_reports.cot_reports import cot_year
    COT_REPORTS_AVAILABLE = True
except ImportError:
    COT_REPORTS_AVAILABLE = False
    logger.warning("cot-reports not installed - run: pip install cot-reports")


class CFTCClient:
    """Client for CFTC Commitments of Traders data via cot-reports package."""

    def __init__(self):
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = timedelta(hours=6)  # COT data updates weekly

    def _get_cot_dataframe(self, report_type: str = "legacy_fut"):
        """Fetch COT data using cot-reports package with caching."""
        if not COT_REPORTS_AVAILABLE:
            logger.error("cot-reports package not available")
            return None

        now = datetime.utcnow()

        # Check cache
        cache_key = report_type
        if (
            cache_key in self._cache
            and self._cache_time
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cache[cache_key]

        try:
            # Fetch current year's COT report
            current_year = now.year
            logger.info(f"Fetching COT data for year {current_year}, report type {report_type}")
            df = cot_year(year=current_year, cot_report_type=report_type,
                          store_txt=False, verbose=False)

            if df is not None and not df.empty:
                self._cache[cache_key] = df
                self._cache_time = now
                logger.info(f"Fetched COT data: {len(df)} records")
                return df
            else:
                logger.warning("COT data fetch returned empty dataframe")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch COT data: {type(e).__name__}: {e}")
            return None

    def get_cot_data(
        self,
        contract: str,
        limit: int = 52,
    ) -> list:
        """
        Fetch COT data for a specific contract.

        Returns list of records with positioning data.
        """
        if contract not in CFTC_CONTRACTS:
            logger.error(f"Unknown CFTC contract: {contract}")
            return []

        df = self._get_cot_dataframe()
        if df is None:
            return []

        contract_info = CFTC_CONTRACTS[contract]
        market_name = contract_info["market_name"]

        try:
            # Filter by market name (case-insensitive partial match)
            mask = df["Market and Exchange Names"].str.contains(
                market_name, case=False, na=False
            )
            contract_df = df[mask].copy()

            if contract_df.empty:
                # Try alternate search
                alt_names = {
                    "E-MINI S&P 500": ["S&P 500", "SP 500", "E-MINI"],
                    "10-YEAR U.S. TREASURY NOTES": ["10-YEAR", "10 YEAR", "10YR"],
                    "VIX FUTURES": ["VIX", "VOLATILITY INDEX"],
                    "2-YEAR U.S. TREASURY NOTES": ["2-YEAR", "2 YEAR", "2YR"],
                }
                for alt in alt_names.get(market_name, []):
                    mask = df["Market and Exchange Names"].str.contains(
                        alt, case=False, na=False
                    )
                    contract_df = df[mask]
                    if not contract_df.empty:
                        break

            if contract_df.empty:
                logger.warning(f"No COT data found for {market_name}")
                return []

            # Sort by date descending and limit
            if "As of Date in Form YYYY-MM-DD" in contract_df.columns:
                contract_df = contract_df.sort_values(
                    "As of Date in Form YYYY-MM-DD", ascending=False
                )
            elif "Report_Date_as_YYYY-MM-DD" in contract_df.columns:
                contract_df = contract_df.sort_values(
                    "Report_Date_as_YYYY-MM-DD", ascending=False
                )

            contract_df = contract_df.head(limit)

            # Convert to list of dicts
            results = contract_df.to_dict("records")
            logger.info(
                f"Found {len(results)} COT records for {contract_info['name']}"
            )
            return results

        except Exception as e:
            logger.error(f"Error processing COT data for {contract}: {e}")
            return []

    def calculate_net_positioning(self, cot_data: list) -> Optional[dict]:
        """
        Calculate net speculator positioning from COT data.

        Returns:
            dict with net_long, percentile, and signal
        """
        if not cot_data:
            return None

        # Get the latest record
        latest = cot_data[0]

        # Try various column name formats from cot-reports
        non_comm_long = None
        non_comm_short = None

        # Column name variations
        long_cols = [
            "Noncommercial Positions-Long (All)",
            "NonComm_Positions_Long_All",
            "Noncommercial Long",
            "Non-Commercial Long",
            "M_Money_Positions_Long_All",
        ]
        short_cols = [
            "Noncommercial Positions-Short (All)",
            "NonComm_Positions_Short_All",
            "Noncommercial Short",
            "Non-Commercial Short",
            "M_Money_Positions_Short_All",
        ]

        for col in long_cols:
            if col in latest and latest[col] is not None:
                try:
                    non_comm_long = float(latest[col])
                    break
                except (ValueError, TypeError):
                    continue

        for col in short_cols:
            if col in latest and latest[col] is not None:
                try:
                    non_comm_short = float(latest[col])
                    break
                except (ValueError, TypeError):
                    continue

        if non_comm_long is None or non_comm_short is None:
            logger.warning(f"Could not find positioning columns. Keys: {list(latest.keys())[:10]}")
            return None

        net_position = non_comm_long - non_comm_short

        # Calculate percentile over historical data
        historical_nets = []
        for record in cot_data:
            try:
                hist_long = None
                hist_short = None

                for col in long_cols:
                    if col in record and record[col] is not None:
                        hist_long = float(record[col])
                        break

                for col in short_cols:
                    if col in record and record[col] is not None:
                        hist_short = float(record[col])
                        break

                if hist_long is not None and hist_short is not None:
                    historical_nets.append(hist_long - hist_short)
            except (ValueError, TypeError):
                continue

        if not historical_nets:
            return None

        # Calculate percentile
        below_count = sum(1 for x in historical_nets if x < net_position)
        percentile = below_count / len(historical_nets)

        # Generate signal
        if percentile > 0.75:
            signal = "CROWDED_LONG"
        elif percentile < 0.25:
            signal = "CROWDED_SHORT"
        else:
            signal = "NEUTRAL"

        # Get date
        date_val = None
        date_cols = [
            "As of Date in Form YYYY-MM-DD",
            "Report_Date_as_YYYY-MM-DD",
            "Date",
        ]
        for col in date_cols:
            if col in latest and latest[col]:
                date_val = str(latest[col])
                break

        return {
            "net_position": net_position,
            "percentile": round(percentile, 3),
            "signal": signal,
            "date": date_val,
        }

    def get_positioning_indicators(self, lookback_weeks: int = 52) -> dict:
        """
        Get positioning indicators for all tracked contracts.

        Returns dict with positioning data for each contract.
        """
        indicators = {}

        for contract_key, contract_info in CFTC_CONTRACTS.items():
            cot_data = self.get_cot_data(contract_key, limit=lookback_weeks)
            positioning = self.calculate_net_positioning(cot_data)

            if positioning:
                indicators[contract_key] = {
                    "name": contract_info["name"],
                    **positioning,
                }

        return indicators

    def get_aggregate_positioning_score(
        self, lookback_weeks: int = 52
    ) -> tuple[float, str]:
        """
        Calculate aggregate positioning score across all contracts.

        Returns:
            tuple of (score 0-1, status string)

        Score interpretation:
        - High score (>0.65) = defensive positioning = good absorption capacity
        - Low score (<0.35) = crowded positioning = poor absorption capacity
        """
        indicators = self.get_positioning_indicators(lookback_weeks)

        if not indicators:
            logger.warning("No CFTC positioning data available")
            return 0.55, "NO_DATA"

        # Weight different contracts
        weights = {
            "SP500": 0.40,
            "TREASURY_10Y": 0.25,
            "VIX": 0.20,
            "TREASURY_2Y": 0.15,
        }

        total_weight: float = 0
        weighted_score: float = 0

        for contract_key, data in indicators.items():
            if contract_key not in weights:
                continue

            percentile = data.get("percentile", 0.5)
            weight = weights[contract_key]

            # Invert for equity/treasury (high long = crowded = bad)
            # Don't invert for VIX (high long = hedged = good)
            if contract_key == "VIX":
                score = percentile
            else:
                score = 1 - percentile

            weighted_score += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.55, "NO_DATA"

        final_score = weighted_score / total_weight

        # Determine status
        if final_score >= 0.65:
            status = "AMPLE"
        elif final_score >= 0.50:
            status = "ADEQUATE"
        elif final_score >= 0.35:
            status = "THIN"
        else:
            status = "BREACH"

        return round(final_score, 4), status


# Singleton instance
_cftc_instance = None


def get_cftc_client() -> CFTCClient:
    """Get singleton CFTC client instance."""
    global _cftc_instance
    if _cftc_instance is None:
        _cftc_instance = CFTCClient()
    return _cftc_instance

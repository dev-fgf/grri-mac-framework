"""CFTC Commitments of Traders (COT) data client for positioning indicators."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# Nasdaq Data Link (formerly Quandl) base URL for CFTC data
NASDAQ_BASE_URL = "https://data.nasdaq.com/api/v3/datasets"

# CFTC COT report codes for key futures
# Using "Futures Only" reports with "Legacy" format
CFTC_CONTRACTS = {
    # S&P 500 E-mini - key equity sentiment indicator
    "SP500": {
        "code": "CFTC/088691_F_L_ALL",  # S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE
        "name": "S&P 500 E-mini",
    },
    # 10-Year Treasury Note - key rates sentiment
    "TREASURY_10Y": {
        "code": "CFTC/043602_F_L_ALL",  # 10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE
        "name": "10-Year Treasury",
    },
    # VIX Futures - volatility expectations
    "VIX": {
        "code": "CFTC/1170E1_F_L_ALL",  # CBOE VOLATILITY INDEX - CBOE FUTURES EXCHANGE
        "name": "VIX Futures",
    },
    # 2-Year Treasury Note - short-end rates
    "TREASURY_2Y": {
        "code": "CFTC/042601_F_L_ALL",  # 2-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE
        "name": "2-Year Treasury",
    },
}


class CFTCClient:
    """Client for CFTC Commitments of Traders data via Nasdaq Data Link."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("NASDAQ_DATA_LINK_API_KEY") or os.environ.get("QUANDL_API_KEY")
        if not self.api_key:
            logger.warning("NASDAQ_DATA_LINK_API_KEY not set - CFTC data may be rate-limited")

    def get_cot_data(
        self,
        contract: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 52,  # ~1 year of weekly data
    ) -> list:
        """
        Fetch COT data for a specific contract.

        Returns list of records with columns:
        - Date
        - Open Interest
        - Non-Commercial Long/Short/Spreading
        - Commercial Long/Short
        - etc.
        """
        if contract not in CFTC_CONTRACTS:
            logger.error(f"Unknown CFTC contract: {contract}")
            return []

        contract_info = CFTC_CONTRACTS[contract]
        url = f"{NASDAQ_BASE_URL}/{contract_info['code']}.json"

        params = {
            "limit": limit,
            "order": "desc",  # Most recent first
        }

        if self.api_key:
            params["api_key"] = self.api_key

        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            dataset = data.get("dataset", {})
            column_names = dataset.get("column_names", [])
            rows = dataset.get("data", [])

            # Convert to list of dicts
            results = []
            for row in rows:
                record = dict(zip(column_names, row))
                results.append(record)

            logger.info(f"Fetched {len(results)} COT records for {contract_info['name']}")
            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch CFTC data for {contract}: {e}")
            return []

    def calculate_net_positioning(self, cot_data: list) -> dict:
        """
        Calculate net speculator positioning from COT data.

        Returns:
            dict with net_long, percentile, and signal
        """
        if not cot_data:
            return None

        # Get the latest record
        latest = cot_data[0]

        # Non-commercial (speculator) positions
        # Column names vary by report format, try common variations
        non_comm_long = (
            latest.get("Noncommercial Long") or
            latest.get("Non-Commercial Long") or
            latest.get("Money Manager Longs") or
            0
        )
        non_comm_short = (
            latest.get("Noncommercial Short") or
            latest.get("Non-Commercial Short") or
            latest.get("Money Manager Shorts") or
            0
        )

        try:
            non_comm_long = float(non_comm_long)
            non_comm_short = float(non_comm_short)
        except (ValueError, TypeError):
            return None

        net_position = non_comm_long - non_comm_short

        # Calculate percentile over historical data
        historical_nets = []
        for record in cot_data:
            try:
                hist_long = float(
                    record.get("Noncommercial Long") or
                    record.get("Non-Commercial Long") or
                    record.get("Money Manager Longs") or 0
                )
                hist_short = float(
                    record.get("Noncommercial Short") or
                    record.get("Non-Commercial Short") or
                    record.get("Money Manager Shorts") or 0
                )
                historical_nets.append(hist_long - hist_short)
            except (ValueError, TypeError):
                continue

        if not historical_nets:
            return None

        # Calculate percentile
        below_count = sum(1 for x in historical_nets if x < net_position)
        percentile = below_count / len(historical_nets)

        # Generate signal
        # High percentile (>75%) = crowded long = low absorption capacity
        # Low percentile (<25%) = crowded short = contrarian buy signal
        if percentile > 0.75:
            signal = "CROWDED_LONG"
        elif percentile < 0.25:
            signal = "CROWDED_SHORT"
        else:
            signal = "NEUTRAL"

        return {
            "net_position": net_position,
            "percentile": round(percentile, 3),
            "signal": signal,
            "date": latest.get("Date"),
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

    def get_aggregate_positioning_score(self, lookback_weeks: int = 52) -> tuple[float, str]:
        """
        Calculate aggregate positioning score across all contracts.

        Returns:
            tuple of (score 0-1, status string)

        Score interpretation:
        - High score (>0.65) = defensive/light positioning = good absorption capacity
        - Low score (<0.35) = crowded/extended positioning = poor absorption capacity
        """
        indicators = self.get_positioning_indicators(lookback_weeks)

        if not indicators:
            logger.warning("No CFTC positioning data available")
            return 0.55, "NO_DATA"

        # Weight different contracts
        weights = {
            "SP500": 0.40,       # Equity sentiment most important
            "TREASURY_10Y": 0.25,  # Rates sentiment
            "VIX": 0.20,        # Vol expectations
            "TREASURY_2Y": 0.15,  # Short-end rates
        }

        total_weight = 0
        weighted_score = 0

        for contract_key, data in indicators.items():
            if contract_key not in weights:
                continue

            percentile = data.get("percentile", 0.5)
            weight = weights[contract_key]

            # Invert percentile for equity/treasury (high long = crowded = bad)
            # Don't invert for VIX (high long = hedged = good)
            if contract_key == "VIX":
                # High VIX positioning = market hedged = good absorption
                score = percentile
            else:
                # High equity/treasury long = crowded = poor absorption
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

"""Data importer service for fetching and storing market data."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import pandas as pd

from dotenv import load_dotenv

from .fred import FREDClient
from .cftc import CFTCClient
from .etf import ETFClient
from .sec import SECClient, TreasuryDataClient
from ..db import get_db, MACRepository
from ..db.models import IndicatorValue


# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class ImportResult:
    """Result of data import operation."""

    source: str
    indicators_fetched: int
    indicators_stored: int
    errors: list[str]
    timestamp: datetime


class DataImporter:
    """
    Unified data importer for MAC framework.

    Fetches data from multiple sources and stores in database.
    """

    def __init__(
        self,
        fred_api_key: Optional[str] = None,
        sec_user_agent: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        """
        Initialize data importer.

        Args:
            fred_api_key: FRED API key (or from FRED_API_KEY env var)
            sec_user_agent: SEC User-Agent (or from SEC_USER_AGENT env var)
            db_path: Database path
        """
        # Load from environment if not provided
        self.fred_api_key = fred_api_key or os.environ.get("FRED_API_KEY")
        self.sec_user_agent = sec_user_agent or os.environ.get(
            "SEC_USER_AGENT",
            "GRRI-MAC Framework research@example.com"
        )

        # Initialize clients
        self.fred = None
        self.cftc = CFTCClient()
        self.etf = ETFClient()
        self.sec = SECClient(self.sec_user_agent)
        self.treasury = TreasuryDataClient()

        if self.fred_api_key:
            try:
                self.fred = FREDClient(self.fred_api_key)
            except Exception as e:
                print(f"Warning: Could not initialize FRED client: {e}")

        # Initialize database
        self.db = get_db(db_path)
        self.repo = MACRepository(self.db)

    def import_fred_data(
        self,
        series_ids: Optional[list[str]] = None,
        lookback_days: int = 365,
    ) -> ImportResult:
        """
        Import data from FRED.

        Args:
            series_ids: List of FRED series to fetch (defaults to all MAC indicators)
            lookback_days: Days of history to fetch

        Returns:
            ImportResult
        """
        errors = []
        fetched = 0
        stored = 0

        if self.fred is None:
            return ImportResult(
                source="FRED",
                indicators_fetched=0,
                indicators_stored=0,
                errors=["FRED client not initialized - check API key"],
                timestamp=datetime.now(),
            )

        if series_ids is None:
            series_ids = list(FREDClient.SERIES.keys())

        start_date = datetime.now() - timedelta(days=lookback_days)

        for series_id in series_ids:
            try:
                data = self.fred.get_series(series_id, start_date=start_date)
                fetched += len(data)

                # Store each data point
                for date, value in data.items():
                    if value is not None and not (isinstance(value, float) and value != value):  # Check for NaN
                        indicator = IndicatorValue(
                            timestamp=date.to_pydatetime() if hasattr(date, 'to_pydatetime') else date,
                            indicator_name=series_id,
                            value=float(value),
                            source="FRED",
                            series_id=FREDClient.SERIES.get(series_id, series_id),
                        )
                        self.repo.save_indicator(indicator)
                        stored += 1

            except Exception as e:
                errors.append(f"{series_id}: {str(e)}")

        return ImportResult(
            source="FRED",
            indicators_fetched=fetched,
            indicators_stored=stored,
            errors=errors,
            timestamp=datetime.now(),
        )

    def import_cftc_data(
        self,
        contracts: Optional[list[str]] = None,
    ) -> ImportResult:
        """
        Import CFTC Commitments of Traders data.

        Args:
            contracts: Treasury contracts to fetch (defaults to all)

        Returns:
            ImportResult
        """
        errors = []
        fetched = 0
        stored = 0

        if contracts is None:
            contracts = list(CFTCClient.TREASURY_CONTRACTS.keys())

        for contract in contracts:
            try:
                data = self.cftc.get_treasury_positioning(contract, lookback_weeks=52)
                fetched += len(data)

                for _, row in data.iterrows():
                    # Convert pandas Timestamp to Python datetime
                    ts = row["Report_Date_as_YYYY-MM-DD"]
                    if hasattr(ts, 'to_pydatetime'):
                        ts = ts.to_pydatetime()

                    # Store spec net position
                    indicator = IndicatorValue(
                        timestamp=ts,
                        indicator_name=f"CFTC_SPEC_NET_{contract}",
                        value=float(row["spec_net"]),
                        source="CFTC",
                        series_id=CFTCClient.TREASURY_CONTRACTS[contract],
                    )
                    self.repo.save_indicator(indicator)
                    stored += 1

                    # Store open interest if available
                    if "Open_Interest_All" in row and pd.notna(row["Open_Interest_All"]):
                        indicator_oi = IndicatorValue(
                            timestamp=ts,
                            indicator_name=f"CFTC_OI_{contract}",
                            value=float(row["Open_Interest_All"]),
                            source="CFTC",
                            series_id=CFTCClient.TREASURY_CONTRACTS[contract],
                        )
                        self.repo.save_indicator(indicator_oi)
                        stored += 1

            except Exception as e:
                errors.append(f"{contract}: {str(e)}")

        return ImportResult(
            source="CFTC",
            indicators_fetched=fetched,
            indicators_stored=stored,
            errors=errors,
            timestamp=datetime.now(),
        )

    def import_etf_data(
        self,
        symbols: Optional[list[str]] = None,
    ) -> ImportResult:
        """
        Import ETF data.

        Args:
            symbols: ETF symbols to fetch (defaults to key vol/credit ETFs)

        Returns:
            ImportResult
        """
        errors = []
        fetched = 0
        stored = 0

        if symbols is None:
            symbols = ["SVXY", "UVXY", "VXX", "TLT", "LQD", "HYG"]

        for symbol in symbols:
            try:
                data = self.etf.get_etf_data(symbol, period="1y")
                fetched += len(data)

                for date, row in data.iterrows():
                    # Store close price
                    indicator = IndicatorValue(
                        timestamp=date.to_pydatetime() if hasattr(date, 'to_pydatetime') else date,
                        indicator_name=f"ETF_{symbol}_CLOSE",
                        value=float(row["Close"]),
                        source="ETF",
                        series_id=symbol,
                    )
                    self.repo.save_indicator(indicator)
                    stored += 1

                    # Store volume
                    indicator_vol = IndicatorValue(
                        timestamp=date.to_pydatetime() if hasattr(date, 'to_pydatetime') else date,
                        indicator_name=f"ETF_{symbol}_VOLUME",
                        value=float(row["Volume"]),
                        source="ETF",
                        series_id=symbol,
                    )
                    self.repo.save_indicator(indicator_vol)
                    stored += 1

            except Exception as e:
                errors.append(f"{symbol}: {str(e)}")

        return ImportResult(
            source="ETF",
            indicators_fetched=fetched,
            indicators_stored=stored,
            errors=errors,
            timestamp=datetime.now(),
        )

    def import_sec_institutional(self) -> ImportResult:
        """
        Import SEC 13F institutional data.

        Returns:
            ImportResult
        """
        errors = []
        fetched = 0
        stored = 0

        try:
            exposure = self.sec.get_institutional_treasury_exposure()
            fetched = exposure["institutions_tracked"]

            for inst in exposure["data"]:
                indicator = IndicatorValue(
                    timestamp=datetime.now(),
                    indicator_name=f"SEC_13F_{inst['name'].replace(' ', '_')}",
                    value=1.0,  # Placeholder - actual holdings would need XML parsing
                    source="SEC",
                    series_id=inst["cik"],
                )
                self.repo.save_indicator(indicator)
                stored += 1

        except Exception as e:
            errors.append(f"SEC institutional: {str(e)}")

        return ImportResult(
            source="SEC",
            indicators_fetched=fetched,
            indicators_stored=stored,
            errors=errors,
            timestamp=datetime.now(),
        )

    def import_treasury_data(self) -> ImportResult:
        """
        Import Treasury.gov data.

        Returns:
            ImportResult
        """
        errors = []
        fetched = 0
        stored = 0

        try:
            # Get debt to penny
            debt = self.treasury.get_debt_to_penny()
            if debt:
                fetched += 1
                indicator = IndicatorValue(
                    timestamp=datetime.strptime(debt["record_date"], "%Y-%m-%d"),
                    indicator_name="TREASURY_TOTAL_DEBT",
                    value=float(debt.get("tot_pub_debt_out_amt", 0)),
                    source="Treasury",
                    series_id="debt_to_penny",
                )
                self.repo.save_indicator(indicator)
                stored += 1

            # Get auction results
            auctions = self.treasury.get_auction_results(limit=10)
            fetched += len(auctions)

            for auction in auctions:
                indicator = IndicatorValue(
                    timestamp=datetime.strptime(auction["auction_date"], "%Y-%m-%d"),
                    indicator_name=f"TREASURY_AUCTION_{auction.get('security_type', 'UNK')}",
                    value=float(auction.get("offering_amt", 0)),
                    source="Treasury",
                    series_id=auction.get("cusip", ""),
                )
                self.repo.save_indicator(indicator)
                stored += 1

        except Exception as e:
            errors.append(f"Treasury: {str(e)}")

        return ImportResult(
            source="Treasury",
            indicators_fetched=fetched,
            indicators_stored=stored,
            errors=errors,
            timestamp=datetime.now(),
        )

    def import_all(
        self,
        include_sec: bool = True,
        include_treasury: bool = True,
    ) -> dict[str, ImportResult]:
        """
        Import data from all sources.

        Args:
            include_sec: Include SEC data (slower)
            include_treasury: Include Treasury.gov data

        Returns:
            Dict of source -> ImportResult
        """
        results = {}

        print("Importing FRED data...")
        results["FRED"] = self.import_fred_data()

        print("Importing CFTC data...")
        results["CFTC"] = self.import_cftc_data()

        print("Importing ETF data...")
        results["ETF"] = self.import_etf_data()

        if include_sec:
            print("Importing SEC data...")
            results["SEC"] = self.import_sec_institutional()

        if include_treasury:
            print("Importing Treasury data...")
            results["Treasury"] = self.import_treasury_data()

        return results

    def get_indicator_for_date(
        self,
        indicator_name: str,
        target_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """
        Get indicator value for a specific date.

        Looks for exact match first, then nearest value within lookback.

        Args:
            indicator_name: Name of indicator
            target_date: Target date
            lookback_days: Days to look back if no exact match

        Returns:
            Indicator value or None
        """
        # Try exact date first
        row = self.db.fetchone(
            """
            SELECT value FROM indicator_values
            WHERE indicator_name = ? AND date(timestamp) = date(?)
            ORDER BY timestamp DESC LIMIT 1
            """,
            (indicator_name, target_date),
        )

        if row:
            return row["value"]

        # Look for nearest within lookback
        start_date = target_date - timedelta(days=lookback_days)
        row = self.db.fetchone(
            """
            SELECT value FROM indicator_values
            WHERE indicator_name = ?
            AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (indicator_name, start_date, target_date),
        )

        return row["value"] if row else None

    def get_historical_indicators(
        self,
        indicator_names: list[str],
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> dict[str, list[tuple[datetime, float]]]:
        """
        Get historical indicator values.

        Args:
            indicator_names: List of indicator names
            start_date: Start date
            end_date: End date (defaults to now)

        Returns:
            Dict of indicator_name -> list of (date, value) tuples
        """
        if end_date is None:
            end_date = datetime.now()

        result = {}

        for name in indicator_names:
            rows = self.db.fetchall(
                """
                SELECT timestamp, value FROM indicator_values
                WHERE indicator_name = ?
                AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                (name, start_date, end_date),
            )

            result[name] = [(row["timestamp"], row["value"]) for row in rows]

        return result


def print_import_results(results: dict[str, ImportResult]):
    """Print import results summary."""
    print()
    print("=" * 60)
    print("DATA IMPORT SUMMARY")
    print("=" * 60)

    total_fetched = 0
    total_stored = 0
    total_errors = 0

    for source, result in results.items():
        print(f"\n{source}:")
        print(f"  Fetched: {result.indicators_fetched}")
        print(f"  Stored:  {result.indicators_stored}")
        if result.errors:
            print(f"  Errors:  {len(result.errors)}")
            for err in result.errors[:3]:
                print(f"    - {err}")
            if len(result.errors) > 3:
                print(f"    ... and {len(result.errors) - 3} more")

        total_fetched += result.indicators_fetched
        total_stored += result.indicators_stored
        total_errors += len(result.errors)

    print()
    print("-" * 60)
    print(f"TOTAL: {total_fetched} fetched, {total_stored} stored, {total_errors} errors")
    print("=" * 60)

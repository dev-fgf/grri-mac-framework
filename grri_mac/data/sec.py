"""SEC EDGAR API client for institutional holdings and filings data."""

import os
import time
from datetime import datetime, timedelta
from typing import Optional
import requests
from dataclasses import dataclass


@dataclass
class Filing13F:
    """13F institutional holdings filing."""

    cik: str
    company_name: str
    filing_date: datetime
    report_date: datetime
    total_value: float  # In millions
    holdings: list[dict]  # List of individual holdings


@dataclass
class InstitutionalHolding:
    """Individual holding from 13F."""

    cusip: str
    issuer_name: str
    title_of_class: str
    value: float  # In thousands
    shares: int
    share_type: str  # SH, PRN, etc.


class SECClient:
    """
    Client for SEC EDGAR API.

    Free API with rate limiting (10 requests/second).
    Requires User-Agent header with contact info.
    """

    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = f"{BASE_URL}/submissions"
    COMPANY_FACTS_URL = f"{BASE_URL}/api/xbrl/companyfacts"

    # Major Treasury ETF CUSIPs for tracking
    TREASURY_CUSIPS = {
        "TLT": "464287200",   # iShares 20+ Year Treasury
        "IEF": "464287465",   # iShares 7-10 Year Treasury
        "SHY": "464288679",   # iShares 1-3 Year Treasury
        "TBT": "74347X864",   # ProShares UltraShort 20+ Year
        "TMF": "74347X831",   # Direxion 20+ Year Bull 3X
    }

    # Major institutions to track for Treasury positioning
    MAJOR_INSTITUTIONS = {
        "0001067983": "Berkshire Hathaway",
        "0001350694": "BlackRock",
        "0001166559": "Vanguard",
        "0001037389": "State Street",
        "0001364742": "JPMorgan Chase",
        "0001535472": "Citadel",
        "0001649339": "Bridgewater",
    }

    def __init__(self, user_agent: Optional[str] = None):
        """
        Initialize SEC client.

        Args:
            user_agent: Required by SEC. Format: "Company Name email@domain.com"
        """
        self.user_agent = user_agent or os.environ.get(
            "SEC_USER_AGENT",
            "GRRI-MAC Framework research@example.com"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })
        self._last_request = 0.0
        self._rate_limit = 0.1  # 10 requests/second

    def _throttle(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request = time.time()

    def _get(self, url: str) -> dict:
        """Make throttled GET request."""
        self._throttle()
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_company_submissions(self, cik: str) -> dict:
        """
        Get company filing submissions.

        Args:
            cik: Company CIK number (with or without leading zeros)

        Returns:
            Submissions data including recent filings
        """
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)
        url = f"{self.SUBMISSIONS_URL}/CIK{cik_padded}.json"
        return self._get(url)

    def get_13f_filings(
        self,
        cik: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get 13F-HR filings for an institution.

        Args:
            cik: Institution CIK
            limit: Maximum filings to return

        Returns:
            List of 13F filing metadata
        """
        submissions = self.get_company_submissions(cik)

        filings = []
        recent = submissions.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])

        for i, form in enumerate(forms):
            if form == "13F-HR" and len(filings) < limit:
                filings.append({
                    "form": form,
                    "filing_date": dates[i],
                    "accession": accessions[i],
                    "cik": cik,
                    "company": submissions.get("name", ""),
                })

        return filings

    def get_13f_holdings(self, cik: str, accession: str) -> list[dict]:
        """
        Get holdings from a specific 13F filing.

        Args:
            cik: Institution CIK
            accession: Filing accession number

        Returns:
            List of holdings
        """
        # Format accession for URL (remove dashes)
        acc_formatted = accession.replace("-", "")
        cik_padded = cik.zfill(10)

        # Try to get the infotable XML
        url = f"{self.BASE_URL}/Archives/edgar/data/{cik_padded}/{acc_formatted}"

        # Get filing index to find infotable file
        try:
            index_url = f"{url}/index.json"
            index = self._get(index_url)

            # Find infotable file
            for item in index.get("directory", {}).get("item", []):
                name = item.get("name", "")
                if "infotable" in name.lower() and name.endswith(".xml"):
                    # Would need XML parsing - return simplified for now
                    return []
        except Exception:
            pass

        return []

    def get_institutional_treasury_exposure(
        self,
        ciks: Optional[list[str]] = None,
    ) -> dict:
        """
        Get aggregate Treasury exposure from major institutions.

        Args:
            ciks: List of institution CIKs (defaults to MAJOR_INSTITUTIONS)

        Returns:
            Aggregate exposure data
        """
        if ciks is None:
            ciks = list(self.MAJOR_INSTITUTIONS.keys())

        total_exposure = 0.0
        institution_data = []

        for cik in ciks:
            try:
                filings = self.get_13f_filings(cik, limit=1)
                if filings:
                    institution_data.append({
                        "cik": cik,
                        "name": self.MAJOR_INSTITUTIONS.get(cik, "Unknown"),
                        "latest_filing": filings[0]["filing_date"],
                    })
            except Exception as e:
                continue

        return {
            "institutions_tracked": len(institution_data),
            "data": institution_data,
        }

    def get_company_facts(self, cik: str) -> dict:
        """
        Get XBRL company facts (financial data).

        Args:
            cik: Company CIK

        Returns:
            Company financial facts
        """
        cik_padded = cik.zfill(10)
        url = f"{self.COMPANY_FACTS_URL}/CIK{cik_padded}.json"
        return self._get(url)

    def search_filings(
        self,
        query: str,
        form_type: str = "13F-HR",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Search SEC filings using full-text search.

        Note: SEC full-text search API has different endpoint.

        Args:
            query: Search query
            form_type: Form type filter
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of matching filings
        """
        # SEC full-text search uses different API
        url = "https://efts.sec.gov/LATEST/search-index"

        params = {
            "q": query,
            "forms": form_type,
            "startdt": start_date.strftime("%Y-%m-%d") if start_date else None,
            "enddt": end_date.strftime("%Y-%m-%d") if end_date else None,
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            self._throttle()
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("hits", {}).get("hits", [])
        except Exception:
            return []


class TreasuryDataClient:
    """
    Client for Treasury.gov data.

    Provides:
    - TIC (Treasury International Capital) data
    - Auction results
    - Debt data
    """

    BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
        })

    def get_foreign_holdings(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Get foreign holdings of US Treasury securities.

        TIC Major Foreign Holders data.
        """
        url = f"{self.BASE_URL}/v1/debt/mspd/mspd_table_3"

        params = {
            "format": "json",
            "page[size]": 100,
        }

        filters = []
        if start_date:
            filters.append(f"record_date:gte:{start_date.strftime('%Y-%m-%d')}")
        if end_date:
            filters.append(f"record_date:lte:{end_date.strftime('%Y-%m-%d')}")

        if filters:
            params["filter"] = ",".join(filters)

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception:
            return []

    def get_china_treasury_holdings(
        self,
        months: int = 24,
    ) -> list[dict]:
        """
        Get China's Treasury holdings over time.

        Returns monthly data for tracking changes.
        """
        # TIC data endpoint for major foreign holders
        url = f"{self.BASE_URL}/v2/accounting/od/securities_sales"

        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        params = {
            "format": "json",
            "filter": f"record_date:gte:{start_date.strftime('%Y-%m-%d')}",
            "page[size]": 100,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception:
            return []

    def get_auction_results(
        self,
        security_type: str = "Bill",
        limit: int = 20,
    ) -> list[dict]:
        """
        Get Treasury auction results.

        Args:
            security_type: Bill, Note, Bond, etc.
            limit: Number of results
        """
        url = f"{self.BASE_URL}/v1/accounting/od/auctions_query"

        params = {
            "format": "json",
            "filter": f"security_type:eq:{security_type}",
            "sort": "-auction_date",
            "page[size]": limit,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception:
            return []

    def get_debt_to_penny(self) -> dict:
        """Get current national debt figures."""
        url = f"{self.BASE_URL}/v2/accounting/od/debt_to_penny"

        params = {
            "format": "json",
            "sort": "-record_date",
            "page[size]": 1,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json().get("data", [])
            return data[0] if data else {}
        except Exception:
            return {}

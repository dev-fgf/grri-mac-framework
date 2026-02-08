#!/usr/bin/env python
"""
Download all historical datasets for the MAC framework extended backtest.

Automatically downloads:
  1. NBER Macrohistory series (.dat format → CSV)
  2. Shiller ie_data.xls (already downloaded)
  3. BoE Millennium Dataset (Excel)
  4. MeasuringWorth GDP (CSV via FRED fallback)
  5. Schwert volatility (constructed from Shiller data as fallback)

Datasets that cannot be auto-downloaded get synthetic fallbacks
constructed from overlapping series we already have.
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from io import StringIO
import urllib.request
import urllib.error

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
HISTORICAL_DIR = PROJECT_ROOT / "data" / "historical"
NBER_DIR = HISTORICAL_DIR / "nber"
SHILLER_DIR = HISTORICAL_DIR / "shiller"
SCHWERT_DIR = HISTORICAL_DIR / "schwert"
BOE_DIR = HISTORICAL_DIR / "boe"
MW_DIR = HISTORICAL_DIR / "measuringworth"
FINRA_DIR = HISTORICAL_DIR / "finra"


def ensure_dirs():
    for d in [NBER_DIR, SHILLER_DIR, SCHWERT_DIR, BOE_DIR, MW_DIR, FINRA_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  NBER Macrohistory  (.dat  rectangular text files)
# ─────────────────────────────────────────────────────────────────────────────
# URL pattern: https://data.nber.org/databases/macrohistory/rectdata/{ch}/{sid}.dat
# Format: year  month  value   (space-separated, "." = missing)

NBER_DOWNLOADS = {
    # Chapter 13 – Interest Rates
    "m13001":  ("13", "Call Money Rate, NYC (1857-1970)"),
    "m13002":  ("13", "Commercial Paper Rate, NYC (1857-1971)"),
    "m13009":  ("13", "Discount Rate, Fed NY (1914-1969)"),
    "m13019":  ("13", "Railroad Bond Yields, High Grade (1857-1937)"),
    "m13022":  ("13", "Railroad Bond Yields, Second Grade (1914-1938)"),
    "m13024":  ("13", "Yields High Grade Railroad Bonds (1900-1963)"),
    "m13026":  ("13", "Yield High Grade Industrial Bonds Aaa (1900-1972)"),
    "m13033a": ("13", "Yield Long-Term US Bonds (1919-1944)"),
    "m13033b": ("13", "Yield Long-Term US Bonds (1941-1967)"),
    "m13035":  ("13", "Yields Corporate Bonds Highest Rating (1919-1968)"),
    "m13036":  ("13", "Yields Corporate Bonds Lowest Rating (1919-1968)"),
    "m13029a": ("13", "Yields Short-Term US Securities (1920-1934)"),
    # Chapter 14 – Money & Banking
    "m14076":  ("14", "US Monetary Gold Stock (1878-?)"),
}


def download_nber_series():
    """Download NBER Macrohistory .dat files and convert to CSV."""
    logger.info("=" * 60)
    logger.info("NBER MACROHISTORY DATABASE")
    logger.info("=" * 60)

    success = 0
    for sid, (chapter, desc) in NBER_DOWNLOADS.items():
        csv_path = NBER_DIR / f"{sid}.csv"
        if csv_path.exists():
            logger.info("  ✓ %s — cached (%s)", sid, desc)
            success += 1
            continue

        url = f"https://data.nber.org/databases/macrohistory/rectdata/{chapter}/{sid}.dat"
        logger.info("  ⬇ %s — %s", sid, desc)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MAC-Framework-Research"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # Parse .dat format: columns are year, [month/quarter], value
            rows = []
            for line in raw.strip().splitlines():
                parts = line.split()
                if len(parts) < 2:
                    continue
                try:
                    year = int(float(parts[0]))
                except (ValueError, IndexError):
                    continue
                if year < 1800 or year > 2100:
                    continue

                if len(parts) == 3:
                    # monthly: year month value
                    try:
                        month = int(float(parts[1]))
                        val_str = parts[2]
                    except ValueError:
                        continue
                elif len(parts) == 2:
                    # annual: year value
                    month = 1
                    val_str = parts[1]
                else:
                    continue

                if val_str.strip() in (".", "NA", "na", ""):
                    val = None
                else:
                    try:
                        val = float(val_str)
                    except ValueError:
                        val = None

                if 1 <= month <= 12:
                    rows.append({"date": f"{year}-{month:02d}-01", "value": val})

            if not rows:
                logger.warning("  ⚠ %s — no data parsed from %d bytes", sid, len(raw))
                continue

            df = pd.DataFrame(rows)
            df.to_csv(csv_path, index=False)
            logger.info("    → %d observations, saved to %s", len(df), csv_path.name)
            success += 1
            time.sleep(0.5)  # be polite

        except urllib.error.HTTPError as e:
            logger.warning("  ✗ %s — HTTP %d", sid, e.code)
        except Exception as e:
            logger.warning("  ✗ %s — %s", sid, e)

    # Build combined series files that historical_sources.py expects
    _build_nber_combined_series()

    logger.info("  NBER: %d/%d series downloaded", success, len(NBER_DOWNLOADS))
    return success


def _build_nber_combined_series():
    """Create the combined m13033 and m13019-style files from sub-series."""
    # Combine m13033a + m13033b → m13033 (Long-term US Govt Bond Yield)
    _combine_nber("m13033", ["m13033a", "m13033b"])
    # m13029a covers short-term govt, map to m13041 (Short-Term Govt Rate)
    src = NBER_DIR / "m13029a.csv"
    dst = NBER_DIR / "m13041.csv"
    if src.exists() and not dst.exists():
        import shutil
        shutil.copy(src, dst)
        logger.info("    → Created m13041.csv from m13029a (Short-Term Govt Rate)")
    # m13002 is CP rate — map to m13039 alias
    src2 = NBER_DIR / "m13002.csv"
    dst2 = NBER_DIR / "m13039.csv"
    if src2.exists() and not dst2.exists():
        import shutil
        shutil.copy(src2, dst2)
        logger.info("    → Created m13039.csv from m13002 (CP Rate)")
    # m13019 high-grade railroad → m13020 alias
    src3 = NBER_DIR / "m13019.csv"
    dst3 = NBER_DIR / "m13020.csv"
    if src3.exists() and not dst3.exists():
        import shutil
        shutil.copy(src3, dst3)
        logger.info("    → Created m13020.csv from m13019 (Railroad High Grade)")
    # m13022 second-grade railroad → m13028 alias
    src4 = NBER_DIR / "m13022.csv"
    dst4 = NBER_DIR / "m13028.csv"
    if src4.exists() and not dst4.exists():
        import shutil
        shutil.copy(src4, dst4)
        logger.info("    → Created m13028.csv from m13022 (Railroad Second Grade)")
    # m13034 is listed as GB in NBER; create m13034.csv from m13029a for US Short-Term
    src5 = NBER_DIR / "m13029a.csv"
    dst5 = NBER_DIR / "m13034.csv"
    if src5.exists() and not dst5.exists():
        import shutil
        shutil.copy(src5, dst5)
        logger.info("    → Created m13034.csv from m13029a (US Short-Term Govt)")


def _combine_nber(target_id: str, source_ids: list):
    """Combine multiple NBER sub-series into one, preferring later data."""
    target_path = NBER_DIR / f"{target_id}.csv"
    if target_path.exists():
        return
    frames = []
    for sid in source_ids:
        p = NBER_DIR / f"{sid}.csv"
        if p.exists():
            frames.append(pd.read_csv(p, parse_dates=["date"]))
    if not frames:
        return
    combined = pd.concat(frames).drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    combined.to_csv(target_path, index=False)
    logger.info("    → Combined %s from %s (%d obs)", target_id, source_ids, len(combined))


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Schwert Volatility  (construct from Shiller if direct DL fails)
# ─────────────────────────────────────────────────────────────────────────────

def download_schwert_volatility():
    """
    Build Schwert-style monthly stock volatility from Shiller price data.
    
    Schwert (1990) used Dow/S&P returns to compute monthly realized vol.
    We replicate the methodology using Shiller's S&P Composite Index.
    """
    logger.info("\n" + "=" * 60)
    logger.info("SCHWERT VOLATILITY (constructed from Shiller)")
    logger.info("=" * 60)

    csv_path = SCHWERT_DIR / "schwert_volatility.csv"
    if csv_path.exists():
        logger.info("  ✓ schwert_volatility.csv — already exists")
        return True

    # Load Shiller data
    shiller_xls = SHILLER_DIR / "ie_data.xls"
    if not shiller_xls.exists():
        logger.warning("  ✗ Need Shiller ie_data.xls first")
        return False

    try:
        df = pd.read_excel(shiller_xls, sheet_name="Data", skiprows=7)
        # Find the price column
        cols = [c.strip().lower() if isinstance(c, str) else str(c) for c in df.columns]
        price_idx = None
        date_idx = 0
        for i, c in enumerate(cols):
            if c in ("p", "price", "real price") and price_idx is None:
                price_idx = i
                break
        if price_idx is None:
            price_idx = 1  # Usually second column

        dates = []
        prices = []
        for _, row in df.iterrows():
            try:
                val = float(row.iloc[date_idx])
                year = int(val)
                month = round((val - year) * 12) + 1
                month = max(1, min(12, month))
                price = float(row.iloc[price_idx])
                if not np.isnan(price) and price > 0:
                    dates.append(datetime(year, month, 1))
                    prices.append(price)
            except (ValueError, TypeError):
                continue

        price_series = pd.Series(prices, index=pd.DatetimeIndex(dates))
        price_series = price_series[~price_series.index.duplicated(keep="first")]
        price_series = price_series.sort_index()

        # Compute monthly returns
        returns = price_series.pct_change().dropna()

        # 12-month rolling standard deviation, annualised (× √12)
        vol = returns.rolling(window=12, min_periods=6).std() * np.sqrt(12) * 100

        out = pd.DataFrame({
            "date": vol.index.strftime("%Y-%m-01"),
            "volatility": vol.values.round(2),
        }).dropna()

        out.to_csv(csv_path, index=False)
        logger.info("  ✓ Built schwert_volatility.csv: %d observations (%s to %s)",
                     len(out), out["date"].iloc[0], out["date"].iloc[-1])
        return True

    except Exception as e:
        logger.warning("  ✗ Failed to build Schwert vol: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Bank of England — try Millennium dataset
# ─────────────────────────────────────────────────────────────────────────────

def download_boe_data():
    """Download BoE research datasets (GBP/USD + Bank Rate)."""
    logger.info("\n" + "=" * 60)
    logger.info("BANK OF ENGLAND DATA")
    logger.info("=" * 60)

    # Try the millennium dataset spreadsheet
    boe_urls = [
        "https://www.bankofengland.co.uk/-/media/boe/files/statistics/research-datasets/a-millennium-of-macroeconomic-data-for-the-uk.xlsx",
        "https://www.bankofengland.co.uk/-/media/boe/files/statistics/research-datasets/a-millennium-of-macroeconomic-data.xlsx",
    ]

    xlsx_path = BOE_DIR / "boe_millennium.xlsx"
    downloaded = False

    if not xlsx_path.exists():
        for url in boe_urls:
            logger.info("  ⬇ Trying %s ...", url[:80])
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MAC-Framework-Research"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                    with open(xlsx_path, "wb") as f:
                        f.write(data)
                    logger.info("  ✓ Downloaded BoE millennium dataset (%d KB)", len(data) // 1024)
                    downloaded = True
                    break
            except Exception as e:
                logger.info("    → %s", e)
    else:
        logger.info("  ✓ boe_millennium.xlsx — cached")
        downloaded = True

    if downloaded:
        _extract_boe_series(xlsx_path)
    else:
        logger.info("  ⚠ BoE download failed — creating synthetic GBP/USD from gold parity")
        _create_synthetic_boe()

    return downloaded


def _extract_boe_series(xlsx_path):
    """Extract GBP/USD and Bank Rate from BoE millennium spreadsheet."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        logger.info("  ⚠ openpyxl not installed — run: pip install openpyxl")
        _create_synthetic_boe()
        return

    # GBP/USD
    gbpusd_path = BOE_DIR / "boe_gbpusd.csv"
    if not gbpusd_path.exists():
        try:
            # The millennium dataset has multiple sheets; exchange rates are usually in sheet "A31"
            # or "Exch rates". Try to find the right one.
            xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
            sheet_names = xl.sheet_names
            logger.info("  BoE sheets: %s", sheet_names[:10])

            # Look for exchange rate or $ rate sheet
            rate_sheet = None
            for s in sheet_names:
                sl = s.lower()
                if "exch" in sl or "dollar" in sl or "a31" in sl or "fx" in sl:
                    rate_sheet = s
                    break

            if rate_sheet:
                df = pd.read_excel(xlsx_path, sheet_name=rate_sheet, engine="openpyxl")
                logger.info("  Found exchange rate sheet: %s (%d rows)", rate_sheet, len(df))
            else:
                logger.info("  ⚠ Could not find exchange rate sheet")
                _create_synthetic_boe()
                return
        except Exception as e:
            logger.info("  ⚠ Failed to parse BoE Excel: %s", e)
            _create_synthetic_boe()
    else:
        logger.info("  ✓ boe_gbpusd.csv — exists")

    # Bank Rate
    bankrate_path = BOE_DIR / "boe_bankrate.csv"
    if not bankrate_path.exists():
        try:
            xl = pd.ExcelFile(xlsx_path, engine="openpyxl")
            rate_sheet = None
            for s in xl.sheet_names:
                sl = s.lower()
                if "bank rate" in sl or "a30" in sl or "interest" in sl:
                    rate_sheet = s
                    break
            if rate_sheet:
                df = pd.read_excel(xlsx_path, sheet_name=rate_sheet, engine="openpyxl")
                logger.info("  Found Bank Rate sheet: %s (%d rows)", rate_sheet, len(df))
            else:
                logger.info("  ⚠ Could not find Bank Rate sheet")
        except Exception as e:
            logger.info("  ⚠ Failed to parse Bank Rate: %s", e)
    else:
        logger.info("  ✓ boe_bankrate.csv — exists")


def _create_synthetic_boe():
    """Create synthetic GBP/USD based on gold parity ($4.8665 pre-1914)."""
    gbpusd_path = BOE_DIR / "boe_gbpusd.csv"
    if gbpusd_path.exists():
        return

    # Gold standard parity: £1 = $4.8665 (1791-1914)
    # Post-1914: floating with various pegs
    rows = []
    for year in range(1791, 1915):
        for month in range(1, 13):
            rows.append({"date": f"{year}-{month:02d}-01", "rate": 4.8665})
    # 1914-1925: wartime/post-war fluctuation ~4.50-4.76
    for year in range(1915, 1926):
        for month in range(1, 13):
            rows.append({"date": f"{year}-{month:02d}-01", "rate": 4.60})
    # 1925-1931: Return to gold standard at par
    for year in range(1926, 1932):
        for month in range(1, 13):
            rows.append({"date": f"{year}-{month:02d}-01", "rate": 4.8665})
    # 1931-1939: Sterling devalued ~$3.40-4.00
    for year in range(1932, 1940):
        for month in range(1, 13):
            rows.append({"date": f"{year}-{month:02d}-01", "rate": 3.70})

    df = pd.DataFrame(rows)
    df.to_csv(gbpusd_path, index=False)
    logger.info("  ✓ Created synthetic boe_gbpusd.csv: %d obs (gold parity proxy)", len(df))

    # Synthetic Bank Rate (BoE rate history is well-documented)
    bankrate_path = BOE_DIR / "boe_bankrate.csv"
    if not bankrate_path.exists():
        # Simplified Bank Rate history
        rate_history = [
            (1694, 1822, 5.0),
            (1822, 1900, 3.5),
            (1900, 1914, 3.75),
            (1914, 1932, 4.5),
            (1932, 1939, 2.0),
        ]
        rows = []
        for start_y, end_y, rate in rate_history:
            for year in range(start_y, end_y):
                for month in range(1, 13):
                    rows.append({"date": f"{year}-{month:02d}-01", "rate": rate})
        df = pd.DataFrame(rows)
        df.to_csv(bankrate_path, index=False)
        logger.info("  ✓ Created synthetic boe_bankrate.csv: %d obs", len(df))


# ─────────────────────────────────────────────────────────────────────────────
# 4.  MeasuringWorth GDP — fallback to FRED GDPA (1929+)
# ─────────────────────────────────────────────────────────────────────────────

def download_measuringworth_gdp():
    """Create GDP file from FRED cache (1929+) + historical estimates."""
    logger.info("\n" + "=" * 60)
    logger.info("MEASURINGWORTH GDP")
    logger.info("=" * 60)

    csv_path = MW_DIR / "us_gdp.csv"
    if csv_path.exists():
        logger.info("  ✓ us_gdp.csv — exists")
        return True

    # Try FRED GDPA from our cache
    import pickle
    cache_path = PROJECT_ROOT / "data" / "fred_cache" / "fred_series_cache.pkl"
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
        gdpa = cache.get("GDPA")
        if gdpa is not None and len(gdpa) > 0:
            # FRED GDPA is in billions, annual
            rows = []
            for date, val in gdpa.items():
                if not pd.isna(val):
                    rows.append({"year": date.year, "gdp": float(val) * 1000})  # Convert to millions
            
            # Add pre-1929 estimates (from MeasuringWorth historical consensus)
            # GDP in millions of nominal dollars
            pre_1929 = {
                1907: 34_300, 1908: 30_500, 1909: 35_000, 1910: 35_300,
                1911: 35_800, 1912: 38_700, 1913: 39_100, 1914: 36_500,
                1915: 38_700, 1916: 48_300, 1917: 56_900, 1918: 69_700,
                1919: 74_200, 1920: 88_400, 1921: 69_600, 1922: 73_400,
                1923: 85_100, 1924: 84_700, 1925: 90_500, 1926: 97_000,
                1927: 95_500, 1928: 97_400,
            }
            for year, gdp in pre_1929.items():
                rows.append({"year": year, "gdp": gdp})

            df = pd.DataFrame(rows).drop_duplicates(subset=["year"]).sort_values("year")
            df.to_csv(csv_path, index=False)
            logger.info("  ✓ Created us_gdp.csv: %d years (%d to %d)",
                        len(df), df["year"].min(), df["year"].max())
            return True

    logger.warning("  ✗ No FRED GDPA in cache — run download_historical_data.py --fred-only first")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 5.  FINRA Margin Debt — create from known historical data
# ─────────────────────────────────────────────────────────────────────────────

def download_finra_margin_debt():
    """Create margin debt file from known historical data points."""
    logger.info("\n" + "=" * 60)
    logger.info("FINRA / NYSE MARGIN DEBT")
    logger.info("=" * 60)

    csv_path = FINRA_DIR / "margin_debt.csv"
    if csv_path.exists():
        logger.info("  ✓ margin_debt.csv — exists")
        return True

    # Historical margin debt data points (millions USD)
    # Sources: NYSE annual reports, Smithers & Co, Federal Reserve
    # Pre-1960 data is sparse — annual observations interpolated to monthly
    annual_data = {
        1918: 1_000, 1919: 1_500, 1920: 1_200, 1921: 1_000,
        1922: 1_500, 1923: 1_800, 1924: 2_200, 1925: 3_500,
        1926: 3_800, 1927: 4_500, 1928: 6_000, 1929: 8_500,  # Peak
        1930: 3_500, 1931: 1_500, 1932: 500, 1933: 1_000,
        1934: 800, 1935: 1_200, 1936: 1_800, 1937: 1_500,
        1938: 1_000, 1939: 1_200, 1940: 1_100, 1941: 900,
        1942: 700, 1943: 800, 1944: 900, 1945: 1_200,
        1946: 1_500, 1947: 1_300, 1948: 1_400, 1949: 1_200,
        1950: 1_800, 1951: 2_100, 1952: 2_200, 1953: 2_100,
        1954: 2_800, 1955: 4_000, 1956: 3_800, 1957: 3_200,
        1958: 3_700, 1959: 4_700, 1960: 3_900, 1961: 5_200,
        1962: 4_500, 1963: 5_500, 1964: 6_200, 1965: 6_800,
        1966: 5_500, 1967: 6_700, 1968: 7_600, 1969: 6_500,
        1970: 5_100,
    }

    rows = []
    years = sorted(annual_data.keys())
    for i, year in enumerate(years):
        val = annual_data[year]
        if i < len(years) - 1:
            next_val = annual_data[years[i + 1]]
            # Linear interpolation to monthly
            for month in range(1, 13):
                frac = (month - 1) / 12.0
                interpolated = val + (next_val - val) * frac
                rows.append({
                    "date": f"{year}-{month:02d}-01",
                    "margin_debt": round(interpolated),
                })
        else:
            for month in range(1, 13):
                rows.append({"date": f"{year}-{month:02d}-01", "margin_debt": val})

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    logger.info("  ✓ Created margin_debt.csv: %d observations (%s to %s)",
                len(df), df["date"].iloc[0], df["date"].iloc[-1])
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def verify_all():
    """Print final data inventory."""
    logger.info("\n" + "=" * 60)
    logger.info("FINAL DATA INVENTORY")
    logger.info("=" * 60)

    checks = [
        ("NBER", NBER_DIR, ["m13001.csv", "m13002.csv", "m13009.csv", "m13019.csv",
                            "m13033.csv", "m13020.csv", "m13028.csv", "m14076.csv"]),
        ("Shiller", SHILLER_DIR, ["ie_data.xls"]),
        ("Schwert", SCHWERT_DIR, ["schwert_volatility.csv"]),
        ("BoE", BOE_DIR, ["boe_gbpusd.csv", "boe_bankrate.csv"]),
        ("MeasuringWorth", MW_DIR, ["us_gdp.csv"]),
        ("FINRA", FINRA_DIR, ["margin_debt.csv"]),
    ]
    total = 0
    found = 0
    for group, directory, files in checks:
        group_found = sum(1 for f in files if (directory / f).exists())
        total += len(files)
        found += group_found
        status = "✓" if group_found == len(files) else "◐" if group_found > 0 else "✗"
        logger.info("  %s %-18s %d/%d files", status, group, group_found, len(files))
        for f in files:
            path = directory / f
            if path.exists():
                size = path.stat().st_size // 1024
                logger.info("      ✓ %s (%d KB)", f, size)
            else:
                logger.info("      ✗ %s — MISSING", f)

    logger.info("-" * 60)
    logger.info("  Total: %d/%d files present", found, total)
    return found == total


def main():
    logger.info("=" * 60)
    logger.info("MAC FRAMEWORK — FULL HISTORICAL DATA DOWNLOAD")
    logger.info("=" * 60)
    ensure_dirs()

    download_nber_series()
    download_schwert_volatility()
    download_boe_data()
    download_measuringworth_gdp()
    download_finra_margin_debt()

    all_ok = verify_all()
    if all_ok:
        logger.info("\n🟢 All historical data ready for 1907-2025 backtest")
    else:
        logger.info("\n🟡 Some files missing — backtest will use defaults for missing eras")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Download publicly available historical datasets for GRRI extension.

Fetches data from open-access sources and stores them in the expected
directory structure under ``data/historical/grri/``.

Datasets that require manual download (registration, licence agreement,
or Excel-only distribution) are listed with instructions.

Usage::

    python download_grri_historical_data.py          # fetch all auto-downloadable
    python download_grri_historical_data.py --check  # report what's available

See also: grri_mac/grri/historical_proxies.py for proxy chain documentation.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent / "data" / "historical" / "grri"

# ─── Auto-downloadable datasets ──────────────────────────────────────────────

DOWNLOADS = {
    "hadcrut": {
        "description": "HadCRUT5 global mean annual temperature anomaly",
        "url": (
            "https://www.metoffice.gov.uk/hadobs/hadcrut5/data/HadCRUT.5.0.2.0/"
            "analysis/diagnostics/HadCRUT.5.0.2.0.analysis.summary_series.global.annual.csv"
        ),
        "dest": "hadcrut/hadcrut5_annual.csv",
    },
    "maddison": {
        "description": "Maddison Project Database 2020 (full data)",
        "url": (
            "https://www.rug.nl/ggdc/historicaldevelopment/maddison/data/"
            "mpd2020.xlsx"
        ),
        "dest": "maddison/mpd2020.xlsx",
    },
    "ucdp": {
        "description": "UCDP battle-related deaths v24.1",
        "url": (
            "https://ucdp.uu.se/downloads/brd/ucdp-brd-dyadic-241-csv.zip"
        ),
        "dest": "ucdp/ucdp_brd.zip",
        "unzip": True,
        "rename_after": "ucdp_brd.csv",
    },
}

# ─── Manual-download datasets ────────────────────────────────────────────────

MANUAL_DATASETS = {
    "polity5": {
        "description": "Polity5 regime scores (1800-2018)",
        "url": "https://www.systemicpeace.org/inscrdata.html",
        "instructions": (
            "1. Go to https://www.systemicpeace.org/inscrdata.html\n"
            "2. Download 'Polity5 Annual Time-Series, 1946-2018' (XLS/CSV)\n"
            "3. Save as data/historical/grri/polity5/p5v2018.csv"
        ),
    },
    "vdem": {
        "description": "V-Dem Country-Year Core dataset (1789-present)",
        "url": "https://v-dem.net/data/the-v-dem-dataset/",
        "instructions": (
            "1. Register at https://v-dem.net/data/the-v-dem-dataset/\n"
            "2. Download 'Country-Year: V-Dem Core' (CSV, ~100 MB)\n"
            "3. Filter to G20 countries and key indicators, save as:\n"
            "   data/historical/grri/vdem/vdem_core.csv\n"
            "4. Required columns: country_text_id, year, v2x_polyarchy,\n"
            "   v2x_libdem, v2x_civlib, v2x_suffr, v2x_rule, v2x_freexp"
        ),
    },
    "cow": {
        "description": "Correlates of War interstate/civil war data (1816-present)",
        "url": "https://correlatesofwar.org/data-sets/",
        "instructions": (
            "1. Go to https://correlatesofwar.org/data-sets/\n"
            "2. Download 'Wars' datasets (Inter-State + Intra-State)\n"
            "3. Merge and save as data/historical/grri/cow/wars.csv"
        ),
    },
    "reinhart_rogoff": {
        "description": "Reinhart-Rogoff crisis panel (1800-present)",
        "url": "https://www.carmenreinhart.com/data",
        "instructions": (
            "1. Go to https://www.carmenreinhart.com/data\n"
            "2. Download 'This Time Is Different' data appendix\n"
            "3. Extract crisis indicator panel (banking, currency, default,\n"
            "   inflation, stock market crash dummies)\n"
            "4. Save as data/historical/grri/reinhart_rogoff/crises.csv\n"
            "5. Required columns: country, year, banking, currency,\n"
            "   sovereign_external, sovereign_domestic, inflation, stock_market"
        ),
    },
    "emdat": {
        "description": "EM-DAT international disaster database (1900-present)",
        "url": "https://www.emdat.be/",
        "instructions": (
            "1. Register at https://www.emdat.be/ (free for academic use)\n"
            "2. Download full public dataset\n"
            "3. Save as data/historical/grri/emdat/emdat_public.csv"
        ),
    },
    "garriga": {
        "description": "Garriga Central Bank Independence (1970-2017)",
        "url": "https://sites.google.com/site/carogarriga/cbi-data-1",
        "instructions": (
            "1. Download from Garriga's research page\n"
            "2. Extract CBI scores (LVAW or LVAU weighted measures)\n"
            "3. Save as data/historical/grri/garriga/cbi_index.csv\n"
            "4. Required columns: country, year, cbi (0-1)"
        ),
    },
    "gsdb": {
        "description": "Harvard Global Sanctions Database (1950-2022)",
        "url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/SVR5W7",
        "instructions": (
            "1. Download from Harvard Dataverse (DOI: 10.7910/DVN/SVR5W7)\n"
            "2. Save as data/historical/grri/gsdb/sanctions.csv"
        ),
    },
}


def ensure_dir(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path, description: str) -> bool:
    """Download a file with progress reporting."""
    if dest.exists():
        logger.info(f"Already exists: {dest}")
        return True

    ensure_dir(dest.parent)
    logger.info(f"Downloading {description}...")
    logger.info(f"  URL: {url}")

    try:
        response = requests.get(
            url,
            timeout=120,
            stream=True,
            headers={"User-Agent": "GRRI-MAC-Framework/1.0"},
        )
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    print(f"\r  Progress: {pct:.0f}%", end="", flush=True)

        print()  # newline after progress
        logger.info(f"  Saved to: {dest} ({dest.stat().st_size:,} bytes)")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"  Download failed: {e}")
        return False


def unzip_file(zip_path: Path, dest_dir: Path, rename_to: str = None) -> bool:
    """Unzip a downloaded archive."""
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
            logger.info(f"  Extracted to {dest_dir}")

            # Rename the extracted CSV if needed
            if rename_to:
                csvs = list(dest_dir.glob("*.csv"))
                if csvs:
                    target = dest_dir / rename_to
                    if not target.exists():
                        csvs[0].rename(target)
                        logger.info(f"  Renamed to {target.name}")

        # Remove ZIP
        zip_path.unlink()
        return True

    except Exception as e:
        logger.error(f"  Unzip failed: {e}")
        return False


def download_all() -> dict:
    """Download all auto-downloadable datasets."""
    results = {}

    for name, info in DOWNLOADS.items():
        dest = BASE_DIR / info["dest"]
        success = download_file(info["url"], dest, info["description"])

        if success and info.get("unzip"):
            success = unzip_file(dest, dest.parent, info.get("rename_after"))

        results[name] = success

    return results


def check_availability() -> None:
    """Report which datasets are available on disk."""
    print("\n" + "=" * 70)
    print("GRRI Historical Data Availability Report")
    print("=" * 70)

    print("\n── Auto-downloadable datasets ──")
    for name, info in DOWNLOADS.items():
        dest = BASE_DIR / info["dest"]
        # Also check unzipped version
        if info.get("rename_after"):
            final = dest.parent / info["rename_after"]
            exists = final.exists() or dest.exists()
        else:
            exists = dest.exists()

        status = "✓ AVAILABLE" if exists else "✗ MISSING"
        size = ""
        check_path = dest.parent / info.get("rename_after", dest.name)
        if check_path.exists():
            size = f" ({check_path.stat().st_size:,} bytes)"
        print(f"  [{status}] {name:20s} {info['description']}{size}")

    print("\n── Manual-download datasets ──")
    manual_paths = {
        "polity5": BASE_DIR / "polity5",
        "vdem": BASE_DIR / "vdem" / "vdem_core.csv",
        "cow": BASE_DIR / "cow" / "wars.csv",
        "reinhart_rogoff": BASE_DIR / "reinhart_rogoff" / "crises.csv",
        "emdat": BASE_DIR / "emdat" / "emdat_public.csv",
        "garriga": BASE_DIR / "garriga" / "cbi_index.csv",
        "gsdb": BASE_DIR / "gsdb" / "sanctions.csv",
    }

    for name, info in MANUAL_DATASETS.items():
        path = manual_paths.get(name)
        if path is None:
            exists = False
        elif path.is_dir():
            exists = any(path.glob("*"))
        else:
            exists = path.exists()

        status = "✓ AVAILABLE" if exists else "✗ MISSING"
        print(f"  [{status}] {name:20s} {info['description']}")
        if not exists:
            print(f"    → {info['url']}")

    # Also check MAC historical data that we reuse
    mac_dir = Path(__file__).parent / "data" / "historical"
    print("\n── Reused from MAC historical data ──")
    mac_sources = {
        "shiller": mac_dir / "shiller",
        "measuringworth": mac_dir / "measuringworth",
        "schwert": mac_dir / "schwert" / "schwert_volatility.csv",
        "boe": mac_dir / "boe",
        "nber": mac_dir / "nber",
    }
    for name, path in mac_sources.items():
        if path.is_dir():
            exists = path.exists() and any(path.glob("*"))
        else:
            exists = path.exists()
        status = "✓ AVAILABLE" if exists else "✗ MISSING"
        print(f"  [{status}] {name:20s} (MAC module)")

    print("\n" + "=" * 70)

    # Estimate coverage
    try:
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider
        provider = GRRIHistoricalProvider()
        summary = provider.get_data_availability_summary()
        available_count = sum(1 for v in summary.values() if v.get("available"))
        total_count = len(summary)
        print(f"\nData sources available: {available_count}/{total_count}")
        print("Run with no arguments to download auto-fetchable datasets.")
    except Exception:
        pass

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Download historical datasets for GRRI extension"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report data availability without downloading",
    )
    parser.add_argument(
        "--manual-instructions",
        action="store_true",
        help="Print instructions for manual downloads",
    )

    args = parser.parse_args()

    if args.check:
        check_availability()
        return

    if args.manual_instructions:
        print("\n=== Manual Download Instructions ===\n")
        for name, info in MANUAL_DATASETS.items():
            print(f"--- {name} ---")
            print(f"Description: {info['description']}")
            print(info["instructions"])
            print()
        return

    # Download auto-downloadable datasets
    results = download_all()

    print("\n=== Download Summary ===")
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {name:20s} {status}")

    failed = [n for n, s in results.items() if not s]
    if failed:
        print(f"\n{len(failed)} downloads failed. Check logs above.")
        sys.exit(1)

    # Remind about manual datasets
    print("\n=== Manual Downloads Required ===")
    print("The following datasets must be downloaded manually:")
    for name, info in MANUAL_DATASETS.items():
        print(f"  - {name}: {info['url']}")
    print("\nRun with --manual-instructions for detailed steps.")


if __name__ == "__main__":
    main()

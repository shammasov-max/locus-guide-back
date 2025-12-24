#!/usr/bin/env python3
"""
Download required GeoNames data files.

Usage:
    python scripts/download_geonames.py

Downloads:
    - cities15000.zip (cities with population > 15000)
    - alternateNamesV2.zip (alternate names in different languages)
    - countryInfo.txt (country information)
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

# GeoNames download URLs
GEONAMES_BASE_URL = "https://download.geonames.org/export/dump"

FILES_TO_DOWNLOAD = [
    {
        "url": f"{GEONAMES_BASE_URL}/cities15000.zip",
        "filename": "cities15000.zip",
        "extract": True,
    },
    {
        "url": f"{GEONAMES_BASE_URL}/alternateNamesV2.zip",
        "filename": "alternateNamesV2.zip",
        "extract": True,
    },
    {
        "url": f"{GEONAMES_BASE_URL}/countryInfo.txt",
        "filename": "countryInfo.txt",
        "extract": False,
    },
]


def get_data_dir() -> Path:
    """Get data directory path."""
    # Check environment variable first
    data_dir = os.environ.get("GEONAMES_DATA_DIR")
    if data_dir:
        return Path(data_dir)

    # Default to ./data relative to script or /app/data in container
    if os.path.exists("/app"):
        return Path("/app/data")
    return Path(__file__).parent.parent / "data"


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file with progress indicator."""
    print(f"Downloading {url}...")

    try:
        def reporthook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                sys.stdout.write(f"\r  Progress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, dest_path, reporthook)
        print()  # New line after progress
        return True

    except Exception as e:
        print(f"\nError downloading {url}: {e}")
        return False


def extract_zip(zip_path: Path, dest_dir: Path) -> bool:
    """Extract a zip file."""
    print(f"Extracting {zip_path.name}...")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        print(f"  Extracted to {dest_dir}")
        return True

    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
        return False


def main():
    """Main download function."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"GeoNames Data Downloader")
    print(f"========================")
    print(f"Data directory: {data_dir}")
    print()

    success_count = 0
    for file_info in FILES_TO_DOWNLOAD:
        filename = file_info["filename"]
        url = file_info["url"]
        dest_path = data_dir / filename

        # Check if already exists (for txt files, check extracted)
        if file_info["extract"]:
            txt_name = filename.replace(".zip", ".txt")
            if (data_dir / txt_name).exists():
                print(f"Skipping {filename} (already extracted)")
                success_count += 1
                continue

        # Download
        if not download_file(url, dest_path):
            continue

        # Extract if needed
        if file_info["extract"]:
            if extract_zip(dest_path, data_dir):
                # Remove zip after extraction
                dest_path.unlink()
                success_count += 1
        else:
            success_count += 1

    print()
    print(f"Downloaded {success_count}/{len(FILES_TO_DOWNLOAD)} files")

    # Verify required files exist
    required_files = ["cities15000.txt", "alternateNamesV2.txt", "countryInfo.txt"]
    missing = [f for f in required_files if not (data_dir / f).exists()]

    if missing:
        print(f"\nWARNING: Missing files: {', '.join(missing)}")
        return 1

    print("\nAll required files downloaded successfully!")
    print("\nNext step: Run 'python scripts/import_data.py' to import data into database")
    return 0


if __name__ == "__main__":
    sys.exit(main())

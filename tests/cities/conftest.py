"""City-specific test fixtures and helpers."""

import os
import subprocess
import pytest
from sqlalchemy import text


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (may require network, external services)"
    )

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/locus_guide_test"
)

# Known GeoNames IDs for assertions (real data from GeoNames)
MOSCOW_GEONAMEID = 524901      # pop ~12.5M, RU
BERLIN_GEONAMEID = 2950159     # pop ~3.4M, DE
PARIS_GEONAMEID = 2988507      # pop ~2.1M, FR
LONDON_GEONAMEID = 2643743     # pop ~7.5M, GB
TOKYO_GEONAMEID = 1850147      # pop ~8.3M, JP

# Coordinates for testing distance sorting
MOSCOW_COORDS = (55.75222, 37.61556)
BERLIN_COORDS = (52.52437, 13.41053)
PARIS_COORDS = (48.85341, 2.3488)


@pytest.fixture(scope="session")
def ensure_geonames_data(setup_test_database):
    """
    Ensure GeoNames data is loaded in test database.

    Checks if cities table has data, if not - runs import_data.py script.
    This fixture depends on setup_test_database to ensure schema exists.
    """
    from sqlalchemy import create_engine

    engine = create_engine(TEST_DATABASE_URL)

    with engine.connect() as conn:
        # Check if cities table has data
        result = conn.execute(text("SELECT COUNT(*) FROM cities"))
        count = result.scalar()

    if count == 0:
        # No data - need to run import script
        print(f"\nNo GeoNames data found in test DB. Running import_data.py...")

        # Check if data files exist
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        cities_file = os.path.join(data_dir, "cities15000.txt")

        if not os.path.exists(cities_file):
            # Need to download first
            print("Downloading GeoNames data...")
            subprocess.run(
                ["python", "scripts/download_geonames.py"],
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
                check=True
            )

        # Run import
        print("Importing GeoNames data into test database...")
        subprocess.run(
            ["python", "scripts/import_data.py"],
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
            check=True
        )

        # Verify import
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM cities"))
            count = result.scalar()
            print(f"Imported {count} cities into test database.")

    return count


@pytest.fixture
def known_cities():
    """Return dict of known GeoNames IDs for test assertions."""
    return {
        "moscow": MOSCOW_GEONAMEID,
        "berlin": BERLIN_GEONAMEID,
        "paris": PARIS_GEONAMEID,
        "london": LONDON_GEONAMEID,
        "tokyo": TOKYO_GEONAMEID,
    }


@pytest.fixture
def city_coords():
    """Return dict of city coordinates for distance testing."""
    return {
        "moscow": MOSCOW_COORDS,
        "berlin": BERLIN_COORDS,
        "paris": PARIS_COORDS,
    }

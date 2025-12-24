#!/usr/bin/env python3
"""
Import GeoNames data into PostgreSQL/PostGIS database.

Usage:
    python scripts/import_data.py

Imports:
    - countries from countryInfo.txt
    - cities from cities15000.txt
    - alternate names from alternateNamesV2.txt (filtered by language)
    - builds search index for prefix matching
"""

import os
import sys
from pathlib import Path
from typing import Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Supported languages for alternate names
SUPPORTED_LANGUAGES = {"en", "ru", "de"}

# Batch size for inserts
BATCH_SIZE = 5000


def get_data_dir() -> Path:
    """Get data directory path."""
    data_dir = os.environ.get("GEONAMES_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    if os.path.exists("/app"):
        return Path("/app/data")
    return Path(__file__).parent.parent / "data"


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/locus_guide")


def create_tables(session):
    """Create database tables."""
    print("Creating tables...")

    session.execute(text("""
        CREATE TABLE IF NOT EXISTS countries (
            iso VARCHAR(2) PRIMARY KEY,
            iso3 VARCHAR(3),
            name VARCHAR(200) NOT NULL,
            capital VARCHAR(200),
            continent VARCHAR(2)
        )
    """))

    session.execute(text("""
        CREATE TABLE IF NOT EXISTS cities (
            geonameid INTEGER PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            asciiname VARCHAR(200),
            country_code VARCHAR(2) NOT NULL REFERENCES countries(iso),
            admin1_code VARCHAR(20),
            population INTEGER DEFAULT 0,
            timezone VARCHAR(40),
            geom GEOMETRY(Point, 4326) NOT NULL
        )
    """))

    session.execute(text("""
        CREATE TABLE IF NOT EXISTS alternate_names (
            id INTEGER PRIMARY KEY,
            geonameid INTEGER NOT NULL REFERENCES cities(geonameid) ON DELETE CASCADE,
            language VARCHAR(7) NOT NULL,
            name VARCHAR(400) NOT NULL,
            is_preferred BOOLEAN DEFAULT FALSE,
            is_short BOOLEAN DEFAULT FALSE
        )
    """))

    session.execute(text("""
        CREATE TABLE IF NOT EXISTS city_search_index (
            id SERIAL PRIMARY KEY,
            geonameid INTEGER NOT NULL REFERENCES cities(geonameid) ON DELETE CASCADE,
            search_term VARCHAR(400) NOT NULL,
            search_term_lower VARCHAR(400) NOT NULL,
            language VARCHAR(7),
            source VARCHAR(20)
        )
    """))

    session.commit()
    print("  Tables created")


def create_indexes(session):
    """Create database indexes."""
    print("Creating indexes...")

    indexes = [
        ("idx_cities_geom", "CREATE INDEX IF NOT EXISTS idx_cities_geom ON cities USING GIST (geom)"),
        ("idx_cities_country", "CREATE INDEX IF NOT EXISTS idx_cities_country ON cities (country_code)"),
        ("idx_cities_population", "CREATE INDEX IF NOT EXISTS idx_cities_population ON cities (population DESC)"),
        ("idx_alt_names_geonameid", "CREATE INDEX IF NOT EXISTS idx_alt_names_geonameid ON alternate_names (geonameid)"),
        ("idx_alt_names_language", "CREATE INDEX IF NOT EXISTS idx_alt_names_language ON alternate_names (language)"),
        ("idx_search_geonameid", "CREATE INDEX IF NOT EXISTS idx_search_geonameid ON city_search_index (geonameid)"),
        ("idx_search_prefix", "CREATE INDEX IF NOT EXISTS idx_search_prefix ON city_search_index (search_term_lower text_pattern_ops)"),
    ]

    for name, sql in indexes:
        session.execute(text(sql))
        print(f"  Created index: {name}")

    session.commit()


def import_countries(session, data_dir: Path):
    """Import countries from countryInfo.txt."""
    print("Importing countries...")

    file_path = data_dir / "countryInfo.txt"
    if not file_path.exists():
        print(f"  ERROR: {file_path} not found")
        return

    # Clear existing data
    session.execute(text("DELETE FROM city_search_index"))
    session.execute(text("DELETE FROM alternate_names"))
    session.execute(text("DELETE FROM cities"))
    session.execute(text("DELETE FROM countries"))
    session.commit()

    countries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue

            iso = parts[0]
            iso3 = parts[1] if len(parts) > 1 else None
            name = parts[4] if len(parts) > 4 else parts[0]
            capital = parts[5] if len(parts) > 5 else None
            continent = parts[8] if len(parts) > 8 else None

            countries.append({
                "iso": iso,
                "iso3": iso3,
                "name": name,
                "capital": capital,
                "continent": continent,
            })

    # Batch insert
    for i in range(0, len(countries), BATCH_SIZE):
        batch = countries[i:i + BATCH_SIZE]
        for c in batch:
            session.execute(
                text("""
                    INSERT INTO countries (iso, iso3, name, capital, continent)
                    VALUES (:iso, :iso3, :name, :capital, :continent)
                    ON CONFLICT (iso) DO NOTHING
                """),
                c
            )
    session.commit()

    print(f"  Imported {len(countries)} countries")


def import_cities(session, data_dir: Path) -> Set[int]:
    """Import cities from cities15000.txt. Returns set of imported geoname IDs."""
    print("Importing cities...")

    file_path = data_dir / "cities15000.txt"
    if not file_path.exists():
        print(f"  ERROR: {file_path} not found")
        return set()

    geoname_ids = set()
    cities = []
    skipped = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 15:
                continue

            try:
                geonameid = int(parts[0])
                name = parts[1]
                asciiname = parts[2] if parts[2] else name
                lat = float(parts[4])
                lon = float(parts[5])
                country_code = parts[8]
                admin1_code = parts[10] if parts[10] else None
                population = int(parts[14]) if parts[14] else 0
                timezone = parts[17] if len(parts) > 17 else None

                geoname_ids.add(geonameid)
                cities.append({
                    "geonameid": geonameid,
                    "name": name,
                    "asciiname": asciiname,
                    "country_code": country_code,
                    "admin1_code": admin1_code,
                    "population": population,
                    "timezone": timezone,
                    "lat": lat,
                    "lon": lon,
                })
            except (ValueError, IndexError):
                skipped += 1
                continue

    # Batch insert
    for i in range(0, len(cities), BATCH_SIZE):
        batch = cities[i:i + BATCH_SIZE]
        for c in batch:
            session.execute(
                text("""
                    INSERT INTO cities (geonameid, name, asciiname, country_code, admin1_code, population, timezone, geom)
                    VALUES (:geonameid, :name, :asciiname, :country_code, :admin1_code, :population, :timezone,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    ON CONFLICT (geonameid) DO NOTHING
                """),
                c
            )
        if i % 10000 == 0 and i > 0:
            print(f"  Processed {i}/{len(cities)} cities...")

    session.commit()

    print(f"  Imported {len(cities)} cities (skipped {skipped})")
    return geoname_ids


def import_alternate_names(session, data_dir: Path, valid_geonames: Set[int]):
    """Import alternate names filtered by language and valid geoname IDs."""
    print("Importing alternate names (en, ru, de)...")

    file_path = data_dir / "alternateNamesV2.txt"
    if not file_path.exists():
        print(f"  ERROR: {file_path} not found")
        return

    names = []
    total_lines = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue

            try:
                alt_id = int(parts[0])
                geonameid = int(parts[1])
                language = parts[2]
                name = parts[3]
                is_preferred = parts[4] == "1" if len(parts) > 4 else False
                is_short = parts[5] == "1" if len(parts) > 5 else False

                # Filter by language and valid geonames
                if language not in SUPPORTED_LANGUAGES:
                    continue
                if geonameid not in valid_geonames:
                    continue

                names.append({
                    "id": alt_id,
                    "geonameid": geonameid,
                    "language": language,
                    "name": name,
                    "is_preferred": is_preferred,
                    "is_short": is_short,
                })

            except (ValueError, IndexError):
                continue

            # Insert in batches
            if len(names) >= BATCH_SIZE:
                for n in names:
                    session.execute(
                        text("""
                            INSERT INTO alternate_names (id, geonameid, language, name, is_preferred, is_short)
                            VALUES (:id, :geonameid, :language, :name, :is_preferred, :is_short)
                            ON CONFLICT (id) DO NOTHING
                        """),
                        n
                    )
                session.commit()
                names = []

            if total_lines % 1000000 == 0:
                print(f"  Processed {total_lines / 1000000:.0f}M lines...")

    # Insert remaining
    if names:
        for n in names:
            session.execute(
                text("""
                    INSERT INTO alternate_names (id, geonameid, language, name, is_preferred, is_short)
                    VALUES (:id, :geonameid, :language, :name, :is_preferred, :is_short)
                    ON CONFLICT (id) DO NOTHING
                """),
                n
            )
        session.commit()

    result = session.execute(text("SELECT COUNT(*) FROM alternate_names"))
    count = result.scalar()
    print(f"  Imported {count} alternate names")


def build_search_index(session):
    """Build search index from cities and alternate names."""
    print("Building search index...")

    # Insert from city names
    session.execute(text("""
        INSERT INTO city_search_index (geonameid, search_term, search_term_lower, language, source)
        SELECT geonameid, name, lower(name), NULL, 'name'
        FROM cities
    """))

    # Insert from ascii names (if different)
    session.execute(text("""
        INSERT INTO city_search_index (geonameid, search_term, search_term_lower, language, source)
        SELECT geonameid, asciiname, lower(asciiname), NULL, 'asciiname'
        FROM cities
        WHERE asciiname IS NOT NULL AND lower(asciiname) != lower(name)
    """))

    # Insert from alternate names
    session.execute(text("""
        INSERT INTO city_search_index (geonameid, search_term, search_term_lower, language, source)
        SELECT geonameid, name, lower(name), language, 'alternate'
        FROM alternate_names
    """))

    session.commit()

    result = session.execute(text("SELECT COUNT(*) FROM city_search_index"))
    count = result.scalar()
    print(f"  Created {count} search index entries")


def main():
    """Main import function."""
    print("=" * 50)
    print("GeoNames Data Import")
    print("=" * 50)

    data_dir = get_data_dir()
    print(f"Data directory: {data_dir}")

    db_url = get_database_url()
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print()

    # Check required files
    required_files = ["cities15000.txt", "alternateNamesV2.txt", "countryInfo.txt"]
    missing = [f for f in required_files if not (data_dir / f).exists()]
    if missing:
        print(f"ERROR: Missing required files: {', '.join(missing)}")
        print("Run 'python scripts/download_geonames.py' first")
        return 1

    # Create engine and session
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        try:
            # Create tables
            create_tables(session)

            # Import data
            import_countries(session, data_dir)
            geoname_ids = import_cities(session, data_dir)
            import_alternate_names(session, data_dir, geoname_ids)

            # Build search index
            build_search_index(session)

            # Create indexes
            create_indexes(session)

            print()
            print("=" * 50)
            print("Import completed successfully!")
            print("=" * 50)

            # Print stats
            for table in ["countries", "cities", "alternate_names", "city_search_index"]:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table}: {count:,} rows")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            return 1

    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())

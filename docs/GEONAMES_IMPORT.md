# GeoNames Data Import Specification

Import specification for populating geo domain tables from GeoNames dump files.

**Source:** https://download.geonames.org/export/dump/

---

## Table Naming

All tables use the `geo_names_` prefix:

| Table | Description |
|-------|-------------|
| `geo_names_countries` | Country reference data |
| `geo_names_cities` | City reference data with PostGIS coordinates |
| `geo_names_admin1_codes` | Region/state names |
| `geo_names_city_search_index` | Denormalized search index (includes alternate names) |

**Note:** `alternateNamesV2.txt` is streamed during import and inserted directly into `geo_names_city_search_index`. No separate `geo_names_alternate_names` table is created.

These tables are **external seed data** and do NOT follow project conventions (see `docs/domains/geo.md`).

---

## Source Files

| File | URL | Size | Records | Description |
|------|-----|------|---------|-------------|
| `cities15000.zip` | `/dump/cities15000.zip` | ~2 MB | ~26K | Cities with population > 15,000 |
| `countryInfo.txt` | `/dump/countryInfo.txt` | ~30 KB | ~250 | Country metadata |
| `alternateNamesV2.zip` | `/dump/alternateNamesV2.zip` | ~200 MB | ~15M | Alternate names (all languages) |
| `admin1CodesASCII.txt` | `/dump/admin1CodesASCII.txt` | ~150 KB | ~4K | First-level admin divisions |

**Encoding:** UTF-8
**Delimiter:** Tab (`\t`)
**Header:** None (raw data, comments start with `#`)

---

## File Formats

### countryInfo.txt

```
# Lines starting with # are comments
ISO	ISO3	ISO-Numeric	fips	Country	Capital	Area(km²)	Population	Continent	tld	CurrencyCode	CurrencyName	Phone	PostalCodeFormat	PostalCodeRegex	Languages	geonameid	neighbours	EquivalentFipsCode
AD	AND	020	AN	Andorra	Andorra la Vella	468.00	84000	EU	.ad	EUR	Euro	376	AD###	^(?:AD)*(\d{3})$	ca	3041565	ES,FR
```

**Fields:** 19 columns, tab-separated

---

### cities15000.txt

```
geonameid	name	asciiname	alternatenames	latitude	longitude	feature_class	feature_code	country_code	cc2	admin1_code	admin2_code	admin3_code	admin4_code	population	elevation	dem	timezone	modification_date
2988507	Paris	Paris	Bariz,Lutetia,...	48.85341	2.3488	P	PPLC	FR		11	75	751	75056	2138551		42	Europe/Paris	2024-10-08
```

**Fields:** 19 columns, tab-separated
**Note:** Field 3 `alternatenames` is comma-separated legacy data (skip, use alternateNamesV2.txt instead)

---

### alternateNamesV2.txt

```
alternateNameId	geonameid	isolanguage	alternate_name	isPreferredName	isShortName	isColloquial	isHistoric	from	to
1558311	2988507	ru	Париж	1
1558320	2988507	en	Paris	1
```

**Fields:** 10 columns, tab-separated
**Boolean fields:** `1` = true, empty = false
**Special isolanguage values:**
- `link` — URL/link
- `wkdt` — Wikidata ID
- `abbr` — abbreviation
- `post` — postal code
- `iata` — airport code
- `icao` — airport code
- `unlc` — UN/LOCODE

---

### admin1CodesASCII.txt

```
code	name	name_ascii	geonameid
US.CA	California	California	5332921
FR.75	Paris	Paris	2988507
```

**Fields:** 4 columns, tab-separated
**Code format:** `{country_code}.{admin1_code}`

---

## Download Script Specification

**Script:** `scripts/download_geonames.py`

### Requirements

```python
# Standard library only
import os
import sys
import zipfile
import urllib.request
from pathlib import Path
```

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GEONAMES_DATA_DIR` | `./data` | Directory for downloaded files |

### Behavior

1. Create data directory if not exists
2. For each file:
   - Skip if already extracted (`.txt` exists)
   - Download with progress indicator
   - Extract ZIP files, delete ZIP after extraction
3. Verify all required files exist
4. Exit with code 0 on success, 1 on failure

### Files to Download

```python
FILES = [
    {"url": "https://download.geonames.org/export/dump/cities15000.zip", "extract": True},
    {"url": "https://download.geonames.org/export/dump/alternateNamesV2.zip", "extract": True},
    {"url": "https://download.geonames.org/export/dump/countryInfo.txt", "extract": False},
    {"url": "https://download.geonames.org/export/dump/admin1CodesASCII.txt", "extract": False},
]
```

---

## Import Script Specification

**Script:** `scripts/import_data.py`

### Requirements

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
```

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/locus_guide` | Database connection |
| `GEONAMES_DATA_DIR` | `./data` | Directory with source files |
| `BATCH_SIZE` | `5000` | Insert batch size |

### Import Order (Dependencies)

```
1. geo_names_countries        ← no dependencies
2. geo_names_admin1_codes     ← no dependencies
3. geo_names_cities           ← depends on geo_names_countries (FK)
4. geo_names_city_search_index ← built from cities + alternateNamesV2.txt stream
```

### Step-by-Step Process

#### Step 1: Create Tables

```sql
-- Enable extensions (if not exists)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create tables (DDL from geo.md)
CREATE TABLE IF NOT EXISTS geo_names_countries (...);
CREATE TABLE IF NOT EXISTS geo_names_admin1_codes (...);
CREATE TABLE IF NOT EXISTS geo_names_cities (...);
CREATE TABLE IF NOT EXISTS geo_names_city_search_index (...);
```

#### Step 2: Truncate Existing Data

```sql
-- Order matters due to FK constraints
TRUNCATE geo_names_city_search_index CASCADE;
TRUNCATE geo_names_cities CASCADE;
TRUNCATE geo_names_admin1_codes CASCADE;
TRUNCATE geo_names_countries CASCADE;
```

#### Step 3: Import Countries (~250 rows)

```python
# Parse countryInfo.txt
# Skip lines starting with #
# Split by \t, map to columns
# INSERT with ON CONFLICT DO NOTHING
```

**Estimated time:** < 1 second

#### Step 4: Import Admin1 Codes (~4K rows)

```python
# Parse admin1CodesASCII.txt
# Split by \t, map to columns
# INSERT with ON CONFLICT DO NOTHING
```

**Estimated time:** < 1 second

#### Step 5: Import Cities (~26K rows)

```python
# Parse cities15000.txt
# Skip field[3] (alternatenames)
# Compute coordinates from lat/lon:
#   ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
# Batch insert, 5000 rows at a time
# Track geonameid set for filtering alternate_names
```

**SQL:**
```sql
INSERT INTO geo_names_cities (geonameid, name, asciiname, latitude, longitude,
                    feature_class, feature_code, country_code, cc2,
                    admin1_code, admin2_code, admin3_code, admin4_code,
                    population, elevation, dem, timezone, modification_date,
                    coordinates)
VALUES (:geonameid, :name, :asciiname, :latitude, :longitude,
        :feature_class, :feature_code, :country_code, :cc2,
        :admin1_code, :admin2_code, :admin3_code, :admin4_code,
        :population, :elevation, :dem, :timezone, :modification_date,
        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326))
ON CONFLICT (geonameid) DO NOTHING
```

**Estimated time:** ~5 seconds

#### Step 6: Build Search Index (from cities + alternateNamesV2.txt)

```sql
-- From city names
INSERT INTO geo_names_city_search_index (geonameid, search_term, isolanguage, source)
SELECT geonameid, name, NULL, 'name'
FROM geo_names_cities;

-- From ASCII names (if different from name)
INSERT INTO geo_names_city_search_index (geonameid, search_term, isolanguage, source)
SELECT geonameid, asciiname, NULL, 'asciiname'
FROM geo_names_cities
WHERE asciiname IS NOT NULL
  AND lower(asciiname) != lower(name);

-- From alternateNamesV2.txt (streamed, not persisted as table)
-- Filter: geonameid IN imported_cities
-- Filter: isolanguage IN SUPPORTED_LANGUAGES OR isolanguage IS NULL
-- Skip special codes: link, wkdt, abbr, post, iata, icao, unlc
-- Batch insert 10000 rows at a time
```

```python
# Stream alternateNamesV2.txt
for line in open("alternateNamesV2.txt", encoding="utf-8"):
    fields = line.strip().split("\t")
    geonameid = int(fields[1])
    isolanguage = fields[2] if fields[2] else None
    alternate_name = fields[3]

    # Skip if city not in imported set
    if geonameid not in imported_city_ids:
        continue
    # Skip special codes
    if isolanguage in ("link", "wkdt", "abbr", "post", "iata", "icao", "unlc"):
        continue
    # Filter to supported languages (or NULL for unnamed)
    if isolanguage and isolanguage not in SUPPORTED_LANGUAGES:
        continue

    batch.append((geonameid, alternate_name, isolanguage, "alternate"))
```

**Estimated time:** ~3-5 minutes (15M lines → ~300K inserts after filtering)
**Memory note:** Stream file, don't load entirely into memory

#### Step 7: Create Indexes

```sql
-- Spatial
CREATE INDEX IF NOT EXISTS idx_geo_names_cities_coordinates
  ON geo_names_cities USING GIST (coordinates);

-- B-Tree
CREATE INDEX IF NOT EXISTS idx_geo_names_cities_country_code
  ON geo_names_cities (country_code);
CREATE INDEX IF NOT EXISTS idx_geo_names_cities_population
  ON geo_names_cities (population DESC);
CREATE INDEX IF NOT EXISTS idx_geo_names_cities_feature_code
  ON geo_names_cities (feature_code);
CREATE INDEX IF NOT EXISTS idx_geo_names_search_geonameid
  ON geo_names_city_search_index (geonameid);

-- Text pattern (for LIKE 'prefix%')
CREATE INDEX IF NOT EXISTS idx_geo_names_search_term_lower
  ON geo_names_city_search_index (lower(search_term) text_pattern_ops);

-- GIN trigram for fuzzy search
CREATE INDEX IF NOT EXISTS idx_geo_names_search_term_trgm
  ON geo_names_city_search_index USING GIN (lower(search_term) gin_trgm_ops);
```

**Estimated time:** ~1-2 minutes

#### Step 8: Vacuum Analyze

```sql
VACUUM ANALYZE geo_names_countries;
VACUUM ANALYZE geo_names_admin1_codes;
VACUUM ANALYZE geo_names_cities;
VACUUM ANALYZE geo_names_city_search_index;
```

**Estimated time:** ~1 minute

---

## Expected Row Counts

| Table | Rows | Size |
|-------|------|------|
| `geo_names_countries` | ~250 | ~50 KB |
| `geo_names_admin1_codes` | ~4,000 | ~200 KB |
| `geo_names_cities` | ~26,000 | ~5 MB |
| `geo_names_city_search_index` | ~300,000* | ~50 MB |

*Includes city names + ASCII names + alternate names filtered to 30 languages

---

## Data Refresh Strategy

### Full Refresh (Recommended)

```bash
# 1. Download fresh data
python scripts/download_geonames.py --force

# 2. Re-import (truncates existing)
python scripts/import_data.py
```

**Frequency:** Monthly or on-demand
**Downtime:** ~10-15 minutes

### Incremental Update (Future)

GeoNames provides daily diff files:
- `modifications-YYYY-MM-DD.txt` — new/modified records
- `deletes-YYYY-MM-DD.txt` — deleted records

**Not implemented** — full refresh is simpler for ~26K cities

---

## Error Handling

### Download Errors

- Retry 3 times with exponential backoff
- Log failed URLs
- Exit with code 1

### Import Errors

- Wrap in transaction
- Rollback on failure
- Log line number and error
- Exit with code 1

### Common Issues

| Issue | Solution |
|-------|----------|
| `UnicodeDecodeError` | Ensure UTF-8 encoding when opening files |
| FK violation | Check import order, countries before cities |
| Memory error | Use streaming/generator for large files |
| Slow inserts | Disable indexes during import, recreate after |

---

## CLI Usage

```bash
# Download data
python scripts/download_geonames.py
# Output: data/cities15000.txt, data/alternateNamesV2.txt, etc.

# Import to database
python scripts/import_data.py
# Output:
#   Importing geo_names_countries... 250 rows
#   Importing geo_names_admin1_codes... 4,012 rows
#   Importing geo_names_cities... 26,437 rows
#   Building geo_names_city_search_index...
#     From cities: 52,874 rows
#     Streaming alternateNamesV2.txt: 15,234,567 lines → 247,582 rows (filtered)
#   Creating indexes...
#   Vacuum analyze...
#   Done! Total: ~6 minutes

# With custom settings
GEONAMES_DATA_DIR=/path/to/data \
DATABASE_URL=postgresql://user:pass@host:5432/db \
python scripts/import_data.py
```

---

## Docker Integration

```yaml
# docker-compose.yml
services:
  import-geonames:
    build: .
    command: >
      sh -c "python scripts/download_geonames.py &&
             python scripts/import_data.py"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/locus_guide
      - GEONAMES_DATA_DIR=/app/data
    volumes:
      - geonames-data:/app/data
    depends_on:
      - db

volumes:
  geonames-data:
```

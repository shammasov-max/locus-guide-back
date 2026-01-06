# Geo Domain

City autocomplete with i18n + distance sort + typo tolerance. Based on GeoNames data dumps.

**Source:** https://download.geonames.org/export/dump/

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Table count | **4 tables** | `alternate_names` not persisted — parsed during import only |
| Language scope | **Top 30 languages** | Reduces index from 550K → ~300K rows |
| Search strategy | **Prefix + fuzzy fallback** | B-tree for speed, pg_trgm for typo tolerance |
| Typo tolerance | **Yes (pg_trgm)** | Fuzzy matching for queries ≥3 chars |
| Language priority | **User's lang first** | Russian names rank higher for `lang=ru` |
| Country filter | **No** | Global search only |

---

## Naming Convention

All GeoNames tables use the `geo_names_` prefix to distinguish them from application domain tables.

| Table | Rows | Size | Purpose |
|-------|------|------|---------|
| `geo_names_countries` | 250 | 50KB | Country names for display |
| `geo_names_admin1_codes` | 4K | 200KB | Region names ("California") |
| `geo_names_cities` | 26K | 5MB | Core city data + PostGIS |
| `geo_names_city_search_index` | ~300K | 50MB | Search index (30 languages) |

**Not persisted:** `geo_names_alternate_names` — parsed during import, inserted directly into search_index.

---

## Supported Languages (Top 30)

```python
SUPPORTED_LANGUAGES = {
    # Major European
    'en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'uk', 'ru',
    # Asian
    'zh', 'zh-CN', 'zh-TW', 'ja', 'ko', 'vi', 'th', 'id', 'ms',
    # Middle East / South Asia
    'ar', 'fa', 'tr', 'hi', 'bn',
    # Other major
    'sv', 'da', 'no', 'fi', 'cs', 'el'
}
```

Filter applied during import: `isolanguage IN SUPPORTED_LANGUAGES OR isolanguage IS NULL`

---

## Exceptions to Project Rules

These tables are **external reference data** imported from GeoNames. They do NOT follow project conventions:

| Project Rule | GeoNames Exception | Reason |
|--------------|-------------------|--------|
| BigInt PK for entities | Integer PK (geonameid) | Match GeoNames IDs exactly |
| `created_at`/`updated_at` timestamps | `modification_date` only | GeoNames provides single date |
| Snake_case column names | Match GeoNames field names | Traceability to source |
| CHAR(2) → String(2) in SQLAlchemy | Keep as-is | Fixed-length ISO codes |

These tables are **read-only seed data** — no application writes, only periodic refresh from GeoNames dumps.

---

## ERD (4 Tables)

```
┌─────────────────────────────────────────────────────────────────┐
│                      geo_names_countries                         │
│ Source: countryInfo.txt (~250 rows, 50KB)                        │
├─────────────────────────────────────────────────────────────────┤
│ iso               │ CHAR(2) PK        │ "US", "RU", "FR"         │
│ iso3              │ CHAR(3)?          │ "USA", "RUS", "FRA"      │
│ iso_numeric       │ SMALLINT?         │ 840                      │
│ fips              │ VARCHAR(3)?       │ "US"                     │
│ name              │ VARCHAR(200)!     │ "United States"          │
│ capital           │ VARCHAR(200)?     │ "Washington"             │
│ area              │ NUMERIC(10,2)?    │ 9629091.00 (km²)         │
│ population        │ BIGINT?           │ 331002651                │
│ continent         │ CHAR(2)?          │ NA, EU, AS, AF, OC, SA, AN│
│ tld               │ VARCHAR(10)?      │ ".us"                    │
│ currency_code     │ CHAR(3)?          │ "USD"                    │
│ currency_name     │ VARCHAR(50)?      │ "Dollar"                 │
│ phone             │ VARCHAR(20)?      │ "1"                      │
│ postal_code_format│ VARCHAR(100)?     │ "#####-####"             │
│ postal_code_regex │ VARCHAR(255)?     │ "^\d{5}(-\d{4})?$"       │
│ languages         │ VARCHAR(200)?     │ "en-US,es-US,haw"        │
│ geonameid         │ INTEGER?          │ 6252001                  │
│ neighbours        │ VARCHAR(100)?     │ "CA,MX,CU"               │
│ equivalent_fips   │ VARCHAR(10)?      │ —                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │ 1:N (country_code → iso)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        geo_names_cities                          │
│ Source: cities15000.txt (~26K rows, 5MB)                         │
├─────────────────────────────────────────────────────────────────┤
│ geonameid         │ INTEGER PK        │ 5391959                  │
│ name              │ VARCHAR(200)!     │ "San Francisco"          │
│ asciiname         │ VARCHAR(200)?     │ "San Francisco"          │
│ latitude          │ FLOAT!            │ 37.7749                  │
│ longitude         │ FLOAT!            │ -122.4194                │
│ feature_class     │ CHAR(1)?          │ "P" (populated place)    │
│ feature_code      │ VARCHAR(10)?      │ "PPLA2"                  │
│ country_code      │ CHAR(2)! FK*      │ "US"                     │
│ cc2               │ VARCHAR(200)?     │ alt country codes        │
│ admin1_code       │ VARCHAR(20)?      │ "CA"                     │
│ admin2_code       │ VARCHAR(80)?      │ "075" (county)           │
│ admin3_code       │ VARCHAR(20)?      │ —                        │
│ admin4_code       │ VARCHAR(20)?      │ —                        │
│ population        │ BIGINT DEF=0*     │ 883305                   │
│ elevation         │ INTEGER?          │ 16 (meters)              │
│ dem               │ INTEGER?          │ digital elevation model  │
│ timezone          │ VARCHAR(40)?      │ "America/Los_Angeles"    │
│ modification_date │ DATE?             │ 2024-10-08               │
│ coordinates       │ GEOMETRY! GIST*   │ PostGIS Point(4326)      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
         ▼                                 ▼
┌─────────────────────────┐  ┌────────────────────────────────────┐
│  geo_names_admin1_codes │  │     geo_names_city_search_index     │
│  (~4K rows, 200KB)      │  │  (~300K rows, 50MB + indexes)       │
├─────────────────────────┤  ├────────────────────────────────────┤
│ code   │VARCHAR(20) PK  │  │ id          │ SERIAL PK             │
│ name   │VARCHAR(255)!   │  │ geonameid   │ INTEGER! FK* CASCADE  │
│ asciiname│VARCHAR(255)? │  │ search_term │ VARCHAR(400)!         │
│ geonameid│INTEGER?      │  │ isolanguage │ VARCHAR(7)?           │
├─────────────────────────┤  │ source      │ VARCHAR(20)?          │
│ Format: "US.CA"         │  ├────────────────────────────────────┤
│ Join: country_code ||   │  │ INDEXES:                           │
│   '.' || admin1_code    │  │  • B-tree (prefix): text_pattern_ops│
└─────────────────────────┘  │  • GIN (fuzzy): gin_trgm_ops       │
                             └────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
                         DATA FLOW (Import)
═══════════════════════════════════════════════════════════════════

countryInfo.txt ──────────────────► geo_names_countries (250)
admin1CodesASCII.txt ─────────────► geo_names_admin1_codes (4K)
cities15000.txt ──────────────────► geo_names_cities (26K)
                                          │
alternateNamesV2.txt ─────────────────────┼──► geo_names_city_search_index
(15M → 300K, filtered to 30 langs)        │    (built from cities + alternates)
                                          ▼
```

*Symbols: `!`=NOT NULL, `?`=nullable, `*`=indexed, `PK`=primary key, `FK`=foreign key*

**Note:** `geo_names_alternate_names` is NOT persisted — data is parsed during import and inserted directly into `search_index`.

---

## Data Type Mappings

### geo_names_countries (countryInfo.txt)

| # | GeoNames Field | Column | PostgreSQL | SQLAlchemy | Notes |
|---|----------------|--------|------------|------------|-------|
| 0 | ISO | `iso` | `CHAR(2)` | `String(2)` | PK, ISO 3166-1 alpha-2 |
| 1 | ISO3 | `iso3` | `CHAR(3)` | `String(3)` | ISO 3166-1 alpha-3 |
| 2 | ISO-Numeric | `iso_numeric` | `SMALLINT` | `SmallInteger` | ISO 3166-1 numeric |
| 3 | fips | `fips` | `VARCHAR(3)` | `String(3)` | FIPS code |
| 4 | Country | `name` | `VARCHAR(200)` | `String(200)` | NOT NULL |
| 5 | Capital | `capital` | `VARCHAR(200)` | `String(200)` | Capital city |
| 6 | Area(km²) | `area` | `NUMERIC(10,2)` | `Numeric(10,2)` | Land area |
| 7 | Population | `population` | `BIGINT` | `BigInteger` | Total pop |
| 8 | Continent | `continent` | `CHAR(2)` | `String(2)` | AF,AS,EU,NA,OC,SA,AN |
| 9 | tld | `tld` | `VARCHAR(10)` | `String(10)` | Top-level domain |
| 10 | CurrencyCode | `currency_code` | `CHAR(3)` | `String(3)` | ISO 4217 |
| 11 | CurrencyName | `currency_name` | `VARCHAR(50)` | `String(50)` | Currency name |
| 12 | Phone | `phone` | `VARCHAR(20)` | `String(20)` | Phone prefix |
| 13 | PostalCodeFormat | `postal_code_format` | `VARCHAR(100)` | `String(100)` | Postal format |
| 14 | PostalCodeRegex | `postal_code_regex` | `VARCHAR(255)` | `String(255)` | Postal regex |
| 15 | Languages | `languages` | `VARCHAR(200)` | `String(200)` | Comma-separated |
| 16 | geonameid | `geonameid` | `INTEGER` | `Integer` | GeoNames ref |
| 17 | neighbours | `neighbours` | `VARCHAR(100)` | `String(100)` | Neighbor ISOs |
| 18 | EquivalentFipsCode | `equivalent_fips` | `VARCHAR(10)` | `String(10)` | Equiv FIPS |

---

### geo_names_cities (cities15000.txt)

| # | GeoNames Field | Column | PostgreSQL | SQLAlchemy | Notes |
|---|----------------|--------|------------|------------|-------|
| 0 | geonameid | `geonameid` | `INTEGER` | `Integer` | PK |
| 1 | name | `name` | `VARCHAR(200)` | `String(200)` | NOT NULL |
| 2 | asciiname | `asciiname` | `VARCHAR(200)` | `String(200)` | ASCII version |
| 3 | alternatenames | — | — | — | ❌ SKIP (use table) |
| 4 | latitude | `latitude` | `DOUBLE PRECISION` | `Float` | -90 to 90 |
| 5 | longitude | `longitude` | `DOUBLE PRECISION` | `Float` | -180 to 180 |
| 6 | feature class | `feature_class` | `CHAR(1)` | `String(1)` | P=populated |
| 7 | feature code | `feature_code` | `VARCHAR(10)` | `String(10)` | PPL/PPLA/PPLC |
| 8 | country code | `country_code` | `CHAR(2)` | `String(2)` | FK, NOT NULL |
| 9 | cc2 | `cc2` | `VARCHAR(200)` | `String(200)` | Alt country codes |
| 10 | admin1 code | `admin1_code` | `VARCHAR(20)` | `String(20)` | State/region |
| 11 | admin2 code | `admin2_code` | `VARCHAR(80)` | `String(80)` | County/district |
| 12 | admin3 code | `admin3_code` | `VARCHAR(20)` | `String(20)` | — |
| 13 | admin4 code | `admin4_code` | `VARCHAR(20)` | `String(20)` | — |
| 14 | population | `population` | `BIGINT` | `BigInteger` | DEFAULT 0 |
| 15 | elevation | `elevation` | `INTEGER` | `Integer` | Meters |
| 16 | dem | `dem` | `INTEGER` | `Integer` | Digital elev model |
| 17 | timezone | `timezone` | `VARCHAR(40)` | `String(40)` | IANA timezone |
| 18 | modification date | `modification_date` | `DATE` | `Date` | Last modified |
| — | (computed) | `coordinates` | `GEOMETRY(Point,4326)` | `Geometry('POINT',4326)` | PostGIS GIST |

**Note:** `alternatenames` (field 3) is a comma-separated legacy field. Use the normalized `geo_names_alternate_names` table from `alternateNamesV2.txt` instead.

**Computed column:** `coordinates` is created from `ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)`

---

### alternateNamesV2.txt (Parsed, Not Persisted)

This file is parsed during import but NOT stored as a table. Relevant fields are inserted directly into `geo_names_city_search_index`.

| # | GeoNames Field | Used | Notes |
|---|----------------|------|-------|
| 0 | alternateNameId | No | — |
| 1 | geonameid | Yes | FK to cities |
| 2 | isolanguage | Yes | BCP 47, filtered to 30 languages |
| 3 | alternate_name | Yes | Inserted into search_index.search_term |
| 4-9 | metadata | No | is_preferred, is_short, etc. — not needed for autocomplete |

**Language codes (BCP 47):**
- 2-letter: `en`, `ru`, `de`, `fr`, `es`, `zh`, `ja`, `ko`
- Extended: `zh-CN`, `zh-TW`, `pt-BR` (up to 7 chars)
- Special codes skipped: `link`, `wkdt`, `abbr`, `post`, `iata`, `icao`, `unlc`

---

### geo_names_admin1_codes (admin1CodesASCII.txt)

| # | GeoNames Field | Column | PostgreSQL | SQLAlchemy | Notes |
|---|----------------|--------|------------|------------|-------|
| 0 | code | `code` | `VARCHAR(20)` | `String(20)` | PK, format: CC.XX |
| 1 | name | `name` | `VARCHAR(255)` | `String(255)` | Unicode name |
| 2 | name ascii | `asciiname` | `VARCHAR(255)` | `String(255)` | ASCII name |
| 3 | geonameid | `geonameid` | `INTEGER` | `Integer` | GeoNames ref |

**Code format:** `{country_code}.{admin1_code}` (e.g., `US.CA`, `FR.75`, `RU.MOW`)

---

### geo_names_city_search_index (Denormalized)

Computed table for efficient prefix search. Built from `geo_names_cities` + `geo_names_alternate_names`.

| Column | PostgreSQL | SQLAlchemy | Notes |
|--------|------------|------------|-------|
| `id` | `SERIAL` | `Integer` | PK, auto-increment |
| `geonameid` | `INTEGER` | `Integer` | FK→geo_names_cities, CASCADE |
| `search_term` | `VARCHAR(400)` | `String(400)` | Original text |
| `isolanguage` | `VARCHAR(7)` | `String(7)` | Source language (NULL for city.name) |
| `source` | `VARCHAR(20)` | `String(20)` | `name`/`asciiname`/`alternate` |

---

## Indexes

### Required Extensions

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Spatial Indexes (GIST)

```sql
CREATE INDEX idx_geo_names_cities_coordinates
  ON geo_names_cities USING GIST (coordinates);
```

### B-Tree Indexes

```sql
-- Country lookups
CREATE INDEX idx_geo_names_cities_country_code
  ON geo_names_cities (country_code);

-- Population sorting
CREATE INDEX idx_geo_names_cities_population
  ON geo_names_cities (population DESC);

-- Search index lookups
CREATE INDEX idx_geo_names_search_geonameid
  ON geo_names_city_search_index (geonameid);
```

### Dual Search Strategy Indexes

```sql
-- B-tree for fast prefix search (LIKE 'query%')
-- Used first, ~5ms on 300K rows
CREATE INDEX idx_geo_names_search_term_prefix
  ON geo_names_city_search_index (lower(search_term) text_pattern_ops);

-- GIN trigram for fuzzy/typo matching (similarity)
-- Used as fallback when prefix returns <3 results
CREATE INDEX idx_geo_names_search_term_trgm
  ON geo_names_city_search_index USING GIN (lower(search_term) gin_trgm_ops);
```

**Query strategy:**
1. First try prefix match (fast, uses B-tree)
2. If <3 results AND query ≥3 chars, fallback to trigram similarity

---

## API

**Base:** `/api/v1/geo`

**Full OpenAPI spec:** [`docs/api/openapi.yaml`](../api/openapi.yaml)

| Method | Path | Auth | Params | Returns |
|--------|------|------|--------|---------|
| GET | `/autocomplete` | - | q! lang lat lon limit | AutocompleteResp |
| GET | `/languages` | - | - | {languages[], default} |

### Parameters

| Param | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `q` | string | Yes | 1-200 chars | Search query |
| `lang` | string | No | BCP 47 | User's language (prioritizes results) |
| `lat` | float | No | -90..90 | User latitude (for distance sort) |
| `lon` | float | No | -180..180 | User longitude |
| `limit` | int | No | 1-50, def:10 | Max results |

### Response

```json
{
  "query": "san fran",
  "lang": "en",
  "user_location": { "lat": 37.7, "lon": -122.4 },
  "count": 3,
  "cities": [
    {
      "geoname_id": 5391959,
      "name": "San Francisco",
      "local_name": "San Francisco",
      "admin1_name": "California",
      "country_code": "US",
      "country_name": "United States",
      "population": 883305,
      "lat": 37.7749,
      "lon": -122.4194,
      "distance_km": 12.5,
      "timezone": "America/Los_Angeles"
    }
  ]
}
```

### CityResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `geoname_id` | int | GeoNames ID |
| `name` | string | Primary city name |
| `local_name` | string | Name in user's language (if available) |
| `admin1_name` | string? | Region name ("California", "Île-de-France") |
| `country_code` | string | ISO 3166-1 alpha-2 ("US", "FR") |
| `country_name` | string? | Country name ("United States") |
| **`population`** | int | City population |
| **`lat`** | float | Latitude (-90 to 90) |
| **`lon`** | float | Longitude (-180 to 180) |
| `distance_km` | float? | Distance from user (if lat/lon provided) |
| `timezone` | string? | IANA timezone ("America/Los_Angeles") |

### Sorting

1. **Distance ASC** (if lat/lon provided)
2. **Population DESC** (fallback)

### Errors

| Code | Condition |
|------|-----------|
| 400 | Unsupported language code |
| 422 | Invalid params (q too short, lat/lon out of range) |

---

## Patterns

### Query Logic (Prefix + Fuzzy Fallback)

```python
async def autocomplete(query: str, lang: str, lat: float, lon: float, limit: int):
    # Step 1: Try prefix match (fast, ~5ms)
    results = await prefix_search(query, lang, lat, lon, limit)

    # Step 2: If insufficient results AND query >= 3 chars, try fuzzy
    if len(results) < 3 and len(query) >= 3:
        fuzzy_results = await fuzzy_search(query, lang, lat, lon, limit)
        results = merge_unique(results, fuzzy_results)

    return results[:limit]
```

### Prefix Search Query

```sql
SELECT DISTINCT ON (c.geonameid)
    c.geonameid, c.name, s.search_term AS local_name,
    c.country_code, co.name AS country_name,
    a.name AS admin1_name,
    c.population, c.latitude, c.longitude, c.timezone,
    ST_Distance(c.coordinates::geography,
                ST_MakePoint(:lon, :lat)::geography) / 1000 AS distance_km
FROM geo_names_city_search_index s
JOIN geo_names_cities c ON s.geonameid = c.geonameid
LEFT JOIN geo_names_countries co ON c.country_code = co.iso
LEFT JOIN geo_names_admin1_codes a ON a.code = c.country_code || '.' || c.admin1_code
WHERE lower(s.search_term) LIKE lower(:query) || '%'
  AND (s.isolanguage = :lang OR s.isolanguage IS NULL)
ORDER BY c.geonameid,
         (s.isolanguage = :lang)::int DESC,
         c.population DESC
```

### Fuzzy Search Query (pg_trgm)

```sql
SELECT DISTINCT ON (c.geonameid)
    c.geonameid, c.name, s.search_term AS local_name,
    similarity(lower(s.search_term), lower(:query)) AS score,
    ...
FROM geo_names_city_search_index s
JOIN geo_names_cities c ON s.geonameid = c.geonameid
...
WHERE lower(s.search_term) % lower(:query)  -- trigram similarity
  AND (s.isolanguage = :lang OR s.isolanguage IS NULL)
ORDER BY c.geonameid, score DESC
```

### Other Patterns

- **PostGIS**: `ST_Distance(coordinates::geography, ST_MakePoint(lon,lat)::geography)/1000` → km
- **GeoIP fallback**: X-Forwarded-For → X-Real-IP → client IP
- **Language priority**: User's lang matches rank higher than NULL (primary name)

---

## Stories

US-001: Cities with tour counts | US-002: Auto-detect location

---

## Implementation Structures

### Pydantic Schemas

**File:** `app/domains/geo/schemas.py`

```python
class UserLocation(BaseModel):
    lat: float  # -90..90
    lon: float  # -180..180

class CityResult(BaseModel):
    geoname_id: int
    name: str
    local_name: str
    admin1_name: str | None
    country_code: str
    country_name: str | None
    population: int
    lat: float
    lon: float
    distance_km: float | None
    timezone: str | None

class AutocompleteResponse(BaseModel):
    query: str
    lang: str
    user_location: UserLocation | None
    count: int
    cities: list[CityResult]

class LanguageInfo(BaseModel):
    code: str   # BCP 47
    name: str   # English name

class LanguagesResponse(BaseModel):
    languages: list[LanguageInfo]
    default: str = "en"

# Constants
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", ...
}
```

### SQLAlchemy Models

**File:** `app/domains/geo/models.py`

```python
class GeoNamesCountry(Base):
    __tablename__ = "geo_names_countries"
    iso: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    population: Mapped[int | None] = mapped_column(BigInteger)
    # ... all 19 fields from countryInfo.txt

class GeoNamesAdmin1Code(Base):
    __tablename__ = "geo_names_admin1_codes"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)  # "US.CA"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ... 4 fields from admin1CodesASCII.txt

class GeoNamesCity(Base):
    __tablename__ = "geo_names_cities"
    geonameid: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    population: Mapped[int] = mapped_column(BigInteger, default=0)
    coordinates: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    # ... all 19 fields from cities15000.txt + computed coordinates

    __table_args__ = (
        Index("idx_geo_names_cities_coordinates", "coordinates", postgresql_using="gist"),
        Index("idx_geo_names_cities_population", population.desc()),
    )

class GeoNamesCitySearchIndex(Base):
    __tablename__ = "geo_names_city_search_index"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geonameid: Mapped[int] = mapped_column(ForeignKey("geo_names_cities.geonameid", ondelete="CASCADE"))
    search_term: Mapped[str] = mapped_column(String(400), nullable=False)
    isolanguage: Mapped[str | None] = mapped_column(String(7))  # BCP 47
    source: Mapped[str | None] = mapped_column(String(20))  # name/asciiname/alternate

    __table_args__ = (
        Index("idx_geo_names_search_term_prefix", "search_term", postgresql_ops={"search_term": "text_pattern_ops"}),
        Index("idx_geo_names_search_term_trgm", "search_term", postgresql_using="gin", postgresql_ops={"search_term": "gin_trgm_ops"}),
    )
```

### Service Layer

**File:** `app/domains/geo/service.py`

```python
class GeoService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def autocomplete(
        self, query: str, lang: str = "en",
        lat: float | None = None, lon: float | None = None,
        limit: int = 10
    ) -> AutocompleteResponse:
        """City autocomplete with prefix + fuzzy fallback."""
        ...

    async def get_languages(self) -> LanguagesResponse:
        """Return supported languages list."""
        ...
```

### FastAPI Routes

**File:** `app/domains/geo/routes.py`

```python
router = APIRouter(prefix="/geo", tags=["geo"])

@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=200),
    lang: str = Query("en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$"),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> AutocompleteResponse:
    """City autocomplete with i18n and distance sorting."""
    ...

@router.get("/languages", response_model=LanguagesResponse)
async def get_languages() -> LanguagesResponse:
    """List supported languages for autocomplete."""
    ...
```

---

## Scripts Specification

### Download Script

**File:** `scripts/download_geonames.py`

**Purpose:** Download and extract GeoNames dump files.

**Usage:**
```bash
python scripts/download_geonames.py [--force]
```

**Environment:**
| Variable | Default | Description |
|----------|---------|-------------|
| `GEONAMES_DATA_DIR` | `./data` | Download directory |

**Files downloaded:**
| File | URL | Size | Output |
|------|-----|------|--------|
| `cities15000.zip` | `/dump/cities15000.zip` | ~2MB | `cities15000.txt` |
| `alternateNamesV2.zip` | `/dump/alternateNamesV2.zip` | ~200MB | `alternateNamesV2.txt` |
| `countryInfo.txt` | `/dump/countryInfo.txt` | ~30KB | (as-is) |
| `admin1CodesASCII.txt` | `/dump/admin1CodesASCII.txt` | ~150KB | (as-is) |

**Behavior:**
1. Create data directory if not exists
2. Skip download if `.txt` file already exists (unless `--force`)
3. Download with progress indicator
4. Extract ZIP files, delete ZIP after extraction
5. Verify all 4 `.txt` files exist
6. Exit code 0 on success, 1 on failure

**Dependencies:** Standard library only (`urllib`, `zipfile`, `pathlib`)

---

### Import Script

**File:** `scripts/import_geonames.py`

**Purpose:** Parse GeoNames files and populate database tables.

**Usage:**
```bash
python scripts/import_geonames.py [--truncate]
```

**Environment:**
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | Async connection string |
| `GEONAMES_DATA_DIR` | `./data` | Source files directory |
| `BATCH_SIZE` | `5000` | Insert batch size |

**Import order (dependencies):**
```
1. geo_names_countries      ← no dependencies (~250 rows)
2. geo_names_admin1_codes   ← no dependencies (~4K rows)
3. geo_names_cities         ← FK → countries (~26K rows)
4. geo_names_city_search_index ← built from cities + alternateNamesV2 (~300K rows)
```

**Processing alternateNamesV2.txt:**
- Stream file (don't load into memory)
- Filter: `geonameid` must exist in imported cities
- Filter: `isolanguage IN SUPPORTED_LANGUAGES OR NULL`
- Skip special codes: `link`, `wkdt`, `abbr`, `post`, `iata`, `icao`, `unlc`
- Insert directly into `search_index`, not as separate table

**Building search_index:**
```sql
-- From city.name (source='name', isolanguage=NULL)
INSERT INTO search_index (geonameid, search_term, isolanguage, source)
SELECT geonameid, name, NULL, 'name' FROM geo_names_cities;

-- From city.asciiname (source='asciiname', isolanguage=NULL)
INSERT INTO search_index (geonameid, search_term, isolanguage, source)
SELECT geonameid, asciiname, NULL, 'asciiname'
FROM geo_names_cities WHERE asciiname IS NOT NULL AND lower(asciiname) != lower(name);

-- From alternateNamesV2.txt (source='alternate', isolanguage=value)
-- Streamed and batch inserted during file parsing
```

**Post-import:**
```sql
CREATE INDEX IF NOT EXISTS idx_geo_names_search_term_prefix ...;
CREATE INDEX IF NOT EXISTS idx_geo_names_search_term_trgm ...;
VACUUM ANALYZE geo_names_city_search_index;
```

**Expected output:**
```
Importing geo_names_countries... 250 rows (0.1s)
Importing geo_names_admin1_codes... 4,012 rows (0.2s)
Importing geo_names_cities... 26,437 rows (2.5s)
Building search_index from cities... 52,874 rows
Processing alternateNamesV2.txt... 15,234,567 lines
  Filtered to 30 languages: 312,456 rows (5m 30s)
Creating indexes... (45s)
Vacuum analyze... (15s)
Done! Total: 6m 32s
```

**Error handling:**
- Wrap in transaction, rollback on failure
- Log line number and error
- Retry download 3x with exponential backoff
- Exit code 1 on failure

---

## Docker Integration

```yaml
# docker-compose.yml
services:
  import-geonames:
    build: .
    command: >
      sh -c "python scripts/download_geonames.py &&
             python scripts/import_geonames.py"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/locus_guide
      - GEONAMES_DATA_DIR=/app/data
    volumes:
      - geonames-data:/app/data
    depends_on:
      db:
        condition: service_healthy

volumes:
  geonames-data:
```

---

## References

*Import specification: see [GEONAMES_IMPORT.md](../GEONAMES_IMPORT.md)*
*Infrastructure: see [INFRA.md](../INFRA.md#geo-domain)*

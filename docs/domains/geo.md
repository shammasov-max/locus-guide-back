# Geo Domain

City autocomplete with i18n + distance sort. Based on GeoNames data dumps.

**Source:** https://download.geonames.org/export/dump/

---

## Naming Convention

All GeoNames tables use the `geo_names_` prefix to distinguish them from application domain tables.

| Table | Purpose |
|-------|---------|
| `geo_names_countries` | Country reference data |
| `geo_names_cities` | City reference data |
| `geo_names_alternate_names` | Multilingual city names |
| `geo_names_admin1_codes` | Region/state names |
| `geo_names_city_search_index` | Denormalized search index |

---

## Exceptions to Project Rules

These tables are **external reference data** imported from GeoNames. They do NOT follow project conventions:

| Project Rule | GeoNames Exception | Reason |
|--------------|-------------------|--------|
| HSTORE for i18n columns | Separate `alternate_names` table | GeoNames provides normalized table |
| BigInt PK for entities | Integer PK (geonameid) | Match GeoNames IDs exactly |
| `created_at`/`updated_at` timestamps | `modification_date` only | GeoNames provides single date |
| Snake_case column names | Match GeoNames field names | Traceability to source |
| CHAR(2) → String(2) in SQLAlchemy | Keep as-is | Fixed-length ISO codes |

These tables are **read-only seed data** — no application writes, only periodic refresh from GeoNames dumps.

---

## ERD

```
┌─────────────────────────────────────────────────────────────────┐
│                   geo_names_countries                           │
│ Source: countryInfo.txt (~250 rows)                             │
│─────────────────────────────────────────────────────────────────│
│ iso               │ CHAR(2) PK                                  │
│ iso3              │ CHAR(3)?                                    │
│ iso_numeric       │ SMALLINT?                                   │
│ fips              │ VARCHAR(3)?                                 │
│ name              │ VARCHAR(200)!                               │
│ capital           │ VARCHAR(200)?                               │
│ area              │ NUMERIC(10,2)?                              │
│ population        │ BIGINT?                                     │
│ continent         │ CHAR(2)?                                    │
│ tld               │ VARCHAR(10)?                                │
│ currency_code     │ CHAR(3)?                                    │
│ currency_name     │ VARCHAR(50)?                                │
│ phone             │ VARCHAR(20)?                                │
│ postal_code_format│ VARCHAR(100)?                               │
│ postal_code_regex │ VARCHAR(255)?                               │
│ languages         │ VARCHAR(200)?                               │
│ geonameid         │ INTEGER?                                    │
│ neighbours        │ VARCHAR(100)?                               │
│ equivalent_fips   │ VARCHAR(10)?                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │ 1:N
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      geo_names_cities                           │
│ Source: cities15000.txt (~26K rows)                             │
│─────────────────────────────────────────────────────────────────│
│ geonameid         │ INTEGER PK                                  │
│ name              │ VARCHAR(200)!                               │
│ asciiname         │ VARCHAR(200)?                               │
│ latitude          │ DOUBLE PRECISION!                           │
│ longitude         │ DOUBLE PRECISION!                           │
│ feature_class     │ CHAR(1)?                                    │
│ feature_code      │ VARCHAR(10)?                                │
│ country_code      │ CHAR(2)! FK→geo_names_countries*            │
│ cc2               │ VARCHAR(200)?                               │
│ admin1_code       │ VARCHAR(20)?                                │
│ admin2_code       │ VARCHAR(80)?                                │
│ admin3_code       │ VARCHAR(20)?                                │
│ admin4_code       │ VARCHAR(20)?                                │
│ population        │ BIGINT DEFAULT=0*                           │
│ elevation         │ INTEGER?                                    │
│ dem               │ INTEGER?                                    │
│ timezone          │ VARCHAR(40)?                                │
│ modification_date │ DATE?                                       │
│ coordinates       │ GEOMETRY(Point,4326)! GIST*                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │ 1:N
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
┌───────────────────────┐ │ ┌────────────────────────────────────┐
│ geo_names_admin1_codes│ │ │    geo_names_alternate_names       │
│ Source: admin1Codes   │ │ │ Source: alternateNamesV2.txt       │
│ ASCII.txt (~4K)       │ │ │ (~15M rows, all languages)         │
│───────────────────────│ │ │────────────────────────────────────│
│ code    │VARCHAR(20)PK│ │ │ id           │ INTEGER PK          │
│ name    │VARCHAR(255)!│ │ │ geonameid    │ INTEGER! FK* CASCADE│
│ asciiname│VARCHAR(255)?│ │ │ isolanguage  │ VARCHAR(7)! *       │
│ geonameid│INTEGER?    │ │ │ alternate_name│VARCHAR(400)!       │
└───────────────────────┘ │ │ is_preferred_name│BOOLEAN DEF=F    │
                          │ │ is_short_name │ BOOLEAN DEF=F       │
                          │ │ is_colloquial │ BOOLEAN DEF=F       │
                          │ │ is_historic   │ BOOLEAN DEF=F       │
                          │ │ from_period   │ VARCHAR(20)?        │
                          │ │ to_period     │ VARCHAR(20)?        │
                          │ └────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                 geo_names_city_search_index                     │
│ Denormalized for prefix search (computed from geo_names_cities  │
│ + geo_names_alternate_names)                                    │
│─────────────────────────────────────────────────────────────────│
│ id                │ SERIAL PK                                   │
│ geonameid         │ INTEGER! FK→geo_names_cities* CASCADE       │
│ search_term       │ VARCHAR(400)!                               │
│ isolanguage       │ VARCHAR(7)?                                 │
│ source            │ VARCHAR(20)?  -- name/asciiname/alternate   │
└─────────────────────────────────────────────────────────────────┘
```

*Symbols: `!`=NOT NULL, `?`=nullable, `*`=indexed, `PK`=primary key, `FK`=foreign key*

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

### geo_names_alternate_names (alternateNamesV2.txt)

| # | GeoNames Field | Column | PostgreSQL | SQLAlchemy | Notes |
|---|----------------|--------|------------|------------|-------|
| 0 | alternateNameId | `id` | `INTEGER` | `Integer` | PK |
| 1 | geonameid | `geonameid` | `INTEGER` | `Integer` | FK→geo_names_cities, CASCADE |
| 2 | isolanguage | `isolanguage` | `VARCHAR(7)` | `String(7)` | BCP 47 (en, ru, zh-CN) |
| 3 | alternate name | `alternate_name` | `VARCHAR(400)` | `String(400)` | NOT NULL |
| 4 | isPreferredName | `is_preferred_name` | `BOOLEAN` | `Boolean` | DEFAULT false |
| 5 | isShortName | `is_short_name` | `BOOLEAN` | `Boolean` | DEFAULT false |
| 6 | isColloquial | `is_colloquial` | `BOOLEAN` | `Boolean` | DEFAULT false |
| 7 | isHistoric | `is_historic` | `BOOLEAN` | `Boolean` | DEFAULT false |
| 8 | from | `from_period` | `VARCHAR(20)` | `String(20)` | ISO 8601 period |
| 9 | to | `to_period` | `VARCHAR(20)` | `String(20)` | ISO 8601 period |

**Language codes:** `isolanguage` uses BCP 47 format:
- 2-letter: `en`, `ru`, `de`, `fr`, `es`, `zh`, `ja`, `ko`
- Extended: `zh-CN`, `zh-TW`, `pt-BR`
- Special: `link` (URLs), `wkdt` (Wikidata), `abbr` (abbreviations)

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

-- Feature filtering
CREATE INDEX idx_geo_names_cities_feature_code
  ON geo_names_cities (feature_code);

-- Alternate name lookups
CREATE INDEX idx_geo_names_altnames_geonameid
  ON geo_names_alternate_names (geonameid);
CREATE INDEX idx_geo_names_altnames_isolanguage
  ON geo_names_alternate_names (isolanguage);

-- Search index lookups
CREATE INDEX idx_geo_names_search_geonameid
  ON geo_names_city_search_index (geonameid);
```

### Text Pattern Indexes (for LIKE 'prefix%')

```sql
-- Prefix search on lowercase alternate names
CREATE INDEX idx_geo_names_altnames_name_lower
  ON geo_names_alternate_names (lower(alternate_name) text_pattern_ops);

-- Prefix search on search index
CREATE INDEX idx_geo_names_search_term_lower
  ON geo_names_city_search_index (lower(search_term) text_pattern_ops);
```

---

## API

**Base:** `/api/v1/geo`

**Full OpenAPI spec:** [`docs/api/openapi.yaml`](../api/openapi.yaml)

| Method | Path | Auth | Params | Returns |
|--------|------|------|--------|---------|
| GET | `/autocomplete` | - | q! lang lat lon limit | AutocompleteResp |
| GET | `/languages` | - | - | {languages[], default} |

**Params**: `q` (1-200), `lang` (BCP 47), `lat` (-90..90), `lon` (-180..180), `limit` (1-50, def:10)
**Sort**: distance ASC (if coords/GeoIP) → population DESC
**Errors**: 400 unsupported lang | 422 invalid params

**Response**: `{query, lang, user_location?, count, cities[]}`
**CityResult**: `{geoname_id, name, local_name, country_code, country_name?, admin1?, population, lat, lon, distance_km?, timezone?}`

---

## Patterns

- **PostGIS**: `ST_Distance(coordinates::geography, ST_MakePoint(lon,lat)::geography)/1000` → km
- **Prefix search**: `lower(search_term) LIKE 'query%'` with `text_pattern_ops` index
- **GeoIP fallback**: X-Forwarded-For → X-Real-IP → client IP
- **Data**: GeoNames cities15000.txt, countryInfo.txt, alternateNamesV2.txt, admin1CodesASCII.txt

---

## Stories

US-001: Cities with tour counts | US-002: Auto-detect location

*Import specification: see [GEONAMES_IMPORT.md](../GEONAMES_IMPORT.md)*
*Infrastructure: see [INFRA.md](../INFRA.md#geo-domain)*

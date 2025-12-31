# Geo Domain

City autocomplete with i18n + distance sort. No deps.

## ERD

```
┌───────────────────────────────────────────┐
│                Country                    │
│───────────────────────────────────────────│
│ iso          │ String(2) PK              │
│ iso3         │ String(3)?                │
│ name         │ String(200)!              │
│ capital      │ String(200)?              │
│ continent    │ String(2)?                │
└─────────────────────┬─────────────────────┘
                      │ 1:N
                      ▼
┌───────────────────────────────────────────┐
│                  City                     │
│───────────────────────────────────────────│
│ geonameid    │ Int PK                    │
│ name         │ String(200)!              │
│ asciiname    │ String(200)?              │
│ country_code │ String(2)! FK→Country*    │
│ admin1_code  │ String(20)?               │
│ population   │ Int DEFAULT=0*            │
│ timezone     │ String(40)?               │
│ geom         │ POINT(4326)!              │
└─────────────────────┬─────────────────────┘
                      │ 1:N
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────────────┐  ┌────────────────────────┐
│    AlternateName      │  │    CitySearchIndex     │
│───────────────────────│  │────────────────────────│
│ id        │ Int PK    │  │ id        │ Int PK     │
│ geonameid │ Int! FK*  │  │ geonameid │ Int! FK*   │
│           │ CASCADE   │  │           │ CASCADE    │
│ language  │ String(7)!│  │ search_term│String(400)!│
│ name      │String(400)!│  │ search_term_lower      │
│ is_preferred│Bool DEF=F│  │           │String(400)!*│
│ is_short  │ Bool DEF=F│  │ language  │ String(7)? │
└───────────────────────┘  │ source    │ String(20)?│
                           └────────────────────────┘
```

*Symbols: `!`=NOT NULL, `?`=nullable, `*`=indexed, `PK`=primary key, `FK`=foreign key*

## API

**Base:** `/api/v1/geo`

| Method | Path | Auth | Params | Returns |
|--------|------|------|--------|---------|
| GET | `/autocomplete` | - | q! lang lat lon limit | AutocompleteResp |
| GET | `/languages` | - | - | {languages[], default} |

**Params**: `q` (1-200), `lang` (en), `lat` (-90..90), `lon` (-180..180), `limit` (1-50, def:10)
**Sort**: distance (if coords/GeoIP) → population DESC
**Errors**: 400 unsupported lang | 422 invalid params

**Response**: `{query, lang, user_location?, count, cities[]}`
**CityResult**: `{geoname_id, name, local_name, country_code, country_name?, admin1?, population, lat, lon, distance_km?, timezone?}`

## Patterns

- **PostGIS**: `ST_Distance(geom::geography, ST_MakePoint(lon,lat)::geography)/1000` → km
- **Prefix search**: `text_pattern_ops` index on lowercase
- **GeoIP fallback**: X-Forwarded-For → X-Real-IP → client IP
- **Data**: GeoNames cities15000.txt, countryInfo.txt, alternateNames.txt

## Stories

US-001: Cities with tour counts | US-002: Auto-detect location

*Infrastructure: see [INFRA.md](../INFRA.md#geo-domain)*

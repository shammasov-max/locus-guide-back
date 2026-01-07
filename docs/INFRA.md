# Infrastructure

## SuperTokens Core

### Service Configuration

```yaml
services:
  supertokens:
    image: registry.supertokens.io/supertokens/supertokens-postgresql:9.0
    depends_on:
      db:
        condition: service_healthy
    environment:
      POSTGRESQL_CONNECTION_URI: "postgresql://postgres:postgres@db:5432/locus_guide"
    ports:
      - "3567:3567"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3567/hello"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Tables Created by SuperTokens

SuperTokens Core creates these tables automatically on first startup:

| Table | Purpose |
|-------|---------|
| `all_auth_recipe_users` | User registry across all recipes |
| `emailpassword_users` | Email/password credentials |
| `emailpassword_pswd_reset_tokens` | Password reset tokens |
| `thirdparty_users` | OAuth provider identities |
| `session_info` | Active sessions |
| `user_roles` | Role assignments |
| `roles` | Role definitions |
| `role_permissions` | Permission assignments |

### Environment Variables

```env
# SuperTokens
SUPERTOKENS_CONNECTION_URI=http://localhost:3567
SUPERTOKENS_API_KEY=  # Optional, for production

# App Info
APP_NAME=Locus Guide
API_DOMAIN=http://localhost:8000
WEBSITE_DOMAIN=http://localhost:3000
API_BASE_PATH=/auth

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

---

## Geo Domain

### Data Sources

**Provider:** [GeoNames](https://download.geonames.org/export/dump) (CC BY 4.0)

| File | Size | Content |
|------|------|---------|
| `cities15000.txt` | 7.7 MB | Cities with population > 15,000 |
| `alternateNamesV2.txt` | 763 MB | Multilingual alternate names |
| `countryInfo.txt` | 31 KB | Country metadata |
| `iso-languagecodes.txt` | 137 KB | Language code mappings |

**Update:** Daily dumps available; monthly refresh recommended

### Seed Scripts

#### `scripts/init.sql`
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```
*Runs automatically via Docker entrypoint on first startup*

#### `scripts/download_geonames.py`
- Downloads required files with progress tracking
- Auto-extracts ZIP archives
- Env: `GEONAMES_DATA_DIR` (default: `/app/data`)
- Validates all files exist before completion

#### `scripts/import_data.py`
| Step | Function | Notes |
|------|----------|-------|
| 1 | `create_tables()` | 4 tables via SQLAlchemy |
| 2 | `import_countries()` | ~250 rows from countryInfo.txt |
| 3 | `import_cities()` | ~24K rows, PostGIS Point geometry |
| 4 | `import_alternate_names()` | Filtered by lang (en, ru, de) + valid geonameid |
| 5 | `build_search_index()` | Denormalized prefix search table |
| 6 | `create_indexes()` | 7 indexes including spatial GIST |

**Batch size:** 5,000 rows | **Clears existing data:** DELETE CASCADE

### Docker

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: geonames
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s

  app:
    build: .
    depends_on:
      db: { condition: service_healthy }
    volumes:
      - ./data:/app/data
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/geonames
```

### Index Strategy

| Index | Column(s) | Type | Purpose |
|-------|-----------|------|---------|
| `idx_cities_geom` | geom | GIST | Spatial distance queries |
| `idx_cities_country` | country_code | BTREE | Country filtering |
| `idx_cities_population` | population DESC | BTREE | Popularity sort |
| `idx_alt_names_geonameid` | geonameid | BTREE | Name lookup |
| `idx_alt_names_language` | language | BTREE | Language filter |
| `idx_search_geonameid` | geonameid | BTREE | Search→city join |
| `idx_search_prefix` | search_term_lower | BTREE (text_pattern_ops) | LIKE 'query%' prefix |

### Startup Sequence

1. `docker compose up -d` — Start services (db, supertokens, app)
2. Wait for db healthcheck (pg_isready)
3. Wait for supertokens healthcheck (curl /hello)
4. SuperTokens Core auto-creates auth tables
5. Run Alembic migrations (creates Account + other app tables)
6. `docker exec app python scripts/download_geonames.py` — Fetch data (~770 MB)
7. `docker exec app python scripts/import_data.py` — Populate database (~2 min)
8. API ready at `http://localhost:8000/api/v1/geo/autocomplete`

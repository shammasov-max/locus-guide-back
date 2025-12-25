# Routes Feature Implementation Plan

## Summary

Implement the Routes feature for Locus Guide audio guide backend with 5 database tables, 4 enums, and phased API rollout.

---

## Schema Decisions (from brainstorm)

| Decision | Choice |
|----------|--------|
| i18n columns | HSTORE (`lang -> text`) |
| Audio metadata | Not stored (URLs only, no metadata) |
| visited_points | State table with composite PK, not event log |
| Route progress | Computed on-the-fly from visited_points |
| Free preview | `free_checkpoint_limit` by seq_no |
| GeoJSON storage | Full GeoJSON + LineString path in route_versions |
| Trigger radius | Backend doesn't track GPS; app calls `/visited` endpoint |
| Completion | Either explicit (manual) OR automatic (all checkpoints done) |

---

## Database Schema

### Enums

```sql
CREATE TYPE route_status AS ENUM ('draft', 'published', 'coming_soon', 'archived');
CREATE TYPE route_version_status AS ENUM ('draft', 'review', 'published', 'superseded');
CREATE TYPE audio_listen_status AS ENUM ('none', 'started', 'completed');
CREATE TYPE completion_type AS ENUM ('manual', 'automatic');
```

### Tables (creation order)

1. **routes** - Main route entity
   - `id` UUID PK
   - `city_id` FK -> cities.geonameid
   - `slug` text (unique per city)
   - `status` route_status
   - `published_version_id` FK -> route_versions.id (nullable, circular)
   - `created_by_user_id` FK -> app_user.id
   - `created_at`, `updated_at` timestamptz

2. **route_versions** - Versioned content
   - `id` UUID PK
   - `route_id` FK -> routes.id
   - `version_no` int
   - `status` route_version_status
   - `title_i18n` HSTORE, `summary_i18n` HSTORE
   - `languages` text[]
   - `duration_min`, `ascent_m`, `descent_m`, `distance_m` int
   - `path` geography(LineString, 4326)
   - `geojson` JSONB
   - `bbox` geography(Polygon, 4326) optional
   - `free_checkpoint_limit` int
   - `price_amount` numeric(10,2), `price_currency` char(3)
   - `published_at`, `created_at` timestamptz
   - `created_by_user_id` FK -> app_user.id
   - UNIQUE(route_id, version_no)

3. **checkpoints** - Route points
   - `id` UUID PK
   - `route_version_id` FK -> route_versions.id
   - `seq_no` int (walking order)
   - `display_number` int nullable (visible label)
   - `is_visible` boolean
   - `source_point_id` int (original GeoJSON id)
   - `title_i18n` HSTORE, `description_i18n` HSTORE
   - `location` geography(Point, 4326)
   - `trigger_radius_m` int default 25
   - `is_free_preview` boolean
   - `osm_way_id` bigint nullable
   - UNIQUE(route_version_id, seq_no)

4. **visited_points** - User checkpoint progress (state table)
   - PK: composite (`user_id`, `checkpoint_id`)
   - `visited` boolean (GPS zone entry)
   - `visited_at` timestamptz
   - `audio_status` audio_listen_status (none/started/completed)
   - `audio_started_at`, `audio_completed_at` timestamptz
   - `updated_at`, `created_at` timestamptz

5. **user_active_routes** - User's active route sessions
   - `id` UUID PK
   - `user_id` FK -> app_user.id
   - `route_id` FK -> routes.id
   - `locked_version_id` FK -> route_versions.id
   - `started_at` timestamptz
   - `completed_at` timestamptz nullable
   - `completion_type` completion_type nullable
   - UNIQUE(user_id, route_id)

### Color Status Logic (from visited_points)

| visited | audio_status | Color | Meaning |
|---------|--------------|-------|---------|
| false | none | purple | Not visited, not listened |
| true | none | gray | GPS visited, audio not started |
| * | started | blue | Audio started, not finished |
| false | completed | orange | Listened manually, no GPS |
| true | completed | green | Fully completed |

---

## API Endpoints

### Phase 1: Read (public/optional auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/routes` | List routes (filters: city, nearby, status) |
| GET | `/api/v1/routes/{route_id}` | Route detail with published version |
| GET | `/api/v1/routes/{route_id}/checkpoints` | Get all checkpoints |

### Phase 2: User Progress (requires auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/routes/checkpoints/{id}/visited` | Mark GPS visited |
| POST | `/api/v1/routes/checkpoints/{id}/audio-status` | Update audio status |
| GET | `/api/v1/routes/me/routes` | User's active routes with progress |
| POST | `/api/v1/routes/{id}/start` | Start route (locks version) |
| POST | `/api/v1/routes/{id}/finish` | Finish route manually |

### Phase 3: Admin (requires auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/routes/admin` | Create new route |
| GET | `/api/v1/routes/admin` | List all routes (incl. drafts) |
| GET | `/api/v1/routes/admin/{route_id}` | Get route admin details |
| PATCH | `/api/v1/routes/admin/{route_id}` | Update route metadata |
| DELETE | `/api/v1/routes/admin/{route_id}` | Delete route |
| GET | `/api/v1/routes/admin/{route_id}/versions` | List versions |
| POST | `/api/v1/routes/admin/{route_id}/versions` | Create version from GeoJSON |
| PATCH | `/api/v1/routes/admin/versions/{version_id}` | Update version |
| POST | `/api/v1/routes/admin/{route_id}/publish` | Publish version |
| GET | `/api/v1/routes/admin/versions/{version_id}/checkpoints` | Get checkpoints |
| PATCH | `/api/v1/routes/admin/checkpoints/{checkpoint_id}` | Update checkpoint |

---

## Completed

- [x] Database migration with 5 tables, 4 enums
- [x] Phase 1: Read endpoints (public routes listing)
- [x] Phase 2: User progress endpoints (visit tracking, audio status)
- [x] Phase 3: Admin endpoints (route/version/checkpoint management)
- [x] GeoJSON import with automatic checkpoint creation

## Next Steps

1. Add nearby routes filter using first checkpoint location
2. Add role-based access control for admin endpoints
3. Implement route search by title/description

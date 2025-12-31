## Стек
- **FastAPI** + Uvicorn (async)
- **PostgreSQL 16** + PostGIS 3.4
- **SQLAlchemy 2.0** async + Alembic
- **JWT** авторизация (python-jose + bcrypt)

## Postgres model rules
| **Language PK** | VARCHAR code | Natural key ('en', 'ru'), no joins needed |
| **User settings** | Embedded in users | Simpler, single query for user |
| **i18n textual columns** | HSTORE columns has suffix *_i18n in the name lang->value map | Efficient, type-safe, no translation tables |
| **geodata, lat lon coordinates** |  store as Postgis Point 

# Entity Glossary — Locus Guide
---

## Roles

All roles share an **Account** entity as their unified identity.

| Entity | Description |
|--------|-------------|
| **User** | End user of mobile app. Browses tours, makes purchases, starts runs, tracks progress, earns achievements |
| **Editor** | Content creator. Creates/edits tours and routes, uploads audio, tests in simulation (creates flagged Run records excluded from analytics) |
| **Admin** | Administrator. Manages editor permissions, creates bundles, sets prices, views analytics |
| **System** | Background processes and automation (deferred to tech spec) |

---

## Core Domain Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Account** | Unified identity for User, Editor, and Admin roles | guid, email, role, created_at |
| **City** | Geographic location containing tours. Optional for Tours. System seed data (not user-created) | id, name, country_code, coordinates (lat/lng), is_active |
| **Tour** | Product unit. Has single active Route + version history for in-progress Runs, plus a non-empty draft Route. Soft delete only (archived, never permanently deleted) | autoincrement id, city_id (optional), active_route_id, draft_route_id, is_archived |
| **Route** | Belongs to a Tour. GeoJSON embeds coordinates with `waypoint_guid` field linking to reusable Waypoints. `waypoint_guids[]` references Waypoint pool. Holds precomputed distance, altitude, time. Lifecycle: Draft → Published. In-progress Runs continue on their original Route version | autoincrement id, tour_id, waypoint_guids[], geojson, status (draft/published), version, distance, altitude, estimated_time |
| **Waypoint** | Reusable point of interest. Can be referenced by multiple Routes across Tours. Immutable: `guid`, `is_checkpoint`. Audio served via REST `/uploads/audio/{waypoint_guid}/{lang}.mp3`. Default: `is_checkpoint=true` | guid, coordinates, i18n_description, is_checkpoint (immutable) |
| **Run** | Progress of an Account on a Route. Unlimited concurrent runs allowed across different tours. States: started → completed \| abandoned (explicit user action only; no auto-timeout). `is_simulation` flag for Editor testing (excluded from analytics). `completed_checkpoints` tracks only checkpoint Waypoints | guid, route_id, account_id, started_at, completed_at, abandoned_at, completed_checkpoints[], is_simulation |

---

## Deferred Entities

The following entities are out of scope for the current specification and will be defined later:

| Entity | Notes |
|--------|-------|
| **Achievement** | User rewards/badges — will be hardcoded initially, formal entity later |
| **Bundle** | Tour collections with discount — pricing logic TBD |
| **Purchase** | Payment records — store integration (Apple/Google) TBD |


Бэкенд для мультиязычного мобильного аудиогида (iOS/Android).
## Документация
- User stories: `docs/user-stories.md`
- План разработки: `plan.md`
 

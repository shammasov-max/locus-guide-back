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

## Entity Schemas

See domain docs for ERDs, API routes, and patterns:
- `docs/domains/auth.md` — Account, AuthIdentity, RefreshToken
- `docs/domains/geo.md` — Country, City
- `docs/domains/tours.md` — Tour, Route, Waypoint, Run

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
 

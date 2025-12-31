# Tours Domain

Audio-guided tours with versioned routes, reusable waypoints, and progress tracking.

---

## ERD

```
              ┌───────────────────────────┐
              │           City            │
              │ (Geo domain seed data)    │
              └─────────┬─────────────────┘
                        │ 0..1
                        ▼
┌──────────────────────────────────────────────────┐
│                     Tour                         │
│──────────────────────────────────────────────────│
│ id                │ Int PK                       │
│ city_id           │ Int? FK→City                 │
│ active_route_id   │ Int? FK→Route                │
│ draft_route_id    │ Int! FK→Route                │
│ title_i18n        │ HSTORE! {lang:text}          │
│ description_i18n  │ HSTORE                       │
│ price_usd         │ Decimal(10,2)                │
│ is_archived*      │ Bool! DEFAULT=false          │
│ created_at        │ Timestamptz! DEFAULT=now()   │
│ updated_at        │ Timestamptz                  │
└────────────┬─────────────────────────────────────┘
             │ 1:N
             ▼
┌──────────────────────────────────────────────────┐
│                    Route                         │
│──────────────────────────────────────────────────│
│ id                │ Int PK                       │
│ tour_id*          │ Int! FK→Tour                 │
│ version           │ Int! UNIQUE(tour_id,version) │
│ status            │ Text! CHECK(draft|published) │
│ geojson           │ JSONB                        │
│ waypoint_guids    │ UUID[]                       │
│ distance_m        │ Int                          │
│ elevation_m       │ Int                          │
│ estimated_min     │ Int                          │
│ languages         │ JSONB {lang:bool}            │
│ created_at        │ Timestamptz! DEFAULT=now()   │
└────────────────────────────────┬─────────────────┘
                                 │ references
                                 ▼
┌──────────────────────────────────────────────────┐
│                   Waypoint                       │
│──────────────────────────────────────────────────│
│ guid              │ UUID PK (immutable)          │
│ coordinates       │ POINT(4326)!                 │
│ description_i18n  │ HSTORE                       │
│ is_checkpoint     │ Bool! DEFAULT=true IMMUTABLE │
│ created_at        │ Timestamptz! DEFAULT=now()   │
│ created_by        │ BigInt! FK→Account           │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│                      Run                         │
│──────────────────────────────────────────────────│
│ guid              │ UUID PK                      │
│ route_id*         │ Int! FK→Route (locked)       │
│ account_id*       │ BigInt! FK→Account           │
│ started_at        │ Timestamptz! DEFAULT=now()   │
│ completed_at      │ Timestamptz?                 │
│ abandoned_at      │ Timestamptz?                 │
│ completed_checkpoints │ UUID[] DEFAULT='{}'      │
│ is_simulation     │ Bool! DEFAULT=false          │
│ last_position     │ POINT(4326)                  │
│ updated_at        │ Timestamptz                  │
└──────────────────────────────────────────────────┘
* indexed
```

---

## API

**Base:** `/api/v1`

### Public

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/cities` | - | Cities with tour counts |
| GET | `/cities/{id}/tours` | - | Tours in city |
| GET | `/tours` | - | All tours (filterable) |
| GET | `/tours/{id}` | - | Tour details + active route |
| GET | `/tours/{id}/preview` | - | First 4 waypoints (free) |

### Runs (User)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/runs` | Bearer | Start run (locks route version) |
| GET | `/runs` | Bearer | My runs (active/completed) |
| GET | `/runs/{guid}` | Bearer | Run details |
| PATCH | `/runs/{guid}` | Bearer | Update progress/checkpoints |
| POST | `/runs/{guid}/abandon` | Bearer | Explicit abandon |
| POST | `/runs/{guid}/complete` | Bearer | Mark completed |

### Editor

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/editor/tours` | Bearer+Editor | My tours |
| POST | `/editor/tours` | Bearer+Editor | Create tour with draft |
| GET | `/editor/tours/{id}/draft` | Bearer+Editor | Get draft route |
| PATCH | `/editor/tours/{id}/draft` | Bearer+Editor | Update draft route |
| POST | `/editor/tours/{id}/publish` | Bearer+Editor | Publish draft → new version |
| GET | `/editor/tours/{id}/history` | Bearer+Editor | Route version history |
| POST | `/editor/waypoints` | Bearer+Editor | Create reusable waypoint |
| POST | `/editor/waypoints/{guid}/audio` | Bearer+Editor | Upload audio (multipart) |

### Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/editors` | Bearer+Admin | List editors |
| POST | `/admin/editors` | Bearer+Admin | Grant editor role |
| DELETE | `/admin/editors/{id}` | Bearer+Admin | Revoke editor role |

**Errors:** 400 (invalid), 401 (auth), 403 (role), 404 (not found), 409 (conflict), 422 (validation)

---

## Patterns

### Versioning
- Draft Route → Publish → New Route version created
- `Tour.active_route_id` updated to new version
- In-progress Runs stay locked to original `route_id`
- Route history preserved (never deleted)

### i18n
- HSTORE columns: `{lang: value}` (e.g., `title_i18n`, `description_i18n`)
- SQL access: `title_i18n -> 'ru'`
- Audio files: `/uploads/audio/{waypoint_guid}/{lang}.mp3`

### Soft Delete
- Tours: `is_archived=true` (never hard delete)
- Prevents orphaning active Runs

### Waypoint Pool
- Reusable across Routes/Tours via `waypoint_guids[]`
- `guid` and `is_checkpoint` immutable after creation
- Default: `is_checkpoint=true`

### Run States
- **Active**: `completed_at IS NULL AND abandoned_at IS NULL`
- **Completed**: `completed_at IS NOT NULL`
- **Abandoned**: `abandoned_at IS NOT NULL` (explicit user action only)
- **Simulation**: `is_simulation=true` (Editor testing, excluded from analytics)

---

## Stories

| ID | Description |
|----|-------------|
| US-003 | Tour cards: title, duration, elevation |
| US-004 | Waypoints on map, audio preview |
| US-013a | First 4 waypoints free preview |
| US-021 | Resume in-progress run (version locked) |
| US-033 | Editor: work with draft before publish |
| US-036 | Progress syncs across devices |
| US-036b | Explicit abandon action |
| US-053 | Mark waypoints as checkpoints |

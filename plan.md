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
- [x] Nearby routes filter using first checkpoint location (PostGIS ST_DWithin)
- [x] Role-based access control for admin endpoints (user/editor/admin roles)
- [x] Route search by title/description (case-insensitive HSTORE search)
- [x] Comprehensive tests (19 test cases)

---

## Phase 4: Advanced Route Management (Planned)

### Overview
Расширенные функции для управления версиями маршрутов, контентом и мультиязычностью на основе требований из ROUTE_VERSIONING_CONVERSATION.md.

**Документация**: См. `docs/business-rules.md` (27 бизнес-правил) и `docs/user-stories.md` (US-036 to US-040).

---

### 4.1 Checkpoint Reusability (US-043)

**Цель**: Переиспользование checkpoint ID между версиями для автоматического применения обновлений audio/метаданных.

#### Database Changes

**New Table: checkpoint_master**
```sql
CREATE TABLE checkpoint_master (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id UUID REFERENCES routes(id) ON DELETE CASCADE,

    -- Geographic data
    location geography(Point, 4326) NOT NULL,
    osm_way_id BIGINT,
    trigger_radius_m INT DEFAULT 25,

    -- Content (shared across versions)
    title_i18n HSTORE NOT NULL,
    description_i18n HSTORE,
    audio_urls JSONB, -- {"en": "https://...", "ru": "https://..."}

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_by_user_id UUID REFERENCES app_user(id)
);

CREATE INDEX idx_checkpoint_master_route_id ON checkpoint_master(route_id);
CREATE INDEX idx_checkpoint_master_location ON checkpoint_master USING GIST(location);
```

**Modify checkpoints table**:
```sql
ALTER TABLE checkpoints ADD COLUMN checkpoint_master_id UUID REFERENCES checkpoint_master(id);
-- Make existing content fields nullable (data now in checkpoint_master)
ALTER TABLE checkpoints ALTER COLUMN title_i18n DROP NOT NULL;
ALTER TABLE checkpoints ALTER COLUMN description_i18n DROP NOT NULL;
```

#### API Changes

**Updated Endpoints**:
- `GET /api/v1/routes/{id}/checkpoints` - JOIN с checkpoint_master для получения content
- `PATCH /api/v1/routes/admin/checkpoints/{id}` - обновляет checkpoint_master вместо checkpoints
- `POST /api/v1/routes/admin/versions/{version_id}/checkpoints` - создает checkpoint_master при первом добавлении точки

**Business Logic**:
- При создании новой версии (BR-003):
  - Копируются checkpoint записи с теми же `checkpoint_master_id`
  - Переиспользуются существующие checkpoint_master записи
  - Новые точки создают новые checkpoint_master записи
- При обновлении checkpoint_master:
  - Изменения видны во ВСЕХ версиях, использующих этот checkpoint_master

**Migration Strategy**:
1. Создать checkpoint_master таблицу
2. Мигрировать существующие checkpoints → checkpoint_master (из последней published версии каждого route)
3. Связать checkpoints с checkpoint_master по location + route_id
4. Обновить API endpoints для использования JOIN

**Related BR**: BR-019, BR-020, BR-021

---

### 4.2 Editing Published Metadata (US-037)

**Цель**: Редакторы могут исправлять опечатки в опубликованных маршрутах без создания новой версии.

#### API Changes

**Endpoint**: `PATCH /api/v1/routes/admin/checkpoints/{checkpoint_id}`

**Request** (без изменений):
```json
{
  "title_i18n": {"en": "Corrected Title", "ru": "Исправленное название"},
  "description_i18n": {"en": "Updated description"}
}
```

**Response** (добавить warning):
```json
{
  "checkpoint": {...},
  "is_published_version": true,
  "warning": "You are editing a published version. Changes will be visible to all users.",
  "affected_users_count": 42
}
```

**Business Logic**:
1. Проверить `route_version.status` для checkpoint
2. Если `status == 'published'`:
   - Подсчитать `user_active_routes` с `locked_version_id = route_version.id`
   - Вернуть `affected_users_count` в response
   - Применить изменения "in-place" к checkpoint_master (если используется US-043)
3. Если `status == 'draft'`:
   - Применить изменения без warning

**Related BR**: BR-004, BR-011, BR-013

---

### 4.3 Admin Validation для структурных изменений (US-038)

**Цель**: Предупреждение в админке при добавлении/удалении точек в опубликованном маршруте.

#### API Changes

**Endpoints**:
- `POST /api/v1/routes/admin/versions/{version_id}/checkpoints`
- `DELETE /api/v1/routes/admin/checkpoints/{checkpoint_id}`

**Query Parameter**: `?confirm_structure_change=true`

**Error Response** (если published version И confirm != true):
```json
HTTP 409 Conflict
{
  "error": "STRUCTURE_CHANGE_REQUIRES_CONFIRMATION",
  "message": "Adding/removing checkpoints in published version creates new draft version.",
  "details": {
    "current_version_no": 2,
    "new_version_no": 3,
    "affected_users_count": 42,
    "action_required": "Add ?confirm_structure_change=true to confirm"
  }
}
```

**Business Logic при подтверждении**:
1. Создать новую route_version:
   - `version_no = current_version_no + 1`
   - `status = 'draft'`
   - Копировать метаданные из текущей published версии
2. Скопировать checkpoints из published версии в новую draft:
   - Переиспользовать `checkpoint_master_id` (если US-043 реализован)
   - Скопировать `seq_no`, `display_number`, `is_visible`, `is_free_preview`
3. Применить структурное изменение к новой draft версии
4. Вернуть новую draft version в response

**Frontend Flow**:
1. Пользователь пытается добавить/удалить точку в published маршруте
2. Backend возвращает 409 Conflict
3. Frontend показывает modal:
   - "Вы добавляете/удаляете точки. Будет создана новая draft-версия маршрута."
   - "N пользователей, уже начавших маршрут, останутся на старой версии."
   - Кнопки: "Продолжить" / "Отмена"
4. При "Продолжить" → повторить запрос с `?confirm_structure_change=true`

**Related BR**: BR-003, BR-014

---

### 4.4 Incremental Language Addition (US-039)

**Цель**: Постепенное добавление языков к опубликованному маршруту с контролем готовности.

#### Database Changes

```sql
ALTER TABLE route_versions ADD COLUMN available_languages TEXT[] DEFAULT '{}';
-- available_languages - языки, видимые пользователям (published)
-- languages - все языки, включая "in progress" (draft + published)
```

#### New Endpoints

**1. Add language to version**
```
POST /api/v1/routes/admin/versions/{version_id}/languages
Body: {"language_code": "es"}
Response: {
  "version_id": "...",
  "all_languages": ["en", "ru", "es"],
  "available_languages": ["en", "ru"],
  "language_status": {
    "es": "draft"
  }
}
```

**2. Publish/unpublish language**
```
PATCH /api/v1/routes/admin/versions/{version_id}/languages/{lang_code}
Body: {"status": "published"} OR {"status": "draft"}
Response: {
  "language_code": "es",
  "status": "published",
  "available_languages": ["en", "ru", "es"]
}
```
- При `status = "published"`: добавить язык в `available_languages`
- При `status = "draft"`: удалить язык из `available_languages`

**3. Check language completeness**
```
GET /api/v1/routes/admin/versions/{version_id}/languages/{lang_code}/completeness
Response: {
  "language_code": "es",
  "checkpoints_total": 15,
  "checkpoints_with_audio": 10,
  "checkpoints_with_title": 12,
  "checkpoints_with_description": 8,
  "is_complete": false,
  "completeness_percentage": 66.7,
  "missing_items": [
    {"checkpoint_id": "...", "seq_no": 3, "missing": ["audio", "description"]},
    {"checkpoint_id": "...", "seq_no": 7, "missing": ["audio"]},
    ...
  ]
}
```

**Business Logic**:
- Language считается "complete", если:
  - 100% checkpoints имеют `title_i18n[lang]` (обязательно)
  - 100% checkpoints имеют audio URL для языка (обязательно)
  - (опционально) 100% checkpoints имеют `description_i18n[lang]`
- Кнопка "Publish language" в админке активна только если `is_complete == true`

**Public API Changes**:
- `GET /api/v1/routes/{id}` возвращает только `available_languages` (НЕ `languages`)
- Пользователи видят только языки из `available_languages`

**Related BR**: BR-015, BR-016, BR-017, BR-018

---

### 4.5 Multi-device Version Locking (US-036)

**Цель**: Синхронизация прогресса между устройствами с сохранением version lock.

#### Current Implementation (Already exists!)

- Таблица `user_active_routes` с полями:
  - `user_id`, `route_id`, `locked_version_id`
  - UNIQUE(user_id, route_id) - один active route per user
- Endpoint `POST /api/v1/routes/{id}/start` создает/возвращает locked version

#### Enhancement: Add user_state to route detail

**Updated Endpoint**: `GET /api/v1/routes/{id}`

**Response** (добавить `user_state` секцию):
```json
{
  "route": {
    "id": "...",
    "slug": "hermitage-museum",
    "status": "published",
    "published_version_id": "v3-uuid",
    ...
  },
  "published_version": {
    "id": "v3-uuid",
    "version_no": 3,
    ...
  },
  "user_state": {
    "is_active": true,
    "locked_version_id": "v2-uuid",
    "locked_version_no": 2,
    "current_published_version_no": 3,
    "version_outdated": true,
    "progress_percentage": 45,
    "checkpoints_visited": 9,
    "checkpoints_total": 20
  }
}
```

**Business Logic**:
- Проверить `user_active_routes` для (user_id, route_id)
- Если `completed_at IS NULL`:
  - `is_active = true`
  - `locked_version_id` из user_active_routes
  - `version_outdated = (locked_version_id != published_version_id)`
- Если нет записи ИЛИ `completed_at IS NOT NULL`:
  - `is_active = false`
  - `locked_version_id = NULL`

**Multi-device Sync Flow**:
1. Пользователь начал маршрут на устройстве A (iPhone)
   - `POST /routes/{id}/start` → создает `user_active_routes` с `locked_version_id = v2`
2. Редактор опубликовал v3 (добавил 5 новых точек)
3. Пользователь открыл маршрут на устройстве B (iPad)
   - `GET /routes/{id}` → возвращает `user_state.locked_version_id = v2`
   - `GET /routes/{id}/checkpoints` → возвращает checkpoints из v2 (НЕ v3)
4. Пользователь прошел точку на iPhone:
   - `POST /checkpoints/{id}/visited` → обновляет `visited_points`
5. Пользователь открыл приложение на iPad:
   - `GET /routes/{id}/checkpoints` → видит обновленный прогресс (синхронизация через `visited_points`)
6. Пользователь завершил маршрут:
   - `POST /routes/{id}/finish` → устанавливает `user_active_routes.completed_at = now()`
   - Version lock снимается
7. Пользователь начинает маршрут заново:
   - `POST /routes/{id}/start` → создает новую запись с `locked_version_id = v3` (актуальная published)

**Related BR**: BR-007, BR-008, BR-009, BR-010

---

### 4.6 Offline Progress Sync (US-040)

**Цель**: Синхронизация offline прогресса с сервером при появлении интернета.

#### Current Implementation

- Endpoints уже идемпотентны:
  - `POST /api/v1/routes/checkpoints/{id}/visited`
  - `POST /api/v1/routes/checkpoints/{id}/audio-status`
- Можно вызывать повторно без побочных эффектов

#### Enhancement: Batch sync endpoint (optional)

**New Endpoint**: `POST /api/v1/routes/progress/sync`

**Request**:
```json
{
  "route_id": "...",
  "updates": [
    {
      "checkpoint_id": "...",
      "visited": true,
      "visited_at": "2025-12-30T10:30:00Z",
      "audio_status": "completed",
      "audio_completed_at": "2025-12-30T10:35:00Z"
    },
    {
      "checkpoint_id": "...",
      "visited": true,
      "visited_at": "2025-12-30T10:40:00Z",
      "audio_status": "started",
      "audio_started_at": "2025-12-30T10:42:00Z"
    }
  ]
}
```

**Response**:
```json
{
  "synced_count": 2,
  "conflicts": [],
  "route_progress": {
    "checkpoints_visited": 12,
    "checkpoints_total": 20,
    "percentage": 60
  }
}
```

**Business Logic**:
- Применить правило "last write wins" по timestamp:
  - Если `visited_at` в запросе > `visited_at` в БД → обновить
  - Если `audio_completed_at` в запросе > `audio_completed_at` в БД → обновить
- Игнорировать обновления с более старым timestamp
- Если checkpoint уже `visited=true, audio_status=completed` → игнорировать (оптимизация)

**Alternative**: Продолжать использовать существующие endpoints (рекомендуется для MVP)
- Мобильное приложение делает batch вызовов `/checkpoints/{id}/visited` при восстановлении сети
- Идемпотентность гарантирует корректность

**Related BR**: BR-024, BR-025, BR-026, BR-027

---

## Implementation Priority

### Phase 4.1: Critical (Must Have)
1. ✅ **US-037**: Editing Published Metadata (4.2) - уже используется редакторами
2. ✅ **US-038**: Admin Validation (4.3) - предотвращает ошибки
3. ✅ **US-039**: Language Management (4.4) - блокирует масштабирование
4. ✅ **US-043**: Checkpoint Reusability (4.1) - критично по запросу клиента

### Phase 4.2: High Priority (Should Have)
5. **US-036**: Multi-device Sync Enhancement (4.5) - улучшение UX
6. **US-040**: Offline Sync (4.6) - улучшение offline режима

### Phase 4.3: Future Enhancements
7. Admin Version History & Comparison (UI feature)
8. Version Rollback (emergency feature)

---

## Testing Strategy for Phase 4

### 4.1 Checkpoint Reusability Tests
- Test checkpoint_master creation on first route publish
- Test checkpoint_master reuse on version creation (structural change)
- Test metadata update propagation across versions
- Test audio URL update visibility in all versions

### 4.2 Published Metadata Editing Tests
- Test in-place update of title_i18n in published version
- Test warning message with affected_users_count
- Test visibility of changes for users on locked version
- Test no new version created after metadata update

### 4.3 Structure Change Validation Tests
- Test 409 Conflict without confirm parameter
- Test new draft version creation after confirmation
- Test checkpoint copy with checkpoint_master_id reuse
- Test affected_users_count calculation

### 4.4 Language Management Tests
- Test adding language to published version (languages array)
- Test language completeness calculation
- Test publishing language (adding to available_languages)
- Test unpublishing language (removing from available_languages)
- Test public API returns only available_languages

### 4.5 Multi-device Sync Tests
- Test version lock persistence across devices
- Test user_state in route detail response
- Test version_outdated flag when new version published
- Test progress sync between devices via visited_points

### 4.6 Offline Sync Tests
- Test idempotent visited endpoint (repeated calls)
- Test last write wins conflict resolution
- Test batch sync endpoint (if implemented)
- Test offline progress storage and sync on reconnect

---

## Related Documentation

- **User Stories**: `docs/user-stories.md` (US-036 to US-040)
- **Business Rules**: `docs/business-rules.md` (BR-001 to BR-027)
- **Conversation Log**: `docs/ROUTE_VERSIONING_CONVERSATION.md` (original requirements)
- **Migration Plans**: TBD (checkpoint_master migrations)

---

## Notes

- Phase 4 основан на обсуждении версионирования между Stanislav Svarichevsky и Max Shammasov (декабрь 2025)
- Все технические решения согласованы с 27 бизнес-правилами из `docs/business-rules.md`
- Checkpoint Reusability (US-043) требует значительных изменений схемы данных - рекомендуется начать с миграции тестовых данных

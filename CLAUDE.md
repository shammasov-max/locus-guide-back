# Locus Guide Backend

Бэкенд для мультиязычного мобильного аудиогида (iOS/Android).
## Документация
- User stories: `docs/user-stories.md`
- План разработки: `plan.md`
 
## User Stories Editing Rules

When editing `docs/user-stories.md`:

- **Format:** "Как [роль], я хочу [что], чтобы [почему]" (15-30 words)
- **Merge stories:** 60%+ overlap (same actor + goal + почему)
- **Delete stories:** Epics ("вся часть", no acceptance criteria)
- **Keep numbering:** Don't renumber after merge/delete (gaps OK)
- **Technical details:** API/schema → Acceptance Criteria, not story text
- **Version pinning:** Always explicit for progress/sync ("привязывался к версии, с которой я начал")


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

## Project Scopes for Commits

Use these scopes in commit messages:

| Scope | Use for |
|-------|---------|
| login | Login flow, session handling |
| register | User registration |
| oauth | Google OAuth, external providers |
| tokens | JWT access/refresh tokens |
| users | User model, profile data |
| profile | Profile updates, preferences |
| cities | City autocomplete, GeoNames data |

## Examples
```
✨ feat(oauth): add Google OAuth callback handler
🐛 fix(tokens): prevent refresh token reuse after rotation
🔧 chore(deps): update sqlalchemy to 2.0
```

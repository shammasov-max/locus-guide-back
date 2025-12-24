# Locus Guide Backend

Бэкенд для мультиязычного мобильного аудиогида (iOS/Android).
## Документация
- User stories: `docs/user-stories.md`
- План разработки: `plan.md`
 
 
## Стек
- **FastAPI** + Uvicorn (async)
- **PostgreSQL 16** + PostGIS 3.4
- **SQLAlchemy 2.0** async + Alembic
- **JWT** авторизация (python-jose + bcrypt)
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

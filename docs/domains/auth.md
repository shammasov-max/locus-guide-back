# Auth Domain

SuperTokens authentication, OAuth (Google), session management, user preferences.

## ERD

```
┌──────────────────────────────────────────────────────────────┐
│                          Account                             │
│──────────────────────────────────────────────────────────────│
│ id                  │ BigInt PK                              │
│ supertokens_user_id │ String(36)! UNIQUE*  -- link to ST     │
│ email               │ String(255)! UNIQUE*                   │
│ display_name        │ Text?                                  │
│ role                │ Text! CHECK('user','editor','admin')   │
│ locale_pref         │ Text?                                  │
│ ui_lang             │ Text?                                  │
│ audio_lang          │ Text?                                  │
│ character           │ JSONB?  -- flexible object             │
│ units               │ Text! CHECK('metric','imperial')       │
│ created_at          │ DateTime(tz)! DEFAULT=now()            │
└──────────────────────────────────────────────────────────────┘
```

### SuperTokens-Managed Tables

The following tables are created and managed by SuperTokens Core (not Alembic):

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

## API

### SuperTokens-Managed Endpoints

**Base:** `/auth` (handled by SuperTokens SDK middleware)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/signup` | Email/password registration |
| POST | `/signin` | Email/password login |
| POST | `/signout` | Logout (revoke session) |
| POST | `/session/refresh` | Refresh access token |
| GET | `/authorisationurl` | Get OAuth redirect URL |
| POST | `/signinup/callback/:providerId` | OAuth callback |
| POST | `/user/password/reset/token` | Request password reset |
| POST | `/user/password/reset` | Confirm password reset |

**Full API docs:** https://supertokens.com/docs/thirdpartyemailpassword/apis

### Custom Endpoints

**Base:** `/api/v1/auth`

**Full OpenAPI spec:** [`docs/api/openapi.yaml`](../api/openapi.yaml)

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/me` | Session | — | `UserResponse` 200 |
| PATCH | `/me` | Session | `{display_name?, units?, ...}` | `UserResponse` 200 |
| DELETE | `/me` | Session | — | `{message}` 200 |
| POST | `/logout-all` | Session | — | `{message}` 200 |

**Errors:** 400 (bad request), 401 (invalid session), 403 (forbidden), 422 (validation)

## Patterns

### Session Management

SuperTokens handles sessions via HTTP-only cookies + access tokens:
- **Access token:** Short-lived, in `sAccessToken` cookie or `st-access-token` header
- **Refresh token:** HTTP-only cookie, automatic rotation
- **Anti-CSRF:** Built-in protection via `sAntiCsrf` cookie

### Roles

Dual storage for performance:
- **SuperTokens `userroles` recipe:** Claims in access token for fast verification
- **`Account.role` column:** Database fallback, admin management UI

**Roles:**
- `user` — End user (default). Mobile app access only.
- `editor` — Content creator. Can create/edit tours, access `/editor/*` endpoints.
- `admin` — Administrator. Full access including `/admin/*` endpoints.

### Password

SuperTokens bcrypt hashing (configurable via Core settings).

### OAuth Providers

- **Google** (primary) — Configured via `thirdparty` recipe
- Extensible: Add Apple, GitHub, etc. via SuperTokens provider config

### Account Linking

SuperTokens handles email-based account linking automatically:
- Same email from email/password and Google → linked to single user
- Managed via `all_auth_recipe_users` table

### Account Sync

On SuperTokens sign-up/sign-in:
1. SuperTokens creates/retrieves user in Core
2. Recipe override creates/syncs Account record in our database
3. `Account.supertokens_user_id` links to SuperTokens user

## Stories

- **US-015** Fast seamless email authorization on launch
- **US-011i** Save settings and sync between devices

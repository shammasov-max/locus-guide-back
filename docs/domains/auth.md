# Auth Domain

JWT authentication, OAuth (Google), session management, user preferences.

## ERD

```
┌──────────────────────────────────────────────────────────────┐
│                          Account                             │
│──────────────────────────────────────────────────────────────│
│ id              │ BigInt PK                                  │
│ email           │ String(255)! UNIQUE*                       │
│ display_name    │ Text?                                      │
│ role            │ Text! CHECK('user','editor','admin') DEF=user│
│ locale_pref     │ Text?                                      │
│ ui_lang         │ Text?                                      │
│ audio_lang      │ Text?                                      │
│ units           │ Text! CHECK('metric','imperial')           │
│ token_version   │ Int! DEFAULT=0                             │
│ created_at      │ DateTime(tz)! DEFAULT=now()                │
└────────────────────────┬─────────────────────────────────────┘
                         │ 1:N
           ┌─────────────┴─────────────┐
           ▼                           ▼
┌────────────────────────┐  ┌─────────────────────────────────┐
│    AuthIdentity        │  │       RefreshToken              │
│────────────────────────│  │─────────────────────────────────│
│ id          │ BigInt PK│  │ id          │ BigInt PK         │
│ account_id  │ FK! *    │  │ account_id  │ FK! *             │
│ provider    │ Text!    │  │ token_hash  │ Text! UNIQUE      │
│ provider_subject Text! │  │ device_info │ Text?             │
│ email_verified Bool! 0 │  │ created_at  │ DateTime(tz)!     │
│ password_hash  Text?   │  │ expires_at  │ DateTime(tz)! *   │
│ created_at DateTime(tz)│  │ revoked_at  │ DateTime(tz)?     │
│ UNIQUE(provider,subj)  │  └─────────────────────────────────┘
└────────┬───────────────┘
         │ 1:N
         ▼
┌──────────────────────────┐
│  PasswordResetToken      │
│──────────────────────────│
│ id          │ BigInt PK  │
│ identity_id │ FK!        │
│ token_hash  │ Text! UNIQ │
│ created_at  │ DateTime!  │
│ expires_at  │ DateTime!  │
│ used_at     │ DateTime?  │
└──────────────────────────┘
```

## API

**Base:** `/api/v1/auth`

**Full OpenAPI spec:** [`docs/api/openapi.yaml`](../api/openapi.yaml)

### Public

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/register` | `{email, password, display_name?, units?}` | `{user, tokens}` 201 |
| POST | `/login` | `{email, password}` | `{user, tokens}` 200 |
| POST | `/google` | `{id_token}` | `{user, tokens}` 200 |
| POST | `/refresh` | `{refresh_token}` | `{access_token, refresh_token, expires_in}` 200 |
| POST | `/password-reset/request` | `{email}` | `{message}` 200 (always success) |
| POST | `/password-reset/confirm` | `{token, new_password}` | `{message}` 200 |

### Protected (Bearer)

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/me` | — | `{id, email, display_name, locale_pref, ui_lang, audio_lang, units, created_at, providers[]}` 200 |
| PATCH | `/me` | `{display_name?, units?, ...}` | Updated UserResponse 200 |
| DELETE | `/me` | — | `{message}` 200 |
| POST | `/logout` | `{refresh_token}` | `{message}` 200 |
| POST | `/logout-all` | — | `{message}` 200 (increments token_version) |

**Errors:** 400 (bad request), 401 (invalid auth), 404 (not found), 409 (email exists), 422 (validation)

## Patterns

**Roles:** Single role per account. Checked via JWT claim or DB lookup.
- `user` — End user (default). Mobile app access only.
- `editor` — Content creator. Can create/edit tours, access `/editor/*` endpoints.
- `admin` — Administrator. Full access including `/admin/*` endpoints.

**Password:** Argon2id `time=3, memory=64MB (65536KB), parallelism=4, hash_len=32, salt_len=16`

**Access Token:** JWT HS256, 30min expiry
```json
{"sub": "123", "tv": 0, "exp": 1705312200, "type": "access"}
```

**Refresh Token:** SHA-256 hash stored, 30d expiry, rotation on use (old revoked, new issued)

**Multi-provider:** User can link both email + google to single account via email match

**Password Reset:** 1h expiry, single-use, SHA-256 hash stored

## Stories

- **US-015** Fast seamless email authorization on launch
- **US-011i** Save settings and sync between devices

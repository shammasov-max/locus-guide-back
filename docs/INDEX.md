# Documentation Index

Quick navigation for Claude context management.

## Domain Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         LOCUS GUIDE                             │
├─────────────────┬─────────────────┬─────────────────────────────┤
│     AUTH        │      GEO        │          TOURS              │
│   (identity)    │   (locations)   │     (core business)         │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Account         │ Country         │ Tour                        │
│ AuthIdentity    │ City            │ Route                       │
│ RefreshToken    │ AlternateName   │ Waypoint                    │
│ PasswordReset   │ CitySearchIndex │ Run                         │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Quick Links

| Domain | Docs | Stories |
|--------|------|---------|
| **Auth** | [auth.md](domains/auth.md) | US-015, US-011i |
| **Geo** | [geo.md](domains/geo.md) | US-001, US-002 |
| **Tours** | [tours.md](domains/tours.md) | US-003..053 |

## Dependencies

```
Auth ─────────────────────────────────┐
  │ provides: JWT, user identity      │
  ▼                                   ▼
Geo ◄───────────────────────────► Tours
  │ provides: City for location       │
  └───────────────────────────────────┘
```

## File Structure

```
docs/
├── INDEX.md                 ← You are here
├── user-stories.md          ← Backend (30 stories)
├── user-stories-frontend.md ← Frontend (21 stories)
└── domains/
    ├── auth.md              ← ERD + API + patterns
    ├── geo.md
    └── tours.md
```

## Code Structure (Target)

```
app/
├── auth/        ← models, schemas, routes, service, security
├── geo/         ← models, schemas, routes, service
├── tours/       ← models, schemas, routes, service
├── common/      ← database, config, exceptions
└── main.py
```

## Notation

*Used in ERD diagrams:*
`!`=NOT NULL | `?`=nullable | `*`=indexed | `PK`=primary key | `FK`=foreign key

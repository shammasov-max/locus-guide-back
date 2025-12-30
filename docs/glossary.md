# Entity Glossary — Locus Guide

> Extracted from user-stories.md

---

## Actors (Roles)

| Entity | Description |
|--------|-------------|
| **User** | End user of mobile app. Browses trips, makes purchases, tracks progress, earns achievements |
| **Editor** | Content creator. Creates/edits trips, manages drafts, uploads audio, tests in simulation |
| **Admin** | Administrator. Manages editor permissions, creates bundles, sets prices, views analytics |
| **System** | Background processes and automation (deferred to tech spec) |

---

## Core Domain Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **City** | Geographic location containing trips | name, trip_count, coordinates |
| **Trip** | Audio guide with Route | title, duration, elevation_gain, language, status, price |
| **POI (Point)** | Point of Interest on a trip | trip_index, display_number, coordinates, description |
| **Audio File** | Audio content attached to POI | language, file_url, pattern: `poi_{seq_no}.mp3` |
| **Route** | Published snapshot of trip content (versioned) | version_number, point_ids, created_at |
| **Draft** | Editor's working version (JSON in `trips.draft_geojson`) | Not visible to users |

---

## User-Related Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Purchase** | Record of user buying a trip or bundle | user_id, trip_id, purchased_at, price_paid |
| **Progress** | User's completion state on a route | user_id, route_id, completed_points[], listen_positions{} |
| **Wishlist** | Trips user wants to purchase later | user_id, trip_id |
| **Settings** | User preferences synced across devices | character (male/female), metric_system (km/miles), language |
| **Achievement** | Gamification reward, immutable once earned | type, earned_at, city_at_completion |

---

## Monetization Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Bundle** | Collection of trips sold with discount | name, trips[], price, discount_percent |
| **Trial** | First 4 POIs available free on paid trips | Calculated from trip_index sort |

---

## Authentication Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Magic Link** | Passwordless auth token sent via email | expires_in: 15min, rate_limit: 5/hour |
| **JWT Token** | Authorization token for API access | user_id, expiry |

---

## Entity Relationships

```
City 1──* Trip
Trip 1──* POI
POI 1──* AudioFile (per language)
Trip 1──* Route
Trip 1──1 Draft

User 1──* Purchase
User 1──* Progress (per Route)
User 1──* Wishlist
User 1──1 Settings
User 1──* Achievement

Bundle *──* Trip
Editor 1──* Trip (ownership)
Admin 1──* Editor (permission management)
```

---

## Achievement Types

| Achievement | Trigger | Threshold |
|-------------|---------|-----------|
| First Steps | Complete first trip by GPS | 1 trip |
| Curious | Trips completed >90% | 5 trips |
| Explorer | Trips completed >90% | 15 trips |
| Traveler | Trips completed >90% | 30 trips |
| Nomad | Trips completed >90% | 50 trips |
| Road Legend | Trips completed >90% | 100 trips |
| Tourist | Unique cities visited | 3 cities |
| Cosmopolitan | Unique cities visited | 10 cities |
| World Citizen | Unique cities visited | 25 cities |
| City Collector | Unique cities visited | 50 cities |
| Fully Explored | 100% trip completion | per trip |

---

## Key Business Rules (from AC)

- **Trial**: First 4 POI by `trip_index` for paid trips
- **Version Lock**: User stays on started version until completion
- **Progress Sync**: Union merge across devices (`merged = A ∪ B`)
- **In-place Edits**: Text fixes apply to ALL versions
- **Achievements**: Never revoked, one per trip completion
- **Bundle Ownership**: Hide bundle if user owns any trip from it

---

*Generated from user-stories.md | 2025-12-31*

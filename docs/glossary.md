# Entity Glossary — Locus Guide

> Extracted from user-stories.md

---

## Actors (Roles)

| Entity | Description |
|--------|-------------|
| **User** | End user of mobile app. Browses tours, makes purchases, tracks progress, earns achievements |
| **Editor** | Content creator. Creates/edits tours, manages drafts, uploads audio, tests in simulation |
| **Admin** | Administrator. Manages editor permissions, creates bundles, sets prices, views analytics |
| **System** | Background processes and automation (deferred to tech spec) |

---

## Core Domain Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **City** | Geographic location containing tours |
| **Tour** | Product with the history of published Routes | 
| **Route** | Route with complex geodata to render and POIs | 
| **POI (Point)** | Point of Interest on a tour | guid, route_index, display_number, coordinates, description,  |
| **Audio File** | Audio content attached to POI | language, file_url, pattern: `poi_{seq_no}.mp3` |
| **Route** | Published snapshot of tour content (versioned) | version_number, point_ids, created_at |
| **Draft** | Editor's working version (JSON in `tours.draft_geojson`) | Not visible to users |

---

## User-Related Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Purchase** | Record of user buying a tour or bundle | user_id, tour_id, purchased_at, price_paid |
| **Progress** | User's completion state on a route | user_id, route_id, completed_points[], listen_positions{} |
| **Wishlist** | Tours user wants to purchase later | user_id, tour_id |
| **Settings** | User preferences synced across devices | character (male/female), metric_system (km/miles), language |
| **Achievement** | Gamification reward, immutable once earned | type, earned_at, city_at_completion |

---

## Monetization Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Bundle** | Collection of tours sold with discount | name, tours[], price, discount_percent |
| **Trial** | First 4 POIs available free on paid tours | Calculated from tour_index sort |

---

## Authentication Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Magic Link** | Passwordless auth token sent via email | expires_in: 15min, rate_limit: 5/hour |
| **JWT Token** | Authorization token for API access | user_id, expiry |

---

## Entity Relationships

```
City 1──* Tour
Tour 1──* POI
POI 1──* AudioFile (per language)
Tour 1──* Route
Tour 1──1 Draft

User 1──* Purchase
User 1──* Progress (per Route)
User 1──* Wishlist
User 1──1 Settings
User 1──* Achievement

Bundle *──* Tour
Editor 1──* Tour (ownership)
Admin 1──* Editor (permission management)
```

---

## Achievement Types

| Achievement | Trigger | Threshold |
|-------------|---------|-----------|
| First Steps | Complete first tour by GPS | 1 tour |
| Curious | Tours completed >90% | 5 tours |
| Explorer | Tours completed >90% | 15 tours |
| Traveler | Tours completed >90% | 30 tours |
| Nomad | Tours completed >90% | 50 tours |
| Road Legend | Tours completed >90% | 100 tours |
| Tourist | Unique cities visited | 3 cities |
| Cosmopolitan | Unique cities visited | 10 cities |
| World Citizen | Unique cities visited | 25 cities |
| City Collector | Unique cities visited | 50 cities |
| Fully Explored | 100% tour completion | per tour |

---

## Key Business Rules (from AC)

- **Trial**: First 4 POI by `tour_index` for paid tours
- **Version Lock**: User stays on started version until completion
- **Progress Sync**: Union merge across devices (`merged = A ∪ B`)
- **In-place Edits**: Text fixes apply to ALL versions
- **Achievements**: Never revoked, one per tour completion
- **Bundle Ownership**: Hide bundle if user owns any tour from it

---

*Generated from user-stories.md | 2025-12-31*

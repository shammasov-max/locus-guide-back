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

## Core Domain Entities

| Entity | Description | Key Attributes |
|--------|-------------|----------------|
| **Account** | Unified identity for User, Editor, and Admin roles | guid, email, role, created_at |
| **City** | Geographic location containing tours. Optional for Tours. System seed data (not user-created) | (define later) |
| **Tour** | Product unit containing a set of Waypoints. Has single active Route + version history for in-progress Runs, plus a non-empty draft Route. Soft delete only (archived, never permanently deleted) | guid, city_id (optional), waypoints[], active_route_id, draft_route_id, is_archived |
| **Route** | Belongs to a Tour. GeoJSON is source of truth for coordinates. Maps Waypoints to inner data structures (coordinates, route_index, display_number, is_visible). Holds precomputed distance, altitude, time to arrive. Lifecycle: Draft → Published. In-progress Runs continue on their original Route version when new version is published | guid, tour_id, geojson, status (draft/published), version, distance, altitude, estimated_time |
| **Waypoint** | Element of a Tour. `is_checkpoint` determines if tracked for Run completion; non-checkpoint waypoints are informational only | guid, tour_id, i18n description, i18n audio, is_checkpoint |
| **Run** | Progress of an Account on a Route. Requires explicit start (user initiates). States: started → completed \| abandoned. `is_simulation` flag for Editor testing (excluded from analytics). `completed_checkpoints` tracks only checkpoint Waypoints | guid, route_id, account_id, started_at, completed_at, abandoned_at, completed_checkpoints[], is_simulation |

---

## Deferred Entities

The following entities are out of scope for the current specification and will be defined later:

| Entity | Notes |
|--------|-------|
| **Achievement** | User rewards/badges system |
| **Bundle** | Admin-created product groupings |
| **Purchase** | Payment and transaction records |

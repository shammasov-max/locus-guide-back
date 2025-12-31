# User Stories — Locus Guide (Backend)

> **Prerequisites:** Read domain schemas before reviewing stories:
> - `domains/auth.md` — Account, AuthIdentity
> - `domains/geo.md` — Country, City
> - `domains/tours.md` — Tour, Route, Waypoint, Run

> Frontend-only stories (`-FE` suffix) have been moved to `user-stories-frontend.md`

## Roles

| Role | Description |
|------|-------------|
| **User** | End user of mobile app |
| **Editor** | Content creator, tour editor |
| **Admin** | Administrator, product/marketing manager |
| **System** | Background processes, automation | *(stories deferred to tech spec)*

---

> **Confidence**: 🟢 90-100% | 🟡 70-89% | 🟠 50-69% | 🔴 <50%

---

## 1. Discovery & Navigation

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-001** | User | I want to **see a list of available cities with tour counts** so that **I can choose a city of interest to explore** | 🟢 95% | — |
| **US-002** | User | I want **the app to automatically detect my location and show nearby tours** so that **I can quickly find relevant options** | 🟢 90% | AC: Default radius 50km. Fallback to manual city selection if GPS unavailable. |
| **US-003** | User | I want to **see tour cards with title, duration, elevation gain, language, status, and price** so that **I can choose a suitable tour** | 🟢 95% | — |
| **US-004** | User | I want to **see waypoints on the map and listen to available audio before purchase** so that **I can make a purchase decision** | 🟢 90% | AC: Full audio for first 4 waypoints (aligns with US-013a). |
| **US-012b** | User | I want to **filter tours (Near Me, Purchased, Await List, In Progress, Downloaded)** so that **I can quickly find what I need** | 🟢 90% | AC: Await List = tours with is_coming_soon. In Progress = active Runs. |

---

## 2. GPS & Progress Tracking

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-011i** | User | I want to **save settings (character, metric system, language) and sync between devices** so that **I don't have to reconfigure when switching phones** | 🟢 90% | Backend API required |
| **US-012a** | User | I want to **manage offline cache (download/delete), with ability to re-download deleted items** so that **I can free up space and use offline** | 🟡 85% | Original compares to "deleted apps on iPhone" |
| **US-036** | User | I want **progress to sync between devices and be tied to locked route** so that **I can continue without losing data** | 🟢 95% | AC: Set-union merge for completed_checkpoints. Never lose progress. |
| **US-036b** | User | I want to **explicitly abandon a run** so that **I can start fresh or switch to another tour** | 🟢 95% | AC: After abandon, new Run starts on latest active_route. No auto-timeout. |

---

## 3. Versioning & Content Lifecycle

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-021** | User | I want to **walk the route I started with until completion** so that **my progress doesn't break due to updates** | 🟢 95% | AC: Structure locked (waypoint order), content shared (typo fixes visible). See ADR-002. |
| **US-033** | Editor | I want to **work with draft version (JSON in routes.draft_geojson) before publishing** so that **I can freely edit without affecting users** | 🟡 85% | Missing AC: GET/PATCH endpoints, copying on publish |
| **US-037** | Editor | I want to **fix typos in published tours without versioning (in-place), but receive warning on structural changes** so that **I understand the impact on users** | 🟢 95% | AC: Text/audio = in-place (visible to locked Runs). Structure = new version. See ADR-002. |
| **US-052** | Editor | I want to **view all past published routes of a tour** so that **I understand the change history** | 🟢 90% | Rollback forbidden — there may be active users on old route snapshots |
| **US-053** | Editor | I want to **mark waypoints as checkpoints or informational** so that **I control what counts toward completion** | 🟢 90% | Default: is_checkpoint=true; immutable after creation |

---

## 4. Multilingual Content

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-010** | User | I want to **choose interface and audio language from 10+ languages** so that **I can use the app comfortably** | 🟢 95% | — |
| **US-039** | Editor | I want to **publish languages only when 100% ready (audio + translation)** so that **users don't see incomplete content** | 🟢 95% | AC: Editor explicitly marks language as complete (checklist). See ADR-007. |
| **US-041** | Editor | I want to **specify planned languages and mark ready ones (languages: {lang: bool})** so that **I can control visibility** | 🟢 90% | — |

---

## 5. Content Creation (Admin Panel)

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-019** | Editor | I want to **use a drag-and-drop constructor on the map with preview** so that **I can easily create and save quality content and stories to server** | 🟢 90% | — |
| **US-020** | Editor | I want to **test the tour in simulation mode before publishing** so that **I can verify transition and navigation logic** | 🟢 95% | — |
| **US-031** | Admin | I want to **manage editor permissions (list, assign/revoke by email, navigate to tours)** so that **I can control access** | 🟡 85% | Missing AC: endpoints, editor sees only their tours |
| **US-034** | Editor | I want to **have automatic free access to my tours** so that **I can test in the app without purchasing** | 🟢 95% | — |
| **US-040** | Editor | I want to **upload and replace audio files (single/batch) with auto-matching by pattern poi_{seq_no}.mp3** so that **I can efficiently populate tours** | 🟢 90% | — |

---

## 6. Monetization & Auth

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-013a** | User | I want to **listen to the first 4 waypoints free on each paid tour** so that **I can try the service without commitment** | 🟢 95% | — |
| **US-013b** | User | I want to **purchase individual tours with desired language ($3-$8) via in-app purchase** so that **I only pay for what I need** | 🟠 60% | Purchase entity deferred |
| **US-015** | User | I want **fast seamless email authorization on launch** so that **I don't lose purchases when switching phones** | 🟢 90% | — |
| **US-042** | User | I want to **purchase bundles (tour collections) with a discount** so that **I save when buying multiple tours** | 🟠 60% | Bundle entity deferred |
| **US-043** | Admin | I want to **create and manage bundles (select tours, set price and discount)** so that **I can offer advantageous collections to users** | 🟠 60% | Bundle entity deferred |

---

## 7. Gamification

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-025** | User | I want to **get "First Steps" achievement for completing my first tour by GPS** so that **I feel the journey beginning** | 🟠 60% | Achievement entity deferred |
| **US-026** | User | I want to **get achievements for tours >90%: "Curious"(5), "Explorer"(15), "Traveler"(30), "Nomad"(50), "Road Legend"(100)** so that **I have motivation** | 🟠 60% | Achievement entity deferred |
| **US-027** | User | I want to **get achievements for cities: "Tourist"(3), "Cosmopolitan"(10), "World Citizen"(25), "City Collector"(50)** so that **I can collect** | 🟠 60% | Achievement entity deferred |
| **US-028** | User | I want to **get "Fully Explored" achievement for 100% tour completion** so that **I strive for complete exploration** | 🟠 60% | Achievement entity deferred |

---

## 8. Analytics & Marketing

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-030** | User | I want to **receive push/email when a tour from Await List is published** so that **I learn about new content** | 🟢 90% | AC: Triggered when is_coming_soon tour gets active_route_id set. |
| **US-030b** | User | I want to **add Coming Soon tours to my Await List** so that **I'm notified when they become available** | 🟢 95% | AC: Only tours with is_coming_soon=true can be awaited. |
| **US-030c** | User | I want to **watch a city and receive notification when new tours appear** so that **I discover content in places I'm interested in** | 🟢 95% | AC: Notification on first publish of any tour in watched city. |

---

## Confidence Summary

| Confidence | Count | % |
|---|---|---|
| 🟢 90-100% | 24 | 75% |
| 🟡 70-89% | 3 | 9% |
| 🟠 50-69% | 5 | 16% |
| 🔴 <50% | 0 | 0% |

---

## Role Summary

| Role | User Stories |
|---|---|
| User | US-001..004, US-010..013, US-021, US-025..028, US-030, US-030b, US-030c, US-036, US-036b, US-042 |
| Editor | US-019, US-020, US-033, US-034, US-037, US-039..041, US-052, US-053 |
| Admin | US-031, US-043 |
| System | — |

---

## Technical Implementation Notes (Backend)

Decisions delegated to frontend (backend only stores state):
- **Skip delta 5 logic:** FE determines when to skip auto-play; backend API marks `visited`/`listened`
- **Teleport handling:** FE decides what to do with skipped points
- **GPS unavailable:** FE fallback to manual mode; backend doesn't depend on GPS
- **Offline download resume:** FE decides resume vs restart
- **GPS_QUEUED color:** FE chooses visualization; backend stores `visited_by_gps: bool`

---

*Generated: 2025-12-30 | Updated: 2025-12-31 (Spec-panel review: +AC for 10 stories, +US-030b/030c, terminology fixes, see decisions.md)*

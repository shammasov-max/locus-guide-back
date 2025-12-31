# User Stories — Locus Guide (Backend)

> Frontend-only stories (`-FE` suffix) have been moved to `_user-stories-frontend.md`

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
| **US-002** | User | I want **the app to automatically detect my location and show nearby tours** so that **I can quickly find relevant options** | 🟡 85% | Original specifies "in a specific city" |
| **US-003** | User | I want to **see tour cards with title, duration, elevation gain, language, status, and price** so that **I can choose a suitable tour** | 🟢 95% | — |
| **US-004** | User | I want to **see tour points on the map and listen to available audio before purchase** so that **I can make a purchase decision** | 🟡 80% | See AC below |
| **US-012b** | User | I want to **filter tours (Near Me, Purchased, Wished, Wanted, Downloaded)** so that **I can quickly find what I need** | 🟡 75% | Original has **two US-012b** — this is the first. Numbering bug in source |

#### AC for US-004 / Audio API (Audio Access):
1. Paid tour (price>0) NOT purchased → first 4 audio files available (trial)
2. Paid tour purchased → all audio files available
3. Free tour (price=0) → all audio files available to all users
4. Verification at API level by authorized JWT
5. Editor has access to all audio files of their tours without purchase

#### AC for price management (US-004, US-013a):
1. **Admin** can change the price of any tour
2. **Editor** can change the price only of their own tours
3. Minimum price: no restrictions (from $0.01)
4. price=0 — free tour (no trial)

---

## 2. GPS & Progress Tracking

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-011i** | User | I want to **save settings (character, metric system, language) and sync between devices** so that **I don't have to reconfigure when switching phones** | 🟢 90% | Backend API required |
| **US-012a** | User | I want to **manage offline cache (download/delete), with ability to re-download deleted items** so that **I can free up space and use offline** | 🟡 85% | Original compares to "deleted apps on iPhone" |
| **US-036** | User | I want **progress to sync between devices and be tied to locked route** so that **I can continue without losing data** | 🟢 90% | See AC below |

#### AC for US-021/US-036 (Version Lock & Sync):
1. **Version lock:** User stays on the route (versioned snapshot) they started with until completion
2. **Progress is calculated** based on locked route (point_ids of that snapshot)
3. **Version storage:** unlimited — all route snapshots stored forever
4. **Cross-device sync:** union merge — combining completed points from all devices
5. **Parallel marking:** user can mark points from different devices in parallel
6. **Merge strategy:** `merged_completed = device_a.completed ∪ device_b.completed`
7. **Listen position:** on conflict, max position per point is taken
8. **Upgrade:** User can voluntarily upgrade to new route snapshot (with progress loss)

#### AC for US-011i (User Settings):
1. **Character:** male/female choice (expandable in future)
2. **Metric system:** km/miles
3. **Language:** interface + audio preference
4. **Sync:** settings tied to account, available on all devices
5. **API:** GET/PATCH /users/me/settings
6. **Offline:** local cache with sync on connection

---

## 3. Versioning & Content Lifecycle

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-021** | User | I want to **walk the route I started with until completion** so that **my progress doesn't break due to updates** | 🟢 90% | — |
| **US-033** | Editor | I want to **work with draft version (JSON in routes.draft_geojson) before publishing** so that **I can freely edit without affecting users** | 🟡 85% | Missing AC: GET/PATCH endpoints, copying on publish |
| **US-037** | Editor | I want to **fix typos in published tours without versioning (in-place), but receive warning on structural changes** so that **I understand the impact on users** | 🟢 90% | — |
| **US-052** | Editor | I want to **view all past published routes of a tour** so that **I understand the change history** | 🟢 90% | Rollback forbidden — there may be active users on old route snapshots |

#### AC for US-037 (Versioning on Edit):
1. Text/description fix = no new version (in-place)
2. Adding/removing points = creates new version on PUBLISH
3. Changing tour_index/display_number = no new version
4. Point IDs are immutable (never change)
5. Warning when attempting to change structure of published tour
6. **In-place edits apply to ALL routes** of the tour (including old snapshots that users are tied to)

#### AC for US-033/US-034 (Draft and Editor Access):
1. **Draft** — editor's working version, not visible to users
2. **Published** — created from draft on publish
3. Editor can **reset draft** to last published route
4. In mobile app, editor **always sees draft version** of their tours
5. **Editor's progress resets** when new route is published

---

## 4. Multilingual Content

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-010** | User | I want to **choose interface and audio language from 10+ languages** so that **I can use the app comfortably** | 🟢 95% | — |
| **US-039** | Editor | I want to **publish languages only when 100% ready (audio + translation)** so that **users don't see incomplete content** | 🟢 90% | — |
| **US-041** | Editor | I want to **specify planned languages and mark ready ones (languages: {lang: bool})** so that **I can control visibility** | 🟢 90% | — |

#### AC for US-039/US-041 (Multilingual Content):
1. Editor adds planned languages to draft version of tour
2. **Language readiness is marked in draft:** `languages: {ru: true, en: false}`
3. On publish, Editor specifies which languages are available to users
4. **Publishing <100% is possible with warning** (soft requirement, not blocking)
5. New languages are added to published route **in-place** (without creating new route snapshot)
6. Language is visible to users only if marked ready in published route

---

## 5. Content Creation (Admin Panel)

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-019** | Editor | I want to **use a drag-and-drop constructor on the map with preview** so that **I can easily create and save quality content and stories to server** | 🟢 90% | — |
| **US-020** | Editor | I want to **test the tour in simulation mode before publishing** so that **I can verify transition and navigation logic** | 🟢 95% | — |
| **US-031** | Admin | I want to **manage editor permissions (list, assign/revoke by email, navigate to tours)** so that **I can control access** | 🟡 85% | Missing AC: endpoints, editor sees only their tours |
| **US-034** | Editor | I want to **have automatic free access to my tours** so that **I can test in the app without purchasing** | 🟢 95% | — |
| **US-040** | Editor | I want to **upload and replace audio files (single/batch) with auto-matching by pattern poi_{seq_no}.mp3** so that **I can efficiently populate tours** | 🟢 90% | — |

#### AC for US-031 (Editor Permission Management):
1. **Admin creation:** manually in database (SQL), no UI
2. **On revoking editor rights:**
   - **Published tours** remain live, available to users
   - Editor loses access to edit their tours
   - **Draft tours** are preserved in database (not deleted)
   - Admin can assign another editor to these tours
3. **On restoring rights:**
   - Tours are **NOT automatically re-assigned** to editor
   - Admin must **manually reassign** tours to editor
4. Editor sees only their tours in admin panel

---

## 6. Monetization & Auth

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-013a** | User | I want to **listen to the first 4 points free on each paid tour** so that **I can try the service without commitment** | 🟢 95% | See AC below |
| **US-013b** | User | I want to **purchase individual tours with desired language ($3-$8) via in-app purchase** so that **I only pay for what I need** | 🟢 90% | — |
| **US-015** | User | I want **fast seamless email authorization on launch** so that **I don't lose purchases when switching phones** | 🟢 90% | — |
| **US-042** | User | I want to **purchase bundles (tour collections) with a discount** so that **I save when buying multiple tours** | 🟢 90% | After bundle purchase — card disappears, individual tours appear |
| **US-043** | Admin | I want to **create and manage bundles (select tours, set price and discount)** so that **I can offer advantageous collections to users** | 🟢 90% | Tours from bundle can be purchased separately too |

#### AC for US-013a (Trial — definition of "point"):
1. **"Point" = POI entity** by `tour_index`, regardless of audio presence
2. **Trial = first 4 POI** sorted by `tour_index`
3. If tour has <4 POI → all are available in trial
4. POI without audio in user's language → show text description
5. Global configuration: 4 points for all paid tours

#### AC for US-015 (Magic Link Authorization):
1. **Link expiry:** 15 minutes
2. **Resend:** "Resend" button available after 60 seconds
3. **Rate limit:** max 5 attempts per hour per email
4. **Multi-device:** link works on any device (not tied to requesting device)
5. **Error messages:**
   - `EMAIL_NOT_FOUND`: "Email not found. Please verify or register"
   - `RATE_LIMITED`: "Too many attempts. Please wait 10 minutes"
   - `LINK_EXPIRED`: "Link expired" + resend button

#### AC for US-042/US-043 (Bundles):
1. **After bundle purchase** all tours from bundle are available to user **forever** — as if purchased separately
2. For tours from purchased bundle, **"Start"** button is displayed instead of "Buy"
3. Tours from bundle can be purchased separately (before bundle purchase)
4. **RESOLVED: Partial ownership** — hide bundle if user owns any tour from it
5. User can purchase remaining tours only separately

---

## 7. Gamification

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-025** | User | I want to **get "First Steps" achievement for completing my first tour by GPS** so that **I feel the journey beginning** | 🟢 90% | — |
| **US-026** | User | I want to **get achievements for tours >90%: "Curious"(5), "Explorer"(15), "Traveler"(30), "Nomad"(50), "Road Legend"(100)** so that **I have motivation** | 🟢 90% | — |
| **US-027** | User | I want to **get achievements for cities: "Tourist"(3), "Cosmopolitan"(10), "World Citizen"(25), "City Collector"(50)** so that **I can collect** | 🟢 90% | — |
| **US-028** | User | I want to **get "Fully Explored" achievement for 100% tour completion** so that **I strive for complete exploration** | 🟢 90% | — |

#### AC for US-025..028 (Achievements):
1. **Immutable:** achievements are never revoked (once earned = forever)
2. **Once per tour:** one tour = one completion (repeat playthrough doesn't increase counter)
3. **Snapshot:** on completion, `city_at_completion` is saved (if tour is moved to another city)
4. **Grandfathered tours count:** tours with grandfathered access count toward achievements
5. **Trial completions:** completing only trial (4 points) does NOT count toward achievements
6. **Offline resilience:** completion is saved locally, sync on connection
7. **Deleted tours:** if tour is deleted after completion — achievement is preserved

---

## 8. Analytics & Marketing

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-017** | Admin | I want to **see detailed analytics (time in points, transitions, exits, clicks) via Firebase** so that **I can improve the product** | 🟢 90% | LA-story (analytics) |
| **US-030** | User | I want to **receive push/email when a tour from wishlist appears** so that **I learn about new content** | 🟢 90% | — |

---

## Confidence Summary

| Confidence | Count | % |
|---|---|---|
| 🟢 90-100% | 23 | 79% |
| 🟡 70-89% | 6 | 21% |
| 🟠 50-69% | 0 | 0% |
| 🔴 <50% | 0 | 0% |

---

## Problematic Stories (require attention)

| ID | Issue |
|---|---|
| 🟡 **US-012b** | Duplicated in original — second story renamed to US-022 |

---

## Role Summary

| Role | User Stories |
|---|---|
| User | US-001..004, US-010..013, US-021, US-025..028, US-030, US-036, US-042 |
| Editor | US-019, US-020, US-033, US-034, US-037, US-039..041, US-052 |
| Admin | US-017, US-031, US-043 |
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

*Generated: 2025-12-30 | Updated: 2025-12-31 (FE stories moved to _user-stories-frontend.md)*

# User Stories — Frontend Only (Locus Guide)

> Stories marked with `-FE` suffix indicate frontend-only implementation with no backend API required.

---

## 1. Discovery & Navigation

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-005-FE** | User | I want to **see my location on the map in real-time with direction indicator** so that **I can navigate** | 🟢 95% | — |

---

## 2. Audio Playback

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-006-FE** | User | I want to **walk the route with phone screen off and receive auto-play audio when reaching a point** so that **I don't need to look at my phone** | 🟢 90% | — |
| **US-007-FE** | User | I want to **control playback (pause, +-15sec, repeat)** so that **I can control the pace of the tour** | 🟢 95% | — |
| **US-008-FE** | User | I want to **see a progress bar with seek capability** so that **I can re-listen to interesting parts** | 🟢 95% | — |
| **US-011-FE** | User | I want to **hear navigation hints (e.g. "turn left around the fountain to the red building") that smoothly interrupt current voice and continue from -2sec after the hint** so that **I don't get lost** | 🟢 90% | — |
| **US-011b-FE** | User | I want **meetsound.mp3 to play when entering a new GPS zone; if current zone ends — start the one entered earlier (even if moved away); if left zone 2 and moved to zone 3, then after zone 1 plays zone 3, and zone 2 = "visited by GPS" (not played, but marked in database for manual listening)** so that **I don't miss points** | 🟢 90% | — |
| **US-011c-FE** | User | I want **points with delta number >5 from current not to auto-play when on the tour line** so that **I avoid false triggers at intersections** | 🟡 80% | Missing condition: "didn't deviate from tour line" |
| **US-011d-FE** | User | I want **pause to disable GPS, play to resume, and leaving zone without unpausing to enable GPS** so that **I can rest** | 🟡 85% | Added clarification about leaving zone |

---

## 3. GPS & Progress Tracking

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-011e-FE** | User | I want to **see an auto-play mode indicator (GPS on/off)** so that **I can manage battery** | 🟡 70% | Original suggests: "cat appears when GPS on" |
| **US-011f-FE** | User | I want **GPS to turn on when entering a tour and turn off when returning to the list** so that **I don't have to manage it manually** | 🟢 90% | — |
| **US-011g-FE** | User | I want **the cat to face the direction of the top of the phone** so that **I can orient myself on location** | 🟢 95% | — |
| **US-011h-FE** | User | I want **the cat to walk (walking animation) in the direction of movement** so that **I associate it with a game guide** | 🟢 95% | — |
| **US-012c-FE** | User | I want to **see points in different colors (purple/green/blue/orange) and numbers** so that **I understand completion status** | 🟢 90% | — |
| **US-012d-FE** | User | I want to **see audio playback controls on the lock screen** so that **I can start and stop the tour without opening the app** | 🟢 95% | Default iOS behavior for audio playback |

#### Acceptance Criteria for US-012c (Point Visualization):
1. **Start/Finish:** first point = "Start", last = "Finish"
2. **Numbers:** each point has a sequence number
3. **Colors:**
   - **Purple** — not visited (no GPS, no manual start)
   - **Green** — automatically started by GPS and fully listened
   - **Blue** — started manually, not listened to completion
   - **Orange** — listened manually to completion without GPS presence
4. **Tour line:** changes color to the color of listened point, if previous point is not purple
5. **RESOLVED: GPS_QUEUED state** — frontend-side solution (backend stores `visited_by_gps: bool` state)

---

## 4. Multilingual Content

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-009-FE** | User | I want **interface and audio language to default to system language** so that **I don't spend time on setup** | 🟢 95% | — |

---

## 5. Analytics & Marketing

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-016-FE** | Admin | I want to **show 1000 cities with "in development" label and notification subscription** so that **I create an illusion of a large catalog and measure demand** | 🟢 90% | Ads targeted to cities where tours exist |
| **US-017-FE** | Admin | I want to **see detailed analytics (time in points, transitions, exits, clicks) via Firebase** so that **I can improve the product** | 🟢 90% | Moved from backend — Firebase SDK is frontend |
| **US-017b-FE** | Admin | I want to **capture click_id and UTM on install via Firebase Dynamic Links (Deferred Deep Link)** so that **I can attribute installs to Instagram/TikTok campaigns** | 🟢 90% | — |

---

## 6. Legal & UX

| ID | Role | Story | Confidence | Comment |
|---|---|---|---|---|
| **US-014-FE** | User | I want to **have access to Terms of Use and Privacy Policy from the app** so that **I understand legal aspects** | 🟢 95% | — |
| **US-018-FE** | User | I want **UX to be at a level where I don't think about inconveniences** so that **I use it comfortably** | 🟢 90% | Meta-story about UX quality |

---

## Confidence Summary

| Confidence | Count | % |
|---|---|---|
| 🟢 90-100% | 18 | 86% |
| 🟡 70-89% | 3 | 14% |
| 🟠 50-69% | 0 | 0% |
| 🔴 <50% | 0 | 0% |


## Technical Implementation Notes

Decisions delegated to frontend (backend only stores state):
- **Skip delta 5 logic:** FE determines when to skip auto-play; backend API marks `visited`/`listened`
- **Teleport handling:** FE decides what to do with skipped points
- **GPS unavailable:** FE fallback to manual mode; backend doesn't depend on GPS
- **Offline download resume:** FE decides resume vs restart
- **GPS_QUEUED color:** FE chooses visualization; backend stores `visited_by_gps: bool`

---

*Extracted from user-stories.md | Total: 21 frontend-only stories | Updated: 2025-12-31 (+US-017-FE, +US-012d-FE)*

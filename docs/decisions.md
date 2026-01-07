# Architecture Decision Log — Locus Guide

> Decisions made during spec-panel review (2025-12-31)

---

## ADR-001: Role System Implementation

**Decision:** Single `role` field on Account table
**Options considered:**
1. Role field on Account (`role ENUM`) ✓
2. Separate Roles table (many-to-many)
3. Boolean flags (`is_editor`, `is_admin`)

**Rationale:** Simplest approach. Users have exactly one role. No need for multiple roles per account in current scope.

---

## ADR-002: Run Locking Strategy

**Decision:** Content shared, structure locked
**Context:** When editor fixes typo (US-037), should locked Run see the fix?

**Behavior:**
- Waypoint text/audio updates → visible to all Runs (content shared)
- Route structure (waypoint order, membership) → locked to version at Run start

**Rationale:** Users benefit from typo fixes. Route structure determines progress tracking, so must stay consistent.

---

## ADR-003: Multi-Device Sync Conflict Resolution

**Decision:** Set-union merge for `completed_checkpoints`
**Options considered:**
1. Set-union merge ✓
2. Last-write-wins
3. Server-authoritative

**Rationale:** User should never lose progress. If waypoint completed on any device, it stays completed.

---

## ADR-004: Await List / Watch List Terminology

**Decision:** Replace "Wished/Wanted" with clear terms
**New definitions:**
- **Await List** — Tours with `is_coming_soon=true` user wants notified on publish
- **Watch List** — Cities where user wants notification of any new tour

**Rationale:** Original terms were ambiguous. New terms reflect actual user intent.

---

## ADR-005: Nearby Tour Radius

**Decision:** 50km default radius
**Options considered:**
1. 25km (urban-focused)
2. 50km (balanced) ✓
3. Dynamic by density

**Rationale:** 50km covers suburban areas with sparse content while still being relevant for urban users.

---

## ADR-006: Free Preview Scope

**Decision:** Fixed 4 waypoints, full audio
**US-013a + US-004 alignment:**
- First 4 waypoints free on paid tours
- Full audio available for preview waypoints (not clips)

**Rationale:** Consistent with original spec. Full audio gives better purchase decision experience.

---

## ADR-007: Language Publication Readiness

**Decision:** Editor explicit checklist
**Options considered:**
1. Audio + description required
2. Audio only
3. Explicit manual mark ✓

**Rationale:** Editor knows best when translation quality is sufficient. Automated checks can't verify content quality.

---

## ADR-008: Run Restart After Abandon

**Decision:** New run starts on latest `active_route` version
**Behavior:**
- User abandons Run v1
- User starts new Run → gets current `active_route` (may be v2+)
- Old abandoned Run stays in history

**Rationale:** Fresh start should use latest content. User explicitly chose to abandon previous progress.

---

## ADR-009: Run Timeout Policy

**Decision:** No automatic timeout
**Rationale:** Users may pause tours for weeks/months (travel, life events). Progress is valuable. User explicitly controls lifecycle via abandon action.

---

## ADR-010: NFR Documentation Strategy

**Decision:** Defer to separate technical specification
**Rationale:** User stories focus on behavior. Performance, rate limits, storage constraints belong in technical spec for implementation clarity.

---

## ADR-011: SuperTokens for Authentication

**Decision:** Replace custom JWT implementation with SuperTokens library
**Options considered:**
1. Custom JWT + refresh tokens (python-jose + bcrypt)
2. SuperTokens SDK + self-hosted Core ✓
3. Auth0 / Firebase Auth (managed SaaS)

**Context:**
Original design specified custom JWT + refresh token implementation with:
- Manual password hashing (Argon2id)
- Manual token generation/validation
- Custom refresh token rotation logic
- Custom password reset flow
- Manual Google ID token verification
- Custom session invalidation (token_version)

**Rationale:**
1. **Security:** Battle-tested session management, CSRF protection, secure token rotation
2. **Reduced complexity:** No custom token/session logic to maintain
3. **OAuth integration:** Built-in provider support with automatic account linking
4. **Extensibility:** Easy to add Apple, GitHub, etc. without code changes
5. **Dashboard:** Built-in admin UI for user management at `/auth/dashboard`
6. **Self-hosted:** No vendor lock-in, data stays in our PostgreSQL database

**Consequences:**
- Requires SuperTokens Core service (Docker container)
- Auth tables managed by SuperTokens, not Alembic migrations
- Simplified Account table (removed AuthIdentity, RefreshToken, PasswordResetToken)
- API paths split: SuperTokens at `/auth/*`, custom at `/api/v1/auth/*`
- Added `supertokens_user_id` column to link Account to SuperTokens user

**Removed from original design:**
- `AuthIdentity` table → SuperTokens `emailpassword_users` + `thirdparty_users`
- `RefreshToken` table → SuperTokens `session_info`
- `PasswordResetToken` table → SuperTokens `emailpassword_pswd_reset_tokens`
- `token_version` column → SuperTokens session revocation

---

*Generated: 2025-12-31*
*Updated: 2026-01-07 (ADR-011)*

# Locus Guide Backend - Comprehensive Code Review Report

**Review Date:** 2025-12-26
**Reviewed By:** Multi-Expert Panel (Security, Performance, Architecture, Quality)
**Project:** Locus Guide Backend - FastAPI Audioguide API

---

## Executive Summary

This comprehensive code review identified **81 issues** across 6 domains:

| Domain | P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low) | Total |
|--------|--------------|-----------|-------------|----------|-------|
| Security | 3 | 3 | 4 | 3 | 13 |
| Database Performance | 3 | 5 | 5 | 3 | 16 |
| API Design | 1 | 2 | 4 | 5 | 12 |
| Architecture | 0 | 1 | 10 | 3 | 14 |
| Testing | 0 | 2 | 6 | 3 | 11 |
| Production Readiness | 2 | 4 | 9 | 0 | 15 |
| **Total** | **9** | **17** | **38** | **17** | **81** |

### Top 5 Critical Issues Requiring Immediate Attention

1. **SECURITY-001:** Google OAuth Client ID Validation Bypass (P0)
2. **SECURITY-002:** Hardcoded JWT Secret Default Value (P0)
3. **SECURITY-003:** Password Reset Token Exposed in API Response (P0)
4. **DATABASE-001:** N+1 Query Pattern in `list_routes()` - 140+ queries/request (P0)
5. **DATABASE-003:** Sync SQLAlchemy Blocking Async Event Loop (P0)

---

## Table of Contents

1. [Security Findings](#1-security-findings)
2. [Database Performance Findings](#2-database-performance-findings)
3. [API Design Findings](#3-api-design-findings)
4. [Architecture Findings](#4-architecture-findings)
5. [Testing Findings](#5-testing-findings)
6. [Production Readiness Findings](#6-production-readiness-findings)
7. [Priority Matrix](#7-priority-matrix)
8. [Remediation Roadmap](#8-remediation-roadmap)

---

## 1. Security Findings

### Critical (P0)

#### SECURITY-001: Google OAuth Client ID Validation Bypass
- **File:** `app/auth/oauth/google.py:41`
- **Description:** Empty `google_client_id` configuration allows audience validation to be skipped entirely
- **Exploitation:** Attacker can authenticate with tokens from ANY Google OAuth application
- **Fix:** Fail startup if `google_client_id` is empty when OAuth is enabled:
```python
if not settings.google_client_id:
    raise GoogleAuthException("Google OAuth is not configured")
```

#### SECURITY-002: Hardcoded JWT Secret Default Value
- **File:** `app/config.py:10`
- **Description:** `jwt_secret_key: str = "change-me-in-production"` - predictable default
- **Exploitation:** All JWTs can be forged if deployed without override
- **Fix:** Remove default or validate at startup that secret is not the default value

#### SECURITY-003: Password Reset Token Exposed in API Response
- **File:** `app/auth/router.py:82-88`
- **Description:** Reset token returned directly in HTTP response (marked "development only")
- **Exploitation:** Attacker can reset any user's password without email access
- **Fix:** Add environment check; implement proper email delivery

### High (P1)

#### SECURITY-004: CORS Wildcard Origin with Credentials
- **File:** `app/main.py:28-34`
- **Description:** `allow_origins=["*"]` with `allow_credentials=True`
- **Impact:** Enables CSRF attacks from any origin
- **Fix:** Use explicit origin whitelist from environment configuration

#### SECURITY-005: Missing Rate Limiting on Authentication Endpoints
- **Files:** `app/auth/router.py` (all endpoints)
- **Description:** No rate limiting on login, registration, password reset
- **Impact:** Vulnerable to brute-force and credential stuffing attacks
- **Fix:** Implement `slowapi` with limits: login 5/min, reset 3/hour

#### SECURITY-006: OAuth Account Auto-Merge Without Verification
- **File:** `app/auth/service.py:191-206`
- **Description:** Google identity auto-linked to existing account by email match
- **Impact:** Account takeover if attacker controls email at Google
- **Fix:** Only merge when `email_verified=true`; require re-authentication

### Medium (P2)

#### SECURITY-007: Weak Token Hashing Algorithm
- **File:** `app/auth/security.py:40-41`
- **Description:** SHA-256 without salt for refresh token hashing
- **Fix:** Use HMAC with secret key for defense-in-depth

#### SECURITY-008: Logout Without Token Ownership Check
- **File:** `app/auth/service.py:264-272`
- **Description:** Any user can revoke any refresh token
- **Fix:** Verify `db_token.user_id` matches authenticated user

#### SECURITY-009: Database Credentials in Default Configuration
- **File:** `app/config.py:7`
- **Description:** Hardcoded `postgres:postgres` in default URL
- **Fix:** Remove default; validate at startup

#### SECURITY-010: GeoIP URL Format String Injection Risk
- **File:** `app/cities/geoip.py:38-40`
- **Description:** IP address used in URL without encoding
- **Fix:** Use `urllib.parse.quote()` for IP parameter

### Low (P3)

#### SECURITY-011: Password Only Enforces Length (8-128)
- **File:** `app/auth/schemas.py:11`
- **Fix:** Add complexity requirements or integrate `zxcvbn`

#### SECURITY-012: Role from JWT Not Verified Against Database
- **File:** `app/auth/dependencies.py:72-90`
- **Fix:** Fetch current role for critical operations

#### SECURITY-013: Missing LIKE Pattern Sanitization
- **File:** `app/routes/service.py:121-127`
- **Fix:** Escape `%` and `_` in search input

---

## 2. Database Performance Findings

### Critical (P0)

#### DATABASE-001: N+1 Query Pattern in `list_routes()`
- **File:** `app/routes/service.py:182-236`
- **Description:** For each route in loop:
  - Checkpoint count query
  - City query
  - WishedRoute check (if authenticated)
  - UserActiveRoute query (if authenticated)
  - `_calculate_user_progress()` (3 more queries)
- **Impact:** 20 routes = **140+ database queries** per request
- **Latency:** 500-2000ms per list call
- **Fix:** Use batch queries and eager loading:
```python
route_ids = [r.id for r in routes]
checkpoint_counts = self.db.query(
    Checkpoint.route_version_id, func.count(Checkpoint.id)
).filter(Checkpoint.route_version_id.in_(version_ids)).group_by(...).all()
```

#### DATABASE-002: N+1 in `get_route_checkpoints()`
- **File:** `app/routes/service.py:323-358`
- **Description:** VisitedPoint query per checkpoint
- **Impact:** 15 checkpoints = 15 extra queries
- **Fix:** Batch load all visited points in single query

#### DATABASE-003: Sync SQLAlchemy Blocking Async Event Loop
- **File:** `app/database.py:8-16`
- **Description:** Synchronous `Session` used with async FastAPI
- **Impact:** Blocks ALL concurrent requests during DB operations
- **Fix:** Migrate to `create_async_engine` with `asyncpg` or use `run_in_executor`

### High (P1)

#### DATABASE-004: Missing Connection Pool Recycle
- **File:** `app/database.py:8-13`
- **Description:** No `pool_recycle` setting; connections become stale
- **Fix:** Add `pool_recycle=1800` (30 minutes)

#### DATABASE-005: No Transaction Rollback on Exception
- **File:** `app/routes/service.py` (multiple)
- **Description:** `db.commit()` without try/except/rollback
- **Fix:** Wrap in try/except or use context manager

#### DATABASE-006: N+1 in `get_user_active_routes()`
- **File:** `app/routes/service.py:472-524`
- **Description:** 5 queries per active route
- **Fix:** Use eager loading with `selectinload`

#### DATABASE-007: N+1 in `get_user_wished_routes()`
- **File:** `app/wishes/service.py:121-135`
- **Description:** 2-3 queries per wish
- **Fix:** Batch load cities and versions

#### DATABASE-008: N+1 in Admin `get_route_wish_stats()`
- **File:** `app/wishes/service.py:295-318`
- **Description:** City + Version query per route
- **Fix:** Use joins in main query

### Medium (P2)

#### DATABASE-009: HSTORE Access Without Null Safety
- **File:** `app/routes/service.py:122-127`
- **Description:** `RouteVersion.summary_i18n[lang]` may fail on NULL
- **Fix:** Use `func.coalesce()` wrapper

#### DATABASE-010: Imported but Unused `selectinload`/`joinedload`
- **File:** `app/routes/service.py:4`
- **Description:** Eager loading tools imported but never applied
- **Fix:** Apply to main queries

#### DATABASE-011: Missing Composite Index for Nearby Filter
- **File:** `alembic/versions/001_initial_schema.py`
- **Description:** No index on `(route_version_id, seq_no)` for first checkpoint
- **Fix:** Add partial index: `WHERE seq_no = 0`

#### DATABASE-012: Inefficient LATERAL Join in City Search
- **File:** `app/cities/service.py:35-42`
- **Description:** Correlated subquery per city
- **Fix:** Use `DISTINCT ON` with window function

#### DATABASE-013: `_calculate_user_progress()` Executes 3 Queries
- **File:** `app/routes/service.py:28-61`
- **Description:** Separate COUNT queries for total, visited, audio_completed
- **Fix:** Combine into single query with conditional aggregates

### Low (P3)

#### DATABASE-014: Missing Index on `is_visible`
- **File:** `app/routes/models.py:231-238`
- **Fix:** Add partial index on `route_version_id WHERE is_visible = true`

#### DATABASE-015: Eager Loading `alternate_names` Always
- **File:** `app/cities/models.py:36`
- **Fix:** Change to `lazy="dynamic"` or explicit loading

#### DATABASE-016: Redundant `count()` Before `all()`
- **File:** `app/routes/service.py:178-179`
- **Fix:** Use window function for count in same query

---

## 3. API Design Findings

### Critical (P0)

#### API-001: Security Token Exposed in Password Reset Response
- **File:** `app/auth/router.py:82-88`
- **Description:** Same as SECURITY-003

### High (P1)

#### API-002: Error Handling via Dict Returns Instead of Exceptions
- **File:** `app/wishes/router.py:38-48`
- **Description:** Service returns `{"error": ...}` dict instead of raising
- **Fix:** Create custom exceptions in `app/common/exceptions.py`

#### API-003: Route Path Collision Risk
- **File:** `app/routes/router.py:155`
- **Description:** `/routes/me/routes` could conflict with route slug "me"
- **Fix:** Move to `/api/v1/me/routes` following wishes pattern

### Medium (P2)

#### API-004: Inconsistent Response Format for Admin Lists
- **File:** `app/routes/admin_router.py:43`
- **Description:** `response_model=dict` instead of Pydantic schema
- **Fix:** Create `RouteAdminListResponse` schema

#### API-005: Inconsistent DELETE Status Codes
- **Files:** `app/auth/router.py:141`, `app/routes/admin_router.py:92`
- **Description:** Auth DELETE returns 200, Routes DELETE returns 204
- **Fix:** Standardize on 204 No Content

#### API-006: Checkpoint Endpoints Outside Route Context
- **File:** `app/routes/router.py:96-152`
- **Description:** `/routes/checkpoints/{id}` breaks RESTful hierarchy
- **Fix:** Nest under route: `/routes/{route_id}/checkpoints/{checkpoint_id}`

#### API-007: Missing Language Parameter Validation
- **Files:** Multiple routers
- **Description:** `lang` accepted without checking supported languages
- **Fix:** Create common validation dependency

### Low (P3)

#### API-008: DELETE /me Returns 200 Instead of 204
- **File:** `app/auth/router.py:141`

#### API-009: Missing 409 for Existing Route Session
- **File:** `app/routes/router.py:173-198`

#### API-010: Unused GPS Coordinates in Mark Visited
- **File:** `app/routes/router.py:100-102`

#### API-011: Missing Pagination on Checkpoints Endpoint
- **File:** `app/routes/router.py:76-91`

#### API-012: async/sync Function Mixing
- **File:** `app/auth/router.py:44-63`

---

## 4. Architecture Findings

### High (P1)

#### ARCH-001: Service Layer Returns Presentation DTOs
- **Files:** `app/routes/service.py`, `app/wishes/service.py`
- **Description:** Services build complete response dicts with i18n resolution
- **Fix:** Return domain models; let routers build responses

### Medium (P2)

#### ARCH-002: Module Boundary Violations
- **File:** `app/routes/service.py:159-160`
- **Description:** Inline imports from wishes module to avoid circular deps
- **Fix:** Use domain events or shared query service

#### ARCH-003: Cross-Module Model Dependencies
- **File:** `app/wishes/service.py:10-11`
- **Description:** Imports Route, City models directly
- **Fix:** Define interfaces for cross-module queries

#### ARCH-004: Missing Repository Pattern
- **Files:** All service files
- **Description:** Direct `self.db.query()` in services
- **Fix:** Extract data access to repository classes

#### ARCH-005: Large Service Class (God Object)
- **File:** `app/routes/service.py` (959 lines)
- **Description:** Single class handles listing, progress, admin, versions
- **Fix:** Split into focused services

#### ARCH-006: Missing Transaction Boundaries
- **File:** `app/routes/service.py:392-401`
- **Description:** Multiple commits without rollback coordination
- **Fix:** Use Unit of Work pattern

#### ARCH-007: Service Layer Handles Commit Logic
- **Files:** All service files
- **Description:** `db.commit()` scattered in service methods
- **Fix:** Control transactions in router layer

#### ARCH-008: Synchronous Database Operations
- **Files:** All service files
- **Description:** Sync queries despite async FastAPI
- **Fix:** Migrate to async SQLAlchemy

#### ARCH-009: Duplicate i18n Resolution Logic
- **Files:** `app/routes/service.py:22-26`, `app/wishes/service.py:18-22`
- **Fix:** Extract to `app/common/i18n.py`

#### ARCH-010: Inconsistent Error Handling Patterns
- **Description:** Auth raises exceptions, Routes returns None, Wishes returns dicts
- **Fix:** Standardize on exception-based errors

#### ARCH-011: Missing Domain Events
- **Description:** No event system for cross-module communication
- **Fix:** Implement simple event emitter

### Low (P3)

#### ARCH-012: CurrentUser Dependency Duplication
- **Files:** `app/auth/dependencies.py:103`, `app/routes/dependencies.py:45`

#### ARCH-013: Hardcoded Language Fallback
- **Files:** Multiple service files
- **Fix:** Move to `settings.default_language`

#### ARCH-014: N+1 Patterns (detailed above)

---

## 5. Testing Findings

### High (P1)

#### TEST-001: No OAuth (Google) Flow Tests
- **File:** `tests/auth/test_auth.py`
- **Description:** Zero tests for `app/auth/oauth/google.py`
- **Missing:** Valid token, expired token, wrong audience, network failures

#### TEST-002: No Refresh Token Reuse Prevention Tests
- **File:** `tests/auth/test_auth.py`
- **Description:** Token rotation not verified
- **Missing:** Same token used twice should fail

### Medium (P2)

#### TEST-003: Missing Rate Limiting Tests
- **Description:** No rate limiting implemented or tested

#### TEST-004: No RBAC Edge Case Tests
- **Description:** Role downgrade, expired tokens, role mismatch

#### TEST-005: No Concurrent Access Tests
- **Description:** Race conditions not tested

#### TEST-006: Missing Password Reset Edge Cases
- **Description:** Token reuse, expiration, invalid format

#### TEST-007: No Security Input Validation Tests
- **Description:** SQL injection, XSS, path traversal

#### TEST-008: E2E Tests Create Permanent Data
- **File:** `tests/e2e/test_live_api.py`
- **Description:** No cleanup of created test users

### Low (P3)

#### TEST-009: Test Fixture Duplication
- **Description:** Helpers duplicated between test files

#### TEST-010: Missing GeoIP Service Tests
- **File:** `app/cities/geoip.py`

#### TEST-011: Missing Session Management Tests
- **Description:** Route progress lifecycle incomplete

---

## 6. Production Readiness Findings

### Critical (P0)

#### PROD-001: Health Check Ignores Database Connectivity
- **File:** `app/main.py:45-47`
- **Description:** Returns `{"status": "healthy"}` unconditionally
- **Fix:** Add database connectivity check; return 503 on failure

#### PROD-002: JWT Secret Default Not Validated
- **File:** `app/config.py:10`
- **Description:** Same as SECURITY-002

### High (P1)

#### PROD-003: No Structured Logging
- **File:** `app/main.py`
- **Description:** No logging configuration; only GeoIP uses logger
- **Fix:** Configure JSON logging with request IDs

#### PROD-004: No Request Tracing/Correlation IDs
- **Description:** Cannot trace requests across services
- **Fix:** Add middleware generating UUID per request

#### PROD-005: CORS Allows All Origins
- **File:** `app/main.py:28-34`
- **Description:** Same as SECURITY-004

#### PROD-006: Docker Image Runs as Root
- **File:** `Dockerfile`
- **Description:** No `USER` directive
- **Fix:** Add `useradd` and `USER appuser`

### Medium (P2)

#### PROD-007: Empty Lifespan Hook
- **File:** `app/main.py:13-17`
- **Description:** No startup verification or graceful shutdown
- **Fix:** Add DB verification and connection pool draining

#### PROD-008: No Metrics Endpoint
- **Description:** No Prometheus integration
- **Fix:** Add `prometheus-fastapi-instrumentator`

#### PROD-009: Docker Image No Health Check
- **File:** `Dockerfile`
- **Fix:** Add `HEALTHCHECK` instruction

#### PROD-010: No Circuit Breaker for External Services
- **Files:** `app/auth/oauth/google.py`, `app/cities/geoip.py`
- **Fix:** Implement `pybreaker` for external calls

#### PROD-011: Database Pool Not Configurable
- **File:** `app/database.py:8-13`
- **Fix:** Move to Settings with env override

#### PROD-012: No Graceful Shutdown
- **Description:** Requests may terminate mid-execution
- **Fix:** Configure uvicorn timeout; implement connection draining

#### PROD-013: Password Reset Token in Response
- **Description:** Same as SECURITY-003

#### PROD-014: Docker Compose Uses --reload
- **File:** `docker-compose.yml:38`
- **Fix:** Create separate prod compose file

#### PROD-015: No Input Size Limits
- **Description:** Vulnerable to large payload DoS
- **Fix:** Configure uvicorn limits; add middleware

#### PROD-016: Secrets in docker-compose.yml
- **File:** `docker-compose.yml:7-8,26-27`
- **Fix:** Use `.env` file or Docker secrets

---

## 7. Priority Matrix

### Immediate Action Required (P0 - Critical)

| ID | Issue | Domain | Effort |
|----|-------|--------|--------|
| SECURITY-001 | Google OAuth bypass | Security | Low |
| SECURITY-002 | JWT secret default | Security | Low |
| SECURITY-003 | Password reset token exposed | Security | Low |
| DATABASE-001 | N+1 in list_routes (140+ queries) | Performance | Medium |
| DATABASE-002 | N+1 in checkpoints | Performance | Low |
| DATABASE-003 | Sync DB blocking async | Performance | High |
| PROD-001 | Health check ignores DB | Production | Low |
| PROD-002 | JWT secret validation | Production | Low |
| API-001 | Token exposed in response | API | Low |

### High Priority (P1)

| ID | Issue | Domain | Effort |
|----|-------|--------|--------|
| SECURITY-004 | CORS wildcard | Security | Low |
| SECURITY-005 | Missing rate limiting | Security | Medium |
| SECURITY-006 | OAuth auto-merge | Security | Low |
| DATABASE-004 | Missing pool_recycle | Performance | Low |
| DATABASE-005 | No rollback handling | Performance | Medium |
| DATABASE-006-008 | Other N+1 patterns | Performance | Medium |
| API-002 | Dict error handling | API | Medium |
| API-003 | Path collision | API | Low |
| ARCH-001 | Service returns DTOs | Architecture | High |
| TEST-001-002 | OAuth/Token tests | Testing | Medium |
| PROD-003-006 | Logging, tracing, Docker | Production | Medium |

---

## 8. Remediation Roadmap

### Phase 1: Critical Security & Stability (Week 1)
- [ ] Fix Google OAuth validation bypass
- [ ] Remove JWT secret default
- [ ] Remove password reset token from response
- [ ] Add database connectivity to health check
- [ ] Configure explicit CORS origins
- [ ] Add pool_recycle to database config

### Phase 2: Performance Quick Wins (Week 2)
- [ ] Fix N+1 in `list_routes()` with batch queries
- [ ] Fix N+1 in `get_route_checkpoints()` with batch loading
- [ ] Add transaction rollback handling
- [ ] Apply eager loading where selectinload/joinedload imported

### Phase 3: Security Hardening (Week 3)
- [ ] Implement rate limiting on auth endpoints
- [ ] Fix OAuth auto-merge verification
- [ ] Add HMAC token hashing
- [ ] Add logout token ownership check

### Phase 4: Production Readiness (Week 4)
- [ ] Configure structured logging
- [ ] Add request correlation IDs
- [ ] Add Prometheus metrics endpoint
- [ ] Fix Docker security (non-root user, healthcheck)
- [ ] Implement circuit breakers

### Phase 5: Architecture & Testing (Ongoing)
- [ ] Add OAuth flow tests
- [ ] Add concurrent access tests
- [ ] Extract repository pattern
- [ ] Split large service classes
- [ ] Evaluate async SQLAlchemy migration

---

## Positive Observations

The codebase demonstrates several best practices:

1. **Argon2id Password Hashing** - Strong parameters (time=3, memory=64MB)
2. **Token Version for Session Invalidation** - Proper logout-all support
3. **Refresh Token Rotation** - Old tokens revoked on refresh
4. **SQLAlchemy ORM** - Parameterized queries prevent SQL injection
5. **JWT Type Claims** - Prevents access/refresh token confusion
6. **Secure Token Generation** - `secrets.token_urlsafe(32)`
7. **Clean Module Structure** - Consistent router/service/schema pattern
8. **HSTORE for i18n** - Efficient multilingual content storage
9. **PostGIS Integration** - Proper spatial queries with indexes
10. **Comprehensive Pydantic Schemas** - Strong input validation

---

*Report generated by Multi-Expert Code Review Panel*

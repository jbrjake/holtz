# Holtz Punchlist
> Generated: 2026-03-15 | Project: widget-api | Baseline: 47 pass, 2 fail, 3 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 1 | 0 |
| HIGH | 1 | 1 | 0 |
| MEDIUM | 1 | 1 | 1 |
| LOW | 0 | 0 | 0 |

## Patterns

## Pattern: PAT-001: Unvalidated external input
**Instances:** BH-001, BH-003
**Root Cause:** No input validation layer between API handlers and domain logic
**Systemic Fix:** Add a validation middleware that runs before handler dispatch
**Detection Rule:** `grep -rn 'request\.(body\|params\|query)' --include='*.ts' src/handlers/`

## Items

### BH-001: SQL injection in user search endpoint
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `src/handlers/users.ts:42`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** User search query parameter is interpolated directly into SQL string without parameterization. Any input containing SQL metacharacters executes arbitrary queries.

**Evidence:**
```typescript
// src/handlers/users.ts:42
const results = await db.query(`SELECT * FROM users WHERE name LIKE '%${req.query.q}%'`);
```

**Discovery Chain:** `users.ts:42` interpolates `req.query.q` directly into SQL string
→ no parameterization or escaping applied
→ attacker-controlled input executes arbitrary SQL

**Acceptance Criteria:**
- [x] Parameterized query used instead of string interpolation
- [x] Test proves injection attempt returns empty results, not SQL error

**Validation Command:**
```bash
npm test -- --grep "user search.*injection"
```

**Resolution:** Fixed in commit a1b2c3d. Test `user-search.test.ts:should reject SQL injection attempts` validates the fix.

### BH-002: Missing error handler for database connection timeout
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `src/db/pool.ts:18`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** Database pool creation has no timeout handler. If the database is unreachable at startup, the process hangs indefinitely instead of failing with an error.

**Evidence:** `pool.ts:18` calls `createPool(config)` without a `connectTimeout` option. The default timeout is `0` (infinite) per the driver docs.

**Discovery Chain:** `pool.ts:18` calls `createPool(config)` with no `connectTimeout`
→ driver docs confirm default timeout is 0 (infinite)
→ unreachable database causes process to hang indefinitely

**Acceptance Criteria:**
- [ ] Pool creation has a configurable timeout (default 5s)
- [ ] Timeout produces a clear error message with connection details
- [ ] Test verifies timeout behavior with unreachable host

**Validation Command:**
```bash
npm test -- --grep "pool.*timeout"
```

### BH-003: Unsanitized filename in file upload endpoint
**Severity:** HIGH
**Category:** bug/security
**Location:** `src/handlers/uploads.ts:31`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** Uploaded filename from multipart form data is used directly in the filesystem path. Path traversal attack can write files outside the upload directory.

**Evidence:**
```typescript
// src/handlers/uploads.ts:31
const dest = path.join(UPLOAD_DIR, file.originalname);
```

**Discovery Chain:** `uploads.ts:31` uses `file.originalname` directly in `path.join`
→ no sanitization of path separators or `..` components
→ attacker-supplied filename like `../../../etc/passwd` escapes upload directory

**Acceptance Criteria:**
- [x] Filename sanitized to remove path separators and relative components
- [x] Test proves `../../../etc/passwd` filename writes to upload dir, not traversal target

**Validation Command:**
```bash
npm test -- --grep "upload.*traversal"
```

**Resolution:** Fixed in commit d4e5f6a. Filename now passed through `path.basename()` and stripped of non-alphanumeric characters except dots and hyphens. Test `uploads.test.ts:should prevent path traversal` validates.

### BH-004: Stale cache served after user deletion
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `src/cache/user-cache.ts:55`
**Status:** DEFERRED
**Determinism:** intermittent

**Problem:** User cache is populated on read but not invalidated on delete. Deleted users continue to appear in search results until cache TTL expires (5 minutes).

**Evidence:** `user-cache.ts` has a `set()` call in `getUser()` (line 22) but `deleteUser()` (line 55) does not call `cache.del()`.

**Discovery Chain:** `getUser()` populates cache on read
→ `deleteUser()` does not call `cache.del()`
→ deleted users served from stale cache until TTL expires

**Acceptance Criteria:**
- [ ] `deleteUser()` invalidates the cache entry
- [ ] Test verifies deleted user is not returned from cached search

**Validation Command:**
```bash
npm test -- --grep "cache.*delete"
```

### BH-005: Test for rate limiter only checks happy path
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/rate-limiter.test.ts:12`
**Status:** OPEN

**Problem:** Rate limiter test sends 5 requests and asserts all succeed. Never sends enough requests to trigger the limit (100/min). The test would pass if the rate limiter were removed entirely.

**Evidence:** Test file has one test case: "should allow requests under the limit." No test for "should reject requests over the limit" or "should reset after window expires."

**Discovery Chain:** rate limiter test sends 5 requests against a 100/min limit
→ test never exceeds the threshold
→ removing the rate limiter entirely would not break this test

**Acceptance Criteria:**
- [ ] Test sends requests exceeding the rate limit and asserts 429 response
- [ ] Test verifies rate limit resets after the configured window
- [ ] Existing test still passes (happy path remains valid)

**Validation Command:**
```bash
npm test -- --grep "rate.limiter"
```

### BH-006: Race condition in session refresh under concurrent requests
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `src/auth/session.ts:78`
**Status:** RESOLVED
**Determinism:** theoretical
**Investigation:** `docs/holtz/investigations/BH-006.md`

**Problem:** When two requests arrive simultaneously with an expired session token, both trigger a refresh. The second refresh overwrites the first refresh's new token, invalidating the response already sent to the first request. The client retries with the now-invalid token and gets a 401.

**Evidence:** Code review of `session.ts:78` shows `refreshSession()` reads the current token, generates a new one, and writes it back without any locking or compare-and-swap. Under concurrent access, the read-modify-write is not atomic.

**Discovery Chain:** `refreshSession()` does read-modify-write on token field
→ no locking or compare-and-swap guards the sequence
→ concurrent requests cause second write to overwrite first
→ first request's response carries an already-invalidated token

**Acceptance Criteria:**
- [x] Session refresh uses atomic compare-and-swap or mutex
- [x] Test proves concurrent refresh requests both receive valid tokens
- [x] Test proves no 401 errors under concurrent refresh load

**Validation Command:**
```bash
npm test -- --grep "session.*concurrent"
```

**Resolution:** Fixed in commit f7a8b9c. Session refresh now uses atomic compare-and-swap on the token field — if the token changed between read and write, the refresh re-reads and retries. Test `session.test.ts:should handle concurrent refresh without 401` validates with 50 parallel refresh requests.
**Root Cause Confidence:** HIGH

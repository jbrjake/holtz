# Merge Protocol — Worked Examples

> These examples demonstrate each of the five classification types defined in
> [merge-protocol.md](merge-protocol.md). Consult these when a specific item
> pair is ambiguous under the matching criteria.
>
> For the classification rules, processing order, and output formats,
> see [merge-protocol.md](merge-protocol.md).

The examples below demonstrate each of the five classification types. All examples assume a Python web application codebase.

### Example 1: Agreement (same bug, same severity)

**Holtz finding:**
```markdown
### BH-011: Missing input validation in user registration
**Severity:** HIGH
**Category:** bug/security
**Location:** `app/routes/auth.py:47`
**Problem:** The `register_user` endpoint accepts email input without validation,
allowing malformed or malicious email strings to reach the database layer.
```

**Justine finding:**
```markdown
### BJ-004: No email validation on registration endpoint
**Severity:** HIGH
**Category:** bug/security
**Location:** `app/routes/auth.py:49`
**Problem:** The registration handler does not validate the email field before
passing it to `create_user()`. Invalid emails are stored without error.
```

**Classification decision:** Same file (`app/routes/auth.py`), same category (`bug/security`), line numbers within 5 of each other (47 and 49, difference = 2). **Agreement.**

**Merged output:**
```markdown
### BH-003: Missing input validation in user registration
**Severity:** HIGH
**Category:** bug/security
**Location:** `app/routes/auth.py:47`
**Found by:** both auditors
<!-- Was: Holtz BH-011 + Justine BJ-004 -->

**Problem:** The `register_user` endpoint accepts email input without validation,
allowing malformed or malicious email strings to reach the database layer.
```

### Example 2: Holtz-only

**Holtz finding:**
```markdown
### BH-015: Race condition in session token refresh
**Severity:** CRITICAL
**Category:** bug/state
**Location:** `app/auth/tokens.py:112`
**Problem:** Concurrent requests can trigger simultaneous token refreshes. The second
refresh invalidates the first's new token, causing an authenticated user to be logged
out. Requires multi-step data flow analysis to detect — only observable under concurrent
request load.
```

**Justine finding:** (none — no Justine item references `app/auth/tokens.py` with category `bug/state`)

**Classification decision:** No matching Justine item for this file + category combination. **Holtz-only.**

**Merged output:**
```markdown
### BH-007: Race condition in session token refresh
**Severity:** CRITICAL
**Category:** bug/state
**Location:** `app/auth/tokens.py:112`
**Found by:** Holtz only
<!-- Was: Holtz BH-015 -->

**Problem:** Concurrent requests can trigger simultaneous token refreshes. The second
refresh invalidates the first's new token, causing an authenticated user to be logged
out.
```

### Example 3: Justine-only

**Holtz finding:** (none — no Holtz item references `README.md` with category `doc/drift`)

**Justine finding:**
```markdown
### BJ-019: README install instructions reference removed dependency
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:34`
**Problem:** The install instructions include `pip install redis` but redis was removed
as a dependency in requirements.txt three months ago. The caching layer was replaced
with an in-memory LRU cache.
```

**Classification decision:** No matching Holtz item. **Justine-only.**

**Merged output:**
```markdown
### BH-012: README install instructions reference removed dependency
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:34`
**Found by:** Justine only
<!-- Was: Justine BJ-019 -->

**Problem:** The install instructions include `pip install redis` but redis was removed
as a dependency in requirements.txt three months ago. The caching layer was replaced
with an in-memory LRU cache.
```

### Example 4: Severity Disagreement

**Holtz finding:**
```markdown
### BH-022: Unchecked return value from database write
**Severity:** CRITICAL
**Category:** bug/error-handling
**Location:** `app/models/order.py:88` (function `save_order`)
**Problem:** The `save_order` function calls `db.execute(insert_query)` without checking
the return value. If the insert fails silently (connection timeout, constraint violation),
the order is reported as saved but is not persisted.
```

**Justine finding:**
```markdown
### BJ-008: save_order ignores db.execute result
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `app/models/order.py:91` (function `save_order`)
**Problem:** `save_order` does not check whether `db.execute` succeeded. A failed write
would go unnoticed.
```

**Classification decision:** Same file (`app/models/order.py`), same category (`bug/error-handling`), same function name (`save_order`), line numbers within 5 (88 and 91, difference = 3). Same bug. Severities differ: Holtz says CRITICAL, Justine says HIGH. **Severity disagreement.** Use CRITICAL (the higher severity).

**Merged output:**
```markdown
### BH-005: Unchecked return value from database write
**Severity:** CRITICAL
**Category:** bug/error-handling
**Location:** `app/models/order.py:88` (function `save_order`)
**Found by:** both auditors
**Severity disagreement:** Holtz=CRITICAL, Justine=HIGH
<!-- Was: Holtz BH-022 + Justine BJ-008 -->

**Problem:** The `save_order` function calls `db.execute(insert_query)` without checking
the return value. If the insert fails silently (connection timeout, constraint violation),
the order is reported as saved but is not persisted.
```

### Example 5: Contradictory

**Holtz finding:**
```markdown
### BH-009: Default timeout of 0 disables request timeouts
**Severity:** HIGH
**Category:** bug/logic
**Location:** `app/client/http.py:23`
**Problem:** The HTTP client sets `timeout=0` as the default. In the `requests` library,
timeout=0 means "no timeout," allowing requests to hang indefinitely. Should be a
positive value like 30.
```

**Justine finding:**
```markdown
(In BJ-015 Evidence section):
"Verified: `app/client/http.py:23` sets `timeout=0`. Confirmed this is intentional —
the project uses `httpx`, not `requests`. In httpx, `timeout=0` means 'use the default
timeout' (5 seconds), not 'no timeout'. This is correct behavior."
```

**Classification decision:** Holtz says `timeout=0` is a bug. Justine explicitly verified `timeout=0` as correct. **Contradictory.** Do not auto-resolve — flag for human review.

**Merged output:**
```markdown
### BH-009: Default timeout of 0 disables request timeouts [CONTRADICTORY]
**Severity:** HIGH
**Category:** bug/logic
**Location:** `app/client/http.py:23`
**Status:** DEFERRED
**Found by:** Holtz only (Justine contradicts)
**Contradictory:** Holtz says timeout=0 disables timeouts (requests library behavior).
Justine says timeout=0 is correct (httpx library behavior, uses default 5s timeout).
<!-- Was: Holtz BH-009 — contradicted by Justine BJ-015 evidence -->

**Problem:** The HTTP client sets `timeout=0` as the default. Holtz interprets this as
"no timeout" (requests library semantics). Justine interprets this as "use default
timeout" (httpx library semantics). Human review required to determine which library
is actually in use.
```

### Example 6: Near-Miss Location Match

This example demonstrates the 5-line proximity threshold.

**Scenario A — Match (4 lines apart):**

**Holtz finding:**
```markdown
### BH-031: Unsafe string concatenation in SQL query
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:47`
```

**Justine finding:**
```markdown
### BJ-022: SQL injection in query builder
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:51`
```

Lines 47 and 51 — difference is 4. **Within 5 lines.** Same file, same category. **This is a match → Agreement.**

---

**Scenario B — No match (6 lines apart):**

**Holtz finding:**
```markdown
### BH-031: Unsafe string concatenation in SQL query
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:47`
```

**Justine finding:**
```markdown
### BJ-023: Unescaped user input in delete query
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:53`
```

Lines 47 and 53 — difference is 6. **Outside 5 lines.** Even though same file and same category, these are classified independently. Holtz's item is **Holtz-only**, Justine's item is **Justine-only** (they are likely two separate SQL injection instances in different queries).

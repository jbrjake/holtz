"""Integration tests: validate_punchlist + convergence_check parse the same format."""

import tempfile
from pathlib import Path

import convergence_check as cc
import validate_punchlist as vp

# A realistic multi-status punchlist that both parsers must agree on.
SHARED_PUNCHLIST = """\
# Bug Hunter Punchlist
> Generated: 2026-03-21 | Project: test | Baseline: 50 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 1 | 1 | 0 |
| MEDIUM | 0 | 1 | 1 |

## Patterns

## Items

### BH-001: Auth bypass via token reuse
**Severity:** HIGH
**Category:** bug/security
**Location:** `auth.py:42`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** Expired tokens are accepted because expiry check uses wrong clock source.

**Evidence:** `auth.py:42` calls `time.time()` but tokens use `datetime.utcnow()`.

**Discovery Chain:** observed expired token accepted → traced to clock mismatch

**Acceptance Criteria:**
- [ ] Token expiry uses consistent clock source
- [ ] Test with expired token fails auth

**Validation Command:**
```bash
pytest -k token_expiry
```

### BH-002: SQL injection in search
**Severity:** HIGH
**Category:** bug/security
**Location:** `search.py:15`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** User input interpolated directly into SQL query string.

**Evidence:** `search.py:15`: `f"SELECT * FROM users WHERE name = '{user_input}'"`.

**Discovery Chain:** code review → found string interpolation → confirmed injectable

**Acceptance Criteria:**
- [x] Parameterized queries used
- [x] Injection test passes

**Validation Command:**
```bash
pytest -k sql_injection
```

**Resolution:** Fixed in commit abc123. Parameterized query, validated by injection test.

### BH-003: Stale cache after delete
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `cache.py:55`
**Status:** DEFERRED
**Determinism:** intermittent

**Problem:** Cache not invalidated on delete. Deleted users appear for up to 5 minutes.

**Evidence:** `cache.py:55` has `set()` in `getUser()` but `deleteUser()` does not call `cache.del()`.

**Discovery Chain:** user report → reproduced in staging → traced to missing invalidation

**Acceptance Criteria:**
- [ ] deleteUser() invalidates cache entry

**Validation Command:**
```bash
pytest -k cache_delete
```

### BH-004: README claims feature X exists
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:15`
**Status:** RESOLVED

**Problem:** README claims feature X exists but it was removed in v2.

**Evidence:** grep for feature X in codebase returns no results.

**Discovery Chain:** doc review → feature claim → grep confirms removal

**Acceptance Criteria:**
- [x] README updated

**Validation Command:**
```bash
grep -r "feature X" README.md
```

**Resolution:** README updated to remove feature X reference in commit def456.
"""


def test_item_count_agreement():
    """Both parsers should find the same number of items."""
    vp_items = vp.parse_punchlist(SHARED_PUNCHLIST)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(SHARED_PUNCHLIST)
        f.flush()
        cc_counts = cc.count_items(Path(f.name))
    assert len(vp_items) == cc_counts["total"]


def test_status_distribution_agreement():
    """Both parsers should agree on status counts."""
    vp_items = vp.parse_punchlist(SHARED_PUNCHLIST)
    vp_counts = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0}
    for item in vp_items:
        if item.status in vp_counts:
            vp_counts[item.status] += 1
        else:
            vp_counts["unknown"] += 1

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(SHARED_PUNCHLIST)
        f.flush()
        cc_counts = cc.count_items(Path(f.name))

    for status in ("OPEN", "IN PROGRESS", "RESOLVED", "DEFERRED", "unknown"):
        assert vp_counts[status] == cc_counts[status], (
            f"Status '{status}': validate_punchlist says {vp_counts[status]}, "
            f"convergence_check says {cc_counts[status]}"
        )


def test_code_fence_immunity_agreement():
    """Both parsers should ignore items inside code fences."""
    content = """\
# Bug Hunter Punchlist
## Summary
## Items

### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Example punchlist:
```markdown
### BH-002: Phantom item
**Status:** RESOLVED
```

**Discovery Chain:** found X → leads to Y

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    vp_items = vp.parse_punchlist(content)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        f.flush()
        cc_counts = cc.count_items(Path(f.name))

    assert len(vp_items) == 1, f"validate_punchlist found {len(vp_items)} items, expected 1"
    assert cc_counts["total"] == 1, f"convergence_check found {cc_counts['total']} items, expected 1"
    assert vp_items[0].status == "OPEN"
    assert cc_counts["OPEN"] == 1


def test_trailing_status_text_agreement():
    """Both parsers should handle trailing text after status the same way."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN but see notes

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Evidence content here with enough detail to pass threshold.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    vp_items = vp.parse_punchlist(content)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        f.flush()
        cc_counts = cc.count_items(Path(f.name))

    assert vp_items[0].status == "OPEN"
    assert cc_counts["OPEN"] == 1
    assert cc_counts["unknown"] == 0

# Holtz Punchlist — Merged (Run 28)
> Generated: 2026-03-29 | Adversarial Self-Play merge | Holtz: 3 items, Justine: 3 items

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 2    | 0        | 0        |
| MEDIUM   | 2    | 0        | 0        |
| LOW      | 0    | 0        | 0        |

## Patterns

(none)

## Items

### BH-001: README badges stale
<!-- Was: Holtz BH-001 + Justine BJ-001 -->
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:7`
**Status:** OPEN
**Found by:** both auditors
**Severity disagreement:** Holtz=LOW, Justine=HIGH. Using HIGH.

**Problem:** Badge claims "76% coverage" but actual measured coverage is 79.94% (rounds to 80%). Badge also claims "857 tests passed" but actual is 856 passed + 1 skipped.

**Evidence:** README line 7: `![76% coverage](https://img.shields.io/badge/coverage-76%25-brightgreen.svg)`. Actual: `python -m pytest --cov=... --cov-fail-under=60` reports "Total coverage: 79.94%". README line 6: `![857 tests](https://img.shields.io/badge/tests-857_passed-brightgreen.svg)`. Actual: `python -m pytest -v --tb=no 2>&1 | tail -1` outputs "856 passed, 1 skipped in 12.71s".

**Discovery Chain:** Holtz (P1): badge text vs toolchain output comparison. Justine: badge text → pytest output → 76% != 80% → stale badge.

**Acceptance Criteria:**
- [ ] Coverage badge in README.md reports actual coverage percentage (80% or current measured value)
- [ ] Test badge reflects accurate passing count (856) or uses total count phrasing (857 total)

**Validation Command:**
```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60 --tb=no -q 2>&1 | grep "Total coverage"
python -m pytest -v --tb=no 2>&1 | tail -1
```

---

### BH-002: README line count and test count stale
<!-- Was: Holtz BH-002 + Justine BJ-002 -->
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:190,214`
**Status:** OPEN
**Found by:** both auditors
**Severity disagreement:** Holtz=LOW, Justine=HIGH. Using HIGH.

**Problem:** Two instances of stale line count: claims 19,446 lines but actual is 19,735 (delta +289). The same locations also claim "857 tests" which overstates passing tests by 1 (856 pass, 1 skipped).

**Evidence:** README lines 190 and 214: "857 tests across 19,446 lines of code". Actual: `wc -l` across codebase yields 19,735; `python -m pytest -v --tb=no 2>&1 | tail -1` yields "856 passed, 1 skipped". Justine additionally observed: README line 6 badge says "857_passed" (same stale count, confirms the drift is systemic across multiple README locations).

**Discovery Chain:** Holtz (P5): line count comparison via wc -l. Justine: badge count → pytest output → same stale count propagated to lines 190 and 214.

**Acceptance Criteria:**
- [ ] Lines 190 and 214 reflect accurate line count (19,735 or current wc -l value)
- [ ] Lines 190 and 214 reflect accurate test count (856 passed or 857 total with accurate phrasing)

**Validation Command:**
```bash
python -m pytest -v --tb=no 2>&1 | tail -1
```

---

### BH-003: SKILL.md CLI examples incomplete
<!-- Was: Holtz BH-003 -->
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `skills/holtz/SKILL.md:87,119,128`
**Status:** OPEN
**Found by:** Holtz only

**Problem:** CLI examples omit required Sahjhan event fields (project, run, auditor, phase, step). Commands following these examples will fail.

**Evidence:** Three locations in SKILL.md show CLI invocations that are missing mandatory event fields required by the Sahjhan event schema. Any user copying these examples verbatim will get a schema validation error.

**Discovery Chain:** Holtz: read SKILL.md examples → compared against events.toml field requirements → examples missing 5 required fields.

**Acceptance Criteria:**
- [ ] All CLI examples in SKILL.md include project, run, auditor, phase, and step fields
- [ ] Examples are copy-paste runnable without schema errors

**Validation Command:**
```bash
grep -n "sahjhan" skills/holtz/SKILL.md | head -20
```

---

### BH-004: test_lists_sessions is a Rubber Stamp
<!-- Was: Justine BJ-003 -->
**Severity:** MEDIUM
**Category:** test/bogus
**Location:** `tests/test_token_profiler_cli.py:270-282`
**Status:** OPEN
**Found by:** Justine only

**Problem:** test_lists_sessions checks that list_sessions returns entries with the expected keys ("path", "name", "size_kb", "turns", "started", "ended") but never verifies the values of those keys. A broken implementation returning `{"path": None, "name": 0, "size_kb": "garbage"}` would pass. This is anti-pattern #11 (Rubber Stamp) — asserts structure not correctness.

**Evidence:** Lines 276-282:
```python
for entry in result:
    assert "path" in entry
    assert "name" in entry
    assert "size_kb" in entry
    assert "turns" in entry
    assert "started" in entry
    assert "ended" in entry
```
No assertion on any value. Would pass with any dict containing these keys regardless of content.

**Discovery Chain:** Justine: grep for `"key" in` assertions in test files → found 6 consecutive key-only checks with no value verification → anti-pattern #11 Rubber Stamp.

**Acceptance Criteria:**
- [ ] Test verifies at least: path is a string containing the session filename, name matches the session file stem, size_kb is a positive number, turns is a non-negative integer
- [ ] Test would fail if list_sessions returned None values for all fields

**Validation Command:**
```bash
python -m pytest tests/test_token_profiler_cli.py::TestListSessions::test_lists_sessions -v 2>&1 | tail -5
```

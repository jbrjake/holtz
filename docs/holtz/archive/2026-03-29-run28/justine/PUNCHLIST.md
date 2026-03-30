# Holtz Punchlist
> Generated: 2026-03-29 | Project: holtz | Baseline: 856 pass, 0 fail, 1 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 2    | 0        | 0        |
| MEDIUM   | 2    | 0        | 0        |
| LOW      | 1    | 0        | 0        |

## Patterns

(none yet)

## Items

### BJ-001: README coverage badge stale (76% vs 80%)
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:7`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction P1 (confidence: HIGH)

**Problem:** The README coverage badge claims "76% coverage" but the actual measured coverage is 79.94% (rounds to 80%). The badge has drifted by 4 percentage points and understates the project's test coverage.

**Evidence:** README line 7: `![76% coverage](https://img.shields.io/badge/coverage-76%25-brightgreen.svg)`. Actual: `python -m pytest --cov=... --cov-fail-under=60` reports "Total coverage: 79.94%".

**Discovery Chain:** Read README badge text -> compared to toolchain coverage output -> 76% != 80% -> stale badge

**Acceptance Criteria:**
- [ ] Coverage badge in README.md reports actual coverage percentage (80% or current measured value)
- [ ] Running coverage and checking the badge value match

**Validation Command:**
```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60 --tb=no -q 2>&1 | grep "Total coverage"
```

### BJ-002: README test badge says "857 passed" but only 856 passed
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:6`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction P2 (confidence: HIGH)

**Problem:** The README badge text is `tests-857_passed-brightgreen` which claims 857 tests passed. The actual test run shows 856 passed and 1 skipped. Total is 857 but the badge specifically says "passed" -- only 856 pass. The badge overstates passing tests by 1. This same "857 tests" claim appears in two other locations: README line 190 ("857 tests across 19,446 lines of code") and line 214 ("857 tests across 19,446 lines of code").

**Evidence:** README line 6: `![857 tests](https://img.shields.io/badge/tests-857_passed-brightgreen.svg)`. Actual: `python -m pytest -v --tb=no 2>&1 | tail -1` outputs "856 passed, 1 skipped in 12.71s". Lines 190 and 214 also say "857 tests" which is the total count but misleading when combined with a "passed" badge.

**Discovery Chain:** Badge says "857_passed" -> test suite reports "856 passed, 1 skipped" -> badge is wrong by 1 -> same stale count in 3 README locations

**Acceptance Criteria:**
- [ ] README badge accurately reflects the number of passing tests (856) or total tests (857 total, not 857 passed)
- [ ] Lines 190 and 214 reflect accurate counts
- [ ] Running pytest confirms badge matches

**Validation Command:**
```bash
python -m pytest -v --tb=no 2>&1 | tail -1
```

### BJ-003: test_lists_sessions is a Rubber Stamp -- checks keys not values
**Severity:** MEDIUM
**Category:** test/bogus
**Location:** `tests/test_token_profiler_cli.py:270-282`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction P9 (confidence: HIGH)

**Problem:** test_lists_sessions checks that list_sessions returns entries with the expected keys ("path", "name", "size_kb", "turns", "started", "ended") but never verifies the VALUES of those keys. A broken implementation returning `{"path": None, "name": 0, "size_kb": "garbage"}` would pass. This is anti-pattern #11 (Rubber Stamp) -- asserts structure not correctness.

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

**Discovery Chain:** Grep for `"key" in` assertions in test files -> found 6 consecutive key-only checks with no value verification -> anti-pattern #11 Rubber Stamp -> the test that killed Mira checked format not value

**Acceptance Criteria:**
- [ ] Test verifies at least: path is a string containing the session filename, name matches the session file stem, size_kb is a positive number, turns is a non-negative integer
- [ ] Test would fail if list_sessions returned None values for all fields

**Validation Command:**
```bash
python -m pytest tests/test_token_profiler_cli.py::TestListSessions::test_lists_sessions -v 2>&1 | tail -5
```

### BJ-004: commit_gate _is_test_cmd narrower than protocol_tracker _is_tdd_cmd
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `enforcement/hooks/commit_gate.py:29-35` vs `enforcement/hooks/protocol_tracker.py:29-38`
**Status:** OPEN
**Lens:** integration

**Problem:** commit_gate defines `_is_test_cmd` recognizing only `pytest` and `python -m pytest`. protocol_tracker defines `_is_tdd_cmd` recognizing `pytest`, `python -m pytest`, `ruff check`, `ruff format`, and `mypy`. When stall threshold (>15 commands) is exceeded, commit_gate hard-blocks ALL non-sahjhan Bash commands (line 81) -- the test exemption at line 84 only covers pytest, not ruff/mypy. So ruff and mypy are recognized as TDD activity for stall-tracking purposes but blocked when stall threshold fires. A model in the fix loop running `ruff check .` after 16 non-protocol commands gets blocked with a stall error, even though ruff is legitimate TDD work.

**Evidence:** commit_gate.py lines 29-35:
```python
def _is_test_cmd(cmd: str) -> bool:
    cmd_stripped = cmd.strip()
    return (
        cmd_stripped.startswith("pytest")
        or cmd_stripped.startswith("python -m pytest")
    )
```
protocol_tracker.py lines 29-38:
```python
def _is_tdd_cmd(cmd: str) -> bool:
    cmd_stripped = cmd.strip()
    return (
        cmd_stripped.startswith("pytest")
        or cmd_stripped.startswith("python -m pytest")
        or cmd_stripped.startswith("ruff check")
        or cmd_stripped.startswith("ruff format")
        or cmd_stripped.startswith("mypy")
    )
```

**Discovery Chain:** Compared commit_gate._is_test_cmd to protocol_tracker._is_tdd_cmd -> found scope mismatch -> ruff/mypy not exempt from stall block in commit_gate -> integration inconsistency at boundary between PreToolUse and PostToolUse hooks

**Acceptance Criteria:**
- [ ] commit_gate._is_test_cmd recognizes the same set of TDD commands as protocol_tracker._is_tdd_cmd (pytest, ruff, mypy)
- [ ] When stall threshold is exceeded, ruff and mypy commands are still allowed through

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from commit_gate import _is_test_cmd
from protocol_tracker import _is_tdd_cmd
cmds = ['ruff check .', 'ruff format .', 'mypy hooks/']
for cmd in cmds:
    print(f'{cmd}: gate={_is_test_cmd(cmd)}, tracker={_is_tdd_cmd(cmd)}')
"
```

### BJ-005: _sahjhan_bootstrap _check_bash_write misses subshell write vectors
**Severity:** LOW
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:129-229`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** security

**Problem:** The `_check_bash_write` function checks specific write patterns (redirect, tee, cp/mv, sed/perl, python/dd/wget) but does not catch write operations nested in subshells: `bash -c 'python3 -c "os.remove(\"enforcement/hooks/test.py\")"'` bypasses all checks because the segment starts with `bash` not `python`. Also misses `truncate`, `rsync`, and `curl -o` as write vectors. This is defense-in-depth only -- bash_guard PostToolUse catches manifest violations after the fact -- but the PreToolUse guard has a gap.

**Evidence:** `_check_bash_write` line 209 checks `seg_stripped.startswith(interp)` for python/ruby/node but `bash -c 'python3 ...'` starts with `bash`, not `python3`. The regex split `r'\s*(?:&&|\|\||[;|])\s*'` does not split on command substitution or subshell boundaries.

**Discovery Chain:** Read _check_bash_write pattern list -> tested subshell wrapping -> confirmed bypass -> verified bash_guard provides second layer -> downgraded from MEDIUM to LOW

**Acceptance Criteria:**
- [ ] bash_guard PostToolUse continues to verify manifest after all Bash commands (current behavior, unchanged)
- [ ] Optionally: _check_bash_write also checks `bash -c`, `sh -c`, and `eval` segments for nested protected path references

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from _sahjhan_bootstrap import _check_bash_write
result = _check_bash_write('bash -c \"echo test > enforcement/hooks/test.py\"')
print('Blocked:' if result else 'Bypassed (expected gap)')
"
```

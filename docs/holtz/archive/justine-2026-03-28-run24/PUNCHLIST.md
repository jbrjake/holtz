# Holtz Punchlist
> Generated: 2026-03-28 | Project: holtz | Baseline: 759 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 2 | 0 | 0 |
| MEDIUM | 4 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

## Items

### BJ-001: generate_quiz_bank.py open() missing encoding -- PAT-006
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `enforcement/scripts/generate_quiz_bank.py:43`
**Status:** OPEN
**Pattern:** PAT-006
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** `open(args.input)` on line 43 omits `encoding='utf-8'`. On non-UTF-8 default locales (Windows, some Linux configurations), this causes `UnicodeDecodeError` or silently reads corrupted data when quiz-bank.json contains non-ASCII characters. This is the same systemic pattern (PAT-006) that was found in 5 enforcement hook files during Run 23 -- but enforcement/scripts/ was missed in that sweep.

**Evidence:**
```python
# enforcement/scripts/generate_quiz_bank.py:43
with open(args.input) as f:
    bank = json.load(f)
```
All other open() calls in enforcement/ and scripts/ now have `encoding='utf-8'`.

**Discovery Chain:** PAT-006 detection heuristic (grep for open() without encoding) -> found generate_quiz_bank.py:43 -> confirmed same pattern as Run 23 findings BH-005/BH-006/BH-008/BH-009/BH-021

**Acceptance Criteria:**
- [ ] `open(args.input, encoding="utf-8")` on line 43
- [ ] No open() calls in enforcement/ without explicit encoding

**Validation Command:**
```bash
grep -rn 'open(' enforcement/ | grep -v encoding | grep -v 'os.fdopen' | grep -v '#'
```

### BJ-002: README numeric claims stale (9th consecutive PAT-005 run)
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:6,160,190,192,198,214`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** Multiple hardcoded counts in README.md diverge from actual values. This is the 9th consecutive run where PAT-005 has fired. Specific discrepancies:

| Location | Claim | Actual |
|----------|-------|--------|
| Line 6 (badge) | 757 tests / 755 passed | 759 tests |
| Line 104 | "11 runs with prediction tracking, HIGH at 65%, MEDIUM at 38%, LOW at 0%" | 7 tracked runs, HIGH 82%, MEDIUM 59%, LOW 67% |
| Line 160 | "Twenty-three runs and counting" | 24+ |
| Line 190 | "23 runs: 757 tests across 17,339 lines of code" | 24+ runs, 759 tests, 21,069 LOC |
| Line 192 | "across all 16 runs" | 24+ runs |
| Line 198 | "Ten hooks backed by the Sahjhan enforcement engine" | 13 enforcement hook files (15 total hook files) |
| Line 214 | "6 Python scripts" | 17 script files |
| Line 214 | "10 enforcement hooks" | 13 enforcement hook files |
| Line 214 | "759 tests across 17,410 lines of code" | 759 tests, 21,069 LOC |

**Evidence:** `wc -l` on all source + test files = 21,069. `ls enforcement/hooks/*.py | wc -l` = 13. `ls skills/holtz/scripts/*.py scripts/token_profiler/*.py enforcement/scripts/*.py | wc -l` = 17. `python -m pytest` = 759 passed.

**Discovery Chain:** PAT-005 detection heuristic -> compared README counts against filesystem -> 9+ discrepancies confirmed

**Acceptance Criteria:**
- [ ] Badge reflects 759 tests
- [ ] Line 104 prediction accuracy matches LIVING-PUNCHLIST.md cumulative data
- [ ] Line 160 run count accurate
- [ ] Line 190 run count, test count, and LOC accurate
- [ ] Line 192 run count accurate
- [ ] Line 198 hook count matches actual enforcement hook files
- [ ] Line 214 script count, hook count, and LOC accurate

**Validation Command:**
```bash
python -m pytest -q 2>&1 | tail -1 && echo "---" && find . -name '*.py' -path '*/tests/*' -o -name '*.py' -path '*/hooks/*' -o -name '*.py' -path '*/scripts/*' -o -name '*.py' -path '*/skills/*' | xargs wc -l | tail -1
```

### BJ-003: CI broken on remote dev -- 23 ruff errors
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `CI (GitHub Actions)`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Predicted:** Prediction 3 (confidence: HIGH)

**Problem:** All 3 most recent CI runs on the dev branch are failing at the lint step. 23 ruff errors in 6 files present on remote dev but not in the local working tree. Local ruff passes because it does not see these files. This means CI is silently broken -- local development sees green while the branch is red.

**Evidence:** Holtz recon step1 documents: `Found 23 errors. [*] 18 fixable with the --fix option`. Failing files include `enforcement/hooks/primer.py`, `scripts/migrate_legacy.py`, `tests/test_enforcement_config.py`, `tests/test_jsonl_integration.py`, `tests/test_migrate_legacy.py`, `tests/test_protocol_enforcement.py`.

**Discovery Chain:** Holtz step1 CI check -> all 3 runs failing -> files not present locally -> local/remote divergence confirmed

**Acceptance Criteria:**
- [ ] Local dev branch pulled to match remote
- [ ] `ruff check .` passes on all files present on remote dev
- [ ] CI turns green

**Validation Command:**
```bash
gh run list --branch dev --limit 1 --json conclusion --jq '.[0].conclusion'
```

### BJ-004: commit_gate _is_test_cmd overly permissive
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/commit_gate.py:29-30`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** `_is_test_cmd` checks if `"pytest" in cmd`, which matches any command containing the string "pytest" anywhere -- including `echo "pytest"`, `grep pytest`, `rm pytest`, or `cat pytest_output.log`. This allows any command to bypass the commit gate by including the string "pytest" in it. The function should check that pytest is the executable being invoked, not just a substring of the command.

**Evidence:**
```python
# enforcement/hooks/commit_gate.py:28-30
def _is_test_cmd(cmd: str) -> bool:
    """Detect test/pytest commands that should always be allowed."""
    return "pytest" in cmd or cmd.strip().startswith("python -m pytest")
```

The `"pytest" in cmd` check is a substring match. A command like `echo "delete everything" # pytest` would pass this check and bypass the commit gate even when stall threshold is not exceeded (but NOT when `blocks_all` is true -- stall override is checked first).

Note: The security impact is limited because (1) stall-blocks-all still overrides this, and (2) this hook runs in a developer tool context, not a production service. However, the enforcement bypass is still a defect in the protocol enforcement logic.

**Discovery Chain:** Code review of commit_gate.py -> _is_test_cmd uses substring match -> any command containing "pytest" bypasses gate -> enforcement bypass possible

**Acceptance Criteria:**
- [ ] `_is_test_cmd` checks that pytest is the executable (e.g., command starts with "pytest" or "python -m pytest", not just contains it)
- [ ] Test: `_is_test_cmd('echo "delete everything" # pytest')` returns False

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from commit_gate import _is_test_cmd
assert not _is_test_cmd('echo pytest'), 'substring bypass not fixed'
assert _is_test_cmd('python -m pytest --tb=short')
assert _is_test_cmd('pytest tests/')
print('PASS')
"
```

### BJ-005: protocol_tracker _is_tdd_cmd same substring match issue
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/protocol_tracker.py:28-34`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** Same pattern as BJ-004. `_is_tdd_cmd` checks `any(keyword in cmd_stripped for keyword in ("pytest", ...))`. A command like `cat pytest_output.log` would be classified as TDD activity and not increment the stall counter, allowing protocol enforcement evasion.

**Evidence:**
```python
# enforcement/hooks/protocol_tracker.py:28-34
def _is_tdd_cmd(cmd: str) -> bool:
    """Detect test, lint, and type-check commands (TDD workflow)."""
    cmd_stripped = cmd.strip()
    return any(keyword in cmd_stripped for keyword in (
        "pytest", "python -m pytest",
        "ruff check", "ruff format",
        "mypy",
    ))
```

**Discovery Chain:** Found BJ-004 substring issue in commit_gate -> searched for sibling patterns -> found identical pattern in protocol_tracker._is_tdd_cmd

**Acceptance Criteria:**
- [ ] `_is_tdd_cmd` checks that the keyword is the executable, not just a substring
- [ ] Test: `_is_tdd_cmd('cat pytest_output.log')` returns False
- [ ] Test: `_is_tdd_cmd('echo "ruff check"')` returns False

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from protocol_tracker import _is_tdd_cmd
assert not _is_tdd_cmd('cat pytest_output.log'), 'substring bypass not fixed'
assert _is_tdd_cmd('python -m pytest --tb=short')
print('PASS')
"
```

### BJ-006: Test anti-pattern -- source code string matching instead of behavioral testing
**Severity:** MEDIUM
**Category:** test/bogus
**Location:** `tests/test_sahjhan_integration.py:296-326,348-358,382-406`
**Status:** OPEN
**Lens:** test-quality

**Problem:** Multiple test methods read source code as a string and assert that specific strings (like `"OSError"`, `"--field"`, `"project=holtz"`) are present. This is Inspector Clouseau (anti-pattern #4) combined with Rubber Stamp (#11). These tests verify implementation details (string presence in source) rather than behavior (that exceptions are actually caught, that fields are actually sent). A refactoring that changes variable names, reorders code, or uses synonyms would break these tests even if behavior is correct. Conversely, the tests would pass even if the exception handling were broken, as long as the string "OSError" appeared somewhere in the file.

Examples:
- `test_violation_cmd_uses_field_syntax` reads bash_guard.py source and asserts `'"--field"' in source` (line 309)
- `test_exception_catches_oserror` reads source and asserts `"OSError" in source` (lines 319, 353, 400)
- `test_reset_cmd_uses_field_syntax` reads primer.py source and asserts string presence (lines 387-393)

**Evidence:** 4 test methods across TestBashGuard, TestStopGate, and TestPrimer classes use `open(source_path) as f: source = f.read()` followed by `assert "string" in source` patterns. None of these tests verify that the exception handling actually works by triggering an OSError.

**Discovery Chain:** Test file scan for anti-patterns #11 (rubber stamp) and #4 (inspector clouseau) -> found source-string-matching pattern in 4 test methods -> tests check implementation detail (string presence) not behavior (exception caught)

**Acceptance Criteria:**
- [ ] Tests verify behavior (exception handling works) rather than source code contents
- [ ] At minimum: tests that trigger the exception path and verify the hook degrades gracefully

**Validation Command:**
```bash
python -m pytest tests/test_sahjhan_integration.py -v -k "exception_catches or field_syntax" 2>&1 | tail -10
```

### BJ-007: _sahjhan_bootstrap Bash redirect check is substring-based
**Severity:** LOW
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:42-48`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** The Bash redirect detection in `_sahjhan_bootstrap.py` checks `p in command` for protected paths combined with redirect operators. This is a substring match that could be evaded (e.g., `echo enforcement/ > /tmp/test.txt` would trigger a false positive, while `echo "test" > enforcement/new_file.py` might not be caught if the path is constructed differently). The check also does not handle pipe redirections, heredocs, or command substitution.

However, the impact is LOW because:
1. The Write/Edit path check (the primary protection) is robust -- it resolves real paths.
2. The Bash redirect check is defense-in-depth for an unlikely attack vector.
3. In practice, the LLM generates straightforward commands, not adversarial evasions.

**Evidence:**
```python
# enforcement/hooks/_sahjhan_bootstrap.py:42-48
if command and not path:
    for p in PROTECTED:
        if p in command and any(op in command for op in (">", ">>", "tee ")):
            _block(...)
```

**Discovery Chain:** Code review of bootstrap hook -> Bash redirect check uses substring matching -> identified as defense-in-depth limitation -> severity LOW because primary protection (path resolution) is sound

**Acceptance Criteria:**
- [ ] Acknowledged as known limitation or improved to parse shell redirections more precisely

**Validation Command:**
```bash
echo "Defense-in-depth check. Primary path protection verified by existing tests."
```

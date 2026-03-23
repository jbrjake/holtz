# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 259 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 1 | 0 | 0 |
| MEDIUM | 3 | 0 | 0 |
| LOW | 2 | 0 | 0 |

## Patterns

## Pattern: PAT-001: doc-spec-drift
**Instances:** BJ-001, BJ-002, BJ-003
**Root Cause:** Documentation not updated when code changes. README, CI config, and architecture baseline all contain stale claims about the project's current state.
**Systemic Fix:** Add a CI check or pre-commit hook that validates concrete claims (test counts, module lists, file counts) against the actual codebase.
**Detection Rule:** `grep -n "tests across" README.md` and compare against `python -m pytest --co -q | tail -1`

## Items

### BJ-001: README claims "235 tests across 4,846 lines" but actual is 259 tests
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:36`
**Status:** OPEN
**Pattern:** PAT-001
**Lens:** contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 36 claims "235 tests across 4,846 lines" but the project has 259 tests and significantly more lines of code. The 24-test and 3,000+ line discrepancy reflects the hooks layer and additional test coverage added in prior runs. Users evaluating the plugin see stale numbers.

**Evidence:** README.md:36 reads: `"235 tests across 4,846 lines"`. Holtz recon confirms 259 tests. The hooks/ directory (5 files) and test_hooks.py (24+ tests) were added after the README count was established.

**Discovery Chain:** README claim "235 tests" -> Holtz recon shows 259 tests -> 24-test gap from hooks layer

**Acceptance Criteria:**
- [ ] README.md line 36 reflects actual test count and line count
- [ ] Numbers match `python -m pytest --co -q | tail -1` output

**Validation Command:**
```bash
python -m pytest --co -q 2>/dev/null | tail -1 | grep -q "259" && echo "PASS" || echo "FAIL: test count mismatch"
```

### BJ-002: CI lints all files but pyproject.toml only configures subset
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `.github/workflows/ci.yml:25`
**Status:** OPEN
**Pattern:** PAT-001
**Lens:** contract
**Predicted:** Prediction 2 (confidence: MEDIUM)

**Problem:** CI workflow runs `ruff check .` which lints the entire repo, but `pyproject.toml` only defines `src = ["skills/holtz/scripts", "tests", "hooks"]`. This means CI and local development use different effective ruff configurations for files outside those three directories. If new Python files are added elsewhere, CI may fail with different rules than local ruff, or local ruff may miss issues CI catches.

**Evidence:** `.github/workflows/ci.yml:25`: `ruff check .` (all files). `pyproject.toml:4`: `src = ["skills/holtz/scripts", "tests", "hooks"]` (subset). The `src` config affects import sorting (isort) behavior -- ruff treats files outside `src` as third-party for import ordering purposes.

**Discovery Chain:** CI config says `ruff check .` -> pyproject.toml `src` only covers 3 dirs -> divergent lint behavior for files outside src

**Acceptance Criteria:**
- [ ] CI `ruff check` scope matches pyproject.toml `src` configuration, or pyproject.toml `src` is expanded to cover all Python files in the repo

**Validation Command:**
```bash
diff <(cd /Users/jonr/Documents/non-nitro-repos/holtz && ruff check . 2>&1) <(cd /Users/jonr/Documents/non-nitro-repos/holtz && ruff check skills/holtz/scripts tests hooks 2>&1) && echo "PASS: same results" || echo "DIFF: lint scope mismatch"
```

### BJ-003: Architecture baseline Module Dependencies table omits hooks layer
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/holtz/architecture-baseline.md:49`
**Status:** OPEN
**Pattern:** PAT-001
**Lens:** contract
**Predicted:** Prediction 3 (confidence: MEDIUM)

**Problem:** The Module Dependencies table (lines 49-56) lists only the 4 scripts modules. The hooks/ layer (5 files) is documented in the Drift Log (lines 90-104) as a "new component" with "Severity: LOW" but was never integrated into the main Module Dependencies table or Layering Direction section. The baseline describes a 2-layer architecture but the actual codebase has 3 layers (scripts, hooks, utility).

**Evidence:** `architecture-baseline.md:49-56` Module Dependencies table has 4 rows (validate_punchlist, convergence_check, impact_graph, markdown_utils). Lines 90-94 acknowledge hooks/ exists: "4 Python hook files + hooks.json manifest + _common.py shared utilities added since baseline. Not documented in Structural Snapshot or Module Dependencies."

**Discovery Chain:** Read Module Dependencies table -> 4 rows -> hooks/ not present -> Drift Log acknowledges gap but doesn't fix it

**Acceptance Criteria:**
- [ ] Module Dependencies table includes hooks/ modules (_common, artifact_verification, impact_graph_gate, status_staleness_gate, subagent_findings_check)
- [ ] Layering Direction section includes hooks as a layer

**Validation Command:**
```bash
grep -c "hooks" docs/holtz/architecture-baseline.md | grep -q "[5-9]" && echo "PASS" || echo "FAIL: hooks underrepresented in baseline"
```

### BJ-004: Convergence deletion detection bypassable by delete-then-add
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:306`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 4 (confidence: LOW)

**Problem:** The partial item deletion check on line 307 compares `curr_pl["total"]` against `prev_max_total` (max total across all history entries except the last). If an auditor deletes 3 items and adds 3 new unrelated items in the same iteration, total remains the same, and the deletion is invisible. The items changed identity but the count-based check cannot detect it.

**Evidence:** Lines 306-313: `prev_max_total = max(_get_punchlist(h)["total"] for h in history[:-1])` followed by `if prev_max_total > 0 and curr_pl["total"] < prev_max_total`. This only catches net decreases. A replacement of items (delete old, add new) where `len(deleted) == len(added)` passes the check.

**Discovery Chain:** check_convergence deletion guard checks total count -> total unchanged when equal items deleted and added -> identity change invisible to count-based check

**Acceptance Criteria:**
- [ ] Deletion detection catches identity changes (items replaced, not just count reduced), OR this is documented as a known limitation
- [ ] Test case: 5 items resolved, next iteration has 5 different OPEN items with new IDs -- convergence should not declare "no new items"

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "deletion" -v 2>&1 | tail -5
```

### BJ-005: detect_test_runner priority order is implicit and undocumented
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:71`
**Status:** OPEN
**Lens:** component

**Problem:** `detect_test_runner` iterates a dict of runners in insertion order (Python 3.7+ guarantees). The priority is: pytest, jest, vitest, cargo, go, swift, mocha. A project with both `conftest.py` and `jest.config.js` will always detect pytest. This ordering is correct (most specific marker files like conftest.py should win) but the priority logic is implicit in dict ordering rather than documented or enforced. A future edit that reorders the dict changes runner priority silently.

**Evidence:** Lines 71-79: `markers = {"pytest": [...], "jest": [...], "vitest": [...], ...}`. The first match wins. No comment explains the priority ordering. No test verifies that a project with multiple runner markers detects the expected one.

**Discovery Chain:** detect_test_runner iterates dict -> dict order determines priority -> no test for multi-marker project -> priority change from dict reorder would be silent

**Acceptance Criteria:**
- [ ] Comment in detect_test_runner explains priority ordering, OR
- [ ] Test verifies correct detection when multiple runner markers exist (e.g., conftest.py + jest.config.js -> pytest)

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "detect" -v 2>&1 | tail -10
```

### BJ-006: make_item fixture missing Discovery Chain in defaults
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/conftest.py:40`
**Status:** OPEN
**Lens:** component

**Problem:** The `make_item` fixture in conftest.py includes a `discovery_chain` parameter with a default value, and it renders the Discovery Chain field into the output. However, the validate function requires Discovery Chain (`has_discovery_chain` check on line 327 of validate_punchlist.py). The fixture correctly renders it, but several test cases in test_validate_punchlist.py construct raw markdown strings without including Discovery Chain, and those tests only check specific fields without validating the full item. This means tests that call `validate()` on items missing Discovery Chain would get errors -- but several tests construct items without Discovery Chain and then only check the specific field they care about, never calling validate(). This is not a bug in the fixture, but a pattern where tests avoid full validation, which could mask missing-field issues.

**Evidence:** `conftest.py:40`: `discovery_chain: str = "observed X -> leads to Y -> causes Z"` -- default provided. But `test_validate_punchlist.py` tests like `test_empty_problem_adjacent_to_evidence` (line 7) construct raw markdown without Discovery Chain and only assert on `has_problem` and `has_evidence`, never calling `validate()`. The test would not catch if the parser extracted Discovery Chain from a wrong location.

**Discovery Chain:** make_item has discovery_chain default -> raw-markdown tests omit it -> those tests never call validate() -> field extraction for Discovery Chain is untested in isolation

**Acceptance Criteria:**
- [ ] At least one test verifies that Discovery Chain is correctly parsed in isolation (present vs absent)
- [ ] At least one test verifies that a missing Discovery Chain produces a validation error when validate() is called

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "discovery" 2>&1 | tail -5
```

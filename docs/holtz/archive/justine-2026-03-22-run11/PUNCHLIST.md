# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 265 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 2 | 0 | 0 |
| MEDIUM | 3 | 0 | 0 |
| LOW | 3 | 0 | 0 |

## Patterns

## Pattern: PAT-001: regex-convention-violation
**Instances:** BJ-003, BJ-004, BJ-008
**Root Cause:** \s used in regex patterns where [ \t] is the project convention. \s matches newlines, which is semantically wrong for horizontal whitespace even when practically safe.
**Systemic Fix:** Search-and-replace \s with [ \t] in all non-line-start positions. Add a ruff custom rule or grep check to CI.
**Detection Rule:** `grep -rnP '\\\\s[*+?]' --include='*.py' skills/ hooks/ | grep -v '^\s*#'`

## Items

### BJ-001: impact_graph_gate enforcement scope is narrower than documented requirement
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/impact_graph_gate.py:33`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract
**Predicted:** Prediction 7 (confidence: HIGH)

**Problem:** The impact graph gate hook only checks writes to `docs/holtz/audit/` and `docs/holtz/justine/audit/` subdirectories, but the SKILL.md HARD-GATE requires the impact graph to exist before ANY Phase 1+ audit work, which includes writes to PUNCHLIST.md, investigations/, and other audit output files. An auditor can write punchlist findings or investigation files without a live impact graph, bypassing the enforcement mechanism entirely.

**Evidence:** `hooks/impact_graph_gate.py:33-36`:
```python
if "docs/holtz/justine/audit/" in normalized:
    required = "docs/holtz/justine/impact-graph.json"
elif "docs/holtz/audit/" in normalized:
    required = "docs/holtz/impact-graph.json"
else:
    exit_ok()
```
The `else: exit_ok()` clause allows any write outside audit/ to proceed ungated. Commented as "Known limitation" at line 30-32.

**Discovery Chain:** SKILL.md HARD-GATE says "audit phases require a live impact graph" -> hook only gates `audit/` subdir -> PUNCHLIST.md and investigations/ writes bypass the gate -> enforcement is incomplete

**Acceptance Criteria:**
- [ ] Hook gates writes to PUNCHLIST.md and investigations/ in addition to audit/
- [ ] Test verifies that writing to PUNCHLIST.md without graph is blocked

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestImpactGraphGate -v
```

### BJ-002: status_staleness_gate allows bypass when STATUS.md is deleted mid-run
**Severity:** HIGH
**Category:** bug/security
**Location:** `hooks/status_staleness_gate.py:56`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Predicted:** Prediction 6 (confidence: HIGH)

**Problem:** The staleness gate treats a missing STATUS.md as "first write of the run" and allows the tool call. If an auditor (or a bug) deletes STATUS.md mid-run, all subsequent writes are unblocked regardless of process drift. The hook explicitly documents this as a "Known limitation" at line 53-55, but no mitigation exists. In a plugin environment where context compaction can cause the LLM to lose track of process state, this bypass is a real failure mode, not a theoretical one.

**Evidence:** `hooks/status_staleness_gate.py:52-57`:
```python
# If STATUS.md doesn't exist yet, allow — first write of the run.
# Known limitation: if STATUS.md is deleted mid-run, this also allows,
# bypassing staleness enforcement.
if not os.path.isfile(status_path):
    exit_ok()
```

**Discovery Chain:** prior run 10 finding BH-104 -> code still has same bypass -> STATUS.md deletion disables all staleness enforcement -> process drift goes undetected

**Acceptance Criteria:**
- [ ] Hook detects deleted STATUS.md when other docs/holtz/ artifacts exist (e.g., recon/ or PUNCHLIST.md)
- [ ] Test verifies that STATUS.md deletion mid-run is detected

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py::TestStatusStalenessGate -v
```

### BJ-003: Jest parser \s+ in Tests: line regex could match across newlines
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:143`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 1 (confidence: MEDIUM)

**Problem:** The Jest parser regex `r'Tests:\s+(.+\d+ total)'` uses `\s+` which matches newlines. If subprocess output concatenation (stdout + stderr) produces a line break between "Tests:" and the count line, the regex could either fail to match (likely, since `.+` does not match newlines by default) or match incorrectly. The semantic intent is horizontal whitespace only. While `\s+` is unlikely to cause a bug here in practice because `re.search` without `re.DOTALL` means `.+` stops at newlines anyway, the pattern is semantically wrong per the project's own convention (architecture baseline: "All regex in source uses `[ \t]` not `\s` for horizontal whitespace").

**Evidence:** `convergence_check.py:143`: `jest_line = re.search(r'Tests:\s+(.+\d+ total)', output)`
Architecture baseline invariant: "All regex in source uses `[ \t]` not `\s` for horizontal whitespace"
Also found at lines 163 (Vitest) and 180 (Cargo).

**Discovery Chain:** pattern library match (regex-newline-leak) -> grep found 3 \s hits in parser regexes -> checked architecture baseline -> baseline says project uses [ \t] not \s -> convention violation

**Acceptance Criteria:**
- [ ] Jest parser regex uses `[ \t]+` instead of `\s+`
- [ ] Vitest parser regex uses `[ \t]*` instead of `\s*`/`\s+`
- [ ] Cargo parser regex uses `[ \t]*` instead of `\s*`

**Validation Command:**
```bash
grep -n '\\s' skills/holtz/scripts/convergence_check.py | grep -v '^\s*#' | grep -v 'test'
```

### BJ-004: artifact_verification.py uses \s+ in --graph regex, violating project convention
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/artifact_verification.py:29`
**Status:** OPEN
**Lens:** data-flow
**Predicted:** Prediction 3 (confidence: LOW)

**Problem:** The `--graph\s+` regex in artifact_verification.py uses `\s+` which technically matches newlines, violating the project's stated convention that regex uses `[ \t]` not `\s` for horizontal whitespace. In practice this is harmless because shell commands passed to hooks are single-line strings, but it is a convention violation.

**Evidence:** `hooks/artifact_verification.py:29`: `match = re.search(r'--graph\s+["\']?([^"\'\s]+)["\']?', command)`
Architecture baseline: "All regex in source uses `[ \t]` not `\s` for horizontal whitespace"

**Discovery Chain:** pattern library match (regex-newline-leak) -> grep hit -> checked baseline convention -> violation confirmed

**Acceptance Criteria:**
- [ ] Regex uses `[ \t]+` instead of `\s+`

**Validation Command:**
```bash
grep -n '\\s' hooks/artifact_verification.py
```

### BJ-005: detect_test_runner multi-marker priority relies on dict insertion order
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:76`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 4 (confidence: MEDIUM)

**Problem:** The test runner detection priority (pytest > jest > vitest > cargo > go > swift > mocha) is determined by dict literal insertion order in CPython 3.7+. While tests for priority exist (test_detect_runner_priority_pytest_over_jest and jest_over_vitest), the priority ordering is implicit rather than documented. The code comment at line 75 explains the ordering rationale but if someone reorders the dict entries, priority silently changes. This is a fragility, not a bug -- the current behavior is correct.

**Evidence:** `convergence_check.py:76-84`:
```python
markers = {
    "pytest": [...],
    "jest": [...],
    "vitest": [...],
    ...
}
```
Tests exist for pytest-over-jest and jest-over-vitest (lines 1036-1053).

**Discovery Chain:** prior run 9 finding BJ-005 -> code unchanged -> dict ordering is implicit priority -> fragile but tested

**Acceptance Criteria:**
- [ ] Comment explicitly states that dict ordering IS the priority
- [ ] Or: use OrderedDict/list-of-tuples to make ordering semantically explicit

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py::test_detect_runner_priority_pytest_over_jest tests/test_convergence_check.py::test_detect_runner_priority_jest_over_vitest -v
```

### BJ-006: Vitest parser returns None for all-skipped output -- test exists but fix may be incomplete
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:163`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component

**Problem:** The Vitest parser regex `r'^\s*Tests\s+(.+\d+ (?:passed|failed|skipped))'` requires the summary line to end with "passed", "failed", or "skipped". A test at line 1082 (`test_vitest_all_skipped`) covers this case with output `"Tests  3 skipped (3)"` which DOES match because it ends with "skipped". However, the regex uses `\s*` at the start, which matches newlines (see BJ-003). More critically, the Vitest fixture `VITEST_WITH_SKIPPED` at runner_fixtures.py line 149 has the summary as `"Tests  2 skipped | 9 passed (11)"` which matches. The real edge case -- Vitest output where the Tests summary line format changes across Vitest versions -- is not tested. The fix from prior run 10 appears present.

**Evidence:** Test exists at line 1082 and passes. But the test uses synthetic output (`" Test Files  1 skipped (1)\n      Tests  3 skipped (3)\n   Duration  100ms\n"`). If real Vitest outputs a different format for all-skipped (e.g., `"Tests  3 skipped"` without parenthetical), the regex still matches. This is now a LOW-risk remaining gap, not the HIGH it was in run 10.

**Discovery Chain:** prior run 10 BH-108 -> checked test file -> test added at line 1082 -> test covers the primary case -> remaining risk is version format variance

**Acceptance Criteria:**
- [ ] Test remains green (fix persists)
- [ ] \s convention violation in regex addressed (covered by BJ-003)

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py::test_vitest_all_skipped -v
```

### BJ-007: Go test parser susceptible to injected output -- documented limitation, no test
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:195`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** security

**Problem:** The Go verbose test parser counts `--- PASS:`, `--- FAIL:`, and `--- SKIP:` lines using regex against raw stdout. A Go test function that prints fake `"--- PASS: FakeTest ("` lines to stdout would inflate the passed count. The code documents this at lines 193-194 as a "Known limitation" but no test covers it, and no mitigation exists.

**Evidence:** `convergence_check.py:192-196`:
```python
# Known limitation: test functions that print "--- PASS: FakeName (" to stdout
# at line start will inflate the count.
passed = len(re.findall(r'^--- PASS: \w+[ (]', output, re.MULTILINE))
```
Prior run 10 (BH-109) flagged this. No test for injected output exists.

**Discovery Chain:** prior run 10 BH-109 -> code still has documented limitation -> no test -> no mitigation -> parser returns wrong counts silently

**Acceptance Criteria:**
- [ ] Test exists demonstrating the limitation (documenting rather than fixing, since there's no reliable fix)
- [ ] Or: parser uses a secondary signal (e.g., `test result:` summary line) to cross-check counts

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k "go" -v
```

### BJ-008: \s usage in impact_graph.py ENTITY_PATTERNS violates convention but is safe
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/impact_graph.py:26-36`
**Status:** OPEN
**Lens:** data-flow

**Problem:** The ENTITY_PATTERNS dict uses `\s` in 9 regex patterns (e.g., `r"^\s*(?:async\s+)?def\s+{name}\s*\("`) which violates the architecture baseline convention "All regex in source uses `[ \t]` not `\s` for horizontal whitespace." However, these patterns are applied line-by-line in `drift_check` (line 277: `for i, line_text in enumerate(content.splitlines(), 1)`), so `\s` never encounters newlines. The violation is cosmetic but inconsistent with the project convention.

**Evidence:** `impact_graph.py:26-36` contains 9 patterns with `\s`. Architecture baseline states `[ \t]` convention. Patterns are applied per-line via `splitlines()` so newline matching is impossible.

**Discovery Chain:** grep found \s in impact_graph.py -> checked usage context -> applied per-line via splitlines -> safe but convention violation

**Acceptance Criteria:**
- [ ] Replace \s with [ \t] in ENTITY_PATTERNS for convention consistency
- [ ] Or: document exception to convention for per-line patterns

**Validation Command:**
```bash
grep -n '\\\\s' skills/holtz/scripts/impact_graph.py
```

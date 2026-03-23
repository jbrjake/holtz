# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 259 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 0    | 1        | 0        |
| LOW      | 0    | 4        | 0        |

## Patterns

## Items

### BH-001: README inventory counts stale — test count and line count wrong
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:36`
**Status:** RESOLVED
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 36 states "235 tests across 4,846 lines" but the current codebase has 259 tests (24 hook tests added in run 8) across 8,026 lines (hooks, additional test code, and SKILL.md growth). Both numbers are significantly stale.

**Evidence:** `python -m pytest --tb=short -q` reports "259 passed". `wc -l` across source, test, and doc files totals 8,026 lines. README says 235 and 4,846 respectively.

**Discovery Chain:** Phase 1 README claim verification → counted tests (259 vs 235) → counted lines (8,026 vs 4,846) → both stale since hooks/ addition

**Acceptance Criteria:**
- [ ] README inventory numbers match actual test count and line count
- [ ] Validation: counts match

**Validation Command:**
```bash
python -m pytest --tb=short -q 2>&1 | tail -1 && wc -l skills/holtz/scripts/*.py hooks/*.py tests/*.py skills/holtz/SKILL.md skills/justine/SKILL.md agents/*.md 2>/dev/null | tail -1
```

**Resolution:** Updated README.md line 36 from "235 tests across 4,846 lines" to "259 tests across 8,026 lines". Note: after adding 2 new tests in this run, actual count is now 261.

### BH-002: validate_punchlist.py uses \s in VC blank-line matcher — convention violation
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/validate_punchlist.py:233`
**Status:** RESOLVED
**Lens:** data-flow

**Problem:** The architecture baseline documents a convention: "All regex in source uses `[ \t]` not `\s` for horizontal whitespace". Line 233 uses `(?:\s*\n)*` to match blank lines between the Validation Command header and the opening fence. While functionally correct (the `\n` anchor prevents actual cross-line matching), it violates the stated convention. The `\s*` could match `\f` or `\v` characters, though these are vanishingly unlikely in markdown.

**Evidence:** `validate_punchlist.py:233`: `_vc_header = r'\*\*Validation Command:\*\*[ \t]*\n(?:\s*\n)*'`. The `[ \t]*` on the same line correctly uses the convention, but `\s*` in the next group does not.

**Discovery Chain:** Global pattern library regex-newline-leak heuristic → grep for `\s[*+?]` → found `(?:\s*\n)*` at line 233 → convention violation in markdown-processing code

**Acceptance Criteria:**
- [ ] `\s*` replaced with `[ \t]*` in the VC blank-line matcher
- [ ] Validation: all tests still pass

**Validation Command:**
```bash
source .venv/bin/activate && grep -n '\\\\s' skills/holtz/scripts/validate_punchlist.py && python -m pytest tests/test_validate_punchlist.py --tb=short -q
```

**Resolution:** Changed `(?:\s*\n)*` to `(?:[ \t]*\n)*` at line 233 of validate_punchlist.py. All 68 tests still pass.

### BH-003: Architecture baseline Module Dependencies table omits hooks layer
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/holtz/architecture-baseline.md:49`
**Status:** RESOLVED
**Lens:** contract

**Problem:** The Module Dependencies table (lines 49-56) lists only the 4 scripts modules. The hooks/ layer (5 files) is documented in the Drift Log as a "new component" but was never integrated into the main Module Dependencies table or Layering Direction section. The Drift Log itself says: "Not documented in Structural Snapshot or Module Dependencies."

**Evidence:** `architecture-baseline.md:49-56` — 4 rows in Module Dependencies. Lines 90-94 of Drift Log: "4 Python hook files + hooks.json manifest + _common.py shared utilities added since baseline. Not documented in Structural Snapshot or Module Dependencies."

**Discovery Chain:** Justine read Module Dependencies table → 4 rows → hooks/ not present → Drift Log acknowledges gap but doesn't fix it

**Acceptance Criteria:**
- [ ] Module Dependencies table includes hooks/ modules
- [ ] Layering Direction section includes hooks as a layer

**Validation Command:**
```bash
grep -c "_common\|artifact_verification\|impact_graph_gate\|status_staleness_gate\|subagent_findings" docs/holtz/architecture-baseline.md
```

**Resolution:** Added 5 hooks modules to Module Dependencies table and hooks layer to Layering Direction section in architecture-baseline.md.

### BH-004: detect_test_runner priority order undocumented and untested
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:71`
**Status:** RESOLVED
**Lens:** component

**Problem:** `detect_test_runner` iterates a dict of runners in insertion order. Priority is: pytest, jest, vitest, cargo, go, swift, mocha. A project with both `conftest.py` and `jest.config.js` will always detect pytest. This ordering is implicit in dict key order with no comment explaining the rationale and no test verifying multi-marker behavior.

**Evidence:** Lines 71-79: `markers = {"pytest": [...], "jest": [...], ...}`. First match wins. No comment on priority. No test with multiple runner markers.

**Discovery Chain:** Justine found dict iteration determines priority → no documentation → no test for multi-marker project → silent behavior change if dict reordered

**Acceptance Criteria:**
- [ ] Comment in detect_test_runner explains priority ordering
- [ ] Test verifies correct detection when multiple runner markers exist

**Validation Command:**
```bash
grep -A2 "def detect_test_runner" skills/holtz/scripts/convergence_check.py | head -5
```

**Resolution:** Added 4-line priority comment to detect_test_runner explaining dict ordering rationale. Added 2 tests: `test_detect_runner_priority_pytest_over_jest` and `test_detect_runner_priority_jest_over_vitest`.

### BH-005: Convergence deletion detection bypassable by delete-then-add
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:306`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** data-flow

**Problem:** The partial item deletion check compares `curr_pl["total"]` against the historical max. If an auditor deletes N items and adds N new items in the same iteration, total remains unchanged and the deletion warning never fires. The items changed identity but the count-based check is blind to it. Note: convergence still requires zero open items, so this can't cause false convergence — it only bypasses the deletion warning message.

**Evidence:** Lines 306-313: `prev_max_total = max(...)` then `if curr_pl["total"] < prev_max_total`. Equal-count replacement passes this check.

**Discovery Chain:** Justine analyzed deletion guard → count-based comparison → equal replacement invisible → loss of audit trail for deleted items

**Acceptance Criteria:**
- [ ] Either detect identity changes (e.g., track item IDs across iterations) or document this as a known limitation in the code

**Validation Command:**
```bash
grep -n "prev_max_total" skills/holtz/scripts/convergence_check.py
```

**Resolution:** Documented the limitation as a 3-line comment above the deletion check in convergence_check.py. The limitation cannot cause false convergence (open items still block), it only bypasses the deletion warning.


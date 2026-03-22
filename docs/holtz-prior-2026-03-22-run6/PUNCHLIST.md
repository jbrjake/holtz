# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 226 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM   | 0    | 1        | 0        |
| LOW      | 0    | 7        | 0        |

## Patterns

## Pattern: PAT-001: Duplicated fence-parsing logic
**Instances:** BH-005, BH-006
**Root Cause:** mask_code_fences and has_unclosed_fence independently implement the same CommonMark fence state machine
**Systemic Fix:** Extract shared _iterate_fences() generator; both functions consume it
**Detection Rule:** grep -n 'in_fence' skills/holtz/scripts/markdown_utils.py | wc -l (should be <= 2 after fix)

## Items

### BH-001: Validator does not check for `## Patterns` section in punchlist file structure
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/holtz/scripts/validate_punchlist.py:267-276`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 4 (confidence: MEDIUM)

**Problem:** punchlist-format.md defines the File Structure as requiring `# Holtz Punchlist`, `## Summary`, `## Patterns`, and `## Items` sections. The validator checks for the header, Summary, and Items sections but does not check for the Patterns section.

**Evidence:** punchlist-format.md File Structure (lines 82-96) lists `## Patterns` as a required section. validate_punchlist.py lines 271-275 check for `# Holtz Punchlist`, `## Summary`, and `## Items` only.

**Discovery Chain:** punchlist-format.md File Structure lists 4 sections → validator checks 3 of 4 → `## Patterns` check missing

**Acceptance Criteria:**
- [x] validate_punchlist.py warns when `## Patterns` section is absent from punchlist content
- [x] Test covers the new warning

**Validation Command:**
```bash
python -m pytest tests/ -k "patterns_section" -v
```

**Resolution:** Added `## Patterns` check to validate() alongside existing structure checks. Added test_missing_patterns_section_produces_warning. Updated 2 existing tests that expected 3 structure warnings to expect 4.

### BH-002: README claims "8 reference docs" but 9 exist
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:31`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 5 (confidence: MEDIUM)

**Problem:** README.md line 31 states "8 reference docs" in the "What's inside" section. The actual count in `skills/holtz/references/` is 9.

**Evidence:** `ls skills/holtz/references/ | wc -l` returns 9. README says "8 reference docs".

**Discovery Chain:** README claims 8 reference docs → `ls` of references directory shows 9 files → count is stale

**Acceptance Criteria:**
- [x] README "What's inside" count matches actual number of reference docs
- [x] Validation: count of files in skills/holtz/references/ matches the number stated in README

**Validation Command:**
```bash
count=$(ls skills/holtz/references/ | wc -l | tr -d ' '); grep -q "$count reference docs" README.md && echo "PASS" || echo "FAIL"
```

**Resolution:** Changed "8 reference docs" to "9 reference docs" in README.md.

### BH-003: README incorrectly attributes `shares_pattern` edges to Phase 1
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:63`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 5 (confidence: MEDIUM)

**Problem:** README.md Phase 1 description includes `shares_pattern` in the edge types added during Phase 1. Per SKILL.md, `shares_pattern` edges are added during Phase 5 (Pattern Analysis), not Phase 1.

**Evidence:** README.md line 63 listed `assumes`, `diverges_from`, `shares_pattern`. SKILL.md Phase 1 specifies only `assumes` and `diverges_from`.

**Discovery Chain:** README lists 3 edge types for Phase 1 → SKILL.md Phase 1 lists only 2 → `shares_pattern` is a Phase 5 activity → README misattributes

**Acceptance Criteria:**
- [x] README Phase 1 description lists only `assumes`, `diverges_from`
- [x] `shares_pattern` removed from Phase 1 description

**Validation Command:**
```bash
grep -A5 "Phase 1:" README.md | grep -q "shares_pattern" && echo "FAIL" || echo "PASS"
```

**Resolution:** Removed `shares_pattern` from README Phase 1 edge type list. Now lists only `assumes`, `diverges_from`.

### BH-004: Dead guard block in validate() duplicates masked_content computation
**Severity:** LOW
**Category:** design/dead-code
**Location:** `skills/holtz/scripts/validate_punchlist.py:279-281`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** The second `if not masked_content:` guard block was unreachable dead code, duplicating the computation already performed by the first guard.

**Evidence:** Two identical `if content: if not masked_content:` blocks existed at lines 268-270 and 279-281.

**Discovery Chain:** Prediction 2 flagged duplicate guard blocks → control flow analysis confirmed second is unreachable

**Acceptance Criteria:**
- [x] Dead guard block removed
- [x] All tests still pass after removal

**Validation Command:**
```bash
python -m pytest tests/ -q --tb=short
```

**Resolution:** Removed the duplicate `if not masked_content:` guard from the pattern block validation section. The two `if content:` blocks remain separate for logical grouping but the second no longer contains the dead guard.

### BH-005: mask_code_fences and has_unclosed_fence duplicate fence iteration logic
**Severity:** LOW
**Category:** design/duplication
**Location:** `skills/holtz/scripts/markdown_utils.py:13-82`
**Status:** RESOLVED
**Pattern:** PAT-001
**Lens:** integration
**Predicted:** Prediction 3 (confidence: MEDIUM)

**Problem:** Both functions independently implemented the same CommonMark fence-detection state machine, risking maintenance divergence.

**Evidence:** Both functions shared module-level regex constants but duplicated the state machine loop.

**Discovery Chain:** Prediction 3 flagged dual-parser-divergence → code reading confirmed identical state machines → risk is maintenance divergence

**Acceptance Criteria:**
- [x] Shared fence iteration extracted (`_iterate_fences()` generator)
- [x] Both functions refactored to consume the shared iterator
- [x] All tests still pass after refactor

**Validation Command:**
```bash
python -m pytest tests/ -q --tb=short
```

**Resolution:** Extracted `_iterate_fences()` generator yielding (line_index, in_fence) tuples. `mask_code_fences` blanks lines where `fenced=True`. `has_unclosed_fence` tracks the last `fenced` state. Single state machine, two consumers.

### BH-006: has_unclosed_fence missing test coverage for tilde fences and CRLF
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_markdown_utils.py`
**Status:** RESOLVED
**Pattern:** PAT-001
**Lens:** component

**Problem:** `has_unclosed_fence` was tested for backtick fences only. No test covered tilde fences or CRLF input.

**Evidence:** Only 4 tests existed for `has_unclosed_fence`, all using backtick fences.

**Discovery Chain:** Phase 2 audit → checked has_unclosed_fence coverage → only backtick scenarios → tilde and CRLF paths untested

**Acceptance Criteria:**
- [x] Test added: unclosed tilde fence returns True
- [x] Test added: closed tilde fence returns False
- [x] Test added: CRLF content with unclosed fence returns True

**Validation Command:**
```bash
python -m pytest tests/test_markdown_utils.py -q --tb=short
```

**Resolution:** Added 3 tests: test_has_unclosed_tilde_fence, test_has_closed_tilde_fence, test_has_unclosed_fence_crlf. All pass.

### BH-007: drift_check has no test for nodes with line=None
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_impact_graph.py`
**Status:** RESOLVED
**Lens:** component

**Problem:** No test exercised the `node["line"] is not None` guard in drift_check, meaning the guard could be accidentally removed without test failure.

**Evidence:** All drift_check tests created nodes with explicit line numbers.

**Discovery Chain:** Phase 2 audit → checked drift_check inputs → all have explicit line numbers → line=None guard untested

**Acceptance Criteria:**
- [x] Test added: node with line=None and entity found does not crash or report drift
- [x] Test exercises the `node["line"] is not None` guard

**Validation Command:**
```bash
python -m pytest tests/test_impact_graph.py -k drift -q --tb=short
```

**Resolution:** Added test_drift_check_line_none_no_crash. Creates a node with line=None for a function that exists in the file. Confirms no crash and no drift reported.

### BH-008: Vitest output parser assumes fixed component order
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:157`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** component

**Problem:** Vitest parser used a single order-dependent regex unlike the Jest parser which uses independent searches per component.

**Evidence:** Vitest parser required `failed | skipped | passed` in exact order. Jest parser uses separate `re.search` calls.

**Discovery Chain:** Phase 3 review → compared Jest and vitest parsers → Jest handles any order → vitest is order-dependent

**Acceptance Criteria:**
- [x] Vitest parser refactored to use independent regex searches per component
- [x] Test added for vitest output with non-standard component order

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k vitest -q --tb=short
```

**Resolution:** Refactored vitest parser to match the Jest pattern: find the Tests summary line, then use independent `re.search` calls for passed/failed/skipped. Added test_vitest_skipped_before_passed for non-standard order.

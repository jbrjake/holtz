# Holtz Punchlist
> Generated: 2026-03-21 | Project: holtz (run 5) | Baseline: 157 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM | 0 | 3 | 0 |
| LOW | 0 | 6 | 0 |

## Patterns

## Items

### BH-001: Type checking recommended in 6 consecutive audit summaries
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** docs/holtz-prior-*/SUMMARY.md, bug-hunter-prior-*/BUG-HUNTER-SUMMARY.md
**Status:** RESOLVED

**Problem:** This recommendation has appeared in 6 consecutive audit summaries without being implemented: "Add mypy or ruff type checking to catch type issues at development time." Ruff linting was added (pyproject.toml selects E, F, W, I, UP, B, SIM) but type annotations enforcement (ANN, TC rules) is not enabled.

**Evidence:** Found in: docs/holtz-prior-2026-03-19-run2/SUMMARY.md, docs/holtz-prior-2026-03-20-run2/SUMMARY.md, docs/holtz-prior-2026-03-20-run3/SUMMARY.md, docs/holtz-prior-2026-03-20-run4/SUMMARY.md, bug-hunter-prior-2026-03-21-run3/BUG-HUNTER-SUMMARY.md, bug-hunter-prior-2026-03-21-run4/BUG-HUNTER-SUMMARY.md.

**Discovery Chain:** Prior summary scan → recommendation "add type checking" found in 6 summaries
→ 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [x] Ruff type annotation rules or mypy is configured and passing
- [x] Validation: type checking produces zero errors on all source files

**Validation Command:**
```bash
.venv/bin/ruff check skills/holtz/scripts/ tests/ --select ANN 2>&1 | head -5
```

**Resolution:** Added ANN rules to ruff select in pyproject.toml. Added type annotations to all source functions (save_history, main, _masked_pos_to_orig_offset, _section_from_original). Tests excluded from ANN via per-file-ignores.

### BH-002: Redundant mask_code_fences call in validate()
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/validate_punchlist.py:263-264`
**Status:** RESOLVED

**Problem:** validate() calls mask_code_fences redundantly when called from main(). parse_punchlist already masks the content.

**Evidence:** Recommended in 3 prior summaries.

**Discovery Chain:** Prior summary scan → recommendation "pass masked content to validate()" found in 3 summaries
→ 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [x] parse_punchlist accepts pre-computed masked content via _masked parameter
- [x] main() calls mask_code_fences once and passes to both parse_punchlist and validate()
- [x] No double mask_code_fences call in the main() path

**Validation Command:**
```bash
grep -n 'mask_code_fences' skills/holtz/scripts/validate_punchlist.py
```

**Resolution:** Added `_masked` parameter to parse_punchlist. main() now calls mask_code_fences once and passes precomputed result to both parse_punchlist and validate(). All 157+ tests pass.

### BH-003: Two residual permissive validator assertions use >= instead of exact count
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_convergence_check.py:76`, `tests/test_validate_punchlist.py:1614`
**Status:** RESOLVED

**Problem:** Two assertions survived the PAT-001 fix because they use `>=` rather than `> 0`.

**Evidence:** Both assertions explicitly document the expected count in their error messages but use `>=` instead of `==`.

**Discovery Chain:** Searched for `>=` assertions in test files → found 2 instances that survived PAT-001 fix → both have deterministic expected counts but use permissive comparison

**Acceptance Criteria:**
- [x] `test_unrecognized_status_counted`: change `>= 2` to `== 2`
- [x] `test_pattern_block_missing_field_warns`: change `>= 2` to `== 2`

**Validation Command:**
```bash
grep -n '>= 2' tests/test_convergence_check.py tests/test_validate_punchlist.py
```

**Resolution:** Changed both assertions from `>= 2` to `== 2`.

### BH-004: Stall detection test asserts "3" in message — vacuously true
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_convergence_check.py:959`
**Status:** RESOLVED

**Problem:** `test_stall_detection_triggers` asserts `"3" in message` which matches fixed text "last 3 iterations", not the actual open_items count.

**Evidence:** `convergence_check.py:331-334`: message template includes "last 3 iterations".

**Discovery Chain:** Audited single-character `in` assertions → `"3" in message` found → cross-referenced with source template → confirmed "3" always present in fixed text

**Acceptance Criteria:**
- [x] Assert specific open_items string: `"3 items remain open" in message`

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_convergence_check.py::test_stall_detection_triggers -v
```

**Resolution:** Changed assertion to `"3 items remain open" in message`.

### BH-005: Integration tests leak temp files
**Severity:** LOW
**Category:** bug/state
**Location:** `tests/test_integration.py:118,135,179,212`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** All 4 integration tests used `NamedTemporaryFile(delete=False)` without cleanup.

**Evidence:** 4 instances of `NamedTemporaryFile(delete=False)` in test_integration.py, zero cleanup.

**Discovery Chain:** Grepped for `NamedTemporaryFile` → found 4 with `delete=False` → no cleanup found → convergence_check tests use `tmp_path` correctly

**Acceptance Criteria:**
- [x] Integration tests use `tmp_path` fixture instead of `NamedTemporaryFile(delete=False)`
- [x] No temp files leaked after test run

**Validation Command:**
```bash
grep -n 'NamedTemporaryFile\|tmp_path' tests/test_integration.py
```

**Resolution:** Rewrote all 4 integration tests to use pytest's `tmp_path` fixture. Removed `tempfile` import.

### BH-006: Evidence field enforced as WARNING but docs say required
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/holtz/scripts/validate_punchlist.py:324-325`
**Status:** RESOLVED

**Problem:** README says evidence is required but validate_punchlist.py only warns on missing evidence.

**Evidence:** `validate_punchlist.py:324`: warning for missing evidence vs. error for missing acceptance criteria.

**Discovery Chain:** README says "every finding" has evidence → validator checks evidence as warning not error → punchlist-format.md does not mark evidence as optional → inconsistency

**Acceptance Criteria:**
- [x] Docs updated to indicate evidence is recommended but not enforced

**Validation Command:**
```bash
grep -n 'evidence' skills/holtz/scripts/validate_punchlist.py | grep -i 'error\|warning'
```

**Resolution:** Updated punchlist-format.md Rules section to document that Evidence is recommended but not enforced (validator warns, does not error). Aligns docs with actual behavior.

### BH-007: Non-atomic save_history risks HISTORY.json corruption
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `skills/holtz/scripts/convergence_check.py:243`
**Status:** RESOLVED
**Determinism:** theoretical

**Problem:** `save_history()` uses `Path.write_text()` which truncates before writing. Interrupted writes corrupt the file.

**Evidence:** No temp file, no atomic rename, no locking.

**Discovery Chain:** Identified `save_history` as write path → `Path.write_text()` truncates first → interrupted write corrupts file → history lost

**Acceptance Criteria:**
- [x] save_history uses atomic write (write to temp file + os.rename)

**Validation Command:**
```bash
grep -n 'write_text\|os.rename\|tempfile' skills/holtz/scripts/convergence_check.py
```

**Resolution:** Rewrote save_history to use tempfile.mkstemp + os.write + os.rename for atomic writes. Exception handler cleans up temp file on failure.

### BH-008: Convergence IN PROGRESS message hides item regressions
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:337-341`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** `max(0, items_resolved)` clamp hides negative values when resolved items are re-opened.

**Evidence:** `items_resolved = curr_pl["RESOLVED"] - prev_pl["RESOLVED"]` can go negative; `max(0, items_resolved)` clamps to 0.

**Discovery Chain:** Read IN PROGRESS message → traced calculation → negative resolved count clamped to 0 → regression hidden

**Acceptance Criteria:**
- [x] Message reports negative resolved count as "N re-opened this iteration"
- [x] Test covers scenario where resolved count decreases between iterations

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_convergence_check.py -x -q 2>&1 | tail -5
```

**Resolution:** Replaced `max(0, ...)` clamping with explicit branch: positive resolved shows "N resolved", negative shows "N re-opened". Added test_reopened_items_reported_in_message.

### BH-009: VC regex fence length not enforced per CommonMark
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:234-238`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** VC extraction regex used `{3,}` independently for open and close fences. A 4-backtick fence could be falsely closed by a 3-backtick line.

**Evidence:** `mask_code_fences` tracks `fence_char_count` but VC extraction did not.

**Discovery Chain:** Compared `mask_code_fences` (uses `fence_char_count`) with VC regex (uses `{3,}`) → identified mismatch

**Acceptance Criteria:**
- [x] VC regex captures opening fence length and requires closing fence to match
- [x] Test: 4-backtick VC fence not prematurely closed by 3-backtick content line

**Validation Command:**
```bash
.venv/bin/python -m pytest tests/test_validate_punchlist.py -x -q 2>&1 | tail -5
```

**Resolution:** Rewrote VC extraction to use a two-step approach: find opening fence with capturing group for char type and length, then dynamically build closing pattern requiring >= that length. Added test_validation_command_4backtick_not_closed_by_3backtick.

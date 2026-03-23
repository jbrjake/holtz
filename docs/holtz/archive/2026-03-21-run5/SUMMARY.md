# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 5
**Date:** 2026-03-21
**Duration:** Phases 0-6 complete

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 157 | 159 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 0.08s | 0.09s |
| Ruff errors | 0 | 0 |
| Ruff rules | E,F,W,I,UP,B,SIM | E,F,W,I,UP,B,SIM,ANN |
| Punchlist items | - | 9 |
| Resolved | - | 9 |
| Open | - | 0 |
| Deferred | - | 0 |

**Net new tests:** 2

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 3 | BH-001, BH-002, BH-007 |
| LOW | 6 | BH-003, BH-004, BH-005, BH-006, BH-008, BH-009 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| design/inconsistency | 2 | BH-001, BH-002 |
| test/shallow | 2 | BH-003, BH-004 |
| bug/state | 2 | BH-005, BH-007 |
| bug/logic | 2 | BH-008, BH-009 |
| doc/drift | 1 | BH-006 |

## Key Fixes

1. **BH-001 (MEDIUM):** Enabled ruff ANN type annotation rules for source files. Added type annotations to 5 functions across 2 source files. Tests excluded from ANN enforcement. Resolves recommendation appearing in 6 consecutive prior summaries.

2. **BH-002 (MEDIUM):** Eliminated redundant mask_code_fences call in main() path. parse_punchlist now accepts pre-computed masked content via `_masked` parameter. main() calls mask_code_fences once and passes result to both parse_punchlist and validate(). Resolves recommendation appearing in 3 consecutive prior summaries.

3. **BH-007 (MEDIUM):** save_history now uses atomic writes (tempfile.mkstemp + os.write + os.rename). Prevents HISTORY.json corruption from interrupted writes. Exception handler cleans up temp file on failure.

4. **BH-009 (LOW):** VC extraction regex now tracks opening fence length and requires closing fence to match, per CommonMark spec. Prevents 4-backtick fences from being falsely closed by 3-backtick content lines.

5. **BH-008 (LOW):** Convergence IN PROGRESS message now reports re-opened items explicitly ("N re-opened this iteration") instead of clamping negative resolved counts to 0.

6. **BH-003, BH-004 (LOW):** Tightened 2 residual `>=` assertions to `==` and fixed vacuous "3" substring assertion in stall detection test.

7. **BH-005 (LOW):** Converted 4 integration tests from leaking `NamedTemporaryFile(delete=False)` to pytest's `tmp_path` fixture.

8. **BH-006 (LOW):** Updated punchlist-format.md to document that Evidence is recommended but not enforced, aligning with actual validator behavior.

## Recommendations

1. **Consider adding mypy** — Ruff ANN rules enforce annotation presence but not type correctness. mypy would catch actual type mismatches at development time. However, this may be diminishing returns for a codebase of this size.

2. **Test boilerplate reduction** — 36 repetitions of the standard valid-item template in test_validate_punchlist.py. A `make_item(**overrides)` builder fixture would reduce this, though inline markdown keeps tests self-documenting.

3. **Coverage reporting** — No coverage tool is configured. Adding `pytest-cov` would make coverage gaps visible. The test suite has good coverage but some paths are only exercised indirectly (e.g., multiple consecutive fences in mask_code_fences, main() functions).

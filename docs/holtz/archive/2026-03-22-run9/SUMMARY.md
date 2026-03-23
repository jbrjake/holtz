# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 9
**Date:** 2026-03-22
**Duration:** Phases 0-6 complete

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 259 | 261 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 0.95s | 0.87s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Mypy files | 9 | 9 |
| Punchlist items | — | 5 |
| Resolved | — | 5 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 2 (detect_test_runner priority tests)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 1 | BH-003 |
| LOW | 4 | BH-001, BH-002, BH-004, BH-005 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| doc/drift | 2 | BH-001, BH-003 |
| design/inconsistency | 2 | BH-002, BH-004 |
| bug/logic | 1 | BH-005 (theoretical, documented) |

## Key Fixes

1. **BH-001 (LOW):** Updated README.md inventory from "235 tests across 4,846 lines" to "261 tests across 8,026 lines".

2. **BH-002 (LOW):** Changed `(?:\s*\n)*` to `(?:[ \t]*\n)*` in validate_punchlist.py:233, aligning with the architecture baseline's `[ \t]` convention.

3. **BH-003 (MEDIUM):** Added 5 hooks modules to the architecture baseline's Module Dependencies table and added hooks as a layer in the Layering Direction section.

4. **BH-004 (LOW):** Added priority documentation comment to `detect_test_runner` and 2 tests verifying pytest-over-jest and jest-over-vitest priority.

5. **BH-005 (LOW):** Documented equal-count replacement limitation in convergence deletion detection as a code comment.

## Justine Merge

Justine found 6 items. After verification:
- 1 agreement (BH-001/BJ-001)
- 1 Holtz-only item (BH-002)
- 3 Justine-only verified items (BH-003/BJ-003, BH-004/BJ-005, BH-005/BJ-004)
- 2 Justine FALSE POSITIVES (BJ-002: CI lint scope — no Python files outside src; BJ-006: Discovery Chain untested — 4 dedicated tests exist)

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 1         | 1         | 100%     |
| MEDIUM     | 2         | 0         | 0%       |
| LOW        | 2         | 0         | 0%       |
| **Total**  | **5**     | **1**     | **20%**  |

- Prediction 1 (HIGH, README doc-spec drift): CONFIRMED -> BH-001
- Prediction 2 (LOW, regex-newline-leak in convergence_check): UNCONFIRMED
- Prediction 3 (MEDIUM, dual parser divergence): UNCONFIRMED
- Prediction 4 (MEDIUM, hooks edge cases): UNCONFIRMED
- Prediction 5 (LOW, VC blank-line \s): Found as convention violation (BH-002), not functional bug

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 1 | 12 | 2 HIGH, 6 MEDIUM, 4 LOW | PAT-001: code-fence-unaware parsing | 48 |
| 2 | 5 | 2 MEDIUM, 3 LOW | PAT-002: incomplete code-fence isolation | 10 |
| 3 | 3 | 3 LOW | None (all distinct) | 2 |
| 4 | 4 | 2 MEDIUM, 2 LOW | PAT-001: structural-awareness divergence | 4 |
| 5 | 9 | 3 MEDIUM, 6 LOW | None | 2 |
| 6 | 8 | 1 MEDIUM, 7 LOW | PAT-001: duplicated fence-parsing logic | 6 |
| 7 | 2 | 2 MEDIUM | None (escalated recommendations only) | 3 |
| 8 | 10 | 2 HIGH, 3 MEDIUM, 5 LOW | None (all in hooks/ -- new component) | 24 |
| 9 | 5 | 1 MEDIUM, 4 LOW | None (doc drift + design items) | 2 |

Run 9 continues the convergence pattern. Zero code bugs found in any module. All 5 findings are documentation drift and design documentation gaps. The scripts/ and hooks/ layers remain clean across all analytical lenses.

## Recommendations

1. **Automate README metrics** -- Consider a CI step or pre-commit hook that validates test count and line count against README.md. First appearance.

2. **pytest-cov** -- Coverage reporting would detect untested paths. Currently not installed. Second appearance (also in run 8).

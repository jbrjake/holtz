# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 6
**Date:** 2026-03-22
**Duration:** Phases 0-6 complete

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 226 | 232 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 0.37s | 0.35s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Punchlist items | -- | 8 |
| Resolved | -- | 8 |
| Open | -- | 0 |
| Deferred | -- | 0 |

**Net new tests:** 6

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 1 | BH-003 |
| LOW | 7 | BH-001, BH-002, BH-004, BH-005, BH-006, BH-007, BH-008 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| doc/drift | 3 | BH-001, BH-002, BH-003 |
| design/dead-code | 1 | BH-004 |
| design/duplication | 1 | BH-005 |
| test/missing | 2 | BH-006, BH-007 |
| bug/logic | 1 | BH-008 |

## Pattern: PAT-001 — Duplicated fence-parsing logic

BH-005 and BH-006 share a root cause: `mask_code_fences` and `has_unclosed_fence` independently implemented the same CommonMark fence state machine. The duplication meant test coverage for one function didn't protect the other.

**Fix:** Extracted `_iterate_fences()` generator. Both functions now consume it. Single state machine, two consumers.

## Key Fixes

1. **BH-003 (MEDIUM):** README Phase 1 incorrectly listed `shares_pattern` as a Phase 1 edge type. Per SKILL.md, `shares_pattern` belongs to Phase 5 (Pattern Analysis). Removed from Phase 1 description.

2. **BH-005 (LOW):** Extracted shared `_iterate_fences()` generator from the duplicated fence state machines in `mask_code_fences` and `has_unclosed_fence`. Both now consume the same iterator.

3. **BH-008 (LOW):** Vitest output parser used order-dependent regex unlike the already-fixed Jest parser. Refactored to use independent `re.search` calls per component, matching the Jest pattern.

4. **BH-004 (LOW):** Removed dead `if not masked_content:` guard block from `validate()`. The second guard was unreachable because the first identical guard already computed the value.

5. **BH-001 (LOW):** Added `## Patterns` section check to validator, aligning with punchlist-format.md's File Structure spec.

6. **BH-002 (LOW):** Fixed README "8 reference docs" to "9 reference docs".

7. **BH-006, BH-007 (LOW):** Added 4 missing tests: unclosed tilde fence, closed tilde fence, CRLF unclosed fence, and drift_check with line=None.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 1         | 50%      |
| MEDIUM     | 3         | 2         | 67%      |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **6**     | **3**     | **50%**  |

- Prediction 1 (HIGH, SKILL.md drift): UNCONFIRMED — SKILL.md-to-scripts alignment was solid
- Prediction 2 (HIGH, dead guard block): CONFIRMED → BH-004
- Prediction 3 (MEDIUM, dual fence logic): CONFIRMED → BH-005
- Prediction 4 (MEDIUM, reference doc drift): CONFIRMED → BH-001
- Prediction 5 (MEDIUM, README drift): CONFIRMED → BH-002, BH-003
- Prediction 6 (LOW, untested fallback path): UNCONFIRMED — the dead guard block was the real issue, not an untested path

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 1 | 12 | 2 HIGH, 6 MEDIUM, 4 LOW | PAT-001: code-fence-unaware parsing | 48 |
| 2 | 5 | 2 MEDIUM, 3 LOW | PAT-002: incomplete code-fence isolation | 10 |
| 3 | 3 | 3 LOW | None (all distinct) | 2 |
| 4 | 4 | 2 MEDIUM, 2 LOW | PAT-001: structural-awareness divergence | 4 |
| 5 | 9 | 3 MEDIUM, 6 LOW | None | 2 |
| 6 | 8 | 1 MEDIUM, 7 LOW | PAT-001: duplicated fence-parsing logic | 6 |

Run 6 continues the trend of finding fewer high-severity issues. The single MEDIUM was a documentation error (README), not a code bug. All 7 LOW items were code quality improvements (dead code, duplication, missing tests, parser inconsistency). The codebase's defense-in-depth has matured: prior runs hardened the parsing logic, this run hardened the infrastructure around it.

## Recommendations

1. **Coverage reporting** — No coverage tool is configured. Adding `pytest-cov` would make coverage gaps visible and help target future test additions.

2. **Test boilerplate reduction** — test_validate_punchlist.py has ~36 repetitions of the standard valid-item template. A `make_item(**overrides)` builder fixture would reduce this.

3. **CI configuration** — No CI/CD is configured. GitHub Actions with ruff + mypy + pytest would prevent regressions on push.

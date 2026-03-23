# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 10
**Date:** 2026-03-22
**Duration:** Phases 0-6 complete (with Justine merge mid-run)

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 261 | 265 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 0.89s | 0.92s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Mypy files | 9 | 9 |
| Coverage | — | 66% |
| Punchlist items | — | 9 |
| Resolved | — | 9 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 4 (save_history round-trip x2, vitest all-skipped, BJ-prefix count)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 7 | BH-002, BH-003, BH-005, BH-006, BH-007, BH-008, BH-009 |
| LOW | 2 | BH-001, BH-004 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| bug/logic | 3 | BH-003 (BJ- prefix), BH-005 (vitest), BH-006 (Go parser) |
| design/inconsistency | 2 | BH-002 (pytest-cov), BH-008 (staleness bypass doc), BH-009 (gate scope doc) |
| doc/drift | 1 | BH-001 (README line count) |
| test/missing | 1 | BH-007 (save_history round-trip) |
| bug/error-handling | 1 | BH-004 (os.rename -> os.replace) |

## Key Fixes

1. **BH-001 (LOW):** Updated README line count 8,026 -> 8,118. Self-referential drift from run 9's own fixes.

2. **BH-002 (MEDIUM):** Installed pytest-cov, configured coverage in pyproject.toml and CI. Escalated after appearing in runs 8 and 9.

3. **BH-003 (MEDIUM):** Changed punchlist parser regex from `BH-\d+` to `B[HJ]-\d+` in both validate_punchlist.py and convergence_check.py. Justine's BJ- namespace was invisible to the tool chain.

4. **BH-004 (LOW):** Replaced `os.rename` with `os.replace` in impact_graph.py and convergence_check.py for Windows compatibility.

5. **BH-005 (MEDIUM):** Added `skipped` to vitest parser regex, allowing all-skipped runs to parse correctly instead of returning None.

6. **BH-006 (MEDIUM):** Documented Go parser limitation: test functions printing fake `--- PASS:` lines can inflate counts.

7. **BH-007 (MEDIUM):** Added save_history round-trip test and overwrite test.

8. **BH-008 (MEDIUM):** Documented STATUS.md deletion bypass as known limitation.

9. **BH-009 (MEDIUM):** Documented impact_graph_gate narrow scope as known limitation.

## Justine Merge

Justine found 10 items. After verification:
- 0 agreements (Holtz found different items this run)
- 2 Holtz-only items (BH-001, BH-002)
- 7 Justine-only verified items (BH-003 through BH-009)
- 1 already deferred design choice (BH-101: empty types=[] semantics, same as run 8)
- 1 theoretical false positive (BH-103: TOML string value containing bracket text)
- 1 already addressed (BH-107: subagent fence masking, same as run 8 BH-009)

Justine found the real bugs this run. Her BJ- prefix finding (BH-110 -> BH-003) was the most significant: the tools that validate Justine's work could not parse her output. Her Vitest and Go parser findings (BH-108/BH-109) caught genuine edge cases.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 2         | 100%     |
| MEDIUM     | 0         | 0         | --       |
| LOW        | 0         | 0         | --       |
| **Total**  | **2**     | **2**     | **100%** |

Predictions only covered doc drift and escalation. Justine's 7 code-level findings were not predicted.

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 1 | 12 | 2 HIGH, 6 MEDIUM, 4 LOW | PAT-001 | 48 |
| 2 | 5 | 2 MEDIUM, 3 LOW | PAT-002 | 10 |
| 3 | 3 | 3 LOW | None | 2 |
| 4 | 4 | 2 MEDIUM, 2 LOW | PAT-001 | 4 |
| 5 | 9 | 3 MEDIUM, 6 LOW | None | 2 |
| 6 | 8 | 1 MEDIUM, 7 LOW | PAT-001 | 6 |
| 7 | 2 | 2 MEDIUM | None | 3 |
| 8 | 10 | 2 HIGH, 3 MEDIUM, 5 LOW | None | 24 |
| 9 | 5 | 1 MEDIUM, 4 LOW | None | 2 |
| 10 | 9 | 7 MEDIUM, 2 LOW | None | 4 |

Run 10 found more items than expected because Justine's adversarial depth-first scan caught edge cases that both Holtz and prior Justine runs missed: the BJ- prefix invisibility, the Vitest all-skipped gap, and the Go parser inflation vulnerability. These are real bugs, not documentation drift. The scripts layer is NOT as clean as runs 7-9 suggested -- it had untested edge cases hiding in the test runner parsers and a namespace contract violation in the punchlist parsers.

## Recommendations

1. **Automate README metrics** -- test count and line count drift on every change. Second appearance (also in run 9). Will be escalated in run 11 if unaddressed.

# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 8
**Date:** 2026-03-22
**Duration:** Phases 0-6 complete

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 235 | 259 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 0.26s | 0.85s |
| Ruff errors | 7 | 0 |
| Mypy errors | 0 | 0 |
| Mypy files | 4 | 9 |
| Punchlist items | — | 10 |
| Resolved | — | 10 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 24 (all hook tests)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| HIGH | 2 | BH-001, BH-006 |
| MEDIUM | 3 | BH-002, BH-003, BH-007 |
| LOW | 5 | BH-004, BH-005, BH-008, BH-009, BH-010 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| bug/logic | 3 | BH-004, BH-007, BH-008 (in hooks/) |
| bug/error-handling | 1 | BH-001 (pyproject.toml) |
| design/inconsistency | 4 | BH-002, BH-003, BH-009, BH-010 |
| test/missing | 1 | BH-006 (hooks/) |
| doc/drift | 1 | BH-005 (README) |

## Key Fixes

1. **BH-001 (HIGH):** Removed broken pytest-cov addopts from pyproject.toml. The dependency was configured in run 7 but never installed, making default `pytest` unusable. Default pytest now runs clean.

2. **BH-006 (HIGH):** Created `tests/test_hooks.py` with 24 tests covering all 5 hook modules. Tests verify exit codes, edge cases, and the fixes from BH-004/BH-007/BH-008. Hooks now have comprehensive test coverage.

3. **BH-002 (MEDIUM):** Created `.github/workflows/ci.yml` with ruff, mypy, and pytest. This recommendation appeared in 2 consecutive run summaries without being addressed.

4. **BH-003 (MEDIUM):** Fixed 7 ruff errors in hooks/ (4 import ordering, 2 ternary, 1 dead code). Added hooks/ to ruff src config.

5. **BH-007 (MEDIUM):** Replaced substring check `"impact_graph.py" not in command` with regex `r'(?:^|[\s/])impact_graph\.py\b'` to prevent false positives on test filenames.

6. **BH-004 (LOW):** Added shell variable detection — `--graph "$VAR"` paths are skipped instead of checked literally.

7. **BH-005 (LOW):** Updated README inventory from "12 reference docs" to "13 reference docs".

8. **BH-008 (LOW):** Tightened STATUS.md exemption from `endswith("STATUS.md")` to explicit path match for protocol STATUS.md files.

9. **BH-009 (LOW):** Documented subagent_findings_check false-positive risk as acceptable (warn-only hook).

10. **BH-010 (LOW):** Added hooks/ to mypy files list and ruff src config. mypy now covers 9 source files (up from 4).

## Justine Merge

Justine found 12 items. After verification:
- 3 agreements (BH-001/107, BH-003/106, BH-006/102)
- 4 Holtz-only items (BH-002, BH-004, BH-005, BH-007)
- 3 Justine-only verified items (BH-008/104, BH-009/105, BH-010/109)
- 1 Justine FALSE POSITIVE (BH-101: claimed impact_graph_gate gates unused path, but SKILL.md line 164 specifies audit/)
- 3 folded into existing items
- 1 deferred design choice (BH-111: empty types=[] semantics)

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 3         | 100%     |
| MEDIUM     | 3         | 1         | 33%      |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **7**     | **4**     | **57%**  |

- Prediction 1 (HIGH, hook logic bugs): CONFIRMED — BH-004, BH-007
- Prediction 2 (MEDIUM, subagent regex): UNCONFIRMED — regex is adequate
- Prediction 3 (MEDIUM, _common.py error handling): CONFIRMED — design issue documented
- Prediction 4 (HIGH, get_test_counts + pytest-cov): CONFIRMED — resolved transitively by BH-001
- Prediction 5 (HIGH, dead code stdout): CONFIRMED — fixed as part of BH-003
- Prediction 6 (MEDIUM, staleness false positive): UNCONFIRMED
- Prediction 7 (LOW, hooks.json config): UNCONFIRMED

HIGH-confidence predictions were 100% accurate. The prediction model correctly identified hooks/ as the primary risk area.

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
| 8 | 10 | 2 HIGH, 3 MEDIUM, 5 LOW | None (all in hooks/ — new component) | 24 |

Run 8 found more items than runs 3-7 because hooks/ was added between runs 7 and 8 without test coverage, linting, or type checking. The scripts/ layer (the focus of runs 1-7) produced zero new findings. The trajectory shows that the original codebase remains hardened; the new findings came entirely from new, untested code.

## Recommendations

1. **Consider pytest-cov reinstallation** — Coverage reporting was useful in run 7 but removed in run 8 to fix the broken dependency. If coverage is desired, install pytest-cov and restore the addopts. The current CI workflow does not include coverage.

2. **Hook testing discipline** — All future hooks should be accompanied by tests. The pattern from BH-006 (zero test coverage for an entire subsystem) should not recur. The CI workflow will catch lint and type errors but not missing tests.

# Holtz Summary

**Project:** holtz
**Run:** 12
**Date:** 2026-03-23
**Duration:** Phases 0-6 complete (with Justine merge)

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 286 | 295 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 2.21s | 2.31s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Mypy files | 9 | 9 |
| Coverage | 66% | 66% |
| Punchlist items | — | 6 |
| Resolved | — | 6 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 9 (3 malformed graph entry tests, 2 PUNCHLIST-MERGED gate tests, 2 Justine PUNCHLIST gate tests, 2 STATUS.md-deleted-mid-run tests)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 4 | BH-003, BH-004, BH-005, BH-006 |
| LOW | 2 | BH-001, BH-002 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| test/missing | 3 | BH-004, BH-005, BH-006 |
| doc/drift | 2 | BH-001, BH-002 |
| bug/error-handling | 1 | BH-003 |

## Key Fixes

1. **BH-001 (LOW):** Updated README "What's inside" — "2 skills" → "1 skill", test count 286 → 295, line count 8,200 → 7,800. Updated test regex to handle singular/plural forms.

2. **BH-002 (LOW):** Updated subagent_findings_check.py docstring — removed legacy "exit 1"/"exit 2" references, replaced with modern JSON output format description.

3. **BH-003 (MEDIUM):** Added per-entry validation to `ImpactGraph.load()`. Malformed edges (missing source/target/type) and malformed nodes (missing type/file) are now filtered during load instead of crashing downstream methods. Added `_REQUIRED_EDGE_KEYS` and `_REQUIRED_NODE_KEYS` class constants.

4. **BH-004 (MEDIUM):** Added tests for PUNCHLIST-MERGED.md gate path in impact_graph_gate — both block (graph missing) and allow (graph exists).

5. **BH-005 (MEDIUM):** Added tests for STATUS.md-deleted-mid-run detection — block when recon/ exists, block when PUNCHLIST.md exists.

6. **BH-006 (MEDIUM):** Added tests for Justine PUNCHLIST.md gate path — block (Justine graph missing) and allow (Justine graph exists).

## Justine Merge

Justine found 3 items. After verification:
- 0 agreements (no matching file + category + location pairs)
- 3 Holtz-only items (BH-001, BH-002, BH-003)
- 3 Justine-only items (BH-004, BH-005, BH-006)

Holtz found the code bug (BH-003: malformed graph entries) and doc drift (BH-001, BH-002). Justine found three untested hook code paths (BH-004, BH-005, BH-006). Zero overlap. Same blind spot pattern as run 11: Holtz drills into code logic, Justine checks coverage completeness.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 1         | 1         | 100%     |
| MEDIUM     | 3         | 1         | 33%      |
| LOW        | 1         | 0.5       | 50%      |
| **Total**  | **5**     | **2.5**   | **50%**  |

- Prediction 1 (HIGH, README drift): CONFIRMED via BH-001
- Prediction 2 (MEDIUM, exit_block design): UNCONFIRMED — current code is correct
- Prediction 3 (MEDIUM, read_event empty): UNCONFIRMED — behavior is correct, tests exist
- Prediction 4 (MEDIUM, graph malformed entries): CONFIRMED via BH-003
- Prediction 5 (LOW, hook test shallow): PARTIALLY CONFIRMED — tests verify gate logic, not just format, but Justine found 3 untested branches

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
| 11 | 13 | 5 MEDIUM, 8 LOW | PAT-003 | 4 |
| 12 | 6 | 4 MEDIUM, 2 LOW | None | 9 |

Run 12 found fewer items than run 11 (6 vs 13). The hook modernization (the main code change) introduced one code bug (BH-003, missing validation in load()) and one stale docstring (BH-002). The remaining 4 items were coverage gaps — untested code paths that existed before the modernization but were first identified by Justine's breadth-first methodology. No new patterns emerged — the 6 items span 3 categories with no shared root cause.

## Additional Finding: Hook Errors from Giles

During the session, the user reported persistent "PreToolUse:Bash hook error" and "PostToolUse:Bash hook error" messages. Investigation traced these to the **Giles** plugin (`giles@jbrjake` v0.7.2), not Holtz. Both `review_gate.py` and `commit_gate.py` in Giles crash with `ModuleNotFoundError: No module named 'hooks'` — they use `from hooks._common import ...` but the Python path doesn't include their parent directory when invoked via the plugin root. Holtz hooks are working correctly with the JSON format modernization.

## Recommendations

1. **Fix Giles hooks** — the `ModuleNotFoundError` in review_gate.py and commit_gate.py fires on every Bash tool call, producing misleading error labels.

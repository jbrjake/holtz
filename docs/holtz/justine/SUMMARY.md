# Justine Audit Summary

**Project:** holtz
**Date:** 2026-03-22
**Auditor:** Justine (breadth-first, parallel dispatch)
**Baseline:** 261 tests passing, 0 failing, 0 skipped (0.97s)
**Post-Audit:** 261 tests passing, 0 failing, 0 skipped (no changes made)

## Results

| Metric | Count |
|--------|-------|
| Total findings | 10 |
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 4 |
| LOW | 2 |
| Open | 10 |
| Resolved | 0 |
| Deferred | 0 |
| Patterns identified | 0 |

## Findings by Category

| Category | Count |
|----------|-------|
| bug/logic | 7 |
| bug/error-handling | 1 |
| bug/security | 1 |
| test/missing | 1 |

## HIGH Findings

1. **BH-104: status_staleness_gate allows bypass when STATUS.md deleted mid-run** -- The staleness enforcement hook cannot distinguish "first write" from "STATUS.md was deleted." Any deletion of STATUS.md mid-run disables staleness checking entirely.

2. **BH-105: impact_graph_gate only gates audit/ subdirectory** -- The impact graph enforcement hook only checks writes to `docs/holtz/audit/` but not to `PUNCHLIST.md`, `investigations/`, or other Phase 1+ output files. The enforcement boundary is narrower than the documented requirement.

3. **BH-109: Go test parser susceptible to injected output** -- The Go verbose parser uses regex against raw stdout. A Go test that prints fake `--- PASS:` lines in its output would inflate the passed count. No test covers this scenario.

4. **BH-110: Punchlist validator hardcoded to BH- prefix** -- Both parsers (validate_punchlist and convergence_check) are hardcoded to `BH-` prefix. Justine's documented `BJ-` namespace is invisible to the tool chain. Architecture baseline says BJ- is valid; tools disagree.

## MEDIUM Findings

1. **BH-101: Empty types list treated as no filter** -- `types=[]` in neighbors/blast_radius is falsy, maps to "no filter" (returns everything). Semantically, empty list should mean "match nothing."

2. **BH-103: detect_test_runner TOML parsing is regex-based** -- TOML values that look like section headers can cause false positive runner detection.

3. **BH-106: No save_history round-trip test** -- Atomic write correctness in convergence_check is untested. No test calls save_history then load_history to verify the round-trip.

4. **BH-108: Vitest parser returns None for all-skipped output** -- The regex requires "passed" or "failed" in the summary line. A Vitest run where all tests are skipped returns None instead of `{passed:0, failed:0, skipped:N}`.

## LOW Findings

1. **BH-102: os.rename not atomic on Windows** -- Both save functions use `os.rename` which fails on Windows when target exists. `os.replace()` is the correct cross-platform function.

2. **BH-107: subagent_findings_check matches paths in code fences** -- Documented trade-off. Hook warns on paths inside code examples. Already mitigated by using exit(1) not exit(2).

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 1         | 0         | 0%       |
| MEDIUM     | 4         | 2         | 50%      |
| LOW        | 1         | 1         | 100%     |
| **Total**  | **6**     | **3**     | **50%**  |

Notes: Prediction 1 (Rubber Stamp) was UNCONFIRMED -- the boolean-only storage is by design, not a test deficiency. Prediction 6 (_section_from_original off-by-one) was UNCONFIRMED -- the function has been heavily tested across 9 prior runs. Predictions 3 and 5 were PARTIALLY CONFIRMED -- the hooks have enforcement gaps but different from the specific edge cases predicted.

## Recommendations

1. **Unify item ID prefix support across tools.** The validator and convergence checker should accept both BH- and BJ- prefixed items. This is a one-line regex change in two files but blocks Justine's standard workflow.

2. **Widen hook enforcement boundaries.** The impact graph gate should cover all Phase 1+ output files, not just the audit/ subdirectory. The staleness gate should detect deleted STATUS.md when other run files exist.

3. **Add os.replace for cross-platform atomic writes.** Both save functions should use `os.replace()` instead of `os.rename()`. One-line change, no behavior change on POSIX.

4. **Add edge case tests for test runner parsers.** The all-skipped scenario for Vitest and the injected-output scenario for Go are untested. These are realistic edge cases that return wrong results silently.

5. **Add save_history round-trip test.** Atomic write correctness should be verified with a save-then-load test.

## Blind Spot Analysis

Justine's breadth-first scan found enforcement gaps (BH-104, BH-105) and cross-module contract violations (BH-110) that depth-first analysis might miss because they span module boundaries. The hook enforcement findings are the kind of bug that survives in plain sight -- the code works correctly in isolation, but the enforcement boundary doesn't match the documented requirement.

Justine's scan was less thorough on the validate_punchlist.py internals, where 9 prior runs have already excavated deep bugs in `_section_from_original` and fence state handling. Holtz's depth-first approach is better suited for finding new issues in that well-trodden code.

## Impact Graph

Justine's graph: `docs/holtz/justine/impact-graph.json` -- 9 nodes, 9 edges (6 imports, 3 assumes). Key semantic edges:
- `convergence_check` assumes `validate_punchlist` (BH- prefix alignment)
- `hooks.status_staleness_gate` assumes (STATUS.md absence = first write)
- `hooks.impact_graph_gate` assumes (audit/ = only Phase 1+ path)

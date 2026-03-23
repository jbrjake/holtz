# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 11
**Date:** 2026-03-22
**Duration:** Phases 0-6 complete (with Justine merge)

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 265 | 269 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 1.29s | 1.78s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Mypy files | 9 | 9 |
| Coverage | 67% | 66% |
| Punchlist items | — | 13 |
| Resolved | — | 13 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 4 (NaN rejection, inf rejection, negative --top, README metrics check)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 5 | BH-001, BH-006, BH-008, BH-009, BH-010 |
| LOW | 8 | BH-002, BH-003, BH-004, BH-005, BH-007, BH-011, BH-012, BH-013 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| design/inconsistency | 7 | BH-001, BH-004, BH-008, BH-009, BH-010, BH-011, BH-012, BH-013 |
| bug/logic | 3 | BH-003, BH-006, BH-007 |
| doc/drift | 1 | BH-002 |
| bug/error-handling | 1 | BH-005 |

## Key Fixes

1. **BH-001 (MEDIUM):** Added test_readme_metrics_match_actual() to test_integration.py. Test count is now automated.

2. **BH-002 (LOW):** Updated README "13 reference docs" to "14 reference docs".

3. **BH-003 (LOW):** Fixed artifact_verification.py \s+ to [ \t]+ in --graph regex.

4. **BH-004 (LOW):** Added comment documenting ordering dependency in impact_graph_gate.py if/elif chain.

5. **BH-005 (LOW):** Wrapped os.path.getmtime in try/except OSError in status_staleness_gate.py.

6. **BH-006 (MEDIUM):** Added math.isfinite() guard to update_risk(). NaN/inf deltas now return error dict.

7. **BH-007 (LOW):** Clamped risk_hotspots top to max(0, top) to prevent negative slice.

8. **BH-008 (MEDIUM):** Widened impact_graph_gate to also gate PUNCHLIST.md and PUNCHLIST-MERGED.md writes.

9. **BH-009 (MEDIUM):** Replaced \s with [ \t] in Jest, Vitest, and Cargo parser regexes.

10. **BH-010 (MEDIUM):** Added sibling artifact detection to status_staleness_gate. Deleting STATUS.md mid-run now detected and blocked.

11. **BH-011 (LOW):** Fixed \s+ to [ \t]+ in artifact_verification.py.

12. **BH-012 (LOW):** Added comment documenting dict ordering as priority in detect_test_runner.

13. **BH-013 (LOW):** Replaced \s with [ \t] in all 9 ENTITY_PATTERNS regexes.

## Justine Merge

Justine found 8 items. After verification:
- 0 agreements (no matching file + category + location pairs)
- 7 Holtz-only items (BH-001 through BH-007)
- 6 Justine-only items (BH-008 through BH-013)
- 1 already fixed (BJ-006: Vitest all-skipped — test exists from run 10)

Justine identified the regex convention violation pattern (PAT-003) with 3 instances. Holtz missed all 3 convention violations. Holtz found the NaN edge case and negative --top CLI bug. Different methodologies, different findings, zero overlap.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 1         | 1         | 100%     |
| MEDIUM     | 2         | 2         | 100%     |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **4**     | **3**     | **75%**  |

- Prediction 1 (HIGH, README drift): CONFIRMED via BH-002
- Prediction 2 (MEDIUM, hook bugs): CONFIRMED via BH-003, BH-004, BH-005
- Prediction 3 (MEDIUM, impact_graph CLI): CONFIRMED via BH-006, BH-007
- Prediction 4 (LOW, convergence_check edge cases): UNCONFIRMED — no bugs found in those lines

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

Run 11 found more items than run 10 because Justine surfaced a new pattern class (PAT-003: regex convention violations with 3 instances) that previous runs missed. The \s-vs-[ \t] convention was established early but never enforced. Once Justine ran the detection heuristic globally, the violations became visible. Additionally, Holtz found the NaN edge case in update_risk() which survived 10 prior audits because the Python min/max behavior with NaN is non-obvious (it silently clamps rather than propagating, unlike most languages).

## Recommendations

1. **Add \s convention check to CI** -- A grep-based check preventing re-introduction of \s in source files would close this pattern permanently.

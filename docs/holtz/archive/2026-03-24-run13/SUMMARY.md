# Holtz Summary

**Project:** holtz
**Run:** 13 (targeted delta audit)
**Date:** 2026-03-23
**Duration:** Phases 0-6 complete (no Justine — targeted mode)

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 320 | 321 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 2.57s | 2.56s |
| Ruff errors | 4 | 0 |
| Mypy errors | 0 | 0 |
| Mypy files | 16 | 16 |
| Coverage | 67% | 67% |
| Punchlist items | — | 4 |
| Resolved | — | 4 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 1 (render_items offset verification with code fences)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 2 | BH-001, BH-004 |
| LOW | 2 | BH-002, BH-003 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| bug/logic | 2 | BH-001, BH-003 |
| doc/drift | 2 | BH-002, BH-004 |

## Key Fixes

1. **BH-001 (MEDIUM, bug/logic):** `render_items()` used masked character offsets to index original content. Since `mask_code_fences` replaces fenced lines with empty strings, character offsets diverge — items after code fences were extracted from wrong positions. Fixed by adding line-number-based offset mapping (same approach `parse_punchlist` already uses). Added test with 3-item punchlist verifying correct extraction after code fences.

2. **BH-002 (LOW, doc/drift):** README "What's inside" counts stale — 15→17 reference docs, 320→321 tests, 7,800→8,500 lines.

3. **BH-003 (LOW, bug/logic):** 4 ruff lint errors in new test file `test_pattern_brief_compact.py` — unsorted import and ambiguous variable names `l`. Fixed: added noqa for import order, renamed `l` to `line`.

4. **BH-004 (MEDIUM, doc/drift):** Filter commands in SKILL.md (2 locations) and justine-skill.md (2 locations) used `--filter-status OPEN "IN PROGRESS" --resolved-before 3` without RESOLVED in the status list. Since `filter_items()` applies status filter before recency filter, all RESOLVED items were excluded — the `--resolved-before` flag had no effect. Fixed by adding RESOLVED to all 4 instances.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 3         | 100%     |
| MEDIUM     | 1         | 1         | 100%     |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **5**     | **4**     | **80%**  |

- Prediction 1 (HIGH, render_items offset): CONFIRMED via BH-001
- Prediction 2 (HIGH, README counts): CONFIRMED via BH-002
- Prediction 3 (HIGH, ruff lint): CONFIRMED via BH-003
- Prediction 4 (MEDIUM, render_items test gap): CONFIRMED — existing tests only exercised first-item rendering
- Prediction 5 (LOW, compact brief guard): UNCONFIRMED — script exits cleanly with exit 0 and empty stdout

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 12 | 6 | 4 MEDIUM, 2 LOW | None | 9 |
| 13 | 4 | 2 MEDIUM, 2 LOW | None | 1 |

Run 13 is a targeted delta audit (24 commits since run 12). Findings dropped from 6 to 4. The most significant find was BH-001 — a real bug in new code where `render_items` used masked character offsets to index original content, causing content bleed from adjacent items. This is related to PAT-003 (code-fence-unaware parsing) — the same root cause family that has appeared in runs 1, 2, 4, and 6. BH-004 was a semantic bug where filter commands omitted RESOLVED from the status filter, making the `--resolved-before` flag silently ineffective.

## Recommendations

1. **README maintenance:** Consider an integration test or hook that checks README counts match reality (partially exists — `test_readme_metrics_match_actual` checks test count but not reference doc count or line count).

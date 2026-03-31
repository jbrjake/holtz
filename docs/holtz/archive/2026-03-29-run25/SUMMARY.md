# Run 25 Summary

**Project:** holtz v0.57.19
**Auditor:** holtz
**Date:** 2026-03-29
**State:** Finalized (109 events)
**Perspectives:** 13/13 complete

## Findings

**Total:** 17 (1 HIGH, 12 MEDIUM, 3 LOW + 1 badge URL fix)
**All resolved.**

### New findings this session (2)

1. **BH-017 (MEDIUM, bug/logic):** `ImpactGraph.risk_hotspots()` sort key uses `n["id"]` but `_REQUIRED_NODE_KEYS` was `{type, file}` — load() allowed nodes without `id`, creating a KeyError path. Fix: added `"id"` to `_REQUIRED_NODE_KEYS`. Blast radius: quiz-bank question updated.

2. **BH-018 (MEDIUM, bug/logic):** `parse_status_text()` hardcoded `current_perspective="unknown"` — never extracted the active lens from status text. Downstream: `primer.py` lens priming line was never emitted after `/clear`. Fix: parse bracket content to find first non-✓ member.

### Prior findings (15)

All resolved in earlier iterations. Categories: 5 doc/drift, 5 bug/logic, 3 test quality, 1 bug/state, 1 design/coupling.

## Commits

| Hash | Description |
|------|-------------|
| baeaeab | fix(scripts): add 'id' to ImpactGraph._REQUIRED_NODE_KEYS (BH-017) |
| 12cc6f6 | fix(enforcement): extract current_perspective from sahjhan status output (BH-018) |
| 33ba2db | fix(enforcement): update quiz-bank entry for _REQUIRED_NODE_KEYS (BH-017) |
| b3d79c6 | fix(docs): update badge URL to match 774 test count (PAT-005) |

## Metrics

- **Tests:** 774 passed
- **Coverage:** 60%
- **Linter:** ruff clean
- **Type checker:** mypy clean (21 source files)

## Prediction Accuracy

N/A — this was a convergence continuation session, not a fresh audit run. No new predictions were made.

## Pattern Notes

- PAT-005 (stale README metrics) recurred again via badge URL. The integration test catches alt text but not URL encoding — a detection gap.
- BH-017 represents a new pattern candidate: "defensive filter gap" — validation at load time doesn't enforce all invariants needed by downstream methods.
- BH-018 represents "incomplete parser output" — parser extracts some fields but leaves sentinel defaults that silently disable features.

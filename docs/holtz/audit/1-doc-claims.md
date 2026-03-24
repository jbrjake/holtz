# Phase 1: Doc-to-Implementation Audit

**Run 14 — 2026-03-24**

## README "What's inside" Verification (Prediction 4 — HIGH)

| Claim | README | Actual | Status |
|-------|--------|--------|--------|
| Skills | 1 | 1 | VERIFIED |
| Agents | 3 | 3 | VERIFIED |
| Reference docs | 17 | 17 | VERIFIED |
| Examples | 1 | 1 | VERIFIED |
| Python scripts | 5 | 5 | VERIFIED |
| Seed patterns | 6 | 6 | VERIFIED |
| Enforcement hooks | 4 | 4 | VERIFIED |
| Tests | 321 | 321 | VERIFIED |
| Lines | 8,500 | 8,545 | VERIFIED (rounded) |

**Result:** All counts match. Prediction 4 UNCONFIRMED — the README was updated in commit 30f4dfc and counts are currently correct. However, BH-001 remains valid: the test only validates test count (1 of 9 fields).

## Architecture Baseline Invariants

| Invariant | Status |
|-----------|--------|
| Field extraction uses masked boundaries, original extraction | VERIFIED |
| mask_code_fences preserves line count | VERIFIED |
| count_items and parse_punchlist split on B[HJ]-NNN headers in masked | VERIFIED (note: baseline says "BH-NNN" but code supports both BH and BJ namespaces) |
| save_history and ImpactGraph.save use atomic writes | VERIFIED |
| Test runner parsers return None for unparseable output | VERIFIED (14 return-None paths checked) |

## Other README Claims

| Claim | Status |
|-------|--------|
| 7 edge types: imports, calls, tests, assumes, diverges_from, shares_pattern, co_fixed | VERIFIED (graph currently has 5 of 7; shares_pattern and co_fixed are Phase 4/5 only) |
| Risk score 0.0-1.0 | VERIFIED (clamped at line 236: `max(0.0, min(1.0, new_score))`) |
| 9 analytical lenses | VERIFIED (lens-registry.md has 9) |
| Drift detection at 10-line threshold | VERIFIED (DRIFT_LINE_THRESHOLD in impact_graph.py) |

## New Findings

No new punchlist items from Phase 1. Escalated items BH-001 (README metrics test) and BH-002 (\s convention check) cover the relevant doc drift.

## Minor Observations (not punchlist-worthy)

- Architecture baseline invariant #3 says "### BH-NNN:" but code uses "### B[HJ]-NNN:" — the baseline description is slightly stale but the invariant itself holds
- Edge type validation in impact_graph.py is permissive (any string accepted) — design choice, not a bug

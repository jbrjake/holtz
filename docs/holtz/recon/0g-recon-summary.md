# 0g: Recon Summary

**Run 17** — Full audit, dev mode (Holtz auditing its own codebase)

## Baseline
- 619 tests, 0 failures, 0 skips, 9.50s
- 62% coverage (60% required)
- Lint: 3 ruff errors in utility script (generate-changelog.py), core clean
- Mypy: clean (0 errors)
- CI: green (4/5 recent runs passed; 1 failure was fixed in next commit)

## Churn Hotspots
1. README.md (15 changes) — doc drift risk
2. SKILL.md (10 changes) — protocol accuracy risk
3. pattern_brief_compact.py (6 changes) — PAT-001 recurrence target
4. convergence_check.py (3 changes)
5. hooks/_common.py (3 changes)

## Graph State
- 52 nodes, 53 edges (18 imports, 6 calls, 14 assumes, 2 diverges_from, 13 tests)
- 0 nodes pruned (no deleted files)
- 2 line-shift drifts: convergence_check::check_convergence (280→296), convergence_check::save_history (247→260)
- Same drifts as Run 16 — graph nodes were never updated. No structural change.

## Architecture Drift
- No structural drift (dependencies, layering, boundaries, conventions all unchanged)
- Persistent line-shift drift in convergence_check.py from Run 15 fixes, not updated in graph

## Pattern Library
- All 6 global seed patterns scanned. No heuristic hits.
- Proactive check from living punchlist (code-fence-unaware regex): 3 grep hits, all false positives on inspection.

## Recommendation Escalation
- 0 items escalated. All previously recurring recommendations (README metrics, \s convention, coverage) have been addressed.
- "Consolidate fence masking" and "Add README semantic claim test" from Run 16 are at 1 appearance each (not yet eligible for escalation).

## Key Observations
1. **README run count stale:** Says "Fifteen runs" but 16 have completed. Same class as BH-002 (Run 16).
2. **README prediction accuracy overstated:** Claims HIGH at 72% but research data shows 65%. Claims "10 runs" but 11 exist.
3. **Ruff errors in generate-changelog.py:** 3 lint errors in new utility script not under core lint scope.
4. **CI test gap:** 619 local vs 573 CI (46 tests difference). 8 are conditional skips; the remaining 38 were added after the CI commit snapshot.
5. **Living punchlist stale:** Says "Audits Completed: 1" but Run 16 also completed.

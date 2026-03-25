# Step 0e: Git Churn Analysis

**Date:** 2026-03-24
**Scope:** Last 50 commits

## Top 20 Most-Changed Files
| Rank | Changes | File |
|------|---------|------|
| 1 | 10 | README.md |
| 2 | 6 | docs/runs/run-14.cast |
| 3 | 5 | skills/holtz/SKILL.md |
| 4 | 4 | docs/runs/extract-session-cast.py |
| 5 | 4 | .claude-plugin/plugin.json |
| 6 | 3 | docs/runs/run-14-walkthrough.md |
| 7 | 3 | docs/runs/generate-run14-cast.py |
| 8 | 3 | docs/holtz/SUMMARY.md |
| 9 | 3 | docs/holtz/STATUS.md |
| 10 | 3 | docs/holtz/recon/* (multiple recon files) |
| 11 | 3 | docs/holtz/PUNCHLIST.md |
| 12 | 3 | docs/holtz/impact-graph.json |
| 13 | 3 | docs/holtz/audit/1-doc-claims.md |
| 14 | 2 | tests/test_token_profiler_*.py (multiple) |
| 15 | 2 | skills/holtz/scripts/* |

## Analysis
- README.md is highest churn (10 changes in 50 commits) — frequent doc updates, risk of doc/code drift
- SKILL.md at 5 changes — active process evolution, risk of inconsistencies
- plugin.json at 4 — version bumps from automated hook
- Token profiler files are recent additions (2 changes each) — newly written code, less battle-tested
- Holtz runtime data (PUNCHLIST, STATUS, recon) appear because of audit runs

## High-Risk Indicators
- **SKILL.md** — high churn on process definition. Process gaps or contradictions likely.
- **README.md** — aspirational claims that may outpace implementation.
- **Token profiler** — new module (~8 files), added recently, moderate test coverage.

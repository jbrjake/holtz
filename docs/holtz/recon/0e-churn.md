# Step 0e: Churn Analysis

**Date:** 2026-03-24
**Run:** 15

## Top 20 Most-Changed Files (last 50 commits)
| Changes | File | Notes |
|---------|------|-------|
| 9 | README.md | Frequent doc updates |
| 6 | docs/runs/run-14.cast | Asciinema recording |
| 4 | skills/holtz/SKILL.md | Core skill definition |
| 4 | docs/runs/extract-session-cast.py | Utility script |
| 3 | docs/runs/run-14-walkthrough.md | Documentation |
| 3 | docs/runs/generate-run14-cast.py | Removed utility |
| 3 | .claude-plugin/plugin.json | Version bumps |
| 2 | tests/test_token_profiler_*.py (8 files) | Token profiler tests |
| 2 | tests/test_pattern_brief_compact.py | Pattern brief tests |
| 2 | skills/holtz/scripts/profiler_plugin.py | Profiler plugin |
| 2 | scripts/token_profiler/*.py (2 files) | Token profiler modules |
| 2 | scripts/session-to-cast.py | Utility script |

## Analysis
- README is highest churn — doc drift risk (verified in run 14, but claims may have drifted again)
- SKILL.md at 4 changes — the core protocol. Inconsistencies between SKILL.md and references/tests should be checked
- Token profiler modules are new (added then immediately refined)
- No high-churn source files in scripts/ — code has stabilized
- Hooks are all new (1 commit each) — high risk area for first-audit findings

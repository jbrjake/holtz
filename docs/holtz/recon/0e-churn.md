# 0e: Churn Analysis

Git churn: top 20 most-changed files in the last 50 commits.

| Changes | File |
|---------|------|
| 49 | (blank — format artifact) |
| 15 | README.md |
| 11 | .claude-plugin/plugin.json |
| 10 | skills/holtz/SKILL.md |
| 6 | skills/holtz/scripts/pattern_brief_compact.py |
| 5 | docs/runs/run-14.cast |
| 4 | tests/test_pattern_brief_compact.py |
| 4 | docs/holtz/SUMMARY.md |
| 4 | docs/holtz/STATUS.md |
| 4 | docs/holtz/PUNCHLIST.md |
| 4 | docs/holtz/impact-graph.json |
| 3 | tests/test_hooks.py |
| 3 | skills/holtz/scripts/convergence_check.py |
| 3 | skills/holtz/references/lens-registry.md |
| 3 | skills/holtz/references/justine-skill.md |
| 3 | hooks/_common.py |
| 3 | docs/runs/extract-session-cast.py |
| 3 | docs/holtz/recon/0h-predictions.md |
| 3 | docs/holtz/recon/0g-recon-summary.md |
| 3 | docs/holtz/recon/0f-skipped-tests.md |

## High-Churn Source Files
1. **README.md (15)** — documentation drift risk, frequently updated
2. **SKILL.md (10)** — protocol changes, high audit sensitivity
3. **pattern_brief_compact.py (6)** — PAT-001 recurrence target, multiple fixes
4. **convergence_check.py (3)** — core convergence logic
5. **hooks/_common.py (3)** — shared hook utilities

## Notes
- plugin.json churn is from auto-version-bumping (expected)
- Audit artifacts (STATUS/PUNCHLIST/SUMMARY) churn is expected from prior runs
- pattern_brief_compact.py has highest source churn — PAT-001 has hit it twice

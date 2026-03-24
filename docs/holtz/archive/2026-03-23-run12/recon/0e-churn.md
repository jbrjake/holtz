# Phase 0e: Churn Analysis

**Date:** 2026-03-23
**Scope:** Last 50 commits

## Top 20 Most-Changed Files

| Changes | File |
|---------|------|
| 15 | README.md |
| 11 | skills/justine/SKILL.md |
| 11 | skills/holtz/SKILL.md |
| 6 | agents/justine.md |
| 5 | tests/test_impact_graph.py |
| 5 | skills/holtz/scripts/validate_punchlist.py |
| 5 | skills/holtz/scripts/impact_graph.py |
| 5 | hooks/status_staleness_gate.py |
| 5 | hooks/impact_graph_gate.py |
| 5 | .claude-plugin/plugin.json |
| 4 | skills/holtz/scripts/convergence_check.py |
| 4 | skills/holtz/patterns/*.md (6 files, 4 each) |
| 4 | pyproject.toml |
| 4 | hooks/artifact_verification.py |
| 3 | tests/test_validate_punchlist.py |
| 3 | tests/test_hooks.py |
| 3 | tests/test_integration.py |

## Notes

- README is highest churn (15) — documentation-heavy project, frequent doc drift
- Hook files (status_staleness_gate, impact_graph_gate, artifact_verification) at 4-5 changes each — recent modernization
- Core scripts (validate_punchlist, impact_graph, convergence_check) at 4-5 — stabilizing
- test_hooks.py at 3 changes — growing alongside hook modernization

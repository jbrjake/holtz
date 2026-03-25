# 0c: Test Baseline

**Run:** `python -m pytest --tb=short -q`
**Duration:** 9.50s
**Results:** 619 passed, 0 failed, 0 skipped

## Coverage

| Module | Stmts | Miss | Cover |
|--------|-------|------|-------|
| hooks/_common.py | 56 | 56 | 0% |
| hooks/artifact_verification.py | 29 | 29 | 0% |
| hooks/convergence_gate.py | 58 | 58 | 0% |
| hooks/convergence_primer.py | 39 | 39 | 0% |
| hooks/impact_graph_gate.py | 27 | 27 | 0% |
| hooks/status_staleness_gate.py | 39 | 39 | 0% |
| hooks/subagent_findings_check.py | 27 | 27 | 0% |
| scripts/convergence_check.py | 255 | 41 | 84% |
| scripts/impact_graph.py | 281 | 97 | 65% |
| scripts/markdown_utils.py | 46 | 0 | 100% |
| scripts/pattern_brief_compact.py | 85 | 18 | 79% |
| scripts/profiler_plugin.py | 42 | 0 | 100% |
| scripts/validate_punchlist.py | 316 | 63 | 80% |
| **TOTAL** | **1300** | **494** | **62%** |

Required coverage (60%) met.

## Notes
- Hooks show 0% because tested via subprocess, not direct import
- 619 passed, same as README badge claim

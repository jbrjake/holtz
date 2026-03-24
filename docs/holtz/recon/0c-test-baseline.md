# Step 0c: Test Baseline

**Tests passing:** 321
**Tests failing:** 0
**Tests skipped:** 0
**Test time:** 2.63s
**Coverage:** 67%

## Coverage by Module

| Module | Stmts | Miss | Cover | Notable Gaps |
|--------|-------|------|-------|-------------|
| hooks/_common.py | 24 | 24 | 0% | All lines uncovered (tested via subprocess in test_hooks.py) |
| hooks/artifact_verification.py | 29 | 29 | 0% | Tested via subprocess |
| hooks/impact_graph_gate.py | 27 | 27 | 0% | Tested via subprocess |
| hooks/status_staleness_gate.py | 39 | 39 | 0% | Tested via subprocess |
| hooks/subagent_findings_check.py | 27 | 27 | 0% | Tested via subprocess |
| convergence_check.py | 223 | 34 | 85% | Lines 272-277, 390-425 (CLI main, edge cases) |
| impact_graph.py | 281 | 97 | 65% | Lines 320-431 (CLI main, prune_missing, drift_check CLI) |
| markdown_utils.py | 46 | 0 | 100% | — |
| pattern_brief_compact.py | 80 | 18 | 78% | Lines 144-164 (CLI file read path) |
| validate_punchlist.py | 316 | 63 | 80% | Lines 504-580 (CLI main, filter/render) |

**Note:** Hooks show 0% coverage because they're tested via subprocess (test_hooks.py runs them as external processes). The coverage tool doesn't trace into subprocesses.

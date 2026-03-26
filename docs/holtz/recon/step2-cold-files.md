# Cold File Inventory — Run 20

## Previously Audited Files
| File | Punchlist Refs |
|------|---------------|
| skills/holtz/scripts/markdown_utils.py | run2 (2026-03-19), run2 (2026-03-20), run6 |
| skills/holtz/scripts/validate_punchlist.py | run2 (2026-03-19), run2 (2026-03-20), run3, run4, run5, run6, run9, run12, run13, run15, justine-run8 |
| skills/holtz/scripts/convergence_check.py | run2 (2026-03-19), run4, run5, run6, run9, run10, run11, run12, run15, run16, run18, justine-run11, justine-run22, justine-run14 |
| skills/holtz/scripts/impact_graph.py | justine-run11, run12, run11, justine-run8, run10, run17 |
| skills/holtz/scripts/pattern_brief_compact.py | run14, run16, justine-run14, justine-run16 |
| skills/holtz/scripts/profiler_plugin.py | run19 (SUMMARY: cold file audit; justine-run16 STATUS: CLEAN) |
| hooks/_common.py | run16, justine-run16 |
| hooks/artifact_verification.py | run8, run11, justine-run8, justine-run11, run19 |
| hooks/impact_graph_gate.py | run8, run11, justine-run8, justine-run11, justine-run12, justine-run23, justine-run24, run10 |
| hooks/status_staleness_gate.py | run8, run11, justine-run8, justine-run11, justine-run12, run10 |
| hooks/subagent_findings_check.py | run8, run12, justine-run8, run10 |
| hooks/convergence_gate.py | justine-run25, justine-run15, run16 |
| hooks/convergence_primer.py | justine-run15 |
| scripts/token_profiler/cli.py | run19 |
| scripts/token_profiler/extract.py | run19 |
| scripts/token_profiler/analyze.py | run19 |

## Cold Files (Never Audited)
| File | Notes |
|------|-------|
| scripts/token_profiler/__init__.py | Package init only; likely minimal logic but unverified. Appears in impact-graph.json (run16/justine) as a node but never cited in a punchlist finding. |
| scripts/token_profiler/__main__.py | Entry-point shim; likely one or two lines delegating to cli.py. Structurally low-risk but completely unaudited. |
| scripts/token_profiler/models.py | Core data model (Pydantic/dataclasses). Leaf module with no internal imports. Named frequently in architecture-baseline but never appeared in a finding. High-value audit target — if models have loose types or missing validation, errors surface far downstream. |
| scripts/token_profiler/plugin_protocol.py | Defines duck-typed protocol for plugins. Never audited. Risk: protocol may be permissive enough that a non-conforming plugin loads silently. |
| scripts/token_profiler/pricing.py | Pricing computation (token cost model). Never audited. Risk area: numeric precision, hardcoded rate tables, no test for stale pricing constants. |
| scripts/token_profiler/report.py | Report generation (markdown/text output). Never audited. Risk: format string construction, hardcoded thresholds, potential code-fence-unaware output. |
| scripts/token_profiler/viewer.py | Optional viewer (deferred import in cli.py). Never audited. Risk: unknown — deferred import means it may not be exercised by standard test runs. |

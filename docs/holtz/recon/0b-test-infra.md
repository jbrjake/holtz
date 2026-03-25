# Step 0b: Test Infrastructure

**Framework:** pytest
**Runner:** `python -m pytest --tb=short -q`
**Config:** pyproject.toml
**Coverage:** pytest-cov (62% overall, hooks at 0% due to subprocess testing)
**Linter:** ruff
**Type checker:** mypy (scoped to skills/holtz/scripts/ and hooks/)
**Build system:** None (plugin, no build step)

## Test Files (17)
| File | Target |
|------|--------|
| test_commit_msg_hook.py | Post-commit hook (version bumping) |
| test_convergence_check.py | convergence_check.py |
| test_hooks.py | All 6 enforcement hooks |
| test_impact_graph.py | impact_graph.py |
| test_integration.py | Cross-module integration |
| test_markdown_utils.py | markdown_utils.py |
| test_pattern_brief_compact.py | pattern_brief_compact.py |
| test_pattern_brief_compact_structure.py | Structural validation of compact briefs |
| test_validate_punchlist.py | validate_punchlist.py |
| test_token_profiler_analyze.py | token_profiler/analyze.py |
| test_token_profiler_cli.py | token_profiler/cli.py |
| test_token_profiler_extract.py | token_profiler/extract.py |
| test_token_profiler_integration.py | token_profiler integration |
| test_token_profiler_models.py | token_profiler/models.py |
| test_token_profiler_plugin.py | token_profiler/plugin_protocol.py |
| test_token_profiler_pricing.py | token_profiler/pricing.py |
| test_token_profiler_report.py | token_profiler/report.py |

## Support Files
- `conftest.py` — shared fixtures
- `runner_fixtures.py` — test runner output fixtures
- `__init__.py` — package marker

## Coverage Notes
- Hooks show 0% because they're tested via subprocess (test_hooks.py runs hooks as external processes). Coverage plugin doesn't capture subprocess execution.
- Core scripts: markdown_utils 100%, profiler_plugin 100%, convergence_check 84%, validate_punchlist 80%, pattern_brief_compact 78%, impact_graph 65%

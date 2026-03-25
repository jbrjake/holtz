# 0b: Test Infrastructure

**Framework:** pytest
**Runner config:** pyproject.toml `[tool.pytest.ini_options]`
**Test dir:** `tests/`
**Coverage:** pytest-cov, `--cov-fail-under=60`

## Test Files (19 files)
- test_commit_msg_hook.py
- test_convergence_check.py
- test_hooks.py
- test_impact_graph.py
- test_integration.py
- test_markdown_utils.py
- test_pattern_brief_compact.py
- test_pattern_brief_compact_structure.py
- test_token_profiler_analyze.py
- test_token_profiler_cli.py
- test_token_profiler_extract.py
- test_token_profiler_integration.py (conditional skip when session JSONL absent)
- test_token_profiler_models.py
- test_token_profiler_plugin.py
- test_token_profiler_pricing.py
- test_token_profiler_report.py
- test_validate_punchlist.py

## Support Files
- conftest.py (shared fixtures)
- runner_fixtures.py (test runner output samples)

## Linting
- ruff: E/F/W/I/UP/B/SIM/ANN selectors. Per-file ignores for tests.
- mypy: covers `skills/holtz/scripts/` and `hooks/`

## Hook Testing
- Hooks are tested via subprocess in `test_hooks.py` (not direct import)
- pytest-cov shows hooks at 0% because subprocess calls aren't traced
- Known architectural risk (documented in LIVING-PUNCHLIST.md)

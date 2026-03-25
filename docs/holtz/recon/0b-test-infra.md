# Step 0b: Test Infrastructure

**Date:** 2026-03-24
**Run:** 15

## Framework
- **Runner:** pytest
- **Coverage:** pytest-cov (configured in pyproject.toml)
- **Linter:** ruff
- **Type checker:** mypy

## Test Files (15)
| File | Module Under Test |
|------|-------------------|
| `tests/test_markdown_utils.py` | markdown_utils.py |
| `tests/test_validate_punchlist.py` | validate_punchlist.py |
| `tests/test_convergence_check.py` | convergence_check.py |
| `tests/test_impact_graph.py` | impact_graph.py |
| `tests/test_pattern_brief_compact.py` | pattern_brief_compact.py |
| `tests/test_pattern_brief_compact_structure.py` | pattern_brief_compact.py |
| `tests/test_integration.py` | cross-module integration |
| `tests/test_hooks.py` | hooks/ |
| `tests/test_commit_msg_hook.py` | git-hooks/post-commit (BROKEN — references git-hooks/commit-msg) |
| `tests/test_token_profiler_analyze.py` | token_profiler/analyze.py |
| `tests/test_token_profiler_cli.py` | token_profiler/cli.py |
| `tests/test_token_profiler_extract.py` | token_profiler/extract.py |
| `tests/test_token_profiler_integration.py` | token_profiler integration |
| `tests/test_token_profiler_models.py` | token_profiler/models.py |
| `tests/test_token_profiler_plugin.py` | token_profiler/profiler_plugin.py |
| `tests/test_token_profiler_pricing.py` | token_profiler/pricing.py |
| `tests/test_token_profiler_report.py` | token_profiler/report.py |

## Support Files
- `tests/conftest.py` — shared fixtures
- `tests/runner_fixtures.py` — test runner output samples
- `tests/__init__.py` — package marker

## pyproject.toml Config
- Coverage configured for `skills/holtz/scripts/` and `hooks/`
- Ruff configured for source and hooks directories
- Mypy configured for `skills/holtz/scripts/` and `hooks/`

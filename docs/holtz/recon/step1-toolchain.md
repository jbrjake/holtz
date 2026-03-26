# Step 1: Toolchain — Run 21 (2026-03-26)

## Test Framework Configuration

- **Framework:** pytest (with pytest-cov)
- **Config:** `pyproject.toml` — `[tool.pytest.ini_options]`
- **Test paths:** `tests/`
- **Coverage targets:** `skills/holtz/scripts/`, `hooks/`
- **Coverage minimum:** 60% (fail-under threshold)
- **conftest.py:** Provides `make_item` fixture for punchlist item construction; adds `skills/holtz/scripts`, `scripts/`, and `tests/` to `sys.path`

## Test Results

**1 failed, 584 passed** (8.44s)

### Failing Test

`tests/test_integration.py::test_readme_metrics_match_actual`

```
AssertionError: README 'What's inside' counts are stale. Update README.md:
    enforcement hooks: README says 6, actual 1
    tests: README says 647, actual 585
    lines: README says 14300, actual 12728
```

The test verifies that README.md metric counts stay in sync with actual filesystem state. Three values are stale:
- Enforcement hooks count: README=6, actual=1
- Test count: README=647, actual=585
- Line count: README=14300, actual=12728

## Coverage

**Total: 76.18%** (above required 60%)

| File | Stmts | Miss | Cover | Missing Lines |
|------|-------|------|-------|---------------|
| hooks/_common.py | 65 | 19 | 71% | 32-38, 48-56, 61-66, 76-85, 95, 161-165 |
| hooks/subagent_findings_check.py | 27 | 27 | 0% | 14-59 |
| skills/holtz/scripts/convergence_check.py | 108 | 5 | 95% | 48, 91, 143, 163, 225 |
| skills/holtz/scripts/impact_graph.py | 285 | 100 | 65% | 100-105, 153, 155, 285, 291, 321-365, 369-435, 439 |
| skills/holtz/scripts/markdown_utils.py | 46 | 0 | 100% | — |
| skills/holtz/scripts/pattern_brief_compact.py | 85 | 18 | 79% | 129, 157, 164-184, 188 |
| skills/holtz/scripts/profiler_plugin.py | 42 | 0 | 100% | — |
| skills/holtz/scripts/validate_punchlist.py | 316 | 63 | 80% | 112, 176, 200, 211, 337-338, 411, 426, 442, 451, 454, 504-580, 584 |
| **TOTAL** | **974** | **232** | **76%** | |

Notable gaps:
- `hooks/subagent_findings_check.py`: 0% coverage (27 statements untested)
- `skills/holtz/scripts/impact_graph.py`: 65%, with large uncovered blocks (321-365, 369-435)

## Linter Results

**ruff check .: All checks passed**

Configuration (`pyproject.toml`):
- `target-version = "py312"`, `line-length = 120`
- Rules: `E, F, W, I, UP, B, SIM, ANN`
- Per-file ignores: `tests/*` skips `E501, E402, ANN`; `tests/runner_fixtures.py` skips `E101, W191`

## Type Checker Results

**mypy: clean across all targets**

- `skills/holtz/scripts/`: Success — no issues found in 8 source files
- `hooks/`: Success — no issues found in 8 source files
- `enforcement/hooks/`: Success — no issues found in 7 source files

Config: `python_version = "3.12"`, `ignore_missing_imports = true`

Note: `enforcement/hooks/` is not in the default mypy config (`[tool.mypy]` only lists `skills/holtz/scripts` and `hooks`), but passes cleanly when checked directly.

## CI Pipeline

Two workflows in `.github/workflows/`:

### ci.yml
- Triggers: push/PR to `main` or `dev`
- Runner: `ubuntu-latest`, Python 3.12
- Steps: install deps → `ruff check .` → `mypy skills/holtz/scripts/ hooks/` → `python -m pytest --tb=short -q`
- Note: CI mypy does NOT include `enforcement/hooks/`

### release.yml
- Triggers: push to `main`
- Reads version from `.claude-plugin/plugin.json`
- Creates GitHub Release with tag `vX.Y.Z` if tag doesn't already exist
- Uses merge commit body as release notes

CI remote run status: not checked (requires `gh run list`).

## Summary Table

| Metric | Value | Status |
|--------|-------|--------|
| Tests passing | 584 | — |
| Tests failing | 1 | FAIL |
| Tests skipped | 0 | — |
| Coverage | 76.18% | PASS (≥60%) |
| Ruff | All checks passed | PASS |
| Mypy (scripts + hooks) | No issues, 8+8 files | PASS |
| Mypy (enforcement/hooks) | No issues, 7 files | PASS |
| CI workflows | ci.yml + release.yml | EXISTS |

# Step 0b: Test Infrastructure

**Framework:** pytest
**Runner:** `python -m pytest`
**Config:** `pyproject.toml` `[tool.pytest.ini_options]`
- testpaths: `["tests"]`
- addopts: `--cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=0`

**Coverage:** pytest-cov (installed and working)

**Linting:**
- ruff: `skills/holtz/scripts`, `tests`, `hooks`
- mypy: `skills/holtz/scripts`, `hooks`

**Test files:** 8 (excluding conftest.py and runner_fixtures.py)
**Fixture files:** conftest.py (shared), runner_fixtures.py (test runner output samples)

**No mutation testing tools detected.**

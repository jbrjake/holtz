# Phase 0b: Test Infrastructure

**Framework:** pytest
**Runner:** python -m pytest tests/
**Config:** pyproject.toml
**Coverage:** pytest-cov (--cov=skills/holtz/scripts --cov=hooks)
**Linters:** ruff (E/F/W/I/UP/B/SIM/ANN), mypy (3.12)
**Test style:** function-based, conftest.py fixtures, runner_fixtures.py samples

## Test Files

| File | Size | Focus |
|------|------|-------|
| test_validate_punchlist.py | 62,820 bytes | Punchlist parsing/validation |
| test_convergence_check.py | 47,371 bytes | Convergence tracking, runner detection |
| test_impact_graph.py | 35,484 bytes | Impact graph operations |
| test_hooks.py | 18,667 bytes | Enforcement hooks |
| test_markdown_utils.py | 8,018 bytes | Code fence masking |
| test_integration.py | 7,270 bytes | Cross-module integration |
| conftest.py | 3,240 bytes | Shared fixtures |
| runner_fixtures.py | 15,240 bytes | Test runner output samples |

## Coverage Scope

`--cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=0`

Note: hooks/ shows 0% coverage despite test_hooks.py existing (18KB). This suggests tests use subprocess/mock rather than direct import, so coverage can't track them.

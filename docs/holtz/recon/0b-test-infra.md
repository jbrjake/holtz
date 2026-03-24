# Phase 0b: Test Infrastructure

- **Framework:** pytest
- **Runner:** python -m pytest tests/ -q --tb=short
- **Coverage:** pytest-cov
- **conftest.py:** provides `make_item` fixture for punchlist item generation
- **Test files:** 8 files, 320 test functions
- **Build system:** None (pure Python plugin, no packaging)

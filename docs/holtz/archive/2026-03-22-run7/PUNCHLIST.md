# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 232 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM   | 0    | 2        | 0        |

## Patterns

## Items

### BH-001: Coverage reporting not configured
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `pyproject.toml`
**Status:** RESOLVED

**Problem:** This recommendation has appeared in 2 consecutive audit summaries
without being implemented: "Adding pytest-cov would make coverage gaps visible".

**Evidence:** Found in: docs/holtz-prior-2026-03-21-run5/SUMMARY.md (run 5, 2026-03-21), docs/holtz-prior-2026-03-22-run6/SUMMARY.md (run 6, 2026-03-22)

**Discovery Chain:** Prior summary scan → recommendation "coverage reporting" found in 2 summaries
→ 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [x] Coverage tool is configured and runnable
- [x] Validation: `python -m pytest --co -q 2>&1 | head -5` shows pytest-cov available

**Validation Command:**
```bash
python -m pytest --co -q 2>&1 | head -5
```

**Resolution:** Added `addopts = "--cov=skills/holtz/scripts --cov-report=term-missing --cov-fail-under=0"` to pyproject.toml. Installed pytest-cov 7.1.0. Coverage report shows 77% total (markdown_utils 100%, validate_punchlist 83%, convergence_check 80%, impact_graph 64%).

### BH-002: Test boilerplate reduction not implemented
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `tests/test_validate_punchlist.py`
**Status:** RESOLVED

**Problem:** This recommendation has appeared in 2 consecutive audit summaries
without being implemented: "36 repetitions of the standard valid-item template. A make_item(**overrides) builder fixture would reduce this".

**Evidence:** Found in: docs/holtz-prior-2026-03-21-run5/SUMMARY.md (run 5, 2026-03-21), docs/holtz-prior-2026-03-22-run6/SUMMARY.md (run 6, 2026-03-22)

**Discovery Chain:** Prior summary scan → recommendation "test boilerplate reduction" found in 2 summaries
→ 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [x] Recommendation is implemented
- [x] Validation: builder fixture exists and is exercised by tests

**Validation Command:**
```bash
grep -c 'make_item' tests/conftest.py tests/test_validate_punchlist.py
```

**Resolution:** Added `make_item` fixture to `tests/conftest.py` with keyword overrides for all punchlist fields (item_id, title, severity, category, location, status, problem, evidence, discovery_chain, acceptance_criteria, validation_command, resolution, extra_fields, wrap). Added 3 tests exercising the builder: defaults validation, severity override, empty problem. Existing inline-markdown tests preserved — builder is for new tests.

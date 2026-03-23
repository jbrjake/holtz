# Holtz Punchlist
> Generated: 2026-03-20 | Project: holtz (self-audit, run 3) | Baseline: 102 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 3 | 0 | 0 |

## Patterns

## Items

### BH-001: test_go_verbose_with_subtests uses partial assertion
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_convergence_check.py:548-556`
**Status:** OPEN

**Problem:** `test_go_verbose_with_subtests` asserts only `result["passed"] == 2` without verifying `failed` and `skipped`. A bug in the Go parser's fail/skip counting for subtest output would pass undetected. The fixture has no failures or skips, so the expected result is deterministic: `{"passed": 2, "failed": 0, "skipped": 0}`.

**Evidence:**
```python
assert result["passed"] == 2, (
    f"Expected 2 top-level tests passed (subtests not counted separately), got {result}"
)
```

Only `passed` is checked. `failed` and `skipped` are not asserted.

**Acceptance Criteria:**
- [ ] Assertion checks the full result dict, not just `passed`

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "go_verbose_with_subtests"
```

### BH-002: GO_PACKAGE_LEVEL fixture is unused dead code
**Severity:** LOW
**Category:** design/dead-code
**Location:** `tests/runner_fixtures.py:199-204`
**Status:** OPEN

**Problem:** The `GO_PACKAGE_LEVEL` fixture was created alongside the Go verbose fixtures in run 1 BH-006, which changed the Go command from `go test ./...` to `go test -v ./...`. The verbose format is now the only one used by the parser and tests. `GO_PACKAGE_LEVEL` is never imported or referenced in any test file.

**Evidence:**
```python
# Old format (non-verbose): only package-level results
GO_PACKAGE_LEVEL = """\
ok  	github.com/spectral/haunted-elevator/floors	0.003s
...
```

No test references `GO_PACKAGE_LEVEL`. Verified: `grep -r "GO_PACKAGE_LEVEL" tests/` returns no results (only the fixture definition).

**Acceptance Criteria:**
- [ ] `GO_PACKAGE_LEVEL` removed from runner_fixtures.py

**Validation Command:**
```bash
python -m pytest tests/ -v && ! grep -q "GO_PACKAGE_LEVEL" tests/test_convergence_check.py
```

### BH-003: Deferred bug warning fires regardless of deferral reason
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/validate_punchlist.py:283-286`
**Status:** OPEN

**Problem:** The validator warns about ALL deferred bug items missing an Investigation link. But the punchlist-format.md spec says evidence of reproduction attempts is required only for items "deferred due to can't-reproduce." Items deferred for other reasons (low priority, out of scope, dependencies) get a misleading warning suggesting they need investigation files.

**Evidence:**
Validator code (line 283-286):
```python
if item.status == "DEFERRED" and is_bug and not item.investigation:
    result.warnings.append(
        f"{prefix}: bug item DEFERRED without Investigation file link"
    )
```

Punchlist-format.md spec:
```
- Items deferred due to can't-reproduce must include evidence of reproduction attempts
  in the Evidence section or the linked investigation file.
```

The spec scopes the requirement to "can't-reproduce" deferrals. The validator applies it universally. Additionally, the spec accepts evidence in "the Evidence section OR the linked investigation file" — the validator only checks for the investigation file link.

**Acceptance Criteria:**
- [ ] Warning message clarified to indicate this is advisory for can't-reproduce deferrals
- [ ] Warning suppressed when the item has sufficient Evidence content (the "OR" branch)

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "deferred"
```

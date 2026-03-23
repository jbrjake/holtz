# Holtz Punchlist
> Generated: 2026-03-19 | Project: holtz (self-audit) | Baseline: 40 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 2 | 0 |
| MEDIUM | 0 | 6 | 0 |
| LOW | 0 | 4 | 0 |

## Patterns

## Pattern: PAT-001: Code-fence-unaware parsing
**Instances:** BH-001, BH-002, BH-003, BH-004
**Root Cause:** Parsing logic operated on raw/normalized content without considering code fence boundaries, allowing phantom headers, field poisoning, and incorrect section termination
**Systemic Fix:** Dual masked/original approach with masked gating for all field detection; line-number mapping for boundary correlation; tilde fence support
**Detection Rule:** `grep -n 'original_block\|normalized' skills/holtz/scripts/validate_punchlist.py` — any new field extraction from original_block must be gated by masked header check

## Items

### BH-001: original_block extracts fields from inside code fences
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:139-157`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** Fields extracted from `original_block` (Problem, Evidence, Resolution) search the entire block including content inside code fences. If a code fence in the Evidence section contains `**Resolution:** Fixed in abc123`, the parser reports `has_resolution = True` for the item — even though the item has no actual Resolution field.

**Evidence:** Lines 139-157 extract Problem, Evidence, and Resolution from `original_block` (the normalized/unmasked content). The `section_re` pattern has no code-fence awareness. A punchlist item whose Evidence section contains a markdown example with `**Resolution:**` text would trigger a false positive.

```python
# validate_punchlist.py:139-157
section_re = r'\*\*%s:\*\*[ \t]*((?:[^\n]*(?:\n(?!\*\*\w)[^\n]*)*))'
problem_m = re.search(section_re % 'Problem', original_block)
# ...
resolution_m = re.search(section_re % 'Resolution', original_block)
item.has_resolution = bool(resolution_m and len(resolution_m.group(1).strip()) > 5)
```

This is particularly relevant for self-audit: when Holtz audits a project that includes punchlist examples in its Evidence sections.

**Acceptance Criteria:**
- [x] Fields extracted from original_block are not poisoned by content inside code fences
- [x] Test proves: item with `**Resolution:** ...` inside a code fence in Evidence does NOT satisfy `has_resolution`
- [x] Test proves: item with `**Problem:** ...` inside a code fence in Evidence does NOT satisfy `has_problem`

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "resolution_inside_code_fence or problem_inside_code_fence"
```

**Resolution:** Fixed in commit 5f14ea3. Added `_section_from_original()` helper that gates original_block extraction on masked_block header existence. Tests `test_resolution_inside_code_fence_not_extracted` and `test_problem_inside_code_fence_not_extracted` validate.

### BH-002: phantom headers in normalized content corrupt ID-based boundary matching
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:72-100`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** `norm_matches_by_id` is built from ALL headers in normalized content, including phantom headers inside code fences. When a phantom header shares an ID with a real item and appears BEFORE it in document order, `pop(0)` grabs the phantom's position. The `original_block` boundaries are calculated from the wrong offset.

**Evidence:** Lines 72-77 build the index from normalized content without code-fence filtering:
```python
norm_matches_by_id: dict[str, list[re.Match]] = {}
for m in item_pattern.finditer(normalized):
    norm_matches_by_id.setdefault(m.group(1), []).append(m)
```

A punchlist with a code fence example before the real item triggers incorrect extraction:
```markdown
Here's an example:
````markdown
### BH-001: Example
**Status:** RESOLVED
````

### BH-001: Real item
**Status:** OPEN
```

The `pop(0)` at line 88 grabs the phantom header at the top, not the real item's header.

**Acceptance Criteria:**
- [x] Phantom headers inside code fences do not appear in `norm_matches_by_id`
- [x] Test proves: punchlist with same-ID example in a code fence before the real item parses correctly

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "phantom_same_id"
```

**Resolution:** Fixed in commit 99baae5. Replaced ID-based norm index with line-number mapping. Since mask_code_fences preserves line count, line N in masked maps directly to line N in normalized. Tests `test_phantom_same_id_before_real_item` and `test_phantom_same_id_problem_content_from_phantom` validate.

### BH-003: section_re truncates content on bold continuation lines
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:139`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** The section content regex uses `(?!\*\*\w)` as a negative lookahead on continuation lines. Any continuation line starting with `**word` (bold emphasis) stops the capture. Content is silently truncated. `has_problem` passes only because the first line exceeds the 10-char threshold.

**Evidence:**
```python
section_re = r'\*\*%s:\*\*[ \t]*((?:[^\n]*(?:\n(?!\*\*\w)[^\n]*)*))'
```

Input:
```markdown
**Problem:** Found a bug where the system fails when
**bold emphasis** is used in the description.
More detail here.
```

Captured: `Found a bug where the system fails when` (39 chars). Lines 2-3 dropped.

**Acceptance Criteria:**
- [x] Bold emphasis on continuation lines does not truncate section capture
- [x] Test proves: multi-line Problem with bold on line 2 captures all lines

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "bold_continuation_full_content"
```

**Resolution:** Fixed in commit 34029dc. Changed lookahead from `(?!\*\*\w)` to `(?!\*\*[A-Z][\w ]*:\*\*)` to only match actual field headers (**FieldName:**), not generic bold emphasis. Test `test_bold_continuation_full_content` validates.

### BH-004: tilde fences not handled by mask_code_fences
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/markdown_utils.py:6`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** CommonMark specifies both backtick (```) and tilde (~~~) as valid code fence delimiters. `mask_code_fences` only handles backtick fences. Content inside tilde fences is not masked, allowing phantom headers and field poisoning.

**Evidence:**
```python
_FENCE_OPEN = re.compile(r'^(`{3,})[^`]*$')  # only backticks
```

Tilde fences are uncommon in Holtz-generated output but could appear in user-edited punclists or in Evidence sections quoting external code.

**Acceptance Criteria:**
- [x] `mask_code_fences` handles tilde fences (`~~~`) the same as backtick fences
- [x] Test proves: content inside tilde fences is blanked in masked output

**Validation Command:**
```bash
python -m pytest tests/test_markdown_utils.py -v -k "tilde"
```

**Resolution:** Fixed in commit f853800. Added `_TILDE_OPEN` and `_TILDE_CLOSE_TMPL` patterns. Tilde fences cannot close backtick fences and vice versa per CommonMark. Tests `test_tilde_fence_masking`, `test_tilde_fence_with_language`, `test_tilde_fence_does_not_close_backtick` validate.

### BH-005: detect_test_runner uses string matching on pyproject.toml instead of TOML parsing
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:56-58`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** The pyproject.toml check uses `in` on raw file content (`"pytest" not in content`). This matches comments like `# we don't use pytest`, string values in unrelated sections, or even package names containing "pytest" as a substring.

**Evidence:**
```python
if runner == "pytest" and f in ("pyproject.toml", "setup.cfg"):
    content = Path(f).read_text()
    if "pytest" not in content and "tool.pytest" not in content and "tool:pytest" not in content:
        continue
```

**Acceptance Criteria:**
- [x] pyproject.toml detection checks for `[tool.pytest` section header, not just substring
- [x] Test proves: pyproject.toml with "pytest" only in a comment does not trigger pytest detection

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "detect_runner_pyproject"
```

**Resolution:** Fixed in commit 5688a8a. Now checks for `[tool.pytest` section header in pyproject.toml and `[tool:pytest]` in setup.cfg. Test `test_detect_pyproject_with_pytest_in_comment` validates.

### BH-006: go test parser counts packages not individual tests
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:127-134`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** The Go test output parser counts `ok` and `FAIL` lines, which are package-level results. A project with 10 packages each containing 50 tests reports "10 passed" not "500 passed." This is inconsistent with other runners (pytest, jest) which count individual tests.

**Evidence:**
```python
if runner == "go":
    passed = len(re.findall(r'^ok\s', output, re.MULTILINE))
    failed = len(re.findall(r'^FAIL\s', output, re.MULTILINE))
```

**Acceptance Criteria:**
- [x] Go parser counts individual test results, or clearly documents that counts are package-level
- [x] Test proves correct count extraction from Go test output

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "go"
```

**Resolution:** Fixed in commit f70abf7. Changed Go command to `go test -v ./...` and parser to count `--- PASS:`, `--- FAIL:`, `--- SKIP:` lines. Subtests (names containing `/`) are excluded to avoid double-counting. Comprehensive fixtures ("Haunted Elevator") validate all-pass, mixed, subtest, and crash scenarios. Also fixed Jest, Cargo, Vitest, and Mocha parsers for crash/unparseable output handling, discovered by the same fixture suite.

### BH-007: get_test_counts returns zero counts instead of None on runner errors
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/convergence_check.py:82-147`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** When a test runner fails to produce parseable output (crashes, permission error, unrecognized output format), `get_test_counts` returns `{"passed": 0, "failed": 0, "skipped": 0}` instead of `None`. This is indistinguishable from "all tests skipped" and misleads the convergence checker into thinking the test suite ran cleanly with zero failures.

**Evidence:** For pytest, if the output contains no "passed"/"failed"/"skipped" strings (e.g., pytest itself crashes with a traceback), all regex matches return None, and the return value is `{"passed": 0, "failed": 0, "skipped": 0}`. The convergence checker treats this as "0 failures" (stable tests).

**Acceptance Criteria:**
- [x] get_test_counts returns None when runner output cannot be parsed
- [x] Test proves: unparseable pytest output returns None, not zero counts

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "unparseable_output"
```

**Resolution:** Fixed in commit e34e80d. Added None-return guard when no regex matches for pytest, vitest, and go parsers. Test `test_get_test_counts_unparseable_output` validates.

### BH-008: test_bold_text_in_problem_continuation does not verify content integrity
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_validate_punchlist.py:340-366`
**Status:** RESOLVED

**Problem:** Test name says "Bold text on continuation lines should not truncate the section" but the assertion only checks `has_problem` (threshold >10 chars). The Problem content IS truncated — the test passes because the first line alone exceeds 10 chars. The test does not verify that the full multi-line content is captured.

**Evidence:**
```python
def test_bold_text_in_problem_continuation():
    """Bold text on continuation lines should not truncate the section."""
    # ... content with bold on line 2 ...
    assert items[0].has_problem, (
        "Problem with bold continuation line should not be truncated"
    )
```

Only `has_problem` is asserted. The actual captured content (just the first line) is never checked.

**Acceptance Criteria:**
- [x] Test verifies the captured Problem content includes all continuation lines, not just threshold
- [x] This test should fail if BH-003 is not fixed, proving it catches the truncation

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "bold_text_in_problem"
```

**Resolution:** Superseded by BH-003 fix and `test_bold_continuation_full_content` test (commit 34029dc). The new test uses a Problem where the first line is too short (6 chars), forcing the test to fail if continuation lines are truncated.

### BH-009: no test for multi-item punchlist parsing
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_validate_punchlist.py`
**Status:** RESOLVED

**Problem:** All parsing tests use single-item punclists (except the duplicate ID test). No test verifies correct parsing of 3+ items with different statuses and severities, or that fields from one item don't bleed into the next item.

**Evidence:** Every test in test_validate_punchlist.py starts with `### BH-001:` as the only (or first) item. There is no test with BH-001, BH-002, BH-003 in sequence verifying that each item's fields are correctly isolated.

**Acceptance Criteria:**
- [x] Test with 3+ items verifies correct field isolation (each item has its own severity, status, etc.)
- [x] Test verifies item count matches expected

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "multi_item"
```

**Resolution:** Added in commit a173970. `test_multi_item_field_isolation` verifies 3 items with different severities, statuses, categories, and resolution states. Also added `test_multi_item_punchlist_field_isolation` in convergence tests for count_items.

### BH-010: no tests for detect_test_runner
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_convergence_check.py`
**Status:** RESOLVED

**Problem:** `detect_test_runner()` has zero test coverage. File existence checks and content matching logic are all untested. The pyproject.toml string matching bug (BH-005) survives because there's no test to catch it.

**Evidence:** `grep -r "detect_test_runner" tests/` returns no results.

**Acceptance Criteria:**
- [x] Tests verify detection of at least pytest, jest, and cargo by config file presence
- [x] Tests verify pyproject.toml content matching logic

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "detect"
```

**Resolution:** Added in commit a173970. Tests: `test_detect_pytest_by_conftest`, `test_detect_jest_by_config`, `test_detect_cargo_by_toml`, `test_detect_no_runner`, `test_detect_pyproject_without_pytest`.

### BH-011: README double-counts backstory in component list
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:27`
**Status:** RESOLVED

**Problem:** README says "5 reference docs, 2 Python scripts, 1 backstory" — but backstory.md IS one of the 5 reference docs. The component list double-counts it.

**Evidence:** `references/` contains 5 files: anti-patterns.md, backstory.md, investigation-format.md, punchlist-format.md, status-file-format.md. The README counts all 5 as "reference docs" then separately lists "1 backstory."

**Acceptance Criteria:**
- [x] Component list accurately counts without double-counting backstory

**Validation Command:**
```bash
grep -c "reference" README.md
```

**Resolution:** Fixed in commit 5eef7ce. Corrected to "4 reference docs, 1 example, 3 Python scripts, 1 backstory."

### BH-012: no tests for get_test_counts output parsing
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_convergence_check.py`
**Status:** RESOLVED

**Problem:** `get_test_counts()` has no tests for its regex parsing of test runner output. Each of the 6 runner formats has a distinct regex pattern, none tested.

**Evidence:** `grep -r "get_test_counts" tests/` returns no results.

**Acceptance Criteria:**
- [x] Tests verify correct parsing of at least pytest and jest output formats
- [x] Tests verify the error/fallback paths

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "test_counts"
```

**Resolution:** Added in commit a173970. Tests: `test_get_test_counts_pytest_output`, `test_get_test_counts_jest_output`, `test_get_test_counts_unparseable_output`.

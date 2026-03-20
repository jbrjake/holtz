# Holtz Punchlist
> Generated: 2026-03-20 | Project: holtz (self-audit, run 2) | Baseline: 92 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 2 | 0 |
| LOW | 0 | 3 | 0 |

## Patterns

## Pattern: PAT-002: Incomplete code-fence isolation in extraction
**Instances:** BH-001, BH-002, BH-004
**Root Cause:** `_section_from_original` gates on masked content to verify field header existence but then performs extraction on original_block using regexes that cannot distinguish code fence content from real content. The masking layer prevents false positives (phantom headers) but the extraction layer is still affected by code fence content.
**Systemic Fix:** Use masked content to determine section boundaries (start/end line numbers), then extract the corresponding line range from original content. This preserves code fence content in the extraction while preventing code-fence headers from interfering with boundary detection.
**Detection Rule:** `grep -n 're.search.*original_block' skills/holtz/scripts/validate_punchlist.py` — any regex search on original_block is vulnerable to code fence interference

## Items

### BH-001: _section_from_original extracts wrong content when field header exists in both code fence and real content
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:148-172`
**Status:** RESOLVED
**Pattern:** PAT-002
**Determinism:** deterministic

**Problem:** `_section_from_original` checks `masked_block` for a field header (confirming it's not only inside a code fence), then runs `re.search(section_re, original_block)` to extract content. If the same field header appears inside a code fence BEFORE the real one in document order, `re.search` matches the code-fence instance first. This extracts wrong content and can cause false negatives on `has_resolution` and `has_validation_command`.

**Evidence:** The function at line 148-152:
```python
def _section_from_original(field_name):
    """Find header in masked, extract content from original."""
    if not re.search(header_re % field_name, masked_block):
        return None
    return re.search(section_re % field_name, original_block)
```

The gating check on `masked_block` prevents false positives when the header exists ONLY inside a code fence (fixed in prior run BH-001). But when the header exists in BOTH a code fence AND as a real field, the gating passes and `re.search` on `original_block` finds whichever comes first — which may be the code-fence instance.

Concrete scenario: an item's Evidence section contains a code fence with `**Resolution:** N/A`, and the item also has a real `**Resolution:** Fixed in commit abc123...`. The Evidence code fence comes first in document order. `re.search` matches the code-fence `**Resolution:** N/A`. `len("N/A") > 5` is False. `has_resolution = False`. Validation reports "marked RESOLVED but no resolution documented."

**Acceptance Criteria:**
- [x] When a field header appears in both a code fence and as a real field, the real field's content is extracted
- [x] Test proves: item with `**Resolution:** N/A` in Evidence code fence AND real `**Resolution:** Fixed in...` outside reports `has_resolution = True`
- [x] Test proves: item with `**Validation Command:**` in Evidence code fence AND real Validation Command outside extracts the real command

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "dual_instance"
```

**Resolution:** Fixed in commit ce375b4. Added `_masked_pos_to_orig_offset()` helper that maps a character position in masked_block to the corresponding line start in original_block. `_section_from_original` now finds the header position in masked_block and starts extraction from that position in original_block, bypassing any earlier code-fence instances. Tests `test_resolution_dual_instance_extracts_real` and `test_validation_command_dual_instance_extracts_real` validate.

### BH-002: section_re terminates capture at non-field bold-colon patterns
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:145`
**Status:** RESOLVED
**Pattern:** PAT-002
**Determinism:** deterministic

**Problem:** The negative lookahead `(?!\*\*[A-Z][\w ]*:\*\*)` in `section_re` treats any `**CapitalizedWord(s):**` as a field header and stops section capture. This is too broad — patterns like `**HTTP Status:**`, `**API Response:**`, or `**Root Cause:**` (when used as descriptive text, not punchlist fields) truncate section content.

**Evidence:**
```python
section_re = r'\*\*%s:\*\*[ \t]*((?:[^\n]*(?:\n(?!\*\*[A-Z][\w ]*:\*\*)[^\n]*)*))'
```

Input:
```markdown
**Problem:** The system returns wrong data when
**HTTP Status:** 404 is received from the upstream API.
More detail about the problem.
```

Captured: `The system returns wrong data when` (34 chars). Lines 2-3 lost.

**Acceptance Criteria:**
- [x] Section capture continues past non-field `**Bold Colon:**` patterns
- [x] Test proves: Problem with `**HTTP Status:**` on continuation line captures all lines

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "non_field_bold_colon"
```

**Resolution:** Fixed in commit 5c0361b. Replaced generic `(?!\*\*[A-Z][\w ]*:\*\*)` with an alternation of the 13 known punchlist field names (Severity, Category, Location, Status, Pattern, Determinism, Investigation, Root Cause Confidence, Problem, Evidence, Acceptance Criteria, Validation Command, Resolution). Test `test_non_field_bold_colon_does_not_truncate` validates.

### BH-003: mask_code_fences ignores indented code fences
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/markdown_utils.py:6-9`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** Per CommonMark spec, code fence opening and closing lines may be indented up to 3 spaces. `_BACKTICK_OPEN` and `_TILDE_OPEN` patterns use `^` anchor without allowing leading whitespace, so indented fences like `   ```python` pass through unmasked. Content inside indented fences is not blanked, potentially allowing phantom headers and field poisoning.

**Evidence:**
```python
_BACKTICK_OPEN = re.compile(r'^(`{3,})[^`]*$')
_TILDE_OPEN = re.compile(r'^(~{3,})[^~]*$')
```

CommonMark spec Section 4.5: "An opening code fence is a sequence of at least three consecutive backtick characters or tilde characters, optionally preceded by up to three spaces of indentation."

**Acceptance Criteria:**
- [x] `mask_code_fences` handles fences indented 1-3 spaces
- [x] Closing fence also handles 0-3 spaces indentation
- [x] Test proves: content inside `   ```\ncode\n   ```\n` is blanked
- [x] Test proves: fence indented 4+ spaces is NOT treated as a code fence

**Validation Command:**
```bash
python -m pytest tests/test_markdown_utils.py -v -k "indented"
```

**Resolution:** Fixed in commit e38d8bd. Changed open patterns to `^ {0,3}` prefix and close templates to `^ {0,3}` prefix. The open patterns now capture fence chars in group(2) instead of group(1). Tests `test_indented_backtick_fence_1_space`, `test_indented_backtick_fence_3_spaces`, `test_indented_4_spaces_not_code_fence`, `test_indented_tilde_fence`, `test_indented_close_fence` validate.

### BH-004: file structure validation uses raw content instead of masked
**Severity:** LOW
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:189-195`
**Status:** RESOLVED
**Pattern:** PAT-002
**Determinism:** deterministic

**Problem:** The `validate()` function checks for `# Holtz Punchlist`, `## Summary`, and `## Items` using raw (unmasked) content. If these strings appear inside a code fence (e.g., in an Evidence section showing punchlist structure), the check passes and the structural warning is suppressed — even if the actual file is missing the proper top-level section.

**Evidence:**
```python
if content:
    if '# Holtz Punchlist' not in content and '# Bug Hunter Punchlist' not in content:
        result.warnings.append("Missing punchlist header section")
    if '## Summary' not in content:
        result.warnings.append("Missing Summary section")
    if '## Items' not in content:
        result.warnings.append("Missing Items section")
```

**Acceptance Criteria:**
- [x] Structural checks use masked content
- [x] Test proves: `## Items` inside a code fence does not suppress the "Missing Items section" warning

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "structure_in_code_fence"
```

**Resolution:** Fixed in commit 331245b. `validate()` now calls `mask_code_fences(content)` and checks the masked output for structural headers. Test `test_structure_in_code_fence_not_counted` validates.

### BH-005: Jest all-fail test uses permissive assertion
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_convergence_check.py:445-451`
**Status:** RESOLVED

**Problem:** `test_jest_all_fail` asserts `result is None or result["failed"] == 7`. The `JEST_ALL_FAIL` fixture contains `7 failed, 0 passed, 7 total`, which deterministically matches the Jest parser regex (because `0 passed` is present). The `result is None` branch is dead code in the assertion — it passes regardless of whether the parser handles the format correctly.

**Evidence:**
```python
def test_jest_all_fail(monkeypatch):
    """The jukebox is broken. Every recommendation is wrong."""
    monkeypatch.setattr(subprocess, "run", _fake_run(fx.JEST_ALL_FAIL))
    result = cc.get_test_counts("jest")
    assert result is None or result["failed"] == 7
```

**Acceptance Criteria:**
- [x] Assertion is definitive: `assert result == {"passed": 0, "failed": 7, "skipped": 0}`
- [x] If the intent was to handle Jest versions that omit "0 passed", add a separate fixture and test for that format

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "jest_all_fail"
```

**Resolution:** Fixed in commit 8adeafe. Split into two tests: `test_jest_all_fail` now asserts exact expected dict; `test_jest_all_fail_no_passed_label` tests the no-passed-label format separately, asserting None.

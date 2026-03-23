# Holtz Punchlist
> Generated: 2026-03-20 | Project: holtz (self-audit, run 4 — integration focus) | Baseline: 104 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 2 | 0 |
| LOW | 0 | 2 | 0 |

## Patterns

## Pattern: PAT-001: Structural-awareness divergence across parsers
**Instances:** BH-001, BH-002
**Root Cause:** The codebase has two parsing approaches (full structured parse in parse_punchlist, flat regex scan in count_items/section_re) that operate at different levels of structural awareness. When content appears at the wrong structural level (field headers inside code fences, Status fields outside item blocks), the less-aware parser sees phantoms that the more-aware parser ignores.
**Systemic Fix:** Unify parsing to always scope extraction to item blocks and always use masked content for structural decisions (header finding AND section boundary detection).
**Detection Rule:** `grep -n 'original_block\|section_re.*original' skills/holtz/scripts/validate_punchlist.py` — any section_re application to unmasked content is suspect.

## Items

### BH-001: section_re on original_block terminates at code-fenced field headers
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:166-172`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** `_section_from_original()` correctly uses masked_block to find field headers (immune to code fences) but then applies section_re to original_block for content extraction. The section_re lookahead terminates capture at any line matching `**FieldName:**` where FieldName is a known punchlist field. In original_block, code-fenced field headers are present (not blanked), so they act as premature section terminators. Content after the code fence but still within the section is silently lost.

**Evidence:**
Proof-of-concept: a Problem section containing a 4-backtick code fence with `**Evidence:**` inside it. The section_re captures only the content before the code fence. The continuation text after the fence is lost.
```python
# _section_from_original('Problem'):
# 1. Finds **Problem:** in masked_block (correct)
# 2. Maps to original_block offset (correct)
# 3. Applies section_re to original_block[offset:] (BUG: code-fenced
#    **Evidence:** terminates the capture prematurely)
# Result: "Real problem...\\n````" — continuation text after fence lost
```
Acceptance Criteria uses masked_block for its section_re (line 180), which is immune to this bug. The inconsistency between approaches is the root cause.

**Acceptance Criteria:**
- [x] section_re for Problem/Evidence/Resolution uses masked_block for boundary detection
- [x] Content between boundaries is extracted from original_block
- [x] Test proves code-fenced field header does not truncate section content

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "code_fence_field_header_no_truncate"
```

**Resolution:** Fixed in commit 400cd23. `_section_from_original` now finds section boundaries in masked_block via section_re, maps the line range to original_block, and extracts original content directly — no section_re on unmasked content. Test `test_code_fence_field_header_no_truncate_problem` validates.

### BH-002: count_items matches Status fields outside item blocks
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:29-36`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** `count_items()` uses a flat regex scan of the entire masked document for `**Status:**` fields. It does not scope to item blocks (`### BH-NNN:` boundaries). If `**Status:**` appears in Pattern block descriptions, section preambles, or item Problem/Evidence content outside code fences, count_items inflates the item count. Since `check_convergence()` relies on count_items for open-item tracking, phantom statuses can block convergence or produce misleading metrics.

**Evidence:**
Proof-of-concept: a punchlist with 1 real item (Status: OPEN) and a Pattern description containing `**Status:** OPEN` in prose text.
```python
# count_items sees: {'OPEN': 2, ..., 'total': 2}
# parse_punchlist sees: 1 item
# Convergence tracker thinks 2 items open when only 1 exists
```

**Acceptance Criteria:**
- [x] count_items scopes Status extraction to item blocks (between `### BH-NNN:` headers)
- [x] Test proves Status in Pattern description does not inflate count
- [x] count_items and parse_punchlist agree on item count for the same content

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "status_outside_item_block"
```

**Resolution:** Fixed in commit a475925. count_items now splits on `### BH-NNN:` headers and extracts only the first Status field per item block. Tests `test_status_outside_item_block_not_counted` and `test_status_in_problem_section_not_counted` validate.

### BH-003: No integration test verifies count_items/parse_punchlist agreement
**Severity:** LOW
**Category:** test/integration-gap
**Location:** `tests/test_convergence_check.py` and `tests/test_validate_punchlist.py`
**Status:** RESOLVED

**Problem:** count_items (convergence tracker) and parse_punchlist (validator) parse the same punchlist format independently. No test feeds the same content to both and asserts they agree on item counts and status distribution. If the two parsing approaches diverge (as BH-002 demonstrates), the divergence is invisible to the test suite.

**Evidence:** `grep -r "count_items.*parse_punchlist\|parse_punchlist.*count_items" tests/` returns no results. The two functions are never tested together.

**Acceptance Criteria:**
- [x] Integration test feeds same content to both parsers and asserts agreement
- [x] Test covers content with Status fields both inside and outside item blocks

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "cross_parser_agreement"
```

**Resolution:** Fixed in commit c3022a8. `test_cross_parser_agreement` feeds a multi-item punchlist with phantom Status fields to both parsers and asserts total count and per-status distribution agreement.

### BH-004: Acceptance Criteria uses masked_block while Problem/Evidence/Resolution use original_block
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/validate_punchlist.py:166-194`
**Status:** RESOLVED
**Pattern:** PAT-001

**Problem:** Section extraction uses two different approaches within the same parsing loop. Acceptance Criteria (line 180) applies section_re to masked_block, making it immune to code-fenced field headers acting as terminators. Problem, Evidence, and Resolution (lines 174-194) use `_section_from_original()` which applies section_re to original_block, where code-fenced field headers CAN terminate the section. This inconsistency means some sections are code-fence-safe while others are not.

**Evidence:**
```python
# Line 180: AC uses masked_block (safe)
ac_m = re.search(section_re % 'Acceptance Criteria', masked_block)

# Line 174: Problem uses original_block via _section_from_original (unsafe)
problem_m = _section_from_original('Problem')
# which calls: re.search(section_re % field_name, original_block[orig_offset:])
```

**Acceptance Criteria:**
- [x] All section extractions use the same approach for boundary detection
- [x] BH-001 fix resolves this inconsistency

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -v -k "code_fence"
```

**Resolution:** Resolved by BH-001 fix (commit 400cd23). `_section_from_original` now uses masked_block for boundary detection (same approach as AC extraction), making all section extractions code-fence-safe.

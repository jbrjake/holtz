# Holtz Audit Summary

**Project:** holtz (self-audit, run 2)
**Date:** 2026-03-20
**Auditor:** Holtz, applied to himself (again)

## Before / After

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 92 | 102 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Findings | — | 5 |
| Resolved | — | 5 |
| Deferred | — | 0 |

## Findings by Category

| Category | Count |
|----------|-------|
| bug/logic | 4 |
| test/shallow | 1 |

## Pattern Identified

**PAT-002: Incomplete code-fence isolation in extraction** (3 instances: BH-001, BH-002, BH-004)

Run 1's PAT-001 introduced `mask_code_fences` and the `_section_from_original` gating pattern. Run 2 found that the gating was necessary but not sufficient — the extraction step still operated on raw `original_block` content without position awareness. This manifested as:

- Field headers inside code fences matching before real ones when both exist (BH-001)
- Overly broad negative lookahead treating non-field bold-colon patterns as section terminators (BH-002)
- Structural validation using raw content instead of masked (BH-004)

Systemic fix: line-mapped extraction (find position in masked, extract from original at that position), field-name-specific lookahead, and masked content for all structural checks.

## Key Fixes

1. **BH-001 (MEDIUM):** `_section_from_original` now maps the masked header position to the corresponding line in `original_block` via `_masked_pos_to_orig_offset()`. This prevents `re.search` from matching a code-fence instance of the same field header that appears earlier in document order. The prior run's fix addressed the case where a field existed *only* inside a code fence; this fix addresses the case where it exists in *both* locations.

2. **BH-002 (LOW):** The `section_re` negative lookahead was narrowed from `(?!\*\*[A-Z][\w ]*:\*\*)` (any capitalized bold-colon pattern) to a specific alternation of the 13 known punchlist field names. This prevents patterns like `**HTTP Status:**` or `**API Response:**` from truncating section content.

3. **BH-003 (LOW):** `mask_code_fences` now handles fences indented 0-3 spaces per CommonMark spec. Both open patterns (`_BACKTICK_OPEN`, `_TILDE_OPEN`) and close templates (`_BACKTICK_CLOSE_TMPL`, `_TILDE_CLOSE_TMPL`) allow `^ {0,3}` prefix. Fences indented 4+ spaces are correctly excluded (those are indented code blocks).

4. **BH-004 (LOW):** `validate()` now calls `mask_code_fences()` on the content before checking for structural headers (`# Holtz Punchlist`, `## Summary`, `## Items`). Previously, these strings inside code fences suppressed warnings.

5. **BH-005 (MEDIUM):** The Jest all-fail test was split from a permissive `result is None or result["failed"] == 7` assertion into two definitive tests: one for the fixture (which deterministically produces a result), and one for Jest versions that omit "0 passed" (which returns None).

## Relationship to Run 1

| Aspect | Run 1 | Run 2 |
|--------|-------|-------|
| Findings | 12 | 5 |
| Dominant pattern | PAT-001: code-fence-unaware parsing | PAT-002: incomplete code-fence isolation |
| Root cause layer | No masking at all | Masking present but extraction bypassed it |
| Fix approach | Add mask_code_fences + gating | Add position mapping + narrow lookahead |
| Tests added | 48 | 10 |

PAT-002 is the second-order consequence of PAT-001. Run 1 added the masking layer. Run 2 found that the extraction layer didn't fully use it. The two patterns together represent the complete arc of making the punchlist parser code-fence-aware.

## Recommendations

1. The primary risk surface remains the markdown parsing in `validate_punchlist.py`. Any new field extraction should use the `_masked_pos_to_orig_offset` → extract pattern.

2. The `_field_names` tuple and `section_re` construction are recomputed per item inside the loop. They could be hoisted to module level for clarity, though the performance impact is negligible for typical punchlist sizes.

3. `validate()` calls `mask_code_fences(content)` redundantly (it was already called in `parse_punchlist()`). Passing the masked content as an argument would eliminate this.

4. No linter or type checker is configured. Adding mypy would catch type issues at development time.

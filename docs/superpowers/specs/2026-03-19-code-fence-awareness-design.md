# Code-Fence-Aware Parsing for Holtz Scripts

## Problem

Both `validate_punchlist.py` and `convergence_check.py` run regexes against raw markdown content with no awareness of fenced code blocks. Content inside fences — item headers, field values, checkboxes, status markers — is treated as real punchlist structure, producing phantom items, poisoned fields, false checkbox matches, and inflated convergence counts.

Five deferred audit items share this root cause (PAT-004):

| ID | What breaks |
|----|------------|
| FA-001 | `### BH-NNN:` inside fences creates phantom items |
| FA-003 | `**Status:**` etc. inside fences poisons field extraction |
| FA-005 | `- [ ]` outside fences but in wrong section (e.g., Problem) fakes acceptance criteria |
| FA-006 | `- [ ]` inside fences fakes acceptance criteria |
| FA-009 | `**Status:**` inside fences inflates convergence counts |

The sample punchlist already uses code fences in Evidence sections (TypeScript snippets). The format spec puts code in Evidence. This is structural to how punchlists work, not hypothetical.

## Constraints

- Section content extraction (Problem, Evidence, Resolution) must still see inside code fences — that is where evidence lives
- Validation command extraction must still work — the command is inside a code fence
- The punchlist format spec uses 4-backtick fences to wrap templates containing 3-backtick examples, so nested fence handling is required
- Line count must be preserved between original and masked versions to allow position-based slicing
- CRLF normalization (currently duplicated in both scripts) should be consolidated

## Design

### New file: `skills/holtz/scripts/markdown_utils.py`

One public function:

```python
def mask_code_fences(content: str) -> tuple[str, str]:
    """Normalize line endings and produce a masked copy with code fence content blanked.

    Returns (normalized, masked) where:
    - normalized: original content with CRLF converted to LF
    - masked: same content but lines inside fenced code blocks replaced with empty lines
    """
```

**Algorithm:**
1. Replace `\r\n` with `\n`
2. Split into lines
3. Walk lines tracking fence state:
   - A line matching opening fence regex `^(`{3,})[^`]*$` (3+ backticks, followed by an optional info string that contains no backticks) opens a fence. Record the backtick count N. The opening fence line is blanked in the masked output.
   - While in a fence, replace each line with an empty string in the masked output
   - A line matching closing fence regex `^`{N,}[ \t]*$` (N or more backticks followed by optional whitespace only) closes the fence. This line is also blanked.
4. If a fence is never closed (EOF), all content from the opening fence onward is blanked
5. Rejoin lines with `\n`
6. Return `(normalized, masked)` — both have LF line endings, `masked` additionally has fence interiors and delimiters blanked

The function is pure. No side effects, no file I/O.

**Scope limitation:** Indented fences (up to 3 spaces before backticks, per CommonMark) are not recognized. Punchlist files never use indented fences. Tilde (`~~~`) fences are not recognized for the same reason.

### Integration: validate_punchlist.py

`parse_punchlist(content)` changes:

1. Call `mask_code_fences(content)` to get `(normalized, masked)`
2. Remove the existing `content.replace('\r\n', '\n')` line — the utility handles it
3. Find item headers (`### BH-NNN:`) in `masked` — this prevents FA-001
4. For each item, build two blocks:
   - `masked_block`: sliced from `masked` using positions from the masked-content header matches — used for field extraction (Severity, Category, Status, etc.) and checkbox detection
   - `original_block`: the corresponding slice from `normalized`, found by re-searching for the exact `### {ID}:` header in `normalized` — used for section content extraction (Problem, Evidence, Resolution) and validation command extraction
5. Field extraction regexes (lines 78-108) run against `masked_block` — prevents FA-003
6. Checkbox detection (line 115) runs against `masked_block` — prevents FA-005/FA-006
7. Section content regex and validation command regex run against `original_block` — preserves Evidence code fences

**Position mapping:** Masking blanks fence content but preserves line count, so the `### BH-NNN:` headers that appear outside fences exist at the same line positions in both `masked` and `normalized`. Character offsets differ (blanked lines are shorter), so the implementation finds all item headers in both `masked` and `normalized` independently, then pairs them by index — the match lists have identical length and ordering since masking only removes headers that are inside fences. The `original_block` for each item is sliced from `normalized` using the positions from the normalized match list.

**Validation command regex:** The validation command regex (`**Validation Command:**...```...````) is the one structural regex that must see fence delimiters to function. It runs against `original_block`, which preserves all fence content. This is explicitly called out because it is the exception to the "structural regexes use masked content" rule.

### Integration: convergence_check.py

`count_items(punchlist_path)` changes:

1. Read the file
2. Call `mask_code_fences(content)` to get `(normalized, masked)`
3. Remove the existing CRLF normalization line
4. Run the status regex against `masked` instead of raw content — prevents FA-009
5. `normalized` is unused (count_items doesn't need section content)

### Testing

**New: `tests/test_markdown_utils.py`** (~9 tests):
- Basic fence masking: content between ` ``` ` pairs becomes blank lines
- Fence delimiter lines themselves are blanked (not just content between them)
- Language-tagged fences (` ```python `): handled correctly
- Nested fences: 4-backtick fence containing 3-backtick content — inner backticks are content, not boundaries
- Unclosed fence at EOF: everything after opening fence is masked
- Fence on first line of file: handled correctly
- Content outside fences: untouched
- CRLF normalization: `\r\n` becomes `\n` in both outputs
- Return type: `(normalized, masked)` tuple, `normalized` preserves original content

**Updated: `tests/test_validate_punchlist.py`** (+3 tests):
- FA-001: `### BH-NNN:` inside a code fence does not create a phantom item
- FA-003: `**Status:** RESOLVED` inside a code fence does not poison extracted status
- FA-006: `- [ ]` inside a code fence does not satisfy acceptance criteria when no real AC section exists (FA-005 — checkboxes in wrong section outside fences — is a scoping issue beyond code-fence awareness; masking alone does not fix it since the checkbox is in unmasked content)

**Updated: `tests/test_convergence_check.py`** (+1 test):
- FA-009: `**Status:** OPEN` inside a code fence does not inflate the count

All existing 26 tests must continue to pass unchanged.

## File changes

| File | Change |
|------|--------|
| `skills/holtz/scripts/markdown_utils.py` | New. ~30 lines. |
| `skills/holtz/scripts/validate_punchlist.py` | Import utility. Restructure `parse_punchlist` to use masked/original split. Remove CRLF line. |
| `skills/holtz/scripts/convergence_check.py` | Import utility. Use masked content in `count_items`. Remove CRLF line. |
| `tests/test_markdown_utils.py` | New. ~9 tests. |
| `tests/test_validate_punchlist.py` | +3 tests. |
| `tests/test_convergence_check.py` | +1 test. |

No documentation changes. Masking is an internal implementation detail.

## Commit strategy

Single commit: `fix: add code-fence-aware parsing to prevent phantom items and field poisoning`

Punchlist item IDs FA-001, FA-003, FA-005, FA-006, FA-009 in the body.

# Holtz Punchlist
> Generated: 2026-03-23 | Project: holtz | Run: 13 | Baseline: 320 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM | 0 | 2 | 0 |
| LOW | 0 | 2 | 0 |

## Patterns

## Items

### BH-001: render_items uses masked offsets to index original content
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:341-352`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** `render_items()` calls `mask_code_fences(original_content)` to get `masked`, then uses `item_pattern.finditer(masked)` to find item headers. The `match.start()` returns character offsets in `masked`, but these are used directly to index `original_content` (line 351: `original_content[start:end]`). Since `mask_code_fences` replaces fenced code lines with empty strings `''`, the masked content is shorter than the original wherever code fences appear. For any item after a code fence, the offset will point to the wrong position in the original content, extracting incorrect markdown.

**Evidence:** `mask_code_fences` in `markdown_utils.py:50-69`: fenced lines become `''` (0 chars). A ````bash` line (7 chars) plus `echo test` (9 chars) plus ` ``` ` (3 chars) = 19 chars reduced to 0+0+0 = 0 chars (plus preserved newlines). After one item with a validation command, the second item's masked offset is ~19 chars less than its original offset. The existing `parse_punchlist` avoids this with `_masked_offset_to_norm` (line 107-112) which maps via line numbers — `render_items` lacks this.

**Discovery Chain:** render_items uses `match.start()` from masked regex → mask_code_fences replaces fenced lines with empty strings → character offsets diverge between masked and original → items after code fences extracted from wrong positions

**Acceptance Criteria:**
- [x] render_items extracts correct content for items that follow items containing code fences
- [x] Test: 3-item punchlist where item 2 has code fence, filter to item 3 only, verify item 3 content is correct

**Validation Command:**
```bash
python -m pytest tests/test_validate_punchlist.py -k "render" -v
```

**Resolution:** Added line-number-based offset mapping to render_items (same approach as parse_punchlist). Builds orig_line_offsets array, converts masked match positions to line numbers, then uses line offsets to index original_content. Test test_render_items_correct_offset_after_code_fences verifies 3-item punchlist with code fences.

### BH-002: README "What's inside" counts are stale
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:164`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** The "What's inside" line says "15 reference docs" but the actual count is 17 (merge-examples.md added today). It says "7,800 lines" but `wc -l` of all Python files totals 8,494.

**Evidence:** `ls skills/holtz/references/*.md | wc -l` = 17. `wc -l skills/holtz/scripts/*.py tests/*.py hooks/*.py | tail -1` = 8494.

**Discovery Chain:** README claims 15 reference docs → counted 17 on disk → merge-examples.md added today without updating count. README claims 7,800 lines → counted 8,494 → new scripts and expanded tests since last update.

**Acceptance Criteria:**
- [x] Reference doc count matches actual count
- [x] Line count is within 100 of actual wc -l total

**Validation Command:**
```bash
test $(ls skills/holtz/references/*.md | wc -l | tr -d ' ') -eq $(grep -oP '\d+ reference docs' README.md | grep -oP '^\d+') && echo "PASS" || echo "FAIL"
```

**Resolution:** Updated README.md "What's inside" line: 15→17 reference docs, 320→321 tests, 7,800→8,500 lines.

### BH-003: Ruff lint errors in test_pattern_brief_compact.py
**Severity:** LOW
**Category:** bug/logic
**Location:** `tests/test_pattern_brief_compact.py:3,52,56,65`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 3 (confidence: HIGH)

**Problem:** 4 ruff errors: 1 unsorted import (I001 at line 3), 3 ambiguous variable names `l` (E741 at lines 52, 56, 65). This file was committed without running the linter. All other test files are clean.

**Evidence:** `ruff check tests/test_pattern_brief_compact.py` shows 4 errors. The `l` variable is used in list comprehensions: `[l for l in output.strip().split('\n') ...]` — should be `line` or similar.

**Discovery Chain:** ruff check on full codebase → 4 errors all in new file → file committed without lint gate

**Acceptance Criteria:**
- [x] `ruff check tests/test_pattern_brief_compact.py` returns 0 errors
- [x] Variable names are unambiguous

**Validation Command:**
```bash
ruff check tests/test_pattern_brief_compact.py
```

**Resolution:** Added `# noqa: I001` to import line (conftest sys.path arrangement requires this order). Renamed `l` to `line` in 3 list comprehensions.

### BH-004: Filter command in SKILL.md omits RESOLVED from --filter-status
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `skills/holtz/SKILL.md:225`, `skills/holtz/SKILL.md:314`, `skills/holtz/references/justine-skill.md:258`, `skills/holtz/references/justine-skill.md:338`
**Status:** RESOLVED
**Lens:** semantic-fidelity
**Determinism:** deterministic

**Problem:** The filter command in 4 locations uses `--filter-status OPEN "IN PROGRESS" --resolved-before 3` without including RESOLVED in the status list. The `filter_items()` function applies the status filter first (line 300-301) — since RESOLVED is not in `status_include`, all RESOLVED items are excluded before the `resolved_before` check runs. The documented intent is "shows all OPEN/IN PROGRESS items plus the 3 most recently resolved items" but the actual output contains zero resolved items.

**Evidence:** In `filter_items()` (line 298-312): when `status_include={"OPEN", "IN PROGRESS"}`, any item with `status="RESOLVED"` hits the `continue` at line 301 and never reaches the recency check at lines 304-310. The fix is to include RESOLVED: `--filter-status OPEN "IN PROGRESS" RESOLVED --resolved-before 3`.

**Discovery Chain:** SKILL.md claims "shows OPEN/IN PROGRESS + 3 most recently resolved" → filter_items applies status filter before recency filter → RESOLVED not in status_include → all resolved items excluded → zero resolved items in output, contradicting documented behavior

**Acceptance Criteria:**
- [x] Filter command in all 4 locations includes RESOLVED in --filter-status
- [x] Running the corrected command on a punchlist with resolved items produces output containing recent resolved items

**Validation Command:**
```bash
grep -n 'filter-status.*OPEN.*IN PROGRESS' skills/holtz/SKILL.md skills/holtz/references/justine-skill.md | grep -v RESOLVED && echo "FAIL: RESOLVED missing" || echo "PASS"
```

**Resolution:** Added RESOLVED to --filter-status in all 4 locations (SKILL.md lines 225 and 314, justine-skill.md lines 258 and 338).

# Holtz Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 613 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 2 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 0 | 0 | 0 |

## Patterns

## Items

### BJ-001: parse_brief uses masked offsets to index original content -- extracts wrong data after code fences
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:59-60`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Lens:** integration, data-flow
**Predicted:** Prediction 4 (confidence: MEDIUM) -- seam bug between masking and extraction

**Problem:** `parse_brief()` finds pattern headers in `masked` content (line 55) but uses the masked match offsets to slice into `content` (original, line 60: `block = content[start:end]`). `mask_code_fences` replaces fenced lines with empty strings, making `masked` shorter than `content`. After the first code fence, all character offsets diverge. PAT entries after a code fence extract content from the wrong position, pulling text from inside code fences instead of the real entry. This is the same class of bug found in Run 13 (render_items offset divergence) and the sixth manifestation of PAT-001 in the project's history.

**Evidence:** Reproduction: create a patterns-brief.md with a code fence between two PAT entries. PAT-002's fields all extract as "fake" (the code-fenced content) instead of the real values:
```python
entries = parse_brief(content_with_code_fence_between_entries)
# PAT-002 what_to_look_for = 'fake'  (WRONG -- should be 'Look for B')
# PAT-002 detection_heuristic = 'fake'  (WRONG)
# PAT-002 example = 'fake\n```'  (WRONG)
# PAT-001 example = 'Example A\n\n```mark'  (content bleeds into fence)
```

**Discovery Chain:** Holtz recon noted PAT-001 recurrence in prior runs → checked parse_brief for same pattern: masked offsets indexing original content → confirmed with reproduction test: fields after code fence extract wrong data

**Acceptance Criteria:**
- [ ] parse_brief uses line-number mapping (not character offsets) between masked and original, same approach as validate_punchlist.py and render_items
- [ ] Test: patterns-brief with code fence between entries -- PAT entries after the fence extract correct field values
- [ ] Test: PAT entry before the fence does not bleed into fence content in its Example field

**Validation Command:**
```bash
python -m pytest tests/test_pattern_brief_compact.py -v -k "code_fence"
```

### BJ-002: mask_fenced_blocks in _common.py does not enforce minimum fence length for closing
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/_common.py:117-119`
**Status:** OPEN
**Determinism:** deterministic
**Pattern:** PAT-001
**Lens:** component, security

**Problem:** `mask_fenced_blocks()` stores `fence_marker = m.group(1)[0]` (line 117) which is just the single character (backtick or tilde). The closing check on line 119 (`line.strip().startswith(fence_marker)`) matches ANY line starting with that character, regardless of how many fence characters opened the block. Per CommonMark spec, a closing fence must have at least as many characters as the opening fence. A ```` (4-backtick) fence will be prematurely closed by ``` (3 backticks), exposing content that should be masked. This affects convergence_gate.py, convergence_primer.py, and status_staleness_gate.py -- any hook that processes markdown containing nested or variable-length code fences.

**Evidence:** Reproduction:
```python
from _common import mask_fenced_blocks
test = "Before\n````\ninside\n```\nstill inside\n````\nAfter"
masked = mask_fenced_blocks(test)
# Result: 'still inside' on line 4 is NOT masked (WRONG)
# '````' on line 5 opens a new fence that never closes (WRONG)
# 'After' on line 6 is incorrectly masked (WRONG)
# Correct: lines 2-5 should all be inside the fence, 'After' outside
```

**Discovery Chain:** comparing mask_fenced_blocks vs mask_code_fences implementations → noticed fence_marker stores single char not full marker → reproduction test confirms premature fence closure on shorter closer

**Acceptance Criteria:**
- [ ] mask_fenced_blocks stores the full fence marker string (e.g., "````") and checks that the closing line has at least as many fence characters
- [ ] Test: 4-backtick fence is NOT closed by 3 backticks
- [ ] Test: 3-backtick fence IS closed by 5 backticks (longer closer is valid per CommonMark)
- [ ] Test: tilde fence is NOT closed by backtick fence (already works but add regression test)

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -v -k "fence_length"
```

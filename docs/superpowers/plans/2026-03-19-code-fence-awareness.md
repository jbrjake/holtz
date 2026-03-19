# Code-Fence-Aware Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make validate_punchlist.py and convergence_check.py ignore markdown content inside fenced code blocks when extracting punchlist structure, preventing phantom items, field poisoning, false checkbox matches, and inflated convergence counts.

**Architecture:** A shared `markdown_utils.py` module provides a `mask_code_fences()` function that returns both the normalized original and a masked copy (code fence interiors replaced with blank lines). Structural parsing (item headers, field extraction, checkboxes) uses the masked copy. Content parsing (Problem/Evidence sections, validation commands) uses the original.

**Tech Stack:** Python 3 stdlib only (re). pytest for testing.

**Spec:** `docs/superpowers/specs/2026-03-19-code-fence-awareness-design.md`

**Note on FA-005:** FA-005 (checkboxes in wrong section *outside* fences, e.g., in Problem instead of Acceptance Criteria) is a scoping issue, not a code-fence issue. Masking does not fix it because the checkbox is in unmasked content. FA-005 remains deferred. This plan addresses FA-001, FA-003, FA-006, and FA-009.

**Commit strategy:** The spec suggests a single commit, but this plan uses 3 incremental commits (one per task) for easier bisection and review. Each commit leaves the test suite green.

---

### Task 1: Create `markdown_utils.py` with `mask_code_fences`

**Files:**
- Create: `skills/holtz/scripts/markdown_utils.py`
- Test: `tests/test_markdown_utils.py`

- [ ] **Step 1: Write the test file with all 9 tests**

Create `tests/test_markdown_utils.py`:

```python
"""Tests for markdown_utils.py."""

import markdown_utils as mu


def test_basic_fence_masking():
    """Content between ``` pairs becomes blank lines."""
    content = "before\n```\nfenced line 1\nfenced line 2\n```\nafter\n"
    normalized, masked = mu.mask_code_fences(content)
    assert normalized == content
    lines = masked.split("\n")
    assert lines[0] == "before"
    assert lines[1] == ""  # opening fence blanked
    assert lines[2] == ""  # content blanked
    assert lines[3] == ""  # content blanked
    assert lines[4] == ""  # closing fence blanked
    assert lines[5] == "after"


def test_fence_delimiters_are_blanked():
    """Opening and closing fence lines themselves are blanked, not just content."""
    content = "```python\ncode\n```\n"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == ""  # opening ```python blanked
    assert lines[1] == ""  # code blanked
    assert lines[2] == ""  # closing ``` blanked


def test_language_tagged_fence():
    """Fences with language tags (```python) are recognized."""
    content = "text\n```typescript\nconst x = 1;\n```\nmore text\n"
    normalized, masked = mu.mask_code_fences(content)
    assert normalized == content
    assert "const x = 1;" not in masked
    assert "more text" in masked
    assert "text" in masked


def test_nested_fences():
    """4-backtick fence containing 3-backtick content treats inner as content."""
    content = "before\n````\n```\ninner\n```\n````\nafter\n"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == "before"
    assert lines[1] == ""  # opening ```` blanked
    assert lines[2] == ""  # ``` is content, blanked
    assert lines[3] == ""  # inner blanked
    assert lines[4] == ""  # ``` is content, blanked
    assert lines[5] == ""  # closing ```` blanked
    assert lines[6] == "after"


def test_unclosed_fence_at_eof():
    """Unclosed fence masks everything from opening to EOF."""
    content = "before\n```\nunclosed content\nmore content"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == "before"
    assert lines[1] == ""  # opening ``` blanked
    assert lines[2] == ""  # content blanked
    assert lines[3] == ""  # content blanked


def test_fence_on_first_line():
    """Fence starting on the first line of the file is handled."""
    content = "```\nfenced\n```\nafter\n"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == ""  # opening ``` blanked
    assert lines[1] == ""  # content blanked
    assert lines[2] == ""  # closing ``` blanked
    assert lines[3] == "after"


def test_content_outside_fences_untouched():
    """Lines outside any fence are preserved exactly."""
    content = "line 1\nline 2\n```\nfenced\n```\nline 3\n"
    _, masked = mu.mask_code_fences(content)
    assert "line 1" in masked
    assert "line 2" in masked
    assert "line 3" in masked
    assert "fenced" not in masked


def test_crlf_normalization():
    """CRLF is normalized to LF in both outputs."""
    content = "line 1\r\nline 2\r\n```\r\nfenced\r\n```\r\n"
    normalized, masked = mu.mask_code_fences(content)
    assert "\r" not in normalized
    assert "\r" not in masked
    assert "line 1" in normalized
    assert "fenced" in normalized
    assert "fenced" not in masked


def test_return_tuple_normalized_preserves_content():
    """Normalized output preserves all original content with LF endings."""
    content = "```python\ncode_here\n```\n"
    normalized, masked = mu.mask_code_fences(content)
    assert "```python" in normalized
    assert "code_here" in normalized
    assert "code_here" not in masked
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_markdown_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'markdown_utils'`

- [ ] **Step 3: Write `markdown_utils.py`**

Create `skills/holtz/scripts/markdown_utils.py`:

```python
"""Shared markdown parsing utilities for Holtz scripts."""

import re


_FENCE_OPEN = re.compile(r'^(`{3,})[^`]*$')
_FENCE_CLOSE_TMPL = r'^`{%d,}[ \t]*$'


def mask_code_fences(content: str) -> tuple[str, str]:
    """Normalize line endings and produce a masked copy with code fence content blanked.

    Returns (normalized, masked) where:
    - normalized: original content with CRLF converted to LF
    - masked: same content but lines inside fenced code blocks replaced with empty lines
    """
    content = content.replace('\r\n', '\n')
    lines = content.split('\n')
    masked_lines = list(lines)

    fence_backtick_count = 0
    in_fence = False

    for i, line in enumerate(lines):
        if not in_fence:
            m = _FENCE_OPEN.match(line)
            if m:
                fence_backtick_count = len(m.group(1))
                in_fence = True
                masked_lines[i] = ''
        else:
            if re.match(_FENCE_CLOSE_TMPL % fence_backtick_count, line):
                masked_lines[i] = ''
                in_fence = False
            else:
                masked_lines[i] = ''

    return content, '\n'.join(masked_lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_markdown_utils.py -v`
Expected: All 9 PASS

- [ ] **Step 5: Run full suite to verify no regressions**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All 26 existing + 9 new = 35 PASS

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/scripts/markdown_utils.py tests/test_markdown_utils.py
git commit -m "feat: add mask_code_fences utility for code-fence-aware parsing

New shared module markdown_utils.py with a function that produces a
masked copy of markdown content where code fence interiors are replaced
with blank lines. Handles nested fences via backtick-count matching,
CRLF normalization, and unclosed fences.

Part of FA-001, FA-003, FA-006, FA-009."
```

---

### Task 2: Integrate masking into `validate_punchlist.py`

**Files:**
- Modify: `skills/holtz/scripts/validate_punchlist.py:15,62-126`
- Test: `tests/test_validate_punchlist.py`

- [ ] **Step 1: Write 3 failing tests for FA-001, FA-003, FA-006**

Append to `tests/test_validate_punchlist.py`:

```python
# --- FA-001: Phantom item inside code fence ---

def test_item_header_inside_code_fence_ignored():
    """### BH-NNN: inside a code fence should not create a phantom item."""
    content = """\
### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:**
```markdown
### BH-002: This is an example inside a code fence, not a real item
**Status:** RESOLVED
```

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1, f"Expected 1 item, got {len(items)}: {[i.id for i in items]}"
    assert items[0].id == "BH-001"


# --- FA-003: Field poisoning from code fence ---

def test_status_inside_code_fence_not_extracted():
    """**Status:** inside a code fence should not poison the real status."""
    content = """\
### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:**
```
**Status:** RESOLVED
```

**Status:** OPEN

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert items[0].status == "OPEN", f"Expected OPEN, got '{items[0].status}'"


# --- FA-006: Checkbox inside code fence ---

def test_checkbox_inside_code_fence_not_counted():
    """- [ ] inside a code fence should not satisfy acceptance criteria."""
    content = """\
### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:**
```markdown
- [ ] this checkbox is inside a code fence
- [x] so is this one
```

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert not items[0].has_acceptance_criteria, (
        "Checkbox inside code fence should not count as acceptance criteria"
    )
```

- [ ] **Step 2: Run the 3 new tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_validate_punchlist.py::test_item_header_inside_code_fence_ignored tests/test_validate_punchlist.py::test_status_inside_code_fence_not_extracted tests/test_validate_punchlist.py::test_checkbox_inside_code_fence_not_counted -v`
Expected: All 3 FAIL

- [ ] **Step 3: Modify `parse_punchlist` to use masked/original split**

In `skills/holtz/scripts/validate_punchlist.py`, make these changes:

**Add import** (after line 15 `import re`):
```python
from markdown_utils import mask_code_fences
```

**Replace the entire `parse_punchlist` function** (lines 62-126) with:

```python
def parse_punchlist(content: str) -> list[PunchlistItem]:
    """Parse markdown punchlist into structured items."""
    normalized, masked = mask_code_fences(content)
    items = []
    # Split on item headers (### BH-NNN: title) in masked content
    # so headers inside code fences are not matched
    item_pattern = re.compile(r'^### (BH-\d+):\s+(.+)$', re.MULTILINE)
    masked_matches = list(item_pattern.finditer(masked))

    # Build an index of header positions in normalized content by ID.
    # normalized may contain phantom headers inside code fences that
    # masked does not, so we cannot pair by array index — we match by ID.
    norm_matches_by_id: dict[str, list[re.Match]] = {}
    for m in item_pattern.finditer(normalized):
        norm_matches_by_id.setdefault(m.group(1), []).append(m)

    for i, match in enumerate(masked_matches):
        item_id = match.group(1)
        masked_start = match.end()
        masked_end = masked_matches[i + 1].start() if i + 1 < len(masked_matches) else len(masked)
        masked_block = masked[masked_start:masked_end]

        # Find this item's header in normalized content by ID.
        # Use the first match for this ID (real headers appear before any
        # phantom copies in code fences, since code fences are in Evidence
        # sections which come after the header).
        norm_match = norm_matches_by_id.get(item_id, [None])[0]
        if norm_match:
            norm_start = norm_match.end()
            # Find end: next real item's position in normalized, or EOF
            next_id = masked_matches[i + 1].group(1) if i + 1 < len(masked_matches) else None
            if next_id and next_id in norm_matches_by_id:
                norm_end = norm_matches_by_id[next_id][0].start()
            else:
                norm_end = len(normalized)
            original_block = normalized[norm_start:norm_end]
        else:
            original_block = masked_block  # fallback (shouldn't happen)

        item = PunchlistItem(id=match.group(1), title=match.group(2).strip())

        # Extract fields from masked block (code fence content hidden)
        sev = re.search(r'\*\*Severity:\*\*[ \t]*(\w+)', masked_block)
        if sev:
            item.severity = sev.group(1)

        cat = re.search(r'\*\*Category:\*\*[ \t]*(.+)', masked_block)
        if cat:
            item.category = cat.group(1).strip()

        loc = re.search(r'\*\*Location:\*\*[ \t]*(.+)', masked_block)
        if loc:
            item.location = loc.group(1).strip()

        stat = re.search(r'\*\*Status:\*\*[ \t]*(\w[\w ]*\w)', masked_block)
        if stat:
            item.status = stat.group(1).strip()

        pat = re.search(r'\*\*Pattern:\*\*[ \t]*(PAT-\d+)', masked_block)
        if pat:
            item.pattern = pat.group(1)

        det = re.search(r'\*\*Determinism:\*\*[ \t]*(\w+)', masked_block)
        if det:
            item.determinism = det.group(1).strip()

        inv = re.search(r'\*\*Investigation:\*\*[ \t]*(.+)', masked_block)
        if inv:
            item.investigation = inv.group(1).strip()

        rcc = re.search(r'\*\*Root Cause Confidence:\*\*[ \t]*(\w+)', masked_block)
        if rcc:
            item.root_cause_confidence = rcc.group(1).strip()

        # Section content and validation command use original block
        # (Evidence sections contain code fences with the actual evidence)
        section_re = r'\*\*%s:\*\*[ \t]*((?:[^\n]*(?:\n(?!\*\*\w)[^\n]*)*))'
        problem_m = re.search(section_re % 'Problem', original_block)
        item.has_problem = bool(problem_m and len(problem_m.group(1).strip()) > 10)
        evidence_m = re.search(section_re % 'Evidence', original_block)
        item.has_evidence = bool(evidence_m and len(evidence_m.group(1).strip()) > 10)

        # Checkbox detection uses masked block (ignore checkboxes in code fences)
        item.has_acceptance_criteria = '- [ ]' in masked_block or '- [x]' in masked_block or '- [X]' in masked_block

        # Validation command uses original block (the command IS in a code fence)
        val_cmd = re.search(r'\*\*Validation Command:\*\*[ \t]*\n?```\w*\n(.+?)\n```', original_block, re.DOTALL)
        if val_cmd:
            item.validation_command = val_cmd.group(1).strip()
        item.has_validation_command = bool(item.validation_command)

        resolution_m = re.search(section_re % 'Resolution', original_block)
        item.has_resolution = bool(resolution_m and len(resolution_m.group(1).strip()) > 5)

        items.append(item)

    return items
```

- [ ] **Step 4: Run the 3 new tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/test_validate_punchlist.py::test_item_header_inside_code_fence_ignored tests/test_validate_punchlist.py::test_status_inside_code_fence_not_extracted tests/test_validate_punchlist.py::test_checkbox_inside_code_fence_not_counted -v`
Expected: All 3 PASS

- [ ] **Step 5: Run full suite to verify no regressions**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All 38 PASS (26 existing + 9 markdown_utils + 3 new validator)

- [ ] **Step 6: Validate sample punchlist still works**

Run: `source .venv/bin/activate && python skills/holtz/scripts/validate_punchlist.py skills/holtz/examples/sample-punchlist.md`
Expected: 6 items, 0 errors, 1 warning (BH-004 deferred without investigation)

- [ ] **Step 7: Commit**

```bash
git add skills/holtz/scripts/validate_punchlist.py tests/test_validate_punchlist.py
git commit -m "fix(validate): use masked content for structural parsing

Integrate mask_code_fences into parse_punchlist so item headers, field
values, and checkboxes inside code fences are ignored. Section content
and validation commands still use original content.

Fixes FA-001, FA-003, FA-006."
```

---

### Task 3: Integrate masking into `convergence_check.py`

**Files:**
- Modify: `skills/holtz/scripts/convergence_check.py:12,23-37`
- Test: `tests/test_convergence_check.py`

- [ ] **Step 1: Write 1 failing test for FA-009**

Append to `tests/test_convergence_check.py`:

```python
# --- FA-009: Status inside code fence inflates count ---

def test_status_inside_code_fence_not_counted(tmp_path):
    """**Status:** inside a code fence should not inflate the item count."""
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text("""\
### BH-001: Real item
**Status:** OPEN

**Evidence:**
```
**Status:** OPEN
**Status:** RESOLVED
```
""")
    counts = cc.count_items(punchlist)
    assert counts["OPEN"] == 1, f"Expected 1 OPEN, got {counts}"
    assert counts["RESOLVED"] == 0, f"Expected 0 RESOLVED, got {counts}"
    assert counts["total"] == 1, f"Expected total 1, got {counts}"
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_convergence_check.py::test_status_inside_code_fence_not_counted -v`
Expected: FAIL — `counts["OPEN"]` is 2 or 3

- [ ] **Step 3: Modify `count_items` to use masked content**

In `skills/holtz/scripts/convergence_check.py`, make these changes:

**Add import** (after line 12 `import re`):
```python
from markdown_utils import mask_code_fences
```

**Replace `count_items` function** (lines 23-37) with:

```python
def count_items(punchlist_path: Path) -> dict:
    """Count punchlist items by status."""
    content = punchlist_path.read_text() if punchlist_path.exists() else ""
    _, masked = mask_code_fences(content)
    counts = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0}

    for match in re.finditer(r'\*\*Status:\*\*[ \t]*(\w[\w ]*\w)', masked):
        status = match.group(1).strip()
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1

    counts["total"] = sum(counts.values())
    return counts
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_convergence_check.py::test_status_inside_code_fence_not_counted -v`
Expected: PASS

- [ ] **Step 5: Run full suite to verify no regressions**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All 39 PASS (26 existing + 9 markdown_utils + 3 validator + 1 convergence)

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/scripts/convergence_check.py tests/test_convergence_check.py
git commit -m "fix(convergence): use masked content for status counting

Integrate mask_code_fences into count_items so **Status:** fields inside
code fences are not counted toward convergence metrics.

Fixes FA-009."
```

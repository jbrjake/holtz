"""Tests for validate_punchlist.py."""

import validate_punchlist as vp


# --- BH-001: Section regex eating adjacent sections on empty headers ---

def test_empty_problem_adjacent_to_evidence():
    """Empty Problem section should not capture Evidence content."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:**
**Evidence:** This is real evidence content here.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    item = items[0]
    # Problem section is empty — should NOT have content from Evidence
    assert not item.has_problem, (
        f"Empty Problem section should be detected as empty, "
        f"not filled with Evidence content"
    )
    assert item.has_evidence


def test_empty_evidence_adjacent_to_acceptance():
    """Empty Evidence section should not capture Acceptance Criteria content."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem description with enough content.

**Evidence:**
**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    item = items[0]
    assert item.has_problem
    assert not item.has_evidence, "Empty Evidence should be detected as empty"


def test_normal_sections_still_work():
    """Normal well-formatted sections should parse correctly."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug
- [ ] Verify fix

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    item = items[0]
    assert item.has_problem
    assert item.has_evidence
    assert item.has_acceptance_criteria
    assert item.has_validation_command


# --- BH-003: Status regex cross-line leak ---

def test_status_single_line_extraction():
    """Status should be extracted from single line only, not leak across lines."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN
Some annotation text on next line

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert items[0].status == "OPEN", (
        f"Status should be 'OPEN', got '{items[0].status}'"
    )


def test_status_in_progress():
    """IN PROGRESS (two words) should be correctly extracted."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** IN PROGRESS

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert items[0].status == "IN PROGRESS"


# --- BH-004: Duplicate ID detection ---

def test_duplicate_ids_detected():
    """Duplicate item IDs should produce validation errors."""
    content = """\
### BH-001: First item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** First problem description with enough detail to pass validation.

**Evidence:** First evidence with enough detail to pass validation check.

**Acceptance Criteria:**
- [ ] Fix it

**Validation Command:**
```bash
echo test
```

### BH-001: Second item with same ID
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `file.py:2`
**Status:** OPEN

**Problem:** Second problem description with enough detail to pass validation.

**Evidence:** Second evidence with enough detail to pass validation check.

**Acceptance Criteria:**
- [ ] Fix it too

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    result = vp.validate(items)
    # Should have an error about duplicate IDs
    dup_errors = [e for e in result.errors if "duplicate" in e.lower()]
    assert len(dup_errors) > 0, (
        f"Expected duplicate ID error, got errors: {result.errors}"
    )


# --- BH-010: Empty punchlist validation ---

def test_empty_punchlist_parse():
    """Parsing a file with no items should return empty list."""
    content = "# Just a title\nNo items here\n"
    items = vp.parse_punchlist(content)
    assert items == []


# --- BH-014: File structure validation ---

def test_missing_file_structure():
    """Validator should warn when required top-level sections are missing."""
    # A punchlist with items but no proper structure
    content = """\
### BH-001: An item without proper file structure
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    result = vp.validate(items, content)
    # Should have warnings about missing structure
    structure_warnings = [w for w in result.warnings if "header" in w.lower() or "structure" in w.lower() or "section" in w.lower()]
    assert len(structure_warnings) > 0, (
        f"Expected structure warnings, got warnings: {result.warnings}"
    )


# --- CS2-001: Empty Category field should not capture next line ---

def test_empty_category_does_not_capture_next_line():
    """Empty Category field should result in missing category, not capturing Location."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:**
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    result = vp.validate(items)
    # Should have a missing category error, not a non-standard category warning
    cat_errors = [e for e in result.errors if "category" in e.lower()]
    assert len(cat_errors) > 0, (
        f"Expected missing category error, got errors: {result.errors}, warnings: {result.warnings}"
    )


# --- CS2-003: Validation command must have actual content ---

def test_validation_command_empty_code_block():
    """Validation command header without actual command content should fail."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert not items[0].has_validation_command, (
        "Validation command header without code block should not pass"
    )


# --- FA-002: CRLF line endings ---

def test_crlf_line_endings():
    """CRLF files should be parsed correctly."""
    content = (
        "### BH-001: Test item\r\n"
        "**Severity:** HIGH\r\n"
        "**Category:** bug/logic\r\n"
        "**Location:** `file.py:1`\r\n"
        "**Status:** OPEN\r\n"
        "\r\n"
        "**Problem:** This is a real problem that describes what went wrong in enough detail.\r\n"
        "\r\n"
        "**Evidence:** Here is the evidence showing the problem with code references.\r\n"
        "\r\n"
        "**Acceptance Criteria:**\r\n"
        "- [ ] Fix the bug\r\n"
        "\r\n"
        "**Validation Command:**\r\n"
        "```bash\r\n"
        "echo test\r\n"
        "```\r\n"
    )
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    item = items[0]
    assert item.severity == "HIGH"
    assert item.status == "OPEN"
    assert item.has_problem
    assert item.has_validation_command, "CRLF file should still detect validation command"


# --- FA-004: Bold text on continuation line truncates section ---

def test_bold_text_in_problem_continuation():
    """Bold text on continuation lines should not truncate the section."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** Found a bug where the system fails when
**bold emphasis** is used in the description and continues here with more detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert items[0].has_problem, (
        "Problem with bold continuation line should not be truncated"
    )


# --- BH-003: section_re truncates on bold continuation lines ---

def test_bold_continuation_full_content():
    """Problem where all meaningful content starts with bold should still be detected."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** Short.
**This is important context** that continues the problem description with
enough detail to matter. Without this content the problem is incomplete.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    # The Problem section has "Short." on the first line (6 chars, under 10 threshold)
    # and the real content on bold continuation lines. If the regex truncates at
    # the bold line, has_problem is False because "Short." is too short.
    assert items[0].has_problem, (
        "Problem with meaningful content on bold continuation lines should be detected"
    )


# --- FA-014: Invalid severity validation ---

def test_invalid_severity_produces_error():
    """Invalid severity value should produce a validation error."""
    content = """\
### BH-001: Test item
**Severity:** URGENT
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    result = vp.validate(items)
    sev_errors = [e for e in result.errors if "severity" in e.lower()]
    assert len(sev_errors) > 0, (
        f"Expected invalid severity error, got errors: {result.errors}"
    )


# --- FA-015: RESOLVED without resolution ---

def test_resolved_without_resolution_produces_error():
    """RESOLVED item without Resolution section should produce error."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** RESOLVED

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [x] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    result = vp.validate(items)
    res_errors = [e for e in result.errors if "resolution" in e.lower() or "resolved" in e.lower()]
    assert len(res_errors) > 0, (
        f"Expected resolved-without-resolution error, got errors: {result.errors}"
    )


# --- FA-017: Normal item should produce zero errors ---

def test_well_formed_item_no_errors():
    """A well-formed item should produce zero validation errors."""
    content = """\
# Holtz Punchlist
> Generated: 2026-03-19 | Project: test | Baseline: 10 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 1 | 0 | 0 |

## Patterns

## Items

### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    result = vp.validate(items, content)
    assert len(result.errors) == 0, (
        f"Well-formed item should have zero errors, got: {result.errors}"
    )


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


# --- FA-005: Checkbox in wrong section outside fence ---

def test_checkbox_in_wrong_section_not_counted():
    """- [ ] in Problem section should not satisfy acceptance criteria."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** Here is a checklist in the wrong section:
- [ ] not a real acceptance criterion
- [ ] also not

**Evidence:** Here is the evidence showing the problem with code references.

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert not items[0].has_acceptance_criteria, (
        "Checkbox in Problem section should not count as acceptance criteria"
    )


# --- BH-001: Code fence content poisons original_block field extraction ---

def test_resolution_inside_code_fence_not_extracted():
    """**Resolution:** inside a code fence should not satisfy has_resolution."""
    content = """\
### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:**
```markdown
**Resolution:** Fixed in commit abc123. This is example text inside a code fence.
```

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    assert not items[0].has_resolution, (
        "**Resolution:** inside a code fence should not satisfy has_resolution"
    )


def test_problem_inside_code_fence_not_extracted():
    """**Problem:** inside a code fence should not satisfy has_problem for a different item."""
    content = """\
### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:**
**Evidence:** Here is the real evidence, which includes an example:
```markdown
**Problem:** This fake problem text is inside a code fence and should not count.
```

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    # The real Problem section is empty (just the header with nothing after it)
    assert not items[0].has_problem, (
        "**Problem:** inside a code fence should not satisfy has_problem"
    )


# --- BH-002: Phantom header with same ID corrupts boundary matching ---

def test_phantom_same_id_before_real_item():
    """Code fence example with same ID before real item should not corrupt parsing."""
    content = """\
Here is an example of a punchlist item:
````markdown
### BH-001: Example item
**Severity:** CRITICAL
**Status:** RESOLVED
**Resolution:** Fixed in commit abc123. Verified and deployed.
````

### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is the real problem description with enough detail to pass validation.

**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1, f"Expected 1 item, got {len(items)}: {[i.id for i in items]}"
    item = items[0]
    assert item.severity == "HIGH", f"Expected HIGH, got '{item.severity}'"
    assert item.status == "OPEN", f"Expected OPEN, got '{item.status}'"
    assert item.has_problem, "Real item should have problem"
    assert not item.has_resolution, "Real item should NOT have resolution from phantom"


def test_phantom_same_id_problem_content_from_phantom():
    """Phantom with same ID should not provide Problem content to real item."""
    content = """\
Here is an example:
````markdown
### BH-001: Example
**Problem:** This is a long fake problem description that lives inside a code fence example.
**Status:** RESOLVED
````

### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:**
**Evidence:** Here is the evidence showing the problem with code references.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 1
    item = items[0]
    # The real item's Problem section is empty. The phantom inside the code fence
    # has a long Problem, but it should NOT count for the real item.
    assert not item.has_problem, (
        "Empty Problem on real item should not be filled by phantom's Problem from code fence"
    )


# --- BH-009: Multi-item punchlist parsing ---

def test_multi_item_field_isolation():
    """Multiple items should have isolated field values, no cross-contamination."""
    content = """\
### BH-001: First item
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `auth.py:1`
**Status:** RESOLVED

**Problem:** SQL injection in user search allows arbitrary query execution.

**Evidence:** Direct string interpolation of user input into SQL query.

**Acceptance Criteria:**
- [x] Parameterized queries used
- [x] Injection test passes

**Validation Command:**
```bash
pytest -k injection
```

**Resolution:** Fixed in commit abc123. Parameterized query validated by test.

### BH-002: Second item
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:15`
**Status:** OPEN

**Problem:** README claims feature X exists but it was removed in v2.

**Evidence:** grep for feature X in codebase returns no results.

**Acceptance Criteria:**
- [ ] README updated to remove feature X reference

**Validation Command:**
```bash
grep -r "feature X" README.md
```

### BH-003: Third item
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `utils.py:42`
**Status:** DEFERRED
**Determinism:** theoretical

**Problem:** Edge case with empty input array not covered by any test.

**Evidence:** Code review shows no test passes empty array to process_items().

**Acceptance Criteria:**
- [ ] Test for empty input array added

**Validation Command:**
```bash
pytest -k empty_input
```
"""
    items = vp.parse_punchlist(content)
    assert len(items) == 3, f"Expected 3 items, got {len(items)}"

    assert items[0].id == "BH-001"
    assert items[0].severity == "CRITICAL"
    assert items[0].category == "bug/security"
    assert items[0].status == "RESOLVED"
    assert items[0].has_resolution

    assert items[1].id == "BH-002"
    assert items[1].severity == "LOW"
    assert items[1].category == "doc/drift"
    assert items[1].status == "OPEN"
    assert not items[1].has_resolution

    assert items[2].id == "BH-003"
    assert items[2].severity == "MEDIUM"
    assert items[2].status == "DEFERRED"
    assert items[2].determinism == "theoretical"

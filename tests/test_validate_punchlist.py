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

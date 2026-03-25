"""Tests for pattern_brief_compact.py."""

import pattern_brief_compact as pbc  # noqa: I001


SAMPLE_BRIEF = """\
# Holtz Pattern Brief

> Read this before starting any audit work. These patterns were discovered
> in prior audits of this project. Check for them in the code you're reviewing.

## PAT-001: missing-edge-case-handling (Run 3, 2026-03-10)
**What to look for:** Functions with early return on happy path that lack guards for null, empty, or boundary inputs. The error path exists but is never reached.
**Detection heuristic:** `grep -rn 'if.*return' --include='*.py' | grep -v 'None\\|empty\\|boundary'`
**Example:** A validation function returns True for valid input but has no branch for empty string — callers assume empty string is valid.

## PAT-002: dual-parser-divergence (Run 5, 2026-03-15)
**What to look for:** Two or more functions that parse, extract, or deserialize from the same data format with different edge-case handling. One handles quoting/escaping, the other does not.
**Detection heuristic:** Find pairs of parse/extract/decode functions targeting the same format. Compare their handling of empty input, special characters, and nested structures.
**Example:** A report generator and a data validator both parse key-value text — one strips quotes, the other preserves them.

## PAT-003: code-fence-unaware-parsing (Run 5, 2026-03-15)
**What to look for:** Regex or string matching applied to document content without first masking or stripping fenced/quoted/literal blocks. Content inside code blocks matches patterns meant for the document layer.
**Detection heuristic:** `grep -rn 're\\.search.*content' --include='*.py'` then check: is there a mask/strip step before the regex?
**Example:** A heading extractor matches `# comment` inside a code block as a real heading.
"""


def test_parse_brief_entries():
    """Parse patterns-brief format into structured entries."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    assert len(entries) == 3
    assert entries[0].pattern_id == "PAT-001"
    assert entries[0].name == "missing-edge-case-handling"
    assert entries[0].run == "Run 3"
    assert "early return" in entries[0].what_to_look_for
    assert "grep" in entries[0].detection_heuristic
    assert "validation function" in entries[0].example


def test_parse_brief_empty():
    """Empty or header-only brief returns no entries."""
    header_only = "# Holtz Pattern Brief\n\n> Read this before starting.\n"
    entries = pbc.parse_brief(header_only)
    assert len(entries) == 0


def test_format_oneliner():
    """Oneliner format: one pipe-delimited line per pattern."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="oneliner")
    lines = [line for line in output.strip().split('\n') if line.strip() and not line.startswith('#')]
    assert len(lines) == 3
    assert "PAT-001" in lines[0]
    assert "|" in lines[0]
    assert all(len(line) < 200 for line in lines)


def test_format_twoliner():
    """Twoliner format: description + detection on two lines."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="twoliner")
    assert "PAT-001" in output
    assert "Detect:" in output
    content_lines = [line for line in output.strip().split('\n') if line.strip()]
    assert len(content_lines) >= 6  # 3 entries x 2 lines


def test_format_structured():
    """Structured format: header + look for + detect + example."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="structured")
    assert "## PAT-001" in output
    assert "Look for:" in output
    assert "Detect:" in output
    assert "e.g.:" in output


# --- BH-004 (run 14): Empty field value causes content bleed ---

def test_parse_brief_empty_field_value():
    """Field with no value on its line returns empty string, not next field's content."""
    brief = (
        "## PAT-001: test-pattern (Run 1, 2026-03-20)\n"
        "**What to look for:**\n"
        "**Detection heuristic:** `grep -rn 'foo' .`\n"
        "**Example:** A test case\n"
    )
    entries = pbc.parse_brief(brief)
    assert len(entries) == 1
    assert entries[0].what_to_look_for == "", (
        f"Expected empty string for field with no value, got: {entries[0].what_to_look_for!r}"
    )
    assert "`grep" in entries[0].detection_heuristic
    assert "test case" in entries[0].example


# --- BH-005 (run 14): Code fence header matched as real entry ---

def test_parse_brief_ignores_code_fenced_headers():
    """Pattern headers inside code fences are not matched as real entries."""
    brief = (
        "## PAT-001: real-pattern (Run 1, 2026-03-20)\n"
        "**What to look for:** Real description\n"
        "**Detection heuristic:** `grep something`\n"
        "**Example:** Real example\n"
        "\n"
        "```\n"
        "## PAT-999: fake-pattern (Run 99, 2099-01-01)\n"
        "**What to look for:** This should not be parsed\n"
        "```\n"
        "\n"
        "## PAT-002: second-real (Run 2, 2026-03-21)\n"
        "**What to look for:** Second real pattern\n"
        "**Detection heuristic:** manual check\n"
        "**Example:** Second example\n"
    )
    entries = pbc.parse_brief(brief)
    ids = [e.pattern_id for e in entries]
    assert "PAT-999" not in ids, "Code fence header should not be matched as a real entry"
    assert ids == ["PAT-001", "PAT-002"], f"Expected only real entries, got: {ids}"


# --- BH-003 (run 16): Masked offsets index original content after code fence ---

def test_parse_brief_fields_correct_after_code_fence():
    """Fields for entries AFTER a code fence must extract from the correct position.

    parse_brief uses finditer(masked) to locate headers but content[start:end]
    to extract fields. mask_code_fences replaces fenced lines with empty strings,
    so character offsets diverge. This test verifies field values are correct,
    not just that the right IDs are found.
    BH-003 run 16, PAT-001.
    """
    brief = (
        "## PAT-001: first-pattern (Run 1, 2026-03-20)\n"
        "**What to look for:** First description\n"
        "**Detection heuristic:** `grep first`\n"
        "**Example:** First example\n"
        "\n"
        "```python\n"
        "## PAT-999: fake (Run 99, 2099-01-01)\n"
        "**What to look for:** This is inside a code fence\n"
        "**Detection heuristic:** fake detection\n"
        "some more fenced content here that pads the offset\n"
        "```\n"
        "\n"
        "## PAT-002: second-pattern (Run 2, 2026-03-21)\n"
        "**What to look for:** Second description\n"
        "**Detection heuristic:** `grep second`\n"
        "**Example:** Second example\n"
    )
    entries = pbc.parse_brief(brief)
    assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"

    # PAT-002's fields must come from the REAL entry, not the fenced content
    pat2 = entries[1]
    assert pat2.pattern_id == "PAT-002"
    assert "Second description" in pat2.what_to_look_for, (
        f"PAT-002 what_to_look_for is wrong: {pat2.what_to_look_for!r}"
    )
    assert "grep second" in pat2.detection_heuristic, (
        f"PAT-002 detection_heuristic is wrong: {pat2.detection_heuristic!r}"
    )
    assert "Second example" in pat2.example, (
        f"PAT-002 example is wrong: {pat2.example!r}"
    )

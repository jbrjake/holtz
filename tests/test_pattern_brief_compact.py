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

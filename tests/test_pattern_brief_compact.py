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


# --- BH-017 (run 26): _truncate output must not exceed max_len ---

class TestTruncate:
    """BH-017: _truncate must respect max_len including the '...' suffix."""

    def test_short_text_unchanged(self):
        assert pbc._truncate("short", 10) == "short"

    def test_long_word_respects_limit(self):
        result = pbc._truncate("verylongword", 5)
        assert len(result) <= 5

    def test_word_boundary_respects_limit(self):
        result = pbc._truncate("abc def ghi jkl", 8)
        assert len(result) <= 8
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        assert pbc._truncate("exact", 5) == "exact"

    def test_ellipsis_present_on_truncation(self):
        result = pbc._truncate("a long sentence here", 10)
        assert result.endswith("...")
        assert len(result) <= 10


# --- format_compact edge cases ---


def test_format_compact_empty_entries():
    """format_compact with no entries returns 'No patterns' message (line 130)."""
    output = pbc.format_compact([], fmt="structured")
    assert "No patterns recorded" in output


def test_format_compact_unknown_format():
    """format_compact with invalid format raises ValueError (line 158)."""
    import pytest
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    with pytest.raises(ValueError, match="Unknown format"):
        pbc.format_compact(entries, fmt="bogus")


# --- CLI main() in-process tests ---


class TestPatternBriefCLI:
    """In-process CLI tests for coverage of main() (lines 164-189)."""

    @staticmethod
    def _run_main(args, capsys):
        import contextlib
        import pytest
        exit_code = 0
        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr("sys.argv", ["pattern_brief_compact.py"] + args)
                pbc.main()
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
        return exit_code, capsys.readouterr()

    def test_cli_default_format(self, tmp_path, capsys):
        """CLI with valid brief outputs structured format by default."""
        brief_file = tmp_path / "patterns-brief.md"
        brief_file.write_text(SAMPLE_BRIEF)
        code, captured = self._run_main([str(brief_file)], capsys)
        assert code == 0
        assert "PAT-001" in captured.out
        assert "Look for:" in captured.out  # structured format

    def test_cli_oneliner_format(self, tmp_path, capsys):
        """CLI --format oneliner produces pipe-delimited output."""
        brief_file = tmp_path / "patterns-brief.md"
        brief_file.write_text(SAMPLE_BRIEF)
        code, captured = self._run_main([str(brief_file), "--format", "oneliner"], capsys)
        assert code == 0
        assert "|" in captured.out

    def test_cli_missing_file(self, tmp_path, capsys):
        """CLI with nonexistent file exits 0 (not an error on early runs)."""
        code, captured = self._run_main([str(tmp_path / "nope.md")], capsys)
        assert code == 0
        assert "No pattern brief" in captured.err

    def test_cli_empty_brief(self, tmp_path, capsys):
        """CLI with brief containing no patterns exits 0."""
        brief_file = tmp_path / "patterns-brief.md"
        brief_file.write_text("# Just a header\n\nNo patterns here.\n")
        code, captured = self._run_main([str(brief_file)], capsys)
        assert code == 0
        assert "No patterns in brief" in captured.err

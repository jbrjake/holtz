"""Structural tests for compact pattern brief formats (CI-safe, no LLM calls)."""

import pattern_brief_compact as pbc

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


def test_all_formats_contain_all_pattern_ids():
    """Every pattern ID must appear in every format's output."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    for fmt in ("oneliner", "twoliner", "structured"):
        output = pbc.format_compact(entries, fmt=fmt)
        for entry in entries:
            assert entry.pattern_id in output, f"{fmt}: missing {entry.pattern_id}"


def test_twoliner_and_structured_contain_heuristics():
    """Twoliner and structured formats must include detection heuristics."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    for fmt in ("twoliner", "structured"):
        output = pbc.format_compact(entries, fmt=fmt)
        assert output.count("Detect:") == len(entries), f"{fmt}: missing Detect lines"


def test_structured_contains_all_fields():
    """Structured format has Look for + Detect + e.g. for each entry."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    output = pbc.format_compact(entries, fmt="structured")
    assert output.count("Look for:") == len(entries)
    assert output.count("Detect:") == len(entries)
    assert output.count("e.g.:") == len(entries)


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def test_all_formats_smaller_than_full():
    """Every compact format must be smaller than the full brief."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    full_size = _approx_tokens(SAMPLE_BRIEF)
    for fmt in ("oneliner", "twoliner", "structured"):
        compact = pbc.format_compact(entries, fmt=fmt)
        assert _approx_tokens(compact) < full_size, f"{fmt} not smaller"


def test_size_ordering():
    """oneliner < twoliner < structured in output size."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    sizes = {fmt: len(pbc.format_compact(entries, fmt=fmt))
             for fmt in ("oneliner", "twoliner", "structured")}
    assert sizes["oneliner"] < sizes["twoliner"] < sizes["structured"]


def test_key_terms_preserved_across_formats():
    """Each format preserves the distinctive terms that distinguish patterns."""
    entries = pbc.parse_brief(SAMPLE_BRIEF)
    for fmt in ("oneliner", "twoliner", "structured"):
        output = pbc.format_compact(entries, fmt=fmt).lower()
        assert any(t in output for t in ['early return', 'edge case', 'boundary', 'null']), \
            f"{fmt}: PAT-001 lost distinguishing terms"
        assert any(t in output for t in ['parser', 'format', 'deserialize', 'diverge']), \
            f"{fmt}: PAT-002 lost distinguishing terms"

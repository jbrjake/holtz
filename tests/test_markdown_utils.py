"""Tests for markdown_utils.py."""

import markdown_utils as mu


def test_basic_fence_masking():
    """Content between ``` pairs becomes blank lines."""
    content = "before\n```\nfenced line 1\nfenced line 2\n```\nafter\n"
    normalized, masked = mu.mask_code_fences(content)
    assert normalized == content
    lines = masked.split("\n")
    assert lines[0] == "before"
    assert lines[1] == ""
    assert lines[2] == ""
    assert lines[3] == ""
    assert lines[4] == ""
    assert lines[5] == "after"


def test_fence_delimiters_are_blanked():
    """Opening and closing fence lines themselves are blanked, not just content."""
    content = "```python\ncode\n```\n"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == ""
    assert lines[1] == ""
    assert lines[2] == ""


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
    assert lines[1] == ""
    assert lines[2] == ""
    assert lines[3] == ""
    assert lines[4] == ""
    assert lines[5] == ""
    assert lines[6] == "after"


def test_unclosed_fence_at_eof():
    """Unclosed fence masks everything from opening to EOF."""
    content = "before\n```\nunclosed content\nmore content"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == "before"
    assert lines[1] == ""
    assert lines[2] == ""
    assert lines[3] == ""


def test_fence_on_first_line():
    """Fence starting on the first line of the file is handled."""
    content = "```\nfenced\n```\nafter\n"
    _, masked = mu.mask_code_fences(content)
    lines = masked.split("\n")
    assert lines[0] == ""
    assert lines[1] == ""
    assert lines[2] == ""
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


# --- BH-004: Tilde fence support ---

def test_tilde_fence_masking():
    """Content between ~~~ pairs should be masked like backtick fences."""
    content = "before\n~~~\nfenced line\n~~~\nafter\n"
    _, masked = mu.mask_code_fences(content)
    assert "before" in masked
    assert "after" in masked
    assert "fenced line" not in masked


def test_tilde_fence_with_language():
    """Tilde fences with language tag (~~~python) should be recognized."""
    content = "text\n~~~python\ncode_here\n~~~\nmore text\n"
    _, masked = mu.mask_code_fences(content)
    assert "code_here" not in masked
    assert "more text" in masked


def test_tilde_fence_does_not_close_backtick():
    """~~~ should not close a backtick fence and vice versa."""
    content = "```\n~~~\nstill fenced\n```\nafter\n"
    _, masked = mu.mask_code_fences(content)
    assert "still fenced" not in masked
    assert "after" in masked

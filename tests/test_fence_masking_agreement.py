"""Cross-implementation test for fence masking agreement.

markdown_utils.mask_code_fences (scripts layer) and _common.mask_fenced_blocks
(hooks layer) are two independent implementations of CommonMark fence masking.
This test verifies they agree on fence boundary detection.

The two implementations intentionally differ in one way:
- markdown_utils blanks fence delimiter lines (opener + closer) along with content
- _common keeps fence delimiter lines, only blanking content between them

Both behaviors are correct for their purpose (PAT-001 protection). The critical
contract is: both must agree on WHAT IS A FENCE — same opener detection, same
closer detection, same content identification. Content lines inside fences must
be empty in both.

BH-003 run 18: indented fence divergence
BH-004 run 18: backtick info string divergence
BH-007 run 18: no cross-implementation test existed
PAT-004: dual-implementation divergence
"""

import re
import sys
from pathlib import Path

import pytest

# Import both implementations
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "holtz" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from markdown_utils import mask_code_fences  # noqa: E402
from _common import mask_fenced_blocks  # noqa: E402

# Matches CommonMark fence delimiters (backtick or tilde, optionally indented 0-3 spaces)
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _compare(text: str) -> None:
    """Assert both maskers agree on which lines are fenced content.

    For each non-delimiter line, both implementations must agree on
    whether it is masked (empty) or preserved. Fence delimiter lines
    are excluded from comparison because markdown_utils blanks them
    while _common keeps them — an intentional design difference.
    """
    text_lf = text.replace('\r\n', '\n')
    _, mu_masked = mask_code_fences(text_lf)
    common_masked = mask_fenced_blocks(text_lf)

    mu_lines = mu_masked.split('\n')
    common_lines = common_masked.split('\n')
    original_lines = text_lf.split('\n')

    assert len(mu_lines) == len(common_lines) == len(original_lines), (
        f"Line count mismatch: mu={len(mu_lines)}, common={len(common_lines)}, "
        f"original={len(original_lines)}"
    )

    for i, (orig, mu_line, common_line) in enumerate(
        zip(original_lines, mu_lines, common_lines)
    ):
        # Skip fence delimiter lines — they differ intentionally
        if _FENCE_LINE.match(orig):
            continue
        # For content lines: both must agree on masked vs preserved
        mu_masked_line = (mu_line == '')
        common_masked_line = (common_line == '')
        assert mu_masked_line == common_masked_line, (
            f"Line {i} masking disagrees:\n"
            f"  original:       {orig!r}\n"
            f"  markdown_utils: {'masked' if mu_masked_line else repr(mu_line)}\n"
            f"  _common:        {'masked' if common_masked_line else repr(common_line)}\n"
            f"  full input:     {text!r}"
        )


class TestFenceMaskingAgreement:
    """Both maskers must agree on fence boundary detection."""

    def test_plain_backtick_fence(self):
        _compare("before\n```\ncode\n```\nafter\n")

    def test_plain_tilde_fence(self):
        _compare("before\n~~~\ncode\n~~~\nafter\n")

    def test_backtick_with_language(self):
        _compare("before\n```python\ncode\n```\nafter\n")

    def test_tilde_with_language(self):
        _compare("before\n~~~python\ncode\n~~~\nafter\n")

    def test_indented_1_space(self):
        """BH-003: 1-space indented fence must be masked."""
        _compare("before\n ```\n code\n ```\nafter\n")

    def test_indented_2_spaces(self):
        """BH-003: 2-space indented fence must be masked."""
        _compare("before\n  ```\n  code\n  ```\nafter\n")

    def test_indented_3_spaces(self):
        """BH-003: 3-space indented fence must be masked."""
        _compare("before\n   ```python\n   code\n   ```\nafter\n")

    def test_indented_4_spaces_not_a_fence(self):
        """4+ spaces is an indented code block, NOT a fenced code block."""
        _compare("before\n    ```\n    code\n    ```\nafter\n")

    def test_indented_tilde_3_spaces(self):
        """BH-003: indented tilde fence."""
        _compare("before\n   ~~~\n   code\n   ~~~\nafter\n")

    def test_backtick_in_info_string(self):
        """BH-004: backtick in info string must NOT open a fence."""
        _compare("before\n```some`thing\ncode\n```\nafter\n")

    def test_backtick_in_info_string_multiple(self):
        """BH-004: multiple backticks in info string."""
        _compare("before\n```a`b`c\ncode\n```\nafter\n")

    def test_tilde_in_tilde_info_string_allowed(self):
        """Tilde fences CAN have tildes in info string per CommonMark."""
        _compare("before\n~~~some~thing\ncode\n~~~\nafter\n")

    def test_longer_fence(self):
        _compare("before\n````\ncode\n````\nafter\n")

    def test_longer_fence_close_requires_same_length(self):
        _compare("before\n````\ncode\n```\nstill in fence\n````\nafter\n")

    def test_tilde_cannot_close_backtick(self):
        _compare("before\n```\ncode\n~~~\nstill in fence\n```\nafter\n")

    def test_backtick_cannot_close_tilde(self):
        _compare("before\n~~~\ncode\n```\nstill in fence\n~~~\nafter\n")

    def test_nested_fences(self):
        _compare("before\n````\n```\ninner\n```\n````\nafter\n")

    def test_empty_content(self):
        _compare("")

    def test_no_fences(self):
        _compare("just plain text\nno fences here\n")

    def test_unclosed_fence(self):
        _compare("before\n```\ncode\nnever closed\n")

    def test_multiple_fences(self):
        _compare("a\n```\nb\n```\nc\n~~~\nd\n~~~\ne\n")

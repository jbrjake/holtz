"""Shared markdown parsing utilities for Holtz scripts."""

import re
from collections.abc import Generator

# CommonMark allows code fences to be indented 0-3 spaces.
# 4+ spaces is an indented code block, not a fenced code block.
_BACKTICK_OPEN = re.compile(r'^( {0,3})(`{3,})[^`]*$')
_TILDE_OPEN = re.compile(r'^( {0,3})(~{3,}).*$')
_BACKTICK_CLOSE_TMPL = r'^ {0,3}`{%d,}[ \t]*$'
_TILDE_CLOSE_TMPL = r'^ {0,3}~{%d,}[ \t]*$'


def _iterate_fences(lines: list[str]) -> Generator[tuple[int, bool], None, None]:
    """Yield (line_index, in_fence) for each line, tracking CommonMark fence state.

    Handles both backtick and tilde fences per CommonMark spec.
    A tilde fence cannot close a backtick fence and vice versa.
    Opening and closing fences may be indented 0-3 spaces independently.
    """
    in_fence = False
    fence_char_count = 0
    fence_close_tmpl = ''

    for i, line in enumerate(lines):
        if not in_fence:
            m = _BACKTICK_OPEN.match(line)
            if m:
                fence_char_count = len(m.group(2))
                fence_close_tmpl = _BACKTICK_CLOSE_TMPL
                in_fence = True
                yield i, True
                continue
            m = _TILDE_OPEN.match(line)
            if m:
                fence_char_count = len(m.group(2))
                fence_close_tmpl = _TILDE_CLOSE_TMPL
                in_fence = True
                yield i, True
                continue
            yield i, False
        else:
            if re.match(fence_close_tmpl % fence_char_count, line):
                yield i, True
                in_fence = False
            else:
                yield i, True


def mask_code_fences(content: str) -> tuple[str, str]:
    """Normalize line endings and produce a masked copy with code fence content blanked.

    Returns (normalized, masked) where:
    - normalized: original content with CRLF converted to LF
    - masked: same content but lines inside fenced code blocks replaced with empty lines

    Handles both backtick (```) and tilde (~~~) fences per CommonMark spec.
    A tilde fence cannot close a backtick fence and vice versa.
    Opening and closing fences may be indented 0-3 spaces independently.
    """
    content = content.replace('\r\n', '\n')
    lines = content.split('\n')
    masked_lines = list(lines)

    for i, fenced in _iterate_fences(lines):
        if fenced:
            masked_lines[i] = ''

    return content, '\n'.join(masked_lines)


def has_unclosed_fence(content: str) -> bool:
    """Check if content has a code fence that is never closed."""
    content = content.replace('\r\n', '\n')
    lines = content.split('\n')
    # Consume the generator; the last yielded in_fence state tells us
    # whether the document ends inside an unclosed fence.
    in_fence = False
    for _, fenced in _iterate_fences(lines):
        in_fence = fenced
    return in_fence

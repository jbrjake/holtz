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

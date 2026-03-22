---
name: Code Fence Unaware Parsing
version: 1
discovered: 2026-03-19
languages: [python, javascript, ruby, go, rust]
categories: [bug/logic]
---

# Code Fence Unaware Parsing

## Description

Parsing structured text (markdown, config files, templates, or any format with fenced/quoted/literal blocks) without first isolating those blocks. Content inside fences, code blocks, or literal regions gets matched by patterns meant for the surrounding document, producing false positives, corrupted extracted data, or silently wrong results.

The root cause is applying regex or string-matching to the full document body when the patterns are only valid for the "prose" or "structural" layer. The fix is to mask, strip, or skip fenced regions before applying document-level patterns.

## Detection Heuristic

### Grep-based scan

```bash
# Find regex searches applied to variables likely holding full document content
grep -rnP 're\.(search|findall|finditer|match)\(.*\b(content|body|text|document|source|raw|markdown|md_text)\b' --include='*.py' .
```

```bash
# JS/TS equivalent
grep -rnP '\.(match|matchAll|search|replace|test)\(.*\b(content|body|text|document|source|raw|markdown)\b' --include='*.js' --include='*.ts' .
```

### Manual triage (apply to each grep hit)

1. Can the input contain fenced/quoted/literal blocks (e.g., triple-backtick code blocks, heredocs, YAML literal blocks)?
2. Is there a prior step that strips or masks those blocks before the regex runs?
3. If fenced blocks are possible and no masking step exists — this is a true positive.

### LLM-based structured check

> "For each function that applies regex or string matching to document content: can that content contain fenced code blocks, quoted literals, or embedded examples? If yes, is there a pre-processing step that removes or masks those regions before the pattern is applied? Flag cases where fenced content is possible but not isolated."

## Indicators

- Regex applied to a variable named `content`, `body`, `text`, `document`, `source`, or similar
- No call to a fence-stripping or masking function before the regex
- The regex pattern could match syntax that legitimately appears inside code examples (e.g., function signatures, import statements, headings)
- False positives reported when documents contain code examples
- Test fixtures do not include fenced blocks in the input text

## Example

### Before (buggy)

```python
import re

def extract_headings(document):
    """Extract all headings from a structured document."""
    return re.findall(r'^(#{1,6})\s+(.+)$', document, re.MULTILINE)

sample = """# Overview

Some text here.

```
# This is a comment in a code example
process_data(items)
```

## Details

More text.
"""

headings = extract_headings(sample)
# Expected: [('#', 'Overview'), ('##', 'Details')]
# Actual: [('#', 'Overview'), ('#', 'This is a comment in a code example'), ('##', 'Details')]
# The comment inside the code fence was matched as a heading.
```

### After (fixed)

```python
import re

def mask_fenced_blocks(document):
    """Replace content inside fenced blocks with blank lines to preserve line numbering."""
    def replace_block(match):
        lines = match.group(0).split('\n')
        return '\n'.join([lines[0]] + [''] * (len(lines) - 2) + [lines[-1]])
    return re.sub(r'^```.*?^```', replace_block, document, flags=re.MULTILINE | re.DOTALL)

def extract_headings(document):
    """Extract all headings from a structured document, ignoring fenced blocks."""
    masked = mask_fenced_blocks(document)
    return re.findall(r'^(#{1,6})\s+(.+)$', masked, re.MULTILINE)

sample = """# Overview

Some text here.

```
# This is a comment in a code example
process_data(items)
```

## Details

More text.
"""

headings = extract_headings(sample)
# Returns: [('#', 'Overview'), ('##', 'Details')]
# The comment inside the code fence is correctly ignored.
```

## Related Patterns

- [regex-newline-leak](regex-newline-leak.md) — another regex pitfall in multi-line text processing
- [dual-parser-divergence](dual-parser-divergence.md) — if one parser masks fences and another does not, they produce divergent results

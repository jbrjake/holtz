---
name: Regex Newline Leak
version: "1.0"
discovered: PAT-001, Bug Hunter run 1
languages: [python, javascript, ruby, go]
categories: [bug/logic, bug/state]
---

# Regex Newline Leak

## Description

Using `\s` in regex patterns where only horizontal whitespace (`[ \t]`) is intended. The `\s` shorthand matches `\n` (and `\r`, `\f`, `\v`), causing patterns to leak across line boundaries in multi-line text processing. This produces silent bugs: the regex matches successfully but captures content from the wrong line, or spans lines when it should stay on one.

The fix is straightforward — replace `\s` with `[ \t]` (or `[^\S\r\n]` if Unicode horizontal whitespace is needed) — but the bug is hard to spot in review because `\s` *looks* correct and tests with single-line input pass.

## Detection Heuristic

### Grep-based scan

```bash
# Find \s quantified with *, +, or ? in Python/JS/Ruby files
grep -rnP '\\s[*+?]' --include='*.py' --include='*.js' --include='*.rb' --include='*.ts' .
```

### Manual triage (apply to each grep hit)

1. Is the input to this regex ever multi-line (contains `\n`)?
2. Is cross-line matching intended here?
3. If the answer is "multi-line input, single-line intent" — this is a true positive.

### LLM-based structured check

> "For each regex containing `\s` with a quantifier: is the input string ever multi-line? If yes, is crossing line boundaries the intended behavior? Flag cases where multi-line input meets single-line intent."

## Indicators

- `\s+`, `\s*`, or `\s?` in a regex applied to multi-line content
- Regex used to parse line-oriented formats (key-value pairs, headers, log lines, config entries)
- Regex used after reading a full file into a single string
- Tests only use single-line input strings (hides the bug)
- Captured group contains unexpected leading/trailing whitespace or content from adjacent lines

## Example

### Before (buggy)

```python
import re

def parse_value(text, key):
    """Extract the value for a given key from multi-line key-value text."""
    pattern = rf'{re.escape(key)}:\s*(.*)'
    match = re.search(pattern, text)
    #                      ^^ \s* matches \n, so (.*) captures from the NEXT line
    return match.group(1) if match else None

data = "item_count: \nparse_items: 42\nvalidate_input: ok"
result = parse_value(data, "item_count")
# Expected: "" (empty value)
# Actual: "parse_items: 42" (leaked to next line)
```

### After (fixed)

```python
import re

def parse_value(text, key):
    """Extract the value for a given key from multi-line key-value text."""
    pattern = rf'{re.escape(key)}:[ \t]*(.*)'
    match = re.search(pattern, text)
    #                           ^^ [ \t]* stays on same line
    return match.group(1) if match else None

data = "item_count: \nparse_items: 42\nvalidate_input: ok"
result = parse_value(data, "item_count")
# Expected: "" (empty value)
# Actual: "" (correct — stays on same line)
```

## Related Patterns

- [code-fence-unaware-parsing](code-fence-unaware-parsing.md) — another class of regex applied to structured multi-line text without accounting for document structure
- [missing-edge-case-handling](missing-edge-case-handling.md) — tests with only single-line input are a form of missing edge-case coverage

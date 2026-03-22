---
name: Dual Parser Divergence
version: 1
discovered: 2026-03-19
languages: [python, javascript, typescript, java, go, rust]
categories: [bug/logic, design/inconsistency]
---

# Dual Parser Divergence

## Description

Two or more independent parsers, extractors, or deserializers exist for the same data format or structure, each with different levels of structural awareness. One parser handles edge cases (escaping, nesting, encoding, empty values, malformed input) that the other does not. Depending on which code path runs, results differ — sometimes silently.

This commonly arises when a quick utility function is written for one use case, then a more robust parser is built later for another, and neither is consolidated. It also happens when parsing logic is duplicated across modules or services rather than shared.

## Detection Heuristic

### Grep-based scan

```bash
# Find multiple parse/extract/deserialize functions — potential duplicates
grep -rnP '(def|function|func)\s+(parse|extract|decode|deserialize|read|load|from_)\w*' --include='*.py' --include='*.js' --include='*.ts' --include='*.go' .
```

```bash
# Find multiple regex patterns targeting the same format indicators
grep -rnP "re\.(compile|search|findall|match)\(.*r['\"]" --include='*.py' . | sort -t: -k3 | uniq -d -f2
```

### Manual triage

1. Group the results by what they parse (e.g., "two functions that parse CSV", "two functions that extract headers from text").
2. For each group: do they handle the same edge cases? Compare their handling of empty input, malformed input, special characters, and nested structures.
3. If two parsers exist for the same format with different edge-case handling — this is a true positive.

### LLM-based structured check

> "Are there two or more functions or modules that parse, extract, or deserialize from the same data format? For each pair: do they handle the same edge cases (empty input, malformed data, special characters, nested structures, encoding issues)? List any divergences."

## Indicators

- Two or more functions with similar names or docstrings targeting the same data format
- Different regex patterns used in different files to extract the same kind of data
- One parser uses a library (e.g., `json.loads`, `csv.reader`) while another uses hand-rolled regex for the same format
- Bug reports where "it works in module A but not module B" for the same input
- One parser was updated to handle an edge case but the other was not

## Example

### Before (buggy)

```python
# report_generator.py — simple parser, no edge-case handling
import re

def extract_fields(text):
    """Extract key-value fields from structured text."""
    fields = {}
    for line in text.split('\n'):
        match = re.match(r'(\w+):\s*(.*)', line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields

# data_validator.py — robust parser, handles edge cases
import re

def extract_fields_validated(text):
    """Extract and validate key-value fields from structured text."""
    fields = {}
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue  # skip blanks and comments
        match = re.match(r'([\w.-]+):\s*(.*)', line)
        if match:
            key = match.group(1).lower()  # normalize key
            value = match.group(2).strip().strip('"')  # handle quoted values
            fields[key] = value
    return fields

# report_generator sees:  {'item_count': '"42"'}     (keeps quotes, case-sensitive keys)
# data_validator sees:    {'item_count': '42'}        (strips quotes, normalized keys)
```

### After (fixed)

```python
# field_parser.py — single shared parser
import re

def extract_fields(text):
    """Extract key-value fields from structured text.

    Handles: blank lines, comment lines, quoted values, key normalization.
    """
    fields = {}
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.match(r'([\w.-]+):\s*(.*)', line)
        if match:
            key = match.group(1).lower()
            value = match.group(2).strip().strip('"')
            fields[key] = value
    return fields

# Both report_generator.py and data_validator.py import from field_parser
```

## Related Patterns

- [incomplete-layer-isolation](incomplete-layer-isolation.md) — dual parsers are a special case of incomplete isolation, where the "layer" is the canonical parser
- [code-fence-unaware-parsing](code-fence-unaware-parsing.md) — a common divergence point: one parser accounts for fenced blocks, the other does not

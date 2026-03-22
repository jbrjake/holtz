---
name: missing-edge-case-handling
version: 1
discovered: 2026-03-19
languages: [python, javascript, typescript, java, go, rust, ruby]
categories: [bug/logic, bug/error-handling]
---

# Missing Edge Case Handling

## Description

Assuming well-formed, present, and complete input without validation. Functions that work correctly on happy-path inputs but fail — via exception, silent wrong result, or corrupted state — when given null, empty, malformed, or missing data.

This is the most common bug pattern in any codebase. It appears wherever a function accesses a dictionary key, array index, object property, or parsed field without first checking that the value exists and is the expected type. The failure mode varies by language: Python raises `KeyError`/`TypeError`, JavaScript returns `undefined` and propagates silently, Go panics on nil pointer dereference, Java throws `NullPointerException`.

## Detection Heuristic

### Grep-based scan

```bash
# Python: dict access without .get() or prior 'in' check
grep -rnP '\w+\[[\x27"][^\x27"]+[\x27"]\]' --include='*.py' . | grep -v '\.get(' | grep -v 'if.*\bin\b'
```

```bash
# Python: chained attribute access (high risk for None in chain)
grep -rnP '\w+\.\w+\.\w+\.\w+' --include='*.py' .
```

```bash
# JavaScript/TypeScript: property access without optional chaining on potentially null values
grep -rnP '\w+\.\w+\.\w+' --include='*.js' --include='*.ts' . | grep -v '\?\.' | grep -v '&&'
```

```bash
# Find functions with no early return/raise for invalid input
grep -rnP '^\s*def\s+\w+' --include='*.py' -A 5 . | grep -v 'if.*is None\|if not\s\|raise\|ValueError\|TypeError'
```

### Manual triage

1. For each hit: can the accessed key/property/index ever be absent at runtime?
2. Is there an upstream guarantee (type system, schema validation, required field) that ensures presence?
3. If no guarantee exists — this is a true positive.

### LLM-based structured check

> "For each function: what inputs does it assume are present and well-formed? Are those assumptions validated before use? What happens if any input is None, empty, missing a key, or the wrong type? Flag functions where assumptions are not validated."

## Indicators

- Direct dict/object key access without existence check (`data["key"]` instead of `data.get("key")`)
- Array index access without length check (`items[0]` without verifying `len(items) > 0`)
- Chained property access without null guards (`result.data.items.count`)
- No type/presence validation at function entry points
- Tests only cover the happy path (all inputs present and well-formed)
- Error messages like `KeyError`, `TypeError`, `undefined is not a function`, `NullPointerException` in logs

## Example

### Before (buggy)

```python
def process_data(records):
    """Summarize records by category."""
    summary = {}
    for record in records:
        category = record["category"]           # KeyError if key missing
        value = record["metadata"]["score"]      # KeyError or TypeError if metadata is None
        count = int(record["count"])             # ValueError if count is not numeric
        if category not in summary:
            summary[category] = 0
        summary[category] += value * count
    return summary
```

### After (fixed)

```python
def process_data(records):
    """Summarize records by category. Skips records with missing or invalid fields."""
    if not records:
        return {}

    summary = {}
    for record in records:
        if not isinstance(record, dict):
            continue

        category = record.get("category")
        if not category:
            continue

        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            continue

        score = metadata.get("score")
        if not isinstance(score, (int, float)):
            continue

        raw_count = record.get("count")
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue

        summary[category] = summary.get(category, 0) + score * count
    return summary
```

## Related Patterns

- [regex-newline-leak](regex-newline-leak.md) — tests with only single-line input are a specific instance of missing edge-case coverage
- [dual-parser-divergence](dual-parser-divergence.md) — divergent parsers often differ precisely in which edge cases they handle

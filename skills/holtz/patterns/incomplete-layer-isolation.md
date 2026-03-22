---
name: incomplete-layer-isolation
version: 1
discovered: 2026-03-19
languages: [python, javascript, typescript, java, go, rust]
categories: [design/inconsistency, bug/logic]
---

# Incomplete Layer Isolation

## Description

Adding an isolation or abstraction layer (API wrapper, data access object, service facade, configuration manager) but not fully routing all access through it. Some callers use the new layer, while others bypass it and access the underlying resource directly. This defeats the layer's purpose — whether that purpose is validation, caching, logging, access control, or consistent error handling.

The pattern is insidious because the layer *works* for the callers that use it, so tests pass and the feature appears complete. The bypassing callers only cause problems when the layer's invariants matter (e.g., a cache gets stale because some writes bypass the caching layer, or validation is skipped because some callers hit the raw API).

## Detection Heuristic

### Step 1: Identify the abstraction layer

```bash
# Find likely abstraction layers — classes/functions with wrapper/manager/service/client/facade/gateway in the name
grep -rnP '(class|def|function|func)\s+\w*(Manager|Service|Client|Facade|Gateway|Wrapper|Provider|Repository|Store|Cache|Adapter)\b' --include='*.py' --include='*.js' --include='*.ts' --include='*.java' --include='*.go' .
```

### Step 2: Find what the layer wraps

Manually inspect each result from Step 1. Identify the underlying resource (e.g., a database connection, HTTP client, file path, config dict).

### Step 3: Find direct access that bypasses the layer

```bash
# Example: if the layer wraps database queries, find direct SQL/query calls outside the layer
grep -rnP '\b(execute|query|cursor|conn\.|db\.)\b' --include='*.py' . | grep -v 'repository\|manager\|service'
```

```bash
# Example: if the layer wraps a config file, find direct file reads of that config
grep -rnP '(open|read|load).*config' --include='*.py' --include='*.js' --include='*.ts' . | grep -v 'config_manager\|config_service\|config_provider'
```

### LLM-based structured check

> "Identify all abstraction layers (wrappers, managers, services, repositories) in this codebase. For each one: what underlying resource does it wrap? Are there any callers that access that resource directly instead of going through the layer? List each bypass with file and line."

## Indicators

- An abstraction layer exists (class or module with a clear wrapping purpose)
- Some modules import and use the layer; others import the underlying resource directly
- The layer enforces invariants (validation, caching, logging) that bypassing callers skip
- Tests for the layer pass, but integration tests reveal inconsistent behavior
- Recent commits added the layer but did not update all existing callers

## Example

### Before (buggy)

```python
# data_store.py — the abstraction layer
class DataStore:
    def __init__(self, db_connection):
        self._db = db_connection
        self._cache = {}

    def get_record(self, record_id):
        if record_id in self._cache:
            return self._cache[record_id]
        row = self._db.execute("SELECT * FROM records WHERE id = ?", (record_id,))
        result = row.fetchone()
        self._cache[record_id] = result
        return result

    def update_record(self, record_id, data):
        self._db.execute("UPDATE records SET data = ? WHERE id = ?", (data, record_id))
        self._cache[record_id] = data

# process_data.py — uses the layer correctly
from data_store import DataStore

def process_data(store: DataStore, record_id):
    record = store.get_record(record_id)  # goes through cache
    return transform(record)

# validate_input.py — BYPASSES the layer
import sqlite3

def validate_input(db_path, record_id):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,))
    record = row.fetchone()  # skips cache, skips DataStore entirely
    return check_validity(record)
```

### After (fixed)

```python
# validate_input.py — now uses the layer
from data_store import DataStore

def validate_input(store: DataStore, record_id):
    record = store.get_record(record_id)  # goes through cache, consistent access
    return check_validity(record)
```

## Related Patterns

- [dual-parser-divergence](dual-parser-divergence.md) — two access paths to the same data is a prerequisite for divergence
- [doc-spec-drift](doc-spec-drift.md) — the layer's documentation may describe it as "the single access point" while bypasses exist in code

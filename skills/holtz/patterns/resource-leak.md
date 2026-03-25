---
name: resource-leak
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, rust, java]
categories: [bug/resource, bug/error-handling]
---

# Resource Leak

## Description

A system resource (file handle, database connection, socket, subprocess, lock, temp file) is acquired but not released on all code paths — particularly exception paths. Each leaked resource is individually harmless; the aggregate exhausts OS limits, causing cascading failures hours or days after deployment.

In Python, the canonical form is `open()` without a `with` block. In Go, it's missing `defer close()` after opening. In JS, it's unclosed database connections in Express middleware. In all languages, the pattern is: the happy path releases the resource, but an early return or exception skips the cleanup.

CWE-772 (resource leak) and CWE-401 (memory leak) cover this class. CVE-2024-21626 demonstrated security implications: a file descriptor leak in runc enabled container escape.

## Detection Heuristic

### Grep-based scan

```bash
# Python: open() calls not used as context managers
grep -rnP '\bopen\s*\(' --include='*.py' . | grep -v 'with\s'
```

```bash
# Go: resource acquisition without defer close
grep -rnP '(\w+),\s*(\w+)\s*:?=\s*os\.Open|sql\.Open|net\.Dial|http\.Get' --include='*.go' -A 5 . | grep -v 'defer.*Close'
```

```bash
# Python: connection/cursor creation without context manager or explicit close
grep -rnP '(\.connect\(|\.cursor\()' --include='*.py' . | grep -v 'with\s'
```

```bash
# Find try blocks with resource acquisition but no finally/close
grep -rnP '^\s*try:' --include='*.py' -A 20 . | grep -P '(open|connect|socket|acquire)' | grep -v 'finally'
```

### Manual triage

1. Is a resource acquired (opened, connected, locked)?
2. Is there a corresponding release on ALL paths — including exceptions, early returns, and break/continue?
3. In Python: is it in a `with` block or a `try/finally`?
4. In Go: is there a `defer close()` immediately after the error check?
5. Does the cleanup itself handle errors (e.g., `close()` can fail)?

### LLM-based structured check

> "For each resource acquisition (file open, db connect, socket create, lock acquire, temp file create): trace all code paths from acquisition to function exit. Is there a release on every path, including exception paths and early returns? Flag any path where the resource is not released."

## Indicators

- `open()` without `with` in Python
- Missing `defer f.Close()` after `os.Open` in Go
- Database connections created in request handlers without pool management
- Temp files created without cleanup (especially in test fixtures)
- Lock `acquire()` without corresponding `release()` in `finally`
- Process count / fd count growing monotonically in production metrics
- "Too many open files" errors after extended runtime

## Example

### Before (buggy)

```python
def process_files(paths):
    results = []
    for path in paths:
        f = open(path, 'r')
        data = parse(f.read())        # If parse() raises, f is never closed
        results.append(transform(data))
        f.close()                     # Never reached on exception
    return results
```

### After (fixed)

```python
def process_files(paths):
    results = []
    for path in paths:
        with open(path, 'r') as f:    # Closed on all paths, including exceptions
            data = parse(f.read())
        results.append(transform(data))
    return results
```

## Related Patterns

- [concurrency-violation](concurrency-violation.md) — blocked-thread exhaustion is a resource leak in the thread pool
- [missing-edge-case-handling](missing-edge-case-handling.md) — exception paths are edge cases that skip cleanup
- [error-destruction](error-destruction.md) — swallowed errors mask the resource leak symptom

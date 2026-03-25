---
name: concurrency-violation
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, rust, java, swift]
categories: [bug/concurrency, bug/state]
---

# Concurrency Violation

## Description

Shared mutable state accessed by concurrent execution contexts (threads, goroutines, async tasks, request handlers) without adequate synchronization. Produces non-deterministic corruption, lost updates, torn reads, or deadlocks depending on timing.

This is a family of related bugs: classic data races (unsynchronized read/write), TOCTOU races (check-then-act with state change between), priority inversion (high-priority task blocked behind low-priority holder while medium-priority tasks preempt), ABA problems (value reverts to original between check and use in lock-free structures), and blocked-thread exhaustion (threads block on shared resources without timeouts, pool drains to zero).

The unifying root cause is: two or more execution contexts access the same state, at least one writes, and the code assumes sequential consistency without enforcing it.

**Real-time constraint violation:** Code on hard-deadline threads (audio callbacks, render loops, interrupt handlers, game tick functions) that is correctly synchronized but violates latency guarantees by performing: heap allocation (object creation, buffer/array resize, string building), lock or semaphore acquisition, blocking calls (completion waits, synchronous dispatch), or triggering non-trivial language-runtime bookkeeping. The code is thread-safe but not RT-safe.

**Lying escape hatch:** Types annotated to opt out of the language's concurrency safety checks but whose implementation doesn't uphold the contract. The annotation promises thread-safety; mutable stored properties without synchronization break that promise.

CWE-362 (race condition) ranks #20 in the 2024 CWE Top 25. NASA's Mars Pathfinder experienced priority inversion severe enough to require uploading a C patch from Earth.

## Detection Heuristic

### Grep-based scan

```bash
# Python: shared state without locking — global dicts/lists mutated in thread/async contexts
grep -rnP '(threading|asyncio|concurrent\.futures)' --include='*.py' -l . | xargs grep -lP '^\s*(global |[A-Z_]+\s*=\s*\{|\w+\.(append|update|pop|__setitem__))'
```

```bash
# Go: goroutine accessing variable from enclosing scope (common race)
grep -rnP 'go\s+func\s*\(' --include='*.go' -A 10 . | grep -P '^\s+\w+\s*[=+\-]'
```

```bash
# Python/JS: check-then-act patterns (TOCTOU)
grep -rnP 'if\s+.*\bexists\b.*:$' --include='*.py' -A 3 . | grep -P '(open|remove|rename|write)'
```

```bash
# Find lock acquisition without timeout
grep -rnP '\.(acquire|lock)\(\s*\)' --include='*.py' --include='*.go' --include='*.java' .
```

```bash
# Weak reference usage in callback/handler contexts (any language)
grep -rnP '(weak|WeakRef|weak_ptr)' --include='*.swift' --include='*.ts' --include='*.cpp' --include='*.rs' . | grep -iP 'callback|handler|render|audio|tick'
```

```bash
# Semaphore or lock near async/await (deadlock on RT thread)
grep -rlP '(Semaphore|semaphore|Mutex|mutex)' . | xargs grep -lP '(async|await|Task|Future|Promise)'
```

```bash
# Unmanaged/unsafe pointer access in callback contexts
grep -rnP '(Unmanaged|UnsafePointer|unsafe\s*\{|raw pointer)' . | grep -iP 'callback|handler|audio|render'
```

```bash
# Concurrency escape hatches with mutable state
grep -rn "@unchecked Sendable" --include='*.swift' .
grep -rn "unsafe impl Send\|unsafe impl Sync" --include='*.rs' .
grep -rn "@SuppressWarnings.*thread-safety" --include='*.java' .
# For each match: check type body for mutable fields without synchronization
```

### Manual triage

1. Is the accessed state shared between concurrent contexts?
2. Is at least one access a write?
3. Is there a synchronization mechanism (lock, channel, atomic) protecting the access?
4. For check-then-act: can state change between the check and the action?
5. For locks: are they always acquired in the same order across all call sites?
6. For blocking calls: is there a timeout? What happens when the pool is exhausted?

### LLM-based structured check

> "Identify all mutable state shared between threads, goroutines, async tasks, or request handlers. For each: is access synchronized? If locks are used, is acquisition order consistent across all sites? Are there check-then-act sequences where state can change between check and act? Are there blocking calls without timeouts? Flag all unprotected shared mutable access."

## Indicators

- Variables modified in one thread/goroutine and read in another without synchronization primitives
- `go func()` capturing loop variables or shared state
- `if os.path.exists(f): os.remove(f)` or `if key in dict: use(dict[key])` in concurrent code
- Lock acquisition in different orders across call sites (deadlock risk)
- Thread/connection pool with no timeout on blocking acquisition
- Intermittent failures that vanish under debugger (Heisenbug)
- Go race detector findings (`go test -race`)
- Python `threading` usage without `Lock`/`RLock`/`Queue`
- Callbacks or handlers that allocate objects, grow containers, or build strings
- Lock acquisition inside a function called from a deadline thread
- Blocking waits in render or audio paths
- Intermittent audio glitches or frame drops under load (classic symptom)
- Type with a concurrency escape-hatch annotation containing mutable fields with no lock, atomic, or actor isolation in scope

## Example

### Before (buggy)

```python
import threading

# Shared mutable state — no synchronization
_cache = {}
_stats = {"hits": 0, "misses": 0}

def get_item(key):
    if key in _cache:                    # TOCTOU: key can be evicted between check and read
        _stats["hits"] += 1             # Race: read-modify-write is not atomic
        return _cache[key]              # Race: may raise KeyError if evicted
    _stats["misses"] += 1
    value = expensive_fetch(key)
    _cache[key] = value                 # Race: concurrent writes can corrupt dict internals (CPython GIL
    return value                        #   mostly prevents this, but not in all implementations)

# 10 threads hammering get_item concurrently
for _ in range(10):
    threading.Thread(target=worker, args=(get_item,)).start()
```

### After (fixed)

```python
import threading

_cache = {}
_stats = {"hits": 0, "misses": 0}
_lock = threading.Lock()

def get_item(key):
    with _lock:
        if key in _cache:
            _stats["hits"] += 1
            return _cache[key]
    # Fetch outside lock to avoid holding it during I/O
    value = expensive_fetch(key)
    with _lock:
        # Double-check: another thread may have populated while we fetched
        if key not in _cache:
            _cache[key] = value
            _stats["misses"] += 1
        return _cache[key]
```

## Related Patterns

- [implicit-ordering-dependency](implicit-ordering-dependency.md) — ordering assumptions are a prerequisite for many races
- [resource-leak](resource-leak.md) — blocked-thread exhaustion is a resource leak in the thread pool
- [missing-edge-case-handling](missing-edge-case-handling.md) — race conditions are edge cases that only manifest under specific timing
- [resource-leak](resource-leak.md) — RT violations from per-frame resource allocation are also resource lifecycle bugs

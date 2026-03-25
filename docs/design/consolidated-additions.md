# Consolidated Additions — 80% Coverage Cut

8 bug patterns, 5 test antipatterns, 4 lenses. Each item below absorbs multiple
related patterns from the research into a single recognizable shape. Existing items
are not duplicated. Appendable to their respective files as-is.

---
---

# PART 1: Bug Patterns (append to `bug-patterns`)

---
name: concurrency-violation
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, rust, java]
categories: [bug/concurrency, bug/state]
---

# Concurrency Violation

## Description

Shared mutable state accessed by concurrent execution contexts (threads, goroutines, async tasks, request handlers) without adequate synchronization. Produces non-deterministic corruption, lost updates, torn reads, or deadlocks depending on timing.

This is a family of related bugs: classic data races (unsynchronized read/write), TOCTOU races (check-then-act with state change between), priority inversion (high-priority task blocked behind low-priority holder while medium-priority tasks preempt), ABA problems (value reverts to original between check and use in lock-free structures), and blocked-thread exhaustion (threads block on shared resources without timeouts, pool drains to zero).

The unifying root cause is: two or more execution contexts access the same state, at least one writes, and the code assumes sequential consistency without enforcing it.

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
---
name: uncontrolled-amplification
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, rust, java]
categories: [bug/distributed, design/resilience]
---

# Uncontrolled Amplification

## Description

A small trigger produces a disproportionately large system response via feedback loops, overwhelming capacity. The system attacks itself. This is a family of patterns sharing one root cause: work generated per failure exceeds work generated per success.

**Retry storm:** Failed requests trigger aggressive client retries without backoff. N clients × M retries = N×M load on an already-failing server. The retries ARE the outage.

**Cascading failure:** A fault in one component propagates to callers who don't handle errors defensively. Caller A times out on B, B times out on C; all three exhaust thread/connection pools simultaneously. Google's SRE book documents a Shakespeare Search outage losing billions of queries from a single cascading resource leak.

**Thundering herd / cache stampede:** A popular cache entry expires; all concurrent requests discover the miss simultaneously and hit the backend. Also called "dogpile." Any system with synchronized TTL expiry on hot keys is vulnerable.

**Self-denial attack:** Internal actions (marketing blast, bulk migration, cron storm, deploy rollout) generate load spikes that overwhelm production. Nygard calls this "the most avoidable of all stability patterns."

**Unbounded result set:** Query without LIMIT returns 10M rows instead of 10, causing OOM. The pathology is identical: small trigger, disproportionate resource consumption.

## Detection Heuristic

### Grep-based scan

```bash
# Find retry logic without backoff
grep -rnP '(retry|retries|attempt|MAX_RETRIES)' --include='*.py' --include='*.js' --include='*.go' . | grep -v -i '(backoff|exponential|jitter)'
```

```bash
# Find cache get-or-set without stampede protection (no locking/singleflight)
grep -rnP 'cache\.(get|miss|fetch)' --include='*.py' --include='*.js' --include='*.go' . | grep -v '(lock|singleflight|dogpile|mutex)'
```

```bash
# Find queries without LIMIT/pagination
grep -rnP '(SELECT|find|query|fetch_all)' --include='*.py' --include='*.js' --include='*.go' . | grep -v -i '(limit|pagina|top\s|take\s|first\s)'
```

### Manual triage

1. For retry logic: is there exponential backoff with jitter? Is there a circuit breaker? What's the max total retry duration?
2. For cache patterns: what happens on a cache miss for a hot key under concurrent load? Is there singleflight/lock-based dedup?
3. For queries: is there a LIMIT? What happens when the dataset is 1000× expected size?
4. For error handling in distributed calls: does the caller have timeouts, bulkheads, and fallback behavior?

### LLM-based structured check

> "For each outbound call (HTTP, DB, cache, queue): what happens when it fails? How many retries, with what backoff? Is there a circuit breaker? For cache reads: what happens on concurrent misses for the same key? For queries: is there a row limit? For batch operations: is there rate limiting? Flag any path where failure generates more work than success."

## Indicators

- Retry loops with fixed delay or no delay
- Cache get-or-compute without singleflight / lock-based deduplication
- HTTP clients without timeouts or circuit breakers
- Database queries without LIMIT that scan user-generated tables
- Cron jobs scheduled at identical times (midnight stampede)
- Marketing/notification systems without rate throttling
- Thread/connection pool exhaustion during partial outages

## Example

### Before (buggy)

```python
import requests

def fetch_data(url, max_retries=5):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            continue  # Immediate retry, no backoff, no jitter
    raise RuntimeError(f"Failed after {max_retries} retries")

# 10,000 clients all retry 5 times = 50,000 requests hitting a struggling server
```

### After (fixed)

```python
import requests
import random
import time

def fetch_data(url, max_retries=5, base_delay=0.5):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=5)  # Shorter timeout
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            time.sleep(delay)  # Exponential backoff with jitter
    raise RuntimeError(f"Failed after {max_retries} retries")

# Combined with a circuit breaker at the caller level to stop retries entirely
# when error rate exceeds threshold
```

## Related Patterns

- [resource-leak](resource-leak.md) — cascading failures often begin with resource exhaustion
- [concurrency-violation](concurrency-violation.md) — thundering herd is a form of unintended concurrency
- [cache-coherence-failure](cache-coherence-failure.md) — stampede is triggered by cache invalidation
---
name: error-destruction
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, java, rust]
categories: [bug/error-handling]
---

# Error Destruction

## Description

Errors are generated but destroyed before reaching anyone who can act on them. The system fails but nobody knows, or the diagnostic information is stripped beyond usefulness.

Four variants, all with the same effect — turning debuggable failures into mysteries:

**Exception swallowing:** Empty catch blocks (`except: pass`, `catch(e) {}`). The error vanishes entirely. SonarQube classifies this as BLOCKER (S108). Called "the most diabolical Python antipattern."

**Log-and-throw:** Every layer catches, logs, and re-throws. A single exception produces N duplicate log entries across N layers, drowning signal in noise while adding zero information.

**Destructive wrapping:** Catching an exception and re-throwing a new one without preserving the original as the cause. `catch (IOException e) { throw new AppError("failed"); }` — the original stack trace and context are permanently lost.

**Unchecked error return:** A function returns an error value that the caller ignores. Epidemic in Go (`err` routinely discarded), common in C (`errno` unchecked), and subtle in Python (functions that return `None` on failure instead of raising). CWE-252 covers this class.

## Detection Heuristic

### Grep-based scan

```bash
# Python: bare except with pass/continue
grep -rnP 'except.*:\s*$' --include='*.py' -A 1 . | grep -P '^\s+(pass|continue)\s*$'
```

```bash
# Python: catch-and-raise without chaining (missing 'from')
grep -rnP 'except\s+\w+.*:' --include='*.py' -A 3 . | grep -P 'raise\s+\w+\(' | grep -v 'from\s'
```

```bash
# Go: error return explicitly ignored
grep -rnP '\b\w+,\s*_\s*:?=\s*' --include='*.go' . | grep -v 'test'
```

```bash
# JS: empty catch blocks
grep -rnP 'catch\s*\([^)]*\)\s*\{' --include='*.js' --include='*.ts' -A 1 . | grep -P '^\s*\}'
```

```bash
# Python: log-and-raise (catch, log, re-raise — usually indicates layer spam)
grep -rnP 'except\s+\w+' --include='*.py' -A 3 . | grep -P 'logging\.(error|exception)' -A 1 | grep 'raise'
```

### Manual triage

1. For catch blocks: is the error communicated to the caller, logged with context, or silently dropped?
2. For re-throws: is the original exception preserved as the cause (`raise X from e` / `Throwable.initCause`)?
3. For Go `_` assignments: is the discarded value an error? Is ignoring it safe?
4. For log-and-throw: does the logging at this layer add information not available at the final handler?

### LLM-based structured check

> "For each catch/except/recover block: what happens to the error? Is it swallowed, re-thrown with cause preserved, logged then re-thrown (adding what context?), or converted to a return value? For each function that returns an error: do all callers check it? Flag: empty catch blocks, re-throws without cause chaining, and unchecked error returns."

## Indicators

- `except: pass` or `except Exception: pass` in Python
- `catch (e) {}` or `catch (e) { console.log(e) }` in JS (logged but not propagated)
- `_, err = foo(); _ = err` or `foo()` discarding error return in Go
- Exception chains with no root cause: `Caused by: null` in stack traces
- Same exception logged at 3+ layers in log output
- `raise CustomError("something failed")` without `from original_error`
- Production bugs where "we saw the error in logs but couldn't trace it to source"

## Example

### Before (buggy)

```python
def process_order(order_id):
    try:
        validate(order_id)
    except ValidationError:
        pass  # Swallowed — processing continues with invalid order

    try:
        result = charge_payment(order_id)
    except PaymentError as e:
        logger.error(f"Payment failed: {e}")   # Logged...
        raise PaymentError("Payment failed")   # ...and re-raised WITHOUT original cause
                                                # Original stack trace is gone

    try:
        send_confirmation(order_id)
    except Exception:
        return None  # Returns None instead of raising — caller gets silent failure
```

### After (fixed)

```python
def process_order(order_id):
    validate(order_id)  # Let ValidationError propagate — callers should handle it

    try:
        result = charge_payment(order_id)
    except PaymentError as e:
        raise ProcessingError(f"Payment failed for order {order_id}") from e
        # 'from e' preserves the full chain; log at the top-level handler, not here

    try:
        send_confirmation(order_id)
    except NotificationError as e:
        logger.warning(f"Confirmation email failed for {order_id}: {e}")
        # Intentional: non-critical, logged with context, order still succeeded
```

## Related Patterns

- [missing-edge-case-handling](missing-edge-case-handling.md) — swallowed errors are missing edge cases in the caller
- [resource-leak](resource-leak.md) — swallowed errors in cleanup code mask resource leaks
- [uncontrolled-amplification](uncontrolled-amplification.md) — silent failures let invalid state propagate until it cascades
---
name: cache-coherence-failure
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, java, rust]
categories: [bug/state, bug/distributed]
---

# Cache Coherence Failure

## Description

Cached data diverges from the source of truth and the system has no reliable mechanism to detect or correct the divergence. There are two named things in computer science harder than this: nothing.

**Missed invalidation:** A write path updates the database but doesn't invalidate/update the cache. Some callers see stale data indefinitely. This is the most common form — it happens whenever a new write path is added without updating the invalidation registry.

**Stale read-after-write:** Between a database write and cache deletion, a concurrent reader repopulates the cache with the old value. The stale value persists until TTL expiry. The standard mitigation (delete-after-write) has a race window; the robust mitigation is write-through or versioned cache entries.

**TTL-synchronized stampede:** Covered in `uncontrolled-amplification`, but the root cause is here — the invalidation strategy (synchronized TTL) creates a predictable moment when all cached entries expire simultaneously.

Facebook's 2010 cache inconsistency bug served stale friend-relationship data across the social graph for hours. The bug was in a missed invalidation path, not in the caching layer itself.

## Detection Heuristic

### Grep-based scan

```bash
# Find all cache write points
grep -rnP 'cache\.(set|put|store|write|update|invalidate|delete|evict|clear)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Find all DB/store write points — compare with cache invalidation points
grep -rnP '\.(save|update|insert|delete|execute|commit|put_item|upsert)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Find hardcoded TTL values (synchronized expiry risk)
grep -rnP '(ttl|TTL|expire|EXPIRE|max_age)\s*[=:]\s*\d+' --include='*.py' --include='*.js' --include='*.go' .
```

### Manual triage

1. Map all write paths to the source of truth (database, API, file).
2. For each write path: is there a corresponding cache invalidation/update?
3. For cache-aside reads: is there a race between the write and the cache repopulation?
4. Are TTL values identical across hot keys (stampede risk)?
5. Is there a mechanism to verify cache freshness (version stamp, ETag, last-modified)?

### LLM-based structured check

> "Map all database/store write operations and all cache invalidation operations. For each write: is there a corresponding cache invalidation? For each cache read-miss-fill: can a concurrent write cause the cache to be populated with stale data? Are TTL values randomized or jittered? Flag any write path without corresponding invalidation and any read-fill path with a stale-read race window."

## Indicators

- Cache writes and DB writes in different modules with no shared invalidation registry
- DB write followed by `cache.delete(key)` without handling the race window
- All cache entries using the same TTL value
- User reports of "I just updated X but it still shows Y"
- Cache hit rate anomalies after deploys (indicates new write paths bypassing invalidation)
- No cache versioning or ETag mechanism

## Example

### Before (buggy)

```python
def update_user_profile(user_id, new_data):
    db.execute("UPDATE users SET data = %s WHERE id = %s", (new_data, user_id))
    # Forgot to invalidate cache — reader still sees stale data
    # This write path was added 6 months after the original cache was implemented

def get_user_profile(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return cached
    profile = db.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
    cache.set(f"user:{user_id}", profile, ttl=3600)  # Stale for up to 1 hour
    return profile
```

### After (fixed)

```python
def update_user_profile(user_id, new_data):
    db.execute("UPDATE users SET data = %s WHERE id = %s", (new_data, user_id))
    cache.delete(f"user:{user_id}")
    # Still has a small race window — for stronger consistency, use write-through:
    # cache.set(f"user:{user_id}", new_data, ttl=3600 + random.randint(0, 300))

def get_user_profile(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return cached
    profile = db.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
    # Jittered TTL prevents synchronized expiry across keys
    cache.set(f"user:{user_id}", profile, ttl=3600 + random.randint(0, 300))
    return profile
```

## Related Patterns

- [uncontrolled-amplification](uncontrolled-amplification.md) — stampede is the amplification triggered by coherence failure
- [incomplete-layer-isolation](incomplete-layer-isolation.md) — new write paths bypassing the cache layer are incomplete isolation
- [doc-spec-drift](doc-spec-drift.md) — the cache invalidation contract drifts from write paths the same way docs drift from code
---
name: silent-semantic-mismatch
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go]
categories: [bug/logic, bug/type-system]
---

# Silent Semantic Mismatch

## Description

The programming language does something technically legal but semantically wrong, and does it silently. The code runs without errors but produces incorrect results because the developer's intent diverges from the language's actual behavior.

This is a family of bugs unified by one property: the language cooperates with the mistake.

**Implicit type coercion:** JS's `"5" + 3 === "53"` but `"5" - 3 === 2`. Python's `True + True === 2`. Comparisons between incompatible types that happen to succeed.

**Identity vs. equality:** Python's `is` vs `==` — works for small integers (interned) but fails for larger values. JS's `==` vs `===` — `0 == "" === true`.

**Floating point comparison:** `0.1 + 0.2 !== 0.3` in every IEEE 754 language. Using `==` on floats.

**Mutable default argument:** Python's `def f(items=[])` — the list is shared across all calls. Every Python dev hits this once; some hit it twice.

**Loop variable capture:** Closures in a loop capture the variable by reference; all closures see the final value. `[lambda: i for i in range(3)]` — all return 2. Go fixed this in 1.22; Python and JS still have it.

**Shallow copy mutation:** `copy = original[:]` or `{...obj}` — nested objects are still shared. Mutations to nested elements affect the original.

**Boolean blindness / stringly-typed interface:** `render(True, False, True)` — what do the bools mean? `process(status="active")` — is "Active" valid? "ACTIVE"? Using bare primitives for domain concepts.

## Detection Heuristic

### Grep-based scan

```bash
# Python: 'is' comparison with non-singleton (should be ==)
grep -rnP '\bis\b\s+(?!None\b|True\b|False\b|not\b)' --include='*.py' .
```

```bash
# Python: mutable default arguments
grep -rnP 'def\s+\w+\(.*=\s*(\[\]|\{\}|set\(\))' --include='*.py' .
```

```bash
# JS: loose equality
grep -rnP '[^=!]==[^=]' --include='*.js' --include='*.ts' .
```

```bash
# Float equality comparison
grep -rnP '==\s*(0\.\d|float|parseFloat|\d+\.\d)' --include='*.py' --include='*.js' .
```

```bash
# Python: lambda/closure in loop
grep -rnP 'for\s+\w+\s+in\s+.*:\s*$' --include='*.py' -A 5 . | grep -P '(lambda|def\s+\w+\()'
```

### Manual triage

1. For comparisons: is identity (`is`, `===`) vs equality (`==`) intentional and correct?
2. For default arguments: are any defaults mutable objects?
3. For closures in loops: does the closure capture a loop variable? Is there a `default=` parameter trick or immediate binding?
4. For shallow copies: are nested objects shared? Are they subsequently mutated?
5. For string/bool parameters: could a typo or case mismatch cause silent wrong behavior?

### LLM-based structured check

> "For each comparison: is identity vs equality correct for the types involved? For each default argument: is any default a mutable object? For each closure created in a loop: does it capture the loop variable by reference? For each copy operation: is it deep enough for the mutations that follow? For each string-typed parameter that selects behavior: is there validation against allowed values? Flag all mismatches."

## Indicators

- `is` comparison returning different results for small vs large integers in Python
- `==` instead of `===` in JavaScript
- `def f(x, cache={})` in Python
- `[lambda: i for i in range(n)]` where all lambdas return the same value
- `copy = original[:]` followed by mutation of nested elements
- Functions with 3+ boolean parameters
- String-typed status/mode/type fields without enum validation

## Example

### Before (buggy)

```python
def make_handlers(names):
    handlers = []
    for name in names:
        handlers.append(lambda: print(f"Handling {name}"))  # Captures 'name' by ref
    return handlers

# All handlers print the LAST name
for h in make_handlers(["alice", "bob", "carol"]):
    h()  # "Handling carol" × 3
```

### After (fixed)

```python
def make_handlers(names):
    handlers = []
    for name in names:
        handlers.append(lambda n=name: print(f"Handling {n}"))  # Default arg binds immediately
    return handlers

for h in make_handlers(["alice", "bob", "carol"]):
    h()  # "Handling alice", "Handling bob", "Handling carol"
```

## Related Patterns

- [missing-edge-case-handling](missing-edge-case-handling.md) — type confusion is an edge case the language hides
- [dual-parser-divergence](dual-parser-divergence.md) — two modules using `is` vs `==` for the same type diverge silently
- [regex-newline-leak](regex-newline-leak.md) — `\s` matching `\n` is another silent semantic mismatch
---
name: implicit-ordering-dependency
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, java, rust]
categories: [bug/logic, design/coupling]
---

# Implicit Ordering Dependency

## Description

System correctness depends on operations executing in a specific order, but that order is not enforced by code — only by convention, documentation, or coincidence. Works until infrastructure changes, concurrency increases, or a new developer doesn't know the rules.

**Initialization ordering:** Module A must initialize before Module B, but nothing enforces this. Kubernetes rolling deploys, auto-scaling events, or import reordering breaks the assumption.

**Migration ordering:** Database migration 005 assumes 004 has run but doesn't declare the dependency. Parallel migration runners or cherry-picked deployments violate this.

**Event processing ordering:** Consumer assumes events arrive in publish order, but the message broker provides at-least-once unordered delivery.

**Configuration loading:** Config from file must be loaded before env var overrides, but the loading code doesn't enforce sequencing.

The common thread: the ordering is load-bearing but invisible. It's documented nowhere, enforced by nothing, and tested by accident.

## Detection Heuristic

### Grep-based scan

```bash
# Find initialization functions that assume prior state
grep -rnP '(init|setup|configure|bootstrap|register)\w*\s*\(' --include='*.py' --include='*.go' --include='*.js' .
```

```bash
# Find comments indicating ordering requirements
grep -rniP '(must be called (before|after|first)|depends on.*being.*init|order matters|call.*before)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Find event/message handlers that assume ordering
grep -rnP '(on_message|handle_event|process_message|consume)' --include='*.py' --include='*.js' . -A 10 | grep -P '(previous|prior|already|sequence|order)'
```

### Manual triage

1. For each initialization function: does it assume state set by another initialization? Is that dependency declared or enforced?
2. For event handlers: do they assume events arrive in order? Does the transport guarantee order?
3. For migrations: is there an explicit dependency graph, or just naming convention (001, 002...)?
4. For multi-service startups: is there a readiness check, or just "Service A starts first by convention"?

### LLM-based structured check

> "For each initialization, setup, or bootstrap function: what state does it assume already exists? Is that state's creation enforced to run first, or is it assumed? For event handlers: do they assume ordering that the transport doesn't guarantee? For migrations: are dependencies declared or just implied by sequence number? Flag all ordering dependencies that are not mechanically enforced."

## Indicators

- Comments saying "must be called after X" or "assumes X is initialized"
- Service startup failures that depend on deploy order
- Works in development (single process, deterministic order) but fails in production (multiple processes, non-deterministic)
- Flaky integration tests that pass individually but fail in CI batches
- Event handlers with state that grows monotonically (sequence counter, "last seen" timestamp)
- Migrations that fail when run out of sequence

## Example

### Before (buggy)

```python
# config.py
_registry = {}

def register_defaults():
    """Must be called before load_overrides — but nothing enforces this."""
    _registry.update({"timeout": 30, "retries": 3, "mode": "standard"})

def load_overrides(overrides):
    """Assumes defaults already registered."""
    for key, value in overrides.items():
        if key not in _registry:
            raise KeyError(f"Unknown config key: {key}")  # Fails if defaults not loaded
        _registry[key] = value

# app.py — works because import order happens to be right
from config import register_defaults, load_overrides
register_defaults()
load_overrides(os.environ)  # Fine... until someone reorders these calls
```

### After (fixed)

```python
# config.py
_DEFAULTS = {"timeout": 30, "retries": 3, "mode": "standard"}
_registry = None

def load_config(overrides=None):
    """Single entry point — ordering is internal, not caller's problem."""
    global _registry
    _registry = dict(_DEFAULTS)
    if overrides:
        unknown = set(overrides) - set(_DEFAULTS)
        if unknown:
            raise KeyError(f"Unknown config keys: {unknown}")
        _registry.update(overrides)
    return _registry

# app.py
from config import load_config
config = load_config(os.environ)  # One call, no ordering dependency
```

## Related Patterns

- [concurrency-violation](concurrency-violation.md) — race conditions are ordering violations under concurrency
- [incomplete-layer-isolation](incomplete-layer-isolation.md) — bypassing the initialization layer creates ordering bugs
- [doc-spec-drift](doc-spec-drift.md) — ordering requirements documented in one place but not enforced in code
---
name: dead-code-latent-path
version: "1.0.0"
discovered: 2026-03-25
languages: [python, javascript, go, java, rust]
categories: [bug/logic, design/maintenance]
---

# Dead Code Latent Path

## Description

Code that is currently unreachable but becomes reachable under deployment changes, configuration changes, feature flag flips, or environmental differences. Unlike benign dead code (unused utility functions), latent paths contain logic that will execute incorrectly when activated because it was never maintained, tested, or even known to exist.

The canonical example: Knight Capital Group, August 2012. A deployment repurposed an old feature flag that activated decade-old order-routing code. The dead code executed, generating $440 million in erroneous trades in 45 minutes. The company was effectively destroyed.

Latent paths arise from: stale feature flags with both branches still in code, commented-out code that gets uncommented, fallback paths never exercised in production, old API versions kept "just in case," and migration code that was supposed to be temporary.

10-30% of a typical codebase is dead code, per industry analysis. Most is harmless. The dangerous subset is code that LOOKS intentional, sits behind a toggle, and has rotted semantically while the rest of the system evolved around it.

## Detection Heuristic

### Grep-based scan

```bash
# Feature flags with both branches — potential latent path
grep -rnP '(if|else)\s+.*\b(feature_flag|flag|toggle|experiment|ENABLE_|DISABLE_|USE_OLD|USE_NEW|LEGACY)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Stale feature flags — defined but potentially never cleaned up
grep -rnP '(FEATURE_|FLAG_|TOGGLE_|EXPERIMENT_)\w+\s*=' --include='*.py' --include='*.js' --include='*.go' . | sort -t= -k1 | head -30
```

```bash
# Fallback/legacy paths
grep -rnP '(fallback|legacy|deprecated|old_|v1_|_backup|_compat)' --include='*.py' --include='*.js' --include='*.go' .
```

```bash
# Unreachable code after return/raise/break
grep -rnP '^\s*(return|raise|break|continue)\s' --include='*.py' -A 1 . | grep -P '^\s+\w' | grep -v '^\s*(#|$|except|finally|else)'
```

### Manual triage

1. For each feature flag: are both branches maintained and tested? When was the flag last toggled?
2. For fallback/legacy code: is it tested? Does it use current APIs and data formats?
3. For commented-out code: does it reference current function signatures and data structures?
4. For code after unconditional return/raise: is it truly dead, or is it reached via exception handlers?

### LLM-based structured check

> "Identify all feature flags, toggle points, and conditional paths that select between 'old' and 'new' behavior. For each: are both paths tested? Is the 'inactive' path maintained — does it use current APIs, data formats, and interfaces? Identify code after unconditional return/raise/break statements. Identify fallback paths — are they exercised in any test? Flag: untested branches behind toggles, unmaintained fallback paths, and code referencing stale interfaces."

## Indicators

- Feature flags older than 6 months with both branches in code
- Functions or modules with "legacy," "old," "deprecated," "v1," "compat" in the name that are still importable
- Code coverage reports showing 0% coverage on entire branches that aren't marked as dead
- Commented-out code blocks longer than 10 lines
- `if False:` or `if 0:` blocks (intentionally disabled but kept)
- Config flags with no owner and no expiration date

## Example

### Before (buggy)

```python
# This flag was added in 2021 for a gradual rollout. The rollout completed in 2022.
# Both branches remain. The old path references APIs that have since changed.
USE_NEW_PRICING = os.environ.get("USE_NEW_PRICING", "true") == "true"

def calculate_price(order):
    if USE_NEW_PRICING:
        return new_pricing_engine.compute(order)
    else:
        # This path hasn't been touched since 2021. It calls an API that now
        # returns a different response format. If the flag is ever set to false
        # (incident rollback, config typo, new environment missing the var),
        # this will either crash or silently compute wrong prices.
        legacy_rate = old_pricing_api.get_rate(order.sku)  # API response changed in 2023
        return legacy_rate * order.quantity  # Missing tax calculation added in 2022
```

### After (fixed)

```python
# Flag removed. Old path deleted. One path, always tested.
def calculate_price(order):
    return new_pricing_engine.compute(order)

# If rollback capability is needed, use version control — not dead code in production.
```

## Related Patterns

- [doc-spec-drift](doc-spec-drift.md) — latent code drifts from current specs the same way docs drift
- [incomplete-layer-isolation](incomplete-layer-isolation.md) — latent paths that bypass current abstraction layers
- [missing-edge-case-handling](missing-edge-case-handling.md) — latent paths are untested edge cases waiting to activate

---
---

# PART 2: Test Anti-Patterns (append to `test-antipatterns`)

Items 13-17 below continue the existing numbering. Slot into the appropriate tiers.

## Tier 1: Actively Harmful (additions)

**13. Assertion Roulette** — Multiple assertions per test with no messages; when one fails, you can't tell which or why without reading source. Detection: count bare `assert` / `assertEqual` calls per test method with no `msg=` parameter. >5 undifferentiated assertions in a single test is a strong signal. Distinct from Green Bar Addict (which has TOO FEW assertions) — this has plenty, but they're anonymous.

**14. Choose Your Own Adventure** — Test contains conditional logic (`if`, `for`, `try/except`) creating branches within the test itself. The test is now a program that itself needs testing. Detection: any `if`/`for`/`while`/`try` inside a test method body (excluding context managers). If the test has branches, some branches are untested. 97% of surveyed developers in test-smell studies recognize this as harmful.

## Tier 2: False Security (additions)

**15. Mystery Guest** — Test depends on external state invisible in the test body: files on disk, database records from another test's setup, environment variables, system locale, or network services. Cause-and-effect is opaque — the test fails and you can't tell why by reading it. Detection: test references file paths, env vars, or external URLs not created within the test or its fixture. Subsumes "The Local Hero" (fails on different OS/timezone/locale) as a specific variant.

**16. The Eager Beaver** — Single test exercises multiple independent production behaviors. When it fails, you know *something* broke but not *what*. Defect localization is destroyed. Detection: test calls 2+ unrelated production methods and asserts on results from each. Test name requires "and" to describe what it tests.

## Tier 3: Missed Opportunities (addition)

**17. The Ice Cream Cone** — Inverted test pyramid: mostly manual or end-to-end tests, minimal unit tests, almost no integration tests. Feedback loop is hours instead of seconds; developers stop running tests locally. Detection: count test files by type (unit vs integration vs e2e). If e2e > unit, the pyramid is inverted. A codebase-level antipattern, not per-test — score it during project audits, not file audits.

## Audit Checklist (additions)

Append to the existing table:

| Check | Red Flag |
|-------|----------|
| Assertion identifiability | >5 assertions per test with no messages |
| Test logic complexity | Conditionals/loops inside test body |
| External dependency visibility | Test relies on state not created in test/fixture |
| Behavioral isolation | Single test exercises multiple unrelated behaviors |
| Pyramid shape | E2E test count exceeds unit test count |

---
---

# PART 3: Analytical Lenses (append to `lens-registry`)

## concurrency
**Focus:** Thread safety, race conditions, synchronization correctness, deadlock potential
**Audit priorities:** Shared mutable state protection, lock ordering consistency, atomic operation correctness, timeout presence on blocking calls, absence of TOCTOU patterns at trust boundaries
**Failure modes:** Data races, deadlocks, priority inversion, blocked-thread pool exhaustion, non-deterministic corruption that passes all tests and only manifests under production load
**Entry point:** Identify all shared mutable state (globals, class-level mutables, caches, connection pools). For each: trace all access sites, check synchronization. Run `go test -race` or equivalent. Ask: "What happens if two requests hit this code path simultaneously?"

## resource-lifecycle
**Focus:** Acquisition, use, and release of system resources on all code paths
**Audit priorities:** File handles, DB connections, sockets, locks, temp files, subprocesses — each must have a corresponding release on every path including exceptions and early returns. Language-idiomatic cleanup (Python `with`, Go `defer`, Java try-with-resources) should be the norm, not the exception.
**Failure modes:** Gradual handle/connection exhaustion, "too many open files" after hours of runtime, connection pool depletion, orphaned temp files filling disk, leaked locks causing deadlocks
**Entry point:** Grep for resource acquisition calls (`open`, `connect`, `socket`, `Lock.acquire`, `subprocess.Popen`). For each: verify cleanup on all paths. Check that cleanup itself handles errors. Ask: "If this function raises on line N, which resources are leaked?"

## idempotency
**Focus:** Whether operations are safe to execute more than once with the same input
**Audit priorities:** Database writes (INSERT vs UPSERT), payment/billing operations, notification dispatch, event handlers, API endpoints that mutate state, queue consumers that may receive duplicate messages
**Failure modes:** Duplicate charges, duplicate notifications, duplicate database records, double-counted metrics, non-convergent state after retry
**Entry point:** For each state-mutating operation: what happens if the exact same request arrives twice? Is there a deduplication key, idempotency token, or UPSERT? For event consumers: does the handler use at-least-once delivery semantics? Ask: "If the network hiccups and this message is delivered twice, does the user get charged twice?"

## observability
**Focus:** Whether the code emits enough telemetry to diagnose failures in production without attaching a debugger
**Audit priorities:** Structured logging at decision points, correlation IDs propagated across service boundaries, metrics for latency/error-rate/saturation, error logs with sufficient context (request ID, user ID, input summary), no PII in logs, log levels appropriate to severity
**Failure modes:** On-call engineer cannot diagnose a 2 AM page without reproducing locally, missing correlation IDs make distributed traces unfollowable, PII leakage in logs, log volume so high that signal is buried, metrics gaps that hide degradation
**Entry point:** For each error path: is there a log entry with enough context to diagnose without source code? For each service boundary: is a correlation ID propagated? For each critical operation: is there a latency metric? Ask: "If this fails at 2 AM, can the on-call engineer figure out what happened from the logs alone?"

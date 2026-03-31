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

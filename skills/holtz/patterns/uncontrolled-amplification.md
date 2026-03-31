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

**Retry storm:** Failed requests trigger aggressive client retries without backoff. N clients x M retries = NxM load on an already-failing server. The retries ARE the outage.

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
3. For queries: is there a LIMIT? What happens when the dataset is 1000x expected size?
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

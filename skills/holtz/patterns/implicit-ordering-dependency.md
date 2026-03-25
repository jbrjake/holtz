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

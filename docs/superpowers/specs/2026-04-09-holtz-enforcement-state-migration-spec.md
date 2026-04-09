# Holtz: Enforcement State Migration to Daemon Memory

Spec for Holtz repo changes. Closes GitHub issue #46.

Related: [Sahjhan daemon spec](2026-04-09-sahjhan-enforcement-state-daemon-spec.md)

## Problem

The enforcement cache (`enforcement-cache.json`) lives on the filesystem and is the source of truth for audit state. The bootstrap hook blocks writes via literal substring matching, but agents can bypass this by constructing paths dynamically at runtime (pathlib, os.path.join, string concatenation, base64, etc.). This was exploited in a live session to escape the stop hook.

## Solution: Read/write enforcement state through the daemon

Replace filesystem reads/writes of `enforcement-cache.json` with daemon socket calls using three new operations: `enforcement_read`, `enforcement_write`, `enforcement_update`. The daemon holds the state in memory — no file to overwrite.

## Changes

### `_protocol_cache.py` — core module

**`read_cache(cwd: str) -> dict[str, Any] | None`**

Replace filesystem read with daemon call:

```python
def read_cache(cwd: str) -> dict[str, Any] | None:
    try:
        sock_path = _get_daemon_socket_path(cwd)
        resp = _daemon_request(sock_path, {"op": "enforcement_read"})
        return json.loads(base64.b64decode(resp["data"]))
    except Exception:
        return None
```

Fail-open behavior is preserved: if the daemon is unreachable, dead, or has no enforcement state, returns `None` — identical to the current "file not found" path. All existing callers already handle `None`.

**`write_cache(cwd: str, cache: dict[str, Any]) -> None`**

Replace filesystem write with daemon call:

```python
def write_cache(cwd: str, cache: dict[str, Any]) -> None:
    sock_path = _get_daemon_socket_path(cwd)
    data = base64.b64encode(json.dumps(cache).encode()).decode()
    _daemon_request(sock_path, {"op": "enforcement_write", "data": data})
```

No longer sets `last_refresh` locally — the daemon does this. Raises on failure (daemon unreachable = can't write state = caller's try/except handles it).

**`update_cache(cwd: str, patch: dict[str, Any]) -> dict[str, Any]`**

New function for atomic read-modify-write:

```python
def update_cache(cwd: str, patch: dict[str, Any]) -> dict[str, Any]:
    sock_path = _get_daemon_socket_path(cwd)
    data = base64.b64encode(json.dumps(patch).encode()).decode()
    resp = _daemon_request(sock_path, {"op": "enforcement_update", "patch": data})
    return json.loads(base64.b64decode(resp["data"]))
```

Returns the full merged state. Raises on failure.

**Deleted code:**
- `_cache_path(cwd)` — no longer needed
- `CACHE_FILENAME` constant — no longer needed
- Atomic tempfile write logic in old `write_cache` — no longer needed
- The `import tempfile` block — no longer needed

**Unchanged code:**
- `empty_cache()` — still constructs the initial state dict
- `_read_perspectives_total()` — still reads protocol.toml for perspective count
- `is_enforcement_fresh()` — still checks `last_sahjhan_cmd` from the dict
- `parse_status_text()` — still parses sahjhan CLI output
- `compute_obligations()`, `format_injection()`, `format_state_line()` — operate on dicts
- `_split_shell_segments()`, `is_git_commit()`, `is_sahjhan_cmd()` — unrelated utilities

### `protocol_tracker.py` — write-path changes

Current pattern (read → mutate → write):
```python
cache = read_cache(cwd)
cache["stall"] += 1
write_cache(cwd, cache)
```

New pattern (atomic update):
```python
update_cache(cwd, {"stall": cache["stall"] + 1})
```

Specific call sites:

1. **Stall increment** (on non-sahjhan bash commands): `update_cache(cwd, {"stall": current_stall + 1})`
2. **Commit registration** (on git commit): `update_cache(cwd, {"unregistered_commits": updated_list, "stall": 0})`
3. **Full refresh** (after sahjhan status): `write_cache(cwd, fully_rebuilt_cache)` — unchanged, still a full write

For (1) and (2), the tracker still calls `read_cache` first to get the current value, then computes the new value and sends it via `update_cache`. The atomicity guarantee is that no other caller can interleave between the daemon's read and write of the merged state. Since hooks are sequential within a Claude session, this is defense-in-depth rather than a concurrency requirement.

### `_daemon_lifecycle.py` — daemon death handling

Current behavior on daemon death: writes `terminated` marker AND updates enforcement cache on disk.

New behavior: writes `terminated` marker only. The enforcement cache no longer exists on disk. When the daemon is dead, `read_cache()` returns `None` (daemon unreachable), and callers handle this the same way they handle "no cache file" today — the stop hook's daemon-liveness check (which runs before the cache check) catches this case and allows exit.

### `stop_hook.py` — no changes needed

The stop hook already has this flow:
1. Check for `terminated` marker → allow exit
2. Check daemon PID liveness → if dead, write `terminated`, allow exit
3. `read_cache(cwd)` → if `None`, block (unknown state)
4. Check state → allow/block based on state

With daemon-backed state, step 3 returns `None` when the daemon is dead, but step 2 already catches that case and allows exit. The only scenario where step 3 returns `None` with a live daemon is if enforcement state was never written — which is the same as today's "no cache file" case.

### `commit_gate.py`, `primer.py`, `post_tool_hook.py` — no changes needed

These all call `read_cache(cwd)` and handle `None` return. The function signature is unchanged.

### `_sahjhan_bootstrap.py` — minimal changes

The `MANAGED_DATA` list still includes `"docs/holtz/.sahjhan/"` as defense-in-depth. The filesystem directory still contains `daemon.sock`, `daemon-init-pid`, `ledger.jsonl`, `ledgers.toml`, `manifest.json`, and the `terminated` marker — all worth protecting from agent writes.

The interpreter guard bypass described in issue #46 becomes a non-issue for enforcement state (the target file no longer exists), but remains relevant for the other managed files. No guard code changes needed.

### `_common.py` — no changes needed

`_get_daemon_socket_path()` and `_daemon_request()` are already the right abstraction. The new operations use them directly.

### New imports in `_protocol_cache.py`

Add `base64` import. Add import of `_get_daemon_socket_path` and `_daemon_request` from `_common`.

## Graceful degradation

| Scenario | `read_cache` | `write_cache` / `update_cache` |
|----------|-------------|-------------------------------|
| Daemon running, state exists | Returns dict | Succeeds |
| Daemon running, no state yet | Returns `None` | `write_cache` succeeds; `update_cache` raises (no state to patch) |
| Daemon dead | Returns `None` | Raises `RuntimeError` |
| Daemon never started | Returns `None` | Raises `RuntimeError` |
| Socket permission denied | Returns `None` | Raises `RuntimeError` |

This matches current behavior: hooks that only read (`stop_hook`, `commit_gate`, `primer`, `post_tool_hook`) degrade gracefully on `None`. The only writer (`protocol_tracker`) already wraps writes in try/except.

## Migration

No migration needed. The enforcement cache is ephemeral — it's recreated every audit session. Old `enforcement-cache.json` files from prior sessions are inert (nothing reads them anymore). They can be cleaned up by `sahjhan init` or left to rot.

## Minimum sahjhan version

This requires sahjhan with enforcement state operations. The `.sahjhan-version` marker in `bin/` should be bumped to the version that includes these ops. The Holtz `_daemon_lifecycle.py` already checks daemon reachability — no version negotiation needed; if the daemon doesn't support the op, it returns an error, and hooks degrade gracefully.

## Testing

1. **Unit test**: `read_cache` returns `None` when daemon unreachable (mock socket error).
2. **Unit test**: `read_cache` returns parsed dict when daemon returns valid response.
3. **Unit test**: `write_cache` sends correct base64-encoded payload to daemon.
4. **Unit test**: `update_cache` sends correct patch and returns merged state.
5. **Unit test**: `write_cache` raises when daemon unreachable.
6. **Integration test**: `protocol_tracker` stall increment uses `update_cache`.
7. **Integration test**: `protocol_tracker` commit registration uses `update_cache`.
8. **Integration test**: Stop hook allows exit when daemon is dead (read_cache returns None after liveness check).
9. **Regression test**: Pathlib-based enforcement cache bypass (from issue #46) no longer works — there's no file to overwrite.

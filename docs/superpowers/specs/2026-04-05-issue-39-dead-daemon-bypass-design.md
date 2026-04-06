# Issue #39: Dead Daemon Silently Disables All Enforcement

**Date:** 2026-04-05
**Issue:** #39
**Status:** Design approved

## Problem

When the Sahjhan daemon dies silently during an active audit, every enforcement hook falls back to "allow" — the entire protocol layer goes dark. The agent proceeds with zero TDD gate enforcement, zero commit registration, and zero protocol violations recorded. Additionally, `_sahjhan_bootstrap.py` doesn't check `MANAGED_DATA` paths for Write/Edit tools, allowing the agent to overwrite `enforcement-cache.json` directly and escape the stop hook.

## Design Decision

**Approach: Shared utility function — fail-closed during active audits.**

A centralized `exit_enforcement_error()` function replaces `exit_ok()` at every daemon-failure fallback path. During an active audit with fresh enforcement, daemon failures are treated as blocks (PreToolUse) or warnings (PostToolUse). Outside audits or with stale enforcement, fail-open behavior is preserved.

Combined with:
- Bootstrap path protection gap fix (MANAGED_DATA in Write/Edit check)
- Daemon lifecycle hardening (block on failed restart during active audit)

## Out of Scope

- P4: Stop hook local evaluation of `output_contains_any` patterns
- P5: Cache reading ledger state directly instead of parsing command output

These are valuable follow-ups but not required to close the bypass.

---

## Component 1: `exit_enforcement_error()` Shared Utility

**File:** `enforcement/hooks/_common.py`

New function that makes the block/allow decision centrally:

```python
def exit_enforcement_error(
    cwd: str,
    reason: str,
    hook_type: str = "PreToolUse",
) -> None:
    """Block if active audit + fresh enforcement, else allow.

    Replaces exit_ok() at daemon-failure fallback paths. During an
    active, fresh audit, daemon failures are blocks (PreToolUse) or
    warnings (PostToolUse). Outside audits or stale, fail-open.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if os.path.isdir(data_dir):
        cache = read_cache(cwd)
        if is_enforcement_fresh(cache):
            if hook_type == "PreToolUse":
                exit_block(f"ENFORCEMENT DEGRADED: {reason}")
            else:
                exit_warn(f"ENFORCEMENT DEGRADED: {reason}")
    # No active audit or stale enforcement — fail-open
    exit_ok("PreToolUse" if hook_type == "PreToolUse" else "")
```

Requires importing `read_cache` and `is_enforcement_fresh` from `_protocol_cache` in `_common.py`.

## Component 2: Bootstrap Path Protection Gap (P2)

**File:** `enforcement/hooks/_sahjhan_bootstrap.py`

In `main()`, after the existing `PROTECTED` loop (line 279-287), add a second loop for `MANAGED_DATA` paths. These are relative to `cwd` (not `_PLUGIN_ROOT`):

```python
# MANAGED_DATA paths are relative to cwd
for p in MANAGED_DATA:
    full = os.path.realpath(os.path.join(cwd, p))
    if resolved == full or resolved.startswith(full + os.sep):
        _block(
            f"BLOCKED: {path} is in the Sahjhan data directory. "
            "This path cannot be modified during an audit session."
        )
```

This closes the escape hatch that allowed the agent to overwrite `enforcement-cache.json` via the Write tool.

## Component 3: Daemon Lifecycle Hardening (P3 + P6)

**File:** `enforcement/hooks/_daemon_lifecycle.py`

Two changes:

### 3a: Block on failed restart during active audit

Replace the unconditional `exit_ok()` after `_start_daemon()`:

```python
# Current:
_start_daemon(cwd)
exit_ok()  # Always allow

# New:
started = _start_daemon(cwd)
if not started:
    pid = _daemon_pid(cwd)
    if pid is None or not _is_process_alive(pid):
        exit_enforcement_error(
            cwd, "Daemon restart failed — enforcement cannot evaluate"
        )
exit_ok()
```

### 3b: Verify PID after daemon start

Harden `_start_daemon()` to verify the daemon is actually alive after a successful return code:

```python
def _start_daemon(cwd: str) -> bool:
    # ... existing subprocess.run code ...
    if result.returncode == 0:
        pid = _daemon_pid(cwd)
        return pid is not None and _is_process_alive(pid)
    return False
```

## Component 4: Hook-by-Hook Fallback Path Changes

### `pre_tool_hook.py` — 5 paths change

| Line | Current | New |
|------|---------|-----|
| 56-57 | `binary is None → exit_ok` | `exit_enforcement_error(cwd, "Sahjhan binary unavailable")` |
| 60-61 | `not config_found → exit_ok` | `exit_enforcement_error(cwd, "Enforcement config not found")` |
| 85-86 | `OSError/TimeoutExpired → exit_ok` | `exit_enforcement_error(cwd, "Hook eval subprocess failed")` |
| 88-89 | `returncode != 0 → exit_ok` | `exit_enforcement_error(cwd, "Hook eval returned error")` |
| 93-94 | `JSONDecodeError → exit_ok` | `exit_enforcement_error(cwd, "Hook eval returned invalid JSON")` |

**Unchanged:** Line 52-53 stale enforcement fast-path stays `exit_ok`.

### `post_tool_hook.py` — 3 paths change (PostToolUse → warn)

| Line | Current | New |
|------|---------|-----|
| 113-115 | `binary is None → exit_ok` | `exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")` |
| 117-119 | `not config_found → exit_ok` | `exit_enforcement_error(cwd, "Enforcement config not found", "PostToolUse")` |
| 141 | subprocess/JSON fail → `pass` (eval_data stays `{}`) | Replace `pass` with `exit_enforcement_error(cwd, "Hook eval failed", "PostToolUse")` inside the except block. This exits before reaching the auto_record processing with empty eval_data. |

**Unchanged:** Line 110-111 stale check.

### `bash_guard.py` — 2 paths change (PostToolUse → warn)

| Line | Current | New |
|------|---------|-----|
| 39-41 | `binary is None → exit_ok` | `exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")` |
| 69-70 | `OSError/TimeoutExpired → exit_ok` | `exit_enforcement_error(cwd, "Manifest verify failed", "PostToolUse")` |

**Unchanged:** Line 52-54 stale check.

## Component 5: Unchanged Files

- **`stop_hook.py`** — Already fail-closed (blocks when cache missing, blocks when fresh + non-terminal). No changes.
- **`commit_gate.py`** — Reads local cache only, no daemon communication. No changes.
- **`protocol_tracker.py`** — PostToolUse, writes cache only. If daemon is dead, PreToolUse block prevents further tool execution. Silent failure acceptable.
- **`hooks.toml`** — Rules unchanged. Evaluated by `sahjhan hook eval` via `pre_tool_hook.py`.
- **Stale enforcement checks** — All unchanged. The 30-minute escape valve remains.

## Testing Strategy

- Unit tests for `exit_enforcement_error()`: active+fresh→block, active+stale→allow, no audit→allow
- Unit tests for bootstrap MANAGED_DATA check: Write to `.sahjhan/` path → blocked
- Unit tests for daemon lifecycle: restart fails during active audit → block
- Integration: mock dead daemon, verify PreToolUse hooks block during active audit
- Regression: verify all hooks still allow when no `.sahjhan/` dir exists

# Daemon Lifecycle Integration — Issue #37

## Problem

Three bugs prevent the `awaiting_clear → fix_loop` transition after `/clear`:

1. **Daemon never started** — No orchestration code calls `sahjhan daemon start`. Hooks that need signing/vault (`primer.py`, `lens_quiz.py`) fail silently.
2. **`active-run` marker never written** — `write_active_run_marker()` exists but is never called. Hooks get `None` from `_active_ledger()`, targeting the wrong ledger.
3. **`context_reset` silently fails** — `primer.py` catches the daemon connection error, injects a warning, but the gate (`ledger_has_event_since: context_reset`) never opens. State stuck forever.

Additionally, there is no mechanism to stop the daemon at audit end or during cleanup of failed/abandoned audits.

## Approach

Belt and suspenders: instruction-layer changes tell the agent what to do, hook-layer changes catch failures automatically.

## Changes

### 1. `phase-recon.md` Step 0 — Instruction Layer (Start)

Update the initialization sequence from:

```
sahjhan ledger create --from run N
sahjhan transition run_start
```

to:

```
sahjhan daemon start
sahjhan ledger create --from run N
sahjhan transition run_start
```

Daemon must start **before** ledger creation because `ledger create` itself doesn't need the daemon, but subsequent hooks fire immediately after `transition run_start` and may need signing.

### 2. `phase-finalize.md` Step 20 — Instruction Layer (Stop)

After `sahjhan transition finalize`, add:

```
sahjhan daemon stop
```

This is the normal teardown path for successful audits.

### 3. New `_daemon_lifecycle.py` — PreToolUse Hook (Safety Net)

A new `PreToolUse` hook that ensures the daemon and active-run marker are present whenever an active audit exists. Runs on every tool use but is designed to be near-zero cost when everything is healthy.

**Logic:**

```
1. Check if docs/holtz/.sahjhan/ exists. If not → exit (no active audit).
2. Check if docs/holtz/.sahjhan/active-run exists.
   - If missing, scan docs/holtz/runs/ for the highest-numbered run-N directory.
   - If found, call write_active_run_marker(cwd, "run-N") to create it.
   - If no runs found → exit (no active audit despite data dir existing).
3. Check daemon health:
   a. Read docs/holtz/.sahjhan/daemon.pid
   b. If PID file missing → daemon not running → start it.
   c. If PID file exists → os.kill(pid, 0) to check if process is alive.
   d. If process dead → start daemon.
   e. If process alive → exit (healthy, nothing to do).
4. Start daemon: subprocess.run([binary, "daemon", "start"], cwd=cwd, timeout=5)
   - On success → exit (daemon now running).
   - On failure → exit with no block (graceful degradation, don't break the tool call).
```

**Performance:** Steps 1-3 are pure filesystem/syscall operations (stat, open, kill(0)). No subprocess calls unless the daemon actually needs starting. Healthy-path cost: ~2 stat calls + 1 file read + 1 kill(0) = microseconds.

**Never blocks:** This hook always allows the tool call. It's a best-effort daemon supervisor, not a gatekeeper. If daemon start fails, downstream hooks handle the degradation (primer warns, quiz retries).

**Hook registration:** Add to `hooks.json` as a `PreToolUse` hook with `"matcher": "*"` (all tools). Must be the first hook in the `*` matcher list so the daemon is healthy before any other hook needs it. Does not conflict with `_sahjhan_bootstrap.py` — the bootstrap hook blocks the *agent* from running `daemon stop/sign/vault` via Bash, but `_daemon_lifecycle.py` is a hook script calling the binary directly, not via the agent's Bash tool.

The `*` matcher is necessary because daemon-dependent hooks fire across multiple event types: `SubagentStop` (lens_quiz), `UserPromptSubmit` (primer), and `PreToolUse` (various). By catching `PreToolUse *`, the lifecycle hook ensures the daemon is alive before the earliest possible consumer.

### 4. `primer.py` Enhancement — UserPromptSubmit (Targeted Fix)

Currently, when `record_authed_event("context_reset", ...)` fails (line 92), primer sets `context_reset_failed = True` and injects a warning. This is the exact codepath that causes the stuck `awaiting_clear` state.

**Change:** Before falling through to the warning, attempt daemon restart and retry:

```python
except (OSError, subprocess.TimeoutExpired, RuntimeError):
    # Daemon may be down — attempt restart and retry once
    restarted = _try_restart_daemon(cwd, binary)
    if restarted:
        try:
            record_authed_event(...)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            context_reset_failed = True
    else:
        context_reset_failed = True
```

`_try_restart_daemon()` is a small helper: runs `sahjhan daemon start`, returns True if exit code 0. This is the direct fix for the reported bug — even if the lifecycle hook didn't fire (e.g., fresh post-`/clear` context where no tool use has happened yet), primer self-heals.

### 5. `protocol_tracker.py` Enhancement — PostToolUse (Teardown Safety Net)

After `_refresh_from_sahjhan()` updates the cache, check if the new state is `finalized`:

```python
if cache.get("state") == "finalized":
    _stop_daemon(cwd, binary)
```

`_stop_daemon()`: runs `sahjhan daemon stop`, ignoring errors (best-effort). This catches the case where the agent follows the finalize instructions but forgets or skips the `daemon stop` command.

### 6. `stop_hook.py` Enhancement — Session End Cleanup

When `stop_hook.py` **allows** the session to stop (terminal state or stale audit), attempt daemon cleanup before exiting:

```python
# Terminal or idle — allow stop, clean up daemon
if current_state in _STOP_ALLOWED_STATES:
    _try_stop_daemon(cwd)
    exit_stop_allow()

# Stale enforcement — warn, clean up daemon
if not is_enforcement_fresh(cache):
    _try_stop_daemon(cwd)
    exit_stop_warn(...)
```

When `stop_hook.py` **blocks** the session stop (active non-terminal audit), add a message informing the user they can manually kill the daemon:

```python
exit_stop_block(
    f"Audit is in state '{current_state}' which is not terminal. "
    "You must complete the audit protocol before stopping. "
    "If this audit cannot be completed, you can manually run: "
    "! sahjhan daemon stop"
)
```

`_try_stop_daemon()`: finds the sahjhan binary via `ensure_sahjhan()`, runs `sahjhan daemon stop`, ignores errors. Best-effort — if daemon is already dead, no harm done.

### 7. `_sahjhan_bootstrap.py` — No Changes

`daemon stop` remains blocked for the agent. Only hook scripts and the user's direct shell can stop the daemon. This is intentional — the agent must not be able to kill its own enforcement infrastructure.

## Files Modified

| File | Change | Type |
|------|--------|------|
| `skills/holtz/references/phase-recon.md` | Add `sahjhan daemon start` to Step 0 | Instruction |
| `skills/holtz/references/phase-finalize.md` | Add `sahjhan daemon stop` to Step 20 | Instruction |
| `enforcement/hooks/_daemon_lifecycle.py` | New file — PreToolUse daemon supervisor | Hook |
| `enforcement/hooks/primer.py` | Restart-and-retry on context_reset failure | Hook |
| `enforcement/hooks/protocol_tracker.py` | Stop daemon on finalized state | Hook |
| `enforcement/hooks/stop_hook.py` | Daemon cleanup on allowed stop; user hint on blocked stop | Hook |
| `hooks/hooks.json` | Register `_daemon_lifecycle.py` | Config |

## Files NOT Modified

| File | Reason |
|------|--------|
| `enforcement/hooks/_sahjhan_bootstrap.py` | `daemon stop` stays blocked for agent — correct behavior |
| `enforcement/hooks/_common.py` | `write_active_run_marker()` already exists, no changes needed |
| `enforcement/hooks/lens_quiz.py` | Already handles daemon errors; lifecycle hook prevents them |

## Testing Strategy

- Unit tests for `_daemon_lifecycle.py`: mock filesystem states (no data dir, missing marker, dead PID, live PID, missing PID file)
- Unit tests for `primer.py` restart-and-retry path
- Unit tests for `protocol_tracker.py` daemon stop on finalized
- Unit tests for `stop_hook.py` daemon cleanup and user hint message
- Existing bootstrap tests remain unchanged (daemon start still allowed, daemon stop still blocked)

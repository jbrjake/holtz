# Daemon Death = Audit Terminal

**Date:** 2026-04-06
**Related:** jbrjake/holtz#37, jbrjake/sahjhan#24
**Status:** Draft

## Problem

Every Holtz hook that detects a dead daemon attempts restart-and-retry. This is wrong. The daemon holds the HMAC session key exclusively in memory. When the daemon dies:

1. The key is gone — OS reclaims memory
2. `sahjhan daemon start` generates a **new** key
3. Events signed with the new key don't chain with events signed by the old key
4. The ledger's integrity guarantee is broken — a restarted daemon is a different daemon

Current code treats daemon death as a transient failure. It's not. It's audit-terminal. The restart-and-retry paths in `_daemon_lifecycle.py`, `primer.py`, and the `exit_enforcement_error` fallback all mask a fundamentally unrecoverable state.

The secondary problem: `awaiting_clear` is the most dangerous state for daemon survival. No hooks fire during the idle window (no tool use = no `PreToolUse`/`PostToolUse`). The user may be away for hours. If the daemon dies here, primer.py is the only hook that runs (on `UserPromptSubmit`), and it cannot recover.

jbrjake/sahjhan#24 addresses the daemon side (configurable idle timeout so the daemon doesn't die unnecessarily). This spec addresses the Holtz side: what to do when the daemon dies anyway.

## Design

### Principle: detect death, don't mask it

If the daemon PID from audit init is dead, the audit is over. No restart attempts. No retry. No degraded mode. Block everything, inform the user, allow stop.

### Component 1: Daemon identity tracking

**Problem:** Current code only checks "is a daemon running?" It cannot distinguish "the original daemon" from "a freshly restarted daemon with a different key."

**Solution:** Record the daemon's PID at audit initialization time. On every lifecycle check, verify the *same* PID is alive — not just *any* PID.

**File:** `docs/holtz/.sahjhan/daemon-init-pid`

Written once during audit init (Step 0 in phase-recon.md), immediately after `sahjhan daemon start`:

```
72578
```

Single line, the PID of the daemon started for this audit. This file is never updated — if the PID dies, the audit is dead.

**Init sequence (phase-recon.md Step 0):**
```
sahjhan --config-dir <config> daemon start
# read daemon.pid, write to daemon-init-pid
sahjhan ledger create --from run-N
sahjhan transition run_start
```

### Component 2: `_daemon_lifecycle.py` — detect death, never restart

Current behavior:
1. Check PID → dead? → restart → restart failed? → `exit_enforcement_error`
2. Restart succeeded? → `exit_ok` (wrong — new key)

New behavior:
1. Read `daemon-init-pid` (the PID from audit init)
2. If file doesn't exist → `exit_ok` (no audit, or pre-daemon-tracking audit)
3. If init PID is alive → `exit_ok` (healthy)
4. If init PID is dead → **audit is terminated**:
   a. Write `docs/holtz/.sahjhan/terminated` marker with reason
   b. Update `enforcement-cache.json` state to `"terminated"`
   c. `exit_block("AUDIT TERMINATED: daemon died — session key lost, ledger unwritable. The audit cannot be completed. Please /stop.")`

No restart attempt. No retry. No `_start_daemon()` call.

```python
def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Already terminated — block immediately
    terminated = os.path.join(data_dir, "terminated")
    if os.path.isfile(terminated):
        exit_block(
            "AUDIT TERMINATED: daemon died — session key lost. "
            "The audit cannot be completed. /stop to exit."
        )

    # Check init PID
    init_pid_file = os.path.join(data_dir, "daemon-init-pid")
    try:
        with open(init_pid_file) as f:
            init_pid = int(f.read().strip())
    except (OSError, ValueError):
        # No init PID tracked — legacy audit or pre-init.
        # Can't distinguish original daemon from restart.
        # Allow rather than kill audits started before this feature.
        exit_ok()

    # Init PID exists — is it still alive?
    if _is_process_alive(init_pid):
        _ensure_active_run_marker(cwd)
        exit_ok()

    # Init PID is dead. Audit is over.
    _write_terminated_marker(cwd, init_pid)
    exit_block(
        "AUDIT TERMINATED: daemon (PID {}) died — session key lost, "
        "ledger unwritable. The audit cannot be completed. "
        "/stop to exit.".format(init_pid)
    )
```

### Component 3: `primer.py` — no restart, check terminated

Current behavior: record `context_reset`, if daemon socket fails → restart → retry → warning.

New behavior:
1. Check `terminated` marker → if present, inject termination message and exit
2. Attempt `record_authed_event` → if socket fails, daemon is dead
3. On failure: check init PID → if dead, write terminated marker, inject termination message
4. No restart. No retry.

```python
# Replace lines 96-126 in primer.py
context_reset_failed = False
try:
    record_authed_event(
        "context_reset",
        {"project": "holtz", "run": run_number,
         "auditor": "holtz", "trigger": "user_prompt_submit"},
        cwd=cwd, ledger=ledger,
    )
except (OSError, subprocess.TimeoutExpired, RuntimeError):
    # Don't restart. Check if daemon init PID is dead.
    init_pid = _read_init_pid(cwd)
    if init_pid is not None and not _is_process_alive(init_pid):
        _write_terminated_marker(cwd, init_pid)
    context_reset_failed = True
```

The injected context message changes from "start daemon and retry" to:

```
AUDIT TERMINATED: daemon died during awaiting_clear — session key lost.
The ledger is unwritable. This audit cannot be completed.
Use /stop to exit, then start a new audit.
```

### Component 4: `terminated` marker file

**Path:** `docs/holtz/.sahjhan/terminated`

Written by whichever hook first detects daemon death. Contents:

```
reason: daemon_pid_dead
init_pid: 72578
detected_by: _daemon_lifecycle
detected_at: 2026-04-06T14:23:07Z
```

All hooks check for this file first — fast path to block/inform without repeating PID checks. The `stop_hook.py` checks for this file and **allows** stop (it's already in `_STOP_ALLOWED_STATES` logic, but we add an explicit terminated check).

### Component 5: `stop_hook.py` — allow stop on terminated

Add to the early-exit logic:

```python
# Terminated audit — always allow stop
terminated = os.path.join(data_dir, "terminated")
if os.path.isfile(terminated):
    exit_stop_allow()
```

### Component 6: Enforcement cache update

When writing the `terminated` marker, also update `enforcement-cache.json`:

```python
def _write_terminated_marker(cwd, init_pid, detected_by="unknown"):
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    marker = os.path.join(data_dir, "terminated")
    with open(marker, "w") as f:
        f.write(f"reason: daemon_pid_dead\n")
        f.write(f"init_pid: {init_pid}\n")
        f.write(f"detected_by: {detected_by}\n")
        f.write(f"detected_at: {datetime.utcnow().isoformat()}Z\n")

    # Update cache so stop_hook reads terminated state
    cache_path = os.path.join(data_dir, "enforcement-cache.json")
    try:
        with open(cache_path) as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        cache = {}
    cache["state"] = "terminated"
    cache["terminated_reason"] = "daemon_pid_dead"
    cache["active"] = False
    with open(cache_path, "w") as f:
        json.dump(cache, f)
```

### Component 7: Remove `_try_restart_daemon` and `_start_daemon` from hook code

**Delete entirely:**
- `primer.py:_try_restart_daemon()` (lines 34-47)
- `_daemon_lifecycle.py:_start_daemon()` (lines 65-86)

These functions embody the wrong mental model. Daemon start belongs exclusively in the audit initialization sequence (phase-recon.md Step 0), not in hook recovery paths.

**Keep:** The daemon start logic in phase-recon.md Step 0 instructions. That's the one legitimate place to start the daemon.

## What this does NOT change

- **`exit_enforcement_error()`** — unchanged. Still used for non-daemon failures (binary missing, config missing, subprocess errors). These are genuinely transient.
- **`_sahjhan_bootstrap.py`** — unchanged. Path protection doesn't depend on daemon.
- **`bash_guard.py`** — keeps `exit_enforcement_error` for manifest verify failures (these don't imply daemon death).
- **`pre_tool_hook.py` / `post_tool_hook.py`** — keep `exit_enforcement_error` for hook eval failures. If daemon death caused the eval failure, `_daemon_lifecycle.py` already blocked (it runs first on `PreToolUse`).
- **State machine** — no new `terminated` state in `states.toml`. The terminated marker is outside the ledger (because we can't write to the ledger). The state machine simply freezes wherever it was.

## Interaction with jbrjake/sahjhan#24

The sahjhan issue requests configurable idle timeout so the daemon doesn't die unnecessarily. This spec handles the case where it dies anyway (crash, OOM, kill, macOS cleanup). The two are complementary:

- sahjhan#24 reduces the frequency of daemon death (prevention)
- This spec handles daemon death correctly when it occurs (detection + response)

Both are needed. Relying on only prevention means one unexpected daemon death silently corrupts an audit. Relying on only detection means audits die unnecessarily during `awaiting_clear`.

## Testing strategy

1. **Unit: `_daemon_lifecycle.py`**
   - Init PID alive → exit_ok
   - Init PID dead → writes terminated marker, exit_block
   - Terminated marker exists → exit_block (fast path)
   - No init PID file → exit_ok (legacy compat)

2. **Unit: `primer.py`**
   - Terminated marker exists → inject termination message
   - Socket fails + init PID dead → write terminated marker
   - Socket fails + no init PID file → context_reset_failed warning (legacy)

3. **Unit: `stop_hook.py`**
   - Terminated marker exists → exit_stop_allow

4. **Unit: `_write_terminated_marker`**
   - Creates marker file with correct fields
   - Updates enforcement-cache.json state to "terminated"
   - Handles missing/corrupt cache file

5. **Integration: full daemon death scenario**
   - Start audit, start daemon, record init PID
   - Kill daemon
   - Next PreToolUse → lifecycle detects death, writes marker, blocks
   - Stop hook → allows stop

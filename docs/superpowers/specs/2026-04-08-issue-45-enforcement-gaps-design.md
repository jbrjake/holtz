# Enforcement Gap Closure — Issue #45

## Problem

During a Holtz audit, the agent encountered broken daemon auth on macOS. Unable to advance the protocol, it escalated to `sahjhan reset`, wiping the entire ledger. The enforcement system defends against an agent *advancing* illegitimately but not against an agent *destroying the enforcement system itself*. Five gaps:

1. Daemon caller auth fails silently on macOS (LOCAL_PEERCRED PID resolution unreliable)
2. `sahjhan reset` is unprotected — agent can self-serve the token from the error message
3. Bootstrap hook has no defense against destructive sahjhan commands (`reset`, etc.)
4. SKILL.md doesn't instruct the agent to stop when enforcement is broken
5. Stop hook creates an inescapable loop — remediation advice doesn't actually unblock

## Approach

Four changes in this repo (Python-side), two daemon-side requirements filed to jbrjake/sahjhan.

---

## Holtz Changes (this repo)

### 1. Allowlist model in `_sahjhan_bootstrap.py`

Replace `BLOCKED_DAEMON_CMDS` blocklist with `ALLOWED_SAHJHAN_SUBCMDS` allowlist. Anything not on the list is blocked by default.

```python
ALLOWED_SAHJHAN_SUBCMDS = {
    "status",        # Read protocol state
    "event",         # Record standard events
    "authed-event",  # Record restricted events (daemon verifies proof)
    "transition",    # Advance protocol state (daemon enforces gates)
    "hook",          # Hook evaluation (called by pre_tool_hook.py)
    "manifest",      # Manifest verify (called by bash_guard.py)
    "ledger",        # Ledger queries (read-only subcommands)
    "render",        # Render STATUS.md/PUNCHLIST.md from ledger
}
```

Replace `_bash_references_daemon_cmd()` with `_bash_references_sahjhan()`:
- Find `sahjhan` token in the command, extract the next token as subcommand.
- If subcommand not in `ALLOWED_SAHJHAN_SUBCMDS` → block.
- Bare `sahjhan` with no subcommand → block.
- Must skip flags before the subcommand (`sahjhan --config-dir <path> status` → subcommand is `status`).
- Must handle chained commands (`&&`, `||`, `;`) — check each segment.

Files: `enforcement/hooks/_sahjhan_bootstrap.py`

### 2. Stop hook daemon liveness check

Add inline daemon liveness check to `stop_hook.py` between the terminated-marker check and the cache read. Uses existing `_read_init_pid()` and `_is_process_alive()` from `_common.py`.

New logic inserted after line 76 (terminated marker check):

```
1. Read daemon-init-pid file
2. If file exists and process is dead → write terminated marker, allow stop
3. If file doesn't exist → no daemon session to protect → allow stop
```

When the stop hook itself detects a dead daemon, it writes the `terminated` marker (so future checks fast-path) and allows stop.

Update the block message (line 108-113) to:

```
Audit is in state '{state}' which is not terminal.
You must complete the audit protocol before stopping.
If this audit cannot be completed, the user can manually run:
! sahjhan daemon stop
(The next stop attempt will detect the dead daemon and allow exit.)
```

Files: `enforcement/hooks/stop_hook.py`

### 3. Fail-closed auth failure in `primer.py`

When `compute_event_proof()` or `record_authed_event()` fails for `context_reset`, inject a hard stop instruction instead of the current soft warning.

Injection text:

```
⛔ ENFORCEMENT FAILURE — STOP IMMEDIATELY

Daemon authentication failed. The context_reset event cannot be recorded,
which means protocol gates are permanently blocked for this session.

This is an unrecoverable state. Do NOT attempt to:
- Reset the ledger (sahjhan reset)
- Modify .sahjhan/ contents directly
- Work around the blocked gate

Report this failure to the user and wait for instructions.
```

The primer still injects resume context (state, perspective) so the user can understand where the audit was. But the instruction is: stop working, report to user.

Files: `enforcement/hooks/primer.py`

### 4. SKILL.md hard gate and rationalization red flag

Add to hard gates section:

```markdown
## Unrecoverable Protocol State

Cannot advance through legitimate transitions → STOP. A broken enforcement state is a finding, not an obstacle. Report to user. Never run `sahjhan reset` or modify `.sahjhan/` directly.
```

Add one row to the rationalization red flags table:

| Your thought | The reality |
|---|---|
| "The enforcement is broken, I'll reset and start fresh" | Broken state is evidence. Report and stop. |

Files: `skills/holtz/SKILL.md`

---

## Daemon Requirements (jbrjake/sahjhan)

### 5. `reset` becomes an authenticated command

Make `sahjhan reset` require caller authentication, same as `sign`/`verify`/`vault`. Unauthenticated callers (including the agent's Bash process) are rejected.

This is defense-in-depth — the Holtz-side allowlist (change 1) is the primary barrier. The daemon-side auth prevents bypass if the hook layer is absent.

### 6. Reliable macOS caller authentication

`POST /sign` on the daemon socket must succeed for callers listed in `trusted-callers.toml` on both Linux and macOS. The current `LOCAL_PEERCRED` mechanism is unreliable on macOS for resolving which script a `python` process is executing.

When auth fails, the error response must include a diagnostic reason instead of generic `auth_failed`. Required reason codes:

- `pid_resolution_failed` — could not resolve caller PID to a script path
- `hash_mismatch` — script resolved but hash doesn't match trusted-callers.toml
- `peer_cred_unavailable` — platform doesn't support LOCAL_PEERCRED or equivalent

The hooks use these codes to distinguish transient from permanent failures and to provide useful diagnostics when reporting to the user.

---

## Defense Layers

After these changes, the `sahjhan reset` attack path is blocked at three levels:

| Layer | Mechanism | Failure mode |
|---|---|---|
| Instruction | SKILL.md hard gate says never run reset | Agent ignores instruction |
| Hook | Bootstrap allowlist blocks the Bash command | Hook not loaded or bypassed |
| Daemon | Auth rejects unauthenticated callers | Agent has no auth path to reset |

The stop hook escape hatch ensures the user can always cleanly exit a stuck audit without destroying the ledger.

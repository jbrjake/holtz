# Issue #43: Stop Hook Kills Daemon in awaiting_clear State

## Problem

The stop hook (`enforcement/hooks/stop_hook.py`) uses a single set `_STOP_ALLOWED_STATES` to control both "can the assistant stop its turn?" and "should we kill the daemon?" The `awaiting_clear` state is in this set, so the daemon gets killed at the end of the turn that transitions to `awaiting_clear` — before the user even has a chance to `/clear`. Since the daemon holds the HMAC session key exclusively in memory, this makes the audit unresumable.

Every audit that reaches `awaiting_clear` via `iteration_boundary` is bricked by this.

## Root Cause

`_STOP_ALLOWED_STATES` on line 34 conflates two concerns:

```python
_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
```

Both the allowed-states path (line 86-88) and the stale-enforcement fallback (line 91-92) call `_try_stop_daemon` without distinguishing whether the daemon should survive.

## Design

### Two state sets

Introduce `_DAEMON_CLEANUP_STATES` that excludes `awaiting_clear`. Add a comment explaining why both sets exist and how to decide which set a new state belongs in.

```python
# Two sets because "allowed to stop" ≠ "safe to kill daemon".
# awaiting_clear allows stop (the turn is done) but the daemon must
# survive — it holds the HMAC session key for the resuming session.
# When adding states, decide: does the audit resume after this? If yes,
# put it in _STOP_ALLOWED only. If the audit is over, put it in both.
_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
_DAEMON_CLEANUP_STATES = {"idle", "finalized", ""}
```

### Call site changes

Two call sites need updating:

1. **Allowed-states path (line 86-88):** Gate `_try_stop_daemon` on `_DAEMON_CLEANUP_STATES`.
2. **Stale-enforcement fallback (line 91-97):** Same gate. A stale `awaiting_clear` audit still has a live daemon that should not be killed by the staleness heuristic — the user may return and `/clear`.

```python
if current_state in _STOP_ALLOWED_STATES:
    if current_state in _DAEMON_CLEANUP_STATES:
        _try_stop_daemon(cwd)
    exit_stop_allow()

if not is_enforcement_fresh(cache):
    if current_state in _DAEMON_CLEANUP_STATES:
        _try_stop_daemon(cwd)
    exit_stop_warn(...)
```

### Files changed

- `enforcement/hooks/stop_hook.py` — add `_DAEMON_CLEANUP_STATES`, guard both call sites
- `tests/test_protocol_enforcement.py` — add test verifying `awaiting_clear` does not trigger daemon cleanup

### Testing

- Existing `test_allows_stop_in_awaiting_clear_state` already verifies stop is allowed (exit code 0). Extend or add a companion test that mocks `_try_stop_daemon` and asserts it is NOT called when state is `awaiting_clear`.
- Add a test for the stale-enforcement path with `awaiting_clear` — should warn but not kill daemon.
- Verify existing tests for `idle`, `finalized`, and active states still pass (daemon cleanup should still happen for those).

### Out of scope

- The `terminated` path (line 68-70) is correct — it always kills the daemon because the audit is already over.
- `protocol_tracker.py` only kills on `finalized`, which is correct.
- No changes to the state machine or transitions.

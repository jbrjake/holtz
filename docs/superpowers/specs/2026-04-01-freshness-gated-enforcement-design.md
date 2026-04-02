# Freshness-Gated Enforcement

**Date:** 2026-04-01
**Issue:** #24 — Stop hook timeout when sahjhan status exceeds 5s
**Scope:** All enforcement hooks in `enforcement/hooks/`

## Problem

Two related failures in the enforcement hook system:

1. **Stop hook timeout (issue #24):** `stop_hook.py` calls `sahjhan status` with a 5-second timeout. When gates include `command_succeeds` checks (e.g., pytest), the status call takes 30+ seconds, times out, and the hook falls through to WARN instead of BLOCK. The agent stops mid-audit.

2. **Stale state poisoning:** When a user force-quits a Holtz audit and starts a new session, the `.sahjhan/` directory persists with non-terminal state. Enforcement hooks fire in the new session, causing:
   - `protocol_tracker` increments stall on every bash command
   - `commit_gate` blocks all bash after stall > 15
   - `primer` injects "SAHJHAN RESUME CONTEXT" into every prompt
   - `stop_hook` blocks session termination
   - The new session becomes unusable or gets hijacked into audit mode

## Design

### Core Signal: `last_sahjhan_cmd`

Add an ISO timestamp field to `enforcement-cache.json` that is updated **only** when `protocol_tracker` detects a sahjhan command (`is_sahjhan_cmd()` returns True).

This field answers: "when was the audit state machine last actively driven?"

- During an active audit: sahjhan commands every 5-15 minutes (fix_commit, transitions, status)
- After session death: no more sahjhan commands; timestamp goes stale

### Shared Function: `is_enforcement_fresh()`

New function in `_protocol_cache.py`:

```python
_ENFORCEMENT_FRESHNESS_MINUTES = 30

def is_enforcement_fresh(cache: dict | None, threshold_minutes: int = _ENFORCEMENT_FRESHNESS_MINUTES) -> bool:
```

Returns True if `last_sahjhan_cmd` is within the threshold. Returns False if the field is missing, unparseable, or stale.

### Per-Hook Behavior

| Hook | Fresh (active audit) | Stale (abandoned) |
|------|---------------------|-------------------|
| **stop_hook** | Read cache state, BLOCK if non-terminal | WARN ("Stale audit found"), allow stop |
| **commit_gate** | Current behavior (block/warn) | Pass through (exit_ok) |
| **protocol_tracker** | Current behavior (track stall) | Exit early (no stall accumulation) |
| **primer** | Current behavior (inject context) | Exit early (no injection) |
| **pre_tool_hook** | Current behavior | Managed-path guard only; skip hook eval |
| **bash_guard** | Current behavior | Exit early |
| **post_tool_hook** | Current behavior | Exit early |

### Stop Hook: No More Subprocess for State

The stop hook currently calls `sahjhan status` via subprocess to get the current state. This is the root cause of issue #24.

New flow:
1. Read `enforcement-cache.json` directly (no subprocess, no timeout)
2. Check `cache["state"]` — if terminal/idle, allow
3. Check `is_enforcement_fresh()` — if stale, WARN and allow
4. Otherwise, BLOCK with current state info
5. Keep the `sahjhan hook eval` subprocess call only for output-pattern-matching (lines 99-122), which doesn't evaluate gates

### Threshold: 30 Minutes

- During active audits, sahjhan commands happen every 5-15 minutes. 30 minutes provides generous headroom.
- After abandonment, most users return after 30+ minutes (hours/days).
- Rapid-switch case (returns within 30 min): enforcement is technically active, but user can Ctrl+C stop hooks, and won't hit stall-based blocking immediately (~15 bash commands of headroom).

### Agent Gaming Analysis

**Attack vector:** Agent avoids sahjhan for 30 minutes using non-bash tools, then stops.

**Assessment:** Theoretical but not practical. The agent would need to deliberately stall for 30 minutes, producing a bizarre transcript. No current AI agent would execute this strategy. The enforcement system prevents accidental/lazy step-skipping, not determined adversarial attacks with unlimited compute budget.

## Files Changed

- `enforcement/hooks/_protocol_cache.py` — add `last_sahjhan_cmd` to `empty_cache()`, add `is_enforcement_fresh()`
- `enforcement/hooks/protocol_tracker.py` — write `last_sahjhan_cmd` in `is_sahjhan_cmd()` branch
- `enforcement/hooks/stop_hook.py` — replace subprocess with cache read + freshness check
- `enforcement/hooks/commit_gate.py` — early-exit on stale enforcement
- `enforcement/hooks/primer.py` — early-exit on stale enforcement
- `enforcement/hooks/pre_tool_hook.py` — skip hook eval on stale; keep managed-path guard
- `enforcement/hooks/post_tool_hook.py` — early-exit on stale enforcement
- `enforcement/hooks/bash_guard.py` — early-exit on stale enforcement
- Tests for all changed hooks

# Holtz: Active Ledger Simplification

**Date:** 2026-04-07
**Status:** Proposed (blocked on sahjhan active-ledger feature)
**Repo:** jbrjake/holtz
**Depends on:** sahjhan active-ledger defaulting (separate spec, jbrjake/sahjhan)

## Problem

Holtz agents consistently write events to the wrong ledger. The SKILL.md requires `--ledger run-N` on every `sahjhan event` and `sahjhan --ledger run-N` command, but after context compaction or `/clear`, agents forget N. The hooks work around this by reading `docs/holtz/.sahjhan/active-run` and injecting `--ledger` into subprocess calls, but the agent's own CLI commands (constructed from SKILL.md templates) have no such safety net.

Once sahjhan supports active-ledger defaulting (reading a marker file as fallback when `--ledger` is omitted), holtz can simplify its entire agent-facing interface.

## Prerequisites

Sahjhan must support:
- `sahjhan ledger create --activate` (creates ledger + writes active-ledger marker)
- `sahjhan ledger activate <name>` / `sahjhan ledger deactivate`
- Automatic ledger resolution from `{data_dir}/active-ledger` when `--ledger` is omitted

## Changes

### 1. SKILL.md Command Reference

**Before:**
```bash
sahjhan --ledger run-N event finding --field project=holtz --field run=N \
  --field auditor=holtz --field phase=audit ...
sahjhan --ledger run-N event finding_resolved --field project=holtz --field run=N ...
sahjhan --ledger run-N event recon_finding --field project=holtz --field run=N ...
sahjhan --ledger run-N event audit_claim --field project=holtz --field run=N ...
sahjhan --ledger run-N status
sahjhan --ledger run-N ledger checkpoint --name pre-clear
```

**After:**
```bash
sahjhan event finding --field project=holtz --field run=N \
  --field auditor=holtz --field phase=audit ...
sahjhan event finding_resolved --field project=holtz --field run=N ...
sahjhan event recon_finding --field project=holtz --field run=N ...
sahjhan event audit_claim --field project=holtz --field run=N ...
sahjhan status
sahjhan ledger checkpoint --name pre-clear
```

The `--field run=N` stays because it's event metadata (used in rendered output and queries), not ledger targeting. The agent still needs the run number for field values, but forgetting it there is a data quality issue, not a "events land in the wrong place" issue.

**Commands that keep explicit `--ledger`:**
```bash
sahjhan --ledger project ledger checkpoint  # cross-ledger: project ledger
```

Project-ledger commands are rare (only at convergence/finalize) and intentionally explicit.

### 2. Run Initialization (phase-recon.md)

**Before (4 commands):**
```bash
nohup sahjhan daemon start > /dev/null 2>&1 &
sleep 1
cp docs/holtz/.sahjhan/daemon.pid docs/holtz/.sahjhan/daemon-init-pid
sahjhan ledger create --from run N
sahjhan transition run_start
```

**After (4 commands, but `--activate` added):**
```bash
nohup sahjhan daemon start > /dev/null 2>&1 &
sleep 1
cp docs/holtz/.sahjhan/daemon.pid docs/holtz/.sahjhan/daemon-init-pid
sahjhan ledger create --from run N --activate
sahjhan transition run_start
```

The only change is `--activate` on `ledger create`. This writes the active-ledger marker atomically with ledger creation. All subsequent commands in the run resolve to `run-N` automatically.

### 3. Hook Simplification

**Current state:** Every hook has this pattern:
```python
ledger = _active_ledger(cwd)
cmd = [binary, "--config-dir", config_dir]
if ledger:
    cmd.extend(["--ledger", ledger])
```

This appears in: `primer.py`, `pre_tool_hook.py`, `post_tool_hook.py`, `bash_guard.py`, `protocol_tracker.py`, `lens_quiz.py`, `_daemon_lifecycle.py`.

**Migration strategy — two phases:**

#### Phase 1: Compatibility (ship with sahjhan active-ledger)

Keep `_active_ledger()` and the `--ledger` injection in hooks. This ensures hooks work with both old and new sahjhan versions. The agent-facing SKILL.md commands are simplified immediately because sahjhan handles the resolution.

No hook code changes needed in Phase 1. The value is entirely in the SKILL.md simplification.

#### Phase 2: Cleanup (after minimum sahjhan version bump)

Once holtz requires a sahjhan version with active-ledger support:
- Remove `_active_ledger()` from `_common.py`
- Remove `write_active_run_marker()` from `_common.py`
- Remove all `if ledger: cmd.extend(["--ledger", ledger])` patterns from hooks
- Remove `_ensure_active_run_marker()` from `_daemon_lifecycle.py`
- Hooks just call `[binary, "--config-dir", config_dir, "event", ...]` — sahjhan resolves the ledger

This removes ~60 lines of boilerplate across 7 hook files.

Phase 2 is optional and can be deferred indefinitely. The hooks work correctly either way — they're just redundantly specifying what sahjhan would resolve on its own.

### 4. Holtz Active-Run Marker Migration

Holtz currently writes to `docs/holtz/.sahjhan/active-run`. Sahjhan will use `{data_dir}/active-ledger`. These are different files.

**Migration:** Update `_daemon_lifecycle.py`'s `_ensure_active_run_marker()` and the `ledger create` step in phase-recon.md to use `sahjhan ledger activate` (or `--activate` flag) instead of writing `active-run` directly. The holtz-side `active-run` file becomes redundant once sahjhan manages its own `active-ledger` marker.

**Transition:** During Phase 1, both files may coexist. Hooks continue reading `active-run` (holtz-side) while sahjhan reads `active-ledger` (sahjhan-side). This is fine — they'll contain the same value. In Phase 2, holtz stops writing `active-run` and relies entirely on sahjhan's marker.

### 5. Primer Context Update

The primer currently outputs:
```
Active ledger: run-31 (use: sahjhan --ledger run-31)
```

After this change, simplify to:
```
Active ledger: run-31
```

The "(use: sahjhan --ledger run-31)" hint is no longer needed since the agent doesn't need to specify the flag.

### 6. Test Updates

- Tests that mock `_active_ledger()` return values: keep in Phase 1, remove in Phase 2
- Tests that write `active-run` marker files: keep in Phase 1, migrate to `active-ledger` in Phase 2
- New test: verify that `sahjhan ledger create --activate` is used in run initialization
- New test: verify SKILL.md command examples don't contain `--ledger run-` (except in the project-ledger section)

## Files Changed

### Phase 1 (SKILL.md simplification)

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Remove `--ledger run-N` from all event/status/checkpoint command examples |
| `skills/holtz/references/phase-recon.md` | Add `--activate` to `ledger create`, remove "must use --ledger run-N" warning |
| `skills/holtz/references/phase-convergence.md` | Remove `--ledger run-N` from checkpoint command |
| `enforcement/hooks/primer.py` | Remove "(use: ...)" hint from active ledger context line |

### Phase 2 (Hook cleanup, optional)

| File | Change |
|------|--------|
| `enforcement/hooks/_common.py` | Remove `_active_ledger()`, `write_active_run_marker()` |
| `enforcement/hooks/_daemon_lifecycle.py` | Remove `_ensure_active_run_marker()`, `_find_highest_run()` |
| `enforcement/hooks/primer.py` | Remove ledger resolution, simplify sahjhan calls |
| `enforcement/hooks/pre_tool_hook.py` | Remove ledger resolution |
| `enforcement/hooks/post_tool_hook.py` | Remove ledger resolution, simplify `_record_event()` |
| `enforcement/hooks/bash_guard.py` | Remove ledger resolution |
| `enforcement/hooks/protocol_tracker.py` | Remove ledger resolution |
| `enforcement/hooks/lens_quiz.py` | Remove ledger parameter threading |
| Tests | Migrate `active-run` references to `active-ledger` |

## Risk

**Low.** Phase 1 is purely documentation changes plus one flag addition (`--activate`). No runtime behavior changes. The hooks continue to work exactly as before. The only risk is an agent running an old sahjhan version without active-ledger support — but `--activate` on an old sahjhan would fail loudly at run initialization, which is the right time to fail.

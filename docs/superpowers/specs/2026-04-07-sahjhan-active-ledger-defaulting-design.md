# Sahjhan: Active Ledger Defaulting

**Date:** 2026-04-07
**Status:** Proposed
**Repo:** jbrjake/sahjhan
**Depends on:** Nothing (standalone sahjhan feature)
**Depended on by:** holtz active-ledger simplification (separate spec)

## Problem

Agents using sahjhan's multi-ledger support must pass `--ledger run-N` on every CLI invocation. After context compaction, `/clear`, or many turns, agents forget the run number and either:

1. **Omit `--ledger`** — events land in the default ledger, not the run ledger. Renders break, gate checks fail, findings are orphaned.
2. **Guess the wrong N** — events land in a stale or nonexistent ledger.

The hooks (holtz-side) already solve this by reading a marker file (`{data_dir}/active-run`) and injecting `--ledger` into every subprocess call. But agents constructing CLI commands from skill templates have no such safety net — they rely on remembering a string across hundreds of turns.

## Solution

Add an **active-ledger marker** to sahjhan's data directory. When `--ledger` is not specified, sahjhan reads this marker and uses the named ledger if it exists and is registered. This moves ledger resolution from "agent must remember" to "sahjhan resolves automatically."

## Ledger Resolution Order

When a command needs a target ledger:

1. **`--ledger <name>` flag** — explicit, highest priority. Used for cross-ledger queries (e.g., `--ledger project`).
2. **`--ledger-path <path>` flag** — explicit path, same priority as above.
3. **`{data_dir}/active-ledger` file** — implicit default. File contains a single line: a ledger name registered in `ledgers.toml`.
4. **The `default` ledger in `ledgers.toml`** — fallback when no marker exists.

Steps 1-2 are existing behavior. Step 3 is new. Step 4 is existing behavior.

## Marker File

**Path:** `{data_dir}/active-ledger`
**Format:** Single line, newline-terminated, containing a ledger name (e.g., `run-31\n`).
**Lifecycle:**
- Created by `sahjhan ledger activate <name>` or `sahjhan ledger create --activate`.
- Removed by `sahjhan ledger deactivate` or `sahjhan reset`.
- NOT removed by `sahjhan ledger remove <name>` (the marker may still be valid if the ledger is re-created).

**Validation on read:** If the marker names a ledger not in `ledgers.toml`, sahjhan should:
- Emit a warning to stderr: `warning: active-ledger marker points to unregistered ledger '{name}', falling back to default`
- Fall back to the default ledger (step 4)
- NOT silently use the unregistered name

## New Subcommands

### `sahjhan ledger activate <name>`

Write `{data_dir}/active-ledger` with the given ledger name.

**Preconditions:**
- `<name>` must be registered in `ledgers.toml`. Error if not.
- `{data_dir}` must exist. Error if not.

**Output (text):** `Activated ledger: <name>`
**Output (--json):** `{"activated": "<name>"}`

### `sahjhan ledger deactivate`

Remove `{data_dir}/active-ledger` if it exists. No-op (success) if it doesn't.

**Output (text):** `Deactivated active ledger` or `No active ledger to deactivate`
**Output (--json):** `{"deactivated": true}` or `{"deactivated": false}`

### `sahjhan ledger create --activate`

New flag on the existing `ledger create` command. After successfully creating and registering the ledger, write the active-ledger marker. Equivalent to `ledger create` + `ledger activate` atomically.

This is the primary intended usage — agents call one command at run start and never think about ledger targeting again.

## Status Output

`sahjhan status` should include the resolved ledger and how it was resolved:

```
Ledger: run-31 (active-ledger marker)
```

or:

```
Ledger: default (no active-ledger marker)
```

or when `--ledger` is explicit:

```
Ledger: project (explicit --ledger flag)
```

This helps agents (and humans debugging) understand which ledger they're operating on without having to check the marker file manually.

## Commands Affected

Every command that currently requires `--ledger` to target a non-default ledger benefits from this fallback. The full list:

- `sahjhan status`
- `sahjhan event <type>`
- `sahjhan authed-event <type>`
- `sahjhan transition <name>`
- `sahjhan gate check <name>`
- `sahjhan set complete <set> <value>`
- `sahjhan set status <set>`
- `sahjhan render`
- `sahjhan query <sql>`
- `sahjhan log <subcommand>`
- `sahjhan ledger checkpoint`
- `sahjhan ledger verify`

Commands that don't use a ledger target (e.g., `daemon start`, `validate`, `mermaid`) are unaffected.

## Edge Cases

### Stale marker from crashed prior run

If an agent crashes mid-run, the marker persists. On the next `ledger create --activate`, the marker is overwritten — no issue. If the agent resumes without creating a new ledger, the marker correctly points to the prior run's ledger, which is the right thing for resume.

### `sahjhan reset`

`reset` archives the current run. It should remove the active-ledger marker as part of cleanup, since the archived run is no longer active.

### Multiple concurrent agents

Two agents targeting different ledgers in the same data directory would conflict on the marker file. This is not a supported use case — sahjhan is single-agent-per-data-dir. If needed later, per-process env var override (`SAHJHAN_ACTIVE_LEDGER`) could supplement the file-based marker, but that's out of scope here.

### `ledger remove` for the active ledger

If an agent runs `sahjhan ledger remove <name>` where `<name>` is the active ledger, the marker becomes stale. On next command, sahjhan hits the "unregistered ledger" validation, warns, and falls back to default. This is acceptable — `ledger remove` is a rare administrative action, not part of normal agent flow.

## Testing

- `ledger activate` with valid name: marker written, subsequent commands target that ledger
- `ledger activate` with unregistered name: error
- `ledger deactivate`: marker removed, commands fall back to default
- `ledger create --activate`: ledger created AND marker written
- Resolution priority: explicit `--ledger` beats marker beats default
- Stale marker (points to removed ledger): warning + fallback to default
- `reset`: marker removed
- `status` output: shows resolved ledger source

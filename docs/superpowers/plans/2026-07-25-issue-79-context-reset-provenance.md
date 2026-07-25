# Issue #79 — `awaiting_clear` gate satisfied without a real `/clear`

**Status:** in progress
**Issue:** [jbrjake/holtz#79](https://github.com/jbrjake/holtz/issues/79) (bug, P1)
**Reported against:** plugin 0.138.2

## The bug in one line

`context_reset` is recorded iff *a prompt was submitted*. It is documented,
gated, and reasoned about as if it were recorded iff *the context was actually
reset*.

## Root cause

`enforcement/hooks/primer.py` runs on `UserPromptSubmit` and records
`context_reset` unconditionally on that path. `UserPromptSubmit` fires for:

- any typed message that is not a `/clear`, and
- automated background-task notifications delivered as a user turn
  (this is what tripped the reporter on a live run).

So the first `UserPromptSubmit` after `fix_loop_start` opens the
`awaiting_clear -> fix_loop` (`resume`) gate regardless of whether a reset
happened. The `"after /clear"` in the `events.toml` description is an
assumption the code never checked.

The failure is silent and *looks like success*: `status` prints
`resume: ready`, so nothing signals that the loop is about to start carrying
the full recon+audit+merge context — the exact state the boundary exists to
prevent.

## The signal that actually means "context was reset"

Claude Code's `SessionStart` hook (spec: https://code.claude.com/docs/en/hooks,
verified 2026-07-25) fires only when the host starts or restarts a session, and
carries a `source` field:

| `source`  | Fires on                                                        | Prior context |
|-----------|-----------------------------------------------------------------|---------------|
| `startup` | new session                                                     | **gone**      |
| `clear`   | `/clear`                                                        | **gone**      |
| `compact` | auto or manual compaction                                       | **replaced by a summary** |
| `resume`  | `--resume`, `--continue`, `/resume`                             | restored      |
| `fork`    | `--fork-session`, `/fork` background copy, `/branch`            | carried over  |

Two properties make this the right source of truth:

1. It is **host-driven**. An agent cannot start, clear, compact, or fork its
   own session — no tool call produces a `SessionStart`. Contrast
   `UserPromptSubmit`, which a background subagent's completion notification
   produces with no human involved.
2. It is **self-describing**. `source` distinguishes a real wipe from a
   restore, so the recorded event can carry its own provenance and the gate
   can require it.

`startup` is included deliberately. Excluding it would trade #79 (a gate
satisfied when it shouldn't be) for #73's failure mode (a gate that cannot be
satisfied): a user who quits and relaunches Claude Code at `awaiting_clear` has
a genuinely empty context but no way to prove it. `resume` and `fork` are
excluded because both carry the prior transcript forward.

## Design

**Invariant to restore:** `context_reset` is recorded **iff** the context was
actually reset.

1. **New hook `enforcement/hooks/session_start.py`** (`SessionStart`).
   Records `context_reset` when `source ∈ {clear, compact, startup}` and an
   active non-terminal run exists. Silent on success (token discipline — the
   primer's banner already reports position on the next turn); speaks only on
   failure.
2. **`primer.py` stops recording.** Resume-context injection stays on
   `UserPromptSubmit` (harmless to re-inject, and it is where the agent needs
   it).
3. **`events.toml` encodes the provenance.** `trigger` pattern narrows from
   `^user_prompt_submit$` to `^session_start$`; a new required `source` field
   is patterned `^(clear|compact|startup)$`. The engine validates event fields
   against the consumer's `events.toml` on the daemon `record_event` path, so
   a `context_reset` claiming a bogus provenance is refused at write time.
4. **`transitions.toml` requires the provenance.** The `resume` gate gains
   `filter = { trigger = "session_start" }`. Block condition and evidence are
   now the same fact — an event recorded on any other path cannot satisfy it,
   including the `user_prompt_submit` events already sitting in live ledgers.

### Preserving the primer's failure signals

Today the primer detects two failures *as a side effect* of the record attempt:

- daemon death (record raises → init PID dead → write `terminated` marker), and
- broken caller auth (record raises → PID alive → `ENFORCEMENT FAILURE` banner).

Removing the write would silently drop both. They are replaced with direct,
non-mutating probes that run on every `UserPromptSubmit`:

- **Death:** read the init PID and signal-0 it. This is strictly better than
  before — it no longer depends on a write happening to fail.
- **Auth:** an `enforcement_read` request over the daemon socket. A reachable
  daemon that rejects the peer answers `caller not authenticated`, which is
  exactly the trusted-callers failure mode that
  [[trusted-callers-manifest-regen]] describes; socket-unreachable and
  no-state-stored are distinguished from it and stay quiet.

The same two banners are emitted from `session_start.py`, where the write now
lives.

## Why no sahjhan change

Checked, and none is needed — every primitive this fix relies on already ships
in 0.19.0:

- `restricted = true` events + the daemon `record_event` op (`>= 0.15.0`)
- per-field pattern validation on `record_event`
  (`handle_record_event` → `validate_event_fields`)
- `ledger_has_event_since` with a payload `filter`
  (`src/gates/ledger.rs`, `entry_matches_filter`)

Everything #79 needs is holtz **domain** config plus a holtz hook. Teaching
sahjhan about `SessionStart` / `source` would push Claude Code host-lifecycle
semantics into a generic state-machine engine — the pollution the project
explicitly forbids. The engine's job here is to validate a declared event
schema and evaluate a declared filter; it already does both.

## Risk considered: what if `SessionStart` never fires?

Making the gate honest also makes it a hard dependency: if a host never fires
`SessionStart` for plugin hooks, `awaiting_clear` deadlocks permanently — #73's
failure mode. No escape hatch was added, because any escape hatch is a route
around the boundary and defeats the fix.

Accepted because the dependency is narrower than ones the plugin already has.
`SessionStart` with `source` is long-standing and documented as supported in
plugin `hooks/hooks.json`; the schema this repo already validates against uses
much newer surface (the `defer` permission decision, the `fork` source). A host
new enough to run the existing enforcement chain fires `SessionStart`.

## Files

| File | Change |
|------|--------|
| `enforcement/hooks/session_start.py` | **new** — records `context_reset` on a real reset |
| `enforcement/hooks/primer.py` | drop the write; direct death + auth probes |
| `hooks/hooks.json` | register the `SessionStart` hook |
| `enforcement/hooks-manifest.json` | require it |
| `enforcement/events.toml` | `trigger` → `^session_start$`; add `source` |
| `enforcement/transitions.toml` | `resume` gate filter; correct the comment |
| `scripts/hash-trusted-callers.sh` | add `session_start.py` |
| `enforcement/trusted-callers.toml` | regenerate |
| `skills/holtz/references/phase-fix-loop.md` | correct the HARD-GATE claim |
| `tests/test_session_start.py` | **new** — `hook_e2e` provenance coverage |
| `tests/test_primer.py`, `tests/test_sahjhan_integration.py` | move reset coverage |

## Test plan

Per CLAUDE.md testing methodology — hooks are tested by **subprocess**, which is
the interface Claude Code actually uses.

1. `hook_e2e`: `session_start.py` records `context_reset` for `clear`,
   `compact`, `startup`; records **nothing** for `resume`, `fork`, an absent
   `source`, and an unknown source.
2. `hook_e2e`: recorded fields carry `trigger=session_start` and the real
   `source`.
3. `hook_e2e`: `primer.py` records **no** `context_reset` for any
   `UserPromptSubmit` — the #79 regression guard.
4. `hook_e2e`: primer still writes the `terminated` marker on a dead init PID,
   and still surfaces `ENFORCEMENT FAILURE` on a reachable-but-rejecting daemon.
5. Config: the `resume` gate filters on `trigger`, and `events.toml` cannot
   express `user_prompt_submit`.
6. No-audit / terminated-audit paths stay silent and never bootstrap the binary.

## Verification (observed evidence required — no future-tense claims)

- [ ] `pytest -m hook_e2e` exit 0
- [ ] full `pytest` with coverage gate exit 0
- [ ] `ruff check .` exit 0
- [ ] `mypy` exit 0
- [ ] `python3 scripts/contract_gate.py` exit 0
- [ ] `scripts/pre-release-check.sh` exit 0
- [ ] CI green on dev (`gh run view <id>` → `conclusion=success`)
- [ ] release PR CI green before merge

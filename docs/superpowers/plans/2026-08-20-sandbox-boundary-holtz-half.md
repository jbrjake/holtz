# Plan: the holtz half of the sandbox boundary (sahjhan 0.21.0)

Date: 2026-08-20
Engine side: `sahjhan` v0.21.0 (`bc471a1`, `3fbb58e`, `a5f664d`, `28b2720`)
Design record: `../../../../sahjhan/PROPOSAL.solution.md`

## The one-sentence design

The daemon provably cannot authenticate a same-user socket peer, so caller
identity is not the boundary — the **Claude Code Bash sandbox** is: the agent's
commands run inside it with unix sockets denied, hooks run outside it, and the
daemon refuses to serve unless it can confirm that boundary is configured.

## What sahjhan 0.21.0 already gives us

| Piece | Where | What holtz must do about it |
|---|---|---|
| `SAHJHAN_DAEMON_SOCKET` honored by the Rust daemon (C1) | `daemon::socket_path_for` | Bind the socket **outside** the project root and derive the same path in every hook |
| Sandbox fuse (D1) | `daemon/fuse.rs` | Arm it with `[daemon] require_sandbox = true`; write settings that satisfy every check |
| Direct-peer auth (D3) | `daemon/auth.rs` | Callers must canonicalize **under `--config-dir`**; drop the manifest entry that can no longer authenticate |
| Bounded per-connection I/O | `daemon/mod.rs` | Nothing |

The fuse refuses with `error: sandbox_required` plus a machine-readable
`reason` (`sandbox_not_enabled`, `unsandboxed_commands_allowed`,
`sandbox_fail_open`, `socket_allowlisted`, `excluded_commands_present`,
`socket_inside_project`, `settings_unreadable`). Consumers fail closed on it.

## What the sandbox breaks in holtz, exhaustively

Everything the **agent's Bash** runs is confined; every **hook** Claude Code
fires is not. So any privileged path that starts in agent Bash is severed:

1. **`nohup sahjhan … daemon start`** (`phase-recon.md` Step 0) — a confined
   process cannot bind a socket outside the workspace. → moves to `holtz-start`.
2. **`verify_suite.py --record`** (`phase-fix-loop.md` step 9) — opens the
   socket to write the restricted `suite_green` event. Without a new channel
   `fix_commit` never opens and the fix loop deadlocks. → PostToolUse courier.
   *(`PROPOSAL.solution.md`'s C2 audit missed this: it enumerated `sahjhan`
   subcommands, and this is a holtz helper, not a subcommand.)*
3. **`! sahjhan daemon stop`** — `daemon stop` opens the socket, and a `!` bang
   line is sandboxed exactly like tool-Bash (validated 2026-08-20). → replaced
   by `holtz-stop`.
4. **`! sahjhan event quiz_exhausted_resolved`** — *not* affected. The event is
   unrestricted, so the CLI writes the ledger file, which lives inside the
   workspace and stays writable. Verified in `enforcement/events.toml`.
5. **`hooks/subagent_findings_check.py`** in `trusted-callers.toml` — sits at
   the plugin root, not under `--config-dir`, so under D3 it can never
   authenticate. It also never opens the socket. → removed from the manifest.

Unaffected (file-only, inside the workspace): `init`, `ledger`, `transition`,
`event`, `set`, `status`, `render`, `log`, `query`, `gate check`, `hook eval`,
`verify_suite.py --check`, `git`, the test suite, the linters.

## Corrections to the proposal, found while verifying

- **`CLAUDE_CODE_SANDBOXED` is not the guardrail probe.** The proposal says it
  "is set inside sandboxed commands and empty otherwise". In the installed
  2.1.237 binary it appears only as an **input** the launcher *reads* (trust-
  dialog bypass when Claude Code itself runs containerized); there is no site
  that sets it in a sandboxed command's environment. The guardrail therefore
  probes the fact itself — can this shell reach the daemon socket — instead of
  a proxy for it.
- **Sandbox settings nesting**, confirmed against the same binary:
  `sandbox.filesystem.{allowWrite,denyWrite,denyRead}` and
  `sandbox.network.{allowUnixSockets,allowAllUnixSockets}` — not
  `sandbox.denyWrite`. The scope filter keeps `enabled:true`,
  `failIfUnavailable:true`, `allowUnsandboxedCommands:false`, and the deny
  lists from a low-trust scope, and drops `allowWrite` — i.e. any scope may
  strengthen. Everything holtz writes is in the strengthening direction.

## The changes

### 1. Pin sahjhan 0.21.0
`enforcement/hooks/_resolve.py`: `SAHJHAN_VERSION` + four checksums (taken from
the release's own `checksums.sha256`, re-verified against the vendored bytes).

### 2. Relocate the socket (C1 consumer side)
One named derivation, `_common.py::_get_daemon_socket_path(cwd)`:

```
$SAHJHAN_DAEMON_SOCKET  (tests / explicit override)
  else  ~/.holtz/run/<sha256(realpath(project_root))[:12]>/daemon.sock
```

Short enough for the macOS 104-byte `AF_UNIX` limit; outside the project root
(the fuse refuses an in-project socket); one expression, so the arming hook and
every consumer hook cannot drift apart. The PID file stays in `data_dir` —
`_daemon_lifecycle.py` watches it there and it guards nothing.

### 3. `holtz-start` / `holtz-stop` (C2)
New `UserPromptSubmit` hook `enforcement/hooks/sandbox_control.py`, firing on an
**exact match** of the whole prompt. Hooks run outside the sandbox, so the hook
can write the sandbox-protected settings file in either direction; the human
types the word and the agent — which cannot submit prompts — never touches
sandbox settings.

`holtz-start`, in order:
1. `sahjhan init` (data dir + manifest + config seal)
2. start the daemon with `SAHJHAN_DAEMON_SOCKET` at the relocated path
3. copy `daemon.pid` → `daemon-init-pid`
4. back up the existing `sandbox` block to `<run dir>/settings-backup.json`
5. write the boundary into `.claude/settings.local.json`
6. **verify** — send a privileged op and report the fuse's own verdict

`holtz-stop`, in the reverse-safe order: stop the daemon **first** (so a live
daemon is never reachable from an unconfined shell), drop `daemon-init-pid` so
the audit is not reported as having crashed, then restore the settings backup.

Both answer with `{"decision": "block", "reason": …}` — the word never reaches
the model and no turn is spent on it.

The settings written:

```json
{"sandbox": {"enabled": true,
             "allowUnsandboxedCommands": false,
             "failIfUnavailable": true,
             "filesystem": {"denyWrite": ["<plugin root>", "<holtz run dir>"]}}}
```

`denyWrite` on the plugin tree is what stops a confined agent planting a
`sitecustomize.py` or a sibling `json.py` that a genuine hook would later
import; `denyWrite` on the run dir stops it squatting the socket path.

### 4. The consumer fails closed (D2)
`read_cache` swallows every daemon error and returns `None`, and every gate
then reads `is_enforcement_fresh(None) == False` and **allows**. So a tripped
fuse currently deletes enforcement instead of enforcing it.

Name the fact once — `_protocol_cache.read_cache_with_boundary(cwd)` returns
`(cache, refusal_reason)` — and block on it in `pre_tool_hook` (Write/Edit),
`commit_gate` (Bash) and `_common.exit_enforcement_error`; warn in the
PostToolUse hooks; surface it in `primer`. No new round trips: those call sites
already read the cache. The condition is self-limiting — only a **live** daemon
can refuse, so this can only fire during a real audit.

### 5. `suite_green` through a courier
`verify_suite.py --record` stops touching the socket: it runs the suite, prints
a `SUITE-GREEN:` marker on green, and exits 0/non-zero. A new PostToolUse hook
`enforcement/hooks/suite_courier.py` records the event, and every field a gate
reads is derived outside the agent's reach:

| field | source | forgeable? |
|---|---|---|
| `tree_hash` | courier runs `git` itself | no |
| `commit_hash` | courier runs `git rev-parse HEAD` | no |
| `scope` | the `--scope` flag in the command text the host reports | no |
| `project`, `run`, `auditor` | courier derives from the tree/ledger | no |
| `command`, `test_count` | the marker | yes — informational, no gate reads them |

Two independent signals must agree before anything is recorded: the host fired
PostToolUse with exit 0 (2.x does not fire it at all on a non-zero Bash exit),
**and** the script printed the marker it only prints on green. Requiring both
means neither assumption is load-bearing alone. The command must be a single
segment matching the prescribed invocation, so no `echo`-forged marker and no
work chained around it.

A widened run (`--scope affected` that could not prove a subset and ran
everything) is recorded as `affected` — the conservative claim the command
made. `full` greens still come from an explicit `--scope full`, which is what
`phase-fix-loop.md` already prescribes.

### 6. The guardrail
`skills/holtz/scripts/boundary_check.py` — attempts to `connect()` the daemon
socket and reports `confined` / `exposed` / `no-daemon`. `phase-recon.md`
Step 0 runs it first and stops with the one-word fix if the boundary is absent.
This is UX for an honest operator; the security is D1 + D2, which refuse
regardless of whether the prompt is read.

### 7. Arm the fuse
`enforcement/protocol.toml` gains `[daemon] require_sandbox = true`. Last,
because everything above has to work first.

## Sequencing (one reviewed commit each) — shipped

| | Commit | Version |
|---|---|---|
| 1 | `feat(deps): pin sahjhan 0.21.0` | 0.142.0 |
| 2 | `feat(enforcement): holtz-start and holtz-stop raise the audit boundary` (C1 + C2 + guardrail + phase-recon) | 0.143.0 |
| 3 | `fix(enforcement): fail closed when the daemon reports the boundary is gone` (D2) | 0.143.1 |
| 4 | `feat(enforcement): record suite_green through a courier hook` | 0.144.0 |
| 5 | `feat(enforcement): arm the sandbox fuse` (+ finalize teardown, README) | 0.145.0 |

The socket relocation merged into commit 2 rather than standing alone: on its
own it would have left a window where the skill file still told the agent to
bind the socket where no hook would look for it.

## What running it corrected, that reading did not

- **`sahjhan init` is not idempotent** — it exits with a usage error when the
  ledger it would create exists. `phase-recon.md` had claimed the opposite for
  as long as it had said it. `holtz-start` now asks the same question sahjhan
  asks, of the same artifact, before calling it.
- **Re-arming would have captured our own settings block as "theirs"**, after
  which `holtz-stop` would have faithfully restored the sandbox instead of
  removing it. The backup is written once and consumed by the restore.
- **`daemon stop` needs no socket** — it SIGTERMs the PID from the PID file, so
  `holtz-stop` still works with the CLI unable to authenticate under D3.
- **`hooks.json` must invoke hooks by absolute path.** A relative path in a
  peer's cmdline resolves against the *daemon's* cwd, so auth fails with
  `pid_resolution_failed`. Found by a smoke run that used a relative path.
- **The `suite_green` scope needed a third answer.** Taking the run's word for
  it puts an agent-authored value where a gate reads; taking only the command's
  word throws away a full green whenever `affected` could not narrow. The
  courier re-derives the widening decision itself.
- **A pre-existing order-dependent test** (`TestStallPenalty`) only exercised
  the branch it is named after when no earlier file had imported
  `_protocol_cache`. Surfaced by the new tests changing collection order.

## Known limits, stated not buried

- **Linux needs the optional seccomp filter.** Without
  `@anthropic-ai/sandbox-runtime`, unix sockets are not blocked at all and
  relocating the socket does not substitute. The fuse cannot verify it.
- **Nothing inside the plugin can guarantee the sandbox is on** — arming is a
  human typing `holtz-start`. D1 + D2 are what make the un-armed case fail
  closed rather than silently unprotected.
- **`holtz-stop` ends the audit.** It stops the daemon, which destroys the
  session key. To pause and resume, use `transition pause` / `resume`, which
  keep the daemon alive.
- **Quiz-bank poisoning is untouched** by this and needs its own fix.
- **Arming changes `protocol.toml`,** so in-flight ledgers sealed against the
  old config will report a config integrity violation and need a fresh run.

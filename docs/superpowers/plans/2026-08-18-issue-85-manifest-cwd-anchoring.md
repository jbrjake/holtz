# Issue #85 — manifest paths resolve against CWD, not the project root

**Reported:** 2026-08-18 by @jbrjake, against holtz `0.141.3` / sahjhan `0.20.0`,
external target `tqdm`, run-1 (8,356 events, chain valid).

**Root cause: sahjhan.** Fix lands in the engine (v0.20.1, `89e7ce5`) plus a holtz-side
change to the violation stream. Authorized by
`fix-root-cause-dont-route-around` — the bug is in sahjhan, so it gets fixed in
sahjhan.

---

## What actually happens

`resolve_data_dir_from` (sahjhan `src/cli/commands.rs`) already walks **up**
from the current directory to the nearest ancestor holding the relative
`data_dir` — that was the holtz #70 item 4 fix, and it means the *ledger* is
found correctly no matter where the shell has drifted to.

The manifest **key** is computed by a different, unrelated derivation. Five
sites do the same thing by hand:

| site | expression |
|---|---|
| `cli/commands.rs::track_ledger_in_manifest` | `pathdiff(&lp, &cwd)` |
| `cli/init.rs` | `pathdiff(&lp, &cwd)` |
| `render/engine.rs::render_all` | `target_path.strip_prefix(current_dir())` |
| `render/engine.rs::render_triggered` | `target_path.strip_prefix(current_dir())` |
| `cli/manifest_cmd.rs::cmd_manifest_verify` | `verify(&manifest, &cwd)` |

So the walk-up *discovers* the project root and then discards it, and the key
derivation re-derives an anchor from CWD and gets a different one. With
CWD = `<root>/docs/holtz`:

- `render_dir` resolves (correctly, via walk-up) to `<root>/docs/holtz`
- the file is written to the right place — nothing is written at the repo root
- the key is `strip_prefix("<root>/docs/holtz")` → **`STATUS.md`**, not
  `docs/holtz/STATUS.md`

The manifest gains a second entry for a file it already tracks, spelled
relative to a directory that is not the project root. `manifest verify` runs
from the session root (bash_guard passes `cwd=event["cwd"]`, which Claude Code
reports as the session directory, not the drifted shell CWD), resolves
`STATUS.md` against `<root>/`, finds nothing, and reports it missing — forever.

This is why the reporter's three phantom hashes are *stale hashes of the real
files*: same file, wrong key, recorded at an earlier render.

**Second manifestation, same defect class.** `StateMachine::new` sets the
`command_succeeds` gate working directory to `current_dir()`, so a drifted CWD
moves every gate that shells out. The four suite gates happen to be safe —
they reach `verify_suite.py` through `$CLAUDE_PLUGIN_ROOT` — but two gates are
genuinely cwd-relative:

- `transitions.toml:312,351` — `${HOLTZ_LINT:-ruff check .}`. Run from
  `docs/holtz` this lints `docs/holtz` and **passes green having checked
  nothing**. That is #83's failure mode reached through a second door: not
  "wrong language" but "right language, wrong directory." Worth noting on #83,
  since it means the default lint gate has two ways to be falsely affirmative
  and only one of them is about polyglot targets.
- `transitions.toml:145` — `test -f docs/holtz/investigations/{{item_id}}.md`,
  which from inside `docs/holtz` resolves to `docs/holtz/docs/holtz/…` and
  fails a gate that should pass.

Fixed in the same change — same anchor, same helper.

---

## The rule this establishes

> **Paths the system owns are resolved against the project root. Paths a user
> types on the command line stay relative to the current directory.**

System-owned: `data_dir`, `render_dir`, manifest keys, manifest verify base,
gate command working directory. User-typed: `--config-dir`, `ledger create
--path`, `ledger import <path>`. Those keep ordinary UNIX semantics and are
deliberately left alone.

The project root is not a new concept to discover — it is the ancestor the
walk-up already finds. Making it a named function and **defining
`resolve_data_dir_from` in terms of it** is what stops the two from drifting
again ([[enforcement-name-the-fact-not-the-text]] applied one layer down, to
the filesystem instead of the ledger).

---

## Changes

### sahjhan v0.20.1

1. **`src/paths.rs` (new).** `project_root_from(data_dir, cwd)` — the ancestor
   that holds the relative `data_dir`; `cwd` when absolute or not found.
   `data_dir_from` is now `project_root_from(..).join(data_dir)`, so the two
   derivations are one expression. Plus `manifest_key(abs, root)` and
   `path_is_under(path, managed)`.

2. **`path_is_under` is component-wise.** The pre-existing E12 check used raw
   string `starts_with`, so `docs/holtz-old/x` counted as under `docs/holtz`.
   Latent, fixed on the way past. `..` components are refused outright.

3. **`Manifest::track` refuses an out-of-managed-path key (E13).** The
   manifest's own `managed_paths` is the invariant; a bare `STATUS.md` at the
   repo root is under neither `docs/holtz` nor `enforcement/` and must never be
   admitted. Empty `managed_paths` = unconstrained (backward compatible;
   `examples/lint-demo` ships `managed = []`). This is the belt to change 1's
   braces: if a key derivation ever drifts again, the write fails loudly
   instead of silently corrupting.

4. **`verify` classifies instead of lumping.** `MismatchKind::{Modified,
   Missing, Unmanaged}`. `Modified` = tracked file whose hash changed;
   `Missing` = tracked file that is gone; `Unmanaged` = an entry outside
   `managed_paths`, which is a bookkeeping defect and not tampering. `clean`
   counts Modified + Missing only. Unmanaged entries are surfaced in their own
   list, in both text and JSON.

   This is what stops the **unbounded violation stream**: an already-poisoned
   manifest stops generating fresh `protocol_violation` events on every Bash
   call after the upgrade. It does **not** clear events already in the chain —
   see "Deliberately not done".

5. **Gate working directory anchored** in `StateMachine::new`, `cli/status.rs`,
   `cli/transition.rs`, `cli/hooks_cmd.rs`.

### holtz

6. **`bash_guard.py` records each distinct condition once.** The reporter
   watched 51 → 57 violation events over ~6 Bash calls, all byte-identical.
   Before recording, the hook queries the ledger for an existing
   `protocol_violation` with the same `(file_path, detail)` and skips it if
   present. Derived from the ledger at check time, never mirrored in a cache
   file ([[enforcement-derive-from-ledger-not-mirror]]). The query only runs on
   the failure path, so the happy path pays nothing.

7. **`bash_guard.py` says what actually happened.** `verify` now reports a
   `kind`, so the violation detail reads `managed file deleted: …` or
   `managed file modified: expected …, got …` instead of the old
   `manifest hash mismatch: expected …, actual missing`, which described a
   deleted file and a never-existed path identically.

8. `SAHJHAN_VERSION` → `0.20.1`; re-vendor `bin/`.

9. **`enforcement_lint.py` learns a third shape of opaque gate.** Regenerating
   `ENFORCEMENT-CONTRACT.md` after change 6 moved the posture from 29 to 30
   gate-consumed events, which exposed a pre-existing under-count rather than
   anything my hook did: `no_violations` sits on `set complete perspective` and
   `converge` — the only two transitions that reach convergence — and reads
   `protocol_violation`, but its predicate lives in the sahjhan binary
   (`eval_no_violations`), so it named no event and the contract printed
   *direct check* for the one gate that can terminate a run.

   `command_succeeds` solved this with `evidence = "<event>"` (H10), but H10
   deliberately *errors* when `evidence` appears on a gate that runs no
   command — "only report what you can decide." So the third shape gets a
   third answer: a small `_ENGINE_GATE_EVENTS` table mapping engine-defined
   gate types to the events their predicate reads, cited to
   `src/gates/ledger.rs`. The two `no_violations` rows now read
   `protocol_violation` / `hook:bash_guard.py` / `agent` / forgeable **yes** —
   which is exactly the posture `events.toml` already argues for in prose
   ("forging one only blocks the forger's own convergence") and which nothing
   had counted.

   Without this the census would have been right by accident, off the
   `type='protocol_violation'` literal in the new dedup SQL, and would have
   silently gone wrong again the moment that query changed.

---

## Deliberately not done

**No reseal without daemon auth.** The report's suggested fix 5 asks for
`reseal` to work without HMAC, or for an operator-accessible escape from
`no_violations`. Making `reseal` work without daemon authentication would let
any process re-seal the config the ledger is bound to — that is the mechanism
the whole chain rests on, not an inconvenience to route around. A user request
is not an implementation requirement.

**No `violation_resolved` escape in this change.** The engine's
`eval_no_violations` already subtracts `violation_resolved` events, and holtz
has a shipped pattern for human-only channels (`quiz_exhausted_resolved`, #81:
`attestation = "human"` + deny the agent's path in `BLOCKED_SAHJHAN_SUBSUB` +
document `! sahjhan event …`). Applying it here would give the poisoned run a
bounded, human-attested way out. But `events.toml` documents permanence as a
deliberate choice, and reversing it is the maintainer's call, not a side effect
of a bug fix. Raised with the maintainer, who directed it to a tracking issue:
**#86**, which also records the engine change it would need (`no_violations`
resolving by key rather than by count — two violations on file A plus one
resolution of file B currently reads as resolved).

**No `manifest prune`.** Adjacent to the recovery question above. After change
4, stale unmanaged entries are inert — reported, not counted — so removing them
is hygiene, not repair. Folded into #86.

**Consequence for the reporter's run, stated plainly:** the 57
`protocol_violation` events are already in the chain. Upgrading stops new ones
and stops the phantom keys, but `no_violations` still counts what is already
recorded. That run remains terminal; a fresh run on the fixed binary is the
remedy today.

---

## Verification

- sahjhan: `cargo test` full suite; new `tests/paths_tests.rs` unit coverage of
  the anchoring helpers and the root/data_dir invariant; new e2e in
  `tests/integration_tests.rs` that runs the real binary **from a
  subdirectory** and asserts the manifest key is root-relative — the shape of
  the reported reproduction, not a hand-built manifest.
- holtz: `pytest -m hook_e2e` for the dedup path, contract gate, full suite +
  coverage, `ruff`, `mypy`.
- `scripts/hash-trusted-callers.sh` re-run after touching `bash_guard.py`
  ([[trusted-callers-manifest-regen]]).

---

## Bearing on other issues

**#73 (lens quiz).** The reporter's run shows `quiz_bank_generated` = 1 and
`recon_complete` fired, so the defect #73 names — nothing ever called
`store_quiz_bank()` — is addressed. But `quiz_posed` = 0 across 8,356 events
because the run never reached `set complete perspective`. Stays open: the
symptom is still unverified end to end, and #85 was the blocker.

**#83 (test/lint gates on non-Python targets).** Untouched by this run; `tqdm`
is Python. Stays open.

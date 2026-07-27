# Fix-loop suite-run cost reduction (proposals 1–4)

**Started:** 2026-07-27
**Branch:** dev
**Baseline:** holtz 0.140.1 (`cd82fed`), sahjhan 0.20.0
**Origin:** console proposal in session 3cb88455. User approved proposals 1–4, declined 5 (xdist docs).
**Related issue:** #83 (non-Python false-green) — filed this session, separate work.

## Problem

The fix loop runs the target's **full test suite three times per finding**, only
one of which is enforced:

| Where | Source | Enforced? |
|---|---|---|
| Subagent step 5 | `phase-fix-loop.md` "Run full suite. Confirm all pass." | prose |
| Orchestrator step B.10 | `phase-fix-loop.md` "re-run the full suite" | prose |
| `fix_commit` gate | `enforcement/transitions.toml:80` | **yes** |

B.10's run and the gate's run execute on a byte-identical working tree
(`git commit` doesn't modify working-tree contents), so one is strictly
redundant. On the eval-harness spec's own numbers (90 fixes, 60 s suite) this is
~4.7 h of suite execution where the spec budgeted 1.5 h.

## Target

| Stage | Suite-time (60 s suite, 90 fixes, 13 lenses) |
|---|---:|
| Today | ~4.7 h |
| + P1 collapse to 1 run | ~1.7 h |
| + P3 selective + boundary fulls | ~40 min |

## Design decisions (settled)

**D1. No sahjhan change required.** Every mechanism exists: `record_authed_event()`
(`enforcement/hooks/_common.py:245`), `restricted = true` events, trusted-callers
SO_PEERCRED auth, active-ledger marker at `docs/holtz/.sahjhan/active-ledger`.

**D2. `--lf` is REJECTED for gate commands.** `--last-failed` runs *only* the
previously-failing tests, so a gate using it can pass having run a two-test
subset — the exact false-green class as issue #83. Use `--ff` (`--failed-first`)
instead: same fail-fast benefit, still runs the whole suite.

**D3. `--no-cov` is REJECTED for the default.** It is a pytest-cov option; on a
target without that plugin pytest exits 4 (`unrecognized arguments`), breaking
every such target. Keep it as a documented override only.

**D4. The gate must NOT record to the ledger.** A `command_succeeds` gate runs
while the daemon is evaluating a transition; calling back into the daemon to
append an event risks re-entrancy/deadlock. Split the roles:
- **agent path** (`--record`): runs the suite, records `suite_green`. No
  transition in flight, so the daemon call is safe.
- **gate path** (`--check`): reads `ledger.jsonl` directly (no daemon), pure
  predicate, exit 0/1. Blocks with a satisfiable escape ("run holtz-test").

**D5. Tree hash excludes `docs/holtz/**`.** STATUS.md / PUNCHLIST.md are
rewritten every fix and cannot affect the target's tests; including them would
invalidate every cached result immediately.

**D6. The agent cannot forge `suite_green`.** Three layers: the event is
`restricted` (daemon refuses `sahjhan event`); the writer script lives under
`enforcement/` (managed path — pre-edit hook + bash_guard block edits, cf. #71);
and trusted-callers.toml pins its SHA-256 so a modified script is rejected.
The script computes the tree hash and runs the suite itself — it accepts no
caller-supplied hash or result.

## Tasks

- [x] **T1 — P2 fail-fast gate command** — DONE, commit `ba697a2`, v0.140.2
  - All 3 pytest gates now `${HOLTZ_PYTEST:-python3 -m pytest -x --ff --tb=short -q}`
  - Kept `--tb=short` rather than the proposed `--tb=line`: with `-x` at most one
    traceback prints, so short costs ~5 lines and is materially better for
    diagnosing a gate block. The win is `-x --ff`, not the tb format.
  - Two contract tests added: `test_gate_commands_never_truncate_the_suite`
    (bans `--lf`/`--last-failed`), `test_pytest_gates_fail_fast` (requires
    `-x --ff`).
  - D2 verified empirically before committing: 4-test suite, one failure, fix
    it, re-run under `--lf` -> "1 passed" exit 0. Under `--ff` -> "4 passed".
  - Observed green: ruff, mypy (51 files), 1880-test fast subset, contract gate
    (37 commands), `sahjhan lint` 0 errors, `enforcement_lint` 0 errors.
  - Also bumped the README test-count badge 1878 -> 1880 (pre-commit caught it).

- [x] **T2 — P4 `suite_green` event + verify_suite.py** — DONE, see Session 2

  **D7 (found while scoping T2, do not rediscover): the enforcement linter does
  not scan `enforcement/scripts/`.** `enforcement_lint.py:196-201` defines
  `py_dirs` as exactly `enforcement/hooks`, `<root>/hooks`, and
  `skills/holtz/scripts`. Writers are discovered by regex over those dirs and
  recorded as `hook:{rel}` (`:478`). So a restricted-event writer dropped into
  `enforcement/scripts/` is invisible: H1 reports "no write path exists" for
  `suite_green` and the restricted-writer check (`:900`) fails.

  Chosen resolution: keep the script at `enforcement/scripts/verify_suite.py`
  (semantically right — it sits beside `check_repro_evidence.py` and
  `check_sweep_evidence.py`, which are also gate-invoked helpers) and **add
  `enforcement/scripts` to `py_dirs`**. That is a correct small linter fix, not
  a workaround: gate-invoked scripts under `enforcement/` are exactly the
  category `py_dirs` means to cover, and today two such scripts already escape
  every H-check. Rejected alternatives: renaming it into `enforcement/hooks/`
  (misleading — it is not a hook) and putting it in `skills/holtz/scripts/`
  (that dir is agent-facing, and a trusted caller does not belong there).

  Daemon keying is fine either way: trusted-callers keys strip the config-dir
  prefix, so `enforcement/scripts/verify_suite.py` -> `scripts/verify_suite.py`.

  Steps:
  1. `enforcement/events.toml`: new `suite_green`, `restricted = true`,
     `attestation = "tool"`, producer `hook:enforcement/scripts/verify_suite.py`.
     Fields: `tree_hash` (`^[0-9a-f]{64}$`), `scope` (`^(full|affected)$`),
     `command`, `test_count` (optional), + `project`/`run`/`auditor`.
     Run context is built like `lens_quiz.py:403` (`base_fields`) — note that
     hook writes `project`/`run`/`auditor` only, so phase/step can be omitted.
  2. `enforcement/scripts/verify_suite.py` with two modes (D4):
     - `--record`: agent path. Computes tree hash, runs `$HOLTZ_PYTEST`, on
       green calls `record_authed_event("suite_green", …, cwd)`.
     - `--check`: gate path. Reads `docs/holtz/runs/{active}/ledger.jsonl`
       directly (NO daemon call — avoids re-entrancy while a transition is being
       evaluated). Pure predicate, exit 0/1, and on failure prints the exact
       `--record` command to run.
     Active run resolution: `docs/holtz/.sahjhan/active-ledger` marker, per
     `lens_quiz.py:347` / `quiz_vault.py:44`.
     Tree hash: HEAD oid + sorted (path, sha256) over tracked-modified and
     untracked files, **excluding `docs/holtz/**`** (D5).
     Accepts NO caller-supplied hash or result (D6).
  3. `scripts/enforcement_lint.py`: add `enforcement/scripts` to `py_dirs`.
     Expect this to surface pre-existing findings for the two existing
     gate-helper scripts — triage them, do not suppress.
  4. `scripts/hash-trusted-callers.sh`: add
     `enforcement/scripts/verify_suite.py` to `TRUSTED_SCRIPTS`, then RUN IT.
     MANDATORY — see memory `trusted-callers-manifest-regen`: skipping this
     silently disables enforcement and only `real_daemon` tests catch it.
  5. Tests: unit for tree hashing (stability, docs/holtz exclusion), `hook_e2e`
     for the record path, and a `real_daemon` test that the gate `--check`
     rejects a forged/mismatched hash.

- [ ] **T3 — P3 selective per-fix + full at boundary**  <- RESUME HERE
  - Confirm `impact_graph.py` CLI exposes `--types` on `blast_radius`
  - `verify_suite.py --scope affected`: changed files -> graph nodes ->
    `tests` edges -> test file list
  - `fix_commit` gate -> affected scope; `iteration_boundary` gate -> full scope
  - Fallback: if the graph has no `tests` edges, fall back to full suite
    (never silently narrow — cf. #83)
  - `--scope affected` is already accepted by the CLI, the event pattern, and
    `accepted_scopes()` (full satisfies affected, never the reverse). What T3
    adds is the *selection*: nothing narrows the command yet.

- [ ] **T4 — P1 collapse the redundant runs**
  - `skills/holtz/references/phase-fix-loop.md`: subagent step 5 -> affected
    subset via verify_suite; orchestrator B.10 -> ledger check, not a re-run
  - Contract tests must be updated in the SAME commit (CLAUDE.md rule)
  - `test_subagent_contract_consistency.py` may need updating
  - **Record AFTER the commit, not before.** The tree hash includes HEAD's oid,
    so committing changes it even when the content is identical. Pinned by
    `TestTreeHash::test_committing_the_same_content_changes_it`. A `--record`
    placed before `git commit` would leave every `fix_commit` gate re-running
    the suite — the exact cost T2 exists to remove, silently restored.
  - Replace all three `${HOLTZ_PYTEST:-...}` gate commands in
    `transitions.toml` with `verify_suite.py --check`. Until then the pytest
    default lives in four places; after T4 it lives only in verify_suite.py.
  - Then add the `tool:`-reachability check deferred below.

- [ ] **T4a — ratchet: a `tool:` producer nothing invokes**
  - H4 asks a `hook:` "is it registered in hooks.json?". The `tool:` analogue
    is "does anything invoke it by path?" — a gate `cmd` in transitions.toml,
    a skill file, or another hook. Today nothing invokes `verify_suite.py`
    (T3/T4 wire it), so adding the check now would fail the build on a
    deliberately half-wired tree. Add it in the T4 commit, where it is green
    on arrival — the same discipline as #82's ratchet rounds.

- [ ] **T5 — release**
  - `scripts/pre-release-check.sh`, changelog, release PR dev -> main

## Open questions

- Does `impact_graph.py`'s CLI expose `--types` for `blast_radius`? The Python
  API does (`impact_graph.py:186`, bidirectional BFS with an edge-type filter,
  so `--types tests --depth 1` walks `tests` edges backwards to the covering
  test files). CLI exposure unverified — check `_build_parser` at `:327`.
- `iteration_boundary` currently carries only the `pattern_analysis_overdue`
  gate; adding a full-suite gate lengthens that transition. Acceptable — it
  fires every 3–5 fixes, not every fix.
- T3's fallback needs deciding explicitly: when the impact graph has no `tests`
  edges for a changed file, fall back to the FULL suite. Never silently narrow
  — that is the #83 failure mode arriving by another road.

## Session log

### Session 1 (2026-07-27)
- Investigated cost structure; confirmed 3 full-suite runs per fix, 1 enforced.
- Confirmed no sahjhan change needed (D1) — `record_authed_event`, `restricted`
  events, trusted-callers SO_PEERCRED auth, and the active-ledger marker all
  already exist in holtz.
- Caught D2 (`--lf` false-green, verified empirically) and D3 (`--no-cov` breaks
  targets without pytest-cov) before writing either into the config.
- Found D7 (linter does not scan `enforcement/scripts/`) while scoping T2.
- Shipped T1 (`ba697a2`, v0.140.2).
- Filed #83 (adjacent, separate work: non-Python false-green).

### Session 2 (2026-07-27)

Shipped T2. Four design points changed from the Session-1 plan, each after
looking at the code rather than reasoning from the plan:

**D8 (supersedes D4's mechanism, keeps its constraint).** `--check` reads the
ledger through `sahjhan query`, not by parsing `ledger.jsonl`. D4's rule — the
gate path must not call the daemon — is right and is satisfied: `cmd_query`
(`sahjhan/src/cli/query.rs`) loads config, resolves the ledger via
`resolve_ledger_from_targeting` (the *same* function the gates use), and runs
SQL over the file. There is no socket anywhere in that path; verified by
reading it and by running `sahjhan query` against this repo with no daemon up
for its config dir. The plan's "read `docs/holtz/runs/{active}/ledger.jsonl`"
was both a mirror of engine resolution (marker → `ledgers.toml` → registry
default → `data_dir/ledger.jsonl`) and factually wrong about the path — this
repo's active ledger is `docs/holtz/.sahjhan/ledger.jsonl` and `runs/` does not
exist. Delegating means block condition and evidence read one file by
construction.

**D9 (new). The producer grammar needed a `tool:` kind.** D7's fix (add
`enforcement/scripts` to `py_dirs`) is necessary but not sufficient: H4 demands
that a `hook:` producer appear in `hooks/hooks.json`, and `verify_suite.py` is
not a Claude Code hook and never will be. Observed, not predicted — declaring
it as `hook:` produced `H4 error: … is not registered in hooks/hooks.json …
the harness never runs it`. So `tool:<path>` now names a writer invoked *by
path* (a gate command, or a command a skill file teaches). H4 skips the
registration question for it and keeps the hash-pin requirement, which is what
the daemon actually checks. `TestToolProducers` pins both halves; four of its
five tests fail against the pre-change linter (verified by stashing it).

**D10 (new). The event type must be a string literal at the write site.**
Writing `record_authed_event(EVENT_TYPE, …)` hid the writer from H2/H3 —
"real writers: none" — because discovery scans for the literal. That is not a
linter shortcoming to work around; the literal is what makes the
`[[producers]]` declaration falsifiable. Constant dropped, comment left at the
top of the file so nobody re-hoists it.

**D11 (new). Every `--check` block prints its escape, including the
configuration failures.** A project whose ledger has never been initialised
makes `sahjhan query` exit 2 with an I/O error, and the first implementation
reported that verbatim with no next step. To the agent, "no ledger" and "no
matching event" mean the same thing and are cleared by the same command, so
`_block()` now prints the underlying reason *and* the `--record` line. Found by
a test, not by reading.

Also observed: D7's expectation that scanning `enforcement/scripts` would
surface pre-existing findings in the other gate helpers did **not** hold — 0
new findings. The discovery regexes are narrow enough that
`check_sweep_evidence.py`'s `("final_sweep_start", "lens_sweep_started")` tuple
is not mistaken for a write.

`available_in_states` deliberately omitted from the producer: which states may
record a green is T3/T4's question (`fix_commit` and `iteration_boundary` at
minimum), and guessing it now would be a claim nothing checks.

**Observed green** (all exit 0 unless noted): ruff, mypy (52 files), full
pytest suite `1912 passed` with coverage 91.15% ≥ 80 (verify_suite.py at 89%),
contract gate 37 commands, `scripts/lint-enforcement.sh` exit 0 (L1–L7 and
H1–H9, 0 errors; the same 12 pre-existing warnings as the T1 baseline),
`enforcement_contract.py --write` regenerated (`tool` count 4 → 5, posture
"21 of 29"). README badge 1880 → 1912. `scripts/hash-trusted-callers.sh` rerun
after the final edit to `verify_suite.py`.

**Handoff state:** T2 committed and green. T3 is next — the mechanism exists
and is unused, which is the intended increment: `verify_suite.py --check` is
wired into no gate and taught in no skill file until T3/T4.

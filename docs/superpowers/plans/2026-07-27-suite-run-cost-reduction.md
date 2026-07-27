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

- [x] **T3 — P3 selective per-fix** — DONE, see Session 3

  The gate wiring bullet that was filed under T3 (`fix_commit` -> affected,
  `iteration_boundary` -> full) **moved to T4 deliberately** — see Session 3's
  closing note. Shipping the gate without the skill file that teaches
  `--record` would deadlock every fix_commit.

- [ ] **T4 — P1 collapse the redundant runs**  <- RESUME HERE
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

- ~~Does `impact_graph.py`'s CLI expose `--types` for `blast_radius`?~~
  **Answered:** yes, spelled `--type` with `dest="types"`, comma-separated
  (`impact_graph.py:352`). Moot in the end — T3 does not shell out to it (D13).
- `iteration_boundary` currently carries only the `pattern_analysis_overdue`
  gate; adding a full-suite gate lengthens that transition. Acceptable — it
  fires every 3–5 fixes, not every fix.
- ~~T3's fallback needs deciding explicitly.~~ **Answered:** D14 — per changed
  file, and again at run time on a pytest exit of 4 or 5.

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

### Session 3 (2026-07-27)

Shipped T3. Four decisions the Session-1 plan left open; each is a place where
the obvious implementation would have produced a false green.

**D12 (new). `affected` is measured from the last *full* green's commit, not
from `HEAD~1` and not from the working tree alone.** The plan says "changed
files" without saying *since when*, and T4's own note makes the omission
load-bearing: the record happens **after** `git commit` (step 11 → 12 of
`phase-fix-loop.md`), so at record time `git diff HEAD` is empty. Read
literally, "changed files" would be the empty set on every fix — a selection of
zero tests, recorded green. `HEAD~1` fixes the symptom but is a heuristic
("one fix = one commit") standing in for a fact. So `suite_green` now carries
`commit_hash` (reusing `finding_resolved`'s existing field name and its column
— the query schema is the union of declared fields, and an undeclared column
makes `sahjhan query` fail outright, verified), and `_baseline_commit` reads
the newest **`scope='full'`** green. `git diff --name-only <baseline>` then
spans committed *and* uncommitted work in one command, which is what the loop
needs because it records on both sides of a commit.

Baselining on the last *full* green rather than the last green of any scope is
the substantive half. Chaining affected runs off each other is only sound if
the selection is complete, and a hand-authored graph is not — a file nobody
drew a `tests` edge for would drop out of every window forever. Measuring from
the last full green bounds the gap to one iteration, and `iteration_boundary`
re-bases it.

**D13 (new). The graph is read as *data*; `impact_graph.py` is never
imported.** This process is the one the daemon authenticates to write a
restricted event. `skills/holtz/scripts/` is **not** in `_sahjhan_bootstrap`'s
`PROTECTED` list (checked: `enforcement/`, `bin/sahjhan`, `hooks/hooks.json`,
`_sahjhan_bootstrap.py`), so importing from it would let agent-authored *code*
execute under the trusted identity — an import-time `subprocess.run` monkeypatch
would forge greens outright. Reading agent-authored *data* is a strictly
smaller hole, and it is the hole the design already accepts. What was needed
was a one-hop edge lookup, not a copy of `blast_radius`, so this is not the
mirror D8 warned about.

**Stated plainly, because it is the honest bound:** an `affected` green is a
**cost** optimisation, not an integrity claim. `docs/holtz/impact-graph.json`
is agent-written, so a bogus `tests` edge can narrow one `fix_commit`. It
cannot survive the next `iteration_boundary`, which accepts `full` and nothing
else. That layering is the reason the boundary gate must stay strict in T4.

**D14 (new). Narrowing is earned per changed file, and again at run time.**
The plan's fallback ("if the graph has no `tests` edges") is global; per-file
is the correct grain — one unaccounted-for file widens the whole run, so a
subset can never quietly skip the file just edited. Concretely: a changed
`test_*.py`/`*_test.py` selects itself (the TDD loop writes one every fix and
recon has never heard of it — without this rule `affected` would never narrow
once); any `conftest.py` widens (its reach is every test below it and no edge
says so); a source file with no `tests` edge widens; a stale edge naming a
deleted test widens. Then a second guard at run time: pytest exits 4 on a usage
error and 5 on an empty collection, and **neither is a statement about the
code** — so a narrowed run ending that way re-runs full instead of recording.
Zero tests executed must never satisfy a gate. This is also what keeps exotic
`$HOLTZ_PYTEST` overrides working: one that rejects trailing paths widens
instead of wedging.

**D15 (new). The recorded scope is what *ran*, not what was asked for.** A
request for `affected` that widened records `full` — true, and strictly
stronger, since `full` satisfies an `affected` check. Recording the request
would understate the run and waste the stronger evidence.

Also added `--print-affected`, because a selection that degrades to the full
suite forever is otherwise indistinguishable from one that works, and the cost
this task exists to remove would come back unnoticed.

**Observed green** (all exit 0 unless noted): ruff, mypy (52 files),
`tests/test_verify_suite.py` 51 passed including 10 `real_daemon` integration
tests, full suite `1936 passed` with coverage 91.07% ≥ 80 (verify_suite.py at
89%), contract gate 37 commands, `scripts/lint-enforcement.sh` exit 0 (L1–L7
and H1–H9, 0 errors, the same 12 pre-existing warnings as T1/T2),
`docs/ENFORCEMENT-CONTRACT.md` reported current (a new optional field does not
change the gate table). README badge 1912 → 1936.
`scripts/hash-trusted-callers.sh` rerun after the last edit to
`verify_suite.py` — required before the `real_daemon` runs, per memory
`trusted-callers-manifest-regen`.

**Handoff state / why T3 stopped where it did.** The mechanism is complete and
still invoked by nothing. Wiring `fix_commit` to `--check --scope affected`
**must land in the same commit as the `phase-fix-loop.md` change that teaches
`--record`** — a gate demanding evidence no one is told to produce blocks every
fix with a message the agent cannot satisfy, which is #77's deadlock shape
rebuilt on purpose. So T4 is one commit: transitions.toml (all three
`${HOLTZ_PYTEST:-...}` gates → `verify_suite.py --check`, `fix_commit` at
`affected` and the rest at `full`), the skill file, the contract tests, and
T4a's `tool:`-reachability ratchet — green on arrival.

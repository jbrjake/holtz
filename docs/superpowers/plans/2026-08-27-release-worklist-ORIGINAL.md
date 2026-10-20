# Release worklist — v0.141.3 → 0.169.1 (dev @ `48c72fd`)

**This is the working document.** Self-contained: every defect, anchor, plan
step, validation check and status field is here. You should not need another
file open to do the work.

- **Findings record (read-only):** `2026-08-26-release-review-punchlist.md` — why
  each item is a defect, the review passes, the driven observations. Cite it; do
  not edit it.
- **Superseded:** `2026-08-27-release-punchlist-remediation-plan.md` — its
  content is folded in here. Safe to delete.

49 items → **30 work units**, ordered by execution sequence within priority
bands. Work top to bottom; the order already respects dependencies.

---

## Status legend

| Mark | Meaning |
|---|---|
| `TODO` | Not started |
| `WIP` | In progress |
| `DONE` | All validation checks observed green, committed |
| `BLOCKED` | Waiting on a decision (see Decisions) or another unit |
| `PARKED` | Deliberately deferred — record why in the unit |

**Status attaches to the clause, not the unit.** A unit is `DONE` only when every
`- [ ]` under it is ticked. Partial work stays `WIP` with the unticked boxes
visible — an item id is not a unit of work, a clause is.

**Evidence is required, not optional.** Each validation check has an
`Evidence:` slot. Paste the observed output — exit code, assertion, `gh run view`
line. A check with an empty evidence slot is not done, regardless of belief.
"Should pass" / "in-flight" / "good to go" are the violation, not just
imprecision (`CLAUDE.md`).

---

## Dashboard

| Unit | Items | Tier | Status | Blocked by |
|---|---|---|---|---|
| **P1 — before functional testing** ||||
| W01 | fixtures F1/F2/F3 | — | `TODO` | — |
| W02 | 29 | A | `TODO` | W01 |
| W03 | 31 | A | `TODO` | — |
| W04 | 19, 1 | A | `TODO` | W01 |
| W05 | 2 | A | `TODO` | ~~D-a~~ ruled |
| W06 | 20 | B | `TODO` | ~~D-d~~ ruled |
| W07 | 3 | A | `TODO` | W06 |
| W22 | 27 | **A** | `TODO` | — *(moved from P3 by D-h)* |
| **P2 — before trusting results** ||||
| W08 | 32, 43 | B | `TODO` | W01 |
| W09 | 25, 26 | B | `TODO` | — |
| W10 | 35 | B | `TODO` | W01 |
| W11 | 42 | B | `TODO` | W01 |
| W12 | 34, 28 | B | `TODO` | — |
| W13 | 37, 17 | B | `TODO` | — |
| W14 | 5, 10 | B | `TODO` | — |
| **P3 — before release** ||||
| W15 | 30 | C | `TODO` | — |
| W16 | 18 | C | `TODO` | W09 |
| W17 | 22 | C | `TODO` | W16 |
| W18 | 36, 33 | C | `TODO` | W02 |
| W19 | 40, 47 | C | `TODO` | W02 |
| W20 | 41, 38 | C | `TODO` | — |
| W21 | 9 | C | `TODO` | ~~D-c~~ ruled |
| ~~W22~~ | 27 | — | — | *moved to P1 above (D-h)* |
| **P4 — hygiene and record** ||||
| W23 | 4, 7, 8, 13, 14 | D | `TODO` | — |
| W24 | 6, 44 | D | `TODO` | ~~D-b, D-g~~ ruled |
| W25 | 11, 39, 49 | D | `TODO` | W05, W14 |
| W26 | 48 | D | `TODO` | — |
| W27 | 15, 45, 46 | D | `TODO` | — |
| W28 | 12, 16 | D | `TODO` | all above |
| W29 | 21, 24 | D | `TODO` | ~~D-e, D-f~~ ruled |
| W30 | 23 | D | `TODO` | W12 *(same file)* |

**Release gate: do not cut before W02, W03, W04, W08 are `DONE`.**
`docs/design/convergence-speed-status.md` records P0.3 as shipped at `48c72fd`.
With items 1 and 19 open that row is wrong, and it is the row a reader trusts.
**W08 is in the gate for the same reason**, from the row's own words: line 51 says
*"D41 — … keyed on the actor now, **clear still run-global**"* — which is item 32.
The row names the defect and still reads SHIPPED.

The other P1 units (W05, W06, W07, W22) are **not** in the release gate by
deliberate choice: they block a *functional test*, not the truthfulness of a
shipped-status row. Cutting with them open is a worse release; cutting with the
four above open is an inaccurate one.

---

## Decisions — all 8 RULED (Jon, 2026-08-27)

**Every decision below is Jon's.** Where a ruling differs from this file's earlier
recommendation, the recommendation is struck and the ruling stands — the
recommendation column is kept only so the reasoning that was put to him remains
auditable. **Do not re-open a ruled row.** A clause that cannot be implemented as
written is a question, not a design opening.

| ID | Unit | Question | **RULED** | Was recommended |
|---|---|---|---|---|
| **D-a** | W05 | MEDIUM budget (item 2) | **Drop the conjunct from `converge`** (`transitions.toml:553`). The cap on `defer_medium` and the breaker's budget-spent post-state on `pattern_done`/`iteration_boundary` are untouched and remain correct. | same (revised recommendation) |
| **D-b** | W24 | `DEFERRED.md` (item 6) | **Ledger predicate over deferrals + drop `finding` from the render trigger.** The predicate must be **vacuously true at zero deferrals**. | "drop conjunct + drop trigger" |
| **D-c** | W21 | `merge_finding` (item 9) | **Severity floor AND target must be open.** Both terms. | severity floor only |
| **D-d** | W06, W07 | Merged findings' perspective (item 20) | **Require Justine to state it.** `validate_punchlist.py` errors on a missing perspective; `justine-skill.md` teaches it; the merge carries the stated value. | (none offered) |
| **D-e** | W29 | Round cap population (item 21) | **Narrow `protocol.toml`'s claim and record the acceptance.** Do not change the population. | same |
| **D-f** | W29 | Hardening batch diff (item 24) | **Document as deliberate; fix the docstring.** | same |
| **D-g** | W24 | `STATUS.md` render timing (item 44) | **Add `on_event` for the finding family.** | same |
| **D-h** | W22 | Tier for item 27 | **Tier A — before functional testing.** Executes in P1. | Tier C |

### Two rulings enlarged the work; one moved a unit

- **D-d** and **D-c** both took the option that does *more*. W06 grows a
  validator change and a skill-file change; W21 gets two SQL terms, not one.
- **D-b** took the ledger-predicate branch, which is the one carrying the
  vacuity trap: **a run that defers nothing must still converge.** That case is
  the first validation check on W24, not an afterthought.
- **D-h** moved item 27 from unassigned to **Tier A**, two bands up from the
  recommendation. W22 now runs in P1, before functional testing — which implies
  Linux-with-seccomp is a target for the next functional run.

---

## Standing gates

Run from the repo root. `.venv/bin/python` is explicit so checks do not depend on
shell activation state.

```bash
.venv/bin/python -m pytest -p no:randomly -q                   # full suite, sequential
.venv/bin/python -m pytest -m hook_e2e -q                      # after any hook change
.venv/bin/python -m pytest -m contract -q                      # after any skill-file change
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/ scripts/ enforcement/scripts/
.venv/bin/python scripts/contract_gate.py
.venv/bin/python scripts/enforcement_lint.py
.venv/bin/python scripts/enforcement_contract.py --check
```

**`real_daemon` is a pytest _fixture_ (`tests/conftest.py:179`), not a marker.**
`pyproject.toml` registers only `machine_specific, contract, hook_e2e,
integration, slow, network`. Where this worklist labels a check `· real_daemon`
it means *request the fixture*. Do not write `@pytest.mark.real_daemon` — there is
no `--strict-markers`, so pytest accepts it silently and `-m real_daemon` then
selects nothing. Mark those tests `slow` if they need selecting.

### Four operational rules that have each already cost time

1. **After editing any hook in `scripts/hash-trusted-callers.sh`, run
   `bash scripts/hash-trusted-callers.sh` before any `real_daemon` test.** A stale
   hash makes every gate fail **open** while the hook still exits 0 — the suite
   goes green for the wrong reason. `git-hooks/pre-commit` self-heals a real
   commit; a manual test run does not. **Regenerate before mutating**, or a RED is
   a stale-hash artifact rather than the thing under test.
2. **Do not bisect against a failure seen once.** The bash TDD gate times out at
   5 s under concurrent pytest. Confirm a failure is deterministic (3× unchanged)
   before treating a bisect step as evidence. This flake is live during this work
   (it is item 17/37's mechanism).
3. **Stage explicitly — never `git add -A`.** The tree carries untracked-by-design
   plan docs and a ~100 MB vendored binary. Use `git add <paths>` and read
   `git status --short` column 1 afterwards; one bad path makes the whole command
   stage nothing, and a partial commit looks successful.
4. **Two `_common.py` modules exist** (`hooks/` and `enforcement/hooks/`). The
   wrong one imports cleanly and makes every query return empty. Drive hooks by
   subprocess, and never let a negative assertion rest on an empty set.

### Commit conventions

`fix:`/`feat:` for skill files, `references/`, `agents/`, `hooks.toml` — these are
functional deliverables. `docs:` only for README, CHANGELOG, CONTRIBUTING.
`post-commit` bumps the version and amends; the first `[dev …]` hash git prints is
orphaned — verify a hash cited in a doc with `git merge-base --is-ancestor`.
**Commit as you go**, each unit the moment its gates are green.

---

## Verification status of this worklist

Every file:line anchor below was re-read against the tree at `48c72fd`. Nothing is
carried on trust from the punchlist. Three results:

- **Item 15 upgraded to observed.** The tier list asked whether the undeclared
  `hypothesis` dependency breaks a fresh checkout. It does:
  ```
  $ python3 -m pytest tests/test_property_based.py --collect-only -q
  E   ModuleNotFoundError: No module named 'hypothesis'
  !!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!
  ```
  `.venv` carries `hypothesis 6.156.6`, which is why every gate observation in
  the punchlist is green while this is true.
- **Item 30 gained an implementation hazard** the review did not name — see W15
  step 3. Adding `&` to the splitter naively breaks `2>&1`.
- **Item 27 is in no tier** — see Decisions.

Everything else confirmed as written: the five `cwd`-relative probes (29), the
three-way `NotebookEdit` disagreement (40), `_sahjhan_bootstrap.py` absent from
`TRUSTED_SCRIPTS` (47), and `deferred.md.tera` missing the `resolved_ids` that
`punchlist.md.tera:21` has (44).

---
---

# P1 — before functional testing

A good-faith three-wide run hits these: it deadlocks, enforcement silently stops
measuring, or convergence is unreachable.

---

## W01 — Test fixtures F1, F2, F3

**Status:** `TODO`  ·  **Tier:** — (enabler)  ·  **Items:** none directly
**Unlocks:** 19, 1, 32, 35, 42 (F2) · 29, 47 (F1) · 31 (F3) — **8 items**
**Commit:** `test: fixtures for worktree cwd, two actors, and taught-command fields`

### Why first

Eight items are unfixable-with-confidence today for one reason: **no test
constructs the situation they break in.** Five separate defects (19, 1, 32, 35,
42) share a single cause — no test drives two actors. Two more (29, 47) share
another — no test runs a hook with a worktree-shaped `cwd`. Build these once.

⚠️ **Two reconciliations, both corrected here rather than carried forward.**

- Items **34** and **26** were listed as unlocked by this unit; nothing in it or
  in W12 / W09 says which fixture they need, and neither unit declares a W01
  dependency. Dropped from the list. If either turns out to need F2 while being
  worked, add the edge to the dashboard then.
- Item **47** is claimed for F1, but its defect (`_sahjhan_bootstrap.py` absent
  from `TRUSTED_SCRIPTS`) is not worktree-shaped, and W19 declares only W02.
  Kept, because W19's **V4** drives a Bash source-write through the fail-open
  half and F1's env-scrubbing is what makes that subprocess reliable under a git
  hook — but **if V4 can be driven without F1, this edge is spurious**; say so
  and drop it rather than manufacturing a use.

### F1 — `worktree_cwd`

- [ ] Temp git repo with `docs/holtz/.sahjhan/` gitignored and populated
- [ ] `git worktree add` producing a linked checkout that (correctly) lacks it
- [ ] Hook events driven through the existing `_run_hook` subprocess helper with
      `cwd` set to the worktree
- [ ] **Scrub `GIT_DIR` / `GIT_INDEX_FILE` from the subprocess env** — they leak
      from the enclosing git hook and make `git worktree add` exit 128 under
      pre-commit only

**Fixture pass criterion:** with **no product change**, a `bash_guard.py` event at
the worktree cwd returns `allow` and one at the main checkout returns the
manifest-verify path. That asymmetry *is* item 29; the fixture is correct when it
reproduces the bug.

- [ ] **F1-V** Asymmetry reproduced. Evidence: ___

### F2 — `two_actors`

- [ ] Drive actor A and actor B through record → courier → edit in the order the
      three-wide loop produces: **both `test_failed_before_fix` rows land before
      either courier runs**
- [ ] Fixture data chosen so every plausible counted quantity gives a **different**
      number (buckets vs commits vs actors)

**Fixture pass criterion:** it can express "A's evidence row names A's finding" as
a *positive* assertion. `len(rows) == 2` and `A != B` are what let items 19 and 32
through — `!=` passes when the code lands on a third wrong answer, and a count
passes when two quantities coincide.

- [ ] **F2-V** Positive per-actor assertion expressible. Evidence: ___

### F3 — `taught_command_fields`

- [ ] For each `sahjhan event <type> --field …` string extracted from a skill file
      or a `hooks.toml` message, assert the field set satisfies `events.toml`'s
      required fields for that type
- [ ] Static, no daemon, runs in CI
- [ ] Second layer, using the `real_daemon` **fixture** (not a marker — see
      Standing gates): missing field → `error: missing field '<name>'`, exit 4

**Why it does not exist:** `contract_gate.py` asks "does the hook allow this
string," never "does the engine accept its fields."

- [ ] **F3-V** Static check runs in CI and reports per-command. Evidence: ___

### Exit criteria

- [ ] `.venv/bin/python -m pytest -m hook_e2e -q` → exit 0. Evidence: ___
- [ ] No product file changed in this commit. Evidence: `git show --stat` ___

---

## W02 — Item 29: worktree path resolution disables enforcement for the three subagents

**Status:** `TODO`  ·  **Tier:** A  ·  **PROVEN**  ·  **Depends on:** W01 (F1)
**Commit:** `fix(enforcement): resolve the audit-active probe at the project anchor`

### Defect · verified at `48c72fd`

`.gitignore:15` ignores `docs/holtz/.sahjhan/`, so a `git worktree add` checkout
does not contain it. **Five sites** decide "is an audit active here" with a
`cwd`-relative probe:

| Site | Consequence in a subagent's worktree |
|---|---|
| `bash_guard.py:49-51` | → `exit_ok()`; managed-file integrity verification skipped for every Bash call the three subagents make |
| `_common.py:171-172` | fails **open**: on `hook eval` timeout the source edit is allowed with the TDD gate never evaluated |
| `_common.py:427` (`_read_init_pid`) | daemon-death detection off |
| `_common.py:458` (`_write_terminated_marker`) | terminated marker written to the wrong place |
| `_sahjhan_bootstrap.py:367` (`_daemon_stop_permitted`) | a subagent may run `sahjhan daemon stop` mid-loop — which the block message itself says "destroys the HMAC session key and terminates the run" |

The socket, by contrast, resolves through `project_anchor` and **is** correctly
shared with the main daemon (D40, `_common.py:278`). The anchor exists; the probe
next to it was left `cwd`-relative.

Sixth site, the courier half: `verify_suite._run_number(cwd)` (`:316-323`) reads
`cwd/docs/holtz/.sahjhan/active-ledger` → `"0"` in a worktree, and `events.toml`
accepts `"0"` against `^\d+$`. Because sahjhan's emit resolver inherits the newest
ledger value, the *next* `fix_commit`'s emitted `finding_resolved` carries
`run=0, project=<worktree-dir>` too, and so do the `defer_*` emits — corrupting run
attribution and breaking `pattern_round._current_run` / `stale_sweep._current_run`.

`pre_tool_hook.py:9` promises "Fails closed during active audits if the daemon is
unreachable." False for exactly these actors.

### Plan

- [ ] **1.** Add one named helper to `_common.py`, beside `boundary_dir`, defined
      in terms of the same anchor — one expression of the fact, not two careful
      copies:
      ```python
      def audit_data_dir(cwd: str) -> str:
          return os.path.join(project_anchor(cwd), "docs", "holtz", ".sahjhan")

      def audit_active(cwd: str) -> bool:
          return os.path.isdir(audit_data_dir(cwd))
      ```
- [ ] **2.** Replace all five probes with `audit_active(cwd)` / `audit_data_dir(cwd)`
- [ ] **3.** `_sahjhan_bootstrap.py` keeps its lazy-import discipline (deliberately
      import-free at module level so a broken sibling cannot disable the bootstrap
      guards) — import inside the function
- [ ] **4.** Point `verify_suite._run_number` and the courier's `project` field at
      `audit_data_dir(cwd)`
- [ ] **5.** `bash scripts/hash-trusted-callers.sh` — this edits `_common.py`,
      `bash_guard.py` and `_sahjhan_bootstrap.py`, three manifest-listed callers

### Validation

- [ ] **V1** `bash_guard.py` at a worktree cwd performs manifest verification
      rather than `exit_ok()`. Evidence: ___
- [ ] **V2** `_common.exit_enforcement_error` at a worktree cwd **denies**. The
      punchlist's observation `nodir → allow, withdir → deny` must become
      `deny → deny`. Evidence: ___
- [ ] **V3** `sahjhan daemon stop` from a worktree cwd is **blocked**. Evidence: ___
- [ ] **V4** `suite_courier` at a worktree cwd writes `run=<real run number>` and
      the anchored project — **not** `run="0"`, not the worktree dir name. Assert
      it equals the main checkout's value. Evidence: ___
- [ ] **V5** Worktree cwd + unreachable daemon → `deny`, making
      `pre_tool_hook.py:9`'s docstring true. Evidence: ___
- [ ] **V6 · non-vacuity** Revert step 1 to `cwd`-relative → V1–V5 **all** go red.
      Any that stays green is asserting the wrong thing. Evidence: ___
- [ ] **V7** `pytest -m hook_e2e` → exit 0. Evidence: ___

---

## W03 — Item 31: the taught TDD record and the gate's own escape omit required fields

**Status:** `TODO`  ·  **Tier:** A  ·  **PROVEN**  ·  **Depends on:** W01 (F3)
**Commit:** `fix(fix-loop): teach the field set the engine actually requires`

⚠️ **`phase-fix-loop.md` is edited by three units — W03 (here), W12 step 4, and
W30.** All three touch or sit next to **line 52**: this unit rewrites the command
on it, W12 adds a "run it alone" warning to it, W30 rewrites the rework path
below it. Execution order is W03 → W12 → W30, so **only this unit may trust the
line numbers**; the later two must re-read and match on text.

### Defect · verified at `48c72fd`

`events.toml:602-607` requires `finding_id, test_name, project, run, auditor` on
`test_failed_before_fix` — none marked optional. But:

| Where | Teaches |
|---|---|
| `phase-fix-loop.md:52` | `--field finding_id=BH-NNN --field test_name=...` only |
| `hooks.toml:30` (the TDD block message) | same two fields only |
| `SKILL.md:156` | the **full** form for `fix_start`: `--field project=holtz --field run=N \` |

`sahjhan event` does not inherit run context — only `emits` do. So the taught
command exits 4 and **the block prints an escape that cannot run as written**, on
the first fix of every run. This is #77's unsatisfiable-escape shape.

Five more inline-backtick commands in `phase-fix-loop.md` share the omission:
`:7` `reference_read`, `:50` and `:167` `fix_start`, `:55` `blast_radius`,
`:57` `hardening_complete`, `:115` `finding`.

**Why it shipped:** `contract_gate.py:37 extract_sahjhan_commands` reads fenced
blocks only, and asks only "does the hook allow it" — never "does the engine
accept its fields." `hooks.toml`'s message is not a skill file, so it is out of
scope entirely.

### Plan

- [ ] **1.** Bring `phase-fix-loop.md:52` to the full field set, using
      `SKILL.md:156`'s spelling verbatim so the two files stop disagreeing
- [ ] **2.** Same edit to the `hooks.toml:30` block message — this is the escape a
      blocked agent actually copies
- [ ] **3.** Same for the six inline-backtick commands. **Check each against its
      own `events.toml` stanza**; do not assume they need the same fields
- [ ] **4.** Extend `contract_gate.py` to inline backticks, not just fenced blocks
- [ ] **5.** Add F3's field-validation check to the gate: a taught command missing
      a required field is a gate failure

### Validation

- [ ] **V1** `.venv/bin/python scripts/contract_gate.py` → exit 0, **and the
      reported command count increases** (it now sees inline backticks). Record
      before/after; an unchanged count means step 4 did not take effect.
      Evidence: before ___ after ___
- [ ] **V2** F3 static check passes for all six commands. Evidence: ___
- [ ] **V3 · real_daemon** Run the exact string from `phase-fix-loop.md:52` against
      the binary → exit 0. Capture the before state too (`error: missing field
      'project'`, exit 4). Evidence: before ___ after ___
- [ ] **V4 · non-vacuity** Delete `--field project=` from the taught form → F3
      check goes red. Evidence: ___
- [ ] **V5** A test asserts `hooks.toml`'s message and the skill file's step 3
      carry the **same** field set, so they cannot drift apart again. Evidence: ___
- [ ] **V6** `pytest -m contract` → exit 0. Evidence: ___

---

## W04 — Items 19 + 1: the fix loop's two independent breaks

**Status:** `TODO`  ·  **Tier:** A  ·  **both PROVEN**  ·  **Depends on:** W01 (F2)
**Commit:** `fix(enforcement): pair TDD evidence by row and scope its window to the actor`

Land together: they interact, they share F2, and **19 fires first** — before any
`fix_commit` exists to revoke anything. One test drives both.

### Defect 19 · `tdd_courier.py:61-66`

`_UNPAIRED` selects the newest `test_failed_before_fix` on the **whole ledger**
past a run-global `tdd_evidence` watermark, then stamps the caller's `agent_id` on
it. It never matches the row *this* Bash line wrote.

```
agent-A records BH-001 / test_A     seq 100
agent-B records BH-002 / test_B     seq 101
courier(agent-A) -> tdd_evidence { agent_id: agent-A, finding_id: BH-002, test_name: test_B }
courier(agent-B) -> warn: "the ledger holds no new test_failed_before_fix"
```

Three consequences: **(a)** it is a TDD-gate bypass — A may now edit source having
recorded nothing, and any actor can ride any other's unpaired failing test;
**(b)** B is starved and its warning does not say why; **(c)** `LIMIT 1` loses the
older row permanently.

### Defect 1 · `enforcement/hooks.toml:32-36`

D33 scoped the gate's **filter** to `agent_id` and left the **window** at
`since = "last_transition"`, which is run-global. The orchestrator records a
`fix_commit` every time any subagent lands, so every other in-flight subagent
loses its own authorisation — and its escape (re-record a failing test) is
unreachable once its fix is written. Observed: agent-B records → `allow`; an
unrelated `fix_commit` lands → the same edit returns **`deny`**.

This is D41's run-global-coupling defect, fixed in one gate and not the other.

### Plan

- [ ] **1.** (19) Pair by the row, not by a global watermark. The command text
      carries `--field finding_id=…` and the courier already refuses anything but a
      single canonical segment, so parse the id and scope **both halves**:
      ```sql
      WHERE type='test_failed_before_fix' AND finding_id=<id>
        AND seq > COALESCE((SELECT MAX(seq) FROM events
                            WHERE type='tdd_evidence' AND finding_id=<id>), 0)
      ```
- [ ] **2.** (19) Keep reading `test_name, run, auditor, project` off the selected
      row, so the courier still invents nothing
- [ ] **3.** (1) **First establish whether the engine can express an actor-scoped
      window.** Run `ledger_has_event_since` against the vendored binary — do not
      infer it from docs
- [ ] **4a.** If it can: scope the window to the actor in `hooks.toml`
- [ ] **4b.** If it cannot, **the fix is in sahjhan and that is the correct place
      for it.** Do not add a holtz-side mirror of the transition log — two
      expressions of one window is the shape that deadlocked before. Ship the
      engine change and bump the pin (three places; `_resolve.SAHJHAN_VERSION`
      governs and silently reverts the binary and marker)
- [ ] **5.** `bash scripts/hash-trusted-callers.sh`

### Validation

- [ ] **V1** (19) Two actors, both rows landing before either courier fires:
      `tdd_evidence where agent_id='agent-A'` names **A's own finding**, same for
      B; both hold exactly one row. Evidence: ___
- [ ] **V2** (19) Delete `test_it_takes_the_newest_unpaired_row` in
      `test_tdd_courier.py` — it asserts the defect as intended behaviour via a
      string match on the SQL. **Do not "repair" it into asserting the new SQL
      string**; replace it with V1's behavioural test. Evidence: ___
- [ ] **V3** (19) Two unpaired rows, two couriers → two evidence rows. No row lost.
      Evidence: ___
- [ ] **V4** (1) An actor holding its own evidence **survives** a sibling's
      `fix_commit`: record → edit(allow) → sibling `fix_commit` → edit(**allow**).
      Evidence: ___
- [ ] **V5** (1) The gate still bites: an actor with **no** evidence is denied after
      a sibling's transition. A window fix that allows everyone is worse than the
      bug. Evidence: ___
- [ ] **V6 · non-vacuity** Restore the global watermark → V1 goes red for **both**
      actors. Restore `last_transition` → V4 goes red while V5 stays green.
      Evidence: ___
- [ ] **V7** If 4b was taken: `bin/.sahjhan-version`, `_resolve.SAHJHAN_VERSION` and
      `bin/sahjhan --version` agree; `check_sahjhan_pin.py` → exit 0. Evidence: ___

---

## W05 — Item 2: fixing more than half your MEDIUMs strands `converge` forever

**Status:** `TODO`  ·  **Tier:** A  ·  **PROVEN**  ·  **D-a RULED**
**Commit:** `fix(enforcement): converge no longer requires the MEDIUM budget be spent`

### Defect · `protocol.toml:259` + `transitions.toml:553`

`converge` requires `medium_deferral_budget expect="false"` — the budget **spent**.
The denominator counts every MEDIUM ever filed, open or closed; `defer_medium`
requires `item_open`. Measured against a real daemon:

- **Exact, not a floor.** `defer_medium`'s gate is `deferred < N/2`, `converge`'s
  is `deferred >= N/2`, same integer division → converging requires **exactly
  `floor(N/2)` deferrals**.
- **Vacuous at N=1, binding from N=2.** N=1 reads `false` (passes, `1/2 = 0`);
  N=2..6 with zero deferrals all read `true` (blocked).
- **The budget must be spent *before* the MEDIUMs are fixed.** Observed at N=6:
  5 resolved, 1 deferred, `open_medium_findings` = `[]`, budget still `true`. The
  run must decide to defer half its MEDIUMs when it is least able to judge which
  half deserve it — and no skill file says so.
- **A late MEDIUM re-blocks an open converge.** N=6 with 3 deferred is spent; file
  a 7th and 8th and it is unspent again.

The only exit is filing new MEDIUM findings in order to defer them — a block whose
escape is not guaranteed by construction, arriving at the end of the run.

### RULED (Jon, 2026-08-27) — D-a: drop the conjunct from `converge`

**The reasoning, recorded so the deletion is not later read as a weakening.** The
predicate has three consumers and two of them are correct:

| Consumer | Expect | Verdict |
|---|---|---|
| `defer_medium` (`transitions.toml:268`) | `true` | **Correct** — a cap. You may defer only while under half |
| `pattern_done` breaker (`:415`) | `false` | **Correct and load-bearing.** The comment at `:405-410` explains it: the breaker's escape must be achievable by construction, and "no open MEDIUM" cannot be achieved because the cap forbids deferring them all — so the predicate is phrased as *budget-spent*, which cannot be refused (D2) |
| **`converge` (`:553`)** | `false` | **Wrong seat.** Converge is a standing precondition, not a block needing a reachable escape. The escape-post-state form was copied here, where its reasoning does not hold — so a run that fixes all its MEDIUMs can never converge |

The intent string on `:553` argues against itself — *"the MEDIUM deferral budget
must be spent — half the MEDIUMs get fixed, not deferred"* — and the second clause
describes the **cap**, which is the other seat. That contradiction is item 11's
entry for this gate, and it is resolved by the deletion rather than by a rewrite.

### Plan

- [ ] **1.** Delete the `medium_deferral_budget` conjunct from `converge`
      (`transitions.toml:553`), including its self-contradictory `intent`
- [ ] **2.** Leave `protocol.toml:259`'s query **unchanged** — its own intent
      ("MEDIUM deferrals must not exceed 50% of total MEDIUM findings") is accurate
      for the two seats that remain
- [ ] **3.** Leave `defer_medium` (`:268`) and the breaker seats (`:415`, `:458`)
      untouched. Confirm by diff that this commit touches exactly one line of gate
      config
- [ ] **4.** Close item 11's `medium_deferral_budget` row against this unit — note
      it in W25 so the escape-audit there does not go looking for a gate that no
      longer exists

### Validation

- [ ] **V1 · the strand, which is the acceptance criterion** N=6, 5 resolved, 1
      deferred, `open_medium_findings` = `[]` → **converge passes**. Observed as
      blocked today. Evidence: before ___ after ___
- [ ] **V2 · the virtuous run** N=6, **6 resolved, 0 deferred** → converge passes.
      This is the case the old gate made unreachable and the reason for the ruling.
      Evidence: ___
- [ ] **V3 · whole domain of N** Parametrised real_daemon over N = 0, 1, 2, 6 with
      zero deferrals → converge passes at every N. The old gate was vacuous at N=1
      and binding from N=2; after the ruling there is no N-dependence left to get
      wrong. Evidence: ___
- [ ] **V4 · late refile no longer re-blocks** N=6 converged, file MEDIUMs 7 and 8
      → converge still passes. Evidence: ___
- [ ] **V5 · the cap still holds** `defer_medium` still refuses the deferral that
      would exceed 50%. **Deleting the converge seat must not weaken the cap** —
      this is the check that distinguishes the ruling from a blanket removal.
      Evidence: ___
- [ ] **V6 · the breaker still holds** `pattern_done`'s `any_of` still opens on
      budget-spent, and its printed escape still clears it. Drive the named command.
      Evidence: ___
- [ ] **V7 · non-vacuity** Restore the conjunct → V1 and V2 go red while V5 and V6
      stay green. Evidence: ___
- [ ] **V8** `enforcement_lint` H1 — the query still has consumers, so it must not
      report an orphan. Evidence: ___

---

## W06 — Item 20: every merged finding belongs to no lens

**Status:** `TODO`  ·  **Tier:** B — *pulled into P1 because it blocks W07*  ·  **D-d RULED**
**Commit:** `fix(merge): require a stated perspective and carry it through the merge`

⚠️ **Coordinate with W09 — the division of labour, so neither unit guesses.**
D-d and item 26 both add a required-field check to `validate_punchlist.py` and
both teach a field in `justine-skill.md`. Two hand-rolled checks in the same file
is how the pair drifts, so the mechanism is built once — **here**:

| | Builds | Consumes |
|---|---|---|
| **W06** (this unit, P1) | the required-field mechanism **and** its `perspective` use | — |
| **W09** step 3 (P2) | — | the same mechanism, for `reachability` |

W09 keeps its own **V6**; it is asserting a different field's behaviour, not
re-testing the mechanism. If W09 finds itself writing a second checking
mechanism, W06 under-built — go back and widen it rather than adding one.

### Defect · verified against a real daemon

`merge_punchlists.py:108,363` default `perspective` to `"unspecified"`, which is
**not** among `[sets.perspective]`'s 13 values. Confirmed two ways by the third
pass, and the second is what makes it worse than stated:

- `[sets.perspective]` holds 13 values; `unspecified` is not among them.
- `sahjhan event finding --field perspective=unspecified` **exits 0.**

So the set is decorative for this field — declaring a set does not validate events
written against it. It is not only that no lens gate will name `unspecified`; it
is that **nothing anywhere refuses it**, and any misspelled perspective has the
same effect. The merge writes one on every Justine finding by default.

Under W07's ruled lens-scoped package, a merged CRITICAL is caught **only** at
`converge`, run-wide, at the end — on the audited run, a large slice of the board
arriving as a surprise at the last gate.

### RULED (Jon, 2026-08-27) — D-d: require Justine to state the perspective

Merged findings are attributed to a real lens, stated by Justine rather than
inferred. This is what makes W07's lens-scoped gate safe: every finding on the
board belongs to a lens that will ask about it.

### Plan

- [ ] **1.** `validate_punchlist.py` errors on a missing `**Perspective:**`, using
      the same required-field mechanism W09 builds for `reachability`
- [ ] **2.** ⚠️ **Validate membership, not just presence.** A presence-only check
      lets `unspecified` and every typo straight through — which is the whole
      defect. Read the 13 values **from `[sets.perspective]`**, do not restate them
      in the validator; one named source, so the two cannot drift
- [ ] **3.** `justine-skill.md` teaches the field and enumerates the lenses,
      alongside the `reachability` line W09 adds
- [ ] **4.** `merge_punchlists.py:108,363` carries the stated value.
      `DEFAULT_PERSPECTIVE`/`"unspecified"` stays as a code-level fallback but
      becomes **unreachable in practice** — assert that, rather than deleting it
      and losing the fail-safe
- [ ] **5.** Record in `merge-protocol.md` that merged findings are lens-attributed
      and therefore lens-gated

### Validation

- [ ] **V1** `validate_punchlist.py` on an item with no `**Perspective:**` →
      non-zero exit naming the field. Evidence: ___
- [ ] **V2** ⭐ **Membership, not presence.** An item stating
      `**Perspective:** unspecified` → **rejected**. An item stating a misspelled
      lens (`concurency`) → **rejected**. A presence-only check passes both, and
      would ship the bug under a green test. Evidence: ___
- [ ] **V3** The validator's lens list is **read from `[sets.perspective]`** —
      mutate the set, and the validator's accepted values follow without a code
      edit. Evidence: ___
- [ ] **V4** A merged finding lands carrying Justine's stated perspective, and its
      lens gate names it. Drive it through W07's gate, not just the merge.
      Evidence: ___
- [ ] **V5** The `unspecified` default is unreachable via the validated path —
      assert it, keeping the fallback as a fail-safe. Evidence: ___
- [ ] **V6** A test asserting **every value the merge can write is a set member** —
      enumerate the field's domain in a test, not in a paragraph. Evidence: ___
- [ ] **V7 · non-vacuity** Revert step 2 to presence-only → V2 goes red (both
      halves). Revert step 4 → V4 goes red. Evidence: ___
- [ ] **V8 · rider, independent of this ruling** Decide whether the daemon should
      refuse a non-member value for a set-typed field. Today it does not
      (`sahjhan event finding --field perspective=unspecified` exits 0), which
      makes this defect class silent everywhere, not just here. If that is a
      sahjhan change, file it; if accepted, record it. Evidence: ___

---

## W07 — Item 3: `all_findings_closed` still gates lens completion, thirteen times

**Status:** `TODO`  ·  **Tier:** A  ·  **PROVEN**  ·  **D-d RULED — unblocked, W06 first**
**Commit:** `fix(enforcement): scope lens completion to the lens`

### Defect · `transitions.toml:472`

P0.1 removed `all_findings_closed == 0` from `converge` because it was unreachable
and would make the four conjuncts decoration —
`test_all_findings_closed_no_longer_gates_converge` asserts that. **The identical
named query still sits on `set complete perspective`**, which must pass **13
times** before `converge` is ever evaluated. The unreachable requirement was not
removed; it was moved one door upstream and multiplied by thirteen.

Two more consequences:
- No reachability filter, so **one open `fault_injected` HIGH reads `1` and blocks
  the lens**. That finding cannot be `fix_commit`'d (`item_is_user_reachable`
  refuses it) and the hardening batch is taught only at Step 15 — after all 13
  lenses.
- **No `intent` string at all**, so the block prints no escape.

### Ruling · Jon, 2026-08-26 — option (a), the lens-scoped package

`set complete perspective` requires every CRITICAL and every `user_reachable` HIGH
**whose finding carries `perspective = {{current_perspective}}`** to be
resolved-or-deferred. Not the whole board. Lens 3 blocks on its own open
CRITICALs; it ignores lens 1's open MEDIUMs — and lens 1's open CRITICALs, which
`converge` catches run-wide. **A clean lens is not an empty board.** Clearing the
board is what made convergence take weeks — it is the disease, not the cure.

**Accepted cost, stated so it is not rediscovered as a bug:** a finding filed
under an already-completed lens is caught only at `converge`. That is the trade
that stops lens 7 being answerable for lens 2's board.

### Plan

- [ ] **0.** **Land W06 first.** D-d is ruled (Justine states the perspective), so
      every finding on the board now belongs to a lens that will ask about it —
      which is precisely the precondition this gate needs. Landing this before W06
      would move the whole merged board to `converge` silently
- [ ] **1.** Two new named queries in `protocol.toml [queries]`, both parameterised
      on `{{current_perspective}}` — the binding `set complete perspective` already
      uses for its `iteration_complete` and quiz gates, so the argument is in scope
- [ ] **2.** Shape them on `all_critical_resolved` / `all_user_reachable_high_closed`
      with one added `f.perspective = '…'` term and the **same max-seq
      correlation**, so severity and reachability stay graded by latest filing (D25)
- [ ] **3.** Delete `all_findings_closed` from this transition. It then has **no
      consumer in `transitions.toml`** — run `enforcement_lint` H1 and let it tell
      you whether to keep it declared for `findings.py`/render use or drop it
- [ ] **4.** Give the gate an `intent` naming a command. H8 note: these are
      parameterised, so `_run_wide()` drops them from escape identity — the intent
      still must name a command, it is just not judged against a named query

### Validation

- [ ] **V1** **Extend `TestEveryCriticalHasARoute` to this transition**, driven
      against a real daemon for **all three** reachability grades, as the
      `converge` version does. The invariant: no grade of finding may be
      un-closable at a gate the run must pass thirteen times. Evidence: ___
- [ ] **V2** Lens 3 blocks on its own open CRITICAL. Evidence: ___
- [ ] **V3** Lens 3 **passes** with lens 1's MEDIUM open — this is the ruling.
      Evidence: ___
- [ ] **V4** The accepted cost is asserted: a finding filed under a completed lens
      **is** caught by `converge`. Evidence: ___
- [ ] **V5** One open `fault_injected` HIGH no longer blocks a lens, and is still
      caught by `no_open_fault_injected` at `converge`. Evidence: ___
- [ ] **V6** The block prints an escape **and the escape runs**. Not "has an intent
      string" — run it. Evidence: ___
- [ ] **V7 · non-vacuity** Restore `all_findings_closed` → V3 and V5 go red.
      Evidence: ___

---
---

# P2 — before trusting results

These corrupt the run's record or weaken enforcement mid-run.

---

## W08 — Items 32 + 43: the pending-commit clear and the escape it prints

**Status:** `TODO`  ·  **Tier:** B  ·  **32 PROVEN**  ·  **Depends on:** W01 (F2)
**Commit:** `fix(enforcement): a refused transition discharges nothing, and the block names a reachable escape`

Land together: 32 is what makes 43's unreachable escape appear to "work," so
fixing 32 first turns 43 from a bad message into a hard block.

### Defect 32 · `protocol_tracker.py:217-222`

```python
if _runs_transition(cmd, "fix_commit"):
    cache["unregistered_commits"] = {}
```

`_runs_transition` is pure `cmd.split()` adjacency. `exit_code` is computed at
`:250` and used **only** in the git-commit branch; this path ignores it. Driven
against the mock daemon from `{"agent-a":["a1"],"agent-b":["b1"],"":["c1"]}`: a
`transition fix_commit` the engine **refuses** (exit 1), and even `echo remember to
run transition fix_commit`, both clear the whole map. Two defects stacked:

- **No success check** — a refused fix_commit discharges the block; the commit was
  never registered and the gate stops asking.
- **Run-global clear** — D41 keyed the *charge* per actor and left the *clear*
  global (`_protocol_cache.py:610-612` argues only the merged subagent's bucket).
  One `fix_commit` grants the other two in-flight subagents a free unregistered
  commit each. The deny-direction was fixed; the allow-direction — the one that
  loses enforcement — was not.

H7/H8 enforce exactly this shape five lines above for `pattern_analysis_overdue`.
`test_unregistered_commit_actor.py:164` asserts the global clear as intended and
never seeds three buckets, a failed transition, or a second commit.

### Defect 43 · `commit_gate.py:78-89`

The comment justifying actor-scoping ends *"the escape named below is the
orchestrator's transition, which a subagent cannot run"* — and the `exit_block`
immediately below prints exactly that escape. A subagent's second commit (the
item-23 rework path) lands here with an unreachable escape.

### Plan

- [ ] **1.** Gate the clear on success. `bash_exit_code(event)` is already in scope
      at `main()` — thread it into `_apply_sahjhan_cmd` and clear only on exit 0
- [ ] **2.** Decide the clear's scope **from the ledger, not the cache**. Ask
      sahjhan which commit the transition registered and clear the bucket holding
      it. If the ledger cannot answer, clear the orchestrator's bucket only —
      losing a clear costs a nudge, losing the charge loses the gate
- [ ] **3.** Rewrite `_protocol_cache.py:610-612`'s comment to match what step 2
      lands. Today it argues a position the code does not implement
- [ ] **4.** (43) Print an escape the blocked actor can run
- [ ] **5.** (43) **If no such route exists, that is a missing escape and a
      question for Jon** — not a licence to narrow the block. Say so explicitly
      rather than shipping a better-worded dead end
- [ ] **6.** `bash scripts/hash-trusted-callers.sh`

### Validation

- [ ] **V1** Seeded as driven: `{"agent-a":["a1"],"agent-b":["b1"],"":["c1"]}` —
      three buckets, three commits, so no count can coincide. Evidence: ___
- [ ] **V2** A `transition fix_commit` the engine **refuses** (exit 1) clears
      **nothing**. Evidence: ___
- [ ] **V3** `echo remember to run transition fix_commit` clears **nothing**.
      Evidence: ___
- [ ] **V4** A successful `fix_commit` clears the bucket it discharges and leaves
      the other two charged — **assert the survivors by name, not by `len()`**.
      Evidence: ___
- [ ] **V5** `test_unregistered_commit_actor.py:164` rewritten (not deleted) — it
      is the guard for step 2's new rule. Evidence: ___
- [ ] **V6** (43) A subagent's second commit is blocked, and the printed escape is
      then **executed as printed** and clears the block. Evidence: ___
- [ ] **V7** (43) The orchestrator's path is unchanged. Evidence: ___
- [ ] **V8 · non-vacuity** Remove the exit-code check → V2 red. Restore the global
      clear → V4 red. Revert 43 → V6's escape fails to clear. Evidence: ___
- [ ] **V9** `enforcement_lint` H8 → exit 0 (the block names the query its escape
      is gated on). Evidence: ___

---

## W09 — Items 25 + 26: the merge destroys the grading it routes on

**Status:** `TODO`  ·  **Tier:** B  ·  **both PROVEN**
**Commit:** `fix(merge): read the whole row, and require the grading that decides routing`

Land together — two ends of one pipeline.

### Defect 25 · `merge_punchlists.py:336-339` · **the only route needing no agent intent**

`_HOLTZ_SQL` reads Holtz's board with:

```sql
SELECT id, severity, category, location, perspective, description, seq
FROM events WHERE type='finding' ORDER BY seq
```

`reachability`, `pattern_id` and `predicted_by` are **not** in that list. So
`holtz_findings()` builds every `Finding` with `DEFAULT_REACHABILITY =
"theoretical"` (`:66`), and `apply_merge()` re-files the escalated finding with
that default.

**The re-file happens only on escalation.** The code path that exists to say *this
is worse than you thought* is the one path that destroys the finding. Driven
against a real daemon:

```
BEFORE   BH-001  HIGH      user_reachable
AFTER    seq 2   BH-001  CRITICAL  theoretical      <-- the re-file
open_theoretical_findings        -> BH-001
theoretical_courier              -> exit 0
finding_deferred                 -> BH-001, reason=theoretical
all_critical_resolved (after)    -> true
```

Four consequences: D25 grades by latest filing, so the board now says
`theoretical`; `theoretical_courier` matches `merge_punchlists.py` by name and
sweeps it in the same Bash call; `all_critical_resolved` reads `true` — a
**fourth** route to closing a CRITICAL with no fix; and `fix_commit` can no longer
touch it, because `item_is_user_reachable` refuses a `theoretical` finding.

Two more fields go the same way: **`pattern_id`** is dropped, so an escalated
sibling leaves its round's population and the merge silently discharges round-cap
pressure; **`predicted_by`** is hard-coded to `"none"` in `_record` (`:401`), so
the finding loses the prediction link `SUMMARY.md`'s accuracy table is computed
from.

**The guard test asserts the one field that changed and none of the fields that
must not.** `test_a_higher_justine_severity_refiles_holtz_id`
(`tests/test_merge_punchlists.py:538`) asserts `len(filings) == 2` and
`severity == "HIGH"`, and never reads `reachability` off the second filing.

### Defect 26 · the other end

`justine_findings()` takes `item.reachability or DEFAULT_REACHABILITY`, so an
ungraded item becomes `theoretical` and is auto-deferred the moment it lands. The
field is required in exactly one place and not in the two that produce it:

| Where | Requires `reachability`? |
|---|---|
| `events.toml [events.finding]` | **yes** — *"a grading nobody has to state is a grading the board will not carry"* |
| `punchlist-format.md` | in the template; prose says "Assess for every finding" |
| `validate_punchlist.py` | **no** — errors on severity, category, status, Problem, Discovery Chain, acceptance criteria, validation command; never mentions reachability |
| `justine-skill.md` | **no** — the word does not appear in the file |

The default is defensible in isolation, but it stops being a grading and becomes
an eraser once D29 auto-defers on it.

### Plan

- [ ] **1.** (25) Add `reachability`, `pattern_id`, `predicted_by` to `_HOLTZ_SQL`,
      carry them onto `Finding`, and have `_record` (`:401`) pass them through
- [ ] **2.** (25) Confine `DEFAULT_REACHABILITY` to where a grading was genuinely
      never stated — Justine's punchlist — never to a Holtz row that has one
- [ ] **3.** (26) `validate_punchlist.py` errors on a missing `**Reachability:**`,
      matching `events.toml`'s own claim about the field. ⚠️ **Use W06's
      required-field mechanism — do not write a second one.** W06 (P1) builds it
      and lands the `perspective` use; this step is its second consumer. If it
      does not fit, widen W06's rather than hand-rolling here
- [ ] **4.** (26) `justine-skill.md` says the word once, next to its
      severity-calibration override

### Validation

- [ ] **V1** Rewrite `test_merge_punchlists.py:538` to assert a re-file changes
      `severity` and **nothing else** — compare the two filings field by field.
      Evidence: ___
- [ ] **V2** After the fix: `seq 2  BH-001  CRITICAL  user_reachable` — not
      `theoretical`. Evidence: ___
- [ ] **V3** `open_theoretical_findings` does **not** name BH-001;
      `all_critical_resolved` reads **false**; no `finding_deferred` is emitted.
      Evidence: ___
- [ ] **V4** `pattern_id` survives, so the escalated sibling stays in its round's
      population. Evidence: ___
- [ ] **V5** `predicted_by` survives. Evidence: ___
- [ ] **V6** (26) `validate_punchlist.py` on an item with no `**Reachability:**` →
      non-zero exit naming the field. Evidence: ___
- [ ] **V7** (26) The shipped fixture reproduces the bug — `_JUSTINE`'s BJ-002
      carries no reachability, so it must now fail validation. **That fixture edit
      is the proof; record it in the commit message** rather than quietly fixing it.
      Evidence: ___
- [ ] **V8** (26) Keep `test_an_unstated_reachability_is_theoretical` as a unit test
      of the *default*, and add a pipeline test that an ungraded item never reaches
      the merge. Evidence: ___
- [ ] **V9 · non-vacuity** Revert `_HOLTZ_SQL` → V1–V5 red. Remove the validator
      check → V6 red. Evidence: ___

---

## W10 — Item 35: `stale_sweep`'s population window is a run-global watermark

**Status:** `TODO`  ·  **Tier:** B  ·  **Depends on:** W01 (F2)
**Commit:** `fix(enforcement): scope the sweep window to the sweep`

### Defect · `stale_sweep.py:69-80`

`_POPULATION_SQL` scopes "this sweep" to `seq > MAX(seq of any state_transition)`.
The docstring calls that *"the same window `defer_cant_reproduce`'s own gate
uses"* — true, and both are run-global. In a three-wide loop the orchestrator
records a `fix_commit` transition every time a subagent lands, so **a sibling
landing mid-sweep advances the watermark past retirements already recorded**:
`check` reports "verdicts name findings this sweep does not cover," the courier
warns, and nothing is recorded. Both the script and the courier's re-derivation
(`stale_sweep_courier.py:126`) read the same window, so the courier cannot rescue
it. This is D41 / item 1 a third time, in a courier.

### Plan

- [ ] **1.** Scope the window to the sweep, not the run — define its start as the
      sweep's own first recorded event, so a sibling's `fix_commit` cannot move it
- [ ] **2.** Script and courier read **one** named window, imported not restated —
      the discipline both files already claim in their comments
- [ ] **3.** Fix the docstring's "same window as `defer_cant_reproduce`" claim, or
      make it true by moving that gate to the same named window. Do not leave the
      comment asserting a correspondence the code no longer has

### Validation

- [ ] **V1** A sweep retires findings, a sibling `fix_commit` lands mid-sweep, then
      `--record`: retirements still covered, sweep records. Today the courier warns
      and writes nothing. Evidence: ___
- [ ] **V2 · the non-adjacent case** The sibling's transition sits **between** two
      of the sweep's own retirements, not after both. A window bug that only shows
      up when the interleaving is adjacent is the "a SQL LIMIT is not a window"
      trap — write the seq floor and test this explicitly. Evidence: ___
- [ ] **V3** Courier and script resolve the same population for the same ledger —
      by construction (same named query) and by test. Evidence: ___
- [ ] **V4 · non-vacuity** Restore the run-global watermark → V1 and V2 go red.
      Evidence: ___

---

## W11 — Item 42: per-actor cache state is read-modify-written over the whole map

**Status:** `TODO`  ·  **Tier:** B  ·  **Depends on:** W01 (F2)
**Commit:** `fix(enforcement): write the actor's own bucket, not the whole map`

### Defect · `protocol_tracker.py`

Both writers send the **entire** actor map computed from a snapshot read up to
~10 s earlier: `update_cache` with `stall_bumped` (`:295-297`), and
`_apply_sahjhan_cmd`'s full `write_cache` (`:235`) after two 5 s subprocesses. The
daemon does a shallow top-level merge, so a sibling's bump/clear/commit landing in
that window is **overwritten** — the actor-keying the delta added is not atomic.
The docstrings claim "every other actor untouched," true of the returned value and
false of the write. No compare-and-swap and no concurrency test exist.

### Plan

- [ ] **1.** Make the write per-actor: send the delta for one actor and let the
      daemon merge, instead of computing the full map client-side and overwriting
- [ ] **2.** If the daemon's op cannot express a per-actor merge, **that is a
      sahjhan change** — take it there rather than adding a client-side
      compare-and-swap that would still race
- [ ] **3.** Correct the two docstrings to describe the write, not the return value

### Validation

- [ ] **V1** Interleave: A reads → B bumps and writes → A writes. **B's bump
      survives.** Evidence: ___
- [ ] **V2** Same for all three colliding writers: `stall_bumped`, `stall_cleared`,
      `pending_commits_appended`. Evidence: ___
- [ ] **V3** Fixture counts chosen so "buckets" and "commits" differ — a `len()`
      over the wrong dimension must not pass by coincidence. Evidence: ___
- [ ] **V4 · non-vacuity** Restore the whole-map write → V1 goes red. Evidence: ___
- [ ] **V5** If step 2's engine path was taken: re-pin, `check_sahjhan_pin.py` →
      exit 0. Evidence: ___

---

## W12 — Items 34 + 28: couriers go silent when a CLI accepts what its recognizer refuses

**Status:** `TODO`  ·  **Tier:** B
**Commit:** `fix(enforcement): each script's parser refuses exactly what its courier refuses`

### Defect · at least four scripts

| Script | Gap | Consequence |
|---|---|---|
| `hardening_batch.py:359` | accepts `--cwd`; `module_of_command` rejects it (verified: `--cwd .` → `None`, bare → `'tqdm'`) | courier `exit_ok()` with **no warning** while the module's `fault_injected` findings stay open and `no_open_fault_injected` blocks `converge` at Step 15 |
| `tdd_courier.py:76-80` | requires a **single** shell segment, exits silently otherwise (`:90`) — and unlike `verify_suite`/`pattern_round`/`stale_sweep` at `:69/:150/:174`, `phase-fix-loop.md:52` carries **no** "run it alone" warning | a subagent chaining `pytest …; sahjhan event test_failed_before_fix …` records nothing — and that silence sits **before** item 19's mis-attribution |
| all four recognizers | accept only `python\|python3\|py` (`verify_suite.py:342 _INTERPRETERS`) | `poetry run python …` / `uv run …` / `python3.12 …` record nothing — shapes `phase-fix-loop.md:230` explicitly invites via `HOLTZ_PYTEST` |
| `stale_sweep.py` (item 28) | `main` (`:276`) accepts `--record` with `--present` and/or `--retired`; `verdicts_of` (`:205`) returns `None` unless `--present` | passes `check()`, prints `STALE-SWEEP:`, exits 0 — and the courier records **nothing, with no warning**, while every other failure on that path warns |

`pattern_round.py --record --siblings-found N --cwd X` has the identical shape.

### Plan

- [ ] **1.** Each script's argument parser refuses exactly what its courier
      refuses: `--present` required with `--record`; `--cwd` dropped from the
      recorded form (or taught to the recognizer — pick one, read it from one place)
- [ ] **2.** Every courier `exit_warn`s on the `None` path instead of `exit_ok`
- [ ] **3.** Widen `_INTERPRETERS` to cover the invited shapes, **or** make the
      taught command the only supported spelling and say so where `HOLTZ_PYTEST` is
      introduced. Do not leave `phase-fix-loop.md:230` inviting a shape that
      silently records nothing
- [ ] **4.** Add the "run it alone" warning to `phase-fix-loop.md:52`, matching
      `:69/:150/:174`

### Validation

- [ ] **V1** For each of the four: a command the CLI accepts but the recognizer
      refuses now **fails at the CLI** (non-zero, with a message) rather than
      exiting 0 and recording nothing. Evidence: ___
- [ ] **V2** A courier reaching its `None` path emits a warning that reaches the
      transcript. **Silence is the defect**, so a test that only checks "nothing
      recorded" reproduces the bug rather than catching it. Evidence: ___
- [ ] **V3** `poetry run python …/verify_suite.py --record --scope full` either
      records or fails loudly — assert which the ruling chose. Both are acceptable;
      silence is not. Evidence: ___
- [ ] **V4** Add the chained form (`pytest …; sahjhan event …`) to the
      combinatorial matrix in `test_contract_commands.py`. Evidence: ___
- [ ] **V5 · non-vacuity** Restore one recognizer's narrow form → V1 goes red.
      Evidence: ___

---

## W13 — Items 37 + 17: the primer's silent degrade and the ordering that hides daemon death

**Status:** `TODO`  ·  **Tier:** B
**Commit:** `fix(enforcement): check daemon death before status, and say so when degraded`

### Defect · `primer.py`

Three fail-open paths, not one:

| Line | Path | Covered by item 17's proposed fix? |
|---|---|---|
| `:117-118` | `TimeoutExpired` → `exit_ok()` | yes |
| `:120-121` | any non-zero `status` exit (corrupt ledger, config error) → `exit_ok()` | **no** |
| `:101-102` | `_recently_failed` marker suppresses the binary for an hour → `exit_ok()` | **no** |

`exit_ok()` emits **no `additionalContext` at all**, and the primer is the hook
whose entire job is re-injecting state after a `/clear` — the
`awaiting_clear → resume` design depends on it.

**The aggravating fact is the ordering:** the daemon-death check (`:147-150`) and
the enforcement-health probe (`:152-153`) sit **after** the status subprocess, so a
slow or failing `status` skips the terminated-marker write and `auth_failed`
detection entirely. The hook whose job is reporting daemon death stays silent when
the daemon dies during a slow status.

**Item 17's flake:** one `pytest -q` run under concurrent load produced 2 failures
— `TestPrimerWithMockBinary::test_injects_lens_priming_in_audit` and
`::test_warns_when_context_reset_fails`, both `assert '<state>' in ''`. The class
passes in isolation and two sequential `-p no:randomly` runs passed. The tree is
not broken; the gate is not reliably green under load.

### Plan

- [ ] **1.** Move the death check (`_read_init_pid` / `_is_process_alive` /
      `_write_terminated_marker`) and the health probe **before** the status
      subprocess. Death detection must not depend on a call that can hang
- [ ] **2.** Inject a short degraded-mode notice on **all three** degrade paths.
      "Nothing to say" and "I could not find out" must not look identical
- [ ] **3.** Close item 17 against this unit. Note in `CHANGELOG` that the timeout
      predates this delta and is not a regression from it
- [ ] **4.** `bash scripts/hash-trusted-callers.sh` — `primer.py` is manifest-listed

### Validation

- [ ] **V1** Each of the three degrade paths emits `additionalContext` containing a
      degraded-mode marker — **three separate tests**. Evidence: ___
- [ ] **V2** Daemon dies during a slow status → the terminated marker is **still
      written**. This is the ordering fix and the reason 37 outranks 17.
      Evidence: ___
- [ ] **V3** The flake resolves *for the right reason*: the assertion now has
      something to match. Run the class under concurrent load **three times
      unchanged**, not once. Evidence: run1 ___ run2 ___ run3 ___
- [ ] **V4 · non-vacuity** Restore the ordering → V2 goes red. Evidence: ___

---

## W14 — Items 5 + 10: the breaker's second seat, and the conjunct that reads the same predicate

**Status:** `TODO`  ·  **Tier:** B  ·  **10 PROVEN**
**Commit:** `fix(enforcement): put the amplification breaker on the path the docs teach`

### Defect 5 · `transitions.toml:411`

P0.1 is the spec's highest-value item ("the difference between terminating and
not"). Its block is on `pattern_done`, reachable **only** from
`pattern_analysis`. But `phase-fix-loop.md:101` teaches:

> - **Stay in `fix_loop`** (usual). Do steps 1-5…
> - **Enter `pattern_analysis`**, when `iteration_boundary` blocks you…

On the usual path `pattern_done` never runs, so the breaker never evaluates and the
mandatory batch deferral is never triggered — and per D3, `pattern_done`'s escape
is *the only place deferral is taught*. The round cap was given a second seat on
`iteration_boundary` for precisely this reason; the breaker was not.

**RULED (Jon, 2026-08-26): the breaker gets a second seat too.**

### Defect 10 · the two converge conjuncts pull against each other

PROVEN: 3 findings filed in-loop, 3 deferred, board empty → `amplification_diverging`
still `true`, because deferrals are not counted on the resolved side. So the
breaker's prescribed escape (`defer batch`) moves the `pattern_done` block and
**not** the `converge` conjunct that reads the same predicate. Converge's
amplification gate names no escape at all.

### Plan

- [ ] **1.** (5) Put the same `any_of` on `iteration_boundary`, referencing the
      **same named queries** so the two seats cannot drift — the arrangement
      `round_item_cap_exceeded` already has
- [ ] **2.** (5) Confirm the escape is reachable from `fix_loop`: `defer_low`/
      `defer_medium` are declared `fix_loop → fix_loop`, so `sahjhan defer batch`
      works there. No new transition edges needed
- [ ] **3.** (5) Both seats reference `medium_deferral_budget` and `open_low_count`
      **by name** — H8 checks that a block names the query its escape is gated on,
      and the escape now has two block sites
- [ ] **4.** (10) Count deferrals on the resolved side of `amplification_diverging`
- [ ] **5.** (10) Give the `converge` seat an `intent` naming a command (also item 11)

### Validation

- [ ] **V1** The breaker fires on the **taught** path: drive a diverging run that
      stays in `fix_loop` and never enters `pattern_analysis`; `iteration_boundary`
      blocks. A test that enters `pattern_analysis` reproduces the old passing
      state. Evidence: ___
- [ ] **V2** Drive the printed escape → the block clears **at both seats**.
      Evidence: ___
- [ ] **V3** (10) 3 filed, 3 deferred, board empty → `amplification_diverging` reads
      **false**. Evidence: ___
- [ ] **V4** (10) One escape, two sites, one outcome: `defer batch` moves **both**
      the `pattern_done` block and the `converge` conjunct. Evidence: ___
- [ ] **V5** **The breaker measures what its title says.** A *converging* run must
      not trip it. P0.1 shipped once as a detector carrying zero information about
      the thing it was named for — assert the two runs read differently.
      Evidence: ___
- [ ] **V6** `enforcement_lint` H7/H8 → exit 0. Evidence: ___
- [ ] **V7 · non-vacuity** Remove the second seat → V1 red. Revert 10 → V3 red.
      Evidence: ___

---
---

# P3 — before release

Integrity and bypass. A good-faith test will not trigger these; a motivated agent
will.

---

## W15 — Item 30: a single `&`, and `eval`/`$VAR` indirection, bypass every command-keyed guard

**Status:** `TODO`  ·  **Tier:** C  ·  **PROVEN**
**Commit:** `fix(enforcement): one segmentation owner, splitting on & and on the resolved command`

### Defect · eight call sites, not four

Every command-keyed guard splits on an operator set that **omits a single `&`**.
Bash's `&` is a separator, so `A & B` is one segment whose first token is `A`, and
every first-token guard inspects the wrong command.

⚠️ **The punchlist named four sites; the tree has eight, and the extra four
include two live guards.** Enumerated at `48c72fd` — note also that the eight
carry **two different literals**, which is why a grep for one of them reads clean:

The two literals, spelled out once here so the greps below are unambiguous:

- **padded** — `\s*(?:` *ops* `)\s*`, a non-capturing group with `\s*` either side
- **bare** — the same *ops* alternation with no group and no padding

| Site | Literal | Named by the review? |
|---|---|---|
| `_sahjhan_bootstrap.py:416` | padded | yes |
| `_sahjhan_bootstrap.py:668` | padded | yes |
| `_protocol_cache.py:292` | bare | yes |
| `commit_gate.py:46` | bare | yes |
| **`_daemon_lifecycle.py:67`** | bare | **no — allowlist bypass, below** |
| **`protocol_tracker.py:67`** (`_is_sleep_cmd`) | bare | **no — anti-gaming guard** |
| **`protocol_tracker.py:52`** (`_is_tdd_cmd`) | bare | **no — silent non-record** |
| **`_sahjhan_bootstrap.py:1128`** | padded | **no — missed download only** |

**`_daemon_lifecycle.py` is the worst of the four.** Its docstring says *"A single
chained segment that does anything else converts the whole command into 'arbitrary
work disguised as recovery' and is denied"* — but `_DAEMON_RECOVERY_RE`'s trailing
`(?:\s+\S+)*\s*\Z` swallows the rest of an unsplit segment as ordinary arguments.
Driven:

```
 True  sahjhan daemon start
False  sahjhan daemon start && rm -rf x     <- correctly refused
 True  sahjhan daemon start &  rm -rf x     <- classified as pure daemon recovery
```

This hook is registered under the `Bash|Write|Edit|NotebookEdit` matcher, so the
allowlist is live for every Bash call. `_is_sleep_cmd` goes the same way:
`true & sleep 600` is not detected, defeating the guard against gaming timing
gates. **Tier is unchanged — C is still right**, because both still require an
agent to deliberately type `&`, which is P3's definition and not P1's. What grew
is the site count, and step 1's single-owner fix already covers all eight.

Driven live through the real hook subprocess, on the originally-named sites:

```
deny   sahjhan reseal --proof X
allow  true & sahjhan reseal --proof X
deny   sahjhan event quiz_exhausted_resolved --field project=holtz
allow  true & sahjhan event quiz_exhausted_resolved --field project=holtz
allow  true & rm -rf enforcement/hooks
```

One character reaches `reseal`/`sign`/`vault read`, the human-only
`quiz_exhausted_resolved` channel, the fix-loop commit gate, `is_git_commit` (so
the commit is invisible to both the gate and `protocol_tracker`), and **the
self-protection guard on `enforcement/hooks/`** — the file whose own docstring is
"DO NOT MODIFY. This hook protects itself." This is the `!` incident's class
(#81), past the token that fix named.

**Second face, same file:** `_check_bash_write` (`:668`) parses the **raw**
command while the sahjhan guard (`:416`) parses `resolve_indirection(...)`, so
`eval "rm -rf enforcement/hooks"` and `T=docs/holtz/.sahjhan; rm -rf $T` slip past
the protected-path guard the indirection module claims to own.

`_protocol_cache.py:289-292`'s comment argues for the hole and for single
ownership in the same breath: *"Use specific multi-char operators first to avoid
splitting on single &"* … *"Must match `_sahjhan_bootstrap.py`'s split pattern to
avoid divergence."*

### Plan

- [ ] **1.** **One owner for segmentation**, in `_shell_norm.py` beside
      `resolve_indirection` — the module whose docstring already claims this
      ownership ("Two hooks answering 'is this sahjhan?' from two parsers is
      PAT-001")
- [ ] **2.** Split on `&` too: `\s*(?:&&|\|\||[;&|\n])\s*`. `&&` precedes `&` in
      the alternation, so the two-character operator still wins
- [ ] **3.** ⚠️ **Hazard not named in the review, and it is load-bearing.** Adding
      `&` to the class breaks `2>&1`, which would split into `foo 2>` and `1`.
      `_protocol_cache.py:285-286` already strips fd-duplication and `/dev/null`
      redirects **before** splitting; the shared splitter must do the strip
      **first**, and the other three call sites must adopt that order
- [ ] **3b.** ⚠️ **Convert all eight sites, not the four the review named.** The
      table above is the checklist. `_daemon_lifecycle.py:67` and
      `protocol_tracker.py:67` are guards and go first; `protocol_tracker.py:52`
      and `_sahjhan_bootstrap.py:1128` lose signal rather than open a hole
- [ ] **4.** Every guard parses `resolve_indirection(cmd)` — including
      `_check_bash_write`, which today parses the raw string
- [ ] **5.** Rebuild the command-keyed branches to scan the **whole segment**, the
      way the surviving redirect/`tee` branches already do
- [ ] **6.** `bash scripts/hash-trusted-callers.sh`. **The expanded scope adds
      `protocol_tracker.py`, which _is_ manifest-listed** (verified: 18 entries,
      `commit_gate.py` and `protocol_tracker.py` among them;
      `_daemon_lifecycle.py`, `_protocol_cache.py`, `_sahjhan_bootstrap.py` and
      `_shell_norm.py` are not). Regenerate **before** any `real_daemon` run, or a
      RED is a stale-hash artifact rather than the thing under test

### Validation

- [ ] **V1** The five driven lines become the regression fixture:
      ```
      deny   sahjhan reseal --proof X
      deny   true & sahjhan reseal --proof X                (was: allow)
      deny   true & sahjhan event quiz_exhausted_resolved …
      deny   true & rm -rf enforcement/hooks                (was: allow)
      ```
      Evidence: ___
- [ ] **V2** `eval "rm -rf enforcement/hooks"` and `T=docs/holtz/.sahjhan; rm -rf $T`
      are denied. Evidence: ___
- [ ] **V3** `is_git_commit` sees `true & git commit` — visible to both the gate and
      `protocol_tracker`. Evidence: ___
- [ ] **V4** **Add `&` as a separator to the combinatorial matrix in
      `test_contract_commands.py`.** It carries `&` today only as a trailing
      suffix, never as a separator — which is exactly why this survived.
      Evidence: ___
- [ ] **V5** `foo 2>&1 & bar` splits into two segments; `foo 2>&1` alone stays one.
      Evidence: ___
- [ ] **V6** ⚠️ **Grep for the _construct_, not for a literal.** There are **two**
      literals in the tree (`\s*(?:…)\s*` and the bare form), so a grep for one
      reads zero while four sites survive — which is how this stayed at four sites.
      The check is: **zero `re.split` calls containing `&&` outside
      `_shell_norm.py`**. Evidence: ___
- [ ] **V6b** `sahjhan daemon start & rm -rf x` is **not** classified as daemon
      recovery, and `true & sleep 600` **is** detected as a long sleep. These are
      the two unnamed guards; without them V1–V3 can all pass with the allowlist
      still open. Evidence: ___
- [ ] **V7 · non-vacuity** Revert the character class → V1–V3 **and V6b** go red.
      Evidence: ___

---

## W16 — Item 18: any CRITICAL can be closed with `reason=theoretical`

**Status:** `TODO`  ·  **Tier:** C  ·  **PROVEN**  ·  **Depends on:** W09
**Commit:** `fix(enforcement): give the theoretical deferral provenance and a reachability correlation`

Sequence after W09 — both end in an unearned `finding_deferred` carrying
`reason=theoretical`, and 25 tells you what the provenance field must survive.

### Defect · `protocol.toml:410-425`

The config justifies the one exclusion in `all_critical_resolved` like this:

> `theoretical` is written by `theoretical_courier.py`, **not chosen by the
> agent** … Every other reason word still refuses.

But `finding_deferred` is `attestation = "agent"`, carries no `restricted = true`,
declares `agent:cli` as a producer, and its `reason` pattern admits
`^(cant_reproduce|low_priority|medium_budget|theoretical)$`. `event` is on the
bootstrap allowlist and `finding_deferred` is not in `BLOCKED_SAHJHAN_SUBSUB`.
Driven against a real daemon:

```
event finding … id=BH-001 severity=CRITICAL reachability=user_reachable
  all_critical_resolved -> false
event finding_deferred … id=BH-001 reason=theoretical      exit 0
  all_critical_resolved -> true
```

A CRITICAL the run **filed as `user_reachable`** is closed by one agent-typed
word, with no fix, no re-grade, and no courier involved.

**The guard tests demonstrate the hole and call it correct.**
`test_fix_loop_eligibility.py:190` and `test_theoretical_defer.py:272` both close
the CRITICAL through `_Board.defer` — literally the forged path — with docstrings
saying "machine-written" while their bodies type it by hand.

### Plan

- [ ] **1. Provenance.** Either `restricted = true` on the courier's path with a
      separate agent-writable spelling, or a provenance field on `finding_deferred`
      that only `record_authed_event` can set — with the conjunct filtering on
      **that**. `context_reset`'s `trigger='session_start'` (`restricted` + `host` +
      a hash-pinned writer) is the pattern done right and is the model to copy
- [ ] **2. Correlation.** The exclusion never checks that the finding it excuses is
      *graded* `theoretical`. Add the latest-filing correlation the other conjuncts
      carry:
      ```sql
      AND EXISTS (… f2.type='finding' AND f2.id=d.id
                  AND f2.reachability='theoretical'
                  AND f2.seq = MAX(seq for that id))
      ```

### Validation

- [ ] **V1** `event finding_deferred --field reason=theoretical` on a
      `user_reachable` CRITICAL → **refused**, or accepted and **not** excluded by
      `all_critical_resolved`. Assert which. Evidence: ___
- [ ] **V2** The courier's own path still works end to end — a genuinely theoretical
      finding is still auto-deferred and still excluded. **A provenance fix that
      breaks the courier trades #79 for #73.** Evidence: ___
- [ ] **V3** Rewrite both guard tests to drive the **courier**, not the CLI.
      Evidence: ___
- [ ] **V4** `test_an_ordinary_deferral_still_does_not_converge` proves only that
      the *other three* words refuse — add the fourth. Evidence: ___
- [ ] **V5** An internally contradictory board row — `user_reachable` CRITICAL
      carrying a `theoretical` deferral — is now noticed by something. Evidence: ___
- [ ] **V6 · non-vacuity** Revert each of the two fixes **separately**; a *distinct*
      test must go red for each. One test covering both means one is untested.
      Evidence: ___

---

## W17 — Item 22: no lint rule binds "a gate filters on this value" to "only a hook may write it"

**Status:** `TODO`  ·  **Tier:** C  ·  **Depends on:** W16
**Commit:** `feat(enforcement): H11 — a gate's literal must be reachable only by the path its prose claims`

Do this while 18 and 25 are fresh: it is the check that would have failed the
build, and it puts items 9 and 21 under machine audit rather than under the next
reviewer.

### Defect

Item 18 is a specific bug; this is why it shipped. `enforcement_lint.py` runs
H1–H10 (`:829`–`:1540`) and none asks item 18's question:

- **H5** asks whether an event claiming *above* `agent` attestation has an
  agent-writable path. `finding_deferred` claims `agent`, so H5 is silent.
- **H7/H8** govern predicate copies and escape identity, not who may write the
  values a predicate reads.
- **H10** binds a delegated gate's named `evidence` event to what the invoked tool
  queries — the right idea, one level up from the field.

Without it, the class recurs. #79 was this; item 18 is this; the next one will be.

### Plan

- [ ] **1.** Add `check_h11_literal_provenance(model)` following the file's rule
      shape (`check_h10_delegated_gate_evidence` at `:1540` is the closest sibling)
- [ ] **2.** The rule: **when a gate's SQL constrains a field to a literal value,
      that value must be reachable only by a path the gate's own prose claims.**
      Every conjunct filtering on `reason=`, `trigger=`, `scope=`, `provenance=` or
      similar is in scope. The config already names both halves, so this is
      mechanically checkable
- [ ] **3.** Hold the others to `context_reset`'s `trigger='session_start'`

### Validation

- [ ] **V1** ⭐ **H11 fails on the tree as it stands at `48c72fd`** (before item 18's
      fix). **A new lint rule that passes on the code that motivated it is not a
      rule.** This is the most important check in this unit. Evidence: ___
- [ ] **V2** H11 passes after W16 lands. Evidence: ___
- [ ] **V3** H11 passes on `context_reset` — the correct pattern — with no
      special-casing. Evidence: ___
- [ ] **V4** `.venv/bin/python scripts/enforcement_lint.py` → exit 0 overall (the 2
      pre-existing warnings stay warnings). Evidence: ___
- [ ] **V5** Unit test for the rule itself in `test_enforcement_lint.py`, with a
      synthetic config exhibiting the violation — the rule is tested, not just run.
      Evidence: ___

---

## W18 — Items 36 + 33: courier triggers and the suite marker

**Status:** `TODO`  ·  **Tier:** C  ·  **33 PROVEN**  ·  **Depends on:** W02
**Commit:** `fix(enforcement): couriers fire on execution, not on mention, and re-derive what they record`

Land after W02 so item 36's new guard uses the anchored probe rather than adding a
sixth `cwd`-relative one.

### Defect 36 · `theoretical_courier.py:54,73`

`files_a_finding` wakes when **any token contains** `merge_punchlists.py`, so
`grep -n reachability …merge_punchlists.py`, `cat …` and `git log -- …` all
trigger it (verified), and `echo event finding` trips the sibling branch. This is
the exact #77 shape the docstring at `:63-66` says it guards against — applied to
only one of its two branches (the sahjhan-verb branch is correct).

The population is re-derived so a real finding is not forged, but an agent can
**time the auto-deferral sweep on demand**, and combined with item 25 (merge
re-files escalations as `theoretical`) `grep`-ing the merge script auto-defers
Justine's escalations.

Separately, `pending()` calls `ensure_sahjhan()` with **no active-audit guard**
(`:85`, reached from `:155`), unlike `primer.py:80-83` — so any Bash line naming
the merge script in **any plugin-installed project** triggers a ~100 MB binary
download and a protocol warning injected into a non-audit session.

### Defect 33 · `verify_suite.py:341,371`

Identity is the path **tail** (`endswith(_SCRIPT_TAIL)`), and the courier never
re-derives its payload: `scope` from command text, `tree_hash`/`commit_hash` from
git, and the only second opinion is the printed `SUITE-GREEN:` line. **It is the
one courier with no ledger re-derivation** — the other four re-run their real
check.

Driven in a throwaway repo, a two-line `sub/enforcement/scripts/verify_suite.py`
that only prints the marker passed the recognizer, exit code, `repo_root`,
`compute_tree_hash` and `_effective_scope`; the sole thing that stopped the write
was the daemon being absent. With a live daemon this writes a `suite_green` naming
the real tree having run **zero tests**, satisfying `verify_suite.py --check` and
the suite gate on `fix_commit`. `_effective_scope` re-derives only for
`--scope affected`; `--scope full` — the stronger claim three transitions demand —
is passed straight through.

### Plan

- [ ] **1.** (36) Give the merge branch the same verb discipline the sahjhan branch
      has: require the token be **executed** (interpreter in the recognizer's set,
      script path in argument position), not merely mentioned.
      `verify_suite.record_scope_of` is the shape to copy
- [ ] **2.** (36) Add the active-audit guard before `ensure_sahjhan()`, ordered as
      `bash_guard.py:46-51` and `primer.py:80-83` do — using W02's `audit_active()`
- [ ] **3.** (33) Have the courier re-run the real check (as the other four do),
      **or** bind the marker to a host-derived signal it cannot echo
- [ ] **4.** (33) Re-derive `--scope full` rather than trusting command text. The
      weaker claim is re-derived today and the stronger one is not — backwards

### Validation

- [ ] **V1** (36) `grep -n reachability …merge_punchlists.py`, `cat …`,
      `git log -- …` and `echo event finding` → courier does **not** fire. Four
      separate cases; they reach the branch by different routes. Evidence: ___
- [ ] **V2** (36) A real `python3 …/merge_punchlists.py …` → courier fires as
      before. Evidence: ___
- [ ] **V3** (36) In a project with **no** audit, a Bash line naming the merge
      script triggers **no** binary download and **no** injected warning. This is
      invisible to any test run inside this repo, which always has an audit dir.
      Evidence: ___
- [ ] **V4** (33) The throwaway-repo reproduction: a two-line fake `verify_suite.py`
      that only prints the marker must **not** produce a `suite_green`. **Run it
      with a live daemon** — the original observation was limited by an absent one,
      so a mock-daemon test reproduces the limitation, not the fix. Evidence: ___
- [ ] **V5** (33) A genuine full-suite run still records. Evidence: ___
- [ ] **V6** (33) `--scope full` is re-derived: a run claiming `full` that ran a
      subset does not record `full`. Evidence: ___
- [ ] **V7** (33) The recorded green still satisfies `verify_suite.py --check` and
      the `fix_commit` suite gate — end to end, not just the write. Evidence: ___
- [ ] **V8 · non-vacuity** Revert 36 step 1 → V1 red; revert step 2 → V3 red;
      revert 33 → V4 red. Evidence: ___

---

## W19 — Items 40 + 47: NotebookEdit registration, and the missing manifest entry

**Status:** `TODO`  ·  **Tier:** C  ·  **Depends on:** W02
**Commit:** `fix(enforcement): register NotebookEdit consistently and trust the bootstrap caller`

### Defect 40 · three files disagree · verified

| File | Says |
|---|---|
| `pre_tool_hook.py:99` | believes it handles `NotebookEdit` |
| `hooks/hooks.json` | registers `pre_tool_hook.py` under matcher **`"Write\|Edit"` only** (the `Bash\|Write\|Edit\|NotebookEdit` matcher belongs to `_daemon_lifecycle.py`) |
| `enforcement/hooks.toml:100` | auto-record rule **includes** `NotebookEdit` |
| `enforcement/hooks.toml:27` | TDD gate is `tools = ["Edit", "Write"]` — **excludes** it |

So a `NotebookEdit` records a `source_edit` — counting toward the accumulation and
stall gates — while being **exempt from the TDD gate and the managed-path guard**,
and `pre_tool_hook`'s branch for it is dead code. Zero notebooks in this repo; the
exposure is downstream-consumer.

### Defect 47 · verified

`_sahjhan_bootstrap.py` is a `hooks.json` PreToolUse entrypoint (registered under
the `Write|Edit`, `Bash`, and `Grep|Glob` matchers) and calls `read_cache` →
`_daemon_request({"op": "enforcement_read"})`, a SO_PEERCRED-gated op — added by
`68ffd91` three months after the manifest's last completeness pass (`5a39a90`) and
**never added to `TRUSTED_SCRIPTS`** (verified: 18 entries, not among them).

Of its two uses of the result, one fails closed (`_daemon_stop_permitted`) and one
fails **open**: `_bash_source_write_tdd_block:1059` returns `None` on
`is_enforcement_fresh(None)`, skipping the TDD gate for Bash-based source writes.
The pre-commit auto-regen fired on that commit but structurally cannot add a file
not already in its own list.

### Plan

- [ ] **1.** (40) Pick one answer and make all three files say it. **Recommended:**
      `NotebookEdit` **is** a source edit — add it to the `hooks.json` matcher for
      `pre_tool_hook.py` and to the TDD gate's `tools`, matching the auto-record
      rule that already counts it
- [ ] **2.** (40) If instead it is deliberately exempt: remove it from the
      auto-record rule too, so it stops counting toward gates it cannot satisfy,
      and delete the dead branch at `pre_tool_hook.py:99`
- [ ] **3.** (47) Add `enforcement/hooks/_sahjhan_bootstrap.py` to `TRUSTED_SCRIPTS`
- [ ] **4.** (47) `bash scripts/hash-trusted-callers.sh`; commit the regenerated
      `enforcement/trusted-callers.toml` **in the same commit**

### Validation

- [ ] **V1** (40) `hook_e2e`: a `NotebookEdit` in `fix_loop` with no failing test
      recorded is **blocked**. Driven through the subprocess — this is a
      registration bug, and an in-process call would not see it. Evidence: ___
- [ ] **V2** (40) A `NotebookEdit` to a managed doc is blocked by the managed-path
      guard. Evidence: ___
- [ ] **V3** (40) A consistency test over the three files: the tool list in
      `hooks.json`, in `hooks.toml`'s gate, and in `pre_tool_hook.py`'s branch must
      agree. Evidence: ___
- [ ] **V4** (47) `real_daemon` `hook_e2e`: drive a **Bash source-write** with no
      failing test recorded → **blocked**. This is the fail-open half and the only
      check that distinguishes the fix from a no-op. Evidence: ___
- [ ] **V5** (47) `test_stale_sweep.py::test_every_registered_authed_writer_is_in_the_manifest`
      now covers this entrypoint. If it does not, extend it — it exists to fail the
      build for exactly this, and did not. Evidence: ___
- [ ] **V6 · non-vacuity** (40) Revert the matcher → V1 **and** V3 go red.
      (47) Remove the entry, **regenerate**, re-run V4 → flips to allow.
      **Regenerate before mutating**, or the RED is a stale-hash artifact.
      Evidence: ___

---

## W20 — Items 41 + 38: boundary ordering, and long-flag writes classified read-only

**Status:** `TODO`  ·  **Tier:** C
**Commit:** `fix(enforcement): release an abandoned audit, and stop reading --in-place as read-only`

### Defect 41 · `pre_tool_hook.py:102-111` / `commit_gate.py:59-76`

Both fire `exit_boundary_missing` **before** `is_enforcement_fresh`, and the
30-minute freshness window is the only thing that releases an abandoned audit. The
daemon is `nohup`'d and torn down only on `finalized`/`idle`. So a session killed
mid-`fix_loop` with a surviving daemon means **every Bash/Write/Edit in every
session in that repo** — and every linked worktree, since the socket is anchored —
denies with "type `holtz-start`", including sessions doing no audit.

`holtz-stop` is a real escape, so this is a wedge, not a deadlock. But the
docstring's "cannot fire in a project that is not being audited" is true only of a
project that never had a daemon.

### Defect 38 · `_protocol_cache.py:358` + `:382-384`

`_WRITING_FLAGS` maps `sed` to `("-i",)` and matches with
`p == flag or p.startswith(flag)`. **`"--in-place".startswith("-i")` is `False`** —
it starts with `--` — so `sed --in-place 's/a/b/' src.py` is classified read-only
and accrues no stall. The `#70/#71` in-place-rewrite bypass, reopened.

The table's own comment claims the opposite (*"also covers -i.bak / --in-place via
prefix match"*) and the function's docstring names this exact direction as the
unacceptable one (*"Misreading a write as a read would let real work escape the
counter"*). Separately, `git` is whitelisted with no writing-flag table, so
`git diff --output=/path HEAD` → read-only too. `test_hook_chains.py:527` tests
`sed -i` and `sed -i.bak` and omits `--in-place`.

### Plan

- [ ] **1.** (41) ⚠️ **Do not simply swap the two checks.** The ordering is
      deliberate and documented in both files (*"a refusing daemon serves no cache,
      so `is_enforcement_fresh` is False and this degrade path would otherwise wave
      through exactly the situation it exists for"*) — swapping reopens the fuse
      inversion
- [ ] **2.** (41) Distinguish the two cases the single ordering conflates:
      *boundary missing during a live audit* (block — correct today) from *boundary
      missing with an abandoned audit* (release). Freshness alone is not the
      discriminator; the terminated marker and the init-pid liveness check are, and
      both already exist in `_common.py`
- [ ] **3.** (41) Correct the docstring either way
- [ ] **4.** (38) Add `--in-place` to `sed`'s writing flags (prefix match then
      covers `--in-place=.bak`), and fix the comment claiming it was already covered
- [ ] **5.** (38) Add a writing-flag entry for `git`: `--output`, and any other
      `git diff` flag that writes
- [ ] **6.** (38) Audit the rest of `_READ_ONLY_COMMANDS` for the same long-flag
      gap — **the bug is the `--`/`-` asymmetry, not the specific word**

### Validation

- [ ] **V1** (41) A session killed mid-`fix_loop` with a surviving daemon, past the
      freshness window: an unrelated session's Bash is **allowed** (or blocked with
      a message naming a working escape — assert which, and run it). Evidence: ___
- [ ] **V2** (41) A live audit with the boundary genuinely down still **blocks**.
      This is the fuse and must not regress. Evidence: ___
- [ ] **V3** (41) A linked worktree behaves as the main checkout does. Evidence: ___
- [ ] **V4** (38) `sed --in-place 's/a/b/' src.py` → **not** read-only; the stall
      counter charges it. Evidence: ___
- [ ] **V5** (38) `git diff --output=/tmp/x HEAD` → not read-only. Evidence: ___
- [ ] **V6** (38) `sed -i`, `sed -i.bak`, `git diff HEAD` keep their current
      classifications — `test_hook_chains.py:527` must not move. Evidence: ___
- [ ] **V7** (38) All three long-flag forms added to `test_hook_chains.py` beside
      the short forms. Evidence: ___
- [ ] **V8 · non-vacuity** (41) Apply the naive swap instead of the fix → **V2 must
      go red**, demonstrating why the swap is wrong. (38) Revert → V4, V5 red.
      Evidence: ___

---

## W21 — Item 9: `merge_finding` has no relatedness or severity constraint

**Status:** `TODO`  ·  **Tier:** C  ·  **PROVEN**  ·  **D-c RULED**
**Commit:** `fix(enforcement): merge_finding requires an open target of at least equal severity`

### Defect

`merge_target_exists` for `BH-010` (CRITICAL) into `BH-011` (an unrelated LOW)
reads `true` — the predicate requires only that the target is a filed finding and
not the item itself. The merge emits `finding_resolved`, so it clears
`all_critical_resolved`, and it lets a round discharge `round_opens_exceed_closes`
by merging away every sibling it just found.

**The table of no-fix CRITICAL closures is now four rows, not three:**

| Command | Blocked? | Status |
|---|---|---|
| `event finding_resolved --field id=… --field commit_hash=…` | no | pre-existing, taught, **documented choice** — `sahjhan resolve` is an alias |
| `event finding_deferred --field reason=theoretical` | no | **item 18** — new in this delta and argued to be impossible |
| `transition merge_finding <crit> <unrelated>` | no | **this item** |
| `merge_punchlists.py` re-filing an escalated finding | no | **item 25** — the only route needing no agent intent |

`commit_hash` is pattern-checked but never resolved, so `0000000` is accepted. The
generated contract already names the posture honestly — *"21 of 32 gate-consumed
events are the agent's own word"* — so row 1 is a deliberate choice, not a defect.

### Plan

### RULED (Jon, 2026-08-27) — D-c: severity floor **and** target must be open

Both terms. The target's severity must be ≥ the merged item's, **and** the target
must still be open — so a finding cannot be merged into something already closed.

- [ ] **1.** Add **both** terms to `merge_target_exists` in `protocol.toml`. Grade
      severity by **latest filing** with the same max-seq correlation the other
      predicates use (D25), or a re-filed correction silently changes the answer
- [ ] **2.** Reuse the existing `item_open` predicate for the openness term rather
      than writing a second expression of it — one named fact, two consumers
- [ ] **3.** Update the item-9 table to four rows wherever it is restated, keeping
      the row-1 distinction (documented choice, not defect)
- [ ] **4.** ⚠️ **Enumerate what the openness term refuses.** It removes a route
      that exists today; if a legitimate late merge into a closed duplicate is a
      real workflow, it now needs a named escape. A gate whose refused cases have
      no route is #77 at the end of the run

### Validation

- [ ] **V1** `merge_finding BH-010(CRITICAL) → BH-011(LOW)` → refused. Evidence: ___
- [ ] **V2** `merge_finding BH-010 → BH-012(already closed)` → refused. Evidence: ___
- [ ] **V3** A legitimate sibling merge into an **open** target of equal severity
      still works — the transition has a real use and must survive. Evidence: ___
- [ ] **V4** Merge into an open target of **higher** severity still works — the
      floor is `>=`, not `==`. Evidence: ___
- [ ] **V5** A round cannot discharge `round_opens_exceed_closes` by merging away
      its own siblings. Drive the round, not just the predicate. Evidence: ___
- [ ] **V6** Severity is graded by latest filing: a LOW re-filed as CRITICAL is a
      valid target for a CRITICAL. Evidence: ___
- [ ] **V7 · non-vacuity** Revert each term **separately**; a distinct check goes
      red for each (V1 for the floor, V2 for openness). One check covering both
      means one term is untested. Evidence: ___

---

## W22 — Item 27: `boundary_check.py` crashes on the one platform path its docstring calls confinement

**Status:** `TODO`  ·  **Tier: A — RULED (Jon, 2026-08-27, D-h)**  ·  **Runs in P1**
**Commit:** `fix(skills): construct the probe socket inside the try`

### RULED — Tier A, before functional testing

Item 27 was in **no tier**: the consolidated fourth-pass list carries 48 of 49
items, and 27 is the omission — it sat at position 9 in "Suggested order" and was
dropped when the tiers superseded it. Ruled **Tier A**, two bands above the
recommendation.

**What that implies for the functional test:** Linux with the optional
`@anthropic-ai/sandbox-runtime` seccomp filter is a target for the next run.
Every other P1 unit should be exercised on that configuration too, not only on
macOS — in particular W02's worktree fixture (F1) and W22's own probe path. A
Tier A ruling here and a macOS-only test run would leave the item's whole reason
for being untested.

⚠️ **Open operational item — does not block starting.** Nothing yet says how that
environment gets stood up or who does it. It is not on this unit's critical path:
the fix is one line and **V1 patches `socket.socket` itself, so it runs on macOS**.
CI is `ubuntu-latest` (`.github/workflows/ci.yml:11`), which covers Linux but
**not** seccomp — the filter is not installed there. So: land W22 and its unit
tests anywhere, and treat "stand up a seccomp-confined session" as a prerequisite
of the **functional run**, to be scheduled when P1 is `DONE`. Raise it then; do
not let it gate the code.

### Defect · `skills/holtz/scripts/boundary_check.py:45`

The socket is constructed **before** the `try`:

```python
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)   # <-- line 45
sock.settimeout(5)
try:
    sock.connect(sock_path)
except PermissionError:
    # …Linux's seccomp filter blocks socket(AF_UNIX) outright…
    return CONFINED
```

The comment names two mechanisms. macOS Seatbelt answers EPERM on `connect()`,
which the `try` catches. **Linux's seccomp filter blocks `socket(AF_UNIX)`
outright** — which raises on line 45, *outside* the `try`, and propagates out of
`probe()` and `main()` as an uncaught traceback. Observed:

```
socket.socket -> PermissionError(1, 'Operation not permitted')
probe()       -> RAISED: PermissionError [Errno 1] Operation not permitted
```

So on a correctly confined Linux session — the configuration `holtz-start`'s own
receipt tells the user to set up — **recon Step 0 dies with a traceback**, and
`SKILL.md:282` reads that as "it did not print `BOUNDARY: confined`" and instructs
the agent to *"stop and ask the user to type `holtz-start`"*, which will not help
because the boundary is already up. **The strongest confinement produces the same
instruction as no daemon at all.**

`test_boundary_check.py:119` patches `socket.socket.connect` only, so the suite
exercises the macOS path and cannot see this.

### Plan

- [ ] **1.** Move the constructor inside the `try` (or wrap it). One line
- [ ] **2.** No dependencies — can land any time

### Validation

- [ ] **V1** Patch `socket.socket` **itself** to raise `PermissionError` →
      `probe()` returns `CONFINED`. Evidence: ___
- [ ] **V2** The macOS path still returns `CONFINED`. Evidence: ___
- [ ] **V3 · non-vacuity** Revert the one-line move → V1 goes red with the observed
      `PermissionError [Errno 1] Operation not permitted`. Evidence: ___

---
---

# P4 — hygiene and record

Correctness, documentation, and recorded decisions. These do not block the
functional test.

---

## W23 — Items 4 + 7 + 8 + 13 + 14: the doc sweep

**Status:** `TODO`  ·  **Tier:** D
**Commit:** `fix(skills): bring the fix-loop and convergence docs to the shipped protocol`

One commit — it is what a real run reads.

### Item 4 · the fix-subagent contract contradicts itself across three files

`phase-fix-loop.md` was rewritten for P0.3; `SKILL.md:233` and
`step-10-fix-loop.md:5` were not:

| Claim | `SKILL.md` / `step-10` | `phase-fix-loop.md` (shipped) |
|---|---|---|
| Where it works | "in the enforced tree" | its own `isolation: "worktree"` |
| The TDD gate | "does not look at `agent_id`" / "agent-agnostic" | filters on `agent_id` |
| Committing | "**Never** let a fix subagent `git commit`" | step A.9: commit, then rebase |

`CLAUDE.md` rule 5 names this exact failure mode and cites `800624f`. The guard —
`test_subagent_contract_consistency.py` — only greps five retired phrases from the
old incident, so it is blind to the new drift and passes.

### Item 7 · `phase-convergence.md` still says converge requires "zero open items"

Verified verbatim in step 4: *"Sahjhan checks all gates: all perspectives
complete, suite passes, linters pass, **zero open items**, no protocol
violations."* That is the gate P0.1 replaced. An agent following this drives
toward the non-terminating behaviour the release exists to end.

### Item 8 · `SKILL.md`'s deferral rules predate P0.5

`SKILL.md:37` verbatim: *"CRITICAL/HIGH must be fixed; LOW, budget-capped MEDIUM,
and can't-reproduce may be deferred."* No mention that only `user_reachable` is
fix-loop eligible, that `fault_injected` batches at Step 15, or that `theoretical`
auto-defers. `reachability` appears once in the whole file, as a field in an
example.

### Item 13 · `docs/ARCHITECTURE.md:272` still lists `PUNCHLIST-MERGED.md`

Verified in the file-layout block. P0.4 deleted the concept and `fix_loop_start`
now refuses to start while the file exists.

### Item 14 · `step-10-fix-loop.md` Fast Path still mandates a third suite run

Verified: *"Write failing test. Verify it fails. Minimal fix. **Full suite.**
Commit."* A third mandated tail run, at the wrong scope, in the file whose Per-Fix
Hardening #3 was edited to say "Do not run the suite here."

### Plan

- [ ] **1.** (4) Rewrite `SKILL.md:233` and `step-10-fix-loop.md:5` to the shipped
      contract
- [ ] **2.** (4) Give `test_subagent_contract_consistency.py` a **positive**
      assertion — worktree, actor-scoped gate, subagent commits — rather than a
      denylist of last year's wording
- [ ] **3.** (7) Replace the "zero open items" clause with the shipped conjuncts
- [ ] **4.** (8) State the reachability routing where the deferral rules are stated.
      **Action only — no rationale**; reasoning goes in the commit message. Do not
      write a prohibition the reader only learns about from the prohibition itself
      ("any more")
- [ ] **5.** (13) Remove the line; check the rest of the layout block in the same
      pass — one stale entry suggests others
- [ ] **6.** (14) Bring the Fast Path in line with the hardening step

### Validation

- [ ] **V1** (4) The rewritten consistency test **fails against the tree as it
      stands**, then passes after the edits. A denylist-to-positive rewrite that
      passes both before and after has changed nothing. Evidence: ___
- [ ] **V2** (4) All three claims asserted **separately**, so a future drift on one
      does not hide behind the other two. Evidence: ___
- [ ] **V3** (4/14) Where step ordering matters, assert on the **document's own line
      order**, not just on the gate. Evidence: ___
- [ ] **V4** (7) Grep the phrase across `skills/**` → zero hits. Evidence: ___
- [ ] **V5** (7) A test asserts the doc's gate list matches `transitions.toml`'s
      `converge` conjuncts **by name**. Prose that restates a gate list drifts.
      Evidence: ___
- [ ] **V6** (8) A doc-consistency test: the three reachability grades named in
      `SKILL.md` match `events.toml`'s pattern for the field. Evidence: ___
- [ ] **V7** (13) Grep `PUNCHLIST-MERGED` across `docs/**` and `skills/**` → only
      unambiguously historical references remain. Extend
      `test_managed_docs_consistency.py` to assert the layout block matches the
      managed-docs list. Evidence: ___
- [ ] **V8** (14) The two sections of `step-10-fix-loop.md` agree, and the taught
      scope matches what `fix_commit`'s suite gate requires. Evidence: ___
- [ ] **V9** `pytest -m contract` and `contract_gate.py` → exit 0. Evidence: ___
- [ ] **V10** Audit the whole 24-hour edit window for rationale creep, not just this
      diff. Evidence: ___

---

## W24 — Items 6 + 44: render triggers and templates

**Status:** `TODO`  ·  **Tier:** D  ·  **D-b + D-g RULED**
**Commit:** `fix(enforcement): gate converge on the deferral record, not on a file that always exists`

Both edit the same `renders.toml` entry.

⚠️ **Line numbers below are stale by the time you get here.** W05 (P1) deletes
`transitions.toml:553` from the same `converge` block this unit edits at `:552`.
Re-read the block and match on the conjunct's **text**, not the line number.
Confirm by diff that the `medium_deferral_budget` conjunct is already gone — if
it is still there, W05 has not landed and this unit is out of order.

### Item 6 · the `DEFERRED.md` conjunct is satisfied by filing one finding

`renders.toml:21-26` renders `DEFERRED.md` on `finding` **and** `finding_deferred`
(verified), so the file exists from the run's first finding — and
`test_it_is_written_once_the_run_has_findings` asserts that as correct. The spec's
conjunct meant "the batch deferral happened"; as shipped it is a `file_exists` on
a file the engine writes unconditionally.

### Item 44 · `DEFERRED.md` shows a deferred-then-fixed finding as still deferred

Verified: `deferred.md.tera:27-40` computes `deferred_ids` and **never**
`resolved_ids`, while `punchlist.md.tera:21` computes it and `:40` gives it
precedence. So a finding deferred then fixed anyway — a legal path, since
`fix_commit` carries no `item_open` gate — is listed as deferred forever.
`renders.toml:25` compounds it by omitting `finding_resolved` from the trigger.

Separately, `STATUS.md` renders `on_transition` while the punchlist family renders
`on_event`, so its Open/Resolved counts freeze between transitions. Both are
agent/human-read only; nothing gates on their content.

### RULED (Jon, 2026-08-27)

- **D-b:** replace the `file_exists` conjunct with a **ledger predicate over
  deferrals**, and drop `finding` from the render trigger.
- **D-g:** add `on_event` for the finding family to `STATUS.md`.

⚠️ **This is the branch carrying the trap, so the trap is acceptance criterion
number one.** Dropping `finding` from the trigger means `DEFERRED.md` no longer
exists on a run that defers nothing. **The replacement predicate must therefore be
vacuously true at zero deferrals** — otherwise a virtuous run that fixed
everything cannot converge, and this unit rebuilds item 2's strand at a different
gate while closing it at the original one.

**The predicate must satisfy all three, and the third is what makes it safe:**

1. **Meaningful when deferrals exist** — it asserts the deferral record is
   complete, which is what P0.1's conjunct meant.
2. **Vacuously true at zero deferrals** — a run with nothing deferred converges.
3. **Achievable by construction** — every state it refuses has a command that
   reaches the state it demands.

*Proposed shape, to confirm at implementation:* every `finding_deferred` names a
filed `finding` and carries a `reason` from the allowed set — an integrity claim
over the deferral record that is vacuously true at zero rows. If that reads too
weak to be worth a gate, the honest alternative is D-b's other branch (drop the
conjunct); **raise that rather than inventing a stronger predicate that fails
property 2.**

### Plan

- [ ] **1.** (6) Drop `finding` from `DEFERRED.md`'s render trigger, leaving
      `finding_deferred`
- [ ] **2.** (6) Replace the `file_exists` conjunct at `transitions.toml:552` with
      the ledger predicate, as a named query in `protocol.toml` with an `intent`
- [ ] **3.** (44) Compute `resolved_ids` in `deferred.md.tera` and give it
      precedence — **copy `punchlist.md.tera:21,40`'s expression** rather than
      writing a second one
- [ ] **4.** (44) Add `finding_resolved` to `DEFERRED.md`'s render trigger
- [ ] **5.** (44/D-g) Add `on_event` for `finding`, `finding_resolved`,
      `finding_deferred` to the `STATUS.md` render entry
- [ ] **6.** Note the churn: `STATUS.md` is a managed file, so every finding event
      now re-renders and re-tracks it. Confirm the manifest absorbs the extra
      writes without a `protocol_violation` — that is the failure mode this
      change could plausibly introduce

### Validation

- [ ] **V1** ⭐ **THE TRAP — check this first.** A run that files findings, fixes
      **all** of them and defers **nothing**: `DEFERRED.md` does not exist, and
      **`converge` still passes**. If this is red, the unit has traded one strand
      for another and must not ship. Evidence: ___
- [ ] **V2** (6) A run with one deferral: the file renders and the predicate reads
      true. Evidence: ___
- [ ] **V3** (6) The predicate is **meaningful** — construct an incomplete deferral
      record and assert it reads false. A predicate that is true in every reachable
      state is decoration, which is what P0.1 removed from `converge` in the first
      place. Evidence: ___
- [ ] **V4** (6) Escape reachability: for the state V3 refuses, drive the named
      command and assert the predicate flips. Evidence: ___
- [ ] **V5** (6) `test_it_is_written_once_the_run_has_findings` rewritten — it
      asserts the defect. Evidence: ___
- [ ] **V6** (44) File → defer → resolve: `DEFERRED.md` does **not** list it.
      Evidence: ___
- [ ] **V7** (44) A finding deferred and not resolved **is** still listed.
      Evidence: ___
- [ ] **V8** (44) All four templates agree on resolved-takes-precedence — assert
      across the family, since three had it and one did not. Evidence: ___
- [ ] **V9** (D-g) `STATUS.md` counts change on a finding event **without** a
      transition. Evidence: ___
- [ ] **V10** (D-g) The extra renders produce **no** `protocol_violation` — the
      manifest tracks the re-renders cleanly. Evidence: ___
- [ ] **V11 · non-vacuity** Revert the trigger → V2 red; revert the template → V6
      red; revert the `STATUS.md` trigger → V9 red. Evidence: ___

---

## W25 — Items 11 + 39 + 49: escapes, the PostToolUse fall-through, and the lower tail

**Status:** `TODO`  ·  **Tier:** D  ·  **Depends on:** W05, W14 (they fix two of item 11's four gates)
**Commit:** `fix(enforcement): every gate names an escape, and no hook degrades in silence`

### Item 11 · gates that print no escape

| Gate | Problem | Fixed by |
|---|---|---|
| `all_findings_closed` | no `intent` | **W07 deletes the conjunct.** If `enforcement_lint` H1 says the query still has consumers (`findings.py` / renders) and it is kept declared, it needs an intent — decide there, not here |
| `quiz_exhaustions_resolved` | no `intent` | **here** |
| `amplification_diverging` on `converge` | names no escape | W14 step 5 |
| `medium_deferral_budget` | intent is **self-contradictory**: *"half the MEDIUMs get fixed, not deferred"* while the gate requires half **deferred** | **W05 — resolved by deletion.** D-a drops the whole conjunct, and the contradictory intent goes with it. The query's own intent at `protocol.toml:260` is accurate for the two seats that remain, so nothing is left to fix |

### Item 39 · `post_tool_hook.py:139-148` · verified

`eval_data` is initialised `{}` and only populated `if result.returncode == 0`, so
a non-zero exit falls through with **no `auto_records`, no
`exit_enforcement_error`, no telemetry**. A config or version fault stops
`file_read`/`source_edit`/`file_search` being recorded, and every predicate
counting `source_edit` — the edit-accumulation block, the stall monitor — reads
zero forever. `pre_tool_hook.py:158-169` handles the same case correctly; **the
two hooks disagree.**

Secondary: a JSON **list** from `result.stdout` makes `data.get` raise
`AttributeError`, which is outside the except tuple
`(OSError, TimeoutExpired, JSONDecodeError, ValueError)` → an uncaught traceback
out of a PostToolUse hook.

### Item 49 · lower tail (bundle) · all verified

| # | Defect | Plan | Validation |
|---|---|---|---|
| a | `_common.py:271-273` — `boundary_dir`'s "fails closed" comment is **inverted** for consumer hooks: an unresolvable `~` yields a relative socket path → `connect` raises → `exit_ok` (fail **open**) | Make it fail closed, or correct the comment | Unresolvable `~` → assert the decision **and** that the docstring matches it |
| b | `protocol_tracker.py:198-199,234-235` — a transient `enforcement_read` failure followed by a successful write constructs and persists `empty_cache()`, **erasing every pending commit and stall count** | Do not write a cache built from a failed read; skip the write | Read fails → write skipped → pending commits and stall survive |
| c | `_protocol_cache.py:565-575` — a mid-flight upgrade maps a pre-delta scalar stall onto `{ORCHESTRATOR: N}`, charging the orchestrator the whole run's stall (the audited run drove one number to 16 across 54 actors) | Decide migrate vs discard; the comment argues migration | Upgrade a cache holding scalar 16 → assert the ruled outcome, with the number chosen so no two quantities coincide |
| d | `post_tool_hook.py:132-133` — **never passes `--agent-id`**, so every PostToolUse gate/monitor is structurally run-global (item-1/19 family); dormant only because no PostToolUse rule templates `{{agent_id}}` today | Pass it as `pre_tool_hook.py:128-130` does | Assert the flag is passed, and that the two hooks agree — the dormancy must not become live silently |
| e | `commit_gate.py:109-121` — `blocks_all` is `any(...)` but the message is always `obligations[0]`, so **a stall block can print the pending-commit remedy** | Print the message belonging to the obligation that actually blocked | Two obligations, the second blocking → the printed escape is the second's, **and it runs** |
| f | `commit_gate.py:66` — the comment names `holtz-stop` (which tears the boundary **down**) as the escape from a boundary-missing block whose message correctly says `holtz-start` | Correct the comment | Comment and message name the same command |
| g | `bash_guard.py:99-122` — records `protocol_violation` under `contextlib.suppress` with **no `returncode` check**, then asserts the violation is "permanent"; and hardcodes `auditor=holtz` three lines under a "derived, never mirrored" comment | Check the return code before claiming permanence; derive the auditor | A failed violation write does not produce the "permanent" claim; the recorded auditor is derived |
| h | `_shell_norm.py:32-35` — `resolve_indirection` treats `--field k=v` as a shell assignment and rewrites `$k` inside quoted data, so guards reason about a command string never typed (latent; no decision flip found) | Exclude `--field`-style operands from assignment collection | `--field finding_id=BH-001 … $finding_id` is not rewritten; no guard's decision changes |

### Plan

- [ ] **1.** (11) Add an `intent` to `quiz_exhaustions_resolved`
- [ ] **2.** (11) **Close the class:** a lint check (or an H8 extension) asserting
      **every** gate carries an `intent`. Item 11 is a symptom list; the check is
      the fix
- [ ] **3.** (39) Handle non-zero the way `pre_tool_hook` does —
      `exit_enforcement_error` with the PostToolUse variant (a warning, since
      PostToolUse cannot undo the work)
- [ ] **4.** (39) Guard the shape: `if not isinstance(data, dict)` before `.get`.
      **Prefer the explicit check** — the except tuple is already doing too much
- [ ] **5.** (49) Work rows a–h from the table above
- [ ] **6.** `bash scripts/hash-trusted-callers.sh` — this touches four
      manifest-listed hooks

### Validation

- [ ] **V1** (11) The new check **fails on the tree at `48c72fd`** and passes after.
      Evidence: ___
- [ ] **V2** (11) For each of the four gates: the block prints an escape **and the
      escape runs**. Evidence: ___
- [ ] **V3** (39) A non-zero `hook eval` exit produces a **visible** degraded-mode
      signal. Silence is the defect — assert the message, not the absence of a
      crash. Evidence: ___
- [ ] **V4** (39) `source_edit` recording unaffected on the success path.
      Evidence: ___
- [ ] **V5** (39) `result.stdout` = `"[]"` → no traceback; hook exits 0 with a
      warning. Evidence: ___
- [ ] **V6** (39) A single test asserts `pre_tool_hook` and `post_tool_hook` agree on
      this case, so they cannot drift apart again. Evidence: ___
- [ ] **V7** (49) Each of rows a–h has its validation from the table observed.
      Evidence: a___ b___ c___ d___ e___ f___ g___ h___
- [ ] **V8** `pytest -m hook_e2e` → exit 0. Evidence: ___
- [ ] **V9 · non-vacuity** Revert 39 → V3 and V5 go red. Evidence: ___

---

## W26 — Item 48: the delta's new enforcement predicates ship with no direct unit tests

**Status:** `TODO`  ·  **Tier:** D
**Commit:** `test: direct unit coverage for the delta's new enforcement predicates`

### Defect

No test imports `is_read_only_cmd`, `_tdd_gate_exempt`, `project_anchor`,
`stall_bumped`/`stall_cleared`, `pending_commits_for`, `exit_boundary_missing` or
`query_named_predicate`.

`is_read_only_cmd` is the notable one: a new ~40-line classifier with two
hand-kept frozensets deciding whether a Bash line escapes the stall counter,
covered only by the parametrized subprocess cases in `test_hook_chains.py` —
**which is where item 38 slipped through.**

### Plan

- [ ] **1.** Direct unit tests for all seven. `is_read_only_cmd` first — it is the
      one with a known escaped defect
- [ ] **2.** For the two hand-kept frozensets, test the **long-flag** forms
      explicitly; the `--`/`-` asymmetry is the defect class, not any single word
- [ ] **3.** Drive hooks by subprocess where the interface matters. ⚠️ **Two
      `_common.py` modules exist** — importing the wrong one imports cleanly and
      makes every query return empty. Never let a negative assertion rest on an
      empty set

### Validation

- [ ] **V1** Each of the seven has at least one test that fails when the function is
      mutated. **Mutate each, confirm RED, revert** — the list is the checklist.
      Evidence: 1___ 2___ 3___ 4___ 5___ 6___ 7___
- [ ] **V2** `is_read_only_cmd`'s test **would have caught item 38**: assert
      `--in-place` before W20 lands and watch it go red. Evidence: ___
- [ ] **V3** Coverage does not fall. **Do not lower a threshold** to accommodate
      this work — if coverage reads low, fix the measurement. Evidence: ___

---

## W27 — Items 15 + 45 + 46: dependency declaration, migration tooling, pin checks

**Status:** `TODO`  ·  **Tier:** D
**Commit:** `chore: declare test dependencies and cross-check the sahjhan pin`

### Item 15 · `hypothesis` is undeclared · **OBSERVED**

`.github/workflows/ci.yml:21` pip-installs it; `pyproject.toml` has **no
`[project]` table at all** (verified — the only tables are `tool.ruff`,
`tool.ruff.lint`, `tool.ruff.lint.per-file-ignores`, `tool.mypy`,
`tool.coverage.run`, `tool.pytest.ini_options`). `tests/test_property_based.py`
imports it unguarded at module scope.

```
$ python3 -m pytest tests/test_property_based.py --collect-only -q
E   ModuleNotFoundError: No module named 'hypothesis'
!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!
```

`.venv` carries `hypothesis 6.156.6`. **Local and CI do not run the same set on a
fresh machine** — the exact divergence `git-hooks/pre-commit` exists to prevent.

### Item 45 · `migrate_legacy.py`

Every migrated `finding`/`finding_resolved` sets `step=""` and often
`commit_hash=""`, both failing their `events.toml` patterns — harmless only
because `sahjhan ledger import` is schema-lax, but born non-compliant and
untouched by the `5679f5c` reachability pass. `--all` prints all runs' events with
reused `BH-NNN` ids and no ledger boundary, and its own usage line invites a single
combined import that would collide identically-numbered findings under D25's
by-id latest-wins. `build_project_ledger` re-run accumulates duplicate
`run_registered`/`run_completed` rows. All historical-tooling paths; none is
gate-consumed.

### Item 46 · the sahjhan pin

The three pins are currently coherent (verified: `bin/.sahjhan-version`,
`_resolve.SAHJHAN_VERSION` and `bin/sahjhan --version` all `0.23.0`). But
`update_sahjhan_pin.py:39-47` hashes whatever bytes sit in `bin_dir` **without
checking they belong to the version being pinned**, and `_resolve.ensure_sahjhan`'s
fast path returns a binary on a version-marker string match with **no checksum
re-verification** (that happens only on a fresh download). `check_sahjhan_pin.py`
is wired only into `pre-release-check.sh`, not the git hooks, so a partially-failed
vendor run leaves an unverified binary trusted until the next release.

### Plan

- [ ] **1.** (15) Add a `[project]` table to `pyproject.toml` with a test extra
      declaring `pytest`, `hypothesis` and anything else CI installs by hand
- [ ] **2.** (15) Point CI at the extra instead of a hand-written `pip install`, so
      the two cannot drift
- [ ] **3.** (45) Emit schema-valid values, or omit the optional fields rather than
      emitting empty strings that fail their own patterns
- [ ] **4.** (45) Give `--all` a ledger boundary per run; fix the usage line that
      invites the colliding import
- [ ] **5.** (45) Make `build_project_ledger` idempotent
- [ ] **6.** (46) `update_sahjhan_pin.py` runs `bin/sahjhan --version` and refuses to
      pin if it disagrees with the version being pinned
- [ ] **7.** (46) Wire `check_sahjhan_pin.py` into `git-hooks/pre-commit` (it is
      fast), not only into the release script
- [ ] **8.** (46) Decide whether `ensure_sahjhan`'s fast path should re-hash.
      Recommendation: re-hash when the marker changes or the mtime moves, not on
      every call

### Validation

- [ ] **V1** (15) In a **clean virtualenv built only from `pyproject.toml`'s test
      extra**: `python -m pytest --collect-only -q` → exit 0, no collection errors.
      Paste the collected count. Evidence: ___
- [ ] **V2** (15) Grep `pip install` in the workflow → every name is declared.
      Evidence: ___
- [ ] **V3** (15) **non-vacuity** Remove `hypothesis` from the extra → V1 goes red
      with the same `ModuleNotFoundError`. Evidence: ___
- [ ] **V4** (45) Every migrated event validates against `events.toml` field-by-field
      — **not** via a lax import that would pass today. Evidence: ___
- [ ] **V5** (45) `--all` across two runs with the same `BH-001` keeps them distinct.
      Evidence: ___
- [ ] **V6** (45) `build_project_ledger` run twice produces the same ledger as once.
      Evidence: ___
- [ ] **V7** (46) Put a mismatched binary in `bin/` → the pin updater refuses,
      naming both versions. Evidence: ___
- [ ] **V8** (46) Stage a mismatched pin → the commit fails via pre-commit.
      Evidence: ___
- [ ] **V9** (46) All three pins agree after a real vendor run, and all four
      `SAHJHAN_CHECKSUMS` recompute and match. Evidence: ___

---

## W28 — Items 12 + 16: README contradiction, then the changelog

**Status:** `TODO`  ·  **Tier:** D  ·  **Depends on:** everything above
**Commit:** `docs: remove the refuted security claim; draft the release changelog`

Draft the changelog **last**, so the notes describe the release rather than the
review.

### Item 12 · README contradicts itself, including on a security claim · verified

- Line 204: *"Twelve hooks backed by the Sahjhan enforcement engine"*; line 222:
  *"20 enforcement hooks"*. **`hooks.json` registers 22** (counted: 6 PreToolUse,
  10 PostToolUse, 2 SubagentStop, 1 Stop, 2 UserPromptSubmit, 1 SessionStart).
- Line 204 says session keys are *"inaccessible to the model or any same-user
  process **without kernel-enforced socket credentials**"*. The "The boundary"
  paragraph eight lines below says that is provably false and explains why.
  **The refuted claim is still in the document, above its own refutation.**

### Item 16 · `CHANGELOG.md` `[Unreleased]` is empty

Verified: the header exists with nothing under it, across 93 commits. Expected
pre-release, but it is step 5 of the release checklist.

### Plan

- [ ] **1.** (12) Delete the refuted clause from line 204. The boundary paragraph is
      the best-told story in the delta and needs no help; it needs the
      contradiction removed
- [ ] **2.** (12) Make both counts say 22, or drop the number
- [ ] **3.** (16) `.venv/bin/python scripts/generate-changelog.py` (preview), review,
      then `--write`
- [ ] **4.** (16) ⚠️ **The release-notes exercise in the punchlist is the honest
      source for what can and cannot be claimed** — three of its five headline
      sentences were unshippable at review time. **Do not restore a sentence whose
      item is still open.**

### Validation

- [ ] **V1** (12) A test asserting the README's hook count equals
      `len(hooks.json entries)` — if a number is kept it must be **derived**, not
      typed. If no number is kept, assert the phrase is absent. Evidence: ___
- [ ] **V2** (12) Grep for the refuted phrase → zero hits. Evidence: ___
- [ ] **V3** (16) `[Unreleased]` is non-empty and every entry maps to a commit in
      `git log dev --not main`. Evidence: ___
- [ ] **V4** (16) Each item fixed in this cycle appears; each item **not** fixed has
      no sentence claiming it. Evidence: ___
- [ ] **V5** `scripts/pre-release-check.sh` → exit 0. Evidence: ___

---

## W29 — Items 21 + 24: the recorded decisions

**Status:** `TODO`  ·  **Tier:** D  ·  **D-e + D-f RULED**
**Commit:** `fix(enforcement): narrow the round-cap claim and record the hardening-batch scope`

**RULED (Jon, 2026-08-27): both take the record-the-decision branch.**
**D-e** — narrow `protocol.toml`'s claim; **do not** change the round-cap
population. **D-f** — document the hardening batch's scope as deliberate and fix
the docstring; **do not** enforce a module-touching diff.

Neither predicate changes. Both units are comment, doc and test work — which is
the point: an overclaiming comment next to a weaker predicate is the defect these
close, and the fix is to make the comment true, not to make the predicate match a
comment nobody decided to honour.

### Item 21 · the round cap's population is an optional field the agent types

`round_item_cap_exceeded` and `round_opens_exceed_closes` count only findings
joined by `strpos(','||p.pattern_ids||',', ','||f.pattern_id||',') > 0`, and
`pattern_id` is `optional = true`, attestation `agent`. A NULL on either side drops
the row. **So the cap is opt-in** — a round that files ten siblings and tags none,
or tags them `PAT-99` when the brief declares `PAT-1`, is never over the cap. And
`test_round_item_cap.py:105,117` assert exactly that as correct behaviour.

`protocol.toml`'s D6 comment argues under-reporting is safe — *"the direction that
forfeits the relief this conjunct grants, not the direction that dodges a block."*
True for the backpressure conjunct. **False for D7's cap and for the
two-dry-rounds clause**, where under-reporting *is* the block-dodging direction:
not writing `## PAT-NNN:` headings twice in a row withdraws the pattern-round
obligation outright, and it costs less than the merge the cap's own block message
names.

### Item 24 · a hardening batch's commit need not touch the module it closes

`hardening_batch.check()` refuses four things — an unfiled module, a partial
module, a commit naming another module's findings, and a commit already spent or
empty. **It does not require the diff to be *in* the named module.** So one
non-empty commit anywhere closes an entire directory's open `fault_injected`
findings. The docstring's own summary — *"a diff that has not been used before is
the work"* — claims more than the check enforces, and `no_open_fault_injected`
gates `converge`.

### Plan

- [ ] **1.** (21) Narrow the `protocol.toml` D6 comment to the conjunct it is
      **true of** — the backpressure conjunct, where under-reporting forfeits
      relief. Say explicitly that it is **false** of D7's cap and of the
      two-dry-rounds clause, where under-reporting is the block-dodging direction
- [ ] **2.** (21) Record the accepted gap: an untagged sibling escapes the cap, and
      that is a known cost of not charging blast-radius and lens findings to a round
- [ ] **3.** (21) ⚠️ **Do not change the population.** The ruling is explicit. If
      the narrowed comment makes the gap look intolerable while writing it, that is
      a new question for Jon, not a licence to close it
- [ ] **4.** (24) Document the scope where `hardening_batch.check()`'s four
      refusals are enumerated, and **correct the docstring** — *"a diff that has not
      been used before is the work"* claims more than the check enforces, and the
      docstring is the defect
- [ ] **5.** (24) ⚠️ **Do not add a module-touching requirement.** Batch closure is
      D35's intent and the commit message must already name every id

### Validation

- [ ] **V1** (21) The narrowed comment is diffed against the SQL as two independent
      claims, and they now agree **for each conjunct separately**. Evidence: ___
- [ ] **V2** (21) `test_round_item_cap.py:105,117` keep asserting the mechanism (they
      are right about it) and gain a docstring naming the accepted cost — so the
      next reader sees a decision, not an oversight. Evidence: ___
- [ ] **V3** (21) The round-cap **behaviour is unchanged** — assert it, so the
      comment edit cannot have quietly moved the predicate. `test_round_item_cap.py`
      passes untouched except for the added docstrings. Evidence: ___
- [ ] **V4** (24) A test asserting the four refusals **and explicitly asserting the
      fifth is not checked**, with the corrected docstring quoted in the test. That
      is what converts an overclaim into a recorded decision. Evidence: ___
- [ ] **V5** (24) `hardening_batch.check()` **behaviour is unchanged** — same
      assertion discipline as V3. Evidence: ___
- [ ] **V6** `enforcement_lint` H8 → exit 0. Evidence: ___
- [ ] **V7** `git show --stat` for this commit touches **no** `.toml` predicate and
      **no** SQL. If it does, the ruling was exceeded. Evidence: ___

---

## W30 — Item 23: three-wide dispatch has no rework path when `--ff-only` refuses

**Status:** `TODO`  ·  **Tier:** D  ·  **Depends on:** W12 (file order, not logic)
**Commit:** `fix(fix-loop): write the rework path, and stage explicitly`

*Last in P4 because it edits `phase-fix-loop.md`, which W03 and W12 step 4 also
edit. Order is W03 → W12 → W30; by the time you are here the line numbers below
have moved, so match on text.*

### Defect

`phase-fix-loop.md:44` launches three subagents; each rebases onto the branch as it
stood when *it* finished (`:58-63`) and the orchestrator merges `--ff-only` one at
a time (`:77`). When A's merge lands after B has already rebased, B's branch no
longer fast-forwards. The doc says *"A refusal means the subagent's rebase is
stale; send it back"* and stops there.

**What "send it back" must include is unwritten:** B must re-rebase **and** re-run
`verify_suite.py --record`, because `:67` already establishes that the rebase moves
the tree and therefore invalidates the recorded `suite_green`. A subagent sent back
that only rebases produces a fix the orchestrator's step 11 will reject **for a
reason that looks like the fix being unreal.**

Also on that path: `:60` is `git add -A && git commit` — the idiom this repo has a
standing rule against, and in a worktree it means whatever else the subagent left
in its tree rides the fix commit.

### Plan

- [ ] **1.** Write the rework path into `phase-fix-loop.md`: re-rebase, **then**
      re-record the green, then hand back
- [ ] **2.** Replace `git add -A` with explicit paths

### Validation

- [ ] **V1** A test over the document's own step order: re-rebase precedes
      re-record, and re-record precedes hand-back. Evidence: ___
- [ ] **V2** `test_fix_loop_worktree_merge.py` gains the refused-`--ff-only` case: B
      is sent back, re-rebases, re-records, and step 11 accepts. Evidence: ___
- [ ] **V3** A subagent that re-rebases **without** re-recording is rejected — the
      failure mode must stay detectable, and its message must not look like "the fix
      is unreal". Evidence: ___
- [ ] **V4** Grep `phase-fix-loop.md` for `git add -A` → zero hits. Evidence: ___

---
---

# Appendix A — item → unit index

| Item | Unit | Item | Unit | Item | Unit |
|---|---|---|---|---|---|
| 1 | W04 | 18 | W16 | 35 | W10 |
| 2 | W05 | 19 | W04 | 36 | W18 |
| 3 | W07 | 20 | W06 | 37 | W13 |
| 4 | W23 | 21 | W29 | 38 | W20 |
| 5 | W14 | 22 | W17 | 39 | W25 |
| 6 | W24 | 23 | W30 | 40 | W19 |
| 7 | W23 | 24 | W29 | 41 | W20 |
| 8 | W23 | 25 | W09 | 42 | W11 |
| 9 | W21 | 26 | W09 | 43 | W08 |
| 10 | W14 | 27 | W22 | 44 | W24 |
| 11 | W25 | 28 | W12 | 45 | W27 |
| 12 | W28 | 29 | W02 | 46 | W27 |
| 13 | W23 | 30 | W15 | 47 | W19 |
| 14 | W23 | 31 | W03 | 48 | W26 |
| 15 | W27 | 32 | W08 | 49 | W25 |
| 16 | W28 | 33 | W18 | | |
| 17 | W13 | 34 | W12 | | |

# Appendix B — what this worklist does not do

- **It does not re-rank anything.** Tiers are the punchlist's. Where units group
  items it is for dependency and shared-fixture reasons, stated at each unit.
- **It does not decide the seven open questions.** Recommendations are marked as
  such; both branches are specified so neither is the default by accident.
- **It does not assert that anything passes.** No gate has been run against a fix,
  because no fix has been written. Every `Evidence:` slot is empty on purpose.

# Remediation plan — release review punchlist (v0.141.3 → 0.169.1 @ `48c72fd`)

Companion to `docs/superpowers/plans/2026-08-26-release-review-punchlist.md`.
**That file is the finding record and is read-only from here** — it is the only
document that can answer "what did the review actually say," and editing it
destroys that ([[never-edit-the-spec-you-are-implementing]]). This file adds the
two things it does not carry: an **actionable plan** and **validation criteria**
for each of its 49 items.

Item numbers, titles and tiers are the punchlist's. Nothing here re-ranks,
retracts, or restates a finding. Where the punchlist already prescribes a fix,
this file keeps it verbatim in intent and adds the steps and the checks; where it
prescribes none (25 of 49 items), the plan is authored here and says so.

**Where a fix requires a design choice the review did not settle, this file does
not choose.** Seven such choices are listed under *Decisions owed* and each one's
entry carries both branches, costed, so implementation is unblocked the moment
the ruling lands ([[deviation-from-plan-requires-asking]]).

---

## Verification status of this plan

Every file:line anchor cited below was re-read against the tree at `48c72fd`
while writing this plan. Nothing here is taken from the punchlist on trust.
Two things changed as a result:

- **Item 15 is now observed, not inferred.** The punchlist's tier list asked
  someone to check whether the undeclared `hypothesis` dependency breaks a
  fresh checkout's collection. It does. With the interpreter that a fresh
  clone would use:

  ```
  $ python3 -m pytest tests/test_property_based.py --collect-only -q
  E   ModuleNotFoundError: No module named 'hypothesis'
  ERROR tests/test_property_based.py
  !!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!
  ```

  `.venv` has `hypothesis 6.156.6`, which is why every gate observation in the
  punchlist is green and this is still true. Local and CI do not run the same
  set on a fresh machine.
- **Item 30 gains an implementation hazard the review did not name.** See its
  entry: the single-owner splitter cannot simply add `&` to the character
  class, because `2>&1` would then split mid-redirect. The strip-then-split
  order is load-bearing and is written into the plan.

Everything else was confirmed as written, including the five `cwd`-relative
probes (29), the three-way `NotebookEdit` disagreement (40), the absent
`_sahjhan_bootstrap.py` manifest entry (47), and `deferred.md.tera`'s missing
`resolved_ids` against `punchlist.md.tera:21`, which has it (44).

---

## How to read an entry

```
#### N. Title · Tier
**Defect** — one line, with the anchor.
**Plan** — numbered, each step naming the file it edits.
**Validation** — numbered, each an observable check with a pass criterion.
**Decision owed** — only when present; implementation is blocked on it.
```

**Validation criteria in this file are observations, not predictions.** A step
that says "expect exit 0" is satisfied by a pasted exit 0 and by nothing else
([[CLAUDE.md — Before claiming anything works]]). Every entry whose fix changes
a predicate also carries a **non-vacuity** step: mutate the fix, re-run, confirm
RED, revert. A test that passes before the fix proves nothing
([[mutation-proof-the-negatives-too]]).

---

## Standing gates — what "green" means

Run from the repo root. `.venv/bin/python` is used explicitly so the check does
not depend on whether the shell is activated.

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

Two rules that are not optional and have each cost real time:

1. **After editing any hook listed in `scripts/hash-trusted-callers.sh`, run
   `bash scripts/hash-trusted-callers.sh` before any `real_daemon` test.** A
   stale hash makes every gate fail *open* while the hook still exits 0, so the
   suite goes green for the wrong reason ([[trusted-callers-manifest-regen]]).
   `git-hooks/pre-commit` self-heals a real commit; a manual test run does not.
2. **Do not bisect against a failure you have not seen three times unchanged.**
   The bash TDD gate times out at 5 s under concurrent pytest, so a single red
   under load is not evidence ([[dont-bisect-against-a-load-flaky-test]]). This
   is item 17/37's mechanism, and it will be live during this work.

`-p no:randomly` is specified because the punchlist's own gate observation
distinguishes a sequential exit 0 from a concurrent run with two failures.

---

## Three fixtures unlock eleven items

Eleven items are unfixable-with-confidence today for the same reason: **no test
anywhere constructs the situation they break in.** Build these first; they are
the missing test classes, and they are cheap relative to the items that depend
on them.

### F1 — `worktree_cwd`: a hook subprocess whose cwd is a linked worktree

*Unlocks 29, 47; needed by 42 and 35 to be realistic.*

A temp git repo with `docs/holtz/.sahjhan/` gitignored and populated, plus
`git worktree add` producing a linked checkout that (correctly) lacks that
directory. Hook events are driven through the existing `_run_hook` subprocess
helper with `cwd` set to the worktree.

Scrub `GIT_DIR` / `GIT_INDEX_FILE` from the subprocess env — they leak from the
enclosing git hook and make `git worktree add` exit 128 under pre-commit only
([[git-hook-env-leaks-into-test-subprocesses]]).

**Pass criterion for the fixture itself:** with no product change, a
`bash_guard.py` event at the worktree cwd returns `allow` and one at the main
checkout returns the manifest-verify path. That asymmetry *is* item 29; the
fixture is correct when it reproduces it.

### F2 — `two_actors`: two agent_ids interleaved before either courier fires

*Unlocks 19, 1, 32, 35, 42.*

Drive actor A and actor B through record → courier → edit in the order the
three-wide loop actually produces: **both `test_failed_before_fix` rows land
before either courier runs.** Every existing courier test drives one actor, which
is why five separate defects in this family all shipped green.

**Pass criterion for the fixture:** it must be able to express "A's evidence row
names A's finding" as a positive assertion. Asserting `len(rows) == 2` or
`A != B` is what let items 19 and 32 through — choose fixture data where every
plausible quantity gives a different number.

### F3 — `taught_command_fields`: the engine's opinion of a taught command

*Unlocks 31, 34; second layer for 26.*

For each `sahjhan event <type> --field …` string extracted from a skill file or
a `hooks.toml` message, assert the field set satisfies `events.toml`'s required
fields for that type. Static, no daemon, runs in CI. The real-daemon form
(`--field` missing → `error: missing field '<name>'`, exit 4) is the second
layer, marked `real_daemon`.

This is the gap `contract_gate.py` structurally cannot see: it asks "does the
hook allow this string," never "does the engine accept its fields"
([[test-the-taught-sequence-not-just-the-gate]]).

---

## Decisions owed (Jon) — 7

Implementation of these items is blocked, not slowed. Each entry below carries
both branches so the work starts the same day the ruling lands.

| # | Item | The choice | This plan's recommendation |
|---|---|---|---|
| D-a | **2** | MEDIUM budget: assert "not under-spent relative to what is still open", or make the denominator count only ever-deferrable findings | Denominator — it fixes N=1, spend-before-fix and late-refile in one predicate |
| D-b | **6** | `DEFERRED.md`: drop the `finding` render trigger, or replace the converge conjunct with a ledger predicate over deferrals | Both — they are independent defects that happen to share a symptom |
| D-c | **9** | `merge_finding`: constrain by severity, by relatedness, or leave loose and document | Severity floor (target ≥ item) — relatedness is not machine-checkable here |
| D-d | **20** | Merged findings: attribute to a real lens during the merge, or accept `unspecified` as deliberately converge-only | **Blocks item 3.** Decide before the lens gate lands, not after |
| D-e | **21** | Untagged siblings escaping the round cap: close the gap, or narrow `protocol.toml`'s claim and record the acceptance | Narrow the claim — the punchlist is explicit that a hasty fix charges lens findings for blast radius |
| D-f | **24** | Hardening batch's diff not required to touch the module: enforce, or document as deliberate | Document — it is arguably within D35's intent, and the docstring is what overclaims |
| D-g | **44** | `STATUS.md` render timing (`on_transition`) leaving counts stale between transitions | Add `on_event` for the finding family; nothing gates on it, so the cost is render churn only |

Two of these have a hard ordering consequence: **D-d blocks item 3** (the lens
gate cannot be scoped by lens while a large slice of the board carries a
perspective no lens gate names), and **D-a changes the shape of item 2's test
matrix**, not just its predicate.

---

# Tier A — a good-faith run hits these; fix before functional testing

#### 29. Worktree path resolution disables enforcement for the three subagents · PROVEN

**Defect** — five sites probe `os.path.isdir(cwd/docs/holtz/.sahjhan)` to decide
"is an audit active here": `bash_guard.py:49`, `_common.py:171`,
`_common.py:427` (`_read_init_pid`), `_common.py:458` (`_write_terminated_marker`),
`_sahjhan_bootstrap.py:367`. In a linked worktree that directory does not exist
(it is gitignored), so the probe is False while the daemon is fully reachable.
`_common.boundary_dir:278` already resolves the socket through `project_anchor`
— the anchor exists and was simply not used next door.

**Plan**

1. Add one named helper to `_common.py`, beside `boundary_dir` and defined in
   terms of the same anchor, so there is one expression of the fact rather than
   two careful copies ([[enforcement-name-the-fact-not-the-text]]):
   ```python
   def audit_data_dir(cwd: str) -> str:
       return os.path.join(project_anchor(cwd), "docs", "holtz", ".sahjhan")

   def audit_active(cwd: str) -> bool:
       return os.path.isdir(audit_data_dir(cwd))
   ```
2. Replace all five probes with `audit_active(cwd)` / `audit_data_dir(cwd)`.
   `_sahjhan_bootstrap.py` must keep its lazy-import discipline (it is
   deliberately import-free at module level so a broken sibling cannot disable
   the bootstrap guards) — import inside the function.
3. Fix the courier's run attribution: `verify_suite._run_number(cwd)` (`:316-323`)
   reads `cwd/docs/holtz/.sahjhan/active-ledger` and returns `"0"` in a worktree.
   Point it at `audit_data_dir(cwd)`. Same for the courier's `project` field.
4. Re-run `bash scripts/hash-trusted-callers.sh` — this edits `_common.py`,
   `bash_guard.py` and `_sahjhan_bootstrap.py`, three manifest-listed callers.

**Validation**

1. **F1 required.** New `hook_e2e` test: `bash_guard.py` at a worktree cwd
   performs manifest verification rather than `exit_ok()`.
2. `_common.exit_enforcement_error` at a worktree cwd **denies**, matching the
   main checkout. The punchlist's own observation is the acceptance criterion:
   `nodir → allow`, `withdir → deny` must become `deny → deny`.
3. `sahjhan daemon stop` from a worktree cwd is **blocked** by
   `_daemon_stop_permitted`.
4. `suite_courier` at a worktree cwd writes `run=<the real run number>` and
   `project=<the anchored project>`, **not** `run="0"` and not the worktree
   directory name. Assert the recorded value equals the main checkout's.
5. Non-vacuity: revert step 1's helper to `cwd`-relative; checks 1–4 must all
   go red. If any stays green it is asserting the wrong thing.
6. `pre_tool_hook.py`'s docstring claim — "Fails closed during active audits if
   the daemon is unreachable" — becomes true for a worktree actor. Assert it
   directly: worktree cwd + unreachable daemon → `deny`.

---

#### 31. The taught TDD record and the gate's own escape omit required fields · PROVEN

**Defect** — `events.toml:602-607` requires `finding_id, test_name, project, run,
auditor` on `test_failed_before_fix`. `phase-fix-loop.md:52` and the TDD block
message at `hooks.toml:30` teach only `--field finding_id= --field test_name=`.
`SKILL.md:156` teaches the full form (`--field project=holtz --field run=N`) for
`fix_start`, so the two files disagree. `sahjhan event` does not inherit run
context — only `emits` do — so the taught command exits 4 and the printed escape
cannot run as written. This is #77's unsatisfiable-escape shape on the *first fix
of every run*.

**Plan**

1. Bring the taught form to the full field set in `phase-fix-loop.md:52`, using
   `SKILL.md:156`'s spelling verbatim so the two files stop disagreeing.
2. Same edit to the `hooks.toml:30` block message. This is the printed escape;
   it is the one a blocked agent actually copies.
3. Same for the five other inline-backtick `sahjhan event` commands in
   `phase-fix-loop.md` — `:7` `reference_read`, `:50` and `:167` `fix_start`,
   `:55` `blast_radius`, `:57` `hardening_complete`, `:115` `finding`. Check each
   against its own `events.toml` stanza; do not assume they need the same fields.
4. Extend `contract_gate.py:37 extract_sahjhan_commands` to inline backticks, not
   just fenced blocks. This is why `:52` was never checked.
5. Add F3's field-validation check to the gate: a taught command missing a
   required field is a gate failure.

**Validation**

1. `.venv/bin/python scripts/contract_gate.py` → exit 0, and the reported command
   count **increases** (it now sees inline backticks). Record the before/after
   count; an unchanged count means step 4 did not take effect.
2. F3 static check passes for all six commands.
3. `real_daemon`: run the exact string from `phase-fix-loop.md:52` against the
   binary → exit 0. Before the fix the same string gives
   `error: missing field 'project'`, exit 4 — capture both.
4. Non-vacuity: delete `--field project=` from the taught form; the F3 check
   must go red.
5. Assert `hooks.toml`'s message and the skill file's step 3 carry the **same**
   field set — a test over both strings, so they cannot drift apart again.

---

#### 19. The TDD courier pairs the wrong actor's failing test · PROVEN

**Defect** — `tdd_courier.py:61-66`. `_UNPAIRED` selects the newest
`test_failed_before_fix` on the *whole ledger* past a run-global `tdd_evidence`
watermark and stamps the caller's `agent_id` on it. With three actors in flight
this is the normal interleaving, not an edge case: A gets B's row, B gets a
warning, and `LIMIT 1` loses the older row permanently.

**Plan**

1. Pair by the row, not by a global watermark. The command text carries
   `--field finding_id=…` and the courier already refuses anything but a single
   canonical segment, so parse the id and scope both halves of the window to it:
   ```sql
   WHERE type='test_failed_before_fix' AND finding_id=<id>
     AND seq > COALESCE((SELECT MAX(seq) FROM events
                         WHERE type='tdd_evidence' AND finding_id=<id>), 0)
   ```
2. Keep reading the remaining fields (`test_name, run, auditor, project`) off the
   selected row, so the courier still invents nothing.
3. Leave the single-segment rule alone — but see item 34, which makes its silent
   failure audible. These two land together or 34 masks 19's own regression test.
4. Re-run `bash scripts/hash-trusted-callers.sh`.

**Validation**

1. **F2 required.** Two actors, both rows landing before either courier fires:
   assert `tdd_evidence where agent_id='agent-A'` names **A's own finding**, and
   the same for B. Both actors hold exactly one row.
2. The punchlist's observed failure is the regression fixture — A holding
   `finding_id: BH-002 / test_name: test_B` must become impossible.
3. Delete `test_it_takes_the_newest_unpaired_row` in `test_tdd_courier.py`. It
   asserts the defect as intended behaviour (a string match on the SQL), so it
   will fail on a correct fix and must not be "repaired" into asserting the new
   SQL string — replace it with the behavioural test in check 1.
4. Non-vacuity: restore the global watermark; check 1 must go red for **both**
   actors, not just one.
5. Assert no row is lost: two unpaired rows, two couriers → two evidence rows.

---

#### 1. A sibling's `fix_commit` revokes a still-working actor's TDD evidence · PROVEN

**Defect** — `enforcement/hooks.toml:32-36`. D33 scoped the gate's **filter** to
`agent_id` and left the **window** at `since = "last_transition"`, which is
run-global. The orchestrator records a `fix_commit` every time any subagent
lands, so every other in-flight subagent loses its own authorisation — and its
escape (re-record a failing test) is not reachable once its fix is written.

**Plan**

1. **First, establish whether the engine can express this.** Check whether
   sahjhan's `ledger_has_event_since` supports an actor-scoped window
   (`last_transition` by `agent_id`). Run it against the vendored binary; do not
   infer it from docs ([[verify-harness-facts-against-the-binary]]).
2. If it can: scope the window to the actor in `hooks.toml`.
3. **If it cannot, the fix is in sahjhan, and that is the correct place for it.**
   Do not route around it with a holtz-side mirror of the transition log — that
   is the shape [[enforcement-derive-from-ledger-not-mirror]] forbids and it
   would put two expressions of one window in the tree. Ship the engine change
   and bump the pin ([[fix-root-cause-dont-route-around]],
   [[sahjhan-version-pinned-in-three-places]] — three places, and
   `_resolve.SAHJHAN_VERSION` governs).
4. Land with item 19: 19 fires first (before any `fix_commit` exists to revoke),
   they share F2, and one test drives both.

**Validation**

1. **F2 required.** The missing `hook_e2e` test the punchlist names: an actor
   holding its own evidence **survives** a sibling's `fix_commit` transition.
   Drive record → edit(allow) → sibling `fix_commit` → edit(**still allow**).
2. The punchlist's observation is the regression fixture: agent-B's second edit
   returning `deny` with the TDD-violation message must become `allow`.
3. The gate must still bite: an actor with **no** evidence is denied after a
   sibling's transition. A window fix that allows everyone is worse than the bug.
4. Non-vacuity: revert to `last_transition`; check 1 goes red and check 3 stays
   green.
5. If step 3's engine path was taken: `bin/.sahjhan-version`,
   `_resolve.SAHJHAN_VERSION` and `bin/sahjhan --version` all agree, and
   `.venv/bin/python scripts/check_sahjhan_pin.py` → exit 0.

---

#### 2. Fixing more than half your MEDIUMs strands `converge` forever · PROVEN

**Defect** — `protocol.toml:259` + `transitions.toml:553`. `converge` requires the
MEDIUM deferral budget **spent**: `deferred >= N/2` where N counts every MEDIUM
ever filed, open or closed, while `defer_medium` requires `item_open`. So
converging requires *exactly* `floor(N/2)` deferrals, it is vacuous at N=1,
binding from N=2, the budget must be spent **before** the MEDIUMs are fixed, and
a late-filed MEDIUM can re-block an already-open converge.

**Decision owed — D-a.** Two branches:

- **(i) Denominator** — count only findings that were ever deferrable
  (open at the time, or never resolved). Fixes N=1, spend-before-fix and
  late-refile in one predicate. *Recommended.*
- **(ii) Relative** — assert the budget is not under-spent *relative to what is
  still open*. Smaller diff; leaves the spend-before-fix ordering trap intact,
  which is the half no skill file describes.

**Plan** (both branches)

1. Edit the named query in `protocol.toml`; both `defer_medium`'s cap and
   `converge`'s conjunct must read the **same** named query so the two can never
   disagree (H7/H8 enforce this — let the linter confirm it).
2. Fix `medium_deferral_budget`'s `intent` string, which today says the opposite
   of what the gate requires ("half the MEDIUMs get fixed, not deferred" — the
   gate requires half *deferred*). This is item 11's entry for this gate; do it
   here where the predicate is in hand.
3. If branch (i): state the new denominator in the skill file, because the
   ordering constraint it removes is currently taught nowhere.

**Validation**

1. **Cover the whole domain of N, not the reported case.** A `real_daemon`
   parametrised test over N = 1, 2, 3, 6:
   - N=1 with 0 deferrals → converge passes (today: passes, vacuously).
   - N=2..6 with 0 deferrals → today blocked; after the fix, the branch's
     intended answer, asserted explicitly per N.
2. **The reachability case, which is the bug:** N=6, 5 resolved, 1 deferred,
   `open_medium_findings` = `[]` → converge must pass. This is the punchlist's
   observed strand and is the acceptance criterion.
3. **Late-refile:** N=6 with the budget spent, then file MEDIUMs 7 and 8 →
   assert the ruled behaviour (branch (i): still open; branch (ii): document
   that it re-blocks and name the escape).
4. Escape reachability: for every N where the gate blocks, drive the **named
   escape command** against the real transitions and assert the predicate flips
   ([[enforcement-block-escape-by-construction]]). Asserting the SQL alone
   proves the block and never the way out.
5. Non-vacuity: revert the predicate; checks 1–3 go red.

---

#### 3. `all_findings_closed` still gates `set complete perspective` · PROVEN

**Defect** — `transitions.toml:472`. P0.1 removed this conjunct from `converge`
as unreachable; the identical named query still sits on `set complete
perspective`, which must pass **13 times** before `converge` is evaluated. It
carries no reachability filter, so one open `fault_injected` HIGH blocks a lens
while being un-`fix_commit`-able, and it has **no `intent`**, so the block prints
no escape.

**RULED (Jon, 2026-08-26): option (a), the lens-scoped package.** A clean lens is
not an empty board.

**Blocked on D-d (item 20).** A lens-scoped gate with `unspecified` unrouted
moves the whole merged board silently to `converge`.

**Plan**

1. Add two named queries to `protocol.toml [queries]`, both parameterised on
   `{{current_perspective}}` — the binding `set complete perspective` already
   uses. Shape them on `all_critical_resolved` /
   `all_user_reachable_high_closed` plus one `f.perspective = '…'` term and the
   same max-seq correlation, so severity and reachability stay graded by latest
   filing (D25).
2. Delete `all_findings_closed` from the transition. It then has no consumer in
   `transitions.toml` — run `enforcement_lint` H1 and let it tell you whether to
   keep the query declared for `findings.py`/render use or drop it.
3. Give the gate an `intent` naming a command. H8 note: these are parameterised,
   so `_run_wide()` drops them from escape identity — the intent still must name
   a command, it is just not judged against a named query.
4. Whatever D-d rules, write it into `merge-protocol.md`. Both branches need the
   sentence; only one needs code.

**Validation**

1. **Extend `TestEveryCriticalHasARoute` to this transition**, driven against a
   real daemon for **all three** reachability grades, as the `converge` version
   does. This is the invariant: no grade of finding may be un-closable at a gate
   the run must pass thirteen times ([[enumerate-every-escape-a-gate-rejects]]).
2. Lens 3 blocks on its own open CRITICAL; lens 3 **passes** with lens 1's
   MEDIUM open. Both asserted — the second is the ruling.
3. The accepted cost, asserted so it is not later rediscovered as a bug: a
   finding filed under an already-completed lens is caught only at `converge`.
   Write the test that proves `converge` catches it.
4. One open `fault_injected` HIGH no longer blocks a lens (the item's second
   consequence), and is still caught by `no_open_fault_injected` at `converge`.
5. The gate's block prints an escape, and that escape runs. Not "has an intent
   string" — run it.
6. Non-vacuity: restore `all_findings_closed`; checks 2 and 4 go red.

---

# Tier B — corrupts the run's record or weakens enforcement mid-run

#### 32. `unregistered_commits` cleared by command text, no success check, over every actor · PROVEN

**Defect** — `protocol_tracker.py:217-222`. `_runs_transition(cmd, "fix_commit")`
is pure `cmd.split()` adjacency, and the branch sets
`cache["unregistered_commits"] = {}` for **every** actor. `exit_code` is computed
at `:250` and consulted only in the git-commit branch, so a *refused* transition
(exit 1) still discharges the block — as does `echo remember to run transition
fix_commit`. Two defects stacked: no success check, and a run-global clear whose
own comment (`_protocol_cache.py:610-612`) argues only the merged subagent's
bucket. D41 keyed the *charge* per actor and left the *clear* global — the
deny-direction was fixed, the allow-direction, which is the one that loses
enforcement, was not.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Gate the clear on success. `bash_exit_code(event)` is already in scope at
   `main()` — thread it into `_apply_sahjhan_cmd` and clear only on exit 0.
   H7/H8 already enforce this shape five lines above for
   `pattern_analysis_overdue`; this path simply never got it.
2. Decide the clear's scope from the ledger, not from the cache. The transition
   registers the commit at HEAD; ask sahjhan which commit that is and clear the
   bucket holding it, rather than clearing all buckets because the orchestrator
   cannot name the author. If the ledger cannot answer, clear the orchestrator's
   bucket only — losing a clear costs a nudge, losing the charge loses the gate.
3. Rewrite `_protocol_cache.py:610-612`'s comment to match whatever step 2
   lands. Today it argues a position the code does not implement, which is the
   [[comment-argues-predicate-decides]] shape that hid this.

**Validation**

1. **F2 required**, seeded as the punchlist drove it:
   `{"agent-a":["a1"],"agent-b":["b1"],"":["c1"]}` — three buckets, three
   commits, so no count can coincide.
2. A `transition fix_commit` the engine **refuses** (exit 1) clears **nothing**.
3. `echo remember to run transition fix_commit` clears **nothing**.
4. A successful `fix_commit` clears the bucket it discharges and leaves the other
   two charged. Assert the two survivors by name, not by `len()`.
5. `test_unregistered_commit_actor.py:164` asserts the global clear as intended
   and must be rewritten, not deleted — it is the guard for step 2's new rule.
6. Non-vacuity: remove the exit-code check; check 2 goes red. Restore the global
   clear; check 4 goes red.

---

#### 25. The merge destroys the reachability grading of every finding Justine escalates · PROVEN · P0

**Defect** — `merge_punchlists.py:336-339`. `_HOLTZ_SQL` does not select
`reachability`, `pattern_id` or `predicted_by`, so `holtz_findings()` builds every
`Finding` with `DEFAULT_REACHABILITY = "theoretical"` (`:66`), and `apply_merge()`
re-files the escalated finding with that default. The re-file happens **only on
escalation** — the path that exists to say *this is worse than you thought* is
the one path that destroys the finding. D25 grades by latest filing, so the board
now reads `theoretical`; the theoretical courier sweeps it in the same Bash call;
`all_critical_resolved` reads `true`; and `item_is_user_reachable` refuses to let
`fix_commit` touch it ever again.

**Plan**

1. Read the whole row: add `reachability`, `pattern_id`, `predicted_by` to
   `_HOLTZ_SQL`, carry them onto `Finding`, and have `_record` (`:401`, which
   hard-codes `predicted_by="none"`) pass them through rather than defaulting.
2. Confine `DEFAULT_REACHABILITY` to where a grading was genuinely never stated —
   Justine's punchlist — and never to a Holtz row that has one on the ledger.
3. Land with item 26, which closes the other end of the same pipeline.

**Validation**

1. **Assert a re-file changes `severity` and *nothing else*.**
   `test_a_higher_justine_severity_refiles_holtz_id`
   (`tests/test_merge_punchlists.py:538`) asserts `len(filings) == 2` and
   `severity == "HIGH"` and never reads `reachability` off the second filing —
   the exact [[mutation-proof-the-negatives-too]] shape. Rewrite it to compare
   the two filings field by field.
2. The punchlist's real-daemon trace is the acceptance criterion. After the fix:
   `seq 2  BH-001  CRITICAL  user_reachable` — not `theoretical`.
3. `open_theoretical_findings` does **not** name BH-001 after the merge;
   `all_critical_resolved` reads **false**; `finding_deferred` is not emitted.
4. `pattern_id` survives, so the escalated sibling stays in its round's
   population and the merge stops silently discharging round-cap pressure
   (item 21's join).
5. `predicted_by` survives, so `SUMMARY.md`'s Prediction Accuracy table is
   computed from a real link.
6. Non-vacuity: revert `_HOLTZ_SQL`; checks 1–5 go red.

---

#### 26. Nothing requires Justine to grade reachability · PROVEN · P1

**Defect** — `justine_findings()` takes `item.reachability or
DEFAULT_REACHABILITY`, so an ungraded item lands `theoretical` and is
auto-deferred on arrival. The field is required by `events.toml` (whose comment
argues it at length) and by neither of the two things that produce it:
`validate_punchlist.py` never mentions it, and the word does not appear in
`justine-skill.md` at all.

**Plan**

1. `validate_punchlist.py` errors on a missing `**Reachability:**`, alongside the
   severity/category/status/Problem/Discovery-Chain checks it already makes. This
   makes the merge's default unreachable in practice and matches `events.toml`'s
   own claim about the field.
2. `justine-skill.md` says the word once, next to its severity-calibration
   override — it is the file that tells her how to grade and is silent on the
   grading that decides whether anything gets fixed.
3. Land in the same commit as item 8 (`SKILL.md`'s deferral rules) — same shape,
   same sweep.

**Validation**

1. `validate_punchlist.py` on a punchlist item with no `**Reachability:**` line →
   non-zero exit naming the field.
2. The shipped fixture reproduces the bug: `_JUSTINE`'s BJ-002 carries no
   reachability. It must now fail validation, so the fixture needs a grading
   added — **and that edit is the proof**, so record it in the commit message
   rather than quietly fixing the fixture.
3. `test_an_unstated_reachability_is_theoretical` asserts the default as correct.
   Keep it as a unit test of the *default*, and add the pipeline test that says
   an ungraded item never reaches the merge.
4. `real_daemon`: a Justine-only CRITICAL with no reachability line no longer
   lands as `reachability=theoretical, perspective=unspecified` and is not swept
   by the courier on the same command.
5. Non-vacuity: remove the new validator check; check 1 goes red.

---

#### 35. `stale_sweep`'s population window is a run-global transition watermark

**Defect** — `stale_sweep.py:69-80`. `_POPULATION_SQL` scopes "this sweep" to
`seq > MAX(seq of any state_transition)`. The docstring calls that "the same
window `defer_cant_reproduce`'s own gate uses" — true, and both are run-global.
In a three-wide loop the orchestrator records a `fix_commit` transition every
time a subagent lands, so a sibling landing mid-sweep advances the watermark past
retirements already recorded: `check` reports "verdicts name findings this sweep
does not cover," the courier warns, nothing is recorded. Both the script and the
courier's re-derivation (`stale_sweep_courier.py:126`) read the same window, so
the courier cannot rescue it. This is D41 / item 1 a third time.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Scope the window to the sweep, not the run. The sweep has an identity —
   define its start as the sweep's own first recorded event rather than as
   "whatever transition happened last," so a sibling's `fix_commit` cannot move
   it.
2. Keep the script and the courier reading **one** named window, imported not
   restated — the discipline both files already claim in their comments
   ([[enforcement-name-the-fact-not-the-text]]).
3. Fix the docstring's "same window as `defer_cant_reproduce`" claim, or make it
   true by moving that gate to the same named window. Do not leave the comment
   asserting a correspondence the code no longer has.

**Validation**

1. **F2 required.** A sweep that retires findings, then a sibling `fix_commit`
   lands mid-sweep, then `--record`: the retirements are still covered and the
   sweep records. Today the courier warns and writes nothing.
2. The non-adjacent case: the sibling's transition sits **between** two of the
   sweep's own retirements, not after both. A window bug that only shows up when
   the interleaving is adjacent is the [[enforcement-sql-limit-is-not-a-window]]
   trap — write the seq floor, and test the non-adjacent case explicitly.
3. Courier and script agree: assert they resolve the same population for the
   same ledger, by construction (same named query) and by test.
4. Non-vacuity: restore the run-global watermark; checks 1 and 2 go red.

---

#### 42. Per-actor cache state is read-modify-written over the whole map

**Defect** — `protocol_tracker.py` both writers send the entire actor map computed
from a snapshot read up to ~10 s earlier: `update_cache` with `stall_bumped`
(`:295-297`), and `_apply_sahjhan_cmd`'s full `write_cache` (`:235`) after two
5 s subprocesses. The daemon does a shallow top-level merge, so a sibling's
bump/clear/commit landing in that window is overwritten. The actor-keying the
delta added is not atomic. The docstrings claim "every other actor untouched" —
true of the returned value, false of the write.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Make the write per-actor rather than whole-map: send the delta for one actor
   and let the daemon merge, instead of computing the full map client-side and
   overwriting. This is the smallest change that removes the lost update.
2. If the daemon's op cannot express a per-actor merge, that is a sahjhan change
   — take it there rather than adding a client-side compare-and-swap loop that
   would still race ([[fix-root-cause-dont-route-around]]).
3. Correct the two docstrings to describe the write, not the return value.

**Validation**

1. **F2 required.** Interleave: A reads → B bumps and writes → A writes. B's bump
   survives. This is a concurrency test, of which the tree currently has none for
   this path.
2. The same for the three writers that collide: `stall_bumped`, `stall_cleared`,
   and `pending_commits_appended`.
3. Choose fixture counts where "buckets" and "commits" differ, so a `len()` over
   the wrong dimension cannot pass by coincidence.
4. Non-vacuity: restore the whole-map write; check 1 goes red.
5. If step 2's engine path was taken: re-pin and `check_sahjhan_pin.py` → exit 0.

---

#### 43. The pending-commit block names an escape the blocked subagent cannot run

**Defect** — `commit_gate.py:78-89`. The comment justifying actor-scoping ends
"the escape named below is the orchestrator's transition, which a subagent cannot
run," and the `exit_block` immediately below prints exactly that escape. D41
actor-scoped the block and left the escape orchestrator-only. Today it clears only
as a side effect of someone else's merge — which is item 32, i.e. the escape is a
bug.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Print an escape the blocked actor can run. A subagent's second commit (the
   item-23 rework path) lands here; it needs a route to registration that does
   not require the orchestrator's transition.
2. If no such route exists, that is a **missing escape and a question for Jon**,
   not a licence to narrow the block ([[enumerate-every-escape-a-gate-rejects]]).
   Say so explicitly rather than shipping a better-worded dead end.
3. Land with item 32 — 32 is what makes the current escape "work," so fixing 32
   first turns this from a bad message into a hard block.

**Validation**

1. `hook_e2e`: a subagent's second commit is blocked, and the printed escape is
   then **executed as printed** and clears the block. Not "the message names a
   command" — run it ([[enforcement-block-escape-by-construction]]).
2. The orchestrator's path is unchanged.
3. Non-vacuity: revert; check 1's escape must fail to clear.
4. `enforcement_lint` H8 still passes — the block names the query its escape is
   gated on.

---

#### 34. Couriers go silent when a script's CLI accepts what its recognizer refuses · extends 28

**Defect** — at least four scripts, one with a worse consequence than item 28
described:
- `hardening_batch.py:359` accepts `--cwd`; `module_of_command` rejects it →
  `exit_ok()` with no warning while the module's `fault_injected` findings stay
  open and `no_open_fault_injected` blocks `converge` at Step 15.
- `tdd_courier.py:76-80` requires a single shell segment and exits silently
  otherwise (`:90`) — and unlike `verify_suite`/`pattern_round`/`stale_sweep`,
  `phase-fix-loop.md:52` carries **no** "run it alone" warning. A subagent that
  chains `pytest …; sahjhan event test_failed_before_fix …` records nothing, and
  that silence sits *before* item 19's mis-attribution.
- All four recognizers accept only `python|python3|py`
  (`verify_suite.py:342 _INTERPRETERS`), so `poetry run python …` / `uv run …` /
  `python3.12 …` record nothing — shapes `phase-fix-loop.md:230` explicitly
  invites via `HOLTZ_PYTEST`.

**Plan**

1. Each script's own argument parser refuses exactly what its courier refuses.
   `--present` becomes required with `--record`; `--cwd` is dropped from the
   recorded form (or taught to the recognizer — pick one and make both ends read
   it from one place).
2. Every courier `exit_warn`s on the `None` path instead of `exit_ok`. Every
   other failure on these paths already warns; this one, with the same outcome,
   is silent.
3. Widen `_INTERPRETERS` to cover the invited shapes, or make the taught command
   the only supported spelling and say so where `HOLTZ_PYTEST` is introduced.
   Do not leave `phase-fix-loop.md:230` inviting a shape that silently records
   nothing.
4. Add the "run it alone" warning to `phase-fix-loop.md:52`, matching `:69/:150/:174`.

**Validation**

1. For each of the four scripts: a command the CLI accepts but the recognizer
   refuses now **fails at the CLI** (non-zero, with a message) rather than
   exiting 0 and recording nothing.
2. A courier reaching its `None` path emits a warning. Assert the warning text
   reaches the transcript — silence is the defect, so a test that only checks
   "nothing recorded" reproduces the bug rather than catching it.
3. `poetry run python …/verify_suite.py --record --scope full` either records or
   fails loudly. Assert which one the ruling chose; both are acceptable, silence
   is not.
4. Contract: add the chained form (`pytest …; sahjhan event …`) to the
   combinatorial matrix in `test_contract_commands.py`.
5. Non-vacuity: restore one recognizer's narrow form; check 1 goes red.

---

#### 37. The primer's silent-degrade is wider than item 17, and its ordering hides daemon death · extends 17

**Defect** — three fail-open paths, not one: `primer.py:117-118` `TimeoutExpired`
(item 17's), `:120-121` `exit_ok()` on any non-zero `status` exit (corrupt
ledger, config error), and `:101-102` `exit_ok()` when a `_recently_failed`
marker suppresses the binary for an hour. The aggravating fact is the ordering:
the daemon-death check (`:147-150`) and the enforcement-health probe (`:152-153`)
sit **after** the status subprocess, so a slow or failing `status` skips the
terminated-marker write and `auth_failed` detection entirely. The hook whose job
is reporting daemon death stays silent when the daemon dies during a slow status.

**Plan**

1. Move the death check (`_read_init_pid` / `_is_process_alive` /
   `_write_terminated_marker`) and the health probe **before** the status
   subprocess. Death detection must not depend on a call that can hang.
2. Inject a short degraded-mode notice on all three degrade paths instead of
   exiting silent. The primer's entire job is re-injecting state after a
   `/clear`; "nothing to say" and "I could not find out" must not look identical.
3. This subsumes item 17. Close 17 against this item's test, and note in
   `CHANGELOG` that the timeout predates the delta and is not a regression from it.

**Validation**

1. Each of the three degrade paths emits `additionalContext` containing a
   degraded-mode marker. Three separate tests — item 17's proposed fix covers
   only the first.
2. **Daemon dies during a slow status** → the terminated marker is still written.
   This is the ordering fix and the reason the item outranks 17.
3. The load-flake resolves for the right reason: `TestPrimerWithMockBinary::
   test_injects_lens_priming_in_audit` and `::test_warns_when_context_reset_fails`
   fail today with `assert '<state>' in ''` — after the fix the assertion has
   something to match. Confirm the failure is gone by running the class under
   concurrent load **three times unchanged**, not once
   ([[dont-bisect-against-a-load-flaky-test]]).
4. Non-vacuity: restore the ordering; check 2 goes red.
5. Re-run `bash scripts/hash-trusted-callers.sh` — `primer.py` is manifest-listed.

---

#### 5. The amplification breaker sits on the path the skill file calls the exception

**Defect** — P0.1's block is on `pattern_done` (`transitions.toml:411`), reachable
only from `pattern_analysis`. `phase-fix-loop.md:101` teaches "Stay in `fix_loop`
(usual)" and "Enter `pattern_analysis`, when `iteration_boundary` blocks you" — so
on the usual path `pattern_done` never runs and the breaker never evaluates. Per
D3, `pattern_done`'s escape is the only place deferral is taught.

**RULED (Jon, 2026-08-26): the breaker gets a second seat too.**

**Plan**

1. Put the same `any_of` on `iteration_boundary`, referencing the **same named
   queries** so the two seats cannot drift — the arrangement
   `round_item_cap_exceeded` already has across `pattern_done` and
   `iteration_boundary`.
2. The escape must be reachable from `fix_loop`: `defer_low`/`defer_medium` are
   declared `fix_loop → fix_loop`, so `sahjhan defer batch` works there. No new
   transition edges needed, unlike D2's `pattern_analysis` pair.
3. Both seats must reference `medium_deferral_budget` and `open_low_count` by
   name — H8 checks that a block names the query its escape is gated on, and the
   escape now has two block sites.

**Validation**

1. The breaker fires on the **taught** path: drive a diverging run that stays in
   `fix_loop` and never enters `pattern_analysis`; `iteration_boundary` blocks.
   This is the whole item — a test that enters `pattern_analysis` reproduces the
   old passing state.
2. Drive the printed escape and assert the block clears, at **both** seats.
3. `enforcement_lint` H7/H8 → exit 0, confirming one named query and two
   consistent escapes.
4. Check the breaker still measures what its title says: a **converging** run must
   not trip it. P0.1 shipped once as a detector carrying no information about
   the thing it was named for ([[dont-substitute-your-design-for-the-plan]]) —
   assert the two runs read differently.
5. Non-vacuity: remove the second seat; check 1 goes red.

---

#### 20. Every merged finding belongs to no lens, and the lens gate is about to be scoped by lens

**Defect** — `merge_punchlists.py:108,363` default `perspective` to
`"unspecified"`, which is not among `[sets.perspective]`'s 13 values. Confirmed
against a real daemon by the third pass: `sahjhan event finding --field
perspective=unspecified` **exits 0**, so the set is decorative for this field —
nothing anywhere refuses it, and any misspelled perspective has the same effect.

**Decision owed — D-d. This blocks item 3.**

- **(i) Attribute** merged findings to a real lens during the merge.
- **(ii) Accept** `unspecified` as deliberately converge-only, and say so in
  `merge-protocol.md`.

**Plan** (both branches)

1. Whichever branch: `[sets.perspective]` and the merge's default must agree.
2. Record the decision in `merge-protocol.md` — under (ii) that sentence *is* the
   deliverable, and it must name the accepted cost (a merged CRITICAL is caught
   only at `converge`, run-wide, at the end).

**Validation**

1. A test asserting **every value the merge can write is either a set member or
   explicitly routed**. This is the enumerate-the-whole-domain discipline D34
   cost a day to learn ([[enumerate-every-escape-a-gate-rejects]]) — enumerate
   the field's domain in a test, not in a paragraph.
2. Under (i): a merged finding lands with a real perspective and its lens gate
   names it. Under (ii): a merged CRITICAL is caught at `converge` — drive it and
   assert, so the backstop is proven rather than assumed.
3. Separately, and regardless of branch: decide whether the daemon should refuse
   a non-member value for a set-typed field. Today it does not, which makes this
   class of defect silent everywhere, not just here. If that is a sahjhan change,
   file it; if it is accepted, record it.
4. Non-vacuity: under (i), revert the attribution; check 2 goes red.

---

# Tier C — integrity/bypass; must-fix before RELEASE

#### 30. A single `&`, and `eval`/`$VAR` indirection, bypass every command-keyed guard · PROVEN

**Defect** — every command-keyed guard splits on `\s*(?:&&|\|\||[;|\n])\s*`
(`_sahjhan_bootstrap.py:416,668`, `_protocol_cache.py:292`, `commit_gate.py:46`),
which omits a single `&`. Bash's `&` is a separator, so `A & B` is one segment
whose first token is `A`. Driven live: `true & sahjhan reseal --proof X` is
allowed, as is `true & sahjhan event quiz_exhausted_resolved …` (the human-only
channel) and `true & rm -rf enforcement/hooks` — the directory whose own hook
docstring is "DO NOT MODIFY. This hook protects itself." Second face:
`_check_bash_write` (`:668`) parses the **raw** command while the sahjhan guard
(`:416`) parses `resolve_indirection(...)`, so `eval "rm -rf enforcement/hooks"`
and `T=docs/holtz/.sahjhan; rm -rf $T` slip past the protected-path guard.
`_protocol_cache.py:289-292`'s comment says the omission is deliberate ("avoid
splitting on single &") and that it "must match `_sahjhan_bootstrap.py`'s split
pattern to avoid divergence" — it argues for the hole and for single ownership in
the same breath.

**Plan**

1. **One owner for segmentation**, in `_shell_norm.py` beside
   `resolve_indirection` — the module whose docstring already claims this
   ownership ("Two hooks answering 'is this sahjhan?' from two parsers is
   PAT-001").
2. Split on `&` as well: `\s*(?:&&|\|\||[;&|\n])\s*`. `&&` precedes `&` in the
   alternation, so the two-character operator still wins.
3. **Hazard the review did not name, and it is load-bearing:** adding `&` to the
   class breaks `2>&1`, which would split into `foo 2>` and `1`.
   `_protocol_cache.py:285-286` already strips fd-duplication and `/dev/null`
   redirects *before* splitting; the shared splitter must do the strip **first**,
   and the other three call sites must adopt that order. A test for `foo 2>&1 &
   bar` covers both halves at once.
4. Every guard parses `resolve_indirection(cmd)` — including `_check_bash_write`,
   which today parses the raw string.
5. Rebuild the command-keyed branches to scan the **whole segment**, the way the
   surviving redirect/`tee` branches already do, so a guard is not defeated by
   token position.
6. Re-run `bash scripts/hash-trusted-callers.sh` (three manifest-listed callers).

**Validation**

1. The five driven lines from the punchlist become the regression fixture, with
   the observed before/after recorded:
   ```
   deny   sahjhan reseal --proof X
   deny   true & sahjhan reseal --proof X          (was: allow)
   deny   true & sahjhan event quiz_exhausted_resolved --field project=holtz
   deny   true & rm -rf enforcement/hooks          (was: allow)
   ```
2. `eval "rm -rf enforcement/hooks"` and `T=docs/holtz/.sahjhan; rm -rf $T` are
   denied.
3. `is_git_commit` sees `true & git commit` — the commit must be visible to both
   the gate and the `protocol_tracker` side.
4. **Add `&` as a separator to the combinatorial matrix in
   `test_contract_commands.py`.** It carries `&` today only as a trailing suffix,
   never as a separator, which is exactly why this survived. Parametrized tests
   then auto-combine it with every subcommand.
5. `foo 2>&1 & bar` splits into two segments, and `foo 2>&1` alone stays one.
6. Assert **one** segmentation function exists: grep the tree for the old regex
   literal and assert zero occurrences outside `_shell_norm.py`. The shared
   *name* is what a linter can check ([[enforcement-name-the-fact-not-the-text]]).
7. Non-vacuity: revert the character class; checks 1–3 go red.

---

#### 18. Any CRITICAL can be closed with `reason=theoretical`, and the config argues it cannot · PROVEN

**Defect** — `protocol.toml:410-425` justifies the exclusion in
`all_critical_resolved` on the grounds that `theoretical` is "written by
`theoretical_courier.py`, **not chosen by the agent**." But `finding_deferred` is
`attestation = "agent"`, carries no `restricted = true`, declares `agent:cli` as a
producer, and its `reason` pattern admits `theoretical`. Driven against a real
daemon: a CRITICAL the run filed as `user_reachable` is closed by one typed word.

**Plan** — two independent defects, both worth fixing:

1. **Provenance.** Record from a signal that entails the fact
   ([[enforcement-event-provenance]]). Either `restricted = true` on the
   courier's path with a separate agent-writable spelling, or a provenance field
   on `finding_deferred` that only `record_authed_event` can set — with the
   conjunct filtering on *that*. `context_reset`'s `trigger='session_start'` is
   the pattern done right and is the model to copy.
2. **Correlation.** Even with honest provenance, the exclusion never checks that
   the finding it excuses is graded `theoretical`. Add the latest-filing
   correlation the other conjuncts carry:
   `AND EXISTS (… f2.type='finding' AND f2.id=d.id AND f2.reachability='theoretical'
   AND f2.seq = MAX(seq for that id))`.
3. Sequence after item 25: both end in an unearned `finding_deferred` carrying
   `reason=theoretical`, and 25 tells you what the provenance field must survive.

**Validation**

1. The punchlist's driven sequence inverts: `event finding_deferred --field
   reason=theoretical` on a `user_reachable` CRITICAL → **refused**, or accepted
   and **not** excluded by `all_critical_resolved`. Assert which.
2. The courier's own path still works end to end — a genuinely theoretical
   finding is still auto-deferred and still excluded. A provenance fix that
   breaks the courier trades #79 for #73.
3. **Two guard tests currently prove the hole and call it correct**:
   `test_fix_loop_eligibility.py:190
   (test_a_theoretical_critical_converges_on_its_deferral)` and
   `test_theoretical_defer.py:272`, both closing the CRITICAL through
   `_Board.defer` — literally the forged path, with docstrings saying
   "machine-written" while their bodies type it by hand. Both must be rewritten
   to drive the courier, not the CLI.
4. `test_an_ordinary_deferral_still_does_not_converge` is the counterweight and
   proves only that the *other three* words refuse. Add the fourth.
5. An internally contradictory board row — `user_reachable` CRITICAL carrying a
   `theoretical` deferral — is now noticed by something. Assert it.
6. Non-vacuity: revert each of the two fixes separately and confirm a distinct
   test goes red for each. One test covering both means one of them is untested.

---

#### 36. The theoretical courier fires on read-only commands, and downloads the binary unguarded

**Defect** — `theoretical_courier.py:54,73`. The merge-script branch wakes when any
token *contains* `merge_punchlists.py`, so `grep -n reachability …merge_punchlists.py`,
`cat …` and `git log -- …` all trigger it — the #77 shape the docstring at `:63-66`
says it guards against, applied to only one of its two branches (the sahjhan-verb
branch is correct). Combined with item 25, `grep`-ing the merge script auto-defers
Justine's escalations. Separately, `pending()` calls `ensure_sahjhan()` with no
active-audit guard (`:85`, reached from `:155`), unlike `primer.py:80-83`, so any
Bash line naming the merge script in **any** plugin-installed project triggers a
~100 MB binary download and injects a protocol warning into a non-audit session.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Give the merge branch the same verb discipline the sahjhan branch already has:
   require that the token is being **executed** (an interpreter in the
   recognizer's `_INTERPRETERS` set, script path in argument position), not merely
   mentioned. `verify_suite.record_scope_of` is the shape to copy.
2. Add the active-audit guard before `ensure_sahjhan()`, ordered as
   `bash_guard.py:46-51` and `primer.py:80-83` order theirs — and use item 29's
   `audit_active()` so this one is worktree-correct from birth.
3. Land after item 29, so step 2 uses the anchored probe rather than adding a
   sixth `cwd`-relative one.

**Validation**

1. `grep -n reachability …merge_punchlists.py`, `cat …merge_punchlists.py`,
   `git log -- …merge_punchlists.py` and `echo event finding` → courier does
   **not** fire. Each of the four is a separate case; they reach the branch by
   different routes.
2. A real `python3 …/merge_punchlists.py …` → courier fires as before.
3. In a project with **no** audit, a Bash line naming the merge script triggers
   **no** binary download and **no** injected warning. Assert no network call —
   this is the item's downstream-consumer half and is invisible to any test run
   inside this repo, which always has an audit dir.
4. Non-vacuity: revert step 1; check 1 goes red. Revert step 2; check 3 goes red.

---

#### 33. `suite_courier` records `suite_green` for any script whose path ends `verify_suite.py` · PROVEN

**Defect** — `verify_suite.py:341,371`. Identity is the path **tail**
(`endswith(_SCRIPT_TAIL)`) and the courier never re-derives its payload: `scope`
comes from command text, `tree_hash`/`commit_hash` from git, and the only second
opinion is the printed `SUITE-GREEN:` line. It is the one courier with no ledger
re-derivation — the other four re-run their real check. Driven in a throwaway
repo, a two-line `sub/enforcement/scripts/verify_suite.py` that only prints the
marker passed the recognizer, exit code, `repo_root`, `compute_tree_hash` and
`_effective_scope`; only an absent daemon stopped the write. With a live daemon
this records a `suite_green` naming the real tree, having run zero tests — which
satisfies `verify_suite.py --check` and the suite gate on `fix_commit`.
`_effective_scope` re-derives only for `--scope affected`; `--scope full` — the
stronger claim three transitions demand — is passed straight through.

**Plan**

1. Have the courier re-run the real check, as the other four couriers do, **or**
   bind the marker to a host-derived signal the script cannot echo.
2. Re-derive `--scope full` rather than trusting the command text. The weaker
   claim is re-derived today and the stronger one is not, which is backwards.

**Validation**

1. The punchlist's throwaway-repo reproduction is the regression test: a
   `sub/enforcement/scripts/verify_suite.py` that only prints the marker must
   **not** produce a `suite_green`. Run it with a live daemon — the original
   observation was limited by an absent one, so a mock-daemon test would
   reproduce the limitation rather than the fix.
2. A genuine full-suite run still records.
3. `--scope full` is re-derived: a run claiming `full` that only ran a subset
   does not record `full`.
4. The recorded green still satisfies `verify_suite.py --check` and the
   `fix_commit` suite gate — assert end to end, not just the write.
5. Non-vacuity: revert; check 1 goes red.

---

#### 9. `merge_finding` has no relatedness or severity constraint

**Defect** — PROVEN: `merge_target_exists` for `BH-010` (CRITICAL) into `BH-011`
(an unrelated LOW) reads `true`; the predicate requires only that the target is a
filed finding and not the item itself. The merge emits `finding_resolved`, so it
clears `all_critical_resolved` and lets a round discharge
`round_opens_exceed_closes` by merging away every sibling it just found.

**Decision owed — D-c.**

**Plan**

1. Add the ruled constraint to `merge_target_exists` in `protocol.toml`
   (recommendation: the target's severity must be ≥ the item's; relatedness is
   not machine-checkable from the ledger).
2. Update item 9's table to **four** rows — item 25 added an automatic route.
   The generated contract already names the posture honestly ("21 of 32
   gate-consumed events are the agent's own word"), so row 1 is a documented
   choice, not a defect; keep that distinction in the text.

**Validation**

1. `merge_finding BH-010(CRITICAL) → BH-011(LOW)` → refused.
2. A legitimate sibling merge at equal severity still works — the transition has
   a real use and must survive.
3. A round cannot discharge `round_opens_exceed_closes` by merging away its own
   siblings. Drive the round, not just the predicate.
4. Non-vacuity: revert the constraint; check 1 goes red.

---

#### 22. No lint rule binds "a gate filters on this value" to "only a hook may write it"

**Defect** — item 18 is the bug; this is why it shipped. H1–H10 exist
(`scripts/enforcement_lint.py:829-1540`) and none asks item 18's question: H5 asks
whether an event claiming *above* `agent` attestation has an agent-writable path,
and `finding_deferred` claims `agent`, so H5 is satisfied. H7/H8 govern predicate
copies and escape identity. H10 binds a delegated gate's `evidence` event to what
the tool queries — the right idea, one level up from the field.

**Plan**

1. Add `check_h11_literal_provenance(model)` following the file's existing rule
   shape (`check_h10_delegated_gate_evidence` at `:1540` is the closest sibling).
2. The rule: **when a gate's SQL constrains a field to a literal value, that
   value must be reachable only by a path the gate's own prose claims.** Every
   conjunct filtering on `reason=`, `trigger=`, `scope=`, `provenance=` or
   similar is in scope. The config already names both halves, so this is
   mechanically checkable.
3. `context_reset`'s `trigger='session_start'` (`restricted` + `host` + a
   hash-pinned writer) is the pattern done right and is what the check holds the
   others to.
4. Do this while 18 and 25 are fresh — it is the check that would have failed
   the build, and it puts items 9 and 21 under machine audit rather than under
   the next reviewer.

**Validation**

1. H11 **fails** on the tree as it stands at `48c72fd` (before item 18's fix).
   A new lint rule that passes on the code that motivated it is not a rule —
   this is the single most important check in this entry.
2. H11 passes after item 18 lands.
3. H11 passes on `context_reset`, the correct pattern, with no special-casing.
4. `.venv/bin/python scripts/enforcement_lint.py` → exit 0 overall (the 2
   pre-existing warnings stay warnings).
5. Add a unit test for the rule itself in `test_enforcement_lint.py`, with a
   synthetic config exhibiting the violation — so the rule is tested, not just
   run.

---

#### 21. The round cap's population is an optional field the agent types

**Defect** — `round_item_cap_exceeded` and `round_opens_exceed_closes` count only
findings joined by `strpos(','||p.pattern_ids||',', ','||f.pattern_id||',') > 0`,
and `pattern_id` is `optional = true`, attestation `agent`. A NULL on either side
drops the row. So the cap is opt-in: a round that files ten siblings and tags none
is never over it — and `test_round_item_cap.py:105,117` assert exactly that as
correct. `protocol.toml`'s D6 comment argues under-reporting is safe ("forfeits
relief, not dodges a block") — **true for the backpressure conjunct, false for
D7's cap and the two-dry-rounds clause**, where under-reporting *is* the
block-dodging direction.

**Decision owed — D-e.** The punchlist is explicit that this should not get a
hasty fix: capping untagged findings would charge a round for blast-radius and
lens findings, which the comment correctly refuses.

**Plan**

1. **Narrow the `protocol.toml` claim to the conjunct it is true of.** This part
   is not blocked on the decision — the comment is wrong as written today and
   makes the gap invisible to the next reader
   ([[comment-argues-predicate-decides]]).
2. Record the decision about whether an untagged sibling is a gap worth closing,
   in the decisions doc, whichever way it goes.
3. Only if D-e rules to close it: change the population. Do not change it as a
   side effect of step 1.

**Validation**

1. The narrowed comment is diffed against the SQL as two independent claims, and
   the two now agree for each conjunct separately.
2. `test_round_item_cap.py:105,117` keep asserting the mechanism (they are right
   about it) and gain a docstring naming the accepted cost, so the next reader
   sees a decision rather than an oversight.
3. If D-e rules to close it: a round filing ten untagged siblings is over the
   cap, **and** a blast-radius finding filed in the same round is not charged to
   it. Both, or the fix is the thing the comment refuses.
4. H8 still passes.

---

#### 24. A hardening batch's commit need not touch the module it closes

**Defect** — `hardening_batch.check()` refuses four things (unfiled module, partial
module, a commit naming another module's findings, a commit already spent or
empty) and does not require the diff to be *in* the named module. One non-empty
commit anywhere closes an entire directory's open `fault_injected` findings. The
docstring's own summary — "a diff that has not been used before is the work" —
claims more than the check enforces, and `no_open_fault_injected` gates `converge`.

**Decision owed — D-f.** The looseness is arguably within D35's intent (batch
closure is the point, and the message must name every id).

**Plan**

1. If **document**: say so where the four refusals are enumerated, and correct the
   docstring so it stops claiming the diff is checked. *Recommended.*
2. If **enforce**: require the diff to touch the named module, and enumerate what
   that does to a legitimate cross-module hardening commit before shipping it —
   that is the escape this would remove.

**Validation**

1. Under (1): a test asserting the four refusals **and** explicitly asserting the
   fifth is *not* checked, with the docstring quoted in the test. That converts
   an overclaim into a recorded decision.
2. Under (2): a commit touching another module fails to close the named one; a
   legitimate module commit still closes it.
3. Non-vacuity under (2): revert; check 2's first half goes red.

---

#### 40. `NotebookEdit` is an ungated source-edit path three files disagree about

**Defect** — confirmed three ways at `48c72fd`:
`pre_tool_hook.py:99` believes it handles `NotebookEdit`; `hooks/hooks.json`
registers `pre_tool_hook.py` under matcher `"Write|Edit"` only (the
`Bash|Write|Edit|NotebookEdit` matcher belongs to `_daemon_lifecycle.py`); and
`enforcement/hooks.toml:100` includes `NotebookEdit` in the auto-record rule while
the TDD gate at `:27` is `tools = ["Edit", "Write"]`. So a `NotebookEdit` records a
`source_edit` — counting toward the accumulation and stall gates — while being
exempt from the TDD gate and the managed-path guard, and `pre_tool_hook`'s branch
for it is dead code. Zero notebooks in this repo; the exposure is
downstream-consumer.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Pick one answer and make all three files say it. Recommended: `NotebookEdit`
   **is** a source edit — add it to the `hooks.json` matcher for
   `pre_tool_hook.py` and to the TDD gate's `tools`, matching the auto-record
   rule that already counts it.
2. If instead it is deliberately exempt, remove it from the auto-record rule too,
   so it stops counting toward gates it cannot satisfy, and delete the dead
   branch at `pre_tool_hook.py:99`.

**Validation**

1. `hook_e2e`: a `NotebookEdit` in `fix_loop` with no failing test recorded is
   **blocked** (under branch 1) — driven through the subprocess, since this is a
   registration bug and an in-process call would not see it.
2. A `NotebookEdit` to a managed doc is blocked by the managed-path guard.
3. A consistency test over the three files: the tool list in `hooks.json`, in
   `hooks.toml`'s gate, and in `pre_tool_hook.py`'s branch must agree. That test
   is what stops the three-way drift recurring.
4. Non-vacuity: revert the matcher; check 1 goes red **and** check 3 goes red.

---

#### 47. `_sahjhan_bootstrap.py` calls a gated daemon op but is absent from the trusted-callers manifest

**Defect** — verified: `TRUSTED_SCRIPTS` in `scripts/hash-trusted-callers.sh` lists
18 scripts and `_sahjhan_bootstrap.py` is not among them, yet it is a `hooks.json`
PreToolUse entrypoint (registered under the `Write|Edit`, `Bash`, and `Grep|Glob`
matchers) and calls `read_cache` → `_daemon_request({"op": "enforcement_read"})`,
a SO_PEERCRED-gated op added by `68ffd91` three months after the manifest's last
completeness pass (`5a39a90`). Of its two uses of the result, one fails closed
(`_daemon_stop_permitted`) and one fails **open**
(`_bash_source_write_tdd_block:1059` returns `None` on
`is_enforcement_fresh(None)`, skipping the TDD gate for Bash-based source writes).
The pre-commit auto-regen fired on that commit but structurally cannot add a file
not already in its own list ([[trusted-callers-manifest-regen]]).

**Plan**

1. Add `enforcement/hooks/_sahjhan_bootstrap.py` to `TRUSTED_SCRIPTS`.
2. `bash scripts/hash-trusted-callers.sh`; commit the regenerated
   `enforcement/trusted-callers.toml` in the same commit.
3. Land with or after item 29 — both touch this file's audit-active probe, and
   both invalidate its hash.

**Validation**

1. `real_daemon` `hook_e2e`: drive a **Bash source-write** with no failing test
   recorded and assert it is **blocked**. This is the fail-open half and the only
   check that distinguishes the fix from a no-op — the runtime consequence is
   INFERRED today precisely because no test isolates it.
2. `test_stale_sweep.py::test_every_registered_authed_writer_is_in_the_manifest`
   must now cover this entrypoint. If it does not, extend it — it exists to fail
   the build for exactly this and did not.
3. `enforcement/trusted-callers.toml` contains the new key; the file's diff is in
   the same commit as the code.
4. Non-vacuity: remove the entry, regenerate, re-run check 1 → it must flip to
   allow. **Regenerate before mutating**, or the RED is a stale-hash artifact
   rather than the thing under test.

---

#### 41. The boundary block precedes the freshness check, so an abandoned audit wedges the repo

**Defect** — `pre_tool_hook.py:102-111` and `commit_gate.py:59-76` fire
`exit_boundary_missing` **before** `is_enforcement_fresh`, and the 30-minute
freshness window is the only thing that releases an abandoned audit. The daemon is
`nohup`'d and torn down only on `finalized`/`idle`. So a session killed
mid-`fix_loop` with a surviving daemon makes every Bash/Write/Edit in every
session in that repo — and every linked worktree, since the socket is anchored —
deny with "type `holtz-start`", including sessions doing no audit. `holtz-stop` is
a real escape, so this is a wedge, not a deadlock; but the docstring's "cannot
fire in a project that is not being audited" is true only of a project that never
had a daemon.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. The ordering is deliberate and documented in both files ("a refusing daemon
   serves no cache, so `is_enforcement_fresh` is False and this degrade path
   would otherwise wave through exactly the situation it exists for"). **Do not
   simply swap the two** — that reopens the fuse-inversion the comment describes.
2. Distinguish the two cases the single ordering currently conflates: *boundary
   missing during a live audit* (block — the current behaviour, correct) from
   *boundary missing with an abandoned audit* (release). Freshness is not the
   right discriminator alone; the terminated marker and the init-pid liveness
   check are, and both already exist in `_common.py`.
3. Correct the docstring either way.

**Validation**

1. A session killed mid-`fix_loop` with a surviving daemon, past the freshness
   window: an unrelated session's Bash is **allowed** (or blocked with a message
   naming a working escape — assert which, and run it).
2. A live audit with the boundary genuinely down still **blocks**. This is the
   fuse and must not regress; it is the reason for the current ordering.
3. A linked worktree behaves as the main checkout does (shared socket).
4. Non-vacuity: apply the naive swap instead of the fix; check 2 must go red —
   demonstrating why the swap is wrong.

---

#### 38. `sed --in-place` and `git diff --output=` are classified read-only

**Defect** — `_protocol_cache.py:358` maps `sed`'s writing flags to `("-i",)` and
matches with `p == flag or p.startswith(flag)` (`:382-384`).
`"--in-place".startswith("-i")` is **False** — it starts with `--` — so
`sed --in-place 's/a/b/' src.py` is classified read-only and accrues no stall.
The `#70/#71` in-place-rewrite bypass, reopened. The table's own comment claims
the opposite ("also covers -i.bak / --in-place via prefix match"), and the
function's docstring names this exact direction as the unacceptable one
("Misreading a write as a read would let real work escape the counter").
Separately `git` is whitelisted with no writing-flag table, so
`git diff --output=/path HEAD` → read-only too. `test_hook_chains.py:527` tests
`sed -i` and `sed -i.bak` and omits `--in-place`.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Add `--in-place` to `sed`'s writing flags (the prefix match then covers
   `--in-place=.bak` as it does `-i.bak`), and fix the comment that claims it was
   already covered.
2. Add a writing-flag entry for `git`: `--output`, `--output-indicator*`, and any
   other `git diff` flag that writes. Prefix matching covers the `=` forms.
3. Audit the rest of `_READ_ONLY_COMMANDS` for the same long-flag gap — the bug
   is the `--`/`-` asymmetry, not the specific word, so `--in-place` is unlikely
   to be the only one.

**Validation**

1. `sed --in-place 's/a/b/' src.py` → **not** read-only; the stall counter
   charges it.
2. `git diff --output=/tmp/x HEAD` → not read-only.
3. `sed -i`, `sed -i.bak`, `git diff HEAD` keep their current classifications —
   the existing `test_hook_chains.py:527` cases must not move.
4. Add all three long-flag forms to `test_hook_chains.py`'s parametrisation
   beside the existing short forms.
5. Non-vacuity: revert; checks 1 and 2 go red.
6. See item 48 — `is_read_only_cmd` has no direct unit test, which is how this
   slipped through. That entry's fix is this one's regression insurance.

---

# Tier D — correctness / hygiene / recorded-decision

#### 4. The fix-subagent contract contradicts itself across three files

**Defect** — `phase-fix-loop.md` was rewritten for P0.3; `SKILL.md:233` and
`step-10-fix-loop.md:5` were not. They disagree on where the subagent works
("in the enforced tree" vs its own worktree), on the TDD gate ("does not look at
`agent_id`" vs filters on it), and on committing ("**Never** let a fix subagent
`git commit`" vs step A.9: commit, then rebase). `CLAUDE.md` rule 5 names this
exact failure mode and cites `800624f`. The guard that exists for it —
`test_subagent_contract_consistency.py` — only greps five retired phrases from the
old incident, so it is blind to the new drift and passes.

**Plan**

1. Rewrite both files to the shipped contract, in one commit.
2. Give the consistency test a **positive** assertion — worktree, actor-scoped
   gate, subagent commits — rather than a denylist of last year's wording.

**Validation**

1. The rewritten consistency test **fails** against the tree as it stands, then
   passes after the doc edits. A denylist-to-positive rewrite that passes both
   before and after has changed nothing.
2. `.venv/bin/python -m pytest -m contract -q` and
   `.venv/bin/python scripts/contract_gate.py` → exit 0.
3. Assert the three files agree on all three claims, each claim a separate
   assertion, so a future drift on one does not hide behind the other two.
4. Where step ordering matters, assert on the **document's own line order**, not
   just on the gate — `test_the_subagent_records_the_green_last` is the pattern
   ([[test-the-taught-sequence-not-just-the-gate]]).

---

#### 6. The `DEFERRED.md` conjunct is satisfied by filing one finding

**Defect** — `renders.toml:21-26` renders `DEFERRED.md` on `finding` **and**
`finding_deferred` (verified), so the file exists from the run's first finding,
and `test_it_is_written_once_the_run_has_findings` asserts that as correct. The
spec's conjunct meant "the batch deferral happened"; as shipped it is a
`file_exists` on a file the engine writes unconditionally.

**Decision owed — D-b** (recommendation: do both — they are independent defects).

**Plan**

1. Drop `finding` from the render trigger, leaving `finding_deferred`.
2. Replace the conjunct with a ledger predicate over deferrals, so the gate reads
   the fact rather than a file's existence.
3. Land with item 44, which also edits this render entry.

**Validation**

1. A run with findings and no deferrals does **not** produce `DEFERRED.md`, and
   the conjunct reads false.
2. A run with one deferral produces it, and the conjunct reads true.
3. `test_it_is_written_once_the_run_has_findings` must be rewritten — it asserts
   the defect.
4. Non-vacuity: revert the trigger; check 1 goes red.

---

#### 7. `phase-convergence.md` still says converge requires "zero open items"

**Defect** — verified verbatim in the file's step 4: "Sahjhan checks all gates: all
perspectives complete, suite passes, linters pass, **zero open items**, no
protocol violations." That is the gate P0.1 replaced. An agent following this doc
drives toward the non-terminating behaviour the release exists to end.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Replace the clause with the shipped conjuncts: every CRITICAL resolved, every
   `user_reachable` HIGH closed, amplification under control, deferrals written
   down.
2. Land with items 8, 13, 14 as one doc sweep.

**Validation**

1. Grep the phrase across `skills/**` → zero hits.
2. A test asserting the doc's gate list matches `transitions.toml`'s `converge`
   conjuncts by name. Prose that restates a gate list drifts; a test that
   compares the two names is what stops it recurring
   ([[enforcement-name-the-fact-not-the-text]]).
3. `contract_gate.py` → exit 0.

---

#### 8. `SKILL.md`'s deferral rules predate P0.5

**Defect** — `SKILL.md:37` (verified verbatim): "CRITICAL/HIGH must be fixed; LOW,
budget-capped MEDIUM, and can't-reproduce may be deferred." No mention that only
`user_reachable` is fix-loop eligible, that `fault_injected` batches at Step 15,
or that `theoretical` auto-defers. `reachability` appears once in the whole file,
as a field in an example.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. State the reachability routing where the deferral rules are stated. Action
   only — no rationale; reasoning belongs in the commit message
   ([[no-rationale-in-skill-files]]).
2. Do not write a prohibition the reader only learns about from the prohibition
   itself ([[skill-files-are-instructions-not-changelogs]]) — no "any more".
3. Land with item 26 (same sweep, both about the grading that decides what gets
   fixed).

**Validation**

1. A doc-consistency test: the three reachability grades named in `SKILL.md`
   match `events.toml`'s pattern for the field. Enumerate the domain in the test.
2. `pytest -m contract` and `contract_gate.py` → exit 0.
3. Audit the whole 24-hour edit window for rationale creep, not just this diff.

---

#### 10. The two converge conjuncts pull against each other

**Defect** — PROVEN: 3 findings filed in-loop, 3 deferred, board empty →
`amplification_diverging` still `true`, because deferrals are not counted on the
resolved side. So the breaker's prescribed escape (`defer batch`) moves the
`pattern_done` block and not the `converge` conjunct reading the same predicate.
Converge's amplification gate names no escape at all.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Count deferrals on the resolved side of `amplification_diverging`, so the
   escape the breaker prints actually moves the conjunct that reads it.
2. Give the `converge` seat an `intent` naming a command (this is also item 11).
3. Land with item 5 — same predicate, same escape, and 5 adds a second block site
   that must print the same escape.

**Validation**

1. The punchlist's observation inverts: 3 filed, 3 deferred, board empty →
   `amplification_diverging` reads **false**.
2. Drive `defer batch` and assert **both** the `pattern_done` block and the
   `converge` conjunct move. One escape, two sites, one outcome.
3. `converge`'s amplification gate prints an escape, and it runs.
4. Non-vacuity: revert; check 1 goes red.

---

#### 11. Gates that print no escape

**Defect** — `all_findings_closed` (no `intent`), `quiz_exhaustions_resolved` (no
`intent`), `amplification_diverging` on `converge`. And
`medium_deferral_budget`'s intent is self-contradictory: "the MEDIUM deferral
budget must be spent — half the MEDIUMs get fixed, not deferred," while the gate
requires half **deferred**.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. `all_findings_closed` — resolved by item 3 (the conjunct is deleted). If D-d
   keeps it declared, it needs an intent.
2. `quiz_exhaustions_resolved` — add an intent naming its command.
3. `amplification_diverging` on `converge` — item 10, step 2.
4. `medium_deferral_budget` — item 2, step 2.
5. Then close the class: make it impossible to add a gate with no intent.

**Validation**

1. A lint check (or an extension of H8) asserting **every** gate carries an
   `intent`, so this list cannot regrow. Item 11 is a symptom list; the check is
   the fix.
2. For each of the four: the block prints an escape and the escape **runs**.
3. The check fails on the tree at `48c72fd` and passes after.

---

#### 12. README contradicts itself, including on a security claim

**Defect** — verified: line 204 says "Twelve hooks backed by the Sahjhan
enforcement engine"; line 222 says "20 enforcement hooks"; `hooks.json` registers
**22** entries (counted: 6 PreToolUse, 10 PostToolUse, 2 SubagentStop, 1 Stop,
2 UserPromptSubmit, 1 SessionStart). Line 204 also says session keys are
"inaccessible to the model or any same-user process **without kernel-enforced
socket credentials**"; the "The boundary" paragraph eight lines below says that is
provably false and explains why. The refuted claim is still in the document, above
its own refutation.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Delete the refuted clause from line 204. The boundary paragraph is the best-told
   story in the delta and needs no help; it needs the contradiction removed.
2. Make both counts say 22, or say "the hooks" without a number.
3. Recount rather than trusting either existing number.

**Validation**

1. A test asserting the README's hook count equals `len(hooks.json entries)` — if
   a number is kept, it must be derived, not typed. If no number is kept, assert
   the phrase is absent.
2. Grep for the refuted phrase → zero hits.
3. `pytest -m contract` → exit 0.

---

#### 13. `docs/ARCHITECTURE.md` still lists `PUNCHLIST-MERGED.md`

**Defect** — verified at `:272` in the file-layout block. P0.4 deleted the concept,
and `fix_loop_start` now refuses to start while the file exists.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Remove the line. Check the rest of the layout block against the tree in the
   same pass — one stale entry suggests others.
2. Land with items 7, 8, 14.

**Validation**

1. Grep `PUNCHLIST-MERGED` across `docs/**` and `skills/**` → only historical
   references (incident write-ups) remain, and each is unambiguously historical.
2. `test_managed_docs_consistency.py` still passes; extend it to assert the
   layout block matches the managed-docs list, so the next deletion cannot go
   stale silently.

---

#### 14. `step-10-fix-loop.md` Fast Path still mandates a third suite run

**Defect** — verified: "Write failing test. Verify it fails. Minimal fix. **Full
suite.** Commit." A third mandated tail run, at the wrong scope, in the file whose
Per-Fix Hardening #3 was edited to say "Do not run the suite here."

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Bring the Fast Path in line with the hardening step (P1.6's residue).
2. Land with items 4, 7, 13.

**Validation**

1. Assert the two sections of the same file agree — a test over both strings.
2. Assert the taught scope matches what `fix_commit`'s suite gate requires;
   `phase-convergence.md` step 4 already notes that per-fix `affected` greens do
   not satisfy `converge`, so the two claims must not disagree.
3. `pytest -m contract` → exit 0.

---

#### 15. `hypothesis` is undeclared · **now observed**

**Defect** — `.github/workflows/ci.yml:21` pip-installs it; `pyproject.toml` has no
`[project]` table at all (verified: the only tables are `tool.ruff`,
`tool.ruff.lint`, `tool.ruff.lint.per-file-ignores`, `tool.mypy`,
`tool.coverage.run`, `tool.pytest.ini_options`). `tests/test_property_based.py`
imports it unguarded at module scope.

**Confirmed by observation** — the tier list asked whether this breaks a fresh
checkout's collection. It does:

```
$ python3 -m pytest tests/test_property_based.py --collect-only -q
E   ModuleNotFoundError: No module named 'hypothesis'
!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!
```

`.venv` carries `hypothesis 6.156.6`, which is why every gate observation in the
punchlist is green while this is true. **Local and CI do not run the same set on
a fresh machine** — the exact divergence `git-hooks/pre-commit` exists to prevent,
and it undercuts the harness rather than merely being untidy.

**Plan**

1. Add a `[project]` table to `pyproject.toml` with a test extra declaring
   `pytest`, `hypothesis` and anything else CI installs by hand.
2. Point CI at the extra instead of a hand-written `pip install` line, so the two
   cannot drift.

**Validation**

1. In a **clean** virtualenv built only from `pyproject.toml`'s test extra:
   `python -m pytest --collect-only -q` → exit 0, no collection errors. Paste the
   collected count.
2. `ci.yml` no longer names a package the project does not declare — grep for
   `pip install` in the workflow and assert each name is declared.
3. Non-vacuity: remove `hypothesis` from the extra; check 1 goes red with the
   same `ModuleNotFoundError` captured above.

---

#### 16. `CHANGELOG.md` `[Unreleased]` is empty

**Defect** — verified: the section header exists with nothing under it, across 93
commits. Expected pre-release, but it is step 5 of the release checklist and
nothing has been drafted.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. `.venv/bin/python scripts/generate-changelog.py` (preview), review, then
   `--write`.
2. Draft **last**, after the Tier A–C fixes land, so the notes describe the
   release rather than the review.
3. The release-notes exercise in the punchlist is the honest source for what can
   and cannot be claimed — three of its five headline sentences were unshippable
   at review time. Do not restore a sentence whose item is still open.

**Validation**

1. `[Unreleased]` is non-empty and every entry maps to a commit in
   `git log dev --not main`.
2. Each punchlist item fixed in this cycle appears, and each item **not** fixed
   has no sentence claiming it.
3. `scripts/pre-release-check.sh` → exit 0 (it includes the version-bump check).

---

#### 17. The primer fails open on timeout and makes the suite load-flaky

**Folded into item 37**, which covers all three degrade paths and the ordering
defect that hides daemon death. Close 17 against 37's validation checks 1 and 3.
Retain 17's own note in the changelog: the timeout predates this delta and is not
a regression from it.

---

#### 23. Three-wide dispatch has no rework path when `--ff-only` refuses

**Defect** — `phase-fix-loop.md:44` launches three subagents; each rebases onto the
branch as it stood when *it* finished, and the orchestrator merges `--ff-only` one
at a time. When A's merge lands after B rebased, B no longer fast-forwards. The
doc says "A refusal means the subagent's rebase is stale; send it back" and stops
there. What "send it back" must include is unwritten: B must re-rebase **and**
re-run `verify_suite.py --record`, because the rebase moves the tree and
invalidates the recorded `suite_green` (line 67 already establishes this). A
subagent that only rebases produces a fix the orchestrator's step 11 rejects for a
reason that looks like the fix being unreal. Also on that path, line 60 is
`git add -A && git commit`.

**Plan**

1. Write the rework path into `phase-fix-loop.md`: re-rebase, **then** re-record
   the green, then hand back.
2. Replace `git add -A` with explicit paths. This repo has a standing rule against
   it — the tree carries untracked-by-design plan docs and a ~100 MB vendored
   binary ([[stage-explicitly-never-git-add-all]]) — and in a worktree it means
   whatever else the subagent left rides the fix commit.

**Validation**

1. A test over the document's own step order: re-rebase precedes re-record, and
   re-record precedes hand-back ([[test-the-taught-sequence-not-just-the-gate]]).
2. `test_fix_loop_worktree_merge.py` gains the refused-`--ff-only` case: B is sent
   back, re-rebases, re-records, and the orchestrator's step 11 accepts.
3. A subagent that re-rebases **without** re-recording is rejected — the failure
   mode must stay detectable, and its message must not look like "the fix is
   unreal."
4. Grep `phase-fix-loop.md` for `git add -A` → zero hits.

---

#### 28. A courier's recognizer is narrower than its script's CLI

**Folded into item 34**, which extends it from two scripts to four and adds the
`tdd_courier` consequence (silence *before* item 19's mis-attribution). Close 28
against 34's validation checks 1 and 2.

---

#### 39. `post_tool_hook` records nothing, silently, on a non-zero eval exit

**Defect** — verified at `post_tool_hook.py:139-148`: `eval_data` is initialised
`{}` and only populated `if result.returncode == 0`, so a non-zero exit falls
through with no `auto_records`, no `exit_enforcement_error`, no telemetry. A
config or version fault therefore stops `file_read`/`source_edit`/`file_search`
being recorded, and every predicate counting `source_edit` — the edit-accumulation
block, the stall monitor — reads zero forever. `pre_tool_hook.py:158-169` handles
the same case correctly, so the two hooks disagree. Secondary: a JSON **list**
from `result.stdout` makes `data.get` raise `AttributeError`, which is outside the
except tuple `(OSError, TimeoutExpired, JSONDecodeError, ValueError)` → an uncaught
traceback out of a PostToolUse hook.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Handle non-zero the way `pre_tool_hook` does — `exit_enforcement_error` with
   the PostToolUse variant (a warning, since PostToolUse cannot undo the work).
2. Guard the shape: `if not isinstance(data, dict)` before `.get`, or add
   `AttributeError`/`TypeError` to the except tuple. Prefer the explicit check —
   the except tuple is already doing too much.
3. Re-run `bash scripts/hash-trusted-callers.sh`.

**Validation**

1. A non-zero `hook eval` exit produces a **visible** degraded-mode signal, not
   silence. Silence is the defect, so assert the message, not the absence of a
   crash.
2. `source_edit` recording is unaffected on the success path.
3. `result.stdout` = `"[]"` → no traceback; the hook exits 0 with a warning.
4. Assert `pre_tool_hook` and `post_tool_hook` agree on this case — one test over
   both, so they cannot drift apart again.
5. Non-vacuity: revert; checks 1 and 3 go red.

---

#### 44. `DEFERRED.md` shows a deferred-then-fixed finding as still deferred; `STATUS.md` goes stale

**Defect** — verified: `deferred.md.tera:27-40` computes `deferred_ids` and **never**
`resolved_ids`, while `punchlist.md.tera:21` computes it and `:40` gives it
precedence. So a finding deferred then fixed anyway — a legal path, since
`fix_commit` carries no `item_open` gate — is listed as deferred forever.
`renders.toml:25` compounds it by omitting `finding_resolved` from the render
trigger. Separately, `STATUS.md` renders `on_transition` while the punchlist
family renders `on_event`, so its Open/Resolved counts freeze between transitions.
Both are agent/human-read only; nothing gates on their content.

**Decision owed — D-g** (the `STATUS.md` half only).

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Compute `resolved_ids` in `deferred.md.tera` and give it precedence, matching
   `punchlist.md.tera:21,40` — copy the working template's expression rather than
   writing a second one.
2. Add `finding_resolved` to `DEFERRED.md`'s render trigger in `renders.toml`.
3. Land with item 6, which edits the same render entry.
4. `STATUS.md` timing per D-g.

**Validation**

1. File a finding, defer it, then resolve it: `DEFERRED.md` does **not** list it.
2. A finding deferred and not resolved is still listed.
3. All four templates agree on resolved-takes-precedence — assert across the
   family, since three had it and one did not.
4. Under D-g: `STATUS.md` counts change on a finding event without a transition.

---

#### 45. `migrate_legacy.py`: schema-violating fields, no `--all` ledger boundary, duplicate rows

**Defect** — every migrated `finding`/`finding_resolved` sets `step=""` and often
`commit_hash=""`, both failing their `events.toml` patterns — harmless only because
`sahjhan ledger import` is schema-lax, but born non-compliant and untouched by the
`5679f5c` reachability pass. `--all` prints all runs' events with reused `BH-NNN`
ids and no ledger boundary, and its own usage line invites a single combined import
that would collide identically-numbered findings under D25's by-id latest-wins.
`build_project_ledger` re-run accumulates duplicate `run_registered`/`run_completed`
rows. All historical-tooling paths; none is gate-consumed.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Emit schema-valid values, or omit the optional fields rather than emitting
   empty strings that fail their own patterns.
2. Give `--all` a ledger boundary per run, and fix the usage line that invites the
   colliding import.
3. Make `build_project_ledger` idempotent.

**Validation**

1. Every migrated event validates against `events.toml` — assert field-by-field,
   not via a lax import that would pass today.
2. `--all` across two runs with the same `BH-001` keeps them distinct.
3. `build_project_ledger` run twice produces the same ledger as once.
4. Non-vacuity: revert each; the matching check goes red.

---

#### 46. The sahjhan pin has no binary/version cross-check and no runtime re-hash

**Defect** — the three pins are currently coherent (verified by the fourth pass:
`bin/.sahjhan-version`, `_resolve.SAHJHAN_VERSION` and `bin/sahjhan --version` all
`0.23.0`). But `update_sahjhan_pin.py:39-47` hashes whatever bytes sit in `bin_dir`
without checking they belong to the version being pinned, and
`_resolve.ensure_sahjhan`'s fast path returns a binary on a version-marker string
match with **no checksum re-verification** (that happens only on a fresh
download). `check_sahjhan_pin.py` — which would catch a mismatch — is wired only
into `pre-release-check.sh`, not the git hooks, so a partially-failed vendor run
leaves an unverified binary trusted until the next release.
See [[sahjhan-version-pinned-in-three-places]].

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. `update_sahjhan_pin.py` runs `bin/sahjhan --version` and refuses to pin if it
   disagrees with the version being pinned.
2. Wire `check_sahjhan_pin.py` into `git-hooks/pre-commit` (it is fast), not only
   into the release script.
3. Decide whether `ensure_sahjhan`'s fast path should re-hash. A checksum on every
   hook invocation is a real cost; a version-marker string match is a real gap.
   Recommendation: re-hash when the marker changes or the mtime moves, not on
   every call.

**Validation**

1. Put a mismatched binary in `bin/` and run the pin updater → refused, naming
   both versions.
2. `check_sahjhan_pin.py` runs from pre-commit: stage a mismatched pin → the
   commit fails.
3. All three pins agree after a real vendor run:
   `bin/.sahjhan-version` == `_resolve.SAHJHAN_VERSION` == `bin/sahjhan --version`,
   and all four `SAHJHAN_CHECKSUMS` recompute and match.
4. Non-vacuity: revert step 1; check 1 goes red.

---

#### 48. The delta's new enforcement predicates ship with no direct unit tests

**Defect** — no test imports `is_read_only_cmd`, `_tdd_gate_exempt`,
`project_anchor`, `stall_bumped`/`stall_cleared`, `pending_commits_for`,
`exit_boundary_missing` or `query_named_predicate`. `is_read_only_cmd` is the
notable one: a new ~40-line classifier with two hand-kept frozensets deciding
whether a Bash line escapes the stall counter, covered only by the parametrized
subprocess cases in `test_hook_chains.py` — which is where item 38 slipped through.

*The punchlist prescribes no fix. Authored here.*

**Plan**

1. Add direct unit tests for all seven, with `is_read_only_cmd` first — it is the
   one with a known escaped defect (item 38).
2. For the two hand-kept frozensets, test the **long-flag** forms explicitly; the
   `--`/`-` asymmetry is the defect class, not any single word.
3. **Import discipline:** drive hooks by subprocess where the interface matters,
   and be careful that the tree has two `_common.py` modules — importing the
   wrong one imports cleanly and makes every query return empty
   ([[two-common-modules-poison-in-process-imports]]). Never let a negative
   assertion rest on an empty set.

**Validation**

1. Each of the seven has at least one test that fails when the function is
   mutated. Mutate each, confirm RED, revert — the list is the checklist.
2. `is_read_only_cmd`'s test would have caught item 38: assert `--in-place`
   before item 38's fix lands, and watch it go red.
3. Coverage does not fall. Do not lower a threshold to accommodate this work — if
   coverage reads low, fix the measurement.

---

#### 49. Lower tail (bundle)

Eight real, low-blast-radius defects, grouped so none is lost. Each gets one plan
line and one validation line; they are individually small and collectively a
commit.

| # | Defect (verified) | Plan | Validation |
|---|---|---|---|
| a | `_common.py:271-273` — `boundary_dir`'s "fails closed" comment is inverted for consumer hooks: an unresolvable `~` yields a relative socket path → `connect` raises → `exit_ok` (fail open) | Make the unresolvable-`~` path fail closed, or correct the comment to describe what happens | Unresolvable `~` → assert the decision, and assert the docstring matches it |
| b | `protocol_tracker.py:198-199,234-235` — a transient `enforcement_read` failure followed by a successful write constructs and persists `empty_cache()`, erasing every pending commit and stall count | Do not write a cache built from a failed read; skip the write | Read fails → write is skipped → pending commits and stall survive |
| c | `_protocol_cache.py:565-575` — a mid-flight upgrade maps a pre-delta scalar stall onto `{ORCHESTRATOR: N}`, charging the orchestrator the whole run's stall (the audited run drove one number to 16 across 54 actors) | Decide whether to migrate or discard; the comment argues migration and the cost is a 16-deep charge on one actor | Upgrade a cache holding a scalar 16 → assert the ruled outcome, with the number chosen so no two quantities coincide |
| d | `post_tool_hook.py:132-133` — never passes `--agent-id`, so every PostToolUse gate/monitor is structurally run-global (item-1/19 family); dormant only because no PostToolUse rule templates `{{agent_id}}` today | Pass `--agent-id` as `pre_tool_hook.py:128-130` does | Assert the flag is passed; assert the two hooks agree, so the dormancy cannot become a live bug silently |
| e | `commit_gate.py:109-121` — `blocks_all` is `any(...)` but the message is always `obligations[0]`, so a stall block can print the pending-commit remedy | Print the message belonging to the obligation that actually blocked | Two obligations, the second blocking → the printed escape is the second's, and it runs |
| f | `commit_gate.py:66` — the comment names `holtz-stop` (which tears the boundary down) as the escape from a boundary-missing block whose message correctly says `holtz-start` | Correct the comment | Assert comment and message name the same command |
| g | `bash_guard.py:99-122` — records `protocol_violation` under `contextlib.suppress` with no `returncode` check, then asserts the violation is "permanent"; and hardcodes `auditor=holtz` three lines under a "derived, never mirrored" comment | Check the return code before claiming permanence; derive the auditor | A failed violation write does not produce the "permanent" claim; the recorded auditor is derived |
| h | `_shell_norm.py:32-35` — `resolve_indirection` treats `--field k=v` as a shell assignment and rewrites `$k` inside quoted data, so downstream guards reason about a command string that was never typed (latent; no decision flip found) | Exclude `--field`-style operands from assignment collection | `--field finding_id=BH-001 … $finding_id` is not rewritten; assert no guard's decision changes |

**Bundle-level validation:** `bash scripts/hash-trusted-callers.sh` after this
commit (it touches four manifest-listed hooks), then `pytest -m hook_e2e` → exit 0.

---

## Commit plan

Ordered by the punchlist's tiers, then by dependency. Each line is one commit;
conventional-commit types follow `CLAUDE.md` (skill files and `hooks.toml` are
functional deliverables — `fix:`/`feat:`, never `docs:`).

**Before functional testing (Tier A)**

1. `test:` **F1 + F2 + F3 fixtures.** No product change. Land first — six items
   depend on them, and each fixture's own pass criterion is that it *reproduces*
   the defect it exists for.
2. `fix(enforcement):` **item 29** — the anchored audit-active probe. Uses F1.
   Regenerate the manifest.
3. `fix(fix-loop):` **item 31** — taught fields + contract-gate extension. Uses F3.
4. `fix(enforcement):` **items 19 + 1** — pair evidence by row, then actor-scope
   the window. Uses F2. One test drives both; item 1 may require a sahjhan change.
5. `fix(enforcement):` **item 2** — the MEDIUM budget. *Blocked on D-a.*
6. `fix(enforcement):` **item 3** — the lens-scoped package. *Blocked on D-d.*

**Before trusting results (Tier B)**

7. `fix(enforcement):` **items 32 + 43** — the clear's success check and scope,
   and the escape the block prints. Uses F2.
8. `fix(merge):` **items 25 + 26** — read the whole row; require the grading.
9. `fix(enforcement):` **item 35** — the sweep's own window. Uses F2.
10. `fix(enforcement):` **item 42** — per-actor writes. Uses F2.
11. `fix(enforcement):` **item 34** (+28) — recognizers refuse what couriers refuse.
12. `fix(enforcement):` **item 37** (+17) — primer ordering and degrade notices.
13. `fix(enforcement):` **items 5 + 10** — the breaker's second seat and the
    conjunct that reads the same predicate.
14. `fix(merge):` **item 20** — *blocked on D-d; must land before commit 6.*

**Before release (Tier C)**

15. `fix(enforcement):` **item 30** — one segmentation owner. Strip-then-split.
16. `fix(enforcement):` **item 18** — provenance + correlation. After 8.
17. `fix(enforcement):` **item 22** — H11. While 18 and 25 are fresh.
18. `fix(enforcement):` **items 36 + 33** — courier triggers and the suite marker.
19. `fix(enforcement):` **items 40 + 47** — NotebookEdit registration; manifest entry.
20. `fix(enforcement):` **items 41 + 38** — boundary ordering; long-flag writes.
21. `fix(enforcement):` **item 9** — *blocked on D-c.*

**Hygiene and record (Tier D)**

22. `fix(skills):` **items 4 + 7 + 8 + 13 + 14** — the doc sweep, one commit, with
    the consistency test rewritten to a positive assertion.
23. `fix(enforcement):` **items 6 + 44** — render triggers and templates.
24. `fix(enforcement):` **items 11 + 39 + 49** — escapes, the PostToolUse fall-through,
    the bundle.
25. `test:` **item 48** — direct unit tests for the seven predicates.
26. `chore:` **items 15 + 45 + 46** — `[project]` table, migration tooling, pin checks.
27. `docs:` **items 12 + 16** — README contradiction, then draft the changelog last.
28. `docs:` **items 21 + 24** — the recorded decisions (D-e, D-f), wherever they land.

**Do not cut the release before commits 2, 3 and 4.** The punchlist's own
instruction is "do not cut before 1, 2 and 3" (its items 25, 18, 19+1);
`docs/design/convergence-speed-status.md` records P0.3 as shipped at `48c72fd`,
and with items 1 and 19 open that row is wrong again — and it is the row a reader
would trust ([[commit-hash-in-a-doc-must-be-post-amend]] for how to verify the
hash it cites).

**Commit as you go.** Each commit lands the moment its own gates are green; do not
batch ([[commit-as-you-go-not-in-a-batch]]).

---

## Coverage — every item has a plan and validation criteria

49 items. "Authored" means the punchlist prescribed no fix and this file supplies
one. "Decision" means implementation is blocked on a ruling, with both branches
specified.

| Item | Tier | Plan | Validation | Source | Blocked |
|---|---|---|---|---|---|
| 1 | A | ✓ | ✓ | punchlist | — |
| 2 | A | ✓ | ✓ | punchlist + authored | **D-a** |
| 3 | A | ✓ | ✓ | punchlist (ruled) | **D-d** |
| 4 | D | ✓ | ✓ | punchlist | — |
| 5 | B | ✓ | ✓ | punchlist (ruled) | — |
| 6 | D | ✓ | ✓ | punchlist | **D-b** |
| 7 | D | ✓ | ✓ | authored | — |
| 8 | D | ✓ | ✓ | authored | — |
| 9 | C | ✓ | ✓ | authored | **D-c** |
| 10 | D | ✓ | ✓ | authored | — |
| 11 | D | ✓ | ✓ | authored | — |
| 12 | D | ✓ | ✓ | authored | — |
| 13 | D | ✓ | ✓ | authored | — |
| 14 | D | ✓ | ✓ | authored | — |
| 15 | D | ✓ | ✓ | authored (**now observed**) | — |
| 16 | D | ✓ | ✓ | authored | — |
| 17 | D | → 37 | → 37 | punchlist | — |
| 18 | C | ✓ | ✓ | punchlist | — |
| 19 | A | ✓ | ✓ | punchlist | — |
| 20 | B | ✓ | ✓ | punchlist | **D-d** |
| 21 | C | ✓ | ✓ | punchlist | **D-e** |
| 22 | C | ✓ | ✓ | punchlist | — |
| 23 | D | ✓ | ✓ | authored | — |
| 24 | C | ✓ | ✓ | authored | **D-f** |
| 25 | B | ✓ | ✓ | punchlist | — |
| 26 | B | ✓ | ✓ | punchlist | — |
| 27 | — | ✓ | ✓ | punchlist | — |
| 28 | D | → 34 | → 34 | punchlist | — |
| 29 | A | ✓ | ✓ | punchlist | — |
| 30 | C | ✓ | ✓ | punchlist + **hazard added** | — |
| 31 | A | ✓ | ✓ | punchlist | — |
| 32 | B | ✓ | ✓ | authored | — |
| 33 | C | ✓ | ✓ | punchlist | — |
| 34 | B | ✓ | ✓ | punchlist | — |
| 35 | B | ✓ | ✓ | authored | — |
| 36 | C | ✓ | ✓ | authored | — |
| 37 | B | ✓ | ✓ | punchlist | — |
| 38 | C | ✓ | ✓ | authored | — |
| 39 | D | ✓ | ✓ | authored | — |
| 40 | C | ✓ | ✓ | authored | — |
| 41 | C | ✓ | ✓ | authored | — |
| 42 | B | ✓ | ✓ | authored | — |
| 43 | B | ✓ | ✓ | authored | — |
| 44 | D | ✓ | ✓ | authored | **D-g** |
| 45 | D | ✓ | ✓ | authored | — |
| 46 | D | ✓ | ✓ | authored | — |
| 47 | C | ✓ | ✓ | punchlist | — |
| 48 | D | ✓ | ✓ | authored | — |
| 49 | D | ✓ (×8) | ✓ (×8) | authored | — |

**Item 27** (`boundary_check.py` crashes on Linux seccomp) is in the punchlist's
third pass but appears in **no tier** in the consolidated fourth-pass tier list —
it is in the "Suggested order" section at position 9 and was dropped when the
tiers superseded it. Its plan and validation are below; **assign it a tier.**

#### 27. `boundary_check.py` crashes on the one platform path its docstring calls confinement · P1

**Defect** — `skills/holtz/scripts/boundary_check.py:45`: the socket is constructed
**before** the `try`. macOS Seatbelt answers EPERM on `connect()`, which the `try`
catches; Linux's seccomp filter blocks `socket(AF_UNIX)` outright, which raises on
line 45, outside the `try`, and propagates out of `probe()` and `main()` as an
uncaught traceback. So on a correctly confined Linux session — the configuration
`holtz-start`'s own receipt tells the user to set up — recon Step 0 dies, and
`SKILL.md:282` reads that as "it did not print `BOUNDARY: confined`" and tells the
agent to ask the user to type `holtz-start`, which will not help. **The strongest
confinement produces the same instruction as no daemon at all.**

**Plan**

1. Move the constructor inside the `try` (or wrap it). One line.
2. Land with items 7/8/13/14 or on its own — it has no dependencies.

**Validation**

1. Patch `socket.socket` itself to raise `PermissionError` → `probe()` returns
   `CONFINED`. `test_boundary_check.py:119` patches `socket.socket.connect` only,
   which is why the suite exercises the macOS path and cannot see this.
2. The macOS path still returns `CONFINED`.
3. Non-vacuity: revert the one-line move; check 1 goes red with the observed
   `PermissionError [Errno 1] Operation not permitted`.

---

## What this plan does not do

- **It does not re-rank anything.** The tiers are the punchlist's. Where this file
  groups items into a commit it is for dependency and shared-fixture reasons,
  stated at each line.
- **It does not decide the seven open questions.** Recommendations are marked as
  recommendations; both branches are specified so neither is the default by
  accident ([[deviation-from-plan-requires-asking]]).
- **It does not re-verify the punchlist's findings as a whole.** Every anchor
  cited *in this file* was re-read at `48c72fd`; the punchlist's own PROVEN
  observations are carried forward as it recorded them, except item 15, which is
  now observed here, and item 30, which gains an implementation hazard.
- **It does not assert that any of this passes.** No gate was run against a fix,
  because no fix has been written.

# Release worklist — handoff

**This is the only handoff. Update it in place; do not write a #7.** Five
predecessors exist for this one worklist and three of them carried the same
unresolved questions forward — that pattern is itself a defect.

**What this file is for:** what to do next, and the traps that have actually
cost sessions time. **It is not a record of finished work** — that is the commit
log, which is written to be read (`git log --stat`).

---

## ⛔ Scope. Read before writing any status line.

**Release means all 49 items. RULED (Jon, 2026-09-01):** *"I ALREADY TOLD YOU A
WEEK AGO WE WERE DOING ALL OF THESE ITEMS BEFORE RELEASE."*

A session once wrote *"Release gate: do not cut before W02, W03, W04, W08"* into
Jon's own worklist, unattributed, and every report for a week read against it —
truthfully saying "blocked only on item 43" while **44 items sat open behind
it**. It is struck (`26406af`). Do not reconstruct it.

**Report as `N of 32 units, M of 51 items`, naming what remains** — the board's
own numbers. Jon's ruling says 49 because that was the list when he made it;
items 50 and 51 were found later, while doing W08, and sit on the dashboard
under the same rule. Do not quietly report 49, and do not drop them. Banned:
"the release gate is closed"; "blocked only on X" when a pile sits behind X;
any phrasing where one unit closing reads as the work closing.

---

## Status

**24 of 32 units · 39 of 51 items · 12 items across 8 units remain.**
Counted off the dashboard, not carried forward. **P3 is finished except W18's
item 33**, and **P4 is under way**: W23, W24 and W25 are `DONE`; **W26 and W27
are `WIP`**. What is left is W26 (48 — only V3), W27 (15 done; 45 and 46
part-done), W28 (12, 16), W29 (21, 24), W30 (23), W18's item 33, W13's item 17
(open by ruling), and W32's step 3 (a question for Jon).

**⭐ Resume here (session paused 2026-09-23 at Jon's request):**

- **W27 is mid-unit, with every decision already ruled** (D-p…D-t, in the
  unit — read them first; D-q′ corrects a misstatement of mine and replaces
  D-q's `PASS` mapping). Owed, in order: **45 step 3** — `step` 7 for audit
  findings / 10 for resolutions, `commit_hash` `0000000` for an unrecorded
  commit, a prose severity's leading word, the four undeclared legacy types
  dropped with a stderr count, and `_parse_claims_table` made header-aware
  (D-q′); **D-t** — declare `run_registered`/`run_completed` in
  `events.toml` (fields `project`, `run`, `auditor`; find a producer id H2
  accepts), then `enforcement_contract --write`; **45 step 5 (D-r)** —
  `--build-project --ledger <name>` reads the existing project ledger and
  emits only unregistered runs. `ledger import` cannot append (measured:
  "File exists"), so the delta goes in by `sahjhan --ledger <name> event`,
  which does append to the event-only ledger (measured); **46 step 8 (D-s)**
  — stamp mtime+size beside the marker, re-hash only when either moves (43 ms
  hash vs 16 µs stat, measured); **V4, V6, V9's download half.**
  `scratchpad/validate_migrated.py` from this session was the V4 validator —
  rebuild it as a test.
- **W26 needs only V3**, read off the one full `--cov` run.
- **The full suite has not run since `489e84d`, and CI has seen nothing** —
  run it once, at the end of the next session, with `--cov` (that is W26's
  V3). Nothing is pushed.
- **Method trap from this session:** restoring a mutation with
  `git checkout -- <file>` also discards that file's *uncommitted* work — it
  cost the D-p edit once. Undo a mutation with a reverse Edit when the file
  carries other changes.

**W25 landed 2026-09-23** in three commits — `1795e6a` (39 + 49d), `b90d713`
(49 a–c, e–h), `d0a0cd4` (11). It is `DONE` with a debt in its dashboard row:
**item 39's config-fault half waits on a sahjhan ask** (below, under Open for
Jon). Four rulings were taken before any code, D-l…D-o, recorded in the unit.

Three units are `WIP` and none moves the unit count. **W13** closed item 37 and
left item 17 open **by ruling**. **W18** closed item 36 and left item 33 open —
a design choice, not a spelling, and the unit carries the two measurements that
decide it. **W32** closed everything but step 3.

Done: W01 (fixtures, no item) · W02 (29) · W03 (31) · W04 (19, 1) · W05 (2) ·
W08 (32, 43) · W22 (27) · W06 (20) · W07 (3) · W09 (25, 26) · W10 (35) ·
W12 (34, 28) · W11 (42) · W14 (5, 10) · W31 (50) · W15 (30) · W16 (18) ·
W17 (22) · W19 (40, 47) · W20 (41, 38) · W21 (9) · W23 (4, 7, 8, 13, 14) ·
W24 (6, 44). Commits are in `git log`; do not re-summarise them here.

### ⛔ W21 left a question for Jon that a later session must not answer for him

Its **step 2** says *"reuse the existing `item_open` predicate for the openness
term"*. That mechanism does not exist: `item_open` is written against
`{{item_id}}`, the openness needed is the target's (`{{merged_into}}`), and a
named-query gate resolves `queries.<name>.sql` and interpolates *its own*
transition's vars — `sahjhan/src/gates/query.rs`, `resolve_gate_sql` feeding
`eval_query_gate`. There is no argument rebinding and no query-in-query. It is
spelled inline as the two `NOT IN`s, which is what `all_findings_closed` and the
three `open_*_findings` predicates already do. **If the intent was a new named
query (`merge_target_open`) consumed by both `merge_finding` seats, it is a
rename.** Recorded in the unit and the commit; do not close it silently.

**The dashboard rows lag the unit sections.** W15 and W16 both sat at `TODO`
in the table while their sections read `DONE`/`WIP`. Corrected — but the rule
that matters is the one that catches it: **count the dashboard *and* read the
sections, and reconcile them, before writing any number here.**

**W15 landed 2026-09-04** — the first P3 unit. All eight sites converted to
one segmentation owner, V1–V7 driven. Four things a later session will
otherwise re-derive:

- **The redirect hazard is solved by masking, not stripping**, and the
  difference is load-bearing. `_check_bash_write` scans each segment for
  redirect *targets*, so a segment handed back with `2>&1` removed would hide
  a real write. The redirect-operator `&`s become NUL for the split and are
  restored after. `test_the_segment_keeps_the_bytes_it_was_written_with` is
  the only thing pinning that choice — anything that "simplifies" it to a
  strip re-opens a write channel.
- **A trailing `&` is a terminator, not a separator.** `A &` is one command,
  and that falls out of dropping empty segments. It is not cosmetic:
  `_is_recovery_command` requires *every* segment to be recovery, so getting
  it wrong denies `nohup sahjhan daemon start &` — the recovery the primer
  tells a user to run.
- **`node --eval` is not the shell builtin `eval`.** `_WRAPPER_RE`'s `\b` sat
  between `-` and `e`, so `resolve_indirection` ate the flag and rewrote the
  command to `node --require(…)` — deleting the token
  `_INTERP_INLINE_FLAGS` keys on to spot an inline interpreter write. Latent
  in two callers already; it only *cost* a block once the resolver went on
  `_check_bash_write`. Now `(?<![-\w])`.
- **Stashing the whole fix is not a valid control here.** The test module
  imports `shell_segments` at module level, so the unmodified tree gives a
  *collection error* — red with every assertion skipped. The three targeted
  single-line mutations recorded in the unit are the evidence; a whole-fix
  stash is not.

**W31 landed 2026-09-04** — `c12469f`, all four validations driven. **P2 is
finished** except W13's item 17 (open by ruling) and W32's step 3 (a question
for Jon). The board is P3 (W16–W21, W15 now done) and P4.

Two things from it a later session will otherwise re-derive:

- **The discharge now has two arms and they are not interchangeable.** A hash
  the ledger stamped, and — new — a charge whose own commit message names a
  finding the ledger resolved. The second exists because `phase-fix-loop.md`
  rebases between the two moments the hash is read, so subagents 2 and 3 strand
  a charge every round. Anything that widens the second arm to "this actor
  rebased, clear the bucket" is caught by
  `test_a_second_commit_for_an_unresolved_finding_stays_charged` and by nothing
  else in the file.
- **The match inherits `fix_commit`'s gate's looseness, deliberately** — the
  gate is `git log -1 --format=%B | grep -q '{{item_id}}'`, a substring, so a
  message that *mentions* a resolved finding it is not fixing discharges. Two
  commits naming the same finding both discharge on one registration; that is
  judged correct (the finding's fix is registered) but it is a judgement and
  the commit message says so. Across two actors nothing has decided it and no
  test pins it.

**W11 landed 2026-09-04** — `0605ed2` (the pin move to 0.27.0) and `3697e31`
(the unit). Read `3697e31`'s message before building on it: it names three
things W11 does **not** close, and the first is load-bearing —
**an actor racing itself is still exposed on the merge paths**, deliberately,
and `test_a_merge_is_not_made_conditional` pins that it is deliberate.

**W13 landed item 37 the same day** — `9555fce`. Item 17 is open **by
ruling**, below. Do not re-run its measurement before reading it: the flake did
not reproduce on *either* arm, and the reason is recorded.

**W14 landed complete** — `7d69854`, all seven validations ticked. One thing
from it a later session will otherwise re-derive the hard way:
`amplification_diverging` joins `f.seq <= r.seq`, so **each round counts only
what had happened by that round**. A deferral after the last round moves no
round's window. `defer batch` reaches `converge`'s conjunct through the next
round it buys, not by acting on rounds already recorded, and
`test_the_batch_alone_does_not_move_the_converge_conjunct` is the tripwire:
if it ever passes, the window has been changed.

**Two corrections to the line this replaced** (*"8 of 30 units · 7 of 49
items"*), both made 2026-09-01 after counting the dashboard rather than
carrying the number forward:

- **The board is 32 units and 51 items, not 30 and 49.** Jon's ruling names 49
  because that was the list when he made it; items **50 (W31)** and **51 (W32)**
  were found later, while doing W08, and sit on the dashboard under the same
  *"nothing is cut until every unit is `DONE`"*. Report the board's number and
  say where the extra two came from — do not quietly report 49 and do not drop
  them.
- **W32 was listed as done and is `WIP`.** Its step 3 is open and is
  [a question for Jon](2026-08-27-release-worklist.md) (*"Open for Jon"*, near
  the end of W32): with #47 shipped, does the hand-vendored-old-binary path
  still want a diagnostic? The unit recommends **no** but records it as *not
  ruled*, so it is not this session's to close.

**Nothing is pushed. CI has never run on any of it.** Do not claim it has.

## ⛔ The full suite runs ONCE, AT THE END. Not per unit.

**RULED (Jon, 2026-09-08).** A session ran it **four times** — once per unit,
as a commit gate — burning ~75 minutes and generating the machine load that
trips the flaky family below, which then cost further runs to control against.

Per-unit evidence is **the fast subset + the targeted `slow`/`integration`
files for what the change touched + the gates** (ruff, mypy, contract gate,
`enforcement_lint`, `sahjhan lint`, `enforcement_contract --check`). Those
targeted files are cheap — 26 s for a courier's `real_daemon` set, 1.2 s for
the lint's. Commit on that, and **say in the message that the full suite has
not run and CI has not either.** Naming the gap is the correct move; a local
substitute for CI is not.

`fast-subset-cannot-see-slow-tests` justifies running **the slow tests that can
see your change**. It does not justify running all of them.

⚠️ **The full suite has not run since `489e84d`. W19, W20, W21, W23, W24 and
W25 are all unrun, and CI has never seen any of them — nothing is pushed.**
Each commit says so. Running it wants a quiet machine; see the flake section.

**Last full run: 2026-09-08 at `489e84d` (W18/item 36)** — observed **exit 0**,
**2998 passed, 8 skipped**, zero `FAILED`/`ERROR`, coverage **89.29%**, 24m44s.
2998 + 8 = 3006 = the README badge at that commit; the two numbers check each
other, so read both. **W19 through W25 have had no full run** and each commit
says so. Badge is **3117** at `d0a0cd4`.

**Read from the run's own output, not from the wrapper's exit code.** ⚠️ **Two
corrections, both measured 2026-09-09 against `pyproject.toml` and against real
runs.** This file previously said the `N passed` summary line is suppressed by
`-q`, and that `-q` is not in `addopts`. **Both are wrong.**
`addopts = "--tb=short -q"` — `-q` is always on, and every run this session
still ended with a `2596 passed, 435 deselected in 136.53s` line. `-q` drops the
per-test names, not the summary. So: read the last line, and cross-check with
`grep -cE "^(FAILED|ERROR)"` being 0. There is nothing to drop.

**It covers everything up to and including `489e84d` (W18 / item 36).** W19,
W20, W21, W23, W24 and W25 are the gap, deliberately.

It is *not* CI: CI runs on ubuntu, and the seccomp debt below is a thing no
local run touches. **Note also that the load-flaky hook family did not fail in
this run.** That is consistent with every previous quiet-machine reading and is
**not** evidence about its cause — see the flake section below before drawing
anything from it.

### ✅ RULED 2026-09-04 — W13's item 17 stays open

**Jon: item 17 closes when an occurrence is captured with a named exception AND
explained. Not on the instrumentation merely being in place.** Two alternatives
were put and declined — closing on instrumentation, and folding in the four
other collapsed `except` sites now. **Do not reopen either.** W13 therefore
stays `WIP`, and 17 is not this board's to tick until a real occurrence is
read. The primer's notice already names the exception, so catching one is now
cheap; the work is catching it, not re-arguing it.

Why the evidence pointed this way: 12 full-file runs per arm in one sitting
gave **0/12 failures on the fixed primer and 0/12 on the unmodified control**.
The 1-in-4 rate seen earlier was the new test file's own fixture orphaning
`sleep` children; fixed with `exec sleep`, and the rate went to zero on
**both** arms. There is also no mechanism — the delta does not touch the
healthy path's timing.

### ✅ W16 is closed — sahjhan#50 shipped, and the answer was not a field

**Provenance is a ledger entry column, `recorded_by`** (sahjhan 0.28.0). It
sits beside `seq`, `ts`, `hash` and `prev`; every entry has one, `events.toml`
declares nothing to get it, and `--field recorded_by=…` lands in the event's
fields as inert data while the column keeps its own answer. So the event split
that was put and declined is not merely unwanted — it is unnecessary, and the
eight queries keyed on `type='finding_deferred'` were never touched.

**The four things a later session would otherwise re-derive:**

- **The literal in the gate is `hook:hooks/theoretical_courier.py`** —
  config-dir-relative, because it is the `trusted-callers.toml` key the daemon
  verified the peer against. **`events.toml` declares the same writer as
  `hook:enforcement/hooks/theoretical_courier.py`** and
  `ENFORCEMENT-CONTRACT.md` prints *that* spelling, which matches no row.
  `engine:emits:defer_low` (declared) vs `engine:emit:defer_low` (real) is the
  same mismatch. **The declared producer ids are documentation and nothing
  cross-checks them against the engine's values** — that is W17's H11 to fix,
  and it is now the most concrete thing H11 could catch.
- **`sahjhan lint` L8 is the guard on that literal, and it is real.**
  Substituting a non-manifest path made L8 error on **both** queries and exit
  3. Renaming the courier or dropping it from the manifest empties the
  exclusion, and L8 is what refuses to let that be silent.
- **At the lens gate the two clauses do not overlap.** Provenance alone
  already refuses an agent-typed deferral on a `user_reachable` finding, so
  the correlation's whole remaining job there is the re-grade *after* a
  courier deferral. Reverting either one takes a different single test red.
- ⚠️ **An entry written before 0.28.0 has no `recorded_by` and reads as the
  empty string** — measured by writing a ledger with the 0.27.0 binary and
  querying it with 0.28.0. Its deferral stops counting. **There is no shim:**
  the empty value cannot tell the courier's old row from the agent's, so
  tolerating it would re-open exactly this hole for those ledgers. A run that
  crosses the upgrade already carrying a deferred `theoretical` CRITICAL
  cannot re-earn the closure — `open_theoretical_findings` drops any id that
  carries a deferral, so the courier will not re-fire — and has to be re-run.
  Fail-closed and deliberate; recorded here because it is a real upgrade
  consequence and nothing in the suite can show it.

### Open for Jon — raised 2026-09-23 during W25, neither guessed at

- **A sahjhan ask.** `hook eval` answers a config- or ledger-load failure
  with `ok:true, decision:"allow"`, exit 0 — deliberately
  (`src/cli/hooks_cmd.rs`, `cmd_hook_eval`). Observed with a malformed and a
  missing `--config-dir`. Byte-identical to a genuine allow, so a malformed
  `protocol.toml` silently turns off every PreToolUse gate and every
  PostToolUse auto-record, and **no holtz-side change can tell the two
  apart.** The ask: report a load failure distinguishably and leave block/warn
  to the consumer (`exit_enforcement_error` already decides it). **Not filed.**
  When it ships, `read_hook_eval` in `enforcement/hooks/_common.py` is the one
  place both hooks read the reply — the change lands there.
- **A candidate item (a fifth NotebookEdit disagreement).** `post_tool_hook.py`
  reads `tool_input["file_path"]` alone; W19 fixed `notebook_path` only on the
  PreToolUse side (`_write_target()`), so a notebook edit reaches PostToolUse
  `hook eval` with no `--file`. Recorded in W25, unruled, not fixed.

### Open for Jon — two more, both raised, neither guessed at

- **W32 step 3** (above): does the hand-vendored-old-binary path still want a
  diagnostic? Unit recommends no; not ruled. **Its premise moved on
  2026-09-04** — the pin is 0.27.0, not 0.26.0. That changes nothing about the
  question, which is about the path's existence and not about a version, so it
  is recorded here rather than answered.
- **W06's V8 — a sahjhan question.** `sahjhan event finding --field
  perspective=not-a-lens` exits 0 and the row lands with that value; measured
  on the pinned engine, not inferred. `events.toml` gives `perspective` no
  `pattern` while `reachability` right below it has one, and no field can
  reference a declared `[sets.*]` — so `[sets.perspective]` decorates rather
  than validates. Closing it holtz-side means restating the 13 values in 8+
  places; closing it properly means letting a field name its set, which is an
  engine change. Justine's side is already closed by `f21620e`; this is the
  Holtz side, which the merge reads back from the ledger.

### Carried debts — landed code that did not finish its unit

- **W25 / item 39 — the config-fault half.** The version fault (exit 2, empty
  stdout) now degrades loudly in both hooks; a config or ledger-load fault
  still reads as a genuine allow, because the engine says so. Waits on the
  sahjhan ask under Open for Jon.

- **W22 / item 27 — the seccomp functional run.** The fix is in (`6852e0d`) and
  both new tests inject the errno on macOS, which is what makes them runnable at
  all. **Nothing has executed under a real seccomp filter**, and CI's
  `ubuntu-latest` does not install the optional
  `@anthropic-ai/sandbox-runtime` one. W22's ruling makes standing up that
  session a prerequisite of the **P1 functional test** — raise it when P1 is
  `DONE`, and do not let the green suite read as having covered it.

- **W11 / item 42 — nothing has driven `enforcement_merge` against a real
  daemon.** The interleave tests run against `MockEnforcementDaemon`, whose
  merge and version rules are a port of `sahjhan/src/daemon/enforcement.rs`
  pinned case-by-case by `TestTheMockMergesLikeTheEngine`. That is not
  fastidiousness — it is forced: the daemon authenticates callers by content
  hash, so a test process is refused (`auth_failed`), and the only authenticated
  route is a hook subprocess whose read and write are atomic end to end, leaving
  no window to interleave into. If a functional session ever stands up (see the
  seccomp debt below), driving one real per-actor merge belongs in it.

- ~~**W06 / item 20 — V4's second half.**~~ **Discharged by W07.** The gate is
  lens-scoped now, and `test_the_gate_moves_with_the_lens_it_is_asked_about`
  drives one board under two lenses and requires the answers to differ.

- **W07 / item 3 — `fix_commit` as an escape is asserted structurally, not
  driven.** Its two other routes (`theoretical`'s courier, `fault_injected`'s
  hardening batch) are run end to end against the real daemon; `fix_commit`
  itself cannot be driven to success by any test, because a real daemon refuses
  `enforcement_write` from a test process and so no test can write the
  `suite_green` its gate reads. That is the standing constraint below, not a
  W07 gap — but do not read the green suite as having driven it.

- **The hook tests flake under load, and it is not this branch.** `TestPrimer`,
  `TestPrimerWithMockBinary`, `TestProtocolTrackerDaemonTeardown` and
  `test_source_write_allowed_once_gate_satisfied` fail intermittently whenever
  other pytest work runs alongside — measured 3 in one full-suite run, 4 in a
  pre-commit run, 4/25 and 2/25 in a 25-iteration loop. The same tests fail on
  a **clean tree with everything stashed**, so it predates this work. A commit
  may need retrying; that is not a reason to `--no-verify`.
  **The obvious hypothesis is disproved-as-stated:** the primer's `timeout=5`
  on its `sahjhan status` subprocess looked confirmed (5s failed, 15s and 60s
  passed) until the **control at the unchanged 5s also passed 3/3** — the
  machine had gone quiet between arms. Production is unchanged. `3446897` makes
  the next occurrence report its reason (the harness had been discarding every
  hook's stderr); **get that reason before changing anything.**

  **✅ 2026-09-01/03 — the reason, captured. Read this before re-investigating.**
  A pre-commit run failed **20** of these (far more than the 3–4 measured
  before), and the preserved message was:

  > `ENFORCEMENT DEGRADED: Hook eval subprocess failed`

  That string has exactly one source: `enforcement/hooks/pre_tool_hook.py:155`,
  the `except (OSError, subprocess.TimeoutExpired)` around its
  `sahjhan hook eval` call at `timeout=5`. So the family's proximate cause is a
  **hook's own subprocess to sahjhan failing**, not the test harness and not
  the assertion under test.

  **What is measured, and what is not.** Measured: the identical fast subset,
  same tree, run standalone immediately after, passed **exit 0 twice**; the
  affected files pass alone; `GIT_INDEX_FILE`/`GIT_DIR` set by hand did **not**
  reproduce it, so the git-hook env leak is not this; `trusted-callers.toml`
  regenerated to a **no-op diff**, so a stale manifest is not this either. Not
  measured, and the open question: **which of the two exceptions fires.** The
  handler collapses them, and they call for opposite responses — a timeout says
  the machine was loaded or the daemon is wedged, an `OSError` says the binary
  or socket is wrong. Collapsing them is why three sessions could not falsify
  anything here.

  **A third occurrence, 2026-09-03, on the W12 commit.** One test —
  `TestPreToolHookSubagentTddParity::test_subagent_source_edit_blocked_by_tdd_
  gate` — failed inside `pre-commit` with the same
  `ENFORCEMENT DEGRADED: Hook eval subprocess failed`, and the **identical
  commit retried immediately afterwards passed**. The commit touched five
  PostToolUse couriers and no `pre_tool_hook.py`, and the regenerated manifest
  changed only those five hashes, so the failing hook's own hash was untouched.
  That is one more data point for "load, not this branch" and none at all for
  which of the two exceptions fires. The **full suite run immediately after,
  with nothing else running, failed none of this family** — consistent with
  every previous reading and, again, not evidence about the cause.

  **✅ 2026-09-04 — the first answer to "which exception". `TimeoutExpired`.**
  W13 (`9555fce`) split the *primer's* own collapsed `except` so its degraded
  notice names the exception. Before that commit's fixture defect was found, an
  occurrence was captured reading:

  > `SAHJHAN PRIMER DEGRADED: \`sahjhan status\` did not complete (TimeoutExpired).`

  The subprocess in question was a **three-line `/bin/sh` script that echoes and
  exits** — so a trivial spawn exceeded the 5 s cap under load. That points at
  machine load, and away from a wedged daemon or a wrong binary path, for this
  occurrence. It is one data point from the primer's site, not from the five
  below; do not generalise it to `pre_tool_hook`'s `hook eval` without catching
  one there.

  **And a caution the same session paid for.** The test file W13 added
  *manufactured* this flake on both arms: its mock binary ran `sleep`, which is
  a child of the shell `subprocess.run` kills on timeout, so two orphaned sleeps
  survived every run and loaded the next test. It read as a 1-in-4 flake on the
  unmodified primer and 0-in-3 on the fixed one — i.e. exactly like a fix. Only
  running the control after the fixture was corrected (`exec sleep`) showed
  0/12 on **both**. Before attributing any flake to a code change here, check
  whether your own fixture is the load.

  **✅ 2026-09-09 — the authorship control, and two hypotheses killed.** W20's
  commit failed this family **three times** (`TestPrimer*`,
  `TestProtocolTrackerDaemonTeardown`, `TestBashGuard`, `TestPreToolHookSubagent
  TddParity`, `test_worktree_audit_anchor`, `test_worktree_fixture` — a
  different subset each time), then passed on the fourth with nothing changed.
  What was measured:

  - **It is not `git commit`.** The identical fast subset run by hand, outside
    any hook, failed 3.
  - **It is not the git-hook env leak.** `GIT_DIR`, `GIT_INDEX_FILE` and
    `GIT_PREFIX` set by hand as git sets them: `TestBashGuard` 15 passed in
    5.2 s. Same answer the 2026-09-01 session got; recorded again because two
    sessions have now spent time on it.
  - **It is not test ordering.** I formed and killed my own hypothesis here:
    `pre-commit` does not pass `-p no:randomly` and my green runs did, which
    looked like the whole difference — **but `pytest-randomly` is not
    installed**, so the flag was a no-op and both commands were identical.
    Check `pip list` before believing a plugin is in play.
  - **It is not this branch, and the control is the strongest one so far.** The
    same command on the **stashed, unmodified tree** failed **eight** — more
    than the working tree's three, and a different set. Stash, run, pop.
  - It is not an orphaned-daemon pile-up: `ps aux | grep sahjhan` during the
    worst of it showed **one** idle process.

  So the family is load-sensitive and pre-existing, exactly as recorded, and
  **retrying is the right move** — it took four attempts. Budget for that;
  do not reach for `--no-verify`, and do not start bisecting.

  **The concrete next step, deliberately not taken yet:** split that `except`
  at each of the **five** sites that collapse it — `pre_tool_hook.py:155`,
  `bash_guard.py:78` and `:152`, `_protocol_cache.py:462`,
  `_sahjhan_bootstrap.py:1112` — so the message names the cause. Two of them
  (`_protocol_cache`, `bash_guard:152`) return `None`/`set()` silently and need
  a stderr line rather than a message. **This is instrumentation, not a fix:**
  do not also change a timeout in the same commit, or the next green run will
  again be unattributable. Note `bash_guard.py`'s `timeout=10` is pinned by
  quiz-bank entry `[52]`, and these are daemon-calling hooks, so
  `scripts/hash-trusted-callers.sh` must rerun (pre-commit does it).

---

## Do this next

### 1. ⭐ P4 — W26 next, then W27–W30. Then the three stragglers.

W23, W24 and W25 are `DONE`. What remains, in the board's own order: **W26
(48), W27 (15, 45, 46), W28 (12, 16), W29 (21, 24), W30 (23)**, then W18's item
33, W13's item 17 (open by ruling — do not reopen), and W32's step 3 (a
question for Jon). **W28 drafts the changelog last** — after every other unit.

**What W25 left that a later session would otherwise re-derive:**

- **H12 is live and gated: every top-level gate's printed intent must name an
  escape.** Adding or editing a gate means ending its intent in the way out —
  a declared transition, a `sahjhan …` line whose `event`/`transition`
  referent exists, a script in the tree, a human action, or the gate's own
  command/file. "Printed" means the engine's resolution: own intent → named
  query's → per-type default; composites print only their own. Argument-scoped
  queries (`{{…}}` in the SQL) are exempt via `_argument_scoped`, shared with H8.
- **H12 and H8 meet on multi-step escapes.** Writing "run `X`" where `X` has
  run-wide gates of its own trips H8, correctly — the escape can refuse when
  printed. Two intents describe a path instead (`fix_commit`'s 15-fix cap,
  `fix_loop_start`'s first-pass gate). Do not "fix" them back to the imperative.
- **Both tool hooks read `hook eval` through `_common.read_hook_eval`.** Do not
  re-inline parsing in either; `TestTheTwoHooksAgree` is the tripwire.
- **`read_cache_for_write` is the writer's reader** — it adds `failed`.
  `not_found` is the only `None` that may create the cache, and
  `protocol_tracker` is its only creator. Gates keep `read_cache_with_boundary`.
- **`socket_unplaceable()` decides the unresolvable-`~` case at the reader**,
  not in `boundary_dir` — raising there would crash every
  `suppress(RuntimeError)` writer, since `_mutate` resolves the socket outside
  its `try`.
- **`event_auditor(event)`** derives `justine`/`holtz` from `agent_type`'s last
  `:`-segment. Read in the 2.1.280 binary; **never driven with a live Justine
  dispatch.**
- **The pre-commit flake hit the first W25 commit twice** (12 failures, then 6
  different ones, all the `Hook eval subprocess failed` timeout arm), then
  passed on the third attempt with nothing changed. Standalone, the 12 passed
  in 6.85 s. Same family, same answer: retry.

**Three plan steps in a row have named a mechanism that does not exist, and the
pattern is worth expecting rather than rediscovering.** W20 step 1 warned
against a swap (so the release became a separate predicate ahead of it); W21
step 2 named a query-reuse the engine cannot express; W24's proposed predicate
included a clause `events.toml` already enforces at write time, and its V1 asks
for two things that cannot both hold. In every case the *behaviour* was right
and implementable — build that, and raise the mechanism gap in the unit and the
commit rather than quietly substituting or quietly dropping. All four are
recorded in their units under the step they belong to.

**W23 built two config-derived doc tests, and one of them fired on W24 at the
commit gate** — `test_the_doc_names_every_converge_query` reads `converge`'s
conjuncts out of `transitions.toml`, so swapping one took
`phase-convergence.md` red immediately. Expect it to fire again on any gate-list
change, and fix the doc rather than the test.

**W20 and W21 both turned up the same shape, and it is worth expecting.** Each
had a plan step whose *mechanism* was unavailable while its *behaviour* was
right: W20 step 1 warns against swapping two checks (so the release became a
separate predicate ahead of them), and W21 step 2 names a query-reuse the engine
cannot express. In both cases the behaviour was implemented and the mechanism
gap was raised rather than papered over. Do that, and say which it was.

**Before touching `merge_target_exists` or anything that merges:** a merge is a
close, so every term in that predicate is a way the close would otherwise be
free. It now needs the target **open** and **at least as severe**, both graded
by latest filing. The three shapes it refuses each have a route —
`defer cant-reproduce` for a closed target, a re-file for a low one, and
`fix_commit`/`resolve` when every other finding is deferred and no legal target
exists at all. `phase-fix-loop.md` teaches the first two. `sahjhan lint` will
not catch a gate whose refused cases have no route; only the enumeration will.

**W19 turned up a fourth disagreement its own unit did not name, and the shape
generalises: a tool's input key is a harness fact, not a guess.**
`NotebookEdit` sends **`notebook_path`**, not `file_path` — confirmed by
grepping the installed `claude` binary, which destructures that key by name.
`pre_tool_hook.py` read `file_path` alone, so registering the tool and widening
the gate would both have been decorative. Worse, the empty path fails in
**opposite directions at two sites**: the managed-path guard has nothing to
match and *allows*, while `hook eval` runs with no `--file` so the TDD gate's
`tests/**` exemption cannot apply and it *denies* the test file the gate is
demanding. Both are pinned now. **Before adding a tool to any guard, check what
key that tool's input actually uses.**

**Item 33 needs a decision before code, and the unit now carries the two
measurements that shape it.** Step 3 offers "re-run the real check **or** bind
the marker to a host-derived signal it cannot echo"; re-running is not open to
a PostToolUse hook at ~24 minutes, so it is the second. Both halves were
measured while doing item 36:

- **`trusted-callers.toml` has no `scripts/` entries** — `grep -c '^"scripts/'`
  is 0. The obvious binding (resolve the executed path, check its content hash
  the way the daemon checks a hook's) has no row to check against yet, and
  `TRUSTED_SCRIPTS` is hand-kept, so nothing will discover it for you.
- **`verify_suite.py:323` runs the suite through `os.environ.get(
  "HOLTZ_PYTEST") or DEFAULT_PYTEST`.** So verifying the script's identity
  does **not** satisfy V6: a genuine script, an honest `--scope full`, and a
  `HOLTZ_PYTEST` that collects nothing still records `full`. Whatever binds
  the marker has to reach that seam or say plainly that it does not.

**And item 36 has a trap worth reading before touching the courier again.**
`theoretical_courier.py` is a daemon-calling hook. Editing it and not rerunning
`scripts/hash-trusted-callers.sh` turns the four `TestTheCourierWritesForReal`
tests red with the deferral simply **absent** — which reads exactly like a
broken trigger, and the trigger was fine. Hit and diagnosed here; only
`real_daemon` tests can see it.

**What H11 does and does not cover — read before assuming item 22 closed the
class.** H11 asks whether a gate excusing itself on an escape-qualifier
literal (`reason`, `trigger`, `scope`) names a writer it may trust: the event
is agent-unwritable, or the same alias's `recorded_by` is pinned to somebody
the agent cannot be. It is *not* a check on how writers are spelled.

- **`sahjhan lint` L8 covers the gate side of the spelling** — a `recorded_by`
  filter naming a script the manifest does not list is an error, so writing
  the declared `hook:enforcement/hooks/…` form into a gate fails the build.
- **Nothing covers the declaration side.** `events.toml` will happily declare
  `hook:enforcement/hooks/theoretical_courier.py` and `engine:emits:defer_low`
  while the engine stamps `hook:hooks/theoretical_courier.py` and
  `engine:emit:defer_low`. H2 checks the declared path against the
  *filesystem*, which is why the repo-root form is right there and wrong
  everywhere a `recorded_by` value is compared. **This is a live gap, not a
  closed one** — a candidate item, unruled, recorded rather than fixed.

Then W19 (40, 47), W20 (41, 38), W21 (9). After P3: P4 (W23–W30) and the
`WIP` stragglers (W16's step 1, W13's item 17, W32's step 3).

**Two things W15 leaves on the table.** Neither is a W15 gap — both are
recorded so they are found by reading rather than by surprise:

- **Quoted operators still split.** `git commit -m "a & b"` yields two
  segments, exactly as `"a; b"` always has. Uniform and pre-existing, and
  fail-closed for the guards (more segments read, not fewer). The one shape it
  bites is an *allowlist*, where over-segmentation denies:
  `sahjhan daemon start --config-dir "a & b"` would be refused recovery. No
  test pins the quoted case in either direction.
- **`>|` (noclobber override) splits on its `|`** — `foo >| bar` becomes
  `foo >` and `bar`. Measured identical before and after W15, so it is
  untouched, but it is the same defect class as the `&` W15 fixed. It wants
  its own unit, not a silent widening of a closed one.

**Before touching a gate or a query, read what W14 just established:**

- **`amplification_diverging` counts per round, up to that round.** The join is
  `f.seq <= r.seq`. Nothing recorded after a round can change what that round
  counted. Any escape you are tempted to describe as "clears the block" needs
  checking against that.
- **Two seats on one predicate is the established arrangement**, not a
  duplication to tidy away: `round_item_cap_exceeded` and now the amplification
  breaker each block at `pattern_done` *and* `iteration_boundary`, because the
  taught path never reaches the first. `enforcement_lint` H8 is what keeps a
  block naming an escape it does not gate on.
- **`enforcement_contract.py --check` is gated and goes stale on any config
  edit.** `--write` and commit it in the same commit.

**W12 left a shared module worth knowing about before touching a courier:**
`enforcement/scripts/_recorded_command.py`. A recognizer's `None` no longer
means one thing — the couriers ask `looks_like_a_record` to tell "not my
command" from "my command, refused", and warn only on the second. Adding a
fifth recorded command means importing from there, not repeating the shape.

**Before starting any of them, read W09's settled decision** (the ⭐ box in its
unit): when a field needs checking in two places, look at *which* declaration
the engine actually enforces before picking the source. `perspective` and
`reachability` needed different sources for the same kind of check, and the
difference was measurable in one command against the binary.

### 2. W22 (item 27) and W11 (item 42) are `DONE` with debts — see Carried debts above.

---

## Standing traps — all measured, all have cost a session

- **Read the filing before asking.** Two questions in the previous handoff were
  already answered in sahjhan#46, an issue *this repo wrote*. `gh issue view`
  the filing and re-read the plan item before putting any design question to
  Jon. If the record answers it, build it.
- **Never edit the tree while the suite runs.** Three restarts today. Finish
  every edit, then run.
- **Full suite is a release gate, not a commit gate.** ~40 min, longer than the
  Bash cap. `pre-commit` runs the fast subset and the contract gate; CI runs the
  full suite on dev pushes. Run it in the background and read the file; a
  partial `.....` line is not a result.
- **`git add <paths>`, never `-A`.** The tree carries untracked-by-design plan
  docs and four ~112MB binaries. Read column 1 of `git status --short` after
  staging — one bad path makes the whole `git add` stage nothing.
- **Editing a daemon-calling hook silently disables enforcement** until
  `bash scripts/hash-trusted-callers.sh` reruns. Only `real_daemon` tests catch
  it. **And it does not present as an authentication failure.** Measured on
  W31: the first run after the code change had *nothing* charged and an
  **empty** state line, because `two_actors.freshen()` drives
  `protocol_tracker.py` too — so the refused write meant the cache was never
  created and the primer had nothing to print. It reads exactly like "the change
  broke the charge". Before debugging a real_daemon test that suddenly sees no
  state, rerun the manifest.
- **`git` prints two `[dev …]` hashes and one is orphaned** (post-commit
  amends). Confirm with `git merge-base --is-ancestor`, never `cat-file`.
  **Which one is orphaned is not fixed.** Five occurrences, and every position
  has now been seen: on `0df93b0` (W07) the *second* printed hash was dead; on
  `2c50986` (W10) the *first* was live; on `7231035` (W12) and again on
  `6092c79` (W21) the live hash **was not in the visible output at all**; on
  `fd60952` (W20) the *first* was live again. Do not learn the position and do
  not trust what you can see — run `git log -1 --format=%H`.
- **The README test badge is a gated derived number** — bump it in the same
  commit that adds tests, before the run you intend to cite.
- **A real daemon refuses `enforcement_write` from a test process**
  (`auth_failed` / `pid_resolution_failed`). No test can write a `restricted`
  event, so gates depending on one must be asserted by *what they read*, not by
  passing. See `test_fix_commit_caller_anchor.py` for the pattern, including
  deriving a probe config from `enforcement/` at test time rather than pasting a
  copy that cannot drift-fail.
- **`gate check <transition>` without its arguments reports parameterised gates
  as `? unevaluable`, not as passing.** So "the run is not blocked on X" read
  off an unbound `gate check` is vacuous for every gate that takes an argument
  — the line is there and carries no ✗. Bind them (`gate check "set complete
  perspective" current_perspective=security`); `_Run.gate_check` now forwards
  `key=value` args for this reason. Measured 2026-09-01 while scoping the lens
  gate, on a test that had been asserting exactly that absence.
- **A transition's `state_transition` row lands BELOW the events it emits**, and
  a `gate_attestation` sits between them. Measured on 0.26.0 while doing W10:
  `defer cant-reproduce` writes `state_transition` at seq 6 and its
  `finding_deferred` at seq 8. So **any window anchored on "the last
  state_transition" is moved by the very transitions whose emits it is trying
  to bound** — a second deferral drops the first one out of the window, with no
  concurrency involved. Item 35 read as a concurrency bug and was not one.
  Before writing `seq > MAX(state_transition)`, ask which transitions emit into
  the set you are windowing.
- **`sahjhan query --format json` spells an absent optional column `"NULL"`** —
  the four-character string, not `null` and not `""`. So
  `str(row.get(x) or "")` keeps it and passes it straight back into a write,
  where a pattern-constrained field refuses it. `merge_punchlists._optional()`
  is the named handling; use it rather than re-deriving the check.
- **Run every new test RED against the unmodified tree first** and read the
  reason, not the colour. Unchanged-behaviour tests must be green before, during
  the non-vacuity mutation, and after.
- **A whole-fix stash is usually NOT that control.** If the new test module
  imports the function the fix adds, the unmodified tree gives an
  `ImportError` at *collection* — pytest reports one `ERROR`, zero `FAILED`,
  and every assertion in the file is skipped. It looks like a strong RED and
  says nothing about which guard was holed. Measured on W15. The control that
  works is a **targeted single-line mutation per claim**, run in the same
  sitting: revert the character class, revert the one `resolve_indirection`
  line, revert the one lookbehind — and read *which* tests go red each time.
  If a mutation takes down a test you did not predict, that is a finding.
- **A green run after a change is not evidence when the failure is load-flaky.
  Run the control.** 2026-09-01: raising the primer's status timeout made four
  failing tests pass, three times running — and then the **unchanged 5s passed
  three times too**. Both arms were measuring an idle machine. Before believing
  any fix for an intermittent failure, re-run the *unmodified* tree under the
  same conditions in the same sitting.
- **`git commit` can outlive the 2-minute Bash default** — `pre-commit` runs the
  fast subset. Pass an explicit timeout; a killed commit leaves everything
  staged and looks like a hook failure.
- **`tests/hook_runner.py` used to discard a hook's stderr** whenever the hook
  printed valid JSON, and defaulted its exit code to 0. Fixed in `3446897`. If
  you are reading a hook test that "says nothing", check you are on that commit
  or later before concluding the hook was silent.

---

## Environment

sahjhan pinned at **v0.28.0** (`_resolve.SAHJHAN_VERSION` governs; the marker
and binary self-heal to it). `check_sahjhan_pin.py` exit 0, `bin/sahjhan
--version` → `sahjhan 0.28.0`, and all four vendored binaries match the
release's published `SHA256SUMS`. Keep in mind what a green pin check does and
does not say: it says the three places agree, not that they agree on the
version you want — check the binary itself.

**0.28.0 makes the ledger entry's own column names reserved** — `recorded_by`,
`seq`, `ts`, `type`, `hash`, `prev`, `schema`, `engine`, `protocol`. A config
declaring a field with one of those now fails validation instead of breaking
every query at runtime with a duplicate column. `events.toml` declares none of
them; `validate` is `valid.` and `lint` is 0 errors / 7 warnings from 8 checks.
`scripts/install-hooks.sh` defaults to dev mode — the plugin's enforcement hooks
are **not** wired into this repo's own session, deliberately.

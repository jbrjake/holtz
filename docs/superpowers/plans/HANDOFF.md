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

**Report as `N of 30 units, M of 49 items`, naming what remains.** Banned:
"the release gate is closed"; "blocked only on X" when a pile sits behind X;
any phrasing where one unit closing reads as the work closing.

---

## Status

**15 of 32 units · 20 of 51 items · 31 items across 17 units remain.**
W13 is `WIP`, not done: it closed item 37 and left item 17 open, so it moves
the item count and not the unit count.

Done: W01 (fixtures, no item) · W02 (29) · W03 (31) · W04 (19, 1) · W05 (2) ·
W08 (32, 43) · W22 (27) · W06 (20) · W07 (3) · W09 (25, 26) · W10 (35) ·
W12 (34, 28) · W11 (42) · W14 (5, 10) · W31 (50). Commits are in `git log`; do
not re-summarise them here.

**W31 landed 2026-09-04** — `c12469f`, all four validations driven. **P2 is now
finished** except W13's item 17 (open by ruling) and W32's step 3 (a question
for Jon). The board is P3 (W15–W21) and P4.

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

**The full suite was run locally on 2026-09-04 at W31's tree** — `pytest --cov …
--cov-fail-under=80`, observed **exit 0**, **2921 collected, 8 skipped, zero
`FAILED`/`ERROR`**, coverage **89.30%**. Read from the run's own output, not
from the wrapper's exit code — and note this repo's `-q` + coverage combination
prints **no `N passed` summary line at all**, so the reading is: every progress
mark is `.` or `s`, and `grep -cE "^(FAILED|ERROR)"` is 0.

**It covers everything up to and including `7d69854` (W14) and W31's working
tree**, which is what was committed as `c12469f`. The earlier gap — a full run
that predated W14 — is closed.

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

### Open for Jon — two, both raised, neither guessed at

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

### 1. ⭐ P3 — W15 (item 30) onward.

P2 is finished. W10, W11, W12, W14 and W31 are `DONE`; W13 is `WIP` with item 37
closed and item 17 open **by ruling** (above) — that is decided, not blocking.

**W15 (item 30) is next**, and nothing blocks it. Then W16 (18) → W17 (22),
W18 (36, 33), W19 (40, 47), W20 (41, 38), W21 (9). After P3: P4 (W23–W30) and
the two `WIP` stragglers (W13's item 17, W32's step 3 — the latter still a
question for Jon).

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
  **Which one is orphaned is not fixed.** Three occurrences, three answers: on
  `0df93b0` (W07) the *second* printed hash was dead; on `2c50986` (W10) the
  *first* was live; on `7231035` (W12) the live hash **was not in the tail of
  the output at all** and the only visible one was orphaned. Do not learn the
  position and do not trust what you can see — run `git log -1 --format=%H`.
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

sahjhan pinned at **v0.27.0** since `0605ed2` (`_resolve.SAHJHAN_VERSION`
governs; the marker and binary self-heal to it). `check_sahjhan_pin.py` exit 0,
`bin/sahjhan --version` → `sahjhan 0.27.0`, and all four vendored binaries match
the release's published `SHA256SUMS`. Keep in mind what a green pin check does
and does not say: it says the three places agree, not that they agree on the
version you want — check the binary itself.
`scripts/install-hooks.sh` defaults to dev mode — the plugin's enforcement hooks
are **not** wired into this repo's own session, deliberately.

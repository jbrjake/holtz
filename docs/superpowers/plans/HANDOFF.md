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

**9 of 32 units · 10 of 51 items · 41 items across 23 units remain.**

Done: W01 (fixtures, no item) · W02 (29) · W03 (31) · W04 (19, 1) · W05 (2) ·
W08 (32, 43) · W22 (27) · W06 (20) · W07 (3). Commits are in `git log`; do not
re-summarise them here.

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
  the end of W32): with #47 shipped and the pin at 0.26.0, does the
  hand-vendored-old-binary path still want a diagnostic? The unit recommends
  **no** but records it as *not ruled*, so it is not this session's to close.

**Nothing is pushed. CI has never run on any of it.** Do not claim it has.

### Open for Jon — two, both raised, neither guessed at

- **W32 step 3** (above): does the hand-vendored-old-binary path still want a
  diagnostic now the pin is 0.26.0? Unit recommends no; not ruled.
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

### 1. W09 — items 25, 26. Unblocked, and W06 built its mechanism.

Do **not** write a second required-field checker: `SetValuedField` +
`set_valued_fields()` + one loop in `validate()` is the mechanism, and
`reachability` is a row. Read W06's *"How W09 plugs in"* box first — there is
one genuine decision there (`reachability` has no `[sets.*]` to point at), and
it is W09's to make, not a gap in the mechanism.

**W07 left a `SetValuedField`-shaped precedent W09 should not mistake for its
own work:** it added `--lens` to `findings.py list`, which is a *read* filter,
not a required-field check. W09's mechanism is still W06's.

### 2. W22 (item 27) is `DONE` in code only — see Carried debts above.

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
  it.
- **`git` prints two `[dev …]` hashes and one is orphaned** (post-commit
  amends). Confirm with `git merge-base --is-ancestor`, never `cat-file`.
  **Which one is orphaned is not fixed** — on `0df93b0` (W07) the *second*
  printed hash was the dead one, the reverse of the previous occurrence. Do not
  learn the position; run the check.
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

sahjhan pinned at **v0.26.0** (`_resolve.SAHJHAN_VERSION` governs; the marker
and binary self-heal to it). `check_sahjhan_pin.py` exit 0.
`scripts/install-hooks.sh` defaults to dev mode — the plugin's enforcement hooks
are **not** wired into this repo's own session, deliberately.

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

**12 of 32 units · 15 of 51 items · 36 items across 20 units remain.**

Done: W01 (fixtures, no item) · W02 (29) · W03 (31) · W04 (19, 1) · W05 (2) ·
W08 (32, 43) · W22 (27) · W06 (20) · W07 (3) · W09 (25, 26) · W10 (35) ·
W12 (34, 28). Commits are in `git log`; do not re-summarise them here.

**W11 (item 42) is UNBLOCKED and is the first thing to do — see "Do this
next".** `sahjhan#49` shipped in **v0.27.0** (2026-09-03/04). Both halves of
the ask landed. The pin is still at 0.26.0, so **moving it is step 0 of W11**.

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

**The full suite was run locally on 2026-09-03 at `7231035`** — `pytest --cov …
--cov-fail-under=80`, observed **exit 0**, no `FAILED` lines, coverage 89.35%.
That covers everything on the branch, not just this session's three commits.
It is *not* CI: CI runs on ubuntu, and the seccomp debt below is a thing no
local run touches.

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

### 1. ⭐ W11 (item 42) — start here. Unblocked by sahjhan 0.27.0.

**Step 0, before any of W11's own steps: move the pin.** It is at 0.26.0 and
`check_sahjhan_pin.py` currently passes *at that version*, so a green pin check
is not evidence you are on 0.27.0.

```bash
bash scripts/vendor-sahjhan.sh 0.27.0
python3 scripts/update_sahjhan_pin.py 0.27.0     # this is what actually governs
python3 scripts/check_sahjhan_pin.py             # must exit 0
```

`_resolve.SAHJHAN_VERSION` is the pin that decides at runtime; vendoring alone
leaves the resolver on the old version and the next hook invocation silently
re-downloads it *and rewrites the marker back*. `update_sahjhan_pin.py` exists
to close that by construction — use it, do not hand-edit `_resolve.py`. This
also lights up **W11's V5**, which was unreachable while step 2 was theoretical.

**What 0.27.0 gives you.** Read `gh issue view 49 --repo jbrjake/sahjhan` for
the full writeup; these are the facts checked against the source at
`src/daemon/enforcement.rs` and `src/daemon/mod.rs`, not read off the summary:

- **`enforcement_merge` is a NEW op. `enforcement_update` is unchanged** —
  still `PatchMode::TopLevel => state.extend(patch_obj)`, byte for byte what
  0.26.0 did. So this is not a behaviour change to absorb; it is a second op to
  pick per call site. `update_cache` stays and is still right wherever the
  caller owns the whole key. Add `merge_cache` beside it; do not reroute
  everything.
- **RFC 7386 semantics**, and the two edges that will bite:
  - **`null` deletes, at any depth.** That is the exact spelling for
    `stall_cleared`. (Holtz's readers already treat `0` and `[]` as equivalent
    to absent — `stall_count` is `.get(actor, 0)`, `pending_commits` filters
    empty lists — so a sentinel works too. `null` is the precise one.)
  - **Arrays REPLACE wholesale; they are not merged element-wise.**
    `unregistered_commits` values are lists, so a merge naming one actor sends
    *that actor's whole list*. It is a per-actor write, **not** an append. An
    actor racing itself therefore still needs `expect_version` — the merge only
    buys you safety from *siblings*.
- **`expect_version` is optional on all three mutations**, and the compare runs
  inside the same `vault.lock()` block that stores. That is why this is not the
  client-side compare-and-swap W11's step 2 forbids: the compare is on the
  daemon's side of the lock. A loser gets `version_conflict` with the current
  version attached and re-reads and retries; nothing is clobbered.
- **`enforcement_read` now returns `version` beside `data`.**
  `read_cache_with_boundary` has to surface it, or no caller can pass
  `expect_version`.
- **The token hashes the blob as stored, not the bytes `enforcement_read`
  serves** (which overlay `state` from the ledger, #57). So **a transition does
  not invalidate your token — only a write does.** Do not build a retry loop
  that assumes otherwise.

**The four write sites, all in `protocol_tracker.py`:**

| line | today | becomes |
|---|---|---|
| `:347` / `:349` | `update_cache({"stall": <whole map>})` | `merge_cache({"stall": {actor: n}})` |
| `:322` | `update_cache` with both whole maps | one merge naming only this actor's two entries |
| `:287` | full `write_cache(cache)` from a snapshot taken **before two 5 s subprocesses** | carry `expect_version` from the read that produced the snapshot; retry on `version_conflict` |

`_discharge_registered_commits` → `pending_commits_discharged` is the same
shape as `:287`: genuinely cross-actor, so it wants `expect_version` and a
retry rather than a per-actor merge.

**`protocol_tracker.py` is manifest-pinned** (`trusted-callers.toml:24`), so
`bash scripts/hash-trusted-callers.sh` must rerun or enforcement silently fails
open. Only the `real_daemon` tests catch that, and this session hit exactly
that trap on W12 — five courier edits, and the failure surfaced as
`caller not authenticated` in unrelated integration tests.

**Do not write the flattening dodge.** `stall::<actor>` as top-level keys was
considered and rejected before the ask went upstream; the unit records why.

### 2. Then W13 (37, 17), then W14 (5, 10).

P2's remainder. W10 and W12 are `DONE`. Neither W13 nor W14 depends on W11.

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

sahjhan pinned at **v0.26.0** (`_resolve.SAHJHAN_VERSION` governs; the marker
and binary self-heal to it). `check_sahjhan_pin.py` exit 0 — **at 0.26.0**,
which is the point: a passing pin check says the three places agree, not that
they agree on the version you want. **v0.27.0 is released and W11 needs it**;
moving the pin is step 0 of "Do this next".
`scripts/install-hooks.sh` defaults to dev mode — the plugin's enforcement hooks
are **not** wired into this repo's own session, deliberately.

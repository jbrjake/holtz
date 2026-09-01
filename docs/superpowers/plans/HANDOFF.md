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

**7 of 32 units · 8 of 51 items · 43 items across 25 units remain.**

Done: W01 (fixtures, no item) · W02 (29) · W03 (31) · W04 (19, 1) · W05 (2) ·
W08 (32, 43) · W22 (27). Commits are in `git log`; do not re-summarise them here.

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

### Carried debts — landed code that did not finish its unit

- **W22 / item 27 — the seccomp functional run.** The fix is in (`6852e0d`) and
  both new tests inject the errno on macOS, which is what makes them runnable at
  all. **Nothing has executed under a real seccomp filter**, and CI's
  `ubuntu-latest` does not install the optional
  `@anthropic-ai/sandbox-runtime` one. W22's ruling makes standing up that
  session a prerequisite of the **P1 functional test** — raise it when P1 is
  `DONE`, and do not let the green suite read as having covered it.

---

## Do this next

### 1. W06 — item 20. Then W07 (item 3), which depends on it.

**The field is `**Lens:**`. RULED (Jon, 2026-09-01):** *"they're lenses, they're
always lenses."* W06's plan text saying `**Perspective:**` is struck. Internal
identifiers (`[sets.perspective]`, `PunchlistItem.perspective`) stay — they are
not names a reader sees.

**Two premises in that plan are stale; the plan has been corrected but read this
anyway.** `Lens` is *already* taught (`justine-skill.md:250`,
`phase-audit.md:67,94,100`) and already in archived punchlists. The break is
downstream: `validate_punchlist.py` lists `Lens` in `FIELD_NAMES` as a **section
terminator only** — never extracted, no attribute on `PunchlistItem`,
`merge_punchlists.justine_findings` never passes one — so the value Justine
writes is parsed, discarded, then defaulted to `"unspecified"`, which no set
contains and nothing refuses.

Owed: extract it, validate membership against `[sets.perspective]`'s 13 values,
make `punchlist-format.md:15` required and replace its 6-value inline copy with
a pointer to the set.

**Constraint:** `validate_punchlist.py` is deliberately Python 3.9-compatible
(`# PEP 604 unions run on Python 3.9 (issue #59)`) and `tomllib` is 3.11+. Read
the set with one scanner in production, cross-checked in a **test** against
`tomllib` — one derivation, not two that can drift.

**Build the required-field mechanism once.** W09 step 3 needs the same one for
`reachability`; if W09 writes a second, W06 under-built.

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
- **The README test badge is a gated derived number** — bump it in the same
  commit that adds tests, before the run you intend to cite.
- **A real daemon refuses `enforcement_write` from a test process**
  (`auth_failed` / `pid_resolution_failed`). No test can write a `restricted`
  event, so gates depending on one must be asserted by *what they read*, not by
  passing. See `test_fix_commit_caller_anchor.py` for the pattern, including
  deriving a probe config from `enforcement/` at test time rather than pasting a
  copy that cannot drift-fail.
- **Run every new test RED against the unmodified tree first** and read the
  reason, not the colour. Unchanged-behaviour tests must be green before, during
  the non-vacuity mutation, and after.

---

## Environment

sahjhan pinned at **v0.26.0** (`_resolve.SAHJHAN_VERSION` governs; the marker
and binary self-heal to it). `check_sahjhan_pin.py` exit 0.
`scripts/install-hooks.sh` defaults to dev mode — the plugin's enforcement hooks
are **not** wired into this repo's own session, deliberately.

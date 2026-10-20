# Release worklist — handoff #4

**Supersedes handoff #3.** Its account of W01–W05 is still accurate and its
three carry-forward lessons still hold; what has changed is that W08 is half
done and **the run is deliberately paused** on an upstream fix.

**Read in this order:**

1. **This file** — where things stand, and what unpauses it.
2. **`2026-08-27-release-worklist.md`** — the working document. Every defect,
   plan step and validation check, with `Evidence:` slots filled through W08's
   item-32 half. Do the work from this, not from a handoff.
3. **`2026-08-27-release-worklist-ORIGINAL.md`** — Jon's text byte-for-byte, so
   everything an implementer added is diffable.
4. **`…-handoff-1.md` §2, §2a, §3** — still the best account of the fixtures and
   the stale-cache trap.

---

## Where things stand

| Unit | Items | Status | Commit |
|---|---|---|---|
| W01 | fixtures F1/F2/F3 | `DONE` | `17e648e` |
| W02 | 29 | `DONE` | `6070c66` (v0.169.2) |
| W03 | 31 | `DONE` | `eae803d` (v0.169.3) |
| W04 | 19 | `DONE` | `2b94345` (v0.169.4) |
| W04 | 1 | `DONE` — route-around undone | `dad0f47` (v0.169.5) |
| W05 | 2 | `DONE` | `ca29f69` (v0.169.6) |
| W08 | **32** | `DONE` | `780ba47` (v0.169.7) |
| W08 | **43** | **`BLOCKED` on [sahjhan#46](https://github.com/jbrjake/sahjhan/issues/46)** | — |
| W06 | 20 | `TODO` — next in worklist order | — |
| W07 | 3 | `TODO` — depends on W06 | — |
| W22 | 27 | `TODO` — rest of P1 | — |
| W31 | **50** (new) | `TODO` | — |
| W32 | **51** (new) | `TODO` — filed as [sahjhan#47](https://github.com/jbrjake/sahjhan/issues/47) | — |

**Release gate was W02, W03, W04, W08.** The first three are done. W08's *gate
rationale* is item 32 — the dashboard's own words: `convergence-speed-status.md:51`
reads SHIPPED while saying "clear still run-global". That sentence is now true.
Item 43 is a bad message on a correct block; it is in W08 for proximity, not
because the gate's reasoning reaches it. **Whether that closes the gate is
Jon's call, not this document's.**

**Nothing is pushed.** Everything is local on `dev`. **CI has never run on any
of it.** Do not claim it has.

---

## Why the run is paused

W08's plan step 5 said: *if no reachable escape exists, that is a question for
Jon — not a licence to narrow the block.* **That branch fired.** The evidence,
all driven rather than read:

1. **A command gate always evaluates at the project anchor.** `gate check
   fix_commit item_id=BH-101` run from a linked worktree whose `HEAD` message
   *is* `fix(x): BH-101`, against a project root whose `HEAD` is something else:
   the `git log -1 --format=%B | grep -q 'BH-101'` gate fails **identically from
   both**, same `tree_hash` too. `transition` builds the same context
   (`transition.rs:293` + `:342`), so the dry run is evidence about the real
   thing.
2. **`git commit --amend` is allowed** — driven through `commit_gate.py`, both
   spellings — because `is_git_commit` excludes it by construction.
3. **But it is not an escape.** It lands the revision and discharges nothing:
   the charge clears only on registration, registration needs the merge, and the
   merge is the orchestrator's.

So the commit gate's block is reachable by a subagent and its printed escape is
not. **RULED (Jon): file it upstream and pause for a handoff** — rather than
print `git commit --amend`, which was the recommendation and which was rejected.

**What unpauses this session's successor:** sahjhan#46 closed. Then W08's
V6/V7 become doable — the block can print something a subagent can run, and a
test can execute it as printed.

---

## What this session did

### W08's item-32 half, and a third defect inside it

Item 32 named two defects: no success check, and a run-global clear. Both fixed:
the clear is gated on `exit_code == 0`, and *what* it clears comes from the
ledger — `[queries.resolution_commit_hashes]`, which already existed for
`hardening_batch.py`. `fix_commit` auto-emits `finding_resolved` stamped with
`git rev-parse --short=7 HEAD`, so **the question the old comment called
unanswerable was only unasked.**

Driving V3 surfaced a third, in the item's own first sentence
(*"`_runs_transition` is pure `cmd.split()` adjacency"*): the verb was read off
the **whole line**, so `sahjhan … status && echo remember to run transition
fix_commit` cleared the map — exit 0, and a whitespace split cannot tell an
echoed word from an argument. Neither of the item's two named fixes touches
that. `_runs_transition` now reads only segments that invoke the sahjhan CLI,
and only their unquoted words.

`pattern_done` had the identical missing success check two lines below. **RULED:
fix here** rather than file it.

### Two new items recorded, not fixed

- **50 (W31): a rewritten commit is never discharged.** The tracker charges the
  hash `git commit` printed; the ledger stamps the hash at `HEAD`. A `git
  rebase` between them — which `phase-fix-loop.md` prescribes and which rewrites
  the hash for every subagent after the first merge — makes those different
  commits. Safe direction, per-actor, cannot deadlock. **RULED: accept, record.**
- **51 (W32): sahjhan's anchor does not understand linked worktrees.**
  `project_root_from` walks up for `data_dir` and falls back to `cwd`; a
  *sibling* worktree therefore anchors on itself and `status`, `event` and
  `query` all fail with `I/O error (os error 2)`, exit 2. **RULED: filed as
  [sahjhan#47](https://github.com/jbrjake/sahjhan/issues/47).** W32 step 3 is
  still open and does not depend on #47 shipping: the failure is loud but says
  nothing about worktrees, so holtz may still owe a diagnostic that names the
  cause.
  ⚠️ **Read W32's severity paragraph before acting on it.** It does *not* bite
  the default layout: Claude Code nests worktrees at
  `<repo>/.claude/worktrees/<name>/`, and the walk-up from there passes through
  the repo root. Stating it unqualified would be an overreach.

---

## Three things to carry forward

### 1. A mock daemon cannot answer a question about the ledger

The pending-commit discharge is decided by a ledger query. Against `mock_daemon`
there is no ledger, so **every mock-driven `fix_commit` takes the fallback
branch** — which is worth pinning and pins nothing about the rule. The rule is
only observable on `real_daemon`, which is why V1/V4 are F2 tests.

The trap this avoids is handoff #1 §2a's in a new place: a test that passes
because the code never ran is indistinguishable from one that passes because it
ran correctly. If you find yourself asserting the *new* rule against the mock,
you are asserting the fallback.

### 2. A real daemon will not let a test write the cache

`enforcement_write` from pytest returns `auth_failed`, reason
`pid_resolution_failed` — the caller is not a hash-pinned hook. So F2 seeds the
buckets through `protocol_tracker.py` and reads them back through
`commit_gate.py`. That is a constraint worth keeping rather than routing around:
it means no assertion can rest on a cache shape production never produces.

`TwoActors` now carries `git_commit`, `fix_commit_transition`, `charges` and a
`commit_hash` on `sibling_fix_commit`. Reach for those before writing new
scaffolding.

### 3. A negative test can be negative for the wrong reason

`test_a_diagnostic_that_names_the_verb_in_its_sql_clears_nothing` was written
first with the SQL ending `-- transition fix_commit"`. It passed — but under the
*old* code too, because the closing quote rides on `fix_commit` and the
adjacency check compares whole tokens. It pinned nothing. Rewritten so the two
words sit inside the quotes with a word after them, it goes red under the old
scan, which is what makes it a guard.

The general form, which is the reusable part: **when a test asserts something
does not happen, check that it would have happened.** Four mutations were
applied and reverted for exactly this reason (V8), and one of them is what
caught this test.

---

## Standing facts

- **Gates observed at `780ba47`** (all `.venv`, not a clean environment): full
  suite `pytest -p no:randomly -q` → **`FULL_EXIT=0`**, zero `FAILED`/`ERROR`,
  2738 collected; `ruff` exit 0; `mypy` exit 0 (69 files);
  `enforcement_lint.py` 0 errors / **2 pre-existing warnings** (the H1
  `prediction` pair); `contract_gate.py` PASS (100 commands, 30 field-checked);
  `enforcement_contract.py --check` current; `check_sahjhan_pin.py` exit 0 at
  v0.24.0 with `bin/sahjhan --version` agreeing. **No `--no-verify`.**
  Not a substitute for CI: item 15 (W27) is that a fresh checkout cannot collect
  `tests/test_property_based.py` because `hypothesis` is undeclared.
- **The full suite takes longer than ten minutes.** Run it in the background and
  read the file; a foreground `Bash` call is killed at the cap and tells you
  nothing. Do not report a partial `.....` line as a result.
- **The README test badge is a gated derived number.** 2729 → **2738**.
- **`git` prints two `[dev …]` hashes and one is orphaned.** Position is not a
  rule. Only `git merge-base --is-ancestor <hash> HEAD` distinguishes them.
- **Regenerate `enforcement/trusted-callers.toml` before every `real_daemon`
  run**, including before each non-vacuity mutation — a stale hash makes the RED
  an artifact. This was done before every mutation in V8.
- **`sahjhan gate check <t> <args…> --json` binds `--json` as a positional
  template value.** `gate check fix_commit item_id=BH-101 --json` expanded
  `{{item_id}}` to `--json` and the gate failed on `grep: unrecognized option`.
  It cost one probe round-trip. Not filed.
- **The plan docs are untracked by design.** Stage explicitly — `git add
  <paths>` — never `git add -A`. The tree also carries a ~100MB vendored binary.

---

## Suggested next step

**Check sahjhan#46 first.** If it has shipped, W08's item-43 half is the natural
resume: V6 wants the printed escape *executed as printed*, and step 5's
condition — that a reachable route exists — is exactly what #46 would create.
Re-check the engine's surface rather than reusing this session's finding; that
is the same discipline handoff #3 asked for around 0.24.0, and it paid.

**If #46 has not shipped, do not wait on it.** Go to **W06** (item 20), which is
next in the worklist's order and which W07 depends on. The thing to be careful
about there is the division of labour with W09 that the worklist spells out:
W06 builds the required-field mechanism *and* its `perspective` use; W09 step 3
consumes the same mechanism for `reachability`. If W09 finds itself writing a
second checking mechanism, W06 under-built — widen it rather than adding one.

**Two questions are open for Jon** and are not blockers for either path:

1. Should item 51 be filed against sahjhan? (It is an engine defect; holtz
   already carries the fix in `_common.project_anchor`. It does not bite the
   default worktree layout.)
2. Is the release gate closed by item 32 alone? The gate's stated rationale
   names only item 32, and that rationale is now satisfied.

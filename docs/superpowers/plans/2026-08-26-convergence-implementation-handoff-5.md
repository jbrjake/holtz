# Convergence work queue — implementation handoff #8

**Written 2026-08-26**, at the end of the eighth implementing session. **The
work queue is empty.** P0.3's remaining half shipped, which was the last item.

**Authority is unchanged and is not this file.**
`2026-08-22-convergence-decisions.md` plus the frozen spec at
`docs/design/convergence-speed-proposals.md` decide things; per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened.

Repo state: branch `dev`, HEAD `12aeb2f`, version **0.169.1**. **Nothing is
pushed** — seven commits sit on local `dev`. No hook was bypassed; no
`--no-verify` in this session.

**On the suite, precisely.** `python3 -m pytest -q` was observed at exit 0 with
**2651 passed, 8 skipped** against the tree of `823c90b`. The two commits after
it are markdown only — a status doc and a three-line wording fix — and were
verified with `pytest -m contract` (21 tests) and the contract gate at 38
commands, not with a fresh full run.

---

## Recording debt, cleared

Handoff #7 left three rulings living only in a handoff. They are now §I of the
decisions doc as **D36** (a courier closes a batch, because `EmitConfig` makes
exactly one event), **D37** (the batch runs before `converge`, not at
`finalize`), and **D38** (`all_critical_resolved` excludes a `theoretical`
deferral). The generalisation they cost is written down with them: when adding
a gate keyed on a field, enumerate every value of that field's domain and name
each one's route, as a test rather than a paragraph.

## Shipped this session

| Commit | What landed |
|---|---|
| `f1bd1e7` | Status doc: what a linked worktree actually measures |
| `6091cda` | **D40** — `boundary_dir` keys on the main worktree |
| `174106a` | Status doc: D40 shipped, and what the commit gate forecloses |
| `2e0b1d7` | **D41** — the pending-commit block is charged per actor |
| `823c90b` | **D39** — the fix loop serializes commits, not findings |
| `36fc492` | Status doc: P0.3 shipped, the queue is empty |
| `12aeb2f` | Wording: three in flight where three are dispatched |

Every hash verified with `git merge-base --is-ancestor` after the post-commit
amend. The amend kept the **first** printed hash all three times this session,
and the **second** in one case last session, which is why the heuristic is
worthless and the `merge-base` check is the only reliable one.

## P0.3's second half, and the three blockers the clause did not name

The clause reads: *"give fix subagents `isolation: "worktree"` so
`verify_suite.py`'s tree hash is per-agent; orchestrator merges and commits
serially."* Its premise holds — measured against Claude Code 2.1.246 and a real
pair of linked worktrees, not read:

- Isolated worktrees are nested at `<project>/.claude/worktrees/<name>/`; the
  base path is built in the binary as `join(root, ".claude", "worktrees")`.
- `git rev-parse --show-toplevel` in a linked worktree returns the worktree, so
  `compute_tree_hash` is per-agent. Two identical checkouts hash identically.
- **The ledger stays shared**, which is the half of the old serialization line
  that had to survive: sahjhan's `project_root_from` walks up for
  `docs/holtz/.sahjhan`, absent from a fresh worktree because it is gitignored,
  so both directories queried the same 118 events.

Three things blocked it, each ruled rather than designed around:

1. **The daemon socket was keyed per checkout, deliberately.** `boundary_dir()`
   hashed `realpath(cwd)`; observed `009ba37dc895` for the main tree and
   `02fab2dfc288` for a worktree. `tdd_evidence` is `restricted`, so the
   per-actor TDD gate D32/D33 had just shipped would have been unopenable for
   exactly the actor it was built for. **D40**: key on the main worktree.
2. **A green does not survive a merge.** Two worktrees with *disjoint* edits
   gave H(A), H(B) and H(A+B) all distinct, the merged tree matching neither
   recorded green. **D39**: rebase, then record; fast-forward only.
3. **A subagent could not reach the pending-commit block's escape.** **D41**:
   key `unregistered_commits` on the actor, clear run-global.

## Working notes for the next session

Everything in handoff #7's notes still holds. New or reconfirmed:

- **A git hook exports `GIT_DIR` and `GIT_INDEX_FILE` for this repository, and
  they follow every subprocess.** Tests that build throwaway repositories pass
  by hand and fail inside the commit that ships them — `git worktree add` exits
  128. `_clean_env()` in `tests/test_worktree_boundary.py` and
  `tests/test_fix_loop_worktree_merge.py` is the fix; copy it rather than
  rediscovering it.
- **A negative assertion can pass under mutation for the wrong reason.** The
  submodule test asserted only "different from the superproject", which stays
  true when the pointer is followed to a third path that is nobody's project.
  Rewritten as a positive claim about the key it must produce. Same class as
  "never let a negative assert an empty set", one step out: *never let a
  negative assert a difference either.*
- **Count assertions want unequal counts.** Two of the pending-commit tests
  passed vacuously because the number of buckets happened to equal the number
  of commits, so a `len()` over the keyed dict agreed by accident. Choose
  layouts where the two numbers differ.
- **Mutating a hook needs `scripts/hash-trusted-callers.sh` re-run first**, or
  the RED is a stale-hash artifact. Every mutation in this session was run that
  way, including the one against the real daemon.
- **`TestReadOnlyCommandsDoNotStall` in `test_hook_chains.py` fails when that
  file is run alone.** Pre-existing, confirmed at HEAD in a worktree: it
  imports `_protocol_cache` without putting the hooks directory on `sys.path`
  and relies on another test file having done so. Not touched here — but it
  means "run one file and it fails" is not, by itself, a regression signal in
  that file.
- **The e2e daemon tests all set `SAHJHAN_DAEMON_SOCKET`**, which short-circuits
  `boundary_dir` entirely. Anything testing socket *resolution* has to start a
  daemon without it, as `worktree_daemon` does.
- **The README test badge moved 2633 → 2644 → 2653 → 2659**, once per commit
  that added tests. Setting it per commit costs a full-suite run each time;
  setting it last means the intervening runs carry one known failure.

# Convergence work queue — implementation handoff #7

**Written 2026-08-25**, at the end of the seventh implementing session, on
Jon's instruction to wrap up. Stopped on a clean boundary: two units shipped
and committed, three rulings taken, tree clean apart from the untracked plan
docs. **P0.5 is complete — all three routes.** One work-queue item remains.

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened and what is next; it decides nothing.

Repo state: branch `dev`, HEAD `e537cae`, version **0.167.0**. `ruff` clean,
`mypy` clean (68 files), `enforcement_lint.py` at its **0 errors / 2 warnings**
baseline (both pre-existing H1s on `prediction` / `prediction_outcome`), the
contract gate PASS at 38 commands, `ENFORCEMENT-CONTRACT.md` regenerated and
current. **No hook was bypassed — no `--no-verify` in this session.**

**On the suite, precisely.** The last full-suite run before the D34 commit
finished with exactly one failure — `test_readme_badge_counts_match_actual`,
stale at 2615 vs 2633 — which was then fixed and that file re-run green. The
D34 commit's own `pre-commit` fast subset ran green (observed) and the
contract gate passed. **A full-suite run has not been observed green since the
badge fix.** Run `python3 -m pytest -q` once at the start of the next session
before building anything, and expect 2633.

---

## Shipped this session

| Commit | What landed |
|---|---|
| `2058677` | **D35** — `hardening_batch.py` + `hardening_batch_courier.py`; one hardening commit takes a module off the board |
| `e537cae` | **D34** — `item_is_user_reachable` on `fix_commit`; the fix loop works what a user can reach |

Both hashes verified with `git merge-base --is-ancestor` after the post-commit
amend — and note that this session the amend kept the **first** printed hash
in one case and the second in the other, so the heuristic is worthless and the
`merge-base` check is the only reliable one.

Both proven non-vacuous by mutating the implementation with `Edit`, re-running,
observing RED, and reverting. Mutating a *hook* requires re-running
`scripts/hash-trusted-callers.sh` first or the RED is a stale-hash artifact,
not a real failure.

### D35 — `fault_injected` batches per module

`hardening_batch.py --record --module <dir>` runs in the agent's sandboxed
shell and derives, checks and prints; `hardening_batch_courier.py` runs outside
the sandbox and writes one `finding_resolved` per covered id. A module is the
containing directory of the file in `location`, derived through
`merge_punchlists.parse_location` — the parser that already existed.

`--record` refuses: a module nobody filed against, a message that misses one of
the module's open ids, a message naming another module's ids, a commit with no
changes, a commit that already closed something, and a finding whose `location`
has no readable path.

### D34 — fix-loop eligibility

`item_is_user_reachable` on `fix_commit`, plus `findings.py list
--reachability` and the filtered worklist read in `phase-fix-loop.md`, so the
agent does not learn at the end of a cycle that the work could not be
committed.

---

## Three rulings this session — all recorded here, none yet in the decisions doc

**These are not in `2026-08-22-convergence-decisions.md` yet.** They were given
interactively. Someone should fold them into §H (or a new §I) so the authority
file stays the authority.

| # | Question | Ruling |
|---|---|---|
| 1 | D35's shape — coverage gate vs a courier closing the findings | **A COURIER CLOSES THEM.** `EmitConfig` (sahjhan `src/config/transitions.rs:101`) makes exactly one event with a fixed field map and `machine.rs:249` iterates a static `Vec`, so no transition can write one resolution per batched id. Closing with `finding_resolved` keeps D29's single definition of closed |
| 2 | Where the batch runs, given the spec says "at finalize" | **BEFORE `converge`**, as Step 15's third line. `all_critical_resolved` gates `converge`, carries no reachability filter and refuses a deferral — observed `false` for a `fault_injected` CRITICAL and still `false` after all three deferral reasons — so `finalize` is two transitions past the door that CRITICAL cannot open |
| 3 | D34 also stranded a `theoretical` CRITICAL | **`all_critical_resolved` EXCLUDES a `theoretical` deferral.** The one reason word a courier writes rather than an agent choosing it. Every discretionary reason still refuses |

**Why ruling 3 was needed, because it is the shape that will recur.** D34's own
text argued the escape for `fault_injected` and stopped there. `theoretical`
had an escape too — `fix_commit`, which is precisely what D34's gate closes.
Measured, not inferred: auto-deferred at filing, refused by
`all_critical_resolved`, refused by `merge_finding` (`item_open` observed
`false`), and outside the hardening batch's `fault_injected`-**and-open**
population. **When adding a gate, enumerate every value of the field it keys
on and name each one's escape.** `TestEveryCriticalHasARoute` is that
enumeration, written as a test.

---

## Next up — one item left

### P0.3's remaining half (work-queue item 16's tail)

Worktree isolation for fix subagents, and rewriting `phase-fix-loop.md` to
serialize **commits, not findings**. Untouched, unblocked — its gate change
shipped in an earlier session (`b564a07` / D32 / D33).

The line to rewrite is the one beginning *"Dispatch subagents **one finding at
a time**"* — currently at `phase-fix-loop.md:75` after this session's worklist
edit shifted it. Its stated reasons are that the ledger is a single hash chain
and commits land on one branch. Worktree isolation addresses the second; the
first is what the serialization must still preserve.

`verify_suite.py`'s tree hash is shared, which is the other half of the
problem: a green bound to a tree hash means two subagents editing the same tree
invalidate each other's evidence. That is likely the real design constraint,
and it was not investigated this session.

**It needs the `hook_e2e` subagent-parity test CLAUDE.md mandates** (rule 5)
**and** the doc-consistency test in `test_subagent_contract_consistency.py`, in
the same commit — a skill claim about what a subagent may do that no test
enforces is how `800624f` shipped a contradictory contract.

---

## Working notes for the next session

Everything in handoff #6's notes still holds. New or reconfirmed:

- **A gate's escape must be enumerated over the whole field domain, not
  argued for the case that prompted it.** See ruling 3 above. This is
  `enforcement-block-escape-by-construction` one level out: not "does the
  predicate imply the escape" but "does *every* value the predicate rejects
  have one".
- **`git merge-base --is-ancestor` is the only way to know which hash the
  post-commit amend left live.** Both orders occurred this session. Never read
  it off the `[dev …]` lines.
- **The README test badge moves on every commit that adds tests** (2569 → 2615
  → 2633) and it fails the full suite, not just a lint. Either set it last —
  which means the intervening full-suite runs have one known failure — or set
  it per commit. This session did the latter, and it cost two full-suite runs.
- **A full suite run takes over ten minutes** and cannot be run concurrently
  with anything else (`test_bash_source_write_gate` and
  `TestProtocolTrackerDaemonTeardown` fail under load — a 5s
  `sahjhan hook eval` timeout, not an engine error). Budget for it; do not
  probe in the foreground while one runs.
- **`_Board` in `tests/test_hardening_batch.py` is reusable** and
  `test_fix_loop_eligibility.py` already imports it. It takes `config_dir` and
  `env`, so the same class drives both a plain `tmp_path` ledger (read side)
  and a `real_daemon` project root (write side). Use the `live` fixture for
  anything that writes through a courier — `mock_daemon` skips hash auth and
  would stay green against a stale manifest.
- **Both README counts moved:** enforcement hooks 19 → 20, tests → 2633.

# Convergence work queue — implementation handoff #4

**Written 2026-08-25**, at the end of the fourth implementing session. Paused
at Jon's request, on a clean boundary: three queue items shipped, tree clean,
nothing half-built, no question outstanding.

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened and what is next; it decides nothing.

Repo state: branch `dev`, HEAD `a745681`, version **0.162.0**. Full suite
green (2459 collected, `pytest` exit 0 observed before each commit); `ruff`,
`mypy` (62 files), the contract gate and the generated
`ENFORCEMENT-CONTRACT.md` all current. **No hook was bypassed — no
`--no-verify` in this session.**

---

## Shipped this session (queue items 13–15)

| # | Item | Commit | What landed |
|---|---|---|---|
| 13 | D7 | `34755d4` | The ≤3-new-items cap, the close-as-many obligation, and `merge_finding` — the escape both halves needed |
| — | status | `209649d` | D7 recorded |
| 14 | D8 | `92c4e86` | `stale_sweep.py` + `stale_sweep_courier.py` + restricted `stale_sweep_complete`; the widened `pattern_analysis_overdue` floor |
| — | status | `b782988` | D8 recorded |
| 15 | P0.5 clause 1a | `5679f5c` | Required `reachability` field on `finding` |
| 15 | D4 + D5 | `a745681` | The four convergence conjuncts, replacing `all_findings_closed` |

Every item was proven non-vacuous by mutating the implementation with `Edit`,
re-running, observing RED, and reverting — three to eight mutations each.

### Three rulings Jon gave this session

1. **D7's escape is a new `merge_finding` transition.** D7 requires the cap's
   escape to be guaranteed by construction and names it "the merge/close
   path". Neither end existed: finding-level merge was only the one-time Step 9
   Holtz/Justine phase, and `finding_resolved`'s producer `fix_commit` is
   `fix_loop → fix_loop`, unreachable from `pattern_analysis`. Jon chose
   building the primitive over moving or weakening the gate.
2. **D8's sweep record is a courier, mirroring P5.4.** Nothing recorded that a
   stale sweep ran, so the obligation could not be discharged by one. Jon chose
   the restricted + tool-attested event over an agent-written one — a weaker
   sibling would become the cheaper door past round 8.
3. **P0.5 ships clause-by-clause.** Its three remaining clauses each name a
   mechanism that does not exist (below). Jon ruled: ship the field, go
   straight to D4, and bring 1b/2/3 back with one decision each.

### Premises falsified this session

Checked against the tree and the binary, not inferred:

- **No finding-level merge existed.** All 22 transition commands, `events.toml`
  and every skill file: "merge" is only `merge_ready → merge_done` + a report.
- **Nothing recorded a stale sweep.** Step 11b emits `fix_start` and a
  `cant_reproduce` deferral only for what it *retires*, so a sweep that
  reproduces everything left no trace. `check_sweep_evidence.py` is a false
  lead — it gates the *final* sweep and is referenced by no TOML.
- **`blast_radius` arrives after filing.** It is recorded at Step 10's per-fix
  procedure, so P0.5's severity derivation is missing two of its three inputs
  at `event finding` time; "public-API surface" has no ledger representation
  at all.
- **Nothing reopens a closed finding.** Re-filing an id supersedes its fields
  (merge-protocol.md:53, D25) but leaves `finding_resolved` standing.

---

## Next up — item 16, then P0.5's remainder

16. **P0.3** (finding-scope the TDD gate — *the gate change must land before
    any batching*, per the spec) and **P4.1** (script the merge — still the
    cheapest open item).

Then P0.5's three owed clauses, each needing one ruling first. The status file
carries the blocker for each:

- **derive severity** — needs a re-grading trigger. `blast_radius` arrives
  late; is severity re-derived at each `blast_radius` event, continuously at
  render/gate time, or does `affected_count` drop out of the inputs?
- **routing** — the `user_reachable`-only fix-loop eligibility half is a plain
  query gate of the `item_is_low` shape and needs nothing new. The auto-defer
  and the `fault_injected` finalize batching both need a mechanism.
- **reopen, don't refile** — needs a `finding_reopened` event (or equivalent)
  *and* every openness predicate taught to respect it: `item_open`,
  `all_findings_closed`, `open_low_findings`, `open_medium_findings`,
  `round_item_cap_exceeded`, `all_critical_resolved`,
  `all_user_reachable_high_closed`.

### One thing left deliberately unresolved

`enforcement_lint.py` H8 warns **twice** that `converge` "prints `sweep_dirty`
as the way out" while `sweep_dirty`'s readiness is "decided by an inline
predicate". `sweep_dirty` has **no gates at all**, so it cannot be
unsatisfiable and the warning is *false* rather than merely noisy. The obvious
narrowing — stay quiet when an escape has no gates — was not made, because H8
was already narrowed once this session (see below) and a second unasked change
to a shipped check is a question, not a judgment call. **Baseline is now 0
errors / 4 warnings** from `enforcement_lint.py` (2 pre-existing H1 + these 2)
and 0 errors / 7 warnings from `sahjhan lint`.

The narrowing that *was* made, and may want reviewing: H8 stays quiet when an
escape's named queries are **all argument-scoped** (their SQL contains `{{`).
`merge_finding` is gated on `item_open` and `merge_target_exists`, both keyed
on `{{item_id}}`; a run-wide block has no argument to bind, so H8's own printed
remedy (`decide this block with query = "item_open"`) cannot be instantiated.
The exemption is per-query, so an escape carrying any run-wide predicate is
still judged on it.

---

## Working notes for the next session

Everything in handoff #3's notes still holds. New this session:

- **`hash-trusted-callers.sh`'s `TRUSTED_SCRIPTS` is a hand-kept list.** A new
  daemon-calling hook is not discovered: the first regeneration after adding
  `stale_sweep_courier.py` produced **zero diff** and looked entirely
  successful. A restricted writer the daemon cannot authenticate is enforcement
  that silently fails open.
  `test_stale_sweep.py::test_every_registered_authed_writer_is_in_the_manifest`
  now fails the build for the next one. It is scoped to hooks.json
  *entrypoints* — since sahjhan 0.21.0 the daemon authenticates the process
  directly holding the socket, so `quiz_vault.py` (a module, no `__main__`) is
  covered by `lens_quiz.py` and `quiz_capture.py`.
- **README carries two counts a new hook moves**, and the badge test masks the
  other: `test_readme_badge_counts_match_actual` (test total) and
  `test_readme_metrics_match_actual` ("N enforcement hooks" in the *What's
  inside* line, currently **17**). Fixing only the first leaves the second
  failing on the next run.
- **The post-commit amend's print order is not fixed.** Twice this session the
  *first* `[dev …]` line git printed was the live commit and the second was the
  orphan — the hook's stdout and git's interleave. `git reflog` is
  unambiguous where the terminal is not: the entry tagged `commit (amend):` is
  HEAD. Always verify with `git merge-base --is-ancestor <hash> HEAD`.
- **`_Run` in `tests/test_amplification_breaker.py` is now the shared harness
  for four files** (`test_pattern_backpressure.py`, `test_round_item_cap.py`,
  `test_stale_sweep.py`, `test_convergence_redefinition.py`). It gained an
  initial `git commit --allow-empty` (both `fix_commit` and `merge_finding`
  stamp `commit_hash` from HEAD and fail on an empty repo), plus `merge()`,
  `sweep()`, `defer()`, a `reachability=` parameter on `file()`, and
  `gate_check(command)` now takes an argument.
- **`gate check` prints one line per gate.** Assert on the line naming the
  *query* (`_blocked_on` in `test_round_item_cap.py`), never on "some ✗ is
  present" — `pattern_done` and `iteration_boundary` normally carry unrelated
  failing conjuncts, and in a `tmp_path` project the suite and linter gates
  fail on `CLAUDE_PLUGIN_ROOT` and `ruff` not being on PATH.
- **A f-string cannot contain a backslash escape** in Python 3.12 — precompute
  the value instead. Cost one collection error.
- **Editing config while a full-suite run is in flight invalidates it.** Tests
  read `protocol.toml` at test time, so the run reflects a tree that never
  existed. Both P0.5 1a and D4 were verified by one combined run for this
  reason; each commit additionally passed the pre-commit fast subset.
- **`batch_edit.py` validates every count before writing**, so a bad spec
  writes nothing — but two subs whose patterns overlap will both count against
  the *original* file and refuse. Split those out and use `Edit`.

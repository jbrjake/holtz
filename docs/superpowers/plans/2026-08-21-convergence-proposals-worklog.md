# Convergence-speed proposals — implementation worklog

**Started:** 2026-08-21 · **Branch:** `dev` · **Version at pause:** 0.151.1
**Punchlist:** [`docs/design/convergence-speed-proposals.md`](../../design/convergence-speed-proposals.md)
**Source:** [`docs/case-studies/2026-08-18-tqdm-process-postmortem.md`](../../case-studies/2026-08-18-tqdm-process-postmortem.md)

The punchlist is the authoritative status record; each item id carries `DONE`,
`PARTIAL`, `REJECTED`, `N/A`, or nothing. This file is the session handoff.

---

## Standing scope decisions (from the user)

1. **Ignore all tqdm and tqdm-audit items.** Only holtz plugin work is in scope.
2. **Nothing depends on resuming that run.**
3. **No verbiage in skill files, ever.** Instructions only — the reasoning goes
   in the commit message. When auditing, check the whole 24h window of skill
   edits, not just the current diff. See `no-rationale-in-skill-files` memory.
   Raised twice, the second time in caps.

---

## Sessions 1–4 (summary)

Tier 3 complete (P3.1–P3.8). P0.4, P5.4, P1.2, P1.6, P2.2 complete. P0.2 down to
its last piece. Detail in git history and in the punchlist's own prose blocks.

## Session 5 — P0.1 and the rest of P0.2

| Commit | Version | What landed |
|---|---|---|
| `fe2ef56` | 0.150.2 | A finding's severity is its latest filing (found while verifying P0.1) |
| `6b12186` | 0.151.0 | P0.1 — `defer_batch.py` + `low_findings_carried` on `iteration_boundary` |
| `f17aaec` | 0.151.1 | P0.2's last piece — Step 16 scoped, convergence-loop punchlist read fixed |
| `1530cc2` | — | Punchlist marked: P0.1 **PARTIAL**, P0.2 **DONE** |

At pause: full suite **green, zero failures or errors** (2237 collected, 8
skipped), ruff + mypy + contract gate (37 commands) + `sahjhan lint` +
`enforcement_lint` all at **0 errors**, tree clean,
`docs/ENFORCEMENT-CONTRACT.md` regenerated, README badge at 2237.

### What P0.1 actually became

Two halves that do not work alone. `skills/holtz/scripts/defer_batch.py` loops
the existing `defer_low` / `defer_medium` transitions over the listing
`findings.py.collect()` builds — 133 of the measured run's 273 open findings
were legally closable this way and the transitions were used **zero** times.
`low_findings_carried` gates `iteration_boundary`: open LOW findings exist
**and** more findings are open than the run has closed.

Three judgment calls, all recorded in the punchlist:

- **The block sits on `iteration_boundary`, not `fix_commit`.** P0.2 had already
  taken pattern analysis off the commit path for the same reason: a block there
  fires between a fix that is written, verified and green and the ledger entry
  naming it.
- **The escape guarantee is structural.** `defer_low`'s gates are exactly
  `item_is_low` + `item_open`, both of which the predicate already asserts — so
  the named command can always close every finding the block counts. LOW was
  forced by this: MEDIUM's budget can refuse, and a block whose escape can be
  refused is #77.
- **The convergence redefinition is NOT done, and only half of it is rejected.**
  `A < 1.0 over last 3 rounds` and `DEFERRED.md` are rejected on merit. The
  `user_reachable HIGH` conjunct is **owed and blocked on P0.5** — a sequencing
  artifact of working P0.1 first, which is the order the punchlist itself
  implies and which is backwards. The severity carve-out is an open decision
  routed to P0.5, because excusing MEDIUM from convergence would silently void
  `defer_medium`'s 50% budget — today the only thing forcing a run to *fix* half
  its MEDIUMs. **P0.1 is PARTIAL, and P0.5's entry now carries both items so
  they cannot be lost there.**

### Things found that the proposals did not name

- **`defer_low` matched any filing's severity.** The board renders the last
  filing; the gate matched any row ever filed under the id, so a finding
  corrected LOW → HIGH could still be closed as a LOW, and a MEDIUM corrected to
  HIGH kept funding MEDIUM budget. **Third counting site of P3.6's shape.**
  Found by probing whether the engine supports correlated subqueries — it does,
  and the probe's own control case was the bug.
- **`phase-convergence.md`'s worklist read always failed.** P0.4's defect at a
  site P0.4 missed, surviving because the invocation named `<path>` — a
  placeholder no filename-matching check could see. The invariant that has teeth
  is "Holtz's procedure has exactly one worklist lookup", derived over every
  phase document.
- **`sahjhan lint` L6 is down from 10 warnings to 5.** Migrating the deferral
  predicates to named queries retired half of them. The remaining five are
  `defer_cant_reproduce` / `set complete perspective` / `lens_rotate` — the same
  87–92% near-duplicates the earlier session logged. Still no `--strict`.

---

## Next up — P0.5, then P0.3, with P4.1 as the cheap one

- **P0.5 — reachability grading. It now also closes out P0.1.** A required field
  on `event finding`, so an `events.toml` schema change plus the skill files that
  record it. The finding schema carries only id/severity/category/location/
  perspective/description/predicted_by — Discovery Chain and Evidence have
  nowhere to go but `description`. Worth settling as part of this item.

  **Two carried items, both written into P0.5's punchlist entry:** add the
  `user_reachable HIGH` conjunct to `converge`, and *decide the severity
  carve-out on the record* — excusing MEDIUM from convergence makes
  `defer_medium`'s 50% cap decoration, and nothing in the post-mortem asks for
  that. P0.1 stays PARTIAL until both are settled.

  Note the new adjacency: `item_is_low` / `item_is_medium` now establish
  "a finding's current grade is its latest filing", which is the same machinery
  a re-grading rule needs. P0.5's *"reopen, don't refile"* clause wants
  `--supersedes BH-NNN`; check first whether last-filing-wins already gives it
  what it wants, since the punchlist already treats a re-filing as a correction.

- **P0.3 — finding-scoped TDD gate.** Highest risk, lowest confidence on
  feasibility. Needs a `hook_e2e` test per CLAUDE.md's subagent-parity rule.
  **The gate change lands before any batching.**

- **P4.1** (script the merge) is the cheapest high-confidence item left.
  `merge-protocol.md:11` calls the merge mechanical and `:165` deterministic, and
  the merge agent hand-writes throwaway `python3 -c` scripts to do it.

---

## Working method that is paying off

- **Verify the premise before implementing.** Every item worked so far has had
  at least one false or misdirected clause — and twice now the probe that
  checked a premise has turned up a live defect next door.
- **Prove non-vacuity, and believe the result.** `git stash push -- <file>` or an
  Edit-mutate-revert, re-run, confirm RED. This session it killed a test that
  looked fine: an "ordering matters" assertion over `defer_batch.py`'s severity
  order stayed green under the reversed order, because a MEDIUM cap never stops
  the LOW pass. The claim was decoration; the test was rewritten to name the
  property that is real. **Mutate with Edit, never `python3 -c`** — CLAUDE.md
  forbids interpreter file edits and the hook enforces it.
- **Test the taught sequence, not the gate.** Assert on the document's own line
  order. `TestTheResweepIsScoped` is the newest instance.
- **Test engine-owned behaviour through the real binary.** `sahjhan query`,
  `render`, plain `event` writes and **`transition`** are all daemon-free, so a
  real ledger in `tmp_path` is cheap. To reach `fix_loop` without walking the
  protocol, write a `state_transition` event directly — `_fast_forward_to_fix_loop`
  in `test_e2e_audit_flow.py` is the original, and `tests/test_defer_batch.py`
  has a standalone copy. **Restricted events still need `real_daemon` plus the
  courier hook.**
- **A scratch project is the fastest way to check an engine question.**
  `git init` + `sahjhan --config-dir <repo>/enforcement init` in a temp dir, then
  `sahjhan query`. Re-init after any `enforcement/*.toml` edit — the config seal
  breaks. In zsh, define `sah() { ... }`; an aliased variable holding the flags
  will not word-split.
- **Correlated subqueries work** (`f.seq = (SELECT MAX(g.seq) … WHERE g.id = f.id)`),
  verified against the binary. That is the last-filing-wins idiom.
- **Run in the venv** — `source .venv/bin/activate`.
- Regenerate `docs/ENFORCEMENT-CONTRACT.md` with
  `python3 scripts/enforcement_contract.py --write` after touching
  `transitions.toml` or `protocol.toml`. Regenerate `trusted-callers.toml` with
  `scripts/hash-trusted-callers.sh` after touching a daemon-calling hook.
- **The README badge tracks *collected* count** and pre-commit fails on it every
  time. `python3 -m pytest --collect-only 2>&1 | grep -oE "[0-9]+ tests collected"`.
  There is a `Python scripts: N` count in the same file — a new script moves both.
- **Stage by name and verify.** `git add <paths>` then read `git status --short`;
  never `git add -A`. When a commit must exclude in-flight work,
  `git stash push -u -- <paths>` leaves the index alone.
- The full suite takes ~6.5 min, past the 120s Bash default — raise the timeout,
  and do not chain two full runs in one command.

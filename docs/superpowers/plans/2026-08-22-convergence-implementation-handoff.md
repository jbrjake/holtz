# Convergence work queue — implementation handoff

**Written 2026-08-22**, at the end of the first implementing session. Paused at
a clean boundary: six queue items shipped, full suite observed green, tree
clean, nothing half-built.

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md` and is current as of
`d716f3e`. This file records what happened and what is next; it decides
nothing.

Repo state: branch `dev`, HEAD `d716f3e`, version **0.153.0**. Full suite green
(2241 collected, `pytest` exit 0 observed after each commit); `ruff`, `mypy`,
enforcement lint (0 errors), contract gate and the generated
`ENFORCEMENT-CONTRACT.md` all current. No hook was bypassed — no `--no-verify`
in this session.

---

## Shipped this session (queue items 1–6)

| # | Item | Commit | What landed |
|---|---|---|---|
| 1 | D27 / P3.4 | `9f04bff` | `pattern_done` clears the cached `pattern_analysis_overdue` flag directly, so a ledger query that could not run no longer holds a discharged obligation True |
| 2 | D10 / P3.2 | `04a4d78` | `stall` is a map from actor to count; charging and clearing are per-actor; six `hook_e2e` tests, and `TestReadOnlyCommandsDoNotStall` now carries the marker its clause demanded |
| 3 | D13 / P2.2 | `6b95aea` | The compact brief read is Step 11's step 4, on its own, ahead of the update step |
| 4 | D12 / P1.2 | `ce3c5a9` | Fix subagents route on "a test that can't fail, or a fix confined to one file"; the Fast Path proxy is gone |
| 5 | D9 / P0.4 | `2741fce` | `PUNCHLIST.md` renders one line per open finding — id, severity, `file:line`, 12-word render-side truncation |
| 6 | D14 / P0.4 | `d716f3e` | `not(file_exists)` on `merge_done → awaiting_clear`: the fix loop cannot start with `PUNCHLIST-MERGED.md` on disk |

Every one of these was proven non-vacuous by mutating the implementation with
`Edit`, re-running, observing RED, and reverting. D10 was mutated three
separate ways because six tests covered three different mechanisms.

---

## Next up — queue items 7–16, in the decisions doc's order

Remaining standalone items (no dependencies, any order):

7. **D21** — widen Step 11b's population to all open findings, every severity.
   Currently `phase-fix-loop.md` Step 11b keeps only findings whose `location`
   names a file the run changed (`bb502ca`). The cited mechanism triaged all 68
   open HIGHs. Note D8 later makes this sweep the only late-run round, which is
   why the ruling widens it.
8. **D22 remainder** — restore the `phase`/`step` fields on
   `pattern_analysis_complete`. `ceb7414` deleted them; everything else in that
   commit is ratified. Touches `enforcement/events.toml` and
   `enforcement/hooks/pattern_courier.py` — **re-run
   `scripts/hash-trusted-callers.sh` after editing the courier** or enforcement
   silently stops trusting it.
9. **D20** — recon's cold-file coverage from a ledger query, replacing the
   punchlist + archive file reads in `phase-recon.md`. The shipped file-read
   stands only until this lands. `tests/test_punchlist_render.py`'s
   `test_a_converged_run_still_archives_every_finding_with_its_location` and
   `TestSkillFilesMatchWhatThePunchlistCarries` both encode the current
   dependency and will need to follow the new source of truth.

Then the sequenced ones (10–16): D11 (P2.1 byte-cap, then P3.5's artifact cap),
D2+D3 (the breaker rebuild — the big one), D6, D7, D8, P0.5 then D4 under D5's
constraint, and finally P0.3 then P4.1.

**D2+D3 is engine work before it is plugin work.** `sahjhan defer batch
--severity low,medium` writing `docs/holtz/DEFERRED.md` does not exist; the
sahjhan source is a working directory of this session
(`/Users/jonr/Documents/code/sahjhan`). The round ordinal it needs also serves
D8 and hands P5.5 over nearly free, so build it once, deliberately. Jon's
granted amendment: the block lands on **dispatching the next fix**, not on
`fix_commit`.

---

## The one open question — asked and answered

**D13's scope, second half.** P2.2 diagnoses two sites: `phase-fix-loop.md`
never mentioned the compactor, and it is "buried as clause (a) of a seven-clause
sentence in `phase-audit.md:59`". The fix-loop step shipped in `6b95aea`; the
burial at `phase-audit.md:59`/`:73` and the same sentence in
`justine-skill.md:224` were left alone, because doing *and* not doing them were
each plausible readings, and "added scope" and "dropped clause" are both
deviations under the standing process rule.

**Ruling (Jon, 2026-08-23): unbury.** Shipped in `a0e0ef5`: all three subagent
briefs are numbered lists with the compact read as step 1, phrased exactly as
the fix loop's pattern round phrases it; the remaining clauses became numbered
items with content and order unchanged. `test_subagent_contract_consistency.py`
counts numbered compact-read steps against the number of subagent briefs per
doc, so a third brief cannot re-bury it.

**No questions are outstanding.** The next session starts at queue item 7 (D21)
with nothing owed.

---

## Working notes for the next session

- Run gates with the venv: `.venv/bin/python3 -m pytest`, `.venv/bin/ruff`,
  `.venv/bin/mypy`. Bare `ruff`/`mypy` are not on PATH and `python3` alone
  lacks `hypothesis`.
- The README test-count badge is gated by
  `tests/test_integration.py::test_readme_badge_counts_match_actual` and needs
  bumping in the same commit as any test-count change. It is currently 2241.
- A `not { gates = [...] }` gate nests. `test_managed_docs_consistency.py`'s
  `_file_exists_gate_paths` now recurses and tracks negation, so the #60
  invariant still sees a positive `file_exists` buried inside a combinator.
- Reaching a protocol state in a test is far cheaper by writing a
  `state_transition` event directly than by walking the transitions — see
  `tests/test_merged_worklist_gate.py`'s `merged_state` fixture.
- Editing a daemon-calling hook (`protocol_tracker.py`, `commit_gate.py`,
  `pattern_courier.py`, …) requires `scripts/hash-trusted-callers.sh`. The
  pre-commit hook regenerates it, but `pytest` run beforehand will fail on the
  stale manifest first and the cause is not obvious from the message.
- Changing `enforcement/transitions.toml` makes `docs/ENFORCEMENT-CONTRACT.md`
  stale; regenerate with `.venv/bin/python3 scripts/enforcement_contract.py --write`.
- Mechanical multi-site substitutions go through
  `python3 /Users/jonr/Documents/code/scripts/batch_edit.py <spec.json>` —
  there is **no** copy at `holtz/scripts/batch_edit.py`.

# Convergence work queue — implementation handoff #3

**Written 2026-08-24**, at the end of the third implementing session. Paused at
Jon's question, on a clean boundary: two queue items shipped, tree clean,
nothing half-built, no question outstanding.

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened and what is next; it decides nothing.

Repo state: branch `dev`, HEAD `934fd42`, version **0.158.0**. Full suite green
(2373 collected, `pytest` exit 0 observed after each commit); `ruff`, `mypy`,
both linters (0 errors; the same 7 + 2 pre-existing warnings), the contract
gate and the generated `ENFORCEMENT-CONTRACT.md` all current. **No hook was
bypassed — no `--no-verify` in this session.**

---

## Shipped this session (queue items 11–12)

| # | Item | Commit | What landed |
|---|---|---|---|
| — | test gap | `f9c46a1` | Every taught `sahjhan` command now runs against the engine, not just the hook. Pin bumped to **0.22.0** |
| 11 | D2/D3 | `a2bd2c5` | `[batches.defer]`, the `"defer batch"` alias, `DEFERRED.md` template + render |
| 11 | D2 | `c620de7` | `amplification_diverging` — the per-round measurement |
| 11 | D2/D3 | `276cd11` | The `any_of` block on `pattern_done`, plus `pattern_analysis` deferral edges |
| 12 | D6 | `6f35730` | The `>25 pattern-filed open` conjunct, on a new `pattern_id` finding field |

Status rows updated in `convergence-speed-status.md` (`a3a804d`, `7a3cab8`,
`e4303c1`, `934fd42`). Every item was proven non-vacuous by mutating the
implementation with `Edit`, re-running, observing RED, and reverting — three or
four mutations each.

### Two rulings Jon gave this session

1. **`defer_low`/`defer_medium` are also declared `pattern_analysis →
   pattern_analysis`.** Asked at the point D2's clause wedged: the block goes on
   `pattern_done`, that state has exactly one exit, and the deferral
   transitions existed only from `fix_loop` — so the block named a command the
   run could not reach. Verified against the binary; `sahjhan defer batch`
   there exits non-zero on the first item and defers nothing at all. Jon chose
   the new edges over moving the gate, so the block stays exactly where D2 puts
   it.
2. **D6's population comes from a new optional `pattern_id` on `finding`.**
   D6's parenthetical guessed `pattern_ids` made it derivable. It does not, and
   the ledger says so four ways (below). Jon chose the field over a round-start
   window or a sibling-id list on the round event.

### The premise D6 rested on, falsified

Checked with `sahjhan query --glob "docs/holtz/**/ledger.jsonl"` across every
archived run, not inferred from the schema:

- `pattern_ids` names the PAT entries a round appended to the brief. **No link
  to any finding.**
- `predicted_by` holds a prediction index — values 0–7 across 86 attributed
  findings — and **never** a PAT id.
- **No finding has ever been filed at `step=11`.** The 30 at `fix_loop/14` are
  lens-rotation findings.
- `siblings_found` is a per-round count with no ids, and no gate reads it.

---

## Next up — queue items 13–16

13. **D7** — the ≤3-new-items cap **and** the close-as-many-as-you-open
    obligation. *Read the decisions doc's own note first:* the 08-21 session's
    wedge concern (a hard cap on `pattern_done` is not undoable once a fourth
    finding is filed) is recorded as **real engineering input** for the cap
    half; the obligation half has no wedge problem and was simply never
    addressed. D7's ruling: **build both**, escape guaranteed by construction,
    *"a design blocker there stops the turn with a question, not a unilateral
    narrowing."* Expect that question — this is the third clause in a row whose
    escape needed thinking through, and the wedge is already named.
14. **D8** — the stale sweep replaces pattern analysis past ~round 8. The round
    ordinal it needs is `count(*) FROM events WHERE
    type='pattern_analysis_complete'`, now used in two places; note that
    `amplification_diverging` already carries the three-round seq-floor idiom
    to copy.
15. **P0.5** (reachability grading), then **D4** — pre-committed, all four
    conjuncts as written — under **D5** (converging still requires the MEDIUM
    budget spent). `medium_deferral_budget` with `expect = "false"` is the
    established spelling for "budget spent"; `pattern_done`'s gate uses it.
16. **P0.3** (gate change before batching) and **P4.1** (script the merge —
    still the cheapest open item).

---

## Working notes for the next session

- Gates run from the venv: `.venv/bin/python3 -m pytest`, `.venv/bin/ruff`,
  `.venv/bin/mypy`. Bare `ruff`/`mypy` are not on PATH and `python3` alone
  lacks `hypothesis`.
- The README test-count badge is gated by
  `tests/test_integration.py::test_readme_badge_counts_match_actual` and needs
  bumping in the same commit as any test-count change. Currently **2373**.
- **`post-commit` amends, so the hash git prints first is orphaned.** The
  `[dev XXXXXXX]` line above `post-commit: bumped version` is *not* the commit;
  the second one is. Five citations in the status file were the wrong hash
  before `934fd42`. Verify with `git merge-base --is-ancestor <hash> HEAD`
  before writing a commit id into a doc — `git cat-file -t` finds the orphan
  too and will tell you it exists.
- **The query planner rejects correlated scalar subqueries** in a WHERE
  comparison: *"Physical plan does not support logical expression
  ScalarSubquery"*. A per-row aggregate over a window has to be a self-join
  with `GROUP BY`/`HAVING` — `amplification_diverging` is the worked example.
- Non-correlated scalar subqueries, `strpos`, `||` concat, and `LIKE` with a
  computed pattern all work. A bare `count(*)` over a derived table is safe;
  an **outer WHERE** over one is what breaks `LIMIT`
  ([[enforcement-sql-limit-is-not-a-window]]).
- Reaching `fix_loop` or `pattern_analysis` in a test is cheapest by writing a
  `state_transition` event directly. `_Run` in
  `tests/test_amplification_breaker.py` is the harness: it drives real pattern
  rounds through `pattern_round.py --record` + `pattern_courier.py` against a
  real daemon, which is the only way a restricted `pattern_analysis_complete`
  reaches a ledger. `tests/test_pattern_backpressure.py` imports it.
- **`pattern_round.py` refuses on a ledger where no event names a run**, so a
  round cannot be the first thing a test writes — file one finding first.
- **The courier matches on the command text.** `pattern_courier.py` records
  nothing unless the `tool_input.command` is the full
  `python3 <abs path>/pattern_round.py --record …` form. An abbreviated command
  string exits 0, prints no error, and writes nothing.
- Editing a daemon-calling hook (`protocol_tracker.py`, `commit_gate.py`,
  `pattern_courier.py`, …) requires `scripts/hash-trusted-callers.sh`.
  `_sahjhan_bootstrap.py` is **not** one of them.
- Changing `transitions.toml` **or** `protocol.toml` makes
  `docs/ENFORCEMENT-CONTRACT.md` stale; regenerate with
  `.venv/bin/python3 scripts/enforcement_contract.py --write`. Changing
  `events.toml` alone does not.
- Adding a render target requires adding it to `MANAGED_DOCS` in
  `_sahjhan_bootstrap.py` — `test_managed_docs_consistency.py` enforces the
  `<=>` invariant both ways.
- Mechanical multi-site substitutions go through
  `python3 /Users/jonr/Documents/code/scripts/batch_edit.py <spec.json>`. It
  validates every occurrence **count** before writing anything, so count with
  `grep -o … | wc -l`, never `grep -c` (which counts lines).
- The intermittent daemon-adjacent flakiness noted in handoff #2 did **not**
  recur in this session across a dozen full runs.

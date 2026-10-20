# Convergence work queue — implementation handoff #2

**Written 2026-08-23**, at the end of the second implementing session. Paused
at Jon's instruction: a natural breaking point before queue item 12 (D6).

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened and what is next; it decides nothing.

Repo state: branch `dev`, HEAD `14fa00b`, version **0.154.0**. Full suite
green (2255 collected, `pytest` exit 0 observed after each commit); `ruff`,
`mypy`, enforcement lint (0 errors, 2 pre-existing `prediction` warnings) and
the contract gate all current. No hook was bypassed — no `--no-verify` in this
session.

---

## Shipped this session (queue items 7–10)

| # | Item | Commit | What landed |
|---|---|---|---|
| 7 | D21 | `7904b54` | Step 11b triages **every open finding, every severity**; the `git diff --name-only` narrowing is gone |
| 8 | D22 remainder | `b184b05` | `phase`/`step` restored on `pattern_analysis_complete`, stamped by the courier from constants pinned against the doc that teaches the round |
| 9 | D20 | `f0a0239` | `findings.py audited-files` — recon's cold-file coverage from a `--glob` query across every run's ledger, replacing the punchlist/archive reads |
| 10 | D11 | `2270506` | P2.1's 20-entries-**and**-40 KB brief cap with a 2 KB entry cap and `pattern-round-NN.md` overflow, reported by the compactor; P3.5's 40 KB artifact cap in SKILL.md |

Each was proven non-vacuous by mutating the implementation with `Edit`,
re-running, observing RED, and reverting — two or three mutations per item.
Status rows for all four are updated in `convergence-speed-status.md`
(`94da845`, `d2a6948`, `14fa00b`, `b2d44bf`).

---

## Queue item 11 (D2+D3) — engine half done, plugin half owed

### What Jon ruled this session

Asked at the point the engine work forked, and answered:

1. **The dead multi-word aliases are fixed engine-side.** Not by rewriting the
   taught commands.
2. **`sahjhan defer batch --severity low,medium` is a generic engine batch
   command plus a holtz alias** — not a `defer` subcommand that knows what a
   finding is. Severity, findings and the budget stay in holtz's TOML.
3. **The sahjhan release is authorized**, with one constraint: *do not commit
   or touch the README or the uncommitted `docs/` files in that repo.* They
   were left alone; only `src/`, `tests/`, `CLAUDE.md`, `Cargo.toml` and
   `Cargo.lock` were staged.

### The defect that forced question 1

Verified against the binary, not inferred:

```
$ sahjhan --config-dir enforcement defer low BH-001
error: unrecognized subcommand 'defer'
```

`resolve_alias()` matched only the **first positional word** against alias
keys, and sahjhan's README documents single-word keys only. Holtz declares 17
two-word aliases. Four are taught in skill files and **all four were
unrunnable**: `defer cant-reproduce` (`phase-fix-loop.md:151`, Step 11b, and
`step-10-fix-loop.md:96`), `defer low` (`:110`), `defer medium` (`:116`).

Nothing caught it because every test drives `transition defer_low` — the
working form — and the contract gate only checks that the *hook* allows a
command, never that the *engine* accepts it. Same shape as v0.141.2: a green
gate over a broken taught step.

### What shipped in sahjhan (v0.22.0, commit `c4c0ff4`)

- **Multi-word alias keys.** Widest key wins; a flag ends the candidate, so
  `defer batch --severity low,medium` matches `"defer batch"` and the flag
  reaches the expanded command. Six unit tests; pinning the resolver back to
  single-word matching fails three of them.
- **`sahjhan batch <name>`,** driven by `[batches.<name>]`: `param` names the
  selector flag, each step maps a `value` to an `items` query (rows carry an
  `id`) and the `transition` its ids receive, one at a time, with that
  transition's own gates. Populations are read per step, after earlier steps
  have appended. Gate refusals are printed per item and are **not** fatal — a
  budget-capped transition is supposed to refuse partway, and reaching that
  line is the point. Renders run once at the end, so the command that defers
  is the command that writes the view.
- **`validate_deep` rejects** a batch with no steps, or a step naming an
  undeclared query or an undefined transition.
- **Named predicates say their name when they refuse** — `query
  'medium_budget' returned 'false', expected 'true'`, so one line per refused
  item is attributable.
- `render_after_transitions` extracted from `cmd_transition`, shared with the
  batch, so renders are not implemented twice.

Nine integration tests in `tests/batch_tests.rs` against a fixture shaped like
holtz: LOW + MEDIUM findings, a budget gate on the MEDIUM step, a DEFERRED.md
render. `cargo test`, `cargo clippy --all-targets -- -D warnings` and
`cargo fmt --all -- --check` all observed clean.

Checked against **holtz's own `enforcement/` config**, not just the fixture —
the 0.22.0 build reaches the protocol on all three previously-dead spellings:

```
$ sahjhan --config-dir <holtz>/enforcement defer low BH-001
error: no transition 'defer_low' from state 'idle'      # was: unrecognized subcommand 'defer'
$ ... defer cant-reproduce BH-001
error: no transition 'defer_cant_reproduce' from state 'idle'
$ ... fix commit
error: no transition 'fix_commit' from state 'idle'
```

A state error is the alias having resolved; the probe ledger is simply in
`idle`.

### What is owed on the holtz side

**Do this first, before anything else in item 11:**

1. **Bump `SAHJHAN_VERSION` in `enforcement/hooks/_resolve.py` to `0.22.0`**
   (currently `0.21.0`). The release is published and its artifacts are
   confirmed: run `32674139801` finished `conclusion=success`, and
   `gh release view v0.22.0` lists `checksums.sha256` plus all four triples
   (`aarch64-apple-darwin`, `aarch64-unknown-linux-gnu`, `x86_64-apple-darwin`,
   `x86_64-unknown-linux-gnu`). Delete `bin/.sahjhan-version` + `bin/sahjhan-*` locally to
   force a re-fetch, or the stale pinned binary keeps answering.
   `scripts/hash-trusted-callers.sh` does **not** need rerunning for this —
   nothing in `enforcement/hooks/` changed — but the real_daemon tests are the
   ones that will tell you the new binary is live.
2. **The four taught deferral commands work the moment that lands**, and there
   is a test gap to close in the same commit: nothing exercises a *taught*
   alias against the engine. Add one — the shape that would have caught this
   is "run the command the skill file teaches, against a real ledger, and
   assert it is not a usage error."

**Then D2+D3 proper**, all of it still unbuilt in holtz:

3. `[batches.defer]` in `protocol.toml` with `param = "severity"` and two
   steps — `low → defer_low`, `medium → defer_medium` — plus the two `items`
   queries (open findings whose *latest* filing is that severity; follow
   `item_is_low`'s correlated-subquery shape, per D25).
4. The alias `"defer batch" = "batch defer"`.
5. `DEFERRED.md`: a template in `enforcement/templates/` and a render in
   `renders.toml` triggered `on_event` for `finding_deferred`, so the batch
   writes it. Add it to the managed-docs invariants the way `PUNCHLIST.md` is.
6. **The breaker itself**, which is the actual P0.1 clause and none of the
   above: `A = findings_filed_since(fix_loop_start) / resolved_since(fix_loop_start)`,
   evaluated **per round**; if `A > 1.0` for **3 consecutive rounds**, gate on
   `pattern_done` and **block dispatching the next fix** (Jon's granted
   amendment — not `fix_commit`), until every open LOW and the MEDIUM budget
   are spent via one `sahjhan defer batch --severity low,medium`.
   - The round ordinal is `count(*) FROM events WHERE
     type='pattern_analysis_complete'`; D8 needs the same number.
   - "Last 3 rounds" must be written as a **seq floor**, never `ORDER BY seq
     DESC LIMIT 3` — see the note in `pattern_analysis_overdue` and
     [[enforcement-sql-limit-is-not-a-window]].
   - `fix_loop_start` is the run's first `state_transition` into `fix_loop`.
   - The escape must be **achievable by construction**: the predicate has to
     assert the post-state the escape produces (LOWs deferred **and** the
     MEDIUM budget spent), not an empty set.
7. **D3: no standing triage default.** Deferral appears in skill files only as
   this breaker's escape. The reverted `6b12186` made it unconditional at
   fix-loop entry; do not reintroduce that in any form.

---

## Then, in the decisions doc's order

12. **D6** — the `>25 pattern-filed findings open` conjunct, population from
    `pattern_ids` (ratified by D22, and the field is on the event).
13. **D7** — the ≤3-new-items cap **and** the close-as-many-as-you-open
    obligation. Escape by construction; a design blocker there is a question,
    not a narrowing.
14. **D8** — the sweep replaces pattern analysis past ~round 8; needs item
    11's round ordinal.
15. **P0.5** then **D4** (pre-committed: all four conjuncts as written) under
    **D5** (converging still requires the MEDIUM budget spent).
16. **P0.3** (gate change before batching) and **P4.1** (script the merge —
    cheapest open item).

---

## Working notes for the next session

- Gates run from the venv: `.venv/bin/python3 -m pytest`, `.venv/bin/ruff`,
  `.venv/bin/mypy`. Bare `ruff`/`mypy` are not on PATH and `python3` alone
  lacks `hypothesis`.
- The README test-count badge is gated by
  `tests/test_integration.py::test_readme_badge_counts_match_actual` and needs
  bumping in the same commit as any test-count change. It is currently 2255.
- **The full suite is intermittently flaky on daemon-adjacent tests.** Two of
  six runs early in this session failed —
  `TestProtocolTrackerDaemonTeardown::test_stops_daemon_on_finalized` once, a
  TDD-gate `enforcement eval failed` once — and both passed in isolation and
  in later full runs; a stashed baseline at `36b7ce0` was green. Not caused by
  this session's changes (markdown and test-only at that point), but worth a
  proper look: a stray daemon from the plugin cache
  (`~/.claude/plugins/cache/.../0.141.3/enforcement`) has been running since
  11 Aug.
- `sahjhan query --glob "docs/holtz/**/ledger.jsonl"` reads every run's ledger
  as one. Verified: `**` spans directories, **brace patterns are not
  supported**, and a glob matching nothing exits 2 with `no files matched
  pattern` — which is the first-run case and must be handled, not propagated.
- Editing a daemon-calling hook (`protocol_tracker.py`, `commit_gate.py`,
  `pattern_courier.py`, …) requires `scripts/hash-trusted-callers.sh`.
- Changing `enforcement/transitions.toml` makes `docs/ENFORCEMENT-CONTRACT.md`
  stale; regenerate with `.venv/bin/python3 scripts/enforcement_contract.py --write`.
  Changing `events.toml` alone did **not** — the generated contract was
  unchanged by D22.
- Mechanical multi-site substitutions go through
  `python3 /Users/jonr/Documents/code/scripts/batch_edit.py <spec.json>` —
  there is **no** copy at `holtz/scripts/batch_edit.py`, and none in sahjhan.
- In sahjhan: `cargo test`, `cargo clippy --all-targets -- -D warnings`,
  `cargo fmt --all -- --check`. Its CLAUDE.md carries a **blocking** rule to
  update the in-file `// ## Index` header and the CLAUDE.md lookup tables in
  the same commit as any source change. Its README and `docs/` currently carry
  uncommitted work of Jon's — leave both alone.

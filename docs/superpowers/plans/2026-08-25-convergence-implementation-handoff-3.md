# Convergence work queue — implementation handoff #6

**Written 2026-08-25**, at the end of the sixth implementing session. Stopped on
a clean boundary: two units shipped and committed, two new rulings recorded,
tree clean, nothing half-built. **One question is answered and waiting to be
built** — D35, whose decisive engine constraint is verified below.

**Authority is unchanged and is not this file.** Implement only from
`2026-08-22-convergence-decisions.md`'s rulings and work queue, against the
frozen spec at `docs/design/convergence-speed-proposals.md`. Per-clause status
lives in `docs/design/convergence-speed-status.md`. This file records what
happened and what is next; it decides nothing.

Repo state: branch `dev`, HEAD `7f2c19b`, version **0.165.0**. Full suite green
(2569 collected, `pytest` exit 0 observed, 8 skips), `ruff` clean,
`mypy` clean (66 files), `enforcement_lint.py` at its **0 errors / 2 warnings**
baseline (both pre-existing H1s on `prediction` / `prediction_outcome`), the
contract gate PASS at 38 commands, and `ENFORCEMENT-CONTRACT.md` regenerated
and current. **No hook was bypassed — no `--no-verify` in this session.**

---

## Shipped this session

| Commit | What landed |
|---|---|
| `c14c881` | **P4.1** — `enforcement/scripts/merge_punchlists.py`. The merge protocol, executed |
| `d7fb931` | **D29 first half** — `theoretical_courier.py`; a `theoretical` finding auto-defers |

Both proven non-vacuous by mutating the implementation with `Edit`, re-running,
observing RED, and reverting.

### P4.1 — script the merge

Sort, one-to-one match, classify, record each Justine-only finding under her
`BJ-` id, re-file Holtz's id where her severity is higher, merge the impact
graphs, write `MERGE-REPORT.md`. The agent's residual job is the one class the
protocol itself excepts: adjudicating contradiction candidates.

Three decisions were forced, not chosen:

- **It lives in `enforcement/scripts`, not the spec's bare `scripts/`.** That
  directory is `enforcement_lint.py`'s only `tool_dir`, so a discovered event
  writer there gets producer id `tool:<path>`; anywhere else it is
  `hook:<path>` and H4 then demands a `hooks/hooks.json` entry it can never
  have. **The write half pins the file's home.** H3 caught the missing producer
  declaration on the first lint run.
- **No courier.** `finding` is a normal event, so `chain.rs::append` writes the
  ledger file directly and the whole thing runs in the agent's sandboxed shell.
- **`severity_disagreements` is a subset of `agreements`**, not a sixth class —
  `merge-protocol.md:56` counts it inside the Agreement total and says
  explicitly it is not double-counted. One list and a view of it cannot
  disagree.

`validate_punchlist.py` now keeps the Problem/Evidence/Discovery-Chain text and
the Reachability field it was already extracting and discarding, so the merge
needs no second parser for the same file.

**Not in scope, deliberately:** the archive step stays the agent's single `mv`.
`merge-protocol.md:138` assigns it to the parent process, and gating it is
P4.9's, still open.

### D29 first half — `theoretical` auto-defers

`theoretical_courier.py` (PostToolUse/Bash) writes a real `finding_deferred`
with `reason=theoretical`, so there stays exactly one definition of closed and
`DEFERRED.md` needs no second rule. The population is re-derived through the
named `open_theoretical_findings` predicate in `protocol.toml` — resolved at
runtime, never restated in Python (H7's rule).

The property that makes auto-deferral safe, and it is **not** obvious:
`all_critical_resolved` requires every CRITICAL to carry a `finding_resolved`
and refuses a deferral by design, so auto-deferring a `theoretical` CRITICAL
would deadlock convergence outright *if the deferral also closed the fix
route*. It does not, because **`fix_commit` has no openness gate** — its gates
are the ordinary fix-work ones, all satisfiable by doing the work.
`test_fix_commit_does_not_gate_on_openness` fails the build if `item_open` is
ever added there.

---

## Two rulings this session (D34, D35) — recorded in the decisions doc, §H

| # | Subject | Ruling |
|---|---|---|
| D34 | The eligibility gate has no escape for `fault_injected` | **HOLD THE GATE, SHIP THE COURIER** — the gate waits until finalize batching gives `fault_injected` a real escape |
| D35 | What a "module" is for finalize batching | **THE CONTAINING DIRECTORY** of the file named in `location` |

**Why D34 was raised.** D29 called the eligibility gate "a plain named-query
gate of the `item_is_low` shape [that] needs nothing new". The shape is right;
the escape is not there. Observed against sahjhan 0.23.0 and the real config,
driving the state machine into `fix_loop`:

- A `fault_injected` **CRITICAL** and **HIGH** are `result: blocked` on all
  three deferral routes. `defer_low`/`defer_medium` are literal severity
  equality, so no HIGH or CRITICAL can use either.
- `all_critical_resolved` stayed `false` after deferring — by design.
- `finding_resolved` is emitted by exactly two transitions, `fix_commit` and
  `merge_finding`.

So gating `fix_commit` on `user_reachable` removes the only route to
`finding_resolved` for a fault-injected CRITICAL while nothing can defer it:
the run can neither converge nor make itself converge. Re-grading is not an
escape either — `reachability` is re-filable with a plain `sahjhan event
finding` and the latest filing wins, so it is a forgery. **The gate's escape
IS the finalize batching**, which is why they had to be one decision.

---

## Next up

### 1. D35 — `fault_injected` finalize batching (unblocks D34)

One hardening commit per **containing directory**. `finalize` is the right
place: an open `fault_injected` HIGH does not block `converge`
(`all_user_reachable_high_closed` filters on `reachability='user_reachable'`),
so these survive to `converged → finalized`.

**The decisive engine constraint, verified in sahjhan's source — read this
before designing anything:**

- `EmitConfig` (`src/config/transitions.rs:101`) produces **exactly one** event
  with a fixed field map. `emits` is a `Vec<EmitConfig>`, not a fan-out. **A
  transition cannot emit N `finding_resolved` events, one per id in a batch.**
- `src/state/machine.rs:250-263` refuses to emit a `restricted` event, checked
  again at emit time on top of config validation.

So "one hardening commit closes that module's fault-injected findings" has no
transition-emit expression. Two shapes remain, and **choosing between them is a
question, not an implementation detail**:

- **(a) Coverage gate.** `finalize` requires every open `fault_injected`
  finding to be covered by a `hardening_batch` for its module. The findings
  stay *open* on a finalized run.
- **(b) A courier closes them.** A courier writes N `finding_resolved` events —
  possible precisely because `finding_resolved` is non-restricted. Consistent
  with D29's own reasoning ("so there stays exactly one definition of closed"),
  but it is a courier closing findings, which is new.

**Do not put the directory rule in SQL.** `location` is free text
(`file.py:88`, `` `file.py:88` ``, `file.py:88 (function f)` — all three appear
in this repo's archived ledgers). Derive the module in Python, in a script
under `enforcement/scripts`, and have the ledger hold the *result* — which ids
a batch covered — so the `finalize` gate is plain id membership with no string
manipulation. That is D8's stale-sweep shape and `merge_punchlists.parse_location`
already does the parsing.

D29's warning still stands: **it must not land as unenforced prose.**

### 2. D34 — the `user_reachable` eligibility gate, *after* D35

A named query of the `item_is_low` shape on `fix_commit`. It must not land
before D35, or it deadlocks convergence exactly as measured above.

### 3. P0.3's remaining half

Worktree isolation for fix subagents, and rewriting `phase-fix-loop.md:68` to
serialize *commits, not findings*. Untouched, unblocked — its gate change
shipped last session. Still needs the `hook_e2e` subagent-parity test CLAUDE.md
mandates for any change to what a subagent may do.

---

## Working notes for the next session

Everything in handoff #5's notes still holds. New this session:

- **Two different `_common.py` modules ship in this tree** —
  `hooks/_common.py` and `enforcement/hooks/_common.py` — with the same exit
  helpers and a *different* `resolve_config_dir`. Whichever an earlier test
  imports first wins for the whole pytest process, and **the import still
  succeeds**, so a hook silently resolves its config to the repo root and every
  ledger query returns empty. Symptom: tests pass alone and fail in the fast
  subset. Worse, negative assertions pass **vacuously** — a broken query and a
  correct exclusion are indistinguishable when both are empty. **Two defences:**
  drive hooks by subprocess (CLAUDE.md's rule 2, which exists for this), and
  make every negative assert something that must *survive*, never an empty set.
- **`test_bash_source_write_gate` and `TestProtocolTrackerDaemonTeardown` fail
  under concurrent pytest load.** The bash TDD gate gives `sahjhan hook eval` a
  5-second budget (`_sahjhan_bootstrap.py:1073`), and "enforcement eval failed"
  is a *timeout*, not an error. `TestProtocolTrackerDaemonTeardown` fails at
  `b3ebda7` too. **Do not "fix" either by widening the timeout**, and do not
  bisect a config change against them — a false bisect cost time this session
  before three clean re-runs showed it. Run one suite at a time.
- **Re-hash the trusted-callers manifest LAST — again.** Adding `--show` to the
  courier after regenerating made the manifest stale instantly, and it surfaced
  as a cascade of unrelated daemon-auth failures across
  `test_sahjhan_integration.py`, not as anything naming the courier.
  `TRUSTED_SCRIPTS` in `scripts/hash-trusted-callers.sh` is still hand-kept: add
  the path *first*, regenerate *last*.
- **A `--show` mode is worth building into every courier.** It is the diagnostic
  to run when a board is carrying items that should have come off it, and it is
  the only honest way to test the derivation given the `_common` collision
  above. `stale_sweep.py --show` is the precedent.
- **Both README counts move on a new hook** (18 → 19), and the test badge moved
  twice (2490 → 2541 → 2569). Set both **last**, after no more tests will be
  added.

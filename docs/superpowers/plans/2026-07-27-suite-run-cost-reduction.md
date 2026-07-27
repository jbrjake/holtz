# Fix-loop suite-run cost reduction (proposals 1–4)

**Started:** 2026-07-27
**Branch:** dev
**Baseline:** holtz 0.140.1 (`cd82fed`), sahjhan 0.20.0
**Origin:** console proposal in session 3cb88455. User approved proposals 1–4, declined 5 (xdist docs).
**Related issue:** #83 (non-Python false-green) — filed this session, separate work.

## Problem

The fix loop runs the target's **full test suite three times per finding**, only
one of which is enforced:

| Where | Source | Enforced? |
|---|---|---|
| Subagent step 5 | `phase-fix-loop.md` "Run full suite. Confirm all pass." | prose |
| Orchestrator step B.10 | `phase-fix-loop.md` "re-run the full suite" | prose |
| `fix_commit` gate | `enforcement/transitions.toml:80` | **yes** |

B.10's run and the gate's run execute on a byte-identical working tree
(`git commit` doesn't modify working-tree contents), so one is strictly
redundant. On the eval-harness spec's own numbers (90 fixes, 60 s suite) this is
~4.7 h of suite execution where the spec budgeted 1.5 h.

## Target

| Stage | Suite-time (60 s suite, 90 fixes, 13 lenses) |
|---|---:|
| Today | ~4.7 h |
| + P1 collapse to 1 run | ~1.7 h |
| + P3 selective + boundary fulls | ~40 min |

## Design decisions (settled)

**D1. No sahjhan change required.** Every mechanism exists: `record_authed_event()`
(`enforcement/hooks/_common.py:245`), `restricted = true` events, trusted-callers
SO_PEERCRED auth, active-ledger marker at `docs/holtz/.sahjhan/active-ledger`.

**D2. `--lf` is REJECTED for gate commands.** `--last-failed` runs *only* the
previously-failing tests, so a gate using it can pass having run a two-test
subset — the exact false-green class as issue #83. Use `--ff` (`--failed-first`)
instead: same fail-fast benefit, still runs the whole suite.

**D3. `--no-cov` is REJECTED for the default.** It is a pytest-cov option; on a
target without that plugin pytest exits 4 (`unrecognized arguments`), breaking
every such target. Keep it as a documented override only.

**D4. The gate must NOT record to the ledger.** A `command_succeeds` gate runs
while the daemon is evaluating a transition; calling back into the daemon to
append an event risks re-entrancy/deadlock. Split the roles:
- **agent path** (`--record`): runs the suite, records `suite_green`. No
  transition in flight, so the daemon call is safe.
- **gate path** (`--check`): reads `ledger.jsonl` directly (no daemon), pure
  predicate, exit 0/1. Blocks with a satisfiable escape ("run holtz-test").

**D5. Tree hash excludes `docs/holtz/**`.** STATUS.md / PUNCHLIST.md are
rewritten every fix and cannot affect the target's tests; including them would
invalidate every cached result immediately.

**D6. The agent cannot forge `suite_green`.** Three layers: the event is
`restricted` (daemon refuses `sahjhan event`); the writer script lives under
`enforcement/` (managed path — pre-edit hook + bash_guard block edits, cf. #71);
and trusted-callers.toml pins its SHA-256 so a modified script is rejected.
The script computes the tree hash and runs the suite itself — it accepts no
caller-supplied hash or result.

## Tasks

- [ ] **T1 — P2 fail-fast gate command** (smallest, independent)
  - `enforcement/transitions.toml`: default -> `python3 -m pytest -x --ff --tb=line -q`
  - Applies to all 3 pytest gates (lines 80, 267, 306)
  - Keep the `${HOLTZ_PYTEST:-...}` wrapper (contract test
    `tests/test_enforcement_config.py:404` asserts the shape)
  - Add a contract test asserting `--lf` never appears in a gate cmd (D2)
  - Gate: `pytest -m contract`, `python3 scripts/contract_gate.py`

- [ ] **T2 — P4 `suite_green` event + verify_suite.py**
  - `enforcement/events.toml`: new `suite_green`, `restricted = true`,
    attestation `tool`, fields: tree_hash, scope, command, test_count,
    + run context
  - `enforcement/scripts/verify_suite.py`: `--record` / `--check` modes
  - `scripts/hash-trusted-callers.sh` regen (MANDATORY — see memory
    `trusted-callers-manifest-regen`; skipping silently disables enforcement)
  - `scripts/enforcement_lint.py` must stay green (H1 closure, H5 attestation)
  - Tests: hook_e2e for the daemon record path, unit for tree hashing

- [ ] **T3 — P3 selective per-fix + full at boundary**
  - Confirm `impact_graph.py` CLI exposes `--types` on `blast_radius`
  - `verify_suite.py --scope affected`: changed files -> graph nodes ->
    `tests` edges -> test file list
  - `fix_commit` gate -> affected scope; `iteration_boundary` gate -> full scope
  - Fallback: if the graph has no `tests` edges, fall back to full suite
    (never silently narrow — cf. #83)

- [ ] **T4 — P1 collapse the redundant runs**
  - `skills/holtz/references/phase-fix-loop.md`: subagent step 5 -> affected
    subset via verify_suite; orchestrator B.10 -> ledger check, not a re-run
  - Contract tests must be updated in the SAME commit (CLAUDE.md rule)
  - `test_subagent_contract_consistency.py` may need updating

- [ ] **T5 — release**
  - `scripts/pre-release-check.sh`, changelog, release PR dev -> main

## Open questions

- Does `impact_graph.py`'s CLI expose `--types` for `blast_radius`? (API does.)
- `iteration_boundary` currently has the `pattern_analysis_overdue` gate only;
  adding a full-suite gate there lengthens that transition — acceptable since it
  fires every 3–5 fixes, not every fix.

## Session log

### Session 1 (2026-07-27)
- Investigated cost structure; confirmed 3 runs/fix, 1 enforced.
- Confirmed no sahjhan change needed (D1).
- Caught D2 (`--lf` false-green) and D3 (`--no-cov` breaks non-cov targets)
  before writing them into the config.
- Filed #83 (unrelated but adjacent: non-Python false-green).
- Wrote this plan.

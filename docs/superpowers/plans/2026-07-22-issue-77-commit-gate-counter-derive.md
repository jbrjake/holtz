# Issue #77: commit_gate pattern-overdue counter diverges from ledger → deadlock

**Goal:** Kill the spurious `git commit` deadlock where the "Pattern analysis
overdue" hard block fires on a cached counter that has drifted from the ledger,
directing the auditor to run `transition pattern_check` — a transition whose own
gate is *blocked* because the ledger shows `< 3` findings resolved. The escape
is unsatisfiable.

**Root cause:** `enforcement/hooks/protocol_tracker.py::_apply_sahjhan_cmd`
maintained `fixes_since_pattern` as a **hand-mirrored** counter, incremented on
the mere *presence* of the token `fix_commit` and reset on `pattern_check` /
`pattern_done` — anywhere in the command text. Read-only diagnostics
(`sahjhan gate check fix_commit`, `sahjhan query "... 'fix_commit' ..."`,
`sahjhan gate check pattern_check`) contain those tokens, so they silently moved
a gate-controlling counter. Meanwhile the authoritative `pattern_check`
transition gate counts real ledger `finding_resolved` events. Two independent
counters → drift → deadlock.

## Decision: derive, don't mirror (issue's preferred fix #1)

Compute `fixes_since_pattern` **from the ledger** — the exact query the
`pattern_check` gate uses (`enforcement/transitions.toml`):

```sql
SELECT count(*) FROM events
WHERE type='finding_resolved'
  AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)
```

Then the commit-gate block condition (`counter >= 3`) and the `pattern_check`
gate readiness (`finding_resolved >= 3`) are the **same fact**, so they can never
disagree: whenever the commit gate blocks, the escape it prints is satisfiable.

## No sahjhan change required — and shouldn't be

sahjhan already ships a generic `query` primitive (`sahjhan --config-dir <dir>
query "<sql>" --format json`, resolves the active-ledger marker — the same ledger
the gates evaluate). The SQL above is **holtz domain logic** (`finding_resolved`,
`pattern_analysis_complete` are holtz event types) and stays entirely in holtz.
Pushing it into the engine would pollute sahjhan's generic state machine with
holtz business logic — exactly what the project forbids. Verified empirically
against a real v0.19.0 ledger: 2 `finding_resolved` → `n=2`; after a
`pattern_analysis_complete` baseline + 1 more → `n=1`.

## Changes

1. **`enforcement/hooks/protocol_tracker.py`**
   - `_refresh_from_sahjhan`: after the status refresh, when state is
     `fix_loop`/`pattern_analysis`, run the ledger count query and set
     `cache["fixes_since_pattern"]` from it. Query failure → leave the previous
     value (safe: under-count only delays the nudge, never deadlocks).
   - `_apply_sahjhan_cmd`: delete the token-mirror increment/reset. Keep the
     pending-commit clear, but scope it to the **mutating** `transition
     fix_commit` verb (`_runs_transition`), so a diagnostic that merely mentions
     `fix_commit` can't silently clear a real pending commit either.

2. **`enforcement/hooks/commit_gate.py`** — unchanged. It reads
   `cache["fixes_since_pattern"]`, now ledger-derived. Kept subprocess-free so it
   stays fast on every Bash call.

3. **Tests**
   - `tests/test_protocol_enforcement.py`: the mock full-cycle test no longer
     asserts the counter increments on token match (mirror removed); it asserts
     the pending-commit clear still works and the counter is *not* moved without
     a real ledger. New mock tests prove diagnostics don't move the counter.
   - `tests/test_e2e_audit_flow.py`: new `real_daemon` test — append N
     `finding_resolved`, run protocol_tracker, assert the derived counter == N,
     assert the commit gate blocks at 3 **and** the `pattern_check` gate is
     simultaneously ready (escape satisfiable). This is the regression guard for
     the deadlock.

4. **`enforcement/trusted-callers.toml`** — regenerated (protocol_tracker.py hash
   changed; a stale manifest silently disables enforcement).

## Failure modes addressed (all four from the issue)

1. Over-count → spurious block: gone. Diagnostics trigger a refresh that
   re-derives from the ledger; block condition ≡ pattern_check readiness.
2. Under-count → silent skip: gone. Diagnostics no longer zero the counter.
3. Cross-`/clear` staleness: the counter re-derives on the first sahjhan command
   of the new window (`resume`), and the `iteration_boundary` gate already forces
   a pattern round before `/clear`, moving the baseline.
4. Shell-var indirection: the counter no longer depends on token-matching in
   `_apply_sahjhan_cmd`; any later recognized sahjhan command re-derives it, so
   indirection can't permanently corrupt it.

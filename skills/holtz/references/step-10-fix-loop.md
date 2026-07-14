# Step 10: TDD Fix Loop — Detailed Procedures

Read this file at the start of Step 10. This file is shared by Holtz and Justine — the fix process is disciplined regardless of how findings were discovered.

**Division of labour (orchestrator vs. fix subagent).** Each finding's investigation, authoring, and verification is delegated to a **fix subagent** that works **in the enforced tree**; the **orchestrator** validates and commits (see [phase-fix-loop.md](phase-fix-loop.md) → Per-Item Fix Procedure). The triage flowchart and paths below describe what the **subagent** does inside its own context — reading code, forming and testing hypotheses, then running the enforced TDD sequence: writing the reproduction test, recording `test_failed_before_fix`, writing the fix, running the suite, and hardening. The subagent is under the **same enforcement the orchestrator is** — the TDD pre-edit gate fires on its edits too and does not look at `agent_id`, so it must run Sahjhan to unblock its own fix edit. The subagent returns a compact result (root cause, blast-radius node, test names, suite pass-count) and a triage verdict; it does **not** `git commit` and does **not** run a `transition`. The orchestrator then validates the verification (re-run suite, confirm the ledger events) and runs the commit + `fix_commit`. This keeps the read/reason-heavy work out of the main context (the ~300K budget) while git and protocol-state transitions stay linear in the orchestrator.

## Triage Flowchart

```dot
digraph {
  rankdir=TB
  node [shape=box]
  read [label="Re-read worklist\n(MERGED if exists,\notherwise PUNCHLIST)"]
  triage [label="Triage item\nby category"]
  fast [label="Fast Path\n(test→fix→commit)"]
  investigate [label="Investigation Path\n(layers→confidence→fix)"]
  cantrepro [label="Can't-Reproduce Path\n(widen→bisect→defer)"]
  defer [label="Priority Deferral\n(LOW or MEDIUM budget)"]
  harden [label="Per-Fix Hardening\n(edges+regression)"]
  blast [label="Blast Radius Analysis\n(impact graph 2-hop)"]
  next [label="Next item"]

  read -> triage
  triage -> fast [label="test/doc/design\nor deterministic bug"]
  triage -> investigate [label="intermittent\nor theoretical bug"]
  triage -> cantrepro [label="repro test\nunexpectedly passes"]
  triage -> defer [label="LOW severity\nor MEDIUM with budget"]
  fast -> harden
  investigate -> harden
  cantrepro -> harden [label="if reproduced"]
  cantrepro -> next [label="sahjhan defer\ncant-reproduce"]
  defer -> next [label="sahjhan defer\nlow/medium"]
  harden -> blast
  blast -> next
}
```

## Triage Rules

- `test/*`, `doc/*`, `design/*` items → **Fast Path**
- `bug/*` items with determinism = deterministic → **Fast Path**
- `bug/*` items with determinism = intermittent or theoretical → **Investigation Path**
- Any item where the reproduction test unexpectedly passes → **Can't-Reproduce Path**

Commit format: `fix(<scope>): <desc>` with punchlist ID in body.

## Fast Path

For straightforward items where the root cause is obvious from the finding:

1. Write failing test. Verify it fails. Minimal fix. Full suite. Commit.
2. If mutation data exists from step 0e.1, re-run the mutation tool on the changed function(s) and record the before/after mutation kill rate in the punchlist item's Resolution notes (e.g., 'Mutation kill rate: 67% → 92%'). Quality check, not gate.
3. **Update PUNCHLIST.md with resolution IMMEDIATELY after each commit** (status, commit hash, validating test).
4. Update STATUS.md with last completed item ID. If this fix revealed a non-obvious insight, update the Strategy section's Last Insight field.

## Investigation Path

Use extended thinking (ultrathink) for this step — root cause analysis through six abstraction layers requires deep reasoning.

For `bug/*` items where the root cause is not obvious, the bug is intermittent or theoretical, or multiple hypotheses need testing. See [investigation-format.md](investigation-format.md) for the investigation file format.

1. Create an investigation file and link it from the punchlist item's `**Investigation:**` field.
2. **Investigate bottom-up** through the layer stack:

   | Layer | Check |
   |-------|-------|
   | **Data** | Is the input what you think it is? Log actual values, types, shapes at entry point |
   | **Dependencies** | Are called systems working? DB connected, API reachable, file exists, permissions correct? |
   | **State** | Is state correct at each step? Add assertions/logging at intermediate points |
   | **Logic** | Does the code do what it says? Trace actual execution path, not intended one |
   | **Integration** | Do pieces work together? Boundary serialization, type mismatches, contract violations |
   | **Timing** | Race condition, async ordering, cache staleness, concurrency issue? |

   At each layer: form a specific, falsifiable hypothesis. Design the smallest check that confirms or refutes it. Run it. Record in the investigation file.

3. **For regressions:** use `git bisect` to find the breaking commit before investigating layers.
4. **Require HIGH confidence** before fixing. If confidence is LOW or MEDIUM, design one more check to raise it.
5. Once root cause is confirmed at HIGH confidence: write failing test, verify it fails, minimal fix, full suite, commit.
6. **Update punchlist** with resolution, root cause confidence, and commit hash IMMEDIATELY.
7. Update STATUS.md. Update the Strategy section's Last Insight with the root cause finding.

## Can't-Reproduce Path

When the reproduction test passes (bug not triggered), do NOT skip the item. Escalate:

1. **Widen conditions:** Try different inputs, orderings, timing, data sizes, concurrency levels
2. **Check environment:** Different OS, runtime version, dependency versions, config differences
3. **Statistical reproduction:** For intermittent bugs, run the test in a loop (100-1000x) and measure failure rate
4. **Git bisect:** If the behavior "used to work," find the breaking commit
5. **Add instrumentation:** If still not reproducible, add logging/tracing to capture state

Log every attempt in the investigation file. Failed reproduction attempts are evidence.

If not reproducible after structured attempts:

1. Ensure reproduction attempts are documented in `docs/holtz/investigations/{item_id}.md`
2. Run: `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" defer cant-reproduce {item_id}`
3. Run: `sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event finding_deferred --field id={item_id} --field reason=cant_reproduce --field evidence_path=docs/holtz/investigations/{item_id}.md`
4. Update PUNCHLIST.md status to DEFERRED

Do not silently drop the item.

## Priority Deferral

For LOW and MEDIUM findings where the fix is legitimate but lower priority than the current audit scope. This is not a shortcut — attempt triage before deferring.

**LOW severity:** All LOW findings may be deferred.

```
sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" defer low {item_id}
sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event finding_deferred --field id={item_id} --field reason=low_priority
```

**MEDIUM severity:** Up to half of MEDIUM findings may be deferred. The budget is enforced at deferral time — if the cap is reached, the transition is blocked.

```
sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" defer medium {item_id}
sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" event finding_deferred --field id={item_id} --field reason=medium_budget
```

HIGH and CRITICAL findings are never deferrable via priority (only via can't-reproduce with evidence).

## Per-Fix Hardening

After each fix passes the reproduction test and full suite:

1. **Edge variants:** Does the fix handle null, empty, boundary, and concurrent cases? If not, write tests for them.
2. **Regression risk:** Could this specific fix regress? If the fix is in a path without existing test coverage, add a regression test beyond the reproduction test.
3. Run full suite again after any hardening tests are added.

This is per-fix robustness, not pattern analysis. Step 11 looks across fixes for systemic issues.

## Blast Radius Analysis

After each fix passes the reproduction test, full suite, and per-fix hardening:

See [impact-graph-operations.md](impact-graph-operations.md) for the blast radius query commands and risk score update procedures.

1. **Identify** the changed function(s)/module(s)
2. **Query** the impact graph with `blast_radius` (depth 2, or depth 3 for architectural fixes)
3. **For each node in the blast radius:** check assumptions, update edges
4. **Update impact graph:** lower risk scores, add/update edges
5. **Update STATUS.md** Strategy section with blast radius findings

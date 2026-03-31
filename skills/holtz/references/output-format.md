# Terminal Output Format

Holtz emits structured terminal output at phase transitions, findings, and convergence. These formats make runs watchable live and reviewable after completion.

## Phase Banners

At the start of each phase, emit a banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PHASE {N}: {NAME}
  {brief description of what this phase does}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Phase names:
- PHASE 0: RECON (Steps 0-4)
- PHASE 1: TOOLCHAIN (Step 1, runs as subagent during recon)
- PHASE 2: CODE SIGNALS (Step 2, runs as subagent during recon)
- PHASE 3: PREDICTIONS (Step 4)
- PHASE 4: AUDIT (Steps 6-8)
- PHASE 5: ADVERSARIAL MERGE (Step 9)
- PHASE 6: FIX LOOP (Steps 10-14)
- PHASE 7: CONVERGENCE (Steps 15-20)

When a phase completes, emit a summary line:

```
  ✓ Phase {N} complete — {key metrics from the phase}
```

Examples:
```
  ✓ Phase 0 complete — 37 nodes, 35 edges, 2 items escalated, 5 predictions
  ✓ Phase 4 complete — 12 findings (4 bug, 3 test-quality, 5 doc-drift)
  ✓ Phase 6 complete — 8/8 items resolved, 3 patterns identified
```

## Finding Callouts

When a bug is confirmed, emit a visually prominent callout:

```
  ██ BUG CONFIRMED: {ID} ({SEVERITY}, {category})
  ██ {one-line description}
  ██ Predicted by: Prediction {N} ({confidence}) — {basis}
```

The `Predicted by` line is only included when the finding matches a prediction. Example:

```
  ██ BUG CONFIRMED: BH-004 (MEDIUM, bug/logic)
  ██ parse_brief field extraction leaks across fields on empty values
  ██ Predicted by: Prediction 1 (HIGH) — regex-newline-leak pattern library
```

For non-bug findings (test-quality, doc-drift, design), use a lighter callout:

```
  ▸ FINDING: {ID} ({SEVERITY}, {category}) — {one-line description}
```

## Prediction Scorecard

After the audit phases (Steps 6-8), before the merge, show prediction results:

```
  Predictions: {confirmed}/{total} confirmed
    ✓ P{N} ({confidence})  {target}  → {punchlist ID}
    ✗ P{N} ({confidence})  {target}  → {reason not confirmed}
```

Example:
```
  Predictions: 2/5 confirmed
    ✓ P1 (HIGH)  regex-newline-leak in parse_brief:53     → BH-004
    ✗ P2 (MED)   CRLF in header regex                     → not a bug
    ✓ P3 (MED)   code-fence-unaware in parse_brief        → BH-005
    ✗ P4 (HIGH)  README counts stale                      → counts correct
    ✗ P5 (LOW)   hook coverage artifact                   → not a real gap
```

## Merge Summary

After the adversarial merge (Step 9), show the classification:

```
  ┌─ ADVERSARIAL MERGE ─────────────────────────────────────────┐
  │  Agreements:     {N}  ({brief note})                        │
  │  Holtz-only:     {N}  ({brief note})                        │
  │  Justine-only:   {N}  ({brief note})                        │
  │  Contradictions: {N}                                        │
  │                                                             │
  │  Blind spots:                                               │
  │    Holtz missed: {categories}                               │
  │    Justine missed: {categories}                             │
  └─────────────────────────────────────────────────────────────┘
```

## Fix Loop Progress

During Step 10, show a running tally for each fix:

```
  FIX {current}/{total}: {ID} — {description}
    ✗ {test_name}      FAIL (expected — TDD red)
    ✓ Fix: {one-line summary of the change}
    ✓ {test_name}      PASS
    ✓ Full suite: {passed} passed, {failed} failed
```

## Convergence Verdict

At convergence (after convergence_check.py returns exit 0):

```
═══════════════════════════════════════════════════════════════════════════
  CONVERGED

  {N} findings ({breakdown by severity}) — all resolved
  {tests} tests passing | {linter status} | {type checker status} | {coverage}%
  {N} commits: {short hashes}

  Context: {tokens} tokens | Cost: ${main} (main) + ${subagents} (subagents)
═══════════════════════════════════════════════════════════════════════════
```

If convergence is NOT reached (circuit breaker or iteration boundary):

```
───────────────────────────────────────────────────────────────────────────
  NOT CONVERGED — iteration {N}

  {resolved}/{total} findings resolved | {open} OPEN | {in_progress} IN PROGRESS
  Next: {what needs to happen next}
  Action: /clear then any message to continue
───────────────────────────────────────────────────────────────────────────
```

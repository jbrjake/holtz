# Hand-maintained auditor status file — format

This is the format for an auditor's **own** status file: `docs/holtz/justine/STATUS.md`. It is Justine's program counter — the first file she reads after any context compaction and the last she updates after completing a step. Nothing renders it, so keeping it current is her job.

**This is not the format of `docs/holtz/STATUS.md`.** Holtz's status file is rendered from the ledger on every transition (`renders.toml` → `templates/status.md.tera`), and every write vector to it is denied — it is a view, not a document. It carries the current state, the transitions taken, perspective completion, and the finding counts, all derived. There is no Next Action to fill in and no Last Insight to update: the ledger already knows where the run is, because the transition that moved it is the thing that recorded it. Holtz advances the run by recording events, and reads position with `sahjhan status`.

## Template

```markdown
# Holtz Status

**Project:** {project name}
**Started:** {ISO date}
**Last Updated:** {ISO timestamp}
**Iteration:** {N}

## Current Position
**Step:** {0-20}
**Status:** {IN PROGRESS | BLOCKED | CONVERGING | COMPLETE}

## Completed
- [ ] Step 0: Project overview + drift detection
- [ ] Step 1: Run toolchain (subagent)
- [ ] Step 2: Code signals (subagent)
- [ ] Step 3: Recon summary
- [ ] Step 4: Predictions
- [ ] Step 5: Dispatch Justine
- [ ] Step 6: Doc-to-implementation audit
- [ ] Step 7: Test quality audit
- [ ] Step 8: Adversarial code audit
- [ ] Step 9: Merge Justine findings (subagent)
- [ ] Step 10: TDD fix loop
- [ ] Step 11: Pattern analysis [recurring]
- [ ] Step 12: Per-fix hardening [recurring]
- [ ] Step 13: Blast radius check [recurring]
- [ ] Step 14: Lens rotation
- [ ] Step 15: Convergence check
- [ ] Step 16: Resweep
- [ ] Step 17: Architecture baseline update (subagent)
- [ ] Step 18: Pattern library contribution (subagent)
- [ ] Step 19: Living punchlist update (subagent)
- [ ] Step 20: Write docs/holtz/justine/SUMMARY.md

## Next Action
{Exactly what to do next. One sentence. Specific enough to resume without context.}

## Metrics
| Metric | Baseline | Current |
|--------|----------|---------|
| Tests passing | {N} | {N} |
| Tests failing | {N} | {N} |
| Tests skipped | {N} | {N} |
| Punchlist open | — | {N} |
| Punchlist resolved | — | {N} |
| Punchlist deferred | — | {N} |
| Patterns identified | — | {N} |
| Convergence iterations | — | {N} |

## Cold File Coverage
| Metric | Value |
|--------|-------|
| Total source files | {n} |
| Files audited (any run) | {n} |
| Cold file ratio | {n}% |
| Cold files audited this run | {n} |

## Notes
{Anything important for resumption: blocked items, user decisions, scope constraints.}

## Active Lens
**Current:** {component | integration | security | error-propagation | data-flow | contract}
**Lenses Completed This Run:**
- [ ] component
- [ ] integration
- [ ] security
- [ ] error-propagation
- [ ] data-flow
- [ ] contract
**Finding Rate (current lens):** {N findings in M minutes}

## Pattern Library
{Compact list of all patterns discovered so far, current run + prior runs}
- **PAT-001:** {one-line description} ({N instances}, run {R})
- **PAT-002:** ...

## Strategy
**High-Risk Areas:** {from recon, updated as audit progresses}
**Last Insight:** {the most recent non-obvious observation — what the auditor learned that should inform the next step}
**Approach:** {current tactical approach, e.g., "checking extraction paths after each masking fix"}
```

## Rules

- Update after every completed step.
- The "Next Action" field must be specific enough that a fresh context can resume without reading anything else first.
- Metrics update with each step transition and each fix loop iteration.
- If blocked, explain why and what would unblock it.
- Active Lens updates whenever the auditor switches to a different lens. Record the completed lens in "Lenses Completed This Run" and reset finding rate tracking. (Lens switching protocol is defined in Tier 2. Until then, the lens remains `component` for the full run.)
- Pattern Library updates whenever a new PAT-NNN pattern is discovered. Carry forward patterns from prior runs.
- Strategy updates after each fix or significant insight. The "Last Insight" field captures what the auditor learned that should inform the next step.

# docs/holtz/STATUS.md Format

This file is Holtz's program counter. Located at `docs/holtz/STATUS.md` in the target project. It is the first file read after any context compaction and the last file updated after completing any step.

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
- [ ] Step 20: Write SUMMARY.md

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

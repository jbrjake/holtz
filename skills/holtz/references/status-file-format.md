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
**Phase:** {0-6}
**Step:** {e.g., 0c, Phase 2 batch 3, Phase 4 item BH-012}
**Status:** {IN PROGRESS | BLOCKED | CONVERGING | COMPLETE}

## Completed
- [x] Phase 0a: Project overview
- [x] Phase 0b: Test infrastructure
- [ ] Phase 0c: Test baseline
- [ ] ...

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

## Notes
{Anything important for resumption: blocked items, user decisions, scope constraints.}

## Active Lens
**Current:** {component | integration | security | error-propagation | data-flow | contract}
**Lenses Completed This Run:** {comma-separated list}
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

- Update after every completed step, not just every phase.
- The "Next Action" field must be specific enough that a fresh context can resume without reading anything else first.
- Metrics update with each phase transition and each fix loop iteration.
- If blocked, explain why and what would unblock it.
- Active Lens updates whenever the auditor switches to a different lens. Record the completed lens in "Lenses Completed This Run" and reset finding rate tracking.
- Pattern Library updates whenever a new PAT-NNN pattern is discovered. Carry forward patterns from prior runs.
- Strategy updates after each fix or significant insight. The "Last Insight" field captures what the auditor learned that should inform the next step.

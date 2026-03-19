# BUG-HUNTER-STATUS.md Format

This file is Holtz's program counter. It is the first file read after any context compaction and the last file updated after completing any step.

## Template

```markdown
# Bug Hunter Status

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
```

## Rules

- Update after every completed step, not just every phase.
- The "Next Action" field must be specific enough that a fresh context can resume without reading anything else first.
- Metrics update with each phase transition and each fix loop iteration.
- If blocked, explain why and what would unblock it.

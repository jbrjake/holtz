# Phase 1: Doc-to-Implementation Claims

## README.md Claims (PUBLIC-CONTRACT lens)

| # | Claim | Location | Status |
|---|-------|----------|--------|
| 1 | "nine analytical lenses" | README:98 | VERIFIED — 9 lenses in lens-registry.md |
| 2 | "Phase 0: ...Eight steps" | README:108 | VERIFIED — 0a-0h = 8 main steps |
| 3 | "twelve anti-patterns" | README:40 | VERIFIED — 12 in anti-patterns.md |
| 4 | "Six seed patterns" | README:92 | VERIFIED — 6 in patterns/*.md |
| 5 | "seven edge types" | README:50,102 | VERIFIED — imports/calls/tests/assumes/diverges_from/shares_pattern/co_fixed |
| 6 | "1 skill" | README:164 | VERIFIED |
| 7 | "3 agents" | README:164 | VERIFIED — holtz.md, justine.md, merge-agent.md |
| 8 | "15 reference docs" | README:164 | **UNDERSTATED** — actual is 17 (merge-examples.md added, possibly 1 more) |
| 9 | "1 example" | README:164 | VERIFIED |
| 10 | "5 Python scripts" | README:164 | VERIFIED |
| 11 | "4 enforcement hooks" | README:164 | VERIFIED |
| 12 | "320 tests" | README:164 | VERIFIED |
| 13 | "7,800 lines" | README:164 | **UNDERSTATED** — actual is 8,494 |
| 14 | "Eleven runs" | README:134 | STALE — run 12 completed, now run 13 |
| 15 | "286 tests across 8,200 lines" | README:144 | Historical (accurate at run 11 time) — narrative context, not current claim |

## SKILL.md Claims (scoped to today's changes)

| # | Claim | Location | Status |
|---|-------|----------|--------|
| S1 | Compact pattern brief for subagent consumption | SKILL.md:182 | VERIFIED — pattern_brief_compact.py exists and works |
| S2 | Merge agent dispatch in Pre-Phase 4 | SKILL.md:211 | VERIFIED — agents/merge-agent.md exists |
| S3 | Filtered punchlist reads with --filter-status/--resolved-before/--render | SKILL.md:225-227 | VERIFIED — validate_punchlist.py CLI implements these flags |
| S4 | Post-convergence architecture baseline update subagent | SKILL.md:325-335 | VERIFIED — dispatch prompt is clear |
| S5 | README mandatory audit in Phase 1 | SKILL.md:170-171 | VERIFIED — instruction is clear |

## merge-protocol.md / merge-examples.md

| # | Claim | Location | Status |
|---|-------|----------|--------|
| M1 | "see merge-examples.md for examples" | merge-protocol.md:149-150 | VERIFIED — cross-reference works |
| M2 | merge-agent reads merge-protocol.md | merge-agent.md:10 | VERIFIED — references ${CLAUDE_PLUGIN_ROOT} path |

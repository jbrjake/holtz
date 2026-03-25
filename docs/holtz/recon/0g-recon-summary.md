# Step 0g: Recon Summary

**Project:** holtz v0.5.2
**Date:** 2026-03-24
**Run:** 16 (full audit, dev mode)

## Baseline State
- **Tests:** 613 passed, 0 failed, 0 skipped (9.27s)
- **Lint:** ruff clean, mypy clean (13 files)
- **Coverage:** 62% overall (hooks 0% due to subprocess testing)
- **CI:** Green (latest 4/5 runs pass, 1 historical failure)
- **Skipped tests:** 0 (1 conditional skip for missing profiler data)

## Architecture
Clean top-down layering. No drift since Run 15 except line shifts in convergence_check.py from bug fixes. No dependency reversals, boundary erosions, or layering breaches. 52 nodes, 52 edges in impact graph (all retained from prior run).

## Churn Profile
- **README.md** — highest churn (10/50 commits). Automated metrics test in place.
- **SKILL.md** — 5 changes. Active process evolution.
- **Token profiler** — new module (~8 source files), recently added, moderate coverage.

## Recommendation Escalation
**0 items escalated.** All prior recurring recommendations (CI, linting, coverage, shared parsing, README metrics, regex convention) have been addressed with tests and tooling.

## Global Pattern Scan
All 6 seed patterns applicable to Python. Detection heuristics ran clean:
- **code-fence-unaware-parsing:** Mitigated (mask_code_fences used correctly)
- **regex-newline-leak:** Prevented ([ \t] convention enforced by integration test)
- **doc-spec-drift:** No violations found
- **dual-parser-divergence:** No duplicate parsers
- **incomplete-layer-isolation:** N/A (no abstraction layers)
- **missing-edge-case-handling:** Properly defended (.get() usage throughout)

## Living Punchlist Items Feeding Predictions
- **PAT-001** (code-fence-unaware parsing): 4 instances in Run 15, mitigated. Watch for new markdown-processing code.
- **Subprocess coverage gap:** Hooks show 0% line coverage despite 24+ subprocess tests. Not a bug but masks coverage holes.

## Key Risk Areas
1. **README claims vs reality** — High churn, extensive claims. Test covers counts but not semantic accuracy.
2. **SKILL.md process accuracy** — 5 changes in 50 commits. Process docs may contain stale instructions, internal contradictions, or references to nonexistent files.
3. **Token profiler** — New module, less battle-tested, not yet audited by Holtz.
4. **Impact graph CLI** — 65% coverage, lowest among core scripts. Uncovered CLI paths.

# Phase 0g: Recon Summary

**Project:** holtz
**Run:** 12
**Date:** 2026-03-23

## Baseline

- 286 tests, 0 fail, 0 skip, 2.21s
- 66% coverage (hooks at 0%, scripts at 65-100%)
- Ruff clean, mypy clean
- 20 nodes, 14 edges in impact graph (no drift, no pruning)

## Key Changes Since Run 11

1. **Hook modernization (4049532):** `_common.py` rewritten to output modern JSON format. All hooks exit 0. `exit_ok()` for PreToolUse includes `hookSpecificOutput` with `permissionDecision` to avoid phantom "hook error" UI label. Old exit-code functions removed.
2. **Justine internal-only (bc165b2):** `skills/justine/` directory removed. Justine's SKILL.md and backstory moved to `skills/holtz/references/justine-skill.md` and `justine-backstory.md`. Agent definition in `agents/justine.md` updated.
3. **README updates:** Multiple doc commits — audit scope, fix loop, pattern learning sections.
4. **Version bumps:** 0.3.1 → 0.3.2 → 0.3.3

## Architecture Drift

- **Justine refactor:** `skills/justine/` directory no longer exists. Justine files now under `skills/holtz/references/`. This changes the "2 skills" architecture — now there is 1 skill directory with 2 agent definitions.
- **Reference doc count:** 16 reference files in `skills/holtz/references/` (was 14 before Justine's files moved in). README says "14 reference docs".

## Risk Areas

1. **Hook layer (0% coverage):** Tests exist (18KB test_hooks.py) but run hooks via subprocess, so pytest-cov can't track them. Hook modernization was significant — all functions rewritten. Risk of untested paths in new JSON output format.
2. **README drift:** Highest churn file (15 changes in 50 commits). Claims "14 reference docs" but actual count is 16. Claims "286 tests" — matches current count. Claims "8,200 lines" — actual is ~7,631.
3. **Hook API contract:** `exit_block()` hardcodes `hookEventName: "PreToolUse"` — but could theoretically be called from PostToolUse context. The comment says "For PreToolUse hooks only" but there's no runtime guard.

## Pattern Library Scan

- **Dual parser divergence:** convergence_check.py and validate_punchlist.py both parse punchlist format independently — known, monitored
- **Missing edge case handling:** impact_graph.py doesn't validate individual node/edge dict structure from JSON — could KeyError on malformed graph files
- **Regex newline leak:** CLEAN (all `[ \t]` convention)
- **Code fence unaware parsing:** One known bypass in subagent_findings_check.py (documented)
- **Incomplete layer isolation:** CLEAN
- **Doc-spec drift:** Constants lack anchoring documentation (minor)

## Recommendation Escalation

No recurring unresolved recommendations. All 7 multi-run recommendations from prior runs were escalated and resolved. Two single-appearance items from runs 8 and 11 to monitor.

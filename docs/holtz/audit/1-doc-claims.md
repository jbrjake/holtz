# Doc-to-Implementation Claims — Run 20

## README Claims (priority-ordered by prediction confidence)

### HIGH-confidence predicted claims (P1, P2)

| # | Claim (README) | Actual | Status |
|---|---|---|---|
| 1 | "Eighteen runs" (line 160) | 19 runs archived (Run 19 converged) | **OVERSTATED** |
| 2 | "After 18 runs: 640 tests across 13,900 lines of code" (line 190) | 641 tests, ~17,100 lines | **OVERSTATED** |
| 3 | "641 tests across 13,900 lines of code" (line 216) | 641 tests correct, 17,112 lines | **OVERSTATED** |
| 4 | Badge: "641 tests" (line 6) | 641 passed | **VERIFIED** |
| 5 | Badge: "65% coverage" (line 7) | 64.74% (rounds to 65%) | **VERIFIED** |

### MEDIUM-confidence claims

| # | Claim (README) | Actual | Status |
|---|---|---|---|
| 6 | "Sixteen seed patterns" (line 108) | 16 patterns in patterns/ | **VERIFIED** |
| 7 | "thirteen analytical lenses" (line 114) | 13 in lens-registry.md | **VERIFIED** |
| 8 | "seventeen anti-patterns" (line 50) | 17 in anti-patterns.md | **VERIFIED** |
| 9 | "Seven defined edge types" (line 66) | 7 edge types in impact_graph.py | **VERIFIED** |
| 10 | "1 skill, 3 agents, 18 reference docs, 1 example, 6 Python scripts, 16 seed patterns, 6 enforcement hooks" (line 216) | 1 SKILL.md, 3 agent files, 18 refs, 1 example, 6 scripts, 16 patterns, 6 hooks | **VERIFIED** |
| 11 | "twenty-one step audit" (line 38) | Steps 0-20 = 21 steps in SKILL.md | **VERIFIED** |
| 12 | "two consecutive passes find nothing new" (line 9, 26) | convergence_check.py requires 3 iterations (1 baseline + 2 clean) — README describes the criterion accurately (2 clean passes), implementation requires a 3rd data point as baseline | **VERIFIED** |

### Behavioral claims

| # | Claim (README) | Check | Status |
|---|---|---|---|
| 13 | "Six enforcement hooks" (line 198) | 6 .py files in hooks/ (excluding _common.py, hooks.json) | **VERIFIED** |
| 14 | "All JSON persistence uses atomic writes" (arch baseline) | save_history and ImpactGraph.save use tempfile+rename | **VERIFIED** |
| 15 | "Test runner parsers return None for unparseable output" (arch baseline) | convergence_check.py parsers return None | **VERIFIED** |
| 16 | "convergence_check.py requires exit 0 before SUMMARY.md" (SKILL.md) | convergence gate hook enforces this | **VERIFIED** |

## SKILL.md Claims

| # | Claim | Check | Status |
|---|---|---|---|
| 17 | "Read references/lens-registry.md for the full set" | 13 lenses in file, all with 4 required fields | **VERIFIED** |
| 18 | "17 anti-patterns with audit checklist" | 17 numbered patterns + checklist table | **VERIFIED** |
| 19 | "Scripts: validate_punchlist.py, convergence_check.py, impact_graph.py, pattern_brief_compact.py" | All 4 exist in skills/holtz/scripts/ | **VERIFIED** |

## Summary

- **VERIFIED:** 16
- **OVERSTATED:** 3 (claims 1, 2, 3)
- **FABRICATED:** 0
- **UNDERSTATED:** 0

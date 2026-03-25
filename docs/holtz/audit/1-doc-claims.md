# Doc-to-Implementation Claims Checklist — Run 18

## README.md

| # | Claim | Location | Status | Notes |
|---|-------|----------|--------|-------|
| 1 | 619 tests badge | L6 | VERIFIED | 619 collected |
| 2 | 62% coverage badge | L7 | VERIFIED | 62% from pytest-cov |
| 3 | "twenty-one step audit" | L38 | VERIFIED | Steps 0-20 = 21 |
| 4 | "nine analytical lenses" | L38 | VERIFIED | 9 in lens-registry.md |
| 5 | "twelve anti-patterns across three tiers" | L50 | VERIFIED | 12 in anti-patterns.md, 3 tiers |
| 6 | "Seven defined edge types" | L66 | VERIFIED | imports, calls, tests, assumes, diverges_from, shares_pattern, co_fixed |
| 7 | "the five in active use" | L66 | VERIFIED | Only 5 types have edges in graph |
| 8 | "Eight steps" for recon | L134 | **OVERSTATED** | Steps 0-4 = 5 steps. BH-001 |
| 9 | "Sixteen runs" | L160 | VERIFIED | 16 completed runs |
| 10 | "619 tests across 13,800 lines" | L190 | VERIFIED | 619 tests, 13,737 lines (within tolerance) |
| 11 | Prediction accuracy "65% HIGH, 38% MEDIUM" | L104 | VERIFIED | Matches convergence-data.md |
| 12 | "11 runs with prediction tracking" | L104 | VERIFIED | Runs 6-16 = 11 |
| 13 | "Six seed patterns" | L108 | VERIFIED | 6 files in patterns/ |
| 14 | PAT-001 "twelve times across six runs" | L102 | VERIFIED | convergence-data.md: 12 manifestations, 6 unique runs |
| 15 | "Six enforcement hooks" | L198 | VERIFIED | 6 hook .py files (excl _common.py) |
| 16 | "1 skill, 3 agents, 17 reference docs..." | L216 | VERIFIED | All counts match (integration test guards this) |
| 17 | Hook descriptions (6 hooks) | L200-210 | VERIFIED | Descriptions match actual hook behavior |

## docs/token-profiling-playbook.md

| # | Claim | Location | Status | Notes |
|---|-------|----------|--------|-------|
| 18 | "Phase 0" reference | L157 | **OVERSTATED** | Should be "Steps 0-4" or "recon". BH-002 |
| 19 | "later phases" | L161 | **OVERSTATED** | Should be "later steps". BH-002 |
| 20 | "execution phases" | L163 | **OVERSTATED** | Should be "execution steps". BH-002 |

## Summary
- 17 claims VERIFIED
- 3 claims OVERSTATED (all related to step-numbering refactor)
- 0 claims FABRICATED
- 0 claims UNDERSTATED

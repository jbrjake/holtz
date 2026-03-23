# Holtz Summary

**Project:** holtz
**Run:** Full audit, run 7
**Date:** 2026-03-22
**Duration:** Phases 0-6 complete

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 232 | 235 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 0.37s | 0.58s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Coverage | — | 77% |
| Punchlist items | — | 2 |
| Resolved | — | 2 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 3

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 2 | BH-001, BH-002 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| design/inconsistency | 2 | BH-001, BH-002 |

## Key Fixes

1. **BH-001 (MEDIUM):** Added pytest-cov configuration to pyproject.toml. Coverage report now runs automatically with every `pytest` invocation, showing per-file line coverage. Results: markdown_utils 100%, validate_punchlist 83%, convergence_check 80%, impact_graph 64%, overall 77%.

2. **BH-002 (MEDIUM):** Added `make_item` fixture to `tests/conftest.py` — a builder that generates valid punchlist item markdown with keyword overrides for all fields. Three tests demonstrate usage: default validation, severity override, empty problem. Existing inline-markdown tests preserved for readability.

## Coverage Report

| Module | Stmts | Miss | Cover |
|--------|-------|------|-------|
| markdown_utils.py | 46 | 0 | 100% |
| validate_punchlist.py | 256 | 44 | 83% |
| convergence_check.py | 223 | 44 | 80% |
| impact_graph.py | 272 | 97 | 64% |
| **Total** | **797** | **185** | **77%** |

Uncovered lines are primarily CLI `main()` functions (which are exercised via subprocess in integration tests but not measured by in-process coverage) and the argparse CLI builder in impact_graph.py.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 2         | 67%      |
| MEDIUM     | 4         | 0         | 0%       |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **8**     | **2**     | **25%**  |

- Prediction 1 (HIGH, README doc-spec drift): UNCONFIRMED — 63 doc claims verified, all TRUE
- Prediction 2 (MEDIUM, dual parser divergence): UNCONFIRMED — parsers still aligned
- Prediction 3 (MEDIUM, impact_graph edge cases): UNCONFIRMED — well handled
- Prediction 4 (MEDIUM, SKILL.md drift): UNCONFIRMED — spec matches code
- Prediction 5 (MEDIUM, test_integration shallow): UNCONFIRMED — tests are well-designed
- Prediction 6 (LOW, runner parser bugs): UNCONFIRMED — all 7 parsers robust
- Prediction 7 (HIGH, coverage reporting escalation): CONFIRMED → BH-001
- Prediction 8 (HIGH, test boilerplate escalation): CONFIRMED → BH-002

Only recommendation escalation predictions confirmed. All code-level predictions unconfirmed — the codebase has been effectively hardened by 6 prior runs.

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 1 | 12 | 2 HIGH, 6 MEDIUM, 4 LOW | PAT-001: code-fence-unaware parsing | 48 |
| 2 | 5 | 2 MEDIUM, 3 LOW | PAT-002: incomplete code-fence isolation | 10 |
| 3 | 3 | 3 LOW | None (all distinct) | 2 |
| 4 | 4 | 2 MEDIUM, 2 LOW | PAT-001: structural-awareness divergence | 4 |
| 5 | 9 | 3 MEDIUM, 6 LOW | None | 2 |
| 6 | 8 | 1 MEDIUM, 7 LOW | PAT-001: duplicated fence-parsing logic | 6 |
| 7 | 2 | 2 MEDIUM | None (escalated recommendations only) | 3 |

Run 7 represents true convergence. For the first time in 7 runs:
- Zero code bugs found (all findings were process/tooling recommendations)
- Zero code patterns identified
- All 6 analytical lenses swept clean
- Every code-level prediction unconfirmed

The trajectory from run 1 (12 findings, 2 HIGH) to run 7 (2 findings, both MEDIUM tooling items) shows a codebase that has been systematically hardened to the point where the auditor cannot find anything wrong with it.

## Recommendations

1. **Impact graph coverage** — `impact_graph.py` has the lowest coverage at 64%, mostly due to CLI code. If the CLI entry points matter, consider adding subprocess-based CLI tests that get measured by coverage (or accept 64% as the baseline for a CLI wrapper).

2. **CI configuration** — No CI/CD is configured. GitHub Actions with `ruff check . && mypy scripts/ && pytest` would prevent regressions on push. This appeared in run 6 but only once, so it wasn't escalated.

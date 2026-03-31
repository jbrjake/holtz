# Holtz Run 19 Summary

**Project:** holtz
**Date:** 2026-03-25
**Mode:** Full audit with adversarial self-play, dev mode (local SKILL.md)
**Version:** 0.26.0

## Results

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 640 | 641 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Coverage | 65% | 65% |
| Punchlist items | 0 | 11 (all resolved) |
| Patterns identified | 1 (PAT-005) | |
| Convergence iterations | 3 | |
| Cold file ratio | 48% | 0% |

## Findings

11 items found and resolved:

### HIGH (2)
- **BH-001:** README seed pattern count stale — "Fourteen" → "Sixteen" (2 new patterns added)
- **BH-002:** README lens count inconsistency — "nine" in 2 places vs "thirteen" in 1 (4 new lenses added)

### MEDIUM (5)
- **BH-003:** README anti-pattern count stale — "twelve" → "seventeen" (5 new anti-patterns added)
- **BH-004:** README run counts stale — "Sixteen runs" → "Eighteen runs" + test/line count updates
- **BH-005:** Recommendation escalation — README semantic claim test coverage gap (from Runs 13+16). Resolved with new `test_readme_prose_counts_match_actual`
- **BH-006:** token_profiler `--pricing` CLI flag is a silent no-op — loads JSON then discards it. Added warning message
- **BH-007:** extract.py `json.loads` without error context at JSONL data boundary. Added file path + line number in error

### LOW (4)
- **BH-008:** artifact_verification.py PAT-003 — `\s` instead of `[ \t]` in regex. Fixed
- **BH-009:** analyze.py `_parse_iso` without error context for timestamps. Added try/except with milestone/turn context
- **BH-010:** Permissive `> 0` assertions in test_token_profiler_analyze where exact values are computable. Tightened
- **BH-011:** Rubber stamp section-heading-only assertions in test_token_profiler_report. Added content assertions

## New Pattern: PAT-005 (README-count-drift)

**Instances:** BH-001, BH-002, BH-003, BH-004
**Root Cause:** README contains hardcoded counts (patterns, lenses, anti-patterns, runs) that must be manually updated when files are added. No test covered all prose count mentions until this run.
**Systemic Fix:** Added `test_readme_prose_counts_match_actual` to catch lens count and anti-pattern count drift in README prose. Combined with existing `test_readme_metrics_match_actual`, all major README counts are now covered by CI.
**Detection Rule:** `grep -nE "(fourteen|Fourteen|sixteen|Sixteen|nine |twelve|Twelve|seventeen) " README.md`

## Cold File Audit

This was the first run to systematically audit cold files (never-before-audited source). 11 of 23 source files (48%) had never appeared in any punchlist finding across 18 prior runs. The entire `scripts/token_profiler/` subtree (10 files) plus `profiler_plugin.py` were cold.

Cold file audit yielded 4 findings (BH-006, BH-007, BH-008, BH-009). All were in token_profiler code or hooks. Previously-audited modules were clean — consistent with 18 prior passes.

**Key insight:** Cold file audit is the most productive use of effort on a mature codebase. The 11 cold files yielded 4 findings that 18 prior runs missed.

## Adversarial Self-Play Analysis

| Found By | Count | Items |
|----------|-------|-------|
| Both auditors | 4 | BH-001, BH-002, BH-003, BH-004 |
| Holtz only | 5 | BH-005, BH-006, BH-007, BH-008, BH-009 |
| Justine only | 2 | BH-010, BH-011 |

**Key insight:** All 4 agreements were README count drifts — the most obvious findings. Holtz's depth-first approach caught the code-level issues in cold files (pricing no-op, error handling, PAT-003). Justine's breadth-first scan caught test quality issues in the same cold files (permissive assertions, rubber stamps). Different methodologies, different categories, same files. This is the value of adversarial self-play: the overlap is small, the union is large.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 2         | 100%     |
| MEDIUM     | 7         | 6         | 86%      |
| LOW        | 1         | 1         | 100%     |
| **Total**  | **10**    | **9**     | **90%**  |

Best prediction accuracy across all runs. Contributing factors:
- HIGH predictions based on failing tests and direct observation remain 100% reliable
- MEDIUM predictions benefited from cold file sweep — cold files with unknown risk at MEDIUM confidence confirmed at 86%
- The one unconfirmed MEDIUM prediction (profiler_plugin.py) targeted the wrong file — the findings were in other token_profiler modules
- Cold file ratio > 40% triggered the cold file prediction requirement, which proved highly productive

## Recommendations

1. **Automate README count maintenance.** PAT-005 has appeared in Runs 13, 14, 16, 18, and 19. The new integration tests will catch it in CI, but a pre-commit hook or generation script would prevent the drift entirely. Consider a test that parses README for number-word patterns and validates them against file counts.

2. **Integrate token_profiler pricing module.** The `--pricing` flag (BH-006) is accepted but ignored. Either integrate the pricing pipeline or remove the flag to avoid confusing users.

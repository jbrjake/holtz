# Holtz Run 15 Summary

**Project:** holtz
**Date:** 2026-03-24
**Mode:** Full audit, dev mode (using local SKILL.md)
**Convergence:** Achieved after 3 iterations

## Metrics

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 595 | 613 |
| Tests failing | 9 | 0 |
| Tests skipped | 0 | 0 |
| Lint errors | 0 | 0 |
| Type errors | 0 | 0 |

## Findings

| Severity | Found | Resolved | Deferred |
|----------|-------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 4 | 4 | 0 |
| MEDIUM | 4 | 4 | 0 |
| LOW | 1 | 1 | 0 |
| **Total** | **9** | **9** | **0** |

### HIGH Items
- **BH-001:** test_commit_msg_hook.py references deleted git-hooks/commit-msg (test/bogus)
- **BH-007:** convergence_check.py CLI silently accepts nonexistent punchlist paths (bug/logic)
- **BH-008:** SKILL.md lacks convergence verification gate (design/inconsistency)
- **BH-009:** SKILL.md does not specify exact convergence_check.py invocation (doc/drift)

### MEDIUM Items
- **BH-002:** No test for REGRESSING label in stall detection (test/missing)
- **BH-003:** convergence_gate.py parses STATUS.md without masking code fences (design/inconsistency, PAT-001)
- **BH-004:** convergence_primer.py parses STATUS.md without masking code fences (design/inconsistency, PAT-001)
- **BH-005:** Convergence hook tests lack code-fence adversarial fixtures (test/shallow, PAT-001)

### LOW Items
- **BH-006:** _count_open_items informational count inflated by code fences (design/inconsistency, PAT-001)

## Patterns

- **PAT-001:** code-fence-unaware parsing — 4 instances this run (BH-003/004/005/006). Fifth manifestation across 15 runs. Same root cause family, different layer each time. Added mask_fenced_blocks() to hooks/_common.py.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 1         | 33%      |
| MEDIUM     | 3         | 0         | 0%       |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **7**     | **1**     | **14%**  |

Notable: MEDIUM predictions 4-6 were directionally correct (pointed to the right code and pattern) but classified as UNCONFIRMED because the actual findings were design/inconsistency rather than bug/logic. The prediction system correctly identified WHERE bugs would be but overestimated severity.

## Adversarial Self-Play

Justine was dispatched after Phase 0 and completed her audit in parallel. Merge results:
- 6 unique findings merged from both auditors
- 1 false positive from Justine (rejected during merge)
- No contradictions between auditors
- Justine's breadth-first approach found the same PAT-001 pattern instances that Holtz found via depth-first analysis

## Process Notes

This run exposed a process gap: the convergence checker itself had a silent data integrity bug (BH-007) and the SKILL.md lacked enforcement language for convergence verification (BH-008). The auditor declared convergence after iteration 1, wrote SUMMARY.md prematurely, and the convergence gate allowed the stop because it trusted SUMMARY.md existence. Fixed by adding explicit exit-code requirements to SKILL.md and a rationalization red flag. History was reset and convergence restarted properly.

## Recommendations

1. **Consider subprocess coverage tracking.** Hooks tested via subprocess show 0% in pytest-cov. A coverage plugin or separate coverage run for subprocess-tested code would give accurate metrics.
2. **Pattern-matching predictions need severity calibration.** PAT-001 predictions correctly identified the code but overestimated severity. Consider a "directional" prediction category that credits location accuracy separately from severity accuracy.
3. **Architecture baseline maintenance.** The baseline drift log was not updated during this run's Phase 0. Automate drift detection or add a Phase 0 verification step.

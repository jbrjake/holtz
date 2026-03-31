# Holtz Run 16 Summary

**Project:** holtz
**Date:** 2026-03-24
**Mode:** Full audit, dev mode (using local SKILL.md)
**Convergence:** Achieved after 3 iterations

## Metrics

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 613 | 617 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Lint errors | 0 | 0 |
| Type errors | 0 | 0 |

## Findings

| Severity | Found | Resolved | Deferred |
|----------|-------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 1 | 1 | 0 |
| MEDIUM | 2 | 2 | 0 |
| LOW | 1 | 1 | 0 |
| **Total** | **4** | **4** | **0** |

### HIGH Items
- **BH-001:** README overstates prediction accuracy as 100%/100%/0% (doc/drift). Actual: HIGH ~72%, MEDIUM ~38%. Fixed.

### MEDIUM Items
- **BH-003:** parse_brief uses masked offsets to index original content (bug/logic, PAT-001). Code fences before pattern entries corrupt field extraction. Fixed with line-number mapping.
- **BH-004:** hooks mask_fenced_blocks ignores fence character count (design/inconsistency, PAT-001). 4-backtick fence prematurely closed by 3 backticks. Fixed to track count.

### LOW Items
- **BH-002:** README says "Fourteen runs" but fifteen have completed (doc/drift). Added Run 15 narrative.

## Patterns

- **PAT-001:** code-fence-unaware parsing — 2 instances this run (BH-003, BH-004). Seventh and eighth manifestations across 16 runs. BH-003 is the offset-divergence variant (masked offsets indexing original content). BH-004 is the fence-grammar variant (closing fence length not enforced). Same root cause family, different layer each time.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 1         | 50%      |
| MEDIUM     | 3         | 1         | 33%      |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **6**     | **2**     | **33%**  |

- Prediction 1 (HIGH, README claims): CONFIRMED — BH-001 (overstated accuracy), BH-002 (stale run count)
- Prediction 2 (HIGH, SKILL.md dev-mode refs): UNCONFIRMED — design intent, not drift
- Prediction 3 (MEDIUM, token profiler): UNCONFIRMED — no bugs found, tests solid
- Prediction 4 (MEDIUM, hooks edge cases): CONFIRMED — BH-004 (fence length)
- Prediction 5 (MEDIUM, impact_graph CLI): UNCONFIRMED — no bugs in CLI paths
- Prediction 6 (LOW, lens count): UNCONFIRMED — 9 lenses, README accurate

## Adversarial Self-Play

Justine was dispatched after Phase 0 and completed her audit in parallel. Merge results:
- 4 items total in merged worklist
- 2 agreements (BH-003/BJ-001, BH-004/BJ-002) — both auditors found same code bugs independently
- 2 Holtz-only (BH-001, BH-002) — README doc drift items Justine didn't flag
- 0 Justine-only, 0 contradictions

Both auditors converged on the PAT-001 findings independently. Justine rated them HIGH; Holtz rated MEDIUM.

## Process Notes

This run was cleaner than Run 15. The codebase is well-hardened after 15 prior runs. Finding surface has narrowed to:
1. README doc drift (claims vs reality)
2. PAT-001 code-fence-unaware parsing (keeps recurring in new code/edge cases)

Both patterns are now well-defended: README has integration tests for counts, and all three fence-masking implementations (markdown_utils, _common, pattern_brief_compact) now properly handle fence grammar. The offset-divergence variant in pattern_brief_compact was the same class of bug fixed in Run 13 (render_items) — line-number mapping is the correct approach.

## Recommendations

1. **Consolidate fence masking implementations.** Three independent implementations (markdown_utils.py, _common.py, pattern_brief_compact.py) each failed at different times. Consider a shared, well-tested CommonMark fence state machine that all layers can use without cross-layer imports — perhaps a standalone module that both hooks and scripts can import.
2. **Add README semantic claim test.** The integration test validates component counts but not descriptive claims (prediction accuracy, run descriptions). Consider a test that validates key README factual claims against data.

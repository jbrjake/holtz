# Holtz Run 18 Summary

**Project:** holtz
**Date:** 2026-03-25
**Mode:** Full audit with adversarial self-play, dev mode (local SKILL.md)
**Version:** 0.16.1 → 0.16.3

## Results

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 619 | 640 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Coverage | 62% | 65% |
| Punchlist items | 0 | 7 (all resolved) |
| Patterns identified | 1 (PAT-004) | |
| Convergence iterations | 3 | |
| Commits | 2 | |

## Findings

7 items found and resolved across 2 commits:

### HIGH (3)
- **BH-001:** README "Eight steps" recon claim stale after step-numbering refactor → fixed to "Five steps"
- **BH-003:** `_common.py mask_fenced_blocks` ignores 1-3 space indented fences (PAT-004) → added CommonMark-compliant indentation handling
- **BH-004:** `_common.py mask_fenced_blocks` accepts backticks in backtick fence info strings (PAT-004) → added `[^`]*$` constraint per CommonMark spec

### MEDIUM (3)
- **BH-002:** Token profiling playbook has 3 stale "Phase" references → updated to "Steps"/"steps"
- **BH-005:** `convergence_gate._count_open_items` counts Status fields outside item blocks → scoped to `### BH-NNN:` headers
- (BH-001 severity disagreement: Holtz=HIGH, Justine=MEDIUM, merged at HIGH)

### LOW (1)
- **BH-006:** `convergence_check.py` output messages use "phases" → "steps"

## New Pattern: PAT-004 (Dual-Implementation Divergence)

**Instances:** BH-003, BH-004
**Root Cause:** `hooks/_common.py` reimplements `markdown_utils.py` fence masking with a simpler algorithm that omits CommonMark edge cases (indented fences, backtick info string restrictions). The two implementations diverge on inputs valid per CommonMark but not handled by the simpler version.
**Systemic Fix:** Added 21-case cross-implementation test (`test_fence_masking_agreement.py`) that verifies both maskers agree on fence boundary detection. This prevents future divergence.
**Detection Rule:** `grep -rn "def mask_" skills/holtz/scripts/ hooks/`

## Adversarial Self-Play Analysis

| Found By | Count | Items |
|----------|-------|-------|
| Both auditors | 2 | BH-001, BH-002 |
| Holtz only | 1 | BH-006 |
| Justine only | 4 | BH-003, BH-004, BH-005, BH-007 |

**Key insight:** Justine's breadth-first integration lens caught the dual-masker divergence (BH-003, BH-004) by directly comparing the two implementations side-by-side. Holtz's depth-first approach reviewed each file in isolation and missed the cross-module contract violation. This is the same blind-spot pattern as Run 11 (regex convention violations) — aggregate bugs invisible in isolation.

Holtz's depth-first approach caught BH-006 (stale "phases" in convergence_check output) by tracing commit history to verify the step-numbering update was complete. Justine missed this because she didn't independently scan scripts/ beyond the prediction targets.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 2         | 100%     |
| MEDIUM     | 3         | 0         | 0%       |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **6**     | **2**     | **33%**  |

HIGH predictions (README stale count, playbook stale Phase refs) both confirmed — direct observation during recon is the most reliable prediction source. MEDIUM predictions (SKILL.md/reference doc Phase refs) were correctly targeted but the refactor was thorough in those files — no findings. LOW prediction (convergence-data.md historical Phase refs) correctly identified as not warranting a finding.

## Recommendations

1. **Add PAT-004 to proactive checks.** The dual-masker divergence survived 18 runs. The cross-implementation test now guards against it, but any new masking implementation should be tested against the shared corpus.
2. **Consider convergence_gate _count_open_items regression test.** The BH-005 fix scoped counting to item blocks, but no hook test directly exercises this scoping logic with Pattern-block Status fields.

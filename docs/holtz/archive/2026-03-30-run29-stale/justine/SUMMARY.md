# Justine Audit Summary

**Project:** holtz v0.72.7
**Run:** 28
**Date:** 2026-03-29
**Auditor:** Justine (breadth-first adversarial)

## Totals

| Metric | Value |
|--------|-------|
| Findings total | 5 |
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 2 |
| LOW | 1 |
| Open | 5 |
| Resolved | 0 |
| Deferred | 0 |
| Tests at start | 856 |
| Tests at end | 856 |
| Coverage at start | 80% |
| Source files scanned | 21/21 |
| Cold files scanned | 2/2 |

## Finding Summary

### HIGH (2)
- **BJ-001:** README coverage badge stale -- claims 76% but actual is 80% (79.94%). Badge has drifted by 4 percentage points.
- **BJ-002:** README test badge says "857 passed" but only 856 pass (1 is skipped). Same stale count appears in 3 README locations.

### MEDIUM (2)
- **BJ-003:** test_lists_sessions in test_token_profiler_cli.py is a Rubber Stamp (anti-pattern #11). Checks 6 keys exist in dict entries but never verifies any values. Would pass with garbage data.
- **BJ-004:** commit_gate._is_test_cmd recognizes only pytest/python-m-pytest, while protocol_tracker._is_tdd_cmd also recognizes ruff/mypy. When stall threshold fires, ruff and mypy commands get blocked despite being legitimate TDD activity.

### LOW (1)
- **BJ-005:** _sahjhan_bootstrap._check_bash_write misses subshell write vectors (bash -c wrapping). Defense-in-depth via bash_guard PostToolUse covers the gap, so impact is theoretical.

## Key Observations

1. **README doc-spec drift is the recurring pattern.** This is the same finding class from runs 14, 16, 27, and now 28. The badge values are manually maintained and drift after every run that changes test count or coverage. Recommendation: automate badge value extraction from CI output, or accept that badges are always slightly stale and document the policy.

2. **Enforcement layer is architecturally sound.** All 13 enforcement Python files and 4 enforcement scripts were scanned. The HMAC auth, manifest verification, quiz gating, and protocol cache mechanisms are well-implemented and well-tested. The _is_test_cmd vs _is_tdd_cmd inconsistency (BJ-004) is the only integration seam issue found.

3. **Test suite quality is high.** Out of 856 tests across 33 test files, only 1 rubber stamp was found (BJ-003). The cross-implementation fence masking tests (test_fence_masking_agreement.py) are a model of good integration testing. The enforcement config tests check actual field values, not just structure.

4. **Cold file ratio dropped to 0%.** Both previously cold files (_resolve.py and profiler_plugin.py) were scanned this run. No issues found in either.

5. **Dual fence masking divergence is a non-issue.** Prediction P3 was unconfirmed because the divergence (opener/closer handling) is intentional, documented, and thoroughly tested by a dedicated cross-implementation test suite with 21 test cases.

## Recommendations

1. **Automate README badge updates** -- either via CI post-step that updates badge values, or by switching to dynamic badges that read from CI artifacts. This would eliminate the recurring doc-spec drift finding class that has appeared in 4+ runs.

2. **Unify _is_test_cmd and _is_tdd_cmd** -- extract a shared `is_tdd_command()` function in `_protocol_cache.py` that both commit_gate and protocol_tracker import. This eliminates the integration seam where definitions can drift independently.

3. **Consider strengthening test_lists_sessions** -- add value assertions (path contains filename, size_kb > 0, turns is int) alongside the existing key-existence checks.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 4         | 3         | 75%      |
| MEDIUM     | 4         | 0.5       | 12%      |
| LOW        | 0         | 0         | N/A      |
| **Total**  | **8**     | **3.5**   | **44%**  |

Notes: P5 counted as 0.5 (partially confirmed at lower severity). HIGH confidence predictions performed well (75%) -- the README drift predictions were correct, and the rubber stamp prediction confirmed. MEDIUM predictions were directionally useful (P5 pointed to the right code area) but mostly unconfirmed because the codebase has been heavily self-audited and the predicted issues had already been addressed or were by design.

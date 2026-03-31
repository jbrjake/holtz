# Justine Audit Summary -- Run 29

**Project:** holtz v0.72.19
**Branch:** dev
**Date:** 2026-03-30
**Mode:** Standalone breadth-first audit

## Results

| Metric | Value |
|--------|-------|
| Total findings | 8 |
| Open | 8 |
| Resolved | 0 |
| Deferred | 0 |
| Patterns discovered | 1 |
| Cold files audited | 10 of 16 |
| Impact graph nodes | 62 (+5) |
| Impact graph edges | 56 (+3) |

### Severity Breakdown

| Severity | Count |
|----------|-------|
| HIGH | 3 |
| MEDIUM | 4 |
| LOW | 1 |

### Findings by Category

| Category | Count |
|----------|-------|
| bug/logic | 2 |
| design/duplication | 2 |
| doc/drift | 1 |
| test/missing | 1 |
| bug/error-handling | 1 |
| test/bogus | 1 |

## Key Findings

### HIGH severity

1. **BJ-001:** README badge shows "869 total" tests but actual count is 874. Badge URL stale; alt text correct. PAT-005 recurrence.

2. **BJ-002:** stop_gate hard-codes an allow-list of 3 non-terminal states (awaiting_clear, idle, recon) against a state machine with 14 states. The `converged` state -- which is reachable via confirm_convergence -- is not in the allow-list, trapping operators who reach convergence but haven't completed finalization (which requires 3 additional events).

3. **BJ-003:** `test_readme_metrics_match_actual` checks body text counts but not the shields.io badge URLs. The badge is the most visible metric element and the one that drifts most often. The test has a blind spot for the most prominent metric display.

### MEDIUM severity

4. **BJ-004:** `_get_session_key_path` uses `except Exception: pass` which swallows programming bugs, converting them into misleading downstream FileNotFoundError.

5. **BJ-005:** `_sahjhan_bootstrap.py._platform_triple()` duplicates the platform triple logic from `_resolve.py.sahjhan_binary()`. Two independent copies must stay in sync.

6. **BJ-006:** `pricing.py` has two copies of longest-prefix model name matching logic (`get_pricing` and `_custom_pricing`).

7. **BJ-008:** `validate_merge_report.py` is a Permissive Validator (anti-pattern #12) -- checks section headers exist but not that they contain content. A headers-only merge report passes validation.

### LOW severity

8. **BJ-007:** `is_git_commit` returns False for `VAR=x git commit -m test` because env-prefix commands don't start with `git`.

## Patterns

### PAT-008: incremental-allow-list
**Instances:** BJ-002, BJ-007
**Root Cause:** Allow-lists built by successive fix commits (adding one entry at a time) rather than derived from a data source or principled rule. Each fix addresses the immediate symptom without considering the full set.
**Systemic Fix:** Derive allow-lists from the data source (e.g., states.toml for stop_gate) or use a deny-list approach (block known-dangerous states instead of allowing known-safe ones).
**Detection Rule:** grep for hard-coded lists that correspond to values defined in configuration files.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 2         | 100%     |
| MEDIUM     | 3         | 1         | 33%      |
| LOW        | 3         | 0         | 0%       |
| **Total**  | **8**     | **3**     | **38%**  |

HIGH predictions performed at 100% -- both were direct observations backed by strong signals (PAT-005 recurrence for P-001, consecutive-fix pattern for P-002). MEDIUM predictions hit 33% -- P-005 (pricing duplication) confirmed; P-003 (is_sahjhan_cmd edge cases) and P-004 (dual fence masking gap) unconfirmed because the code handles the predicted edge cases correctly and the equivalence test exists. LOW predictions at 0% -- all theoretical concerns that the code handles acceptably.

## Recommendations

### This Run (address before next audit)

1. **Fix BJ-001 + BJ-003 together:** Update README badge AND add a test that verifies badge URLs match actual counts. This is the same class as PAT-005 and will recur without CI enforcement.

2. **Fix BJ-002:** Either derive the stop_gate allow-list from states.toml programmatically, or explicitly document which non-terminal states should block exit and why. At minimum, add `converged` to the allow-list.

3. **Fix BJ-004:** Narrow the exception handler in `_get_session_key_path` to specific exception types.

### Future Runs

4. **BJ-005 + BJ-006 (duplication):** Extract shared platform triple helper. Extract shared pricing lookup helper. Both are design improvements, not bugs.

5. **BJ-008 (Permissive Validator):** Add content checks to merge report validation. At least verify one section has non-whitespace content below its header.

6. **Living Punchlist stale entry:** The "No equivalence test for dual fence-masking implementations" entry in LIVING-PUNCHLIST.md is stale -- `tests/test_fence_masking_agreement.py` was added in Run 18 with 20+ test cases. Update the Living Punchlist to reflect this.

## Test Health

- 873 passed, 1 skipped, 0 failed
- 79.94% coverage (gate at 60%)
- Ruff: clean
- mypy: clean
- No Green Bar Addict tests found
- No Rubber Stamp tests found (type-only assertions are supplemented with value checks)
- 1 Permissive Validator found in enforcement (BJ-008: validate_merge_report.py)
- 6 conditional skips are all runtime guards on live data availability (acceptable)

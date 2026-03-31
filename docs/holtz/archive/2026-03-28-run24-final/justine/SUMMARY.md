# Justine Audit Summary -- Run 25

**Project:** holtz
**Date:** 2026-03-28
**Auditor:** Justine (breadth-first, adversarial)
**Mode:** Parallel dispatch with Holtz (inherited recon)

## Results

| Severity | Open | Resolved | Deferred | Total |
|----------|------|----------|----------|-------|
| HIGH     | 2    | 0        | 0        | 2     |
| MEDIUM   | 2    | 0        | 0        | 2     |
| LOW      | 3    | 0        | 0        | 3     |
| **Total**| **7**| **0**    | **0**    | **7** |

## Findings Summary

### HIGH Severity (2)

1. **BJ-001:** README numeric claims stale -- LOC count 24% below actual (17,469 claimed vs 21,630 actual), run count off by 1 (24 vs 25), anti-pattern count wrong (17 claimed vs 12 actual). PAT-005 instance, 7th+ consecutive run.

2. **BJ-002:** 6 test methods in test_sahjhan_integration.py and test_protocol_enforcement.py use source-code string matching instead of behavioral testing (Inspector Clouseau #4 + Rubber Stamp #11). Tests read .py source files and assert substring presence. These tests would pass if the asserted strings appeared in comments or dead code. Run 24 BJ-006 flagged 4 of these; the finding persists with 2 additional instances found.

### MEDIUM Severity (2)

3. **BJ-003:** primer.py uses `status.get("run_number", "?")` (line 96) to extract run number from sahjhan status JSON, but lens_quiz.py uses `status.get("run", "0")` (line 209). Cross-hook field name mismatch. If sahjhan's JSON uses "run" (as lens_quiz.py assumes), primer.py's resume context displays "Run ?" instead of the actual run number.

4. **BJ-004:** Quiz bank validator (`generate_quiz_bank.py`) does not check for empty option strings. A quiz entry with `"opts": ["", "foo", "bar", "baz"]` passes validation but causes `verify_answer_freshness` to silently mark the question as stale (empty answer text produces empty answer_parts, returns False). Verified: empty option passes validation.

### LOW Severity (3)

5. **BJ-005:** `_sahjhan_bootstrap.py` Bash redirect detection is substring-based (defense-in-depth limitation). `p in command and any(op in command for op in (">", ">>", "tee "))` produces false positives when protected path names appear in non-path positions. Same as run 24 BJ-007.

6. **BJ-006:** `_protocol_cache.py` `_read_perspectives_total()` uses a hand-rolled line-by-line TOML parser instead of `tomllib`. Currently returns correct count (13, matching `tomllib` parse) but would break if protocol.toml switches to inline arrays or if a `values` key appears in another section first.

7. **BJ-007:** `lens_quiz.py` computes and records a `questions_hash` when posing a quiz but never verifies this hash when scoring answers. If the quiz bank changes between posing and answering, the student may be scored against different questions than they saw.

## Patterns Identified

No new patterns identified. BJ-001 is a recurring instance of PAT-005 (doc-spec-drift). BJ-002 is a recurring instance of Inspector Clouseau + Rubber Stamp anti-patterns (same as run 24 BJ-006, not resolved).

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 4         | 4         | 100%     |
| MEDIUM     | 3         | 2         | 67%      |
| LOW        | 1         | 1         | 100%     |
| **Total**  | **8**     | **7**     | **88%**  |

### Prediction Details

- **P1 (HIGH):** README count drift PAT-005 -- CONFIRMED (BJ-001). LOC 24% drift, run count +1, anti-pattern count wrong.
- **P2 (HIGH):** Source-code string-matching tests -- CONFIRMED (BJ-002). 6 methods found (5 in test_sahjhan_integration.py, 1 in test_protocol_enforcement.py).
- **P3 (HIGH):** Empty quiz options pass validation -- CONFIRMED (BJ-004). Verified programmatically.
- **P4 (HIGH):** primer.py run_number field mismatch -- CONFIRMED (BJ-003). Uses "run_number" vs "run" across hooks.
- **P5 (MEDIUM):** Bootstrap redirect false positives -- CONFIRMED (BJ-005). Same as run 24 BJ-007.
- **P6 (MEDIUM):** Quiz scoring mismatch error message -- UNCONFIRMED. Behavior is defensive (blocks correctly). Not a finding.
- **P7 (MEDIUM):** TOML parser fragility -- CONFIRMED (BJ-006). Parser correct today but structurally fragile. Downgraded to LOW.
- **P8 (LOW):** Quiz hash not verified -- CONFIRMED (BJ-007). Hash recorded but never compared during scoring.

### Calibration Notes

- HIGH predictions at 100% for the fourth consecutive Justine run. Direct code observation remains the most reliable prediction signal.
- MEDIUM predictions at 67% (2/3). P6 was a false positive -- defensive behavior that blocks correctly despite a misleading error message is not a finding. The UX issue is minor and the security posture is correct.
- LOW predictions at 100% (1/1). Better than historical baseline (0% in run 24). The quiz hash verification issue is a real design gap, just low severity.

## Convergence

- **Iterations:** 1 (single-pass convergence)
- **Areas examined:** All enforcement hooks (13 files), all legacy hooks (2 files), all scripts (6 files), profiler plugin (1 file), markdown utils (1 file), all test files audited for anti-patterns (12 files), README.md, enforcement TOML configs, quiz bank
- **Lenses applied:** integration, security, data-flow, error-propagation, contract, component (all 6 core lenses)
- **Circuit breakers:** None triggered

## Recommendations

1. **Fix primer.py run_number field name** -- change `status.get("run_number", "?")` to `status.get("run", "?")` to match the field name used by lens_quiz.py and the likely sahjhan status JSON schema. This is a one-line fix.

2. **Replace source-code string-matching tests with behavioral tests** -- the 6 tests that read source files and assert substring presence should be replaced with tests that invoke the actual hooks and verify behavioral outcomes. This is the second consecutive run flagging this issue. The tests provide false security -- they confirm code structure, not behavior.

3. **Update README numeric claims** -- LOC count, run count, and anti-pattern count are all stale. This is the 7th+ consecutive run flagging PAT-005. The escalated recommendation for automated count maintenance from run 20 remains unaddressed.

4. **Add empty-option validation to quiz bank** -- `validate_quiz_bank` should reject entries with empty or whitespace-only option strings. One-line addition: `if not all(opt.strip() for opt in entry["opts"]):`.

5. **Consider replacing hand-rolled TOML parser** -- `_read_perspectives_total()` currently works but is structurally fragile. Python 3.11+ includes `tomllib` in stdlib. Since the project targets Python 3.12+, this is a free upgrade.

## Metrics

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 759 | 759 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Coverage | 76% | 76% |
| Punchlist items | 0 | 7 |
| Convergence iterations | -- | 1 |

## Files Written

- `docs/holtz/justine/STATUS.md`
- `docs/holtz/justine/PUNCHLIST.md`
- `docs/holtz/justine/SUMMARY.md`
- `docs/holtz/justine/recon/0g-recon-summary.md`
- `docs/holtz/justine/recon/0h-predictions.md`
- `docs/holtz/justine/impact-graph.json`

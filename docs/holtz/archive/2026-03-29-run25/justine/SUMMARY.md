# Justine Audit Summary -- Run 25

**Project:** holtz v0.57.9
**Date:** 2026-03-28
**Auditor:** Justine (breadth-first, adversarial)
**Mode:** Parallel dispatch with Holtz (inherited recon)

## Results

| Severity | Open | Resolved | Deferred | Total |
|----------|------|----------|----------|-------|
| HIGH     | 3    | 0        | 0        | 3     |
| MEDIUM   | 3    | 0        | 0        | 3     |
| LOW      | 1    | 0        | 0        | 1     |
| **Total**| **7**| **0**    | **0**    | **7** |

## Findings Summary

### HIGH Severity (3)

1. **BJ-001:** `test_readme_metrics_match_actual` crashes because `pytest --co -q` output format changed. The test parses the last line with `re.search(r"(\d+) test", ...)` but `-q` mode shows per-file counts, not a summary "N tests collected" line. The regex returns None and `.group(1)` raises AttributeError. Deterministic failure.

2. **BJ-002:** Two `TestStopGate` tests (`test_allows_without_sahjhan_binary`, `test_allows_without_active_run`) leak live session state. They pass empty events to `stop_gate.py` which defaults to `os.getcwd()`, finds the active Sahjhan audit state, and blocks. Tests fail whenever a Sahjhan audit is active -- which is always during Holtz runs.

3. **BJ-003:** README "What's inside" counts stale (PAT-005, 8th+ consecutive run). Badge says 759 tests (actual: 761), line 190 says 21,120 LOC (actual: 17,577 in counted dirs), "After 25 runs" (actual: 24 archived). The LOC discrepancy of 3,543 lines suggests different counting methodologies between the README and the test.

### MEDIUM Severity (3)

4. **BJ-004:** CI persistent failure on `TestBootstrapHook::test_blocks_binary_modification` for 3+ consecutive runs. Passes locally on macOS, fails on ubuntu-latest. Root cause: the `bin/sahjhan` symlink targets `sahjhan-aarch64-apple-darwin` which is gitignored. On CI, the symlink dangles and `os.path.realpath` may behave differently for path comparison.

5. **BJ-005:** `_sahjhan_bootstrap.py` Bash redirect detection uses `p in command` substring matching. False positives confirmed: `echo "enforcement/" > /tmp/log.txt` is blocked (string mention, not actual write), and `cp enforcement/hooks/primer.py /tmp/backup.py` is blocked (reads FROM protected path, not writes TO). Defense-in-depth only -- primary Write/Edit protection via realpath is correct.

6. **BJ-006:** `verify_answer_freshness` in `lens_quiz.py` splits answer text on commas and uses `any(part in window)` for freshness verification. Short answer parts (e.g., single letters) match spuriously against any file content. Theoretical risk -- current quiz bank uses multi-word options.

### LOW Severity (1)

7. **BJ-007:** `enforcement/hooks/_common.py` bridge re-exports 7 specific names from `hooks/_common.py` via importlib. The export list is manually maintained. No test validates sync. Currently in sync but fragile by design.

## What I Did Not Find

- No logic bugs in enforcement hooks (commit_gate, protocol_tracker, write_guard, bash_guard, verify_hooks, lens_evidence -- all clean)
- No security vulnerabilities (no eval/exec/shell=True anywhere in codebase)
- No PAT-006 instances (all `open()` calls now have encoding parameter -- resolved since Run 24)
- No Rubber Stamp (#11) or Permissive Validator (#12) anti-patterns in test files (tests check actual values, not just types/structures)
- No resource leaks (all file handles use context managers)
- No concurrency issues (single-threaded code, subprocess calls have timeouts)
- No error-propagation issues (BaseException handler in _protocol_cache.py is correct cleanup pattern)
- `_is_test_cmd` and `_is_tdd_cmd` substring bypass (PAT-CMD-001 from Run 24) is RESOLVED -- both now use `startswith`
- Source-code string matching tests (BJ-006 from Run 24) are RESOLVED -- replaced with behavioral tests
- profiler_plugin.py (cold file) is functional -- priority-by-position is intentional design

## Patterns Identified

No new patterns. All findings are distinct issues rather than instances of a shared root cause.

Existing patterns checked:
- **PAT-005 (README count drift):** CONFIRMED active -- BJ-003
- **PAT-006 (missing encoding):** RESOLVED -- all instances fixed
- **PAT-CMD-001 (substring command detection):** RESOLVED -- fixed to startswith

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 3         | 3         | 100%     |
| MEDIUM     | 3         | 3         | 100%     |
| LOW        | 2         | 1         | 50%      |
| **Total**  | **8**     | **7**     | **88%**  |

### Prediction Details
- **P1 (HIGH):** test_readme_metrics regex crash -- CONFIRMED (BJ-001)
- **P2 (HIGH):** README count drift PAT-005 -- CONFIRMED (BJ-003)
- **P3 (HIGH):** TestStopGate test isolation -- CONFIRMED (BJ-002)
- **P4 (MEDIUM):** CI regression TestBootstrapHook -- CONFIRMED (BJ-004)
- **P5 (MEDIUM):** _sahjhan_bootstrap false positive -- CONFIRMED (BJ-005)
- **P6 (MEDIUM):** verify_answer_freshness substring -- CONFIRMED (BJ-006, theoretical)
- **P7 (LOW):** profiler_plugin.py cold file -- UNCONFIRMED (code is functional)
- **P8 (LOW):** _common.py bridge fragility -- CONFIRMED (BJ-007, design issue)

### Calibration Notes
- HIGH predictions at 100% for the fourth consecutive Justine run. Direct observation (test failures, filesystem counts) remains the most reliable signal.
- MEDIUM predictions at 100% -- improved from 67% in Run 24. All three confirmed via code analysis and reproduction.
- LOW predictions at 50% -- P7 (profiler_plugin cold file) was a false positive. The code is simple and correct. Cold-file predictions on utility modules continue to be unreliable.
- Overall accuracy improved from 71% (Run 24) to 88% (Run 25). Aggressive calibration (HIGH = one strong signal) continues to work well for HIGH and MEDIUM tiers.

## Convergence

- **Iterations:** 1 (single-pass convergence)
- **Areas examined:** All enforcement hooks (13 files), all harness hooks (2 files), all skill scripts (6 files), all test files (28 files), README.md, enforcement config (5 TOML files), CI workflow, install-hooks.sh
- **Lenses applied:** integration, security, data-flow, error-propagation, contract, component (all 6 core lenses)
- **Circuit breakers:** None triggered

## Recommendations

1. **Fix BJ-001 (test regex):** Change the test to use `pytest --co` without `-q`, or parse the output differently. The `-q` format shows per-file counts, not a summary line. Use the non-quiet format and parse the "N tests collected" summary.

2. **Fix BJ-002 (stop gate isolation):** Both TestStopGate tests need `tmp_path` isolation. Pass `cwd=str(tmp_path)` in the event dict so the hook doesn't read live session state. Create a clean `tmp_path` with no `.sahjhan/` directory.

3. **Fix BJ-003 (README counts):** Update all stale counts. For LOC, clarify the counting methodology -- the test counts 4 directories (tests/, skills/holtz/scripts/, hooks/, enforcement/hooks/) totaling 17,577 lines, while the README claims 21,120. Either the test or the README should be authoritative. PAT-005 is in its 8th+ consecutive run; consider automating the counts.

4. **Investigate BJ-004 (CI regression):** The CI failure on `test_blocks_binary_modification` is likely caused by `os.path.realpath` on a dangling symlink. The test should either: (a) create a mock bin/ structure instead of relying on the repo's symlink, or (b) be marked as `@pytest.mark.skipif` when the target binary is absent.

5. **Fix BJ-005 (bootstrap false positives):** The Bash redirect check should verify the protected path is the TARGET of the redirect, not just present in the command string. Consider parsing the command to identify the redirect target.

## Metrics

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 758 | 758 |
| Tests failing | 3 | 3 |
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

# Adversarial Self-Play Merge Report

**Date:** 2026-03-29
**Run:** 26
**Holtz findings:** 14 total items
**Justine findings:** 15 total items
**Merged total:** 25 items

> **Note:** BH-020 and BH-021 are both derived from Justine JH-007. Justine's JH-007 matched Holtz BH-003 on location proximity (README.md:192 vs 196, difference=4) — producing Agreement BH-020. The distinct hooks-count observation in JH-007 was substantively different from the footnote error and is carried forward as BH-021 (Justine-only). This is the one case where a single Justine item contributed to two merged items; total merged item count is 25, not 24.

---

## Agreement

5 items found by both auditors (including 2 with severity disagreements).

| Merged ID | Original IDs | Description |
|-----------|-------------|-------------|
| BH-006 | Holtz BH-014 + Justine JH-001 | HMAC null byte injection, _common.py:82 |
| BH-009 | Holtz BH-009 + Justine JH-002 | Unknown severity rank 0 passes downgrade, check_severity_change.py:25 |
| BH-004 | Holtz BH-008 + Justine JH-010 | Read-guard bypass, _sahjhan_bootstrap.py (severity disagreement) |
| BH-018 | Holtz BH-002 + Justine JH-005 | LOC count stale in README, README.md:190 (severity disagreement) |
| BH-020 | Holtz BH-003 + Justine JH-007 | Research footnote run count wrong, README.md:192-196 |

---

## Holtz-only

9 items — depth-first analysis found subtle multi-step logic bugs, state management issues, and test-path correctness problems that require tracing execution flow across multiple files.

| Merged ID | Original ID | Description |
|-----------|-------------|-------------|
| BH-001 | Holtz BH-001 | CRITICAL: STATUS.md renders from wrong ledger (ledgers.toml name mismatch) |
| BH-002 | Holtz BH-005 | HIGH: _active_ledger() always returns None — hooks write to wrong ledger |
| BH-003 | Holtz BH-007 | HIGH: lens_quiz.py record_authed_event unprotected from FileNotFoundError |
| BH-005 | Holtz BH-011 | HIGH: test_evidence_rejects_rubber_stamp tests wrong code path |
| BH-008 | Holtz BH-006 | MEDIUM: check_sweep_evidence counts entire session, not final sweep |
| BH-011 | Holtz BH-010 | MEDIUM: Answer count mismatch shows wrong error message (lens_quiz.py) |
| BH-023 | Holtz BH-004 | LOW: Run count says twenty-five, now twenty-six |
| BH-024 | Holtz BH-012 | LOW: is_git_commit regex false-positives on echo/quoted strings |
| BH-025 | Holtz BH-013 | MEDIUM: 200-node round-trip test suppresses KeyError |

---

## Justine-only

10 items — breadth-first analysis found surface-level test coverage gaps, doc/drift in sections Holtz did not focus on, infrastructure issues, and new bypass vectors in security guards.

| Merged ID | Original ID | Description |
|-----------|-------------|-------------|
| BH-007 | Justine JH-014 | HIGH: HMAC tests do not verify null byte rejection (Rubber Stamp) |
| BH-010 | Justine JH-011 | MEDIUM: is_sahjhan_cmd fails with env var prefix (_protocol_cache.py:178) |
| BH-012 | Justine JH-008 | MEDIUM: Coverage gate not enforced in CI |
| BH-013 | Justine JH-012 | MEDIUM: test_severity_change.py has no edge case coverage (Rubber Stamp) |
| BH-014 | Justine JH-003 | MEDIUM: check_severity_change case-sensitive without normalization |
| BH-015 | Justine JH-009 | MEDIUM: subagent_findings_check.py has 0% test coverage |
| BH-016 | Justine JH-004 | MEDIUM: Sleep detection bypass via sleep infinity/subshell |
| BH-017 | Justine JH-013 | LOW: test_sweep_evidence.py missing boundary/empty transcript tests |
| BH-019 | Justine JH-015 | LOW: subagent_findings_check.py operates on raw text without fence masking |
| BH-021 | Justine JH-007 | MEDIUM: README documents only 5 of 9 hooks |
| BH-022 | Justine JH-006 | LOW: README prediction accuracy figures stale |

> BH-021 and BH-022 are listed here; BH-021 is the hooks-count observation from JH-007 (distinct from the footnote error that matched BH-003 as BH-020), and BH-022 is from JH-006.

---

## Severity Disagreements

2 items — listed with both ratings.

- **BH-004:** Holtz=HIGH, Justine=LOW. Using HIGH. Item: read-guard bypass in `_sahjhan_bootstrap.py`. Holtz focuses on active bypass vectors (sed, perl, patch, python open()); Justine recommends accepting as advisory/defense-in-depth. Using Holtz=HIGH pending human review of whether strengthening or documenting is the right fix.
- **BH-018:** Holtz=MEDIUM, Justine=LOW. Using MEDIUM. Item: LOC count stale in README. Holtz flags as MEDIUM (doc/drift with 24% divergence is meaningful); Justine rates LOW (cosmetic). Using MEDIUM.

---

## Contradictions

0 items. No contradictions detected. Neither auditor explicitly verified any finding from the other as "not a bug" or "correct behavior." Note: Justine's JH-010 characterizes the read-guard bypass as architectural (recommendation to document as advisory) rather than as a contradiction — this is a severity/approach disagreement, not a factual contradiction about whether the bypass exists.

---

## Blind Spot Analysis

### Holtz's blind spots

Holtz missed 10 items that Justine found:

1. **Infrastructure and CI gaps (BH-012):** Holtz did not audit the CI workflow for coverage gate enforcement. This is a breadth-first surface scan — Holtz's depth-first focus on enforcement logic skipped the build configuration layer.

2. **Zero-coverage file (BH-015):** Holtz did not run a full coverage report and missed that `subagent_findings_check.py` has 0% coverage. Justine's breadth-first pass includes coverage-report scanning as a systematic step.

3. **Co-located doc/drift items (BH-021, BH-022):** Holtz found doc/drift in the README (BH-002, BH-003, BH-004) but focused on LOC figures and the research footnote — missing the hooks-count discrepancy at line 196 and the prediction accuracy figures at line 104. Justine's breadth-first scan covered more README sections.

4. **Test edge-case gaps (BH-007, BH-013, BH-017):** Holtz caught one bogus test (BH-005) and one suppressed error in a test (BH-025), but missed the pattern of missing edge-case tests in `test_severity_change.py`, `test_sweep_evidence.py`, and `test_hmac_helpers.py`. Justine systematically audited each test file for missing scenarios.

5. **Enforcement bypass vectors (BH-016):** Holtz analyzed the sleep detection regex in context of protocol enforcement but did not enumerate non-numeric bypass patterns (`sleep infinity`, subshell wrapping). Justine explicitly probed the regex with non-numeric inputs.

6. **Case sensitivity bug (BH-014):** Holtz found the rank-0 default bug (BH-009) but did not probe the same function for case normalization. Justine's follow-up on the same function found the adjacent case-sensitivity issue.

7. **is_sahjhan_cmd env-prefix bypass (BH-010):** Holtz found the `is_git_commit` false-positive (BH-024) in `_protocol_cache.py:165` but did not look at the nearby `is_sahjhan_cmd()` at line 178 for a symmetrical pattern.

8. **Fence masking gap (BH-019):** Holtz did not audit `subagent_findings_check.py` for the fenced-block masking pattern (PAT-001). Justine applied PAT-001 as a systematic breadth-first pattern check.

**Pattern:** Holtz's blind spots cluster around: (a) test coverage completeness scans, (b) README sections beyond those containing bug-relevant claims, (c) adjacent-line variants of bugs already found, and (d) build/CI infrastructure. These are all breadth-first surface scans rather than deep multi-file analysis.

---

### Justine's blind spots

Justine missed 9 items that Holtz found:

1. **Ledger name mismatch (BH-001, CRITICAL):** Justine did not read `docs/holtz/.sahjhan/ledgers.toml` and did not notice that STATUS.md renders from the wrong ledger. This required cross-referencing the ledger configuration file with the STATUS.md template — a multi-file state-tracing task.

2. **_active_ledger() always returns None (BH-002, HIGH):** Justine did not trace the data flow from `_active_ledger()` through the hooks event-writing path to the gate conditions. This is the deepest multi-file analysis in the punchlist — it requires reading `_common.py`, the hooks that call it, the ledger write logic, and the gate condition readers.

3. **FileNotFoundError in lens_quiz.py (BH-003, HIGH):** Justine audited `_sahjhan_bootstrap.py` (JH-010) and `_common.py` (JH-001) but did not audit `lens_quiz.py` for error handling. The `primer.py` vs `lens_quiz.py` comparison requires reading both files.

4. **Bogus test code path (BH-005, HIGH):** Justine found test shallow issues (JH-012, JH-013, JH-014) but did not identify the specific test that exercises the wrong code path in `test_lens_quiz_integration.py`. This requires understanding what the rubber-stamp detection code path actually is vs. what the test exercises.

5. **check_sweep_evidence final-sweep window (BH-008, MEDIUM):** Justine found the test for sweep evidence shallow (JH-013) but did not identify the underlying logic bug — that `count_distinct_reads` counts the entire session instead of the final-sweep window.

6. **Answer count wrong error message (BH-011, MEDIUM):** Justine did not audit `lens_quiz.py` for the (0,0) sentinel/error-message confusion.

7. **200-node test KeyError suppression (BH-025, MEDIUM):** Justine found multiple shallow test issues but did not audit `test_impact_graph.py` at all.

8. **Run count stale (BH-023, LOW):** Justine updated LOC and prediction accuracy figures in README but did not check the run count at line 162.

9. **is_git_commit false positive (BH-024, LOW):** Justine found `is_sahjhan_cmd` at line 178 but not the `is_git_commit` regex at line 165, which is 13 lines away and a different category.

**Pattern:** Justine's blind spots cluster around: (a) multi-file state tracing (ledger path, hook write path, gate read path), (b) cross-file comparison bugs (primer.py vs lens_quiz.py error handling, correct vs bogus test code path), and (c) logic bugs that require tracing sentinel values through call stacks. These are exactly the deep, multi-step analyses that characterize Holtz's depth-first methodology. Justine's breadth-first pass reliably found surface patterns but did not chase execution chains across file boundaries.

---

## Auditor Stall Status

Neither auditor stalled. Both reached convergence before merge.

- **Holtz:** 14 findings across 14 items. Convergence reached at Step 9 (Merge Ready).
- **Justine:** 15 findings across 15 items. Convergence reached independently.

---

## Merge Statistics Summary

| Metric | Count |
|--------|-------|
| Holtz findings | 14 |
| Justine findings | 15 |
| Agreements (same bug, both found) | 5 |
| — of which: severity disagreements | 2 |
| — of which: same severity | 3 |
| Holtz-only findings | 9 |
| Justine-only findings | 11 |
| Contradictions | 0 |
| Merged total | 25 |
| Overlap rate | 5 / (14 + 15 - 5) = 20.8% |

The 20.8% overlap rate is consistent with expectations for depth-first vs. breadth-first auditors operating independently: each auditor finds a distinct majority of issues, with overlap concentrated on the most salient bugs (the HMAC null byte vulnerability and the severity-check rank-0 default were independently flagged as HIGH/MEDIUM by both auditors).

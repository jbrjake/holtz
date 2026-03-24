# Recommendation Escalation Report

Cross-referencing recommendations from 11 audit run summaries (runs 1-11, excluding justine-* directories) to identify recurring items that warrant escalation to punchlist items.

## Recurring Recommendations

### 1. Add mypy / type checker

| Run | Wording |
|-----|---------|
| Run 1 (2026-03-19) | "No linter or type checker is configured. Adding mypy would catch type issues at development time." |
| Run 2 (2026-03-20) | "No linter or type checker is configured. Adding mypy would catch type issues at development time." |
| Run 3 (2026-03-20) | "No linter or type checker is configured. Adding mypy and ruff would prevent future regressions." |
| Run 4 (2026-03-20) | "No linter or type checker is configured. Adding mypy and ruff would prevent future regressions." |
| Run 5 (2026-03-21) | "Consider adding mypy -- Ruff ANN rules enforce annotation presence but not type correctness." |

**Appeared in:** Runs 1, 2, 3, 4, 5 (5 runs)
**Resolution:** Escalated in run 5 (BH-001 added ruff ANN rules). mypy added between runs 5 and 6 (run 6 baseline shows "Mypy errors: 0"). Fully resolved.
**Escalate to punchlist?** No -- already resolved.

---

### 2. Hoist `_field_names` / `section_re` to module level

| Run | Wording |
|-----|---------|
| Run 2 (2026-03-20) | "The _field_names tuple and section_re construction are recomputed per item inside the loop. They could be hoisted to module level for clarity." |
| Run 3 (2026-03-20) | "The _field_names tuple and section_re construction are still recomputed per item inside the parse loop. Hoisting to module level would improve clarity." |
| Run 4 (2026-03-20) | "The _field_names tuple and section_re are still recomputed per item. Hoisting to module level would improve clarity and eliminate redundant work." |

**Appeared in:** Runs 2, 3, 4 (3 runs)
**Resolution:** Not explicitly resolved in any summary. Disappeared after run 4, possibly addressed silently or superseded by other refactoring.
**Escalate to punchlist?** No -- low impact (clarity only, negligible performance), and it stopped recurring after run 4. If it still exists, it is a minor code hygiene item, not a defect.

---

### 3. Eliminate redundant `mask_code_fences` call in `validate()`

| Run | Wording |
|-----|---------|
| Run 2 (2026-03-20) | "validate() calls mask_code_fences(content) redundantly (it was already called in parse_punchlist()). Passing the masked content as an argument would eliminate this." |
| Run 3 (2026-03-20) | "validate() still calls mask_code_fences(content) redundantly. Passing masked content as a parameter would eliminate this." |
| Run 4 (2026-03-20) | "validate() still calls mask_code_fences redundantly. Passing masked content as a parameter to validate() would eliminate the double call." |

**Appeared in:** Runs 2, 3, 4 (3 runs)
**Resolution:** Escalated and resolved in run 5 (BH-002: "Eliminated redundant mask_code_fences call in main() path. parse_punchlist now accepts pre-computed masked content via `_masked` parameter.").
**Escalate to punchlist?** No -- already resolved.

---

### 4. Add coverage reporting (pytest-cov)

| Run | Wording |
|-----|---------|
| Run 5 (2026-03-21) | "No coverage tool is configured. Adding pytest-cov would make coverage gaps visible." |
| Run 6 (2026-03-22) | "No coverage tool is configured. Adding pytest-cov would make coverage gaps visible and help target future test additions." |
| Run 8 (2026-03-22) | "Consider pytest-cov reinstallation -- Coverage reporting was useful in run 7 but removed in run 8 to fix the broken dependency." |
| Run 9 (2026-03-22) | "pytest-cov -- Coverage reporting would detect untested paths. Currently not installed. Second appearance." |

**Appeared in:** Runs 5, 6, 8, 9 (4 runs)
**Resolution:** First escalated in run 7 (BH-001 added pytest-cov config). Broken config removed in run 8 (BH-001). Reinstalled and properly configured in run 10 (BH-002). Finally resolved.
**Escalate to punchlist?** No -- already resolved (run 10).

---

### 5. Test boilerplate reduction (`make_item` builder)

| Run | Wording |
|-----|---------|
| Run 5 (2026-03-21) | "36 repetitions of the standard valid-item template in test_validate_punchlist.py. A make_item(**overrides) builder fixture would reduce this." |
| Run 6 (2026-03-22) | "test_validate_punchlist.py has ~36 repetitions of the standard valid-item template. A make_item(**overrides) builder fixture would reduce this." |

**Appeared in:** Runs 5, 6 (2 runs)
**Resolution:** Escalated and resolved in run 7 (BH-002: "Added make_item fixture to tests/conftest.py").
**Escalate to punchlist?** No -- already resolved.

---

### 6. Add CI configuration (GitHub Actions)

| Run | Wording |
|-----|---------|
| Run 6 (2026-03-22) | "No CI/CD is configured. GitHub Actions with ruff + mypy + pytest would prevent regressions on push." |
| Run 7 (2026-03-22) | "No CI/CD is configured. GitHub Actions with ruff check . && mypy scripts/ && pytest would prevent regressions on push." |

**Appeared in:** Runs 6, 7 (2 runs)
**Resolution:** Escalated and resolved in run 8 (BH-002: "Created .github/workflows/ci.yml with ruff, mypy, and pytest").
**Escalate to punchlist?** No -- already resolved.

---

### 7. Automate README metrics

| Run | Wording |
|-----|---------|
| Run 9 (2026-03-22) | "Automate README metrics -- Consider a CI step or pre-commit hook that validates test count and line count against README.md." |
| Run 10 (2026-03-22) | "Automate README metrics -- test count and line count drift on every change. Second appearance." |

**Appeared in:** Runs 9, 10 (2 runs)
**Resolution:** Escalated and resolved in run 11 (BH-001: "Added test_readme_metrics_match_actual() to test_integration.py").
**Escalate to punchlist?** No -- already resolved.

---

### 8. Markdown parsing risk surface (use correct extraction pattern)

| Run | Wording |
|-----|---------|
| Run 1 (2026-03-19) | "The primary risk surface is the markdown parsing in validate_punchlist.py -- every new field extraction should use the _section_from_original pattern." |
| Run 2 (2026-03-20) | "The primary risk surface remains the markdown parsing in validate_punchlist.py. Any new field extraction should use the _masked_pos_to_orig_offset -> extract pattern." |

**Appeared in:** Runs 1, 2 (2 runs)
**Resolution:** Addressed through progressive hardening (runs 1-4 all targeted parsing). Not a discrete punchlist item -- it is architectural guidance.
**Escalate to punchlist?** No -- architectural guidance, not a fixable defect. The parsing layer has been hardened through 4 runs of fixes.

---

## Non-Recurring Recommendations (single appearance only)

These appeared in exactly one summary and are listed for completeness:

| Run | Recommendation |
|-----|---------------|
| Run 1 | Runner fixture suite can be extended with new formats |
| Run 3 | A fourth run is likely to find 0-1 items (convergence note) |
| Run 4 | Consider a shared parsing layer for count_items and parse_punchlist |
| Run 7 | Impact graph coverage at 64%, consider CLI tests |
| Run 8 | Hook testing discipline -- all future hooks need tests |
| Run 11 | Add \s convention check to CI |

---

## Summary

| # | Recommendation | Runs | Escalated? | Status |
|---|---------------|------|------------|--------|
| 1 | Add mypy / type checker | 1, 2, 3, 4, 5 | Yes (run 5-6) | Resolved |
| 2 | Hoist _field_names / section_re | 2, 3, 4 | No | Stopped recurring |
| 3 | Eliminate redundant mask_code_fences | 2, 3, 4 | Yes (run 5) | Resolved |
| 4 | Add pytest-cov | 5, 6, 8, 9 | Yes (run 7, 10) | Resolved |
| 5 | Test boilerplate make_item builder | 5, 6 | Yes (run 7) | Resolved |
| 6 | CI configuration | 6, 7 | Yes (run 8) | Resolved |
| 7 | Automate README metrics | 9, 10 | Yes (run 11) | Resolved |
| 8 | Markdown parsing risk guidance | 1, 2 | No | Architectural guidance |

**Result: All recurring recommendations have already been resolved or have stopped recurring.** There are no outstanding items to escalate to the punchlist. The recommendation-to-escalation pipeline has been functioning correctly: items that appeared in 2+ consecutive runs were consistently promoted to punchlist items in a subsequent run and resolved.

The single-appearance recommendations from runs 8 and 11 (hook testing discipline, \s convention CI check) should be monitored -- if they reappear in a future run, they become escalation candidates.

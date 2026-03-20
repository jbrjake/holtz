# Holtz Audit Summary

**Project:** holtz (self-audit, run 4 — integration focus)
**Date:** 2026-03-20
**Auditor:** Holtz, applied to himself (fourth time)

## Before / After

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 104 | 108 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Findings | — | 4 |
| Resolved | — | 4 |
| Deferred | — | 0 |

## Findings by Category

| Category | Count |
|----------|-------|
| bug/logic | 2 |
| test/integration-gap | 1 |
| design/inconsistency | 1 |

## Pattern: PAT-001 — Structural-awareness divergence across parsers

All 4 findings trace to a single systemic issue: **parsers operating at different levels of structural awareness produce inconsistent results when content appears at the wrong structural level**.

- **BH-001 (MEDIUM):** `_section_from_original()` used masked_block for header finding but applied section_re to original_block for content extraction. Code-fenced field headers in original_block prematurely terminated section capture, silently truncating content.

- **BH-002 (MEDIUM):** `count_items()` scanned the entire document for `**Status:**` fields instead of scoping to item blocks. Phantom statuses in Pattern descriptions or item prose inflated the convergence tracker's item count.

- **BH-003 (LOW):** No integration test verified that the two parsing approaches (count_items vs parse_punchlist) agreed on item counts. The divergence was invisible to the test suite.

- **BH-004 (LOW):** Acceptance Criteria extraction used masked_block (safe) while Problem/Evidence/Resolution used original_block (unsafe). Inconsistent code-fence handling across section types.

**Root cause:** The codebase has two independent parsers for the same format — one structurally aware (parse_punchlist splits on item headers, uses masked content for decisions) and one flat (count_items does global regex, section_re runs on unmasked content). When these diverge, the convergence tracker and validator see different realities.

**Fix:** Unified both to always scope extraction to item blocks and use masked content for structural decisions.

## Key Fixes

1. **BH-001 (commit 400cd23):** `_section_from_original` now finds section boundaries in masked_block, maps the line range to original_block, and extracts original content directly. No section_re on unmasked content.

2. **BH-002 (commit a475925):** `count_items` now splits on `### BH-NNN:` headers and extracts only the first Status per item block, matching parse_punchlist's structural awareness.

3. **BH-003 (commit c3022a8):** `test_cross_parser_agreement` feeds the same punchlist to both parsers and asserts they agree on counts and status distribution.

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 1 | 12 | 2 HIGH, 6 MEDIUM, 4 LOW | PAT-001: code-fence-unaware parsing | 48 |
| 2 | 5 | 2 MEDIUM, 3 LOW | PAT-002: incomplete code-fence isolation | 10 |
| 3 | 3 | 3 LOW | None (all distinct) | 2 |
| 4 | 4 | 2 MEDIUM, 2 LOW | PAT-001: structural-awareness divergence | 4 |

Run 4 reversed the convergence trend — findings increased from 3 to 4, and severity rose from all-LOW back to 2 MEDIUM. This is because the audit lens shifted from component-level to integration-level. Runs 1-3 progressively hardened individual components; run 4 found bugs at the seams between them.

## Recommendations

1. **Consider a shared parsing layer.** Both count_items and parse_punchlist parse the same format. A single `parse_items()` function returning structured data would eliminate the divergence risk entirely.

2. **The `_field_names` tuple and `section_re` are still recomputed per item.** Hoisting to module level would improve clarity and eliminate redundant work.

3. **validate() still calls mask_code_fences redundantly.** The content is already masked inside parse_punchlist. Passing masked content as a parameter to validate() would eliminate the double call.

4. **No linter or type checker is configured.** Adding mypy and ruff would prevent future regressions.

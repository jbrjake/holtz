# Adversarial Self-Play Merge Report

**Date:** 2026-03-25
**Run:** 20
**Holtz findings:** 15 total items
**Justine findings:** 8 total items
**Merged total:** 21 items

## Agreement
2 items found by both auditors (0 with severity disagreements)

- **BH-001** (README.md:160, doc/drift, HIGH): Was Holtz BH-001 + Justine BJ-001. Both found the README run/test/line count staleness. Same severity (HIGH).
- **BH-003** (test_token_profiler_report.py:289-327, test/shallow, MEDIUM): Was Holtz BH-003 + Justine BJ-003. Both found the TestSectionsPresent rubber stamp pattern. Same severity (MEDIUM). Justine's evidence adds specificity: "Bucket" and "Turn" keywords match headings only, not table columns.

## Holtz-only
13 items — depth-first analysis found bugs that require tracing implementation across multiple files or following anti-pattern heuristics through test bodies

- **BH-002** (README.md:216, doc/drift) — Was: Holtz BH-002
- **BH-004** (test_token_profiler_report.py:492-503, test/fragile) — Was: Holtz BH-004
- **BH-005** (test_token_profiler_cli.py:304-313, test/fragile) — Was: Holtz BH-005
- **BH-006** (test_token_profiler_cli.py, test/missing) — Was: Holtz BH-006
- **BH-007** (test_token_profiler_integration.py:22-27, test/missing) — Was: Holtz BH-007
- **BH-008** (test_token_profiler_models.py:90-93, test/shallow) — Was: Holtz BH-008
- **BH-009** (test_token_profiler_report.py:420-421,443-447, test/shallow) — Was: Holtz BH-009
- **BH-010** (cli.py:218, bug/error-handling) — Was: Holtz BH-010
- **BH-011** (analyze.py:326,471; cli.py:421, bug/logic) — Was: Holtz BH-011
- **BH-013** (viewer.py:17 + hooks, design/inconsistency) — Was: Holtz BH-012
- **BH-014** (convergence_check.py:320-321, bug/error-handling) — Was: Holtz BH-013
- **BH-015** (report.py:34-36, doc/drift) — Was: Holtz BH-014
- **BH-016** (plugin_protocol.py:10; cli.py:141-195, design/inconsistency) — Was: Holtz BH-015

## Justine-only
6 items — breadth-first analysis found bugs in integration seams, contract violations, and error-handling edge cases

- **BH-012** (analyze.py:309,380,398, bug/logic) — Was: Justine BJ-002
- **BH-017** (cli.py:250-256, bug/error-handling) — Was: Justine BJ-004
- **BH-018** (hooks/_common.py:103-155 + markdown_utils.py:21-57, design/inconsistency) — Was: Justine BJ-005
- **BH-019** (test_token_profiler_report.py:TestSummaryFormatting, test/shallow) — Was: Justine BJ-006
- **BH-020** (tests/test_integration.py, test/missing) — Was: Justine BJ-007
- **BH-021** (analyze.py:265-274, bug/logic) — Was: Justine BJ-008

## Severity Disagreements
0 items

## Contradictions
0 items

## Near-Miss Note

**BH-011 and BH-012 describe the same underlying defect** (pricing module disconnected, dollar costs always $0.00). They were classified as separate items because their line anchors exceed the 5-line proximity threshold (BH-011 at analyze.py:326,471; BH-012 at analyze.py:309,380,398 — minimum diff = 17 lines). Similarly BH-010 (cli.py:218) and BH-017 (cli.py:250-256) are distinct bugs (json.loads vs wrong exception type) in the same file/category — correctly classified separately. Holtz should fix the pricing bug once, referencing both items.

## Blind Spot Analysis

**Holtz's blind spots (Justine-only findings):**
- **Integration seam bugs:** Justine found `apply_phase_labels` contract violation (BH-021) and mask_fenced_blocks divergence (BH-018) — both require comparing two implementations or reading docstring contracts against implementations. Holtz's depth-first approach traced data flow through single modules but missed cross-module behavioral contracts.
- **Wrong exception type:** Justine caught `except ImportError` masking `FileNotFoundError` in viewer handling (BH-017) — a different error-handling class in the same file where Holtz found `json.loads` unguarded. Holtz may have stopped at the first error-handling finding per file.
- **Test fixture vs. pipeline computation:** Justine's BH-019 (TestSummaryFormatting) identifies that fixture values are synthetic, not derived from input. Holtz found rubber-stamp and permissive-validator issues but missed this "computation-bypass" variant.
- **README test coverage gap:** Justine found that no test covers the narrative run-count claims (BH-020), a gap Holtz noted as a doc/drift issue (BH-001) but did not convert into a test/missing finding.

**Justine's blind spots (Holtz-only findings):**
- **Test-body anti-patterns:** Holtz found 5 test-quality issues Justine missed: Choose Your Own Adventure loop (BH-004), Time Bomb sleep (BH-005), tautology test (BH-008), permissive or-based assertion (BH-009), and Missing Guest integration tests (BH-007). Justine found the rubber-stamp pattern but not the more subtle anti-patterns (#14, #7, #1, #12, #15).
- **Missing behavioral tests:** BH-006 (no --pricing pipeline test) required cross-referencing argument-parsing tests against end-to-end tests — a multi-file comparison Justine's breadth-first pass skipped.
- **Secondary README drift:** BH-002 (line 216 line count) is a separate location from BH-001 (line 160 run count). Justine's BJ-001 covered both lines 160 and 190 in a single item but missed line 216 ("What's inside").
- **Encoding omission:** BH-013 (open() without encoding=) required a codebase-wide survey; Justine did not apply this cross-cutting check.
- **Docstring trap:** BH-015 (_fmt_pct docstring says "fraction") required reading implementation against docstring with specific attention to units — a detail Justine's pass did not reach.
- **Protocol parallel duplicate:** BH-016 (@runtime_checkable unused) required comparing plugin_protocol.py against _is_plugin_class logic — a two-file contract check Justine's run missed.
- **Anti-gaming bypass:** BH-014 (bare pass on timestamp parse failure) required reading convergence_check.py with attention to security intent vs. exception behavior — a Holtz-specific lens area.

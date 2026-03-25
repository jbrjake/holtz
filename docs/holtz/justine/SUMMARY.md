# Justine Audit Summary

**Project:** holtz v0.5.2
**Date:** 2026-03-24
**Run:** 16 (parallel dispatch with Holtz)
**Auditor:** Justine (breadth-first, all lenses simultaneous)
**Baseline:** 613 tests passing, 0 failing, 0 skipped (9.27s)

## Results

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 2 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 0 | 0 | 0 |
| **Total** | **2** | **0** | **0** |

## Findings

### BJ-001 (HIGH, bug/logic): parse_brief masked-offset-to-original divergence

`pattern_brief_compact.py` line 60 uses character offsets from `masked` content to index into `content` (original). `mask_code_fences` replaces fenced lines with empty strings, making `masked` shorter than `content`. After the first code fence, all offsets diverge. PAT entries after a code fence extract field values from the wrong position -- pulling text from inside the code fence instead of the real entry.

Reproduction: patterns-brief.md with a code fence between two PAT entries. PAT-002's fields all extract as the fenced content ("fake") instead of the real values. PAT-001's Example field bleeds into the fence.

This is the sixth manifestation of PAT-001 (code-fence-unaware parsing) across the project's 16 runs. The fix is to use line-number mapping between masked and original, the same approach already used in `validate_punchlist.py` and `render_items`.

### BJ-002 (HIGH, bug/logic): mask_fenced_blocks does not enforce CommonMark fence length

`hooks/_common.py` line 117 stores `fence_marker = m.group(1)[0]` -- a single character. The closing check on line 119 (`line.strip().startswith(fence_marker)`) matches ANY line starting with that character, regardless of opener length. Per CommonMark spec, a closing fence must have at least as many characters as the opener.

Impact: A ```` (4-backtick) fence is prematurely closed by ``` (3 backticks). Content between the premature close and the real close is unmasked and exposed to hook regex matching. Confirmed exploitable: a **Status:** RESOLVED field placed after a ``` line inside a ```` fence is counted as a real status by convergence_gate.py.

Affects: convergence_gate.py (open item count), convergence_primer.py (field extraction), and any future hook that uses mask_fenced_blocks with content containing nested or variable-length fences.

## Patterns

Both findings are PAT-001 (code-fence-unaware parsing):
- **BJ-001:** offset mapping variant -- character offsets from masked content used to index original content
- **BJ-002:** fence grammar variant -- closing fence length check does not match CommonMark spec

PAT-001 has now appeared in 6 distinct manifestations across 16 runs. The pattern keeps recurring because the codebase has multiple independent implementations of fence-aware processing (markdown_utils.py, _common.py, pattern_brief_compact.py), each of which can fail in its own way.

## Test Quality Assessment

The test suite is strong. 613 tests across 17 test files. Anti-pattern scan across all test files:

| Anti-Pattern | Status |
|-------------|--------|
| Tautology Test (#1) | Not found |
| Green Bar Addict (#2) | Not found |
| Mockingbird (#3) | Not found -- mocks minimal, limited to subprocess |
| Inspector Clouseau (#4) | Not found |
| Happy Path Tourist (#5) | Not found -- extensive edge case coverage |
| Snapshot Trap (#6) | Not applicable |
| Time Bomb (#7) | Not found -- no hardcoded dates in tests |
| Schrodinger Test (#8) | Not found -- no shared mutable state |
| Shallow End (#9) | Not found -- test_integration.py covers cross-module contracts |
| Copy-Paste Archipelago (#10) | Minor -- helper fixtures mitigate well |
| **Rubber Stamp (#11)** | **Not found** -- all assertions check computed values |
| **Permissive Validator (#12)** | **Not found** -- exact value assertions throughout |

Justine override check (Rubber Stamp + Permissive Validator at +1 severity): CLEAN. Every test assertion in this codebase checks the VALUE, not just the type or structure. The token profiler tests in particular are exemplary -- they verify delta * remaining = session_cost, pricing at exact dollar amounts ($15.00/MTok for Opus input), and context_window = input + cache_creation + cache_read. These tests would fail with random data.

The README metrics test (`test_readme_metrics_match_actual`) has been upgraded since prior runs -- it now validates all 9 extracted component counts, not just the test count. The 4-run recurring recommendation for this test is now RESOLVED.

## Security Assessment

No security concerns. No eval/exec, no shell=True, no path traversal. Hook exit codes well-defined. sys.path.insert is local-only. BJ-002 affects enforcement correctness but is not a security vulnerability -- it allows process bypass (false status counts), not code execution or data exposure.

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 3 | 1 | 33% |
| MEDIUM | 3 | 1 | 33% |
| LOW | 1 | 0 | 0% |
| **Total** | **7** | **2** | **29%** |

- P1 (HIGH, README drift): UNCONFIRMED -- test now validates all counts
- P2 (HIGH, token profiler rubber stamps): UNCONFIRMED -- tests are excellent
- P3 (HIGH, hook enforcement): PARTIALLY CONFIRMED -- new bug found in mask_fenced_blocks (BJ-002)
- P4 (MEDIUM, header regex divergence): CONFIRMED via BJ-001 -- offset divergence in parse_brief
- P5 (MEDIUM, filter/render offset mapping): UNCONFIRMED -- already fixed with line-number mapping
- P6 (MEDIUM, SKILL.md references): UNCONFIRMED -- design intent, not drift
- P7 (LOW, impact_graph edge cases): UNCONFIRMED -- edge cases handled correctly

Calibration note: The 4-run recurring README recommendation (P1) is now RESOLVED -- the test was improved since the last Justine run. P3 was directionally correct (hook boundary enforcement bugs) but found a different specific bug than predicted. P4 hit exactly the right class of bug (offset divergence) but in a different file than predicted.

## Recommendation Escalation

- **README metrics (4/4 prior runs):** NOW RESOLVED. test_readme_metrics_match_actual validates all 9 fields.
- **`\s` convention (3/4 prior runs):** NOW RESOLVED. test_no_backslash_s_in_source_regex enforces the convention.
- **Hook enforcement scope (2/4 prior runs):** PARTIALLY RESOLVED. Scope was widened. But BJ-002 introduces a new correctness issue in the masking layer underneath.

## Convergence Assessment

Converged in a single pass. After the initial breadth-first scan across all lenses and all code areas, no additional findings surfaced on the convergence sweep. Both findings were discovered during prediction testing (BJ-001 from P4, BJ-002 discovered while auditing hooks for P3).

The codebase is well-hardened after 15 prior Holtz runs and 4 prior Justine runs. The finding surface has narrowed to the intersection of: (1) code-fence-aware processing (PAT-001 family) and (2) boundary/seam bugs between masking and extraction. These are the bugs that keep recurring because the masking abstraction has multiple independent implementations, and each implementation can fail independently.

## Impact Graph

Justine's impact graph at `docs/holtz/justine/impact-graph.json` contains 15 nodes and 12 edges. Key semantic edges:
- `convergence_check` assumes `validate_punchlist` (header regex alignment)
- `hooks.impact_graph_gate` assumes `hooks.status_staleness_gate` (shared path matching pattern)
- `test_integration` tests `README` (metrics validation gap -- now resolved)

## Artifacts

- `docs/holtz/justine/STATUS.md` -- program counter (CONVERGED)
- `docs/holtz/justine/PUNCHLIST.md` -- 2 items, both OPEN
- `docs/holtz/justine/impact-graph.json` -- 15 nodes, 12 edges
- `docs/holtz/justine/recon/0g-recon-summary.md` -- Justine's integration-first synthesis
- `docs/holtz/justine/recon/0h-predictions.md` -- 7 predictions, 2 confirmed
- `docs/holtz/justine/SUMMARY.md` -- this file

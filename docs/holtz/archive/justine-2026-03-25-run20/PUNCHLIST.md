# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz (self-audit) | Baseline: 641 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 2 | 0 | 0 |
| MEDIUM | 4 | 0 | 0 |
| LOW | 2 | 0 | 0 |

## Patterns

## Items

### BJ-001: README prose counts stale -- run count and line count claims outdated
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160,190`
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH)
**Lens:** public-contract

**Problem:** README line 160 says "Eighteen runs" but this is at least Run 19-20. Line 190 says "After 18 runs: 640 tests across 13,900 lines" but actual is 641 tests across ~14,000 lines. Line 216 ("What's inside") says "641 tests across 13,900 lines" -- the test count is correct but line count is stale. The automated test `test_readme_metrics_match_actual` does not catch the line 160/190 prose claims because they are narrative, not in the structured "What's inside" format the test parses.

**Evidence:** `grep -n "Eighteen runs\|After 18 runs\|640 test\|13,900" README.md` returns lines 160 and 190 with stale values. `wc -l` on all source files shows ~14,000 lines. The `test_readme_prose_counts_match_actual` test only checks lens and anti-pattern counts, not run counts or historical claims.

**Discovery Chain:** recon identified "Eighteen runs" as stale -> grep confirmed line 160 and 190 -> automated tests do not cover these narrative claims -> drift confirmed

**Acceptance Criteria:**
- [ ] README line 160 reflects the actual run count
- [ ] README line 190 reflects actual test and line counts
- [ ] A test exists covering narrative run count claims, or the counts are parameterized

**Validation Command:**
```bash
grep -n "Eighteen runs\|After 18 runs\|640 test" README.md | wc -l
```

### BJ-002: Pricing module disconnected from analysis pipeline -- dollar costs always $0.00
**Severity:** HIGH
**Category:** bug/logic
**Location:** `scripts/token_profiler/analyze.py:309,380,398`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 2 (confidence: HIGH)
**Lens:** data-flow, integration

**Problem:** The pricing module (`pricing.py`) implements correct dollar-cost computation with `apply_pricing_to_usage()`, and the analysis pipeline accepts a `pricing_fn` parameter in `build_session_profile()`. However, no caller ever passes `pricing_fn`. All dollar costs in the pipeline are hardcoded to `0.0`: `_build_phase_profiles()` creates `DollarCost(0.0, 0.0, 0.0, 0.0)` at line 380, and `_build_session_summary()` hardcodes `total_dollars=0.0` at line 398. The `--pricing` CLI flag explicitly warns it is "not yet integrated." The pricing module exists, is tested, and is correct, but is dead code in the pipeline.

**Evidence:** `grep -n "pricing_fn\|apply_pricing" scripts/token_profiler/analyze.py` shows only the parameter declaration and docstring reference. `grep -rn "from token_profiler.pricing\|import pricing" scripts/token_profiler/cli.py scripts/token_profiler/analyze.py` returns nothing. The `--pricing` CLI flag warns: "Dollar costs will show $0.00."

**Discovery Chain:** cold file scan found pricing.py tested but not imported -> traced callers of `apply_pricing_to_usage` -> zero callers outside tests -> pipeline hardcodes $0.00 -> confirmed dead integration

**Acceptance Criteria:**
- [ ] `build_session_profile()` calls `apply_pricing_to_usage()` for each turn's usage
- [ ] `_build_phase_profiles()` aggregates actual dollar costs instead of zero
- [ ] `_build_session_summary()` sums actual dollar costs
- [ ] End-to-end test verifies non-zero dollar amounts in profile output

**Validation Command:**
```bash
PYTHONPATH=scripts python -c "from token_profiler.analyze import build_session_profile; from token_profiler.models import RawTurn, Usage; t = RawTurn(request_id='r', index=0, timestamp=None, usage=Usage(input_tokens=1000000, output_tokens=0), stop_reason='end_turn', content_blocks=[], tool_results=[], assistant_text='', model='claude-opus-4-6'); p = build_session_profile('test', [t]); print(p.summary.total_dollars)"
```

### BJ-003: Report tests use Rubber Stamp assertions -- check heading presence, not table content
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:TestSectionsPresent`
**Status:** OPEN
**Predicted:** Prediction 4 (confidence: MEDIUM)
**Lens:** test audit

**Problem:** `TestSectionsPresent` contains tests that assert keywords appear in the markdown output without verifying the actual content. `test_cost_buckets_section_has_table` asserts `"Bucket" in md` -- this passes because "Bucket" appears in the heading "Cost Buckets", not because a "Bucket" column exists in the table. `test_hottest_turns_section_has_table` asserts `"Turn" in md` and claims "Hottest turns section should contain a Turn column" -- but "Turn" only appears in the heading "Top 20 Hottest Turns", not as a column. The actual output has no "Turn" column header. These tests would pass even if the sections produced no table at all, as long as the heading contained the keyword.

**Evidence:** `test_cost_buckets_section_has_table` assertion: `assert "Bucket" in md`. Actual table header: `"| Phase | Input | Cache Create | Cache Read | Output | Total |"`. No "Bucket" column exists. `test_hottest_turns_section_has_table` assertion: `assert "Turn" in md`. Actual content: `"#1 [10:00:00] init | +1,000 tokens | x3 remaining | 3,000 session cost"`. No "Turn" column exists. Both keywords match only via section headings.

**Discovery Chain:** scanned test file for assertions -> found keyword-in-md assertions -> generated actual output -> confirmed keywords match headings not table structure -> Rubber Stamp anti-pattern confirmed

**Acceptance Criteria:**
- [ ] `test_cost_buckets_section_has_table` asserts the actual table header pattern `"| Phase | Input |"`
- [ ] `test_hottest_turns_section_has_table` asserts actual content format (e.g., rank number, timestamp, session cost)
- [ ] Assertions target content within the section, not the heading itself

**Validation Command:**
```bash
python -m pytest tests/test_token_profiler_report.py::TestSectionsPresent -v --no-cov
```

### BJ-004: viewer.py error handling catches wrong exception type
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/cli.py:250-256`
**Status:** OPEN
**Determinism:** theoretical
**Predicted:** Prediction 3 (confidence: HIGH, partially wrong -- template exists)
**Lens:** error-propagation

**Problem:** `cli.py` wraps the viewer import and generation in `try/except ImportError`. If `viewer.py` imports correctly but the template file `viewer_template.html` is missing or unreadable, the actual exception would be `FileNotFoundError` (from `TEMPLATE_PATH.read_text()`), not `ImportError`. Currently the template file exists, so this never fires. But if the template is moved, deleted, or the package is installed without it, the exception escapes the handler and crashes the CLI instead of gracefully skipping HTML generation.

**Evidence:** `cli.py:250`: `except ImportError:` -- only catches import failures. `viewer.py:13`: `template = TEMPLATE_PATH.read_text()` -- raises `FileNotFoundError` if template missing. The template currently exists at `scripts/token_profiler/viewer_template.html`.

**Discovery Chain:** read viewer.py -> template loaded via `Path.read_text()` -> cli.py catches ImportError only -> FileNotFoundError would escape -> confirmed wrong exception type

**Acceptance Criteria:**
- [ ] CLI catches `(ImportError, FileNotFoundError, OSError)` around viewer generation
- [ ] Test verifies graceful degradation when template is missing

**Validation Command:**
```bash
PYTHONPATH=scripts python -c "
import os, tempfile
os.rename('scripts/token_profiler/viewer_template.html', '/tmp/_holtz_viewer_template.html')
try:
    from token_profiler.cli import main
    main(['--html', '--latest'])
except FileNotFoundError as e:
    print(f'BUG CONFIRMED: {e}')
except SystemExit:
    pass
finally:
    os.rename('/tmp/_holtz_viewer_template.html', 'scripts/token_profiler/viewer_template.html')
"
```

### BJ-005: mask_code_fences implementations disagree on fence delimiter treatment
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/_common.py:103-155`, `skills/holtz/scripts/markdown_utils.py:21-57`
**Status:** OPEN
**Predicted:** Prediction 5 (confidence: MEDIUM)
**Lens:** integration

**Problem:** `hooks/_common.py::mask_fenced_blocks` preserves fence delimiter lines (opening and closing fence markers remain in output) but blanks content lines. `skills/holtz/scripts/markdown_utils.py::mask_code_fences` blanks ALL lines including fence delimiters. Both implementations exist independently to avoid cross-layer imports. However, they produce different masked output for the same input. Currently this does not cause a functional bug because no logic depends on fence delimiter presence/absence. However, any future code that assumes masked output format is consistent between the two implementations will fail silently.

**Evidence:** Test:
```python
from hooks._common import mask_fenced_blocks
result = mask_fenced_blocks("line1\n```python\ncode\n```\nline5")
# Result: line1, ```python, (blank), ```, line5  -- delimiters preserved

from skills.holtz.scripts.markdown_utils import mask_code_fences
_, masked = mask_code_fences("line1\n```python\ncode\n```\nline5")
# Result: line1, (blank), (blank), (blank), line5  -- delimiters blanked
```

**Discovery Chain:** read both masking implementations -> tested with same input -> fence delimiters preserved in hooks version, blanked in scripts version -> confirmed behavioral divergence

**Acceptance Criteria:**
- [ ] Both implementations agree on fence delimiter treatment (either both preserve or both blank)
- [ ] Integration test confirms agreement on a set of representative inputs

**Validation Command:**
```bash
python -m pytest tests/test_fence_masking_agreement.py -v --no-cov
```

### BJ-006: test_token_profiler_report TestSummaryFormatting checks format, not computed values
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:TestSummaryFormatting`
**Status:** OPEN
**Lens:** test audit

**Problem:** `TestSummaryFormatting` tests verify that specific formatted strings appear in the output (e.g., `"| Total billed tokens | 2,400 |"`). While this is better than just checking heading presence, the values come from the manually constructed `_make_single_session_run()` fixture, not from the pipeline. The test confirms the report correctly formats the value `2400` as `"2,400"` -- but never verifies that `2400` is the correct billed token count for the given input. If the rollup calculation in `build_run_profile` were wrong but the report faithfully formatted the wrong number, this test would pass. The test is a formatting test wearing a correctness test's clothes.

**Evidence:** `_make_single_session_run` manually constructs `CrossSessionSummary(total_billed_tokens=2400, ...)`. The test asserts `"| Total billed tokens | 2,400 |" in md`. The value 2400 was hand-picked by the test author; no computation derives it from the input data. The test would pass with any billed token value as long as the fixture is updated to match.

**Discovery Chain:** reviewed test assertions -> values come from manually constructed fixture -> no computation chain from input to expected output -> Rubber Stamp variant: format-check with synthetic values

**Acceptance Criteria:**
- [ ] At least one test verifies that the billed token count in the report matches the sum of bucket breakdowns from the input turns
- [ ] Expected values are derived from input data, not hardcoded in fixtures

**Validation Command:**
```bash
python -m pytest tests/test_token_profiler_report.py::TestSummaryFormatting -v --no-cov
```

### BJ-007: README "What this looks like in practice" section has test coverage gap
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_integration.py:test_readme_metrics_match_actual`
**Status:** OPEN
**Lens:** public-contract

**Problem:** The automated README tests cover the "What's inside" line (test_readme_metrics_match_actual) and lens/anti-pattern counts (test_readme_prose_counts_match_actual), but do NOT cover narrative claims like "Eighteen runs" (line 160) or "After 18 runs: 640 tests across 13,900 lines" (line 190). These narrative claims drift every run and require manual updates. The escalated recommendation from 5 consecutive runs (pre-commit hook or generator) remains unaddressed.

**Evidence:** `test_readme_metrics_match_actual` parses the regex pattern for the "What's inside" line only. `test_readme_prose_counts_match_actual` only checks lens and anti-pattern word-form numbers. Neither test checks the "What this looks like in practice" section.

**Discovery Chain:** ran both README tests -> both pass -> grepped for "Eighteen runs" -> stale value not caught by tests -> test coverage gap confirmed

**Acceptance Criteria:**
- [ ] Automated test covers the narrative run count claims on README lines 160 and 190
- [ ] OR: pre-commit hook auto-generates these values from git/test metadata

**Validation Command:**
```bash
python -m pytest tests/test_integration.py -k readme -v --no-cov
```

### BJ-008: apply_phase_labels discards milestone labels when plugin returns partial coverage
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/token_profiler/analyze.py:265-274`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract

**Problem:** When both milestones and a plugin are provided to `apply_phase_labels()`, the function applies milestones first, then overwrites ALL labels with plugin results. If the plugin provides partial coverage (only some turn indices), uncovered turns revert to "unknown" -- losing the milestone labels. The docstring says "Priority: plugin.label_phases() > milestones > 'unknown'", implying that uncovered turns should fall through to milestones, but the implementation replaces the entire labels dict with `{turn.index: "unknown" for turn in turns}` before applying plugin labels.

**Evidence:** `analyze.py:268-274`:
```python
if plugin is not None and hasattr(plugin, "label_phases"):
    plugin_labels = plugin.label_phases(turns)
    if plugin_labels:
        # Start with unknown, then apply plugin labels
        labels = {turn.index: "unknown" for turn in turns}
        for idx, lbl in plugin_labels.items():
            if idx in labels:
                labels[idx] = lbl
```
This resets ALL labels to "unknown" before applying plugin overrides, discarding any milestone labels for turns not covered by the plugin.

**Discovery Chain:** read docstring claiming priority "plugin > milestones > unknown" -> read implementation -> plugin path resets all labels to unknown before patching -> milestone labels lost for uncovered turns -> contract violation

**Acceptance Criteria:**
- [ ] When plugin provides partial coverage, uncovered turns retain milestone labels
- [ ] Test verifies that milestones fill gaps not covered by plugin

**Validation Command:**
```bash
PYTHONPATH=scripts python -c "
from token_profiler.analyze import apply_phase_labels
from token_profiler.models import RawTurn, Usage
turns = [RawTurn(request_id=f'r{i}', index=i, timestamp=None, usage=Usage(), stop_reason='end_turn', content_blocks=[], tool_results=[], assistant_text='', model='x') for i in range(3)]
class P:
    name = 'partial'
    def label_phases(self, turns): return {0: 'plugin_a'}
milestones = [{'start': 1, 'end': 2, 'label': 'from_milestone'}]
labels = apply_phase_labels(turns, milestones=milestones, plugin=P())
print(labels)  # {0: 'plugin_a', 1: 'unknown', 2: 'unknown'} -- milestone labels lost
"
```

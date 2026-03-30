# Holtz Punchlist — Merged
> Generated: 2026-03-25 | Run 20 | Adversarial Self-Play merge
> Holtz findings: 15 | Justine findings: 8 | Merged total: 21

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 2 | 1 |
| MEDIUM | 0 | 4 | 3 |
| LOW | 0 | 11 | 0 |

## Patterns

(none yet)

## Items

### BH-001: README run count stale — "Eighteen runs" → 19
<!-- Was: Holtz BH-001 + Justine BJ-001 -->
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 1 (HIGH) — PAT-005 README-count-drift
**Found by:** both auditors

**Problem:** README says "Eighteen runs" but Run 19 has completed and is archived. Also "After 18 runs: 640 tests across 13,900 lines of code" on line 190 — test count is now 641 and line count is ~17,100.

**Evidence:**
- Line 160: `Holtz has been auditing his own codebase since it was written. Eighteen runs.`
- Line 190: `After 18 runs: 640 tests across 13,900 lines of code.`
- `docs/holtz/archive/2026-03-25-run19/SUMMARY.md` exists (Run 19 completed)
- `python -m pytest --tb=no -q` → 641 passed
- `wc -l` of all Python files → 17,112 lines

**Discovery Chain:** Recon pattern heuristic (PAT-005) → grep README for number words → compared against actual counts → run count, test count, and line count all stale

**Acceptance Criteria:** README line 160 says "Nineteen runs" (or numeric equivalent). Line 190 says "After 19 runs: 641 tests across 17,100 lines of code" (or equivalent).

**Validation Command:** `grep -n "Eighteen\|18 runs\|640 tests\|13,900" README.md` returns no matches

---

### BH-002: README "What's inside" line count stale — 13,900 → ~17,100
<!-- Was: Holtz BH-002 -->
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:216`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 2 (HIGH) — PAT-005 README-count-drift
**Found by:** Holtz only

**Problem:** "What's inside" summary says "641 tests across 13,900 lines of code" — test count is correct but line count is 17,112. This is a user-facing claim about project size that is ~23% understated.

**Evidence:**
- Line 216: `1 skill, 3 agents, 18 reference docs, 1 example, 6 Python scripts, 16 seed patterns, 6 enforcement hooks, 641 tests across 13,900 lines of code`
- `find . -name "*.py" ... | xargs wc -l` → 17,112 total

**Discovery Chain:** P2 predicted README line count drift → verified with wc -l → 13,900 vs 17,112 (3,200 lines added since count was set)

**Acceptance Criteria:** Line 216 says "17,100 lines of code" (rounded to nearest 100).

**Validation Command:** `grep "13,900" README.md` returns no matches

---

### BH-003: Rubber stamp assertions in TestSectionsPresent — structure only, no values
<!-- Was: Holtz BH-003 + Justine BJ-003 -->
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:289-327`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 7 (MEDIUM) — report.py rubber stamps
**Found by:** both auditors

**Problem:** All 9 tests in TestSectionsPresent check only that section headings and table column headers are present in the output. A report with correct headers but entirely wrong numbers passes every test. Specifically: `test_cost_buckets_section_has_table` asserts `"Bucket" in md` — but "Bucket" only appears in the heading, not as a column. `test_hottest_turns_section_has_table` asserts `"Turn" in md` — but "Turn" only appears in the heading "Top 20 Hottest Turns", not as a column header.

**Evidence:** `test_summary_section_has_metrics` (line 293): sole assertion is `"Total API calls" in md`. No computed value verified. `test_cost_buckets_section_has_table`: actual table header is `"| Phase | Input | Cache Create | Cache Read | Output | Total |"` — no "Bucket" column. Both keywords match headings, not table structure.

**Discovery Chain:** Anti-pattern #11 (Rubber Stamp) → TestSectionsPresent class → 9/9 tests assert only string presence → zero mutation-catching power for computed values

**Acceptance Criteria:** At least 3 of 9 tests upgraded to also assert a representative computed value within the section. `test_cost_buckets_section_has_table` asserts actual table header pattern `"| Phase | Input |"`. `test_hottest_turns_section_has_table` asserts actual content format.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestSectionsPresent -v`

---

### BH-004: Choose Your Own Adventure in test_dollar_table_headers
<!-- Was: Holtz BH-004 -->
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_token_profiler_report.py:492-503`
**Status:** RESOLVED
**Lens:** component
**Found by:** Holtz only

**Problem:** Test uses a for-loop and if-chain to locate the Dollar Costs header. Conditional logic inside test body (anti-pattern #14).

**Evidence:** Lines 492-503 contain `for ln in lines:` / `if "## Dollar Costs" in ln:` loop that could be replaced with a direct string assertion.

**Discovery Chain:** Anti-pattern #14 scan → test_token_profiler_report.py → single instance at lines 492-503

**Acceptance Criteria:** Test rewritten without for-loop/if-block in test body.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestDollarCosts::test_dollar_table_headers -v`

---

### BH-005: Time Bomb in test_latest_flag — time.sleep for mtime ordering
<!-- Was: Holtz BH-005 -->
**Severity:** MEDIUM
**Category:** test/fragile
**Location:** `tests/test_token_profiler_cli.py:304-313`
**Status:** RESOLVED
**Lens:** component
**Found by:** Holtz only

**Problem:** Test uses `time.sleep(0.05)` to ensure file mtime ordering. Filesystem mtime resolution on some systems (FAT32, APFS 1-second precision) is coarser than 50ms.

**Evidence:** Line 308: `time.sleep(0.05)` between file creations.

**Discovery Chain:** Anti-pattern #7 (Time Bomb) scan → time.sleep in test body → mtime ordering depends on sub-second filesystem precision

**Acceptance Criteria:** `time.sleep` removed; mtime set explicitly via `os.utime()`.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py::TestResolveSession::test_latest_flag -v`

---

### BH-006: No test for --pricing pipeline behavior
<!-- Was: Holtz BH-006 -->
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_token_profiler_cli.py`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 3 (MEDIUM) — pricing no-op
**Found by:** Holtz only

**Problem:** `--pricing` flag tested only for argument parsing. No test verifies behavior when passed to `main()`.

**Evidence:** `TestParseArgs.test_pricing_flag` (line 143-145) asserts `args.pricing == "custom.json"`. No TestMainEndToEnd test exercises `--pricing`.

**Discovery Chain:** Anti-pattern #9 (Shallow End) → no --pricing in main tests → cross-reference P3 → confirmed gap

**Acceptance Criteria:** At least one test exercises `main([..., "--pricing", "custom.json"])` and asserts expected behavior.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py::TestMainEndToEnd -v -k pricing`

---

### BH-007: All integration tests skip on non-author machines — Mystery Guest
<!-- Was: Holtz BH-007 -->
**Severity:** HIGH
**Category:** test/missing
**Location:** `tests/test_token_profiler_integration.py:22-27`
**Status:** RESOLVED
**Lens:** component
**Found by:** Holtz only

**Problem:** All 8 integration tests depend on a hardcoded session JSONL file path that only exists on the author's machine. All skip silently in CI and on other developer machines. The full pipeline (extract → analyze → report → HTML) is untested in any automated environment.

**Evidence:** Lines 22-27: `SESSION_PATH = Path.home() / ".claude/projects/..."`. All 8 test classes use `skip_if_no_session` fixture.

**Discovery Chain:** Anti-pattern #15 (Mystery Guest) → hardcoded path → skip_if_no_session fixture → 8/8 tests skip in CI

**Acceptance Criteria:** A portable integration test exercises the full pipeline using synthetic JSONL data in tmp_path. Passes in CI with no filesystem preconditions.

**Validation Command:** `python -m pytest tests/test_token_profiler_integration.py -v`

---

### BH-008: Tautology test — test_model_default_unknown supplies the value it asserts
<!-- Was: Holtz BH-008 -->
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_models.py:90-93`
**Status:** RESOLVED
**Lens:** component
**Found by:** Holtz only

**Problem:** Test constructs `RawTurn(model="unknown")` then asserts `turn.model == "unknown"`. Tests Python attribute storage, not default behavior.

**Evidence:** Lines 90-93: explicitly supplies `model="unknown"` then asserts the same value.

**Discovery Chain:** Anti-pattern #1 (Tautology Test) → test sets the value it asserts → no default behavior tested

**Acceptance Criteria:** Test either omits `model=` parameter to test actual default, or is documented as a storage test.

**Validation Command:** `python -m pytest tests/test_token_profiler_models.py::TestRawTurn -v`

---

### BH-009: Permissive validators in report tests — or-based assertion and unbounded presence
<!-- Was: Holtz BH-009 -->
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:420-421, 443-447`
**Status:** RESOLVED
**Lens:** component
**Found by:** Holtz only

**Problem:** `test_turn_entry_format` uses `or`-based assertion: `"x2 remaining" in md or "x1 remaining" in md`. Both values should be present with the fixture data. `test_tool_aggregation` asserts `"Read" in md` — unbounded, would pass if "Read" appeared anywhere.

**Evidence:** Lines 420-421: `or` disjunction allows half the data to be missing. Lines 443-447: `"Read" in md` matches anywhere in output.

**Discovery Chain:** Anti-pattern #12 (Permissive Validator) scan → or-based assertion + unbounded presence check

**Acceptance Criteria:** `or` replaced with `and` (or separate assertions). Tool assertion scoped to the Heat Map section.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestHottestTurns::test_turn_entry_format tests/test_token_profiler_report.py::TestHottestTools::test_tool_aggregation -v`

---

### BH-010: list_sessions crashes on malformed JSONL line
<!-- Was: Holtz BH-010 -->
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/cli.py:218`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** error-propagation
**Found by:** Holtz only

**Problem:** `list_sessions` calls `json.loads(line)` without try/except. A malformed JSONL line crashes `--list` with an unhandled `json.JSONDecodeError`. Sibling function `_read_jsonl` in extract.py wraps the same operation correctly.

**Evidence:** cli.py:218 `obj = json.loads(line)` — no exception handling. Compare extract.py:_read_jsonl which wraps in try/except.

**Discovery Chain:** error-propagation lens → compared json.loads usage across modules → asymmetry between cli.py and extract.py

**Acceptance Criteria:** `list_sessions` wraps `json.loads` in try/except. On malformed line: warns and continues. Never crashes with raw traceback.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py -q`

---

### BH-011: Pricing module fully implemented but never called — dollar costs always $0.00
<!-- Was: Holtz BH-011 -->
<!-- Note: Justine BJ-002 describes the same defect from different line anchors (analyze.py:309,380,398). Counted separately per location-proximity protocol; see BH-012 below. -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/token_profiler/analyze.py:326,471; scripts/token_profiler/cli.py:421`
**Status:** DEFERRED
**Determinism:** deterministic
**Lens:** data-flow, contract
**Predicted:** Prediction 3 (MEDIUM) — pricing no-op
**Found by:** Holtz only

**Problem:** `pricing.py` is complete and tested but never called. `build_session_profile` accepts `pricing_fn` parameter but never invokes it. Phase-level `dollar_cost` fields hardcoded to 0.0. `--pricing` CLI flag loads file then discards with `_ = custom_pricing`. Stale comment: "placeholder until pricing module exists" — but module exists.

**Evidence:** analyze.py:471 `total_dollars=0.0` with comment "placeholder until pricing module exists". cli.py:421 `_ = custom_pricing`.

**Discovery Chain:** P3 prediction → data-flow lens → traced pricing.py callers → zero callers → confirmed stale placeholder

**Acceptance Criteria:** `build_session_profile` calls pricing when model is known. Phase dollar costs populated. Reports show real dollar amounts.

**Validation Command:** `python -m pytest tests/test_token_profiler_pricing.py tests/test_token_profiler_analyze.py -q`

---

### BH-012: Pricing module disconnected from analysis pipeline — dollar costs always $0.00 (Justine perspective)
<!-- Was: Justine BJ-002 -->
<!-- Note: Holtz BH-011 describes the same defect from different line anchors (analyze.py:326,471; cli.py:421). Counted separately per location-proximity protocol; see BH-011 above. -->
**Severity:** HIGH
**Category:** bug/logic
**Location:** `scripts/token_profiler/analyze.py:309,380,398`
**Status:** DEFERRED
**Determinism:** deterministic
**Lens:** data-flow, integration
**Found by:** Justine only

**Problem:** The pricing module (`pricing.py`) implements correct dollar-cost computation with `apply_pricing_to_usage()`, and the analysis pipeline accepts a `pricing_fn` parameter in `build_session_profile()`. However, no caller ever passes `pricing_fn`. All dollar costs in the pipeline are hardcoded to `0.0`: `_build_phase_profiles()` creates `DollarCost(0.0, 0.0, 0.0, 0.0)` at line 380, and `_build_session_summary()` hardcodes `total_dollars=0.0` at line 398. The `--pricing` CLI flag explicitly warns it is "not yet integrated." The pricing module exists, is tested, and is correct, but is dead code in the pipeline.

**Evidence:** `grep -n "pricing_fn\|apply_pricing" scripts/token_profiler/analyze.py` shows only the parameter declaration and docstring reference. `grep -rn "from token_profiler.pricing\|import pricing" scripts/token_profiler/cli.py scripts/token_profiler/analyze.py` returns nothing. The `--pricing` CLI flag warns: "Dollar costs will show $0.00."

**Discovery Chain:** cold file scan found pricing.py tested but not imported → traced callers of `apply_pricing_to_usage` → zero callers outside tests → pipeline hardcodes $0.00 → confirmed dead integration

**Acceptance Criteria:**
- `build_session_profile()` calls `apply_pricing_to_usage()` for each turn's usage
- `_build_phase_profiles()` aggregates actual dollar costs instead of zero
- `_build_session_summary()` sums actual dollar costs
- End-to-end test verifies non-zero dollar amounts in profile output

**Validation Command:** `python -m pytest tests/test_token_profiler_pricing.py tests/test_token_profiler_analyze.py -q`

---

### BH-013: open() without explicit encoding= parameter
<!-- Was: Holtz BH-012 -->
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `scripts/token_profiler/viewer.py:17; hooks/convergence_gate.py:45,86; hooks/convergence_primer.py:27; scripts/token_profiler/cli.py:213+`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** resource-lifecycle
**Predicted:** Prediction 9 (LOW) — open without encoding
**Found by:** Holtz only

**Problem:** Multiple `open()` and `read_text()` calls omit `encoding=` parameter. Default encoding is platform-dependent. Files may contain Unicode (em-dashes, smart quotes).

**Evidence:** viewer.py:17 `TEMPLATE_PATH.read_text()`, hooks/convergence_gate.py:45 `with open(path) as f:`.

**Discovery Chain:** P9 prediction → confirmed in hooks → extended survey → pattern throughout hooks and profiler

**Acceptance Criteria:** All text file `open()` and `read_text()` calls specify `encoding="utf-8"`.

**Validation Command:** `python -m pytest tests/ -q`

---

### BH-014: convergence_check.py silently bypasses timing check on unparseable timestamps
<!-- Was: Holtz BH-013 -->
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/convergence_check.py:320-321`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** error-propagation
**Predicted:** Prediction 8 (LOW) — bare pass
**Found by:** Holtz only

**Problem:** Rapid-fire rejection guard silently skips timing check when timestamps are unparseable. `except (ValueError, TypeError): pass` means corrupted timestamps bypass the anti-gaming check — opposite of the guard's intent.

**Evidence:** Lines 320-321: `except (ValueError, TypeError): pass # Unparseable timestamps — skip timing check`

**Discovery Chain:** P8 prediction → confirmed bare pass → gap between stated purpose (anti-gaming) and exception behavior (skip check)

**Acceptance Criteria:** Unparseable timestamps either warn or conservatively reject. Behavior accurately documented.

**Validation Command:** `python -m pytest tests/test_convergence_check.py -q`

---

### BH-015: _fmt_pct docstring says "fraction" but expects percentage
<!-- Was: Holtz BH-014 -->
**Severity:** LOW
**Category:** doc/drift
**Location:** `scripts/token_profiler/report.py:34-36`
**Status:** RESOLVED
**Lens:** semantic-fidelity
**Found by:** Holtz only

**Problem:** Docstring says "Format a fraction as a percentage string" but function takes a pre-scaled percentage (80.0, not 0.8). All callers correct but docstring is a trap.

**Evidence:** Line 34-36: `def _fmt_pct(f: float) -> str: """Format a fraction as a percentage string.""" return f"{f:.1f}%"`

**Discovery Chain:** semantic-fidelity lens → docstring contradicts implementation → verified callers all pre-scale

**Acceptance Criteria:** Docstring updated to accurately describe the parameter as a pre-scaled percentage.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py -q`

---

### BH-016: @runtime_checkable Protocol unused — parallel duplicate in CLI
<!-- Was: Holtz BH-015 -->
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `scripts/token_profiler/plugin_protocol.py:10; scripts/token_profiler/cli.py:141-195`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 6 (MEDIUM) — interface divergence
**Found by:** Holtz only

**Problem:** `ProfilerPlugin` declared `@runtime_checkable` but `_is_plugin_class` uses manual `hasattr` against hardcoded `_PLUGIN_METHODS` set. Protocol and enforcement are parallel duplicates that can diverge silently.

**Evidence:** plugin_protocol.py: `@runtime_checkable class ProfilerPlugin(Protocol)`. cli.py: `_PLUGIN_METHODS = {"detect", "label_phases", ...}` — manual duplicate.

**Discovery Chain:** P6 prediction → contract lens → @runtime_checkable unused → traced enforcement to _is_plugin_class → confirmed parallel duplicate

**Acceptance Criteria:** CLI uses `isinstance(obj, ProfilerPlugin)` for detection, OR `_PLUGIN_METHODS` derived from Protocol so they can't diverge.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py tests/test_token_profiler_plugin.py -q`

---

### BH-017: viewer.py error handling catches wrong exception type
<!-- Was: Justine BJ-004 -->
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/cli.py:250-256`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** error-propagation
**Found by:** Justine only

**Problem:** `cli.py` wraps the viewer import and generation in `try/except ImportError`. If `viewer.py` imports correctly but the template file `viewer_template.html` is missing or unreadable, the actual exception would be `FileNotFoundError` (from `TEMPLATE_PATH.read_text()`), not `ImportError`. Currently the template file exists, so this never fires. But if the template is moved, deleted, or the package is installed without it, the exception escapes the handler and crashes the CLI instead of gracefully skipping HTML generation.

**Evidence:** `cli.py:250`: `except ImportError:` — only catches import failures. `viewer.py:13`: `template = TEMPLATE_PATH.read_text()` — raises `FileNotFoundError` if template missing. The template currently exists at `scripts/token_profiler/viewer_template.html`.

**Discovery Chain:** read viewer.py → template loaded via `Path.read_text()` → cli.py catches ImportError only → FileNotFoundError would escape → confirmed wrong exception type

**Acceptance Criteria:**
- CLI catches `(ImportError, FileNotFoundError, OSError)` around viewer generation
- Test verifies graceful degradation when template is missing

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py -q`

---

### BH-018: mask_code_fences implementations disagree on fence delimiter treatment
<!-- Was: Justine BJ-005 -->
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/_common.py:103-155`, `skills/holtz/scripts/markdown_utils.py:21-57`
**Status:** DEFERRED
**Lens:** integration
**Found by:** Justine only

**Problem:** `hooks/_common.py::mask_fenced_blocks` preserves fence delimiter lines (opening and closing fence markers remain in output) but blanks content lines. `skills/holtz/scripts/markdown_utils.py::mask_code_fences` blanks ALL lines including fence delimiters. Both implementations exist independently to avoid cross-layer imports. However, they produce different masked output for the same input. Currently this does not cause a functional bug because no logic depends on fence delimiter presence/absence. However, any future code that assumes masked output format is consistent between the two implementations will fail silently.

**Evidence:**
- `hooks._common.mask_fenced_blocks("line1\n```python\ncode\n```\nline5")` → `line1, ```python, (blank), ```, line5` (delimiters preserved)
- `markdown_utils.mask_code_fences("line1\n```python\ncode\n```\nline5")` → `line1, (blank), (blank), (blank), line5` (delimiters blanked)

**Discovery Chain:** read both masking implementations → tested with same input → fence delimiters preserved in hooks version, blanked in scripts version → confirmed behavioral divergence

**Acceptance Criteria:**
- Both implementations agree on fence delimiter treatment (either both preserve or both blank)
- Integration test confirms agreement on a set of representative inputs

**Validation Command:** `python -m pytest tests/test_fence_masking_agreement.py -v --no-cov`

---

### BH-019: TestSummaryFormatting checks format not computed values
<!-- Was: Justine BJ-006 -->
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:TestSummaryFormatting`
**Status:** DEFERRED
**Lens:** test audit
**Found by:** Justine only

**Problem:** `TestSummaryFormatting` tests verify that specific formatted strings appear in the output (e.g., `"| Total billed tokens | 2,400 |"`). While this is better than just checking heading presence, the values come from the manually constructed `_make_single_session_run()` fixture, not from the pipeline. The test confirms the report correctly formats the value `2400` as `"2,400"` — but never verifies that `2400` is the correct billed token count for the given input. If the rollup calculation in `build_run_profile` were wrong but the report faithfully formatted the wrong number, this test would pass.

**Evidence:** `_make_single_session_run` manually constructs `CrossSessionSummary(total_billed_tokens=2400, ...)`. The test asserts `"| Total billed tokens | 2,400 |" in md`. The value 2400 was hand-picked by the test author; no computation derives it from the input data.

**Discovery Chain:** reviewed test assertions → values come from manually constructed fixture → no computation chain from input to expected output → Rubber Stamp variant: format-check with synthetic values

**Acceptance Criteria:**
- At least one test verifies that the billed token count in the report matches the sum of bucket breakdowns from the input turns
- Expected values are derived from input data, not hardcoded in fixtures

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestSummaryFormatting -v --no-cov`

---

### BH-020: README "What this looks like in practice" section has test coverage gap
<!-- Was: Justine BJ-007 -->
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_integration.py:test_readme_metrics_match_actual`
**Status:** RESOLVED
**Lens:** public-contract
**Found by:** Justine only

**Problem:** The automated README tests cover the "What's inside" line (test_readme_metrics_match_actual) and lens/anti-pattern counts (test_readme_prose_counts_match_actual), but do NOT cover narrative claims like "Eighteen runs" (line 160) or "After 18 runs: 640 tests across 13,900 lines" (line 190). These narrative claims drift every run and require manual updates.

**Evidence:** `test_readme_metrics_match_actual` parses the regex pattern for the "What's inside" line only. `test_readme_prose_counts_match_actual` only checks lens and anti-pattern word-form numbers. Neither test checks the "What this looks like in practice" section.

**Discovery Chain:** ran both README tests → both pass → grepped for "Eighteen runs" → stale value not caught by tests → test coverage gap confirmed

**Acceptance Criteria:**
- Automated test covers the narrative run count claims on README lines 160 and 190
- OR: pre-commit hook auto-generates these values from git/test metadata

**Validation Command:** `python -m pytest tests/test_integration.py -k readme -v --no-cov`

---

### BH-021: apply_phase_labels discards milestone labels when plugin returns partial coverage
<!-- Was: Justine BJ-008 -->
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/token_profiler/analyze.py:265-274`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** contract
**Found by:** Justine only

**Problem:** When both milestones and a plugin are provided to `apply_phase_labels()`, the function applies milestones first, then overwrites ALL labels with plugin results. If the plugin provides partial coverage (only some turn indices), uncovered turns revert to "unknown" — losing the milestone labels. The docstring says "Priority: plugin.label_phases() > milestones > 'unknown'", implying that uncovered turns should fall through to milestones, but the implementation replaces the entire labels dict with `{turn.index: "unknown" for turn in turns}` before applying plugin labels.

**Evidence:** `analyze.py:268-274`: resets ALL labels to "unknown" before applying plugin overrides, discarding any milestone labels for turns not covered by the plugin. Docstring contract violated.

**Discovery Chain:** read docstring claiming priority "plugin > milestones > unknown" → read implementation → plugin path resets all labels to unknown before patching → milestone labels lost for uncovered turns → contract violation

**Acceptance Criteria:**
- When plugin provides partial coverage, uncovered turns retain milestone labels
- Test verifies that milestones fill gaps not covered by plugin

**Validation Command:** `python -m pytest tests/test_token_profiler_analyze.py -q`

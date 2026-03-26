# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz (self-audit, Run 20) | Baseline: 641 pass, 0 fail, 0 skip

## Summary

*Note: BH-001 through BH-015 from the component lens pass are resolved/deferred in `PUNCHLIST-MERGED.md` (13 resolved, 2 deferred). Items below are from the lens rotation (BH-016-027).*

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 5 | 0 |
| LOW | 0 | 7 | 0 |

## Patterns

(none yet)

## Items

### BH-001: README run count stale — "Eighteen runs" → 19
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 1 (HIGH) — PAT-005 README-count-drift

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

### BH-002: README "What's inside" line count stale — 13,900 → ~17,100
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:216`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 2 (HIGH) — PAT-005 README-count-drift

**Problem:** "What's inside" summary says "641 tests across 13,900 lines of code" — test count is correct but line count is 17,112. This is a user-facing claim about project size that is ~23% understated.

**Evidence:**
- Line 216: `1 skill, 3 agents, 18 reference docs, 1 example, 6 Python scripts, 16 seed patterns, 6 enforcement hooks, 641 tests across 13,900 lines of code`
- `find . -name "*.py" ... | xargs wc -l` → 17,112 total

**Discovery Chain:** P2 predicted README line count drift → verified with wc -l → 13,900 vs 17,112 (3,200 lines added since count was set)

**Acceptance Criteria:** Line 216 says "17,100 lines of code" (rounded to nearest 100).

**Validation Command:** `grep "13,900" README.md` returns no matches

### BH-003: Rubber stamp assertions in TestSectionsPresent — structure only, no values
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:289-327`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 7 (MEDIUM) — report.py rubber stamps

**Problem:** All 9 tests in TestSectionsPresent check only that section headings and table column headers are present in the output. A report with correct headers but entirely wrong numbers passes every test.

**Evidence:** `test_summary_section_has_metrics` (line 293): sole assertion is `"Total API calls" in md`. No computed value verified.

**Discovery Chain:** Anti-pattern #11 (Rubber Stamp) → TestSectionsPresent class → 9/9 tests assert only string presence → zero mutation-catching power for computed values

**Acceptance Criteria:** At least 3 of 9 tests upgraded to also assert a representative computed value within the section.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestSectionsPresent -v`

### BH-004: Choose Your Own Adventure in test_dollar_table_headers
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_token_profiler_report.py:492-503`
**Status:** RESOLVED
**Lens:** component

**Problem:** Test uses a for-loop and if-chain to locate the Dollar Costs header. Conditional logic inside test body (anti-pattern #14).

**Evidence:** Lines 492-503 contain `for ln in lines:` / `if "## Dollar Costs" in ln:` loop that could be replaced with a direct string assertion.

**Discovery Chain:** Anti-pattern #14 scan → test_token_profiler_report.py → single instance at lines 492-503

**Acceptance Criteria:** Test rewritten without for-loop/if-block in test body.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestDollarCosts::test_dollar_table_headers -v`

### BH-005: Time Bomb in test_latest_flag — time.sleep for mtime ordering
**Severity:** MEDIUM
**Category:** test/fragile
**Location:** `tests/test_token_profiler_cli.py:304-313`
**Status:** RESOLVED
**Lens:** component

**Problem:** Test uses `time.sleep(0.05)` to ensure file mtime ordering. Filesystem mtime resolution on some systems (FAT32, APFS 1-second precision) is coarser than 50ms.

**Evidence:** Line 308: `time.sleep(0.05)` between file creations.

**Discovery Chain:** Anti-pattern #7 (Time Bomb) scan → time.sleep in test body → mtime ordering depends on sub-second filesystem precision

**Acceptance Criteria:** `time.sleep` removed; mtime set explicitly via `os.utime()`.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py::TestResolveSession::test_latest_flag -v`

### BH-006: No test for --pricing pipeline behavior
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_token_profiler_cli.py`
**Status:** RESOLVED
**Lens:** component
**Predicted:** Prediction 3 (MEDIUM) — pricing no-op

**Problem:** `--pricing` flag tested only for argument parsing. No test verifies behavior when passed to `main()`.

**Evidence:** `TestParseArgs.test_pricing_flag` (line 143-145) asserts `args.pricing == "custom.json"`. No TestMainEndToEnd test exercises `--pricing`.

**Discovery Chain:** Anti-pattern #9 (Shallow End) → no --pricing in main tests → cross-reference P3 → confirmed gap

**Acceptance Criteria:** At least one test exercises `main([..., "--pricing", "custom.json"])` and asserts expected behavior.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py::TestMainEndToEnd -v -k pricing`

### BH-007: All integration tests skip on non-author machines — Mystery Guest
**Severity:** HIGH
**Category:** test/missing
**Location:** `tests/test_token_profiler_integration.py:22-27`
**Status:** RESOLVED
**Lens:** component

**Problem:** All 8 integration tests depend on a hardcoded session JSONL file path that only exists on the author's machine. All skip silently in CI and on other developer machines. The full pipeline (extract → analyze → report → HTML) is untested in any automated environment.

**Evidence:** Lines 22-27: `SESSION_PATH = Path.home() / ".claude/projects/..."`. All 8 test classes use `skip_if_no_session` fixture.

**Discovery Chain:** Anti-pattern #15 (Mystery Guest) → hardcoded path → skip_if_no_session fixture → 8/8 tests skip in CI

**Acceptance Criteria:** A portable integration test exercises the full pipeline using synthetic JSONL data in tmp_path. Passes in CI with no filesystem preconditions.

**Validation Command:** `python -m pytest tests/test_token_profiler_integration.py -v`

### BH-008: Tautology test — test_model_default_unknown supplies the value it asserts
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_models.py:90-93`
**Status:** RESOLVED
**Lens:** component

**Problem:** Test constructs `RawTurn(model="unknown")` then asserts `turn.model == "unknown"`. Tests Python attribute storage, not default behavior.

**Evidence:** Lines 90-93: explicitly supplies `model="unknown"` then asserts the same value.

**Discovery Chain:** Anti-pattern #1 (Tautology Test) → test sets the value it asserts → no default behavior tested

**Acceptance Criteria:** Test either omits `model=` parameter to test actual default, or is documented as a storage test.

**Validation Command:** `python -m pytest tests/test_token_profiler_models.py::TestRawTurn -v`

### BH-009: Permissive validators in report tests — or-based assertion and unbounded presence
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:420-421, 443-447`
**Status:** RESOLVED
**Lens:** component

**Problem:** `test_turn_entry_format` uses `or`-based assertion: `"x2 remaining" in md or "x1 remaining" in md`. Both values should be present with the fixture data. `test_tool_aggregation` asserts `"Read" in md` — unbounded, would pass if "Read" appeared anywhere.

**Evidence:** Lines 420-421: `or` disjunction allows half the data to be missing. Lines 443-447: `"Read" in md` matches anywhere in output.

**Discovery Chain:** Anti-pattern #12 (Permissive Validator) scan → or-based assertion + unbounded presence check

**Acceptance Criteria:** `or` replaced with `and` (or separate assertions). Tool assertion scoped to the Heat Map section.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py::TestHottestTurns::test_turn_entry_format tests/test_token_profiler_report.py::TestHottestTools::test_tool_aggregation -v`

### BH-010: list_sessions crashes on malformed JSONL line
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/cli.py:218`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** error-propagation

**Problem:** `list_sessions` calls `json.loads(line)` without try/except. A malformed JSONL line crashes `--list` with an unhandled `json.JSONDecodeError`. Sibling function `_read_jsonl` in extract.py wraps the same operation correctly.

**Evidence:** cli.py:218 `obj = json.loads(line)` — no exception handling. Compare extract.py:_read_jsonl which wraps in try/except.

**Discovery Chain:** error-propagation lens → compared json.loads usage across modules → asymmetry between cli.py and extract.py

**Acceptance Criteria:** `list_sessions` wraps `json.loads` in try/except. On malformed line: warns and continues. Never crashes with raw traceback.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py -q`

### BH-011: Pricing module fully implemented but never called — dollar costs always $0.00
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/token_profiler/analyze.py:326,471; scripts/token_profiler/cli.py:421`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** data-flow, contract
**Predicted:** Prediction 3 (MEDIUM) — pricing no-op

**Problem:** `pricing.py` is complete and tested but never called. `build_session_profile` accepts `pricing_fn` parameter but never invokes it. Phase-level `dollar_cost` fields hardcoded to 0.0. `--pricing` CLI flag loads file then discards with `_ = custom_pricing`. Stale comment: "placeholder until pricing module exists" — but module exists.

**Evidence:** analyze.py:471 `total_dollars=0.0` with comment "placeholder until pricing module exists". cli.py:421 `_ = custom_pricing`.

**Discovery Chain:** P3 prediction → data-flow lens → traced pricing.py callers → zero callers → confirmed stale placeholder

**Acceptance Criteria:** `build_session_profile` calls pricing when model is known. Phase dollar costs populated. Reports show real dollar amounts.

**Validation Command:** `python -m pytest tests/test_token_profiler_pricing.py tests/test_token_profiler_analyze.py -q`

### BH-012: open() without explicit encoding= parameter
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `scripts/token_profiler/viewer.py:17; hooks/convergence_gate.py:45,86; hooks/convergence_primer.py:27; scripts/token_profiler/cli.py:213+`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** resource-lifecycle
**Predicted:** Prediction 9 (LOW) — open without encoding

**Problem:** Multiple `open()` and `read_text()` calls omit `encoding=` parameter. Default encoding is platform-dependent. Files may contain Unicode (em-dashes, smart quotes).

**Evidence:** viewer.py:17 `TEMPLATE_PATH.read_text()`, hooks/convergence_gate.py:45 `with open(path) as f:`.

**Discovery Chain:** P9 prediction → confirmed in hooks → extended survey → pattern throughout hooks and profiler

**Acceptance Criteria:** All text file `open()` and `read_text()` calls specify `encoding="utf-8"`.

**Validation Command:** `python -m pytest tests/ -q`

### BH-013: convergence_check.py silently bypasses timing check on unparseable timestamps
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/convergence_check.py:320-321`
**Status:** RESOLVED
**Determinism:** theoretical
**Lens:** error-propagation
**Predicted:** Prediction 8 (LOW) — bare pass

**Problem:** Rapid-fire rejection guard silently skips timing check when timestamps are unparseable. `except (ValueError, TypeError): pass` means corrupted timestamps bypass the anti-gaming check — opposite of the guard's intent.

**Evidence:** Lines 320-321: `except (ValueError, TypeError): pass # Unparseable timestamps — skip timing check`

**Discovery Chain:** P8 prediction → confirmed bare pass → gap between stated purpose (anti-gaming) and exception behavior (skip check)

**Acceptance Criteria:** Unparseable timestamps either warn or conservatively reject. Behavior accurately documented.

**Validation Command:** `python -m pytest tests/test_convergence_check.py -q`

### BH-014: _fmt_pct docstring says "fraction" but expects percentage
**Severity:** LOW
**Category:** doc/drift
**Location:** `scripts/token_profiler/report.py:34-36`
**Status:** RESOLVED
**Lens:** semantic-fidelity

**Problem:** Docstring says "Format a fraction as a percentage string" but function takes a pre-scaled percentage (80.0, not 0.8). All callers correct but docstring is a trap.

**Evidence:** Line 34-36: `def _fmt_pct(f: float) -> str: """Format a fraction as a percentage string.""" return f"{f:.1f}%"`

**Discovery Chain:** semantic-fidelity lens → docstring contradicts implementation → verified callers all pre-scale

**Acceptance Criteria:** Docstring updated to accurately describe the parameter as a pre-scaled percentage.

**Validation Command:** `python -m pytest tests/test_token_profiler_report.py -q`

### BH-015: @runtime_checkable Protocol unused — parallel duplicate in CLI
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `scripts/token_profiler/plugin_protocol.py:10; scripts/token_profiler/cli.py:141-195`
**Status:** RESOLVED
**Lens:** contract
**Predicted:** Prediction 6 (MEDIUM) — interface divergence

**Problem:** `ProfilerPlugin` declared `@runtime_checkable` but `_is_plugin_class` uses manual `hasattr` against hardcoded `_PLUGIN_METHODS` set. Protocol and enforcement are parallel duplicates that can diverge silently.

**Evidence:** plugin_protocol.py: `@runtime_checkable class ProfilerPlugin(Protocol)`. cli.py: `_PLUGIN_METHODS = {"detect", "label_phases", ...}` — manual duplicate.

**Discovery Chain:** P6 prediction → contract lens → @runtime_checkable unused → traced enforcement to _is_plugin_class → confirmed parallel duplicate

**Acceptance Criteria:** CLI uses `isinstance(obj, ProfilerPlugin)` for detection, OR `_PLUGIN_METHODS` derived from Protocol so they can't diverge.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py tests/test_token_profiler_plugin.py -q`

### BH-016: Three ProfilerPlugin protocol methods never called — dead contract
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/token_profiler/cli.py:349-378`
**Status:** RESOLVED
**Lens:** integration
**Related:** BH-015

**Problem:** `ProfilerPlugin` defines 5 methods. Load-time validation checks all 5 exist. But `cli.py` only calls `detect()` and `label_phases()` (via `build_session_profile`). The other 3 — `name_subagent()`, `enrich_profile()`, `optimization_patterns()` — are never invoked anywhere in the pipeline. Plugin authors implement them (the holtz profiler plugin does), but the orchestrator silently ignores the results.

**Evidence:**
- `grep -rn 'name_subagent\|enrich_profile\|optimization_patterns' scripts/token_profiler/` → only appears in plugin_protocol.py (definition) and cli.py:196 (load-time check). Zero invocations.
- `cli.py:370-378`: subagent loop builds profiles but never calls `plugin.name_subagent(sub_turns)` — `subagent_name` field in `SessionProfile` stays `None`.
- `cli.py:357-378`: neither main nor subagent profile construction calls `plugin.enrich_profile(profile)`.

**Discovery Chain:** Integration lens → traced ProfilerPlugin methods through pipeline → 3/5 methods checked but never called → dead contract

**Acceptance Criteria:** Either (a) `cli.py` calls all 3 methods at appropriate points in the pipeline, or (b) methods removed from the protocol and load-time check if intentionally deferred.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py -q`

### BH-017: Integration test fixture lacks IN PROGRESS item — agreement test blind spot
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_integration.py:7-110`
**Status:** RESOLVED
**Lens:** integration

**Problem:** `SHARED_PUNCHLIST` fixture has items with OPEN, RESOLVED, and DEFERRED status but none with IN PROGRESS. `test_status_distribution_agreement` checks all 5 statuses, but IN PROGRESS always compares 0==0 — a parsing disagreement between `validate_punchlist` and `convergence_check` for IN PROGRESS status would pass undetected. IN PROGRESS items directly affect convergence gate decisions.

**Evidence:**
- `grep "IN PROGRESS" tests/test_integration.py` → appears only in the status list, not in any fixture item
- `test_status_distribution_agreement` line 135: iterates all 5 statuses including IN PROGRESS
- Both parsers return 0 for IN PROGRESS, so agreement is trivially true

**Discovery Chain:** Integration lens → reviewed SHARED_PUNCHLIST fixture → no IN PROGRESS item → agreement test can't detect disagreement for this status

**Acceptance Criteria:** SHARED_PUNCHLIST includes at least one item with `**Status:** IN PROGRESS`. Test verifies non-zero agreement for that status.

**Validation Command:** `python -m pytest tests/test_integration.py::test_status_distribution_agreement -v`

### BH-018: Viewer Turn Table column "Remaining" renders context_window instead
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/token_profiler/viewer.py` (template)
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** integration

**Problem:** The Turn Table in the viewer template labels a column "Remaining" (implying `remaining_calls_in_segment`, a small integer) but renders `t.context_window` (a large token count). The sort key also maps to `context_window`. The `remaining_calls_in_segment` field — which determines the session cost formula — is not shown in the table at all.

**Evidence:** viewer_template.html column header says "Remaining", data cell renders `t.context_window`.

**Discovery Chain:** Integration lens → viewer template column labels → "Remaining" header → data binding renders wrong field → semantic mismatch

**Acceptance Criteria:** Column either labelled "Context Window" (matching the data) or rendered from `remaining_calls_in_segment` (matching the label).

**Validation Command:** Manual inspection of viewer HTML output.

### BH-019: Subagent milestones silently dropped
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/token_profiler/cli.py:372-377`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** integration

**Problem:** `cli.py` passes `milestones=milestones` to `build_session_profile` for the main session (line 362) but omits it for subagent sessions (line 372-377, defaults to `None`). All subagent turns are labelled `"unknown"` regardless of user-supplied milestone files, with no warning.

**Evidence:** cli.py:362 `milestones=milestones` (main). cli.py:372-377 no milestones argument (subagent).

**Discovery Chain:** Integration lens → compared main vs subagent profile construction → milestones parameter missing in subagent path

**Acceptance Criteria:** Either subagent loop passes milestones, or documents that milestones are main-session only.

**Validation Command:** `python -m pytest tests/test_token_profiler_cli.py -q`

### BH-020: @property fields absent from profile.json serialization
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `scripts/token_profiler/analyze.py; scripts/token_profiler/cli.py:400-403`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** integration

**Problem:** `BucketBreakdown.total` and `DollarCost.total_cost` are `@property` methods. `dataclasses.asdict()` (cli.py:400) does not serialize `@property` methods. These computed fields exist in Python but are silently absent from `profile.json`. Downstream consumers expecting a `total` key won't find it.

**Evidence:** `dataclasses.asdict()` only serializes dataclass fields, not properties. `BucketBreakdown.total` is a property.

**Discovery Chain:** Integration lens → profile.json serialization → dataclasses.asdict → @property not included → field absent from JSON

**Acceptance Criteria:** Either properties replaced with computed dataclass fields, or a custom serializer includes them, or documented as Python-only.

**Validation Command:** `python -c "from dataclasses import asdict; from token_profiler.models import BucketBreakdown; print('total' in asdict(BucketBreakdown()))"`

### BH-021: convergence_gate._count_open_items is a third independent punchlist parser
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/convergence_gate.py`
**Status:** RESOLVED
**Lens:** integration
**Related:** PAT-004

**Problem:** `convergence_gate.py` has `_count_open_items()` — a third independent implementation of punchlist item counting alongside `validate_punchlist.parse_punchlist()` and `convergence_check.count_items()`. The existing fence-masking agreement test covers only the masker pair, not the item-boundary + status-parsing logic layered above it. The gate's own comment calls its count "approximate," but it drives enforcement decisions.

**Evidence:** Three independent implementations of punchlist status parsing, each with their own regex patterns. Integration test only covers vp↔cc agreement, not gate.

**Discovery Chain:** Integration lens → counted punchlist parsers → three independent implementations → only two covered by agreement test

**Acceptance Criteria:** Either (a) gate delegates to one of the canonical parsers, or (b) a third agreement test covers gate↔canonical parser agreement.

**Validation Command:** `python -m pytest tests/test_integration.py -q`

### BH-022: Viewer HTML renders JSONL-derived data via innerHTML without escaping
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `scripts/token_profiler/viewer_template.html` (multiple lines)
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** security

**Problem:** The HTML viewer injects JSONL-derived string fields (phase names, tool names, descriptions, session IDs, model names) directly into `innerHTML` via template literals with no HTML escaping. `json.dumps` in `viewer.py` prevents escaping out of the JS assignment, but once data is in JS, those strings hit `innerHTML` raw. A session file where Claude Code interacted with a server that injected `<img src=x onerror=...>` into a tool response would execute arbitrary JS in the local browser when the viewer opens.

**Evidence:** 10+ `innerHTML` assignments, 0 `textContent` uses. Template literals like `` wrap.innerHTML = `<div class="heatstrip-label">${label}` `` inject unsanitized data.

**Discovery Chain:** Security lens → traced JSONL data through viewer pipeline → json.dumps escapes JS context → but innerHTML consumes data-derived strings without HTML escaping → XSS at file:// context

**Acceptance Criteria:** Add an `esc()` helper that HTML-encodes `<>&"` characters. Apply to all data-derived values in template literals. Use `textContent` where possible.

**Validation Command:** Manual inspection of generated HTML output with crafted session data.

### BH-023: extract_session() ValueError crashes CLI with raw traceback
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `scripts/token_profiler/cli.py:349,371`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** error-propagation

**Problem:** `extract_session()` raises `ValueError` on corrupt JSONL, but `main()` has no try/except around the calls at lines 349 and 371. Malformed session or subagent JSONL crashes with a raw Python traceback instead of a clean error message + exit code 1. Asymmetric with `resolve_session()` which uses `SystemExit(1)` with a clear message.

**Evidence:** cli.py:349 `raw_turns_main = extract_session(session_path)` — no try/except. cli.py:371 `sub_turns = extract_session(sub_path)` — no try/except.

**Discovery Chain:** Error-propagation lens → traced ValueError from extract.py through cli.py → no catch → raw traceback

**Acceptance Criteria:** Malformed JSONL produces a clean error message (e.g., "Error: could not parse session file: {path}: {reason}") and exit code 1.

**Validation Command:** `echo "not json" > /tmp/bad.jsonl && python -m token_profiler /tmp/bad.jsonl 2>&1; echo "exit: $?"`

### BH-024: ImpactGraph methods return error dicts instead of raising exceptions
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/impact_graph.py:138-141,230-233,253-254`
**Status:** RESOLVED
**Lens:** contract

**Problem:** `add_edge()`, `update_risk()`, and `prune_node()` return `{"error": "..."}` sentinel dicts on failure instead of raising exceptions. Library callers who don't check `"error" in result` silently get a no-op — no edge created, no risk updated, no node pruned. The CLI dispatcher handles this, but programmatic callers (if any) would miss errors silently.

**Evidence:** impact_graph.py:138 `return {"error": f"Source node '{source}' does not exist"}`. Same pattern at lines 230, 253.

**Discovery Chain:** Contract lens → compared documented return types → error dict sentinel pattern → callers don't check for error key

**Acceptance Criteria:** Either (a) methods raise ValueError/KeyError on invalid input, or (b) return type annotated as union with error dict and callers check, or (c) documented as CLI-only pattern.

**Validation Command:** `python -m pytest tests/ -q`

### BH-025: ImpactGraph.load() silently resets on corrupt JSON — data loss
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/impact_graph.py`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** error-propagation, observability

**Problem:** `ImpactGraph.load()` catches `json.JSONDecodeError` and silently resets nodes/edges to empty with no stderr warning. A corrupt graph file causes silent data loss — the next `save()` overwrites the corrupt file with an empty graph. Compare: `load_history()` in convergence_check.py prints a WARNING before returning empty.

**Evidence:** load() catches JSONDecodeError and resets to `{}`/`[]` silently.

**Discovery Chain:** Error-propagation lens → traced load error path → silent reset → next save overwrites → data loss

**Acceptance Criteria:** Corrupt graph triggers a stderr warning before resetting (matching convergence_check.py convention).

**Validation Command:** `echo "corrupt" > /tmp/test-graph.json && python -c "from impact_graph import ImpactGraph; g = ImpactGraph('/tmp/test-graph.json'); print(len(g.nodes))"`

### BH-026: artifact_verification says "BLOCKED" but doesn't block
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/artifact_verification.py:49-52`
**Status:** RESOLVED
**Lens:** semantic-fidelity

**Problem:** The hook calls `exit_warn()` (which sets `"continue": true` — allows the action) but the message text begins with "BLOCKED:". This is a PostToolUse hook — the tool already ran, so blocking isn't possible. The message implies prevention that didn't happen.

**Evidence:** Line 49-52: `exit_warn("BLOCKED: impact_graph.py ran but {graph_rel} does not exist on disk...")`. `exit_warn` sets `continue: true`.

**Discovery Chain:** Semantic-fidelity lens → hook message says "BLOCKED" → exit_warn allows continuation → semantic mismatch

**Acceptance Criteria:** Message text changed from "BLOCKED:" to "WARNING:" or similar — accurately reflecting that this is advisory, not blocking.

**Validation Command:** `grep -n "BLOCKED" hooks/artifact_verification.py`

### BH-027: count_items calls sys.exit(2) on missing file instead of raising
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py`
**Status:** RESOLVED
**Lens:** semantic-fidelity, contract

**Problem:** `count_items()` is named as a data-returning function but calls `sys.exit(2)` when the punchlist file is missing. A programmatic caller expecting a dict gets process termination. Compare: `validate_punchlist.parse_punchlist()` raises ValueError for invalid input.

**Evidence:** Function named `count_items` (implies data return) but contains `sys.exit(2)` on error path.

**Discovery Chain:** Semantic-fidelity lens → function name implies data return → sys.exit on error path → breaks caller expectations

**Acceptance Criteria:** Either raise FileNotFoundError (letting callers decide), or document the sys.exit behavior in the docstring.

**Validation Command:** `python -m pytest tests/test_convergence_check.py -q`

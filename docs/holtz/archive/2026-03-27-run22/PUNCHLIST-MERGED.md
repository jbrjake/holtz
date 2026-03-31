# Merged Punchlist — Run 31

> Generated: 2026-03-26 | Merge: Holtz + Justine | Branch: dev

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 7    | 0        | 0        |
| MEDIUM   | 6    | 0        | 0        |
| LOW      | 4    | 0        | 0        |

## Agreements (Both Found)

### BH-001: Gate SQL uses JSON arrow syntax but Sahjhan uses flat columns
**Severity:** HIGH
**Category:** bug/config
**Location:** `enforcement/transitions.toml:14,75`
**Status:** OPEN
**Found by:** Holtz (BH-001), Justine (BJ-002 partial — identified as part of mypy gate blocker)
**Perspective:** component

**Problem:** Gate queries use `fields->>'step'` and `fields->>'command'` (PostgreSQL JSON arrow syntax) but Sahjhan flattens event fields into top-level columns. Queries fail with schema errors, blocking all query-gated transitions.

**Discovery Chain:** Gate check for recon_complete returned schema error → inspected transitions.toml → found JSON arrow syntax → confirmed Sahjhan uses flat column schema

**Acceptance Criteria:**
- [ ] All SQL queries in transitions.toml use column names directly (e.g., `step` not `fields->>'step'`)
- [ ] `sahjhan gate check recon_complete` SQL gate passes

**Validation Command:** `./bin/sahjhan gate check recon_complete 2>&1 | grep -c "query returned"`

---

### BH-002: Gate commands reference ${CLAUDE_PLUGIN_ROOT} — breaks in dev/non-plugin contexts
**Severity:** MEDIUM
**Category:** bug/config
**Location:** `enforcement/transitions.toml:18,29,123,133,172,174`
**Status:** OPEN
**Found by:** Holtz (BH-002), Justine (BJ-002, BJ-005)
**Predicted:** Prediction 3 (HIGH)
**Perspective:** integration

**Problem:** Six gate conditions in transitions.toml use `${CLAUDE_PLUGIN_ROOT}` for script paths. When not installed as a plugin (dev mode, CI, standalone), the variable is unset and commands fail with exit 127. Affects: snapshot_compare, command_output (validate_punchlist), command_succeeds (mypy invocations).

Additionally, the `mypy skills/holtz/scripts/ hooks/ enforcement/hooks/` command in gates always fails due to duplicate `_common` module name. This blocks `perspective_clean` and `final_sweep_clean` transitions — convergence is unreachable.

**Discovery Chain:** recon_complete gate check → command_succeeds exit 127 → CLAUDE_PLUGIN_ROOT not set → traced to 6 locations → also found mypy duplicate module collision

**Acceptance Criteria:**
- [ ] Gates work without CLAUDE_PLUGIN_ROOT (use relative paths or resolve at runtime)
- [ ] mypy invocation uses `--explicit-package-bases` or equivalent
- [ ] Same fix in CLAUDE.md and .github/workflows/ci.yml

**Validation Command:** `./bin/sahjhan gate check converge 2>&1`

---

### BH-003: README describes 3 deleted hooks as current features
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:200-211`
**Status:** OPEN
**Found by:** Holtz (BH-003), Justine (BJ-004, BJ-009)
**Predicted:** Prediction 2 (HIGH)
**Perspective:** public-contract

**Problem:** README "The hooks" section describes impact_graph_gate, status_staleness_gate, and artifact_verification as active features. All three were deleted and replaced by Sahjhan enforcement engine. Also, none of the new enforcement hooks (bash_guard, write_guard, stop_gate, primer) are described.

**Discovery Chain:** Impact graph prune removed 15 nodes for deleted hooks → README still describes them → README does not describe replacements

**Acceptance Criteria:**
- [ ] README "The hooks" section describes actual current hooks
- [ ] Deleted hooks removed from README
- [ ] New enforcement hooks described

**Validation Command:** `grep -c "impact_graph_gate\|status_staleness_gate\|artifact_verification" README.md` (should be 0)

---

### BH-009: write_guard blocks ALL docs/holtz/ writes — breaks audit workflow
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/write_guard.py:18-20`
**Status:** OPEN
**Found by:** Holtz (BH-009), Justine (BJ-003)
**Predicted:** Prediction 1 (HIGH)
**Perspective:** security

**Problem:** MANAGED_PATHS = ["docs/holtz"] blocks ALL writes to docs/holtz/ but only sahjhan-rendered files (STATUS.md, PUNCHLIST.md, SUMMARY.md, etc.) should be blocked. Blocks legitimate writes to recon/, audit/, impact-graph.json, architecture-baseline.md, LIVING-PUNCHLIST.md, patterns-brief.md, and Justine's output directory.

**Discovery Chain:** Step 0 architectural analysis → write_guard source review → MANAGED_PATHS too broad → confirmed blocks all audit output

**Acceptance Criteria:**
- [ ] write_guard blocks only sahjhan-rendered files (STATUS.md, PUNCHLIST.md, SUMMARY.md, MERGE-REPORT.md, PUNCHLIST-MERGED.md)
- [ ] Legitimate audit writes (recon/, audit/, impact-graph.json) NOT blocked

**Validation Command:** Test with a Write to docs/holtz/recon/test.md — should NOT be blocked

---

## Holtz Only

### BH-007: bash_guard violation recording uses wrong CLI argument format
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/bash_guard.py:66-74`
**Status:** OPEN
**Found by:** Holtz
**Predicted:** Prediction 1 (HIGH)
**Perspective:** component

**Problem:** Uses `--file_path` and `--detail` as direct CLI args but sahjhan requires `--field key=value` syntax. Violation events silently fail to record.

**Discovery Chain:** Read bash_guard source → saw `--file_path` arg → tested with sahjhan CLI → confirmed "unexpected argument" error

**Acceptance Criteria:**
- [ ] violation_cmd uses `--field file_path=...` and `--field detail=...`
- [ ] Also needs `--field project=holtz --field run=... --field auditor=holtz`

**Validation Command:** `./bin/sahjhan event protocol_violation --field project=holtz --field run=31 --field auditor=holtz --field file_path=test --field detail=test`

---

### BH-008: primer.py context_reset uses wrong CLI argument format
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/primer.py:78-81`
**Status:** OPEN
**Found by:** Holtz
**Predicted:** Prediction 1 (HIGH)
**Perspective:** component

**Problem:** Uses `--trigger` as direct CLI arg but sahjhan requires `--field trigger=value`. context_reset events fail to record, breaking the awaiting_clear→fix_loop gate.

**Discovery Chain:** Read primer source → saw `--trigger` arg → tested with sahjhan CLI → confirmed "unexpected argument" error

**Acceptance Criteria:**
- [ ] reset_cmd uses `--field trigger=user_prompt_submit` (plus project, run, auditor)
- [ ] context_reset events actually appear in ledger after UserPromptSubmit

**Validation Command:** `./bin/sahjhan event context_reset --field project=holtz --field run=31 --field auditor=holtz --field trigger=user_prompt_submit`

---

### BH-013: bash_guard violation also missing required fields
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/bash_guard.py:62-76`
**Status:** OPEN
**Found by:** Holtz
**Predicted:** Prediction 1 (HIGH)
**Perspective:** component

**Problem:** Even with fixed CLI syntax, protocol_violation event requires `project`, `run`, `auditor` fields per events.toml — bash_guard doesn't pass these. Double bug: wrong format AND missing fields.

**Discovery Chain:** Read events.toml → protocol_violation requires project/run/auditor → bash_guard only passes file_path/detail

**Acceptance Criteria:**
- [ ] violation_cmd includes all required fields
- [ ] Uses `--field` syntax

**Validation Command:** N/A (part of BH-007 fix)

---

### BH-015: PermissionError uncaught in three enforcement hooks
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `enforcement/hooks/bash_guard.py:56, stop_gate.py:48, primer.py:56`
**Status:** OPEN
**Found by:** Holtz (BH-015), subagent (F-03)
**Predicted:** Prediction 1 (HIGH)
**Perspective:** error-propagation

**Problem:** Three hooks catch only (FileNotFoundError, TimeoutExpired) but PermissionError (binary exists but not executable) is uncaught. Crashes hook process with no JSON output.

**Discovery Chain:** Code audit → exception clause review → PermissionError is OSError subclass, not FileNotFoundError → uncaught

**Acceptance Criteria:**
- [ ] All three hooks catch `(OSError, subprocess.TimeoutExpired)` instead

**Validation Command:** `python -c "raise PermissionError()" 2>&1 | grep -c PermissionError`

---

### BH-014: Path prefix collision in write_guard and bootstrap
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/write_guard.py:35, _sahjhan_bootstrap.py:49`
**Status:** OPEN
**Found by:** Holtz subagent (F-01, F-02)
**Predicted:** Prediction 1 (HIGH)
**Perspective:** security

**Problem:** `startswith(full)` without trailing separator means `docs/holtz2` or `enforcement_evil` would match. Over-blocking only (not a security bypass).

**Discovery Chain:** Code review → startswith without os.sep → tested: `/repo/docs/holtz2/x.md`.startswith(`/repo/docs/holtz`) == True

**Acceptance Criteria:**
- [ ] All startswith checks use `full + os.sep` or `full + "/"`

**Validation Command:** Test write to hypothetical `docs/holtz2/test.md` — should NOT be blocked

---

### BH-004: README counts stale (PAT-005 recurring)
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:7,190,216`
**Status:** OPEN
**Found by:** Holtz (BH-004), Justine (BJ-004)
**Predicted:** Prediction 2 (HIGH)
**Perspective:** public-contract

**Problem:** PAT-005 recurring 7th+ run. 14,300 lines (actual 18,151), 19 runs (actual 30+), 647 tests badge, 65% coverage (actual 76%).

**Acceptance Criteria:**
- [ ] All counts in README match reality
- [ ] test_readme_metrics_match_actual passes

**Validation Command:** `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v`

---

### BH-005: Architecture baseline lists deleted modules
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/holtz/architecture-baseline.md:70-73`
**Status:** OPEN
**Perspective:** semantic-fidelity

**Problem:** Module Dependencies table lists impact_graph_gate.py, status_staleness_gate.py, artifact_verification.py as active. All deleted.

**Acceptance Criteria:**
- [ ] Deleted modules removed from baseline
- [ ] enforcement/hooks/ modules added

**Validation Command:** `grep -c "impact_graph_gate\|status_staleness_gate\|artifact_verification" docs/holtz/architecture-baseline.md` (should be 0 in Module Dependencies)

---

### BH-016: PAT-001 in migrate_legacy.py — 3 functions parse without fence masking
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/migrate_legacy.py:160-168,295-298,420-430`
**Status:** OPEN
**Found by:** Holtz (BH-016), Justine (BJ-001)
**Predicted:** Prediction 4 (MEDIUM)
**Perspective:** data-flow

**Problem:** PAT-001: _extract_field, _parse_predictions, and _is_table_format apply regex to raw markdown. Code-fenced content could cause phantom events in JSONL ledger.

**Acceptance Criteria:**
- [ ] Import and apply masking before regex extraction
- [ ] Test with code-fenced content

**Validation Command:** `grep -c 'mask_code_fences\|mask_fenced_blocks' scripts/migrate_legacy.py` (should be > 0)

---

### BH-017: parse_summary greedy regex extracts wrong counts
**Severity:** HIGH
**Category:** bug/logic
**Location:** `scripts/migrate_legacy.py:561-567`
**Status:** OPEN
**Found by:** Holtz subagent (F-11)
**Predicted:** Prediction 4 (MEDIUM)
**Perspective:** data-flow

**Problem:** `re.search(r'total.*?(\d+)')` on content with "Total Resolved: 7" before "Total Findings: 10" extracts 7 as total.

**Acceptance Criteria:**
- [ ] Regex anchored to actual SUMMARY.md field format
- [ ] Test with summary containing "Total Resolved" before "Total Findings"

**Validation Command:** `python -c "import re; c='Total Resolved: 7\nTotal Findings: 10'; print(re.search(r'total.*?(\d+)', c, re.I).group(1))"` (should print 10, currently prints 7)

---

## Justine Only

### BH-006: Coverage badge stale (65% → 76%)
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:7`
**Status:** OPEN
**Found by:** Holtz (BH-006)
**Perspective:** public-contract

**Problem:** Coverage badge says 65%, actual is 76%. Part of PAT-005 README drift.

**Acceptance Criteria:**
- [ ] Badge reflects actual coverage percentage

**Validation Command:** Visual inspection of README badge

---

### BH-010: Enforcement hook tests only exercise "no binary" path
**Severity:** LOW (downgraded — test quality, not bug)
**Category:** test/shallow
**Location:** `tests/test_sahjhan_integration.py:188-242`
**Status:** OPEN
**Found by:** Holtz Step 7

**Problem:** 8 tests across TestBashGuard, TestStopGate, TestPrimer only exercise the "binary not installed" early-exit. Real guard logic never tested in CI.

**Acceptance Criteria:**
- [ ] Tests restructured to mock or skip when binary absent
- [ ] At least one test per hook exercises the actual guard logic

**Validation Command:** `python -m pytest tests/test_sahjhan_integration.py -v`

---

### BH-011: test_finding_rejects_invalid_id_pattern conditionally asserts
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_jsonl_integration.py:389-411`
**Status:** OPEN

**Problem:** Passes with zero assertions when sahjhan accepts invalid IDs.

**Acceptance Criteria:**
- [ ] Assertion is unconditional

**Validation Command:** `python -m pytest tests/test_jsonl_integration.py::test_finding_rejects_invalid_id_pattern -v`

---

### BH-012: Token profiler integration tests hardcoded to one machine
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_integration.py:22-27`
**Status:** OPEN

**Problem:** 8 test classes depend on session file at specific absolute path. Always skipped on other machines.

**Acceptance Criteria:**
- [ ] Machine-specific tests marked with pytest marker and documented

**Validation Command:** `python -m pytest tests/test_token_profiler_integration.py -v 2>&1 | grep -c "skipped"`

---

## Merge Report

| Classification | Count |
|---------------|-------|
| Agreements | 5 (BH-001/BJ-002, BH-002/BJ-002+BJ-005, BH-003/BJ-004+BJ-009, BH-009/BJ-003, BH-016/BJ-001) |
| Holtz only | 8 (BH-007, BH-008, BH-013, BH-014, BH-015, BH-010, BH-011, BH-012) |
| Justine only | 4 (BJ-006 coverage gap, BJ-007 subagent_findings_check, BJ-008 error suppression, BJ-009 README prose) — incorporated into BH-003/BH-004 |
| Contradictions | 0 |
| **Total unique items** | **17** |

### Blind Spot Analysis
- **Holtz missed:** None unique — all Justine findings overlap or extend Holtz findings
- **Justine missed:** BH-007/BH-008 (wrong CLI arg format), BH-015 (PermissionError), BH-013 (missing required fields), BH-014 (path prefix collision) — Justine flagged the enforcement hooks as problematic but didn't test specific CLI interactions or exception types

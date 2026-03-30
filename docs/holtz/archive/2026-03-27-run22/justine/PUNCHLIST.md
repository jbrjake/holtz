# Justine Punchlist

> Generated: 2026-03-26 | Run: 31 | Auditor: Justine | Branch: dev

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 4    | 0        | 0        |
| MEDIUM   | 4    | 0        | 0        |
| LOW      | 1    | 0        | 0        |

## Patterns

## Pattern: PAT-001: Code-fence-unaware parsing

**Instances:** BJ-001
**Root Cause:** Regex applied to raw markdown content without masking code fences. `migrate_legacy.py` has 12+ regex calls on unmasked `content` parameters across 8 parser functions. None import or call `mask_code_fences` or `mask_fenced_blocks`.
**Systemic Fix:** Add masking layer to migrate_legacy.py or document as intentional (migration data is historical and won't contain adversarial content).
**Detection Rule:** `grep -rn 'mask_code_fences\|mask_fenced_blocks' scripts/migrate_legacy.py`

## Pattern: PAT-005: README-count-drift

**Instances:** BJ-004
**Root Cause:** Numeric literals in README.md for dynamically-growing counts. No automated sync.
**Systemic Fix:** Update README counts or automate via CI.
**Detection Rule:** Run `test_readme_metrics_match_actual`

## Items

### BJ-001: migrate_legacy.py parses markdown without code-fence masking (PAT-001)
**Severity:** HIGH
**Category:** bug/logic
**Location:** `scripts/migrate_legacy.py` (all parser functions)
**Status:** OPEN
**Pattern:** PAT-001
**Determinism:** deterministic

**Problem:** All 8 parser functions in `migrate_legacy.py` apply regex to raw markdown content without code-fence masking. The functions `parse_punchlist`, `_parse_table_punchlist`, `_parse_block_punchlist`, `parse_recon_dir`, `parse_audit_file`, `_parse_claims_table`, `_parse_test_findings`, `_parse_code_findings`, `parse_summary`, and `_parse_predictions` all operate on raw `content` strings. If any archived markdown file contains a code fence with content that matches the parsing patterns (e.g., a `### BH-001:` header inside a code example), the parser will emit phantom events.

This is the same root cause as PAT-001 instances BH-003, BH-004, BH-005, BH-006, which were found and fixed in the production scripts (`validate_punchlist.py`, `pattern_brief_compact.py`). The migration script was written after those fixes but does not incorporate the masking pattern.

**Evidence:** `grep -rn 'mask_code_fences\|mask_fenced_blocks' scripts/migrate_legacy.py` returns zero matches. Meanwhile, every regex call in the file operates on `content` parameters passed directly from `Path.read_text()`.

Specific vulnerable lines:
- L161-168: `_is_table_format()` scans raw content for `|` and `### B` patterns
- L186-242: `_parse_table_punchlist()` regex on raw `content.split("\n")`
- L252-292: `_parse_block_punchlist()` regex on raw `content`
- L297: `_extract_field()` regex on raw `block`
- L420-431: `_parse_predictions()` regex on raw `content`
- L471-489: `_parse_claims_table()` regex on raw `content`
- L496-518: `_parse_test_findings()` regex on raw `content`
- L521-546: `_parse_code_findings()` regex on raw `content`
- L561-563: `parse_summary()` greedy regex on raw `content`

**Discovery Chain:** PAT-001 proactive check (LIVING-PUNCHLIST check 1) applied to new cold file

**Acceptance Criteria:**
- [ ] migrate_legacy.py imports and uses `mask_code_fences` before regex extraction, OR documents why masking is unnecessary for historical data
- [ ] Test with sample markdown containing code-fenced punchlist headers verifies no phantom events

**Validation Command:**
```bash
grep -c 'mask_code_fences\|mask_fenced_blocks' scripts/migrate_legacy.py
```

### BJ-002: mypy gate in transitions.toml blocks all convergence
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/transitions.toml:134`, `enforcement/transitions.toml:173`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** Two transition gates in `transitions.toml` use `mypy skills/holtz/scripts/ hooks/ enforcement/hooks/` as a `command_succeeds` condition. This command always exits with error 2 due to the duplicate `_common` module name between `hooks/_common.py` and `enforcement/hooks/_common.py`. The affected transitions are:

1. `fix_loop -> perspective_clean` (line 134): requires mypy to pass for perspective completion
2. `final_sweep -> final_sweep_clean` (line 173): requires mypy to pass for convergence

Since these gates always fail, no Sahjhan-enforced audit run can ever reach `perspective_clean` or `final_sweep_clean` states. The enforcement engine's convergence protocol is broken at the gate level.

This is the same root cause as the CI breakage (`.github/workflows/ci.yml:29`) and the CLAUDE.md instruction (`mypy skills/holtz/scripts/ hooks/ enforcement/hooks/`), but the transitions.toml instance has the highest severity because it blocks the audit protocol's convergence.

**Evidence:** `mypy skills/holtz/scripts/ hooks/ enforcement/hooks/` returns exit code 2 with "Duplicate module named '_common'". Lines 134 and 173 of transitions.toml use this exact command string.

**Discovery Chain:** Step 1 toolchain check (mypy broken) -> traced to CI -> traced to transitions.toml gates -> realized convergence is blocked

**Acceptance Criteria:**
- [ ] `mypy` invocation in transitions.toml lines 134 and 173 passes (exit 0)
- [ ] Either add `--explicit-package-bases` flag or rename one of the `_common.py` files
- [ ] Same fix applied to `.github/workflows/ci.yml` and `CLAUDE.md`

**Validation Command:**
```bash
mypy skills/holtz/scripts/ hooks/ enforcement/hooks/ && echo PASS || echo FAIL
```

### BJ-003: write_guard blocks Justine output in dev mode
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/write_guard.py:18-20`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** `write_guard.py` defines `MANAGED_PATHS = ["docs/holtz"]`, which blocks all Write/Edit operations to any path starting with `docs/holtz/`. Justine's output directory is `docs/holtz/justine/`. When an active Sahjhan run exists (`.sahjhan/` directory present), write_guard blocks Justine from writing her punchlist, summary, and recon files.

This means Holtz's own audit workflow -- where Justine runs in parallel and writes to `docs/holtz/justine/` -- is blocked by the enforcement layer that Holtz designed. The write_guard needs an exclusion for audit output paths, or Justine's output should be moved outside the managed zone.

**Evidence:** `write_guard.py` line 18-20: `MANAGED_PATHS = ["docs/holtz"]`. The `docs/holtz/.sahjhan/` directory exists (confirmed via `ls`). Any Write to `docs/holtz/justine/PUNCHLIST.md` would trigger `resolved.startswith(full)` on line 35 and be blocked.

**Discovery Chain:** Observed that Justine writes to `docs/holtz/justine/` -> checked write_guard MANAGED_PATHS -> confirmed path collision -> verified active .sahjhan directory

**Acceptance Criteria:**
- [ ] Justine can write to `docs/holtz/justine/` without being blocked by write_guard
- [ ] Test verifies write_guard allows writes to Justine's output directory

**Validation Command:**
```bash
echo '{"tool_input":{"file_path":"docs/holtz/justine/test.md"},"cwd":"."}' | python enforcement/hooks/write_guard.py
```

### BJ-004: README "What's inside" counts stale (PAT-005)
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:216`
**Status:** OPEN
**Pattern:** PAT-005
**Determinism:** deterministic

**Problem:** The "What's inside" line claims: "6 enforcement hooks, 647 tests across 14,300 lines of code". Actual values:
- Enforcement hooks: 1 (only `subagent_findings_check.py` in `hooks/`, excluding `_common.py`)
- Lines: 14,176
- Test count: 647 is correct (646 passed + 1 failed = 647 collected)

Additionally, README line 190 claims "19 runs" but 30+ runs have been completed. README line 198 claims "Six enforcement hooks" and describes hooks that no longer exist (impact_graph_gate, status_staleness_gate, artifact_verification were replaced by Sahjhan). The entire "The hooks" section (lines 196-212) is stale -- it describes the old hook architecture, not the current Sahjhan enforcement engine.

**Evidence:** Test failure: `test_readme_metrics_match_actual` reports "enforcement hooks: README says 6, actual 1" and "lines: README says 14300, actual 14176".

**Discovery Chain:** Failing test -> README inspection -> cross-referenced with hooks.json and enforcement/hooks/

**Acceptance Criteria:**
- [ ] `test_readme_metrics_match_actual` passes
- [ ] README "The hooks" section describes current architecture (Sahjhan + write_guard + bash_guard + stop_gate + primer + bootstrap)
- [ ] Run count updated from 19 to current

**Validation Command:**
```bash
python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v
```

### BJ-005: CI mypy step broken by _common.py module collision
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `.github/workflows/ci.yml:29`, `pyproject.toml:14`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** CI workflow runs `mypy skills/holtz/scripts/ hooks/ enforcement/hooks/` which fails with "Duplicate module named '_common'". The `pyproject.toml` `[tool.mypy]` section only lists `files = ["skills/holtz/scripts", "hooks"]` (without enforcement/hooks/), so `mypy` without arguments works. But the CI invocation and CLAUDE.md instruction both include `enforcement/hooks/`.

Fix: add `--explicit-package-bases` to the mypy invocation in ci.yml, CLAUDE.md, and transitions.toml, or rename `enforcement/hooks/_common.py` to something unique (e.g., `_enforcement_common.py`).

**Evidence:** `mypy skills/holtz/scripts/ hooks/ enforcement/hooks/` returns exit code 2. `mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/` returns "Success: no issues found in 15 source files".

**Discovery Chain:** CLAUDE.md instruction -> ran mypy -> observed failure -> tested workaround

**Acceptance Criteria:**
- [ ] `mypy` invocation in ci.yml passes
- [ ] Same fix applied to CLAUDE.md and transitions.toml

**Validation Command:**
```bash
mypy skills/holtz/scripts/ hooks/ enforcement/hooks/
```

### BJ-006: 8 ruff lint errors in tests and migration script
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `scripts/migrate_legacy.py:106`, `tests/test_enforcement_config.py`, `tests/test_jsonl_integration.py`, `tests/test_migrate_legacy.py`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** 8 ruff errors:
1. `scripts/migrate_legacy.py:106` — UP017: Use `datetime.UTC` instead of `timezone.utc`
2. `tests/test_enforcement_config.py:7` — UP036: Version block outdated for min Python 3.12
3. `tests/test_enforcement_config.py:70` — B904: `raise ... from err` missing in except clause
4. `tests/test_jsonl_integration.py:15` — F401: unused import `os`
5-7. `tests/test_jsonl_integration.py:456,469,590` — E741: Ambiguous variable name `l`
8. `tests/test_migrate_legacy.py:11` — I001: Import block unsorted

Three are auto-fixable with `--fix`.

**Evidence:** `ruff check .` output shows 8 errors.

**Discovery Chain:** Ruff check during Step 1 toolchain

**Acceptance Criteria:**
- [ ] `ruff check .` returns 0 errors

**Validation Command:**
```bash
ruff check .
```

### BJ-007: enforcement/hooks/ excluded from test coverage
**Severity:** MEDIUM
**Category:** test/integration-gap
**Location:** `pyproject.toml:20`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** `pyproject.toml` configures coverage for `skills/holtz/scripts` and `hooks` only:
```
addopts = "--cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60"
```

The 7 files in `enforcement/hooks/` are not covered. These are security-critical files (write_guard, bash_guard, stop_gate, primer, bootstrap) that gate agent behavior. While they are tested via subprocess in `test_sahjhan_integration.py` and `test_enforcement_config.py`, their actual line coverage is unmeasured.

Additionally, `hooks/subagent_findings_check.py` shows 0% coverage despite having tests in `test_hooks.py`. This is because hooks are tested via subprocess (as noted in LIVING-PUNCHLIST architectural risks), so pytest-cov can't see the execution.

**Evidence:** Coverage report shows 0% for `hooks/subagent_findings_check.py`. No `--cov=enforcement/hooks` in pyproject.toml addopts.

**Discovery Chain:** Coverage output review -> pyproject.toml inspection -> identified gap

**Acceptance Criteria:**
- [ ] enforcement/hooks/ added to coverage measurement, OR documented as intentionally excluded with justification
- [ ] Coverage threshold accounts for subprocess-tested modules

**Validation Command:**
```bash
python -m pytest --cov=enforcement/hooks --cov-report=term-missing tests/ -q 2>&1 | head -20
```

### BJ-008: enforcement hooks silently suppress all errors via exit_ok()
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/bash_guard.py:56-57`, `enforcement/hooks/primer.py:56-57`, `enforcement/hooks/stop_gate.py:48-49`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** All enforcement hooks catch `FileNotFoundError` and `subprocess.TimeoutExpired` and call `exit_ok()` -- silently allowing the operation. This is correct for graceful degradation when Sahjhan is not installed, but it means:

1. If the Sahjhan binary path is misconfigured (wrong architecture, permission denied, etc.), all enforcement is silently disabled.
2. If Sahjhan crashes or hangs (TimeoutExpired), the violation is never recorded and the operation proceeds.
3. `bash_guard.py` line 62: even the violation recording itself suppresses errors with `contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired)` -- so a timeout during manifest verify followed by a timeout during violation recording means the violation is lost.

The hooks correctly implement fail-open semantics (agent is not blocked by broken tooling), but there is no observability -- no warning, no log, no event. A broken Sahjhan binary renders the entire enforcement layer inert with zero diagnostic signal.

**Evidence:** `bash_guard.py:56-57`: `except (FileNotFoundError, subprocess.TimeoutExpired): exit_ok()`. Same pattern in `primer.py:56-57` and `stop_gate.py:48-49`.

**Discovery Chain:** Enforcement hook code review -> error path analysis -> observed silent suppression

**Acceptance Criteria:**
- [ ] Hooks emit a diagnostic warning (via stderr or additionalContext) when Sahjhan subprocess fails unexpectedly
- [ ] Distinguish "Sahjhan not installed" (expected, silent) from "Sahjhan crashed" (unexpected, should warn)

**Validation Command:**
```bash
grep -n 'exit_ok' enforcement/hooks/bash_guard.py enforcement/hooks/primer.py enforcement/hooks/stop_gate.py
```

### BJ-009: README "The hooks" section describes deleted hooks
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:196-212`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** README lines 198-212 describe six enforcement hooks by name:
- "Impact graph gate" -- deleted, replaced by Sahjhan gate in transitions.toml
- "Status staleness gate" -- deleted, replaced by Sahjhan
- "Artifact verification" -- deleted, replaced by Sahjhan
- "Subagent findings check" -- still exists in hooks/
- "Convergence gate" -- replaced by stop_gate.py in enforcement/hooks/
- "Convergence primer" -- replaced by primer.py in enforcement/hooks/

The current architecture has 5 active hooks registered in hooks.json: _sahjhan_bootstrap, write_guard, bash_guard (in enforcement/hooks/), subagent_findings_check (in hooks/), and stop_gate + primer (in enforcement/hooks/). The README describes none of the new hooks (write_guard, bash_guard, bootstrap) and describes three that no longer exist.

This is a superset of BJ-004 -- BJ-004 covers the count; this covers the prose descriptions.

**Evidence:** `hooks.json` lists 5 hook commands across PreToolUse, PostToolUse, SubagentStop, Stop, and UserPromptSubmit. README describes 6 hooks, 3 of which are deleted.

**Discovery Chain:** README line-by-line review -> cross-referenced with hooks.json and enforcement/hooks/ directory listing

**Acceptance Criteria:**
- [ ] README "The hooks" section describes the current 5-hook architecture
- [ ] Sahjhan enforcement engine described (at least briefly)

**Validation Command:**
```bash
grep -c 'Impact graph gate\|Status staleness gate\|Artifact verification' README.md
```

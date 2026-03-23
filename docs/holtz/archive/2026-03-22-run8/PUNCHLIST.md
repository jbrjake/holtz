# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 235 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 2        | 0        |
| MEDIUM   | 0    | 3        | 0        |
| LOW      | 0    | 5        | 0        |

## Patterns

## Items

### BH-001: pytest-cov configured but not installed — default pytest broken
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `pyproject.toml:20`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** `pyproject.toml` sets `addopts = "--cov=skills/holtz/scripts --cov-report=term-missing --cov-fail-under=0"` but `pytest-cov` is not installed in the virtualenv. Running `pytest` fails with `unrecognized arguments: --cov=skills/holtz/scripts`. This was "resolved" in run 7 (BH-001) by adding the config, but the dependency was never actually installed, so the fix was incomplete.

**Evidence:** `source .venv/bin/activate && python -m pytest --tb=short -q 2>&1` exits with error code 4. `pip list | grep -i cov` returns empty. Tests only pass with `--override-ini="addopts="`.

**Discovery Chain:** Run baseline test → pytest fails with exit code 4 → unrecognized --cov args → pip list confirms pytest-cov not installed → run 7 BH-001 added config without installing dependency

**Acceptance Criteria:**
- [x] Either pytest-cov is installed and `pytest` runs clean, OR the addopts line is removed/conditioned
- [x] Validation: `python -m pytest --tb=short -q` succeeds without --override-ini

**Validation Command:**
```bash
source .venv/bin/activate && python -m pytest --tb=short -q 2>&1 | tail -1
```

**Resolution:** Removed pytest-cov addopts from pyproject.toml (set `addopts = ""`). pytest-cov was never installed; the config was added in run 7 without the dependency. Default `pytest` now runs clean (235 passed, 0.26s).

### BH-002: CI configuration recommendation recurring without implementation
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `docs/holtz/archive/*/SUMMARY.md`
**Status:** RESOLVED

**Problem:** This recommendation has appeared in 2 consecutive audit summaries without being implemented: "No CI/CD is configured. GitHub Actions with ruff + mypy + pytest would prevent regressions on push."

**Evidence:** Found in: docs/holtz/archive/2026-03-22-run6/SUMMARY.md (run 6), docs/holtz/archive/2026-03-22-run7/SUMMARY.md (run 7)

**Discovery Chain:** Prior summary scan → recommendation "CI configuration" found in 2 summaries → 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [x] CI is configured OR explicitly rejected with rationale
- [x] Validation: CI config file exists or rejection documented

**Validation Command:**
```bash
ls .github/workflows/*.yml 2>/dev/null || echo "No CI configured"
```

**Resolution:** Created `.github/workflows/ci.yml` with ruff check, mypy, and pytest on push/PR to main.

### BH-003: hooks/ directory has 7 ruff lint errors
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/`
**Status:** RESOLVED

**Problem:** The `hooks/` directory was added but is not covered by the linting configuration. 7 ruff errors exist: 4x I001 (unsorted imports), 2x SIM108 (use ternary), 1x F841 (unused variable `stdout` in artifact_verification.py:43). The unused `stdout` variable is also dead code — it's assigned but never read.

**Evidence:** `ruff check .` outputs 7 errors, all in `hooks/`. `hooks/` is not excluded from ruff, so errors exist but were never addressed. The `stdout` variable at artifact_verification.py:43 is assigned from `tool_response.get("stdout", "")` but only `stderr` is used on line 44-46.

**Discovery Chain:** Ran ruff check → 7 errors all in hooks/ → hooks/ added after run 7 convergence → never linted during development

**Acceptance Criteria:**
- [x] All 7 ruff errors resolved
- [x] Validation: `ruff check .` exits clean

**Validation Command:**
```bash
ruff check . 2>&1
```

**Resolution:** `ruff check --fix` fixed 4 import ordering (I001). Manually fixed SIM108 ternary and F841 unused stdout in artifact_verification.py (as part of BH-004/BH-007 fix). Added hooks/ to ruff src config. `ruff check .` now exits clean.

### BH-004: artifact_verification hook false-positives on shell variable in --graph arg
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/artifact_verification.py:28`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** The hook extracts the `--graph` path using `re.search(r'--graph\s+["\']?([^"\'\s]+)["\']?', command)`. When the command contains `--graph "$GRAPH"`, the regex captures the literal string `$GRAPH` (not the resolved path), then checks if that literal file exists. It doesn't, so the hook blocks a valid operation. Shell variables in the command string are not resolved by the hook.

**Evidence:** Observed during Phase 0: running `impact_graph.py --graph "$GRAPH" add_node ...` triggered `BLOCKED: impact_graph.py ran but $GRAPH does not exist on disk` even though the graph was successfully created at the resolved path.

**Discovery Chain:** Impact graph init command blocked by PostToolUse hook → hook extracted literal `$GRAPH` from command → checked if `$GRAPH` file exists → false positive block on valid operation

**Acceptance Criteria:**
- [x] Hook handles shell variable references in --graph argument (skip check or resolve)
- [x] Validation: hook does not false-positive on `--graph "$VAR"` commands

**Validation Command:**
```bash
echo '{"tool_input":{"command":"python impact_graph.py --graph \"$GRAPH\" add_node x"}, "cwd":"/tmp"}' | python hooks/artifact_verification.py 2>&1; echo "exit: $?"
```

**Resolution:** Added `$` prefix check — if graph_rel starts with `$`, skip the file existence check. Also improved the command detection regex from substring match to `r'(?:^|[\s/])impact_graph\.py\b'` which fixes BH-007 simultaneously.

### BH-005: README claims 12 reference docs but there are 13
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:36`
**Status:** RESOLVED

**Problem:** README line 36 states "12 reference docs" in the inventory list, but `skills/holtz/references/` contains 13 non-backstory markdown files. The extra file appears to be `recommendation-escalation.md`, likely added after the README count was written.

**Evidence:** `ls skills/holtz/references/*.md | grep -v backstory | wc -l` returns 13. README says 12.

**Discovery Chain:** Phase 1 inventory verification → counted 13 reference files → README says 12 → off-by-one from added file

**Acceptance Criteria:**
- [x] README inventory count matches actual file count
- [x] Validation: count matches

**Validation Command:**
```bash
grep -o '12 reference docs' README.md && ls skills/holtz/references/*.md | grep -v backstory | wc -l
```

**Resolution:** Updated README.md line 36 from "12 reference docs" to "13 reference docs".

### BH-006: hooks/ has zero test coverage
**Severity:** HIGH (upgraded from MEDIUM per Justine merge)
**Category:** test/missing
**Location:** `hooks/`
**Status:** RESOLVED
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** The `hooks/` directory contains 5 Python files (4 hooks + `_common.py`) with real logic — path parsing, event handling, file existence checks, time-based staleness gating — but zero test coverage. These hooks gate critical operations (blocking writes, verifying artifacts). An untested bug in a hook could block valid operations (observed: BH-004) or allow invalid ones to pass silently.

**Evidence:** `grep -r 'import.*hooks\|from.*hooks' tests/` returns nothing. No test file references any hook module. `hooks/` is not in `sys.path` of conftest.py.

**Discovery Chain:** Phase 2 test coverage analysis → grep for hook imports in tests/ → zero results → 5 files with gate logic completely untested

**Acceptance Criteria:**
- [x] Test file exists for hooks with at least basic coverage of each hook's main() function
- [x] Validation: at least one test per hook file

**Validation Command:**
```bash
source .venv/bin/activate && python -m pytest --override-ini="addopts=" -q tests/test_hooks.py 2>&1 | tail -1
```

**Resolution:** Created `tests/test_hooks.py` with 24 tests covering all 5 hook modules: _common.py (2 tests), impact_graph_gate.py (5 tests), status_staleness_gate.py (6 tests), artifact_verification.py (6 tests), subagent_findings_check.py (5 tests). Tests cover happy path, error path, exit codes, edge cases, and the fixes from BH-004/BH-007/BH-008.

### BH-007: artifact_verification hook matches test filenames via substring
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/artifact_verification.py:24`
**Status:** RESOLVED
**Determinism:** deterministic
**Predicted:** Prediction 1 (confidence: HIGH)
**Lens:** component

**Problem:** The hook checks `"impact_graph.py" not in command` using a substring match. Running `python -m pytest test_impact_graph.py` contains the substring "impact_graph.py", so the hook fires and attempts to verify the graph file exists. This is a false positive — the command is running tests, not the impact graph script. If no graph file exists (e.g., clean checkout), the hook blocks a valid test run.

**Evidence:** `hooks/artifact_verification.py:24`: `if "impact_graph.py" not in command: exit_ok()`. The string `test_impact_graph.py` contains `impact_graph.py` as a substring.

**Discovery Chain:** Phase 3 adversarial audit of hooks/ → analyzed substring match on line 24 → test filenames contain "impact_graph.py" as substring → false positive on pytest commands

**Acceptance Criteria:**
- [x] Hook distinguishes between running impact_graph.py and referencing it in test filenames
- [x] Validation: hook allows pytest commands referencing test_impact_graph.py

**Validation Command:**
```bash
echo '{"tool_input":{"command":"python -m pytest test_impact_graph.py"}, "cwd":"/tmp"}' | python hooks/artifact_verification.py 2>&1; echo "exit: $?"
```

**Resolution:** Replaced substring check `"impact_graph.py" not in command` with regex `r'(?:^|[\s/])impact_graph\.py\b'` which matches the script name at word boundaries, not as part of test filenames.

### BH-008: status_staleness_gate STATUS.md exemption too broad
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/status_staleness_gate.py:39`
**Status:** RESOLVED
**Lens:** security

**Problem:** The staleness gate exempts any file ending with `STATUS.md` from the staleness check (`normalized.endswith("STATUS.md")`). While the `docs/holtz/` prefix check limits scope, a file like `docs/holtz/recon/STATUS.md` would bypass the gate. The exemption should check for the specific STATUS.md paths used by the protocol.

**Evidence:** Line 39: `if normalized.endswith("STATUS.md"):` with no path prefix validation beyond the `docs/holtz/` check.

**Discovery Chain:** Justine Phase 3 → endswith("STATUS.md") too broad → only intended for 2 specific paths

**Acceptance Criteria:**
- [x] Exemption scoped to specific STATUS.md paths or documented as acceptable
- [x] Validation: confirmed

**Validation Command:**
```bash
grep 'endswith.*STATUS' hooks/status_staleness_gate.py
```

**Resolution:** Changed `normalized.endswith("STATUS.md")` to explicit check for `docs/holtz/STATUS.md` and `docs/holtz/justine/STATUS.md`. Also applied ternary refactor for status_rel.

### BH-009: subagent_findings_check scans raw text without code-fence awareness
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/subagent_findings_check.py:28`
**Status:** RESOLVED
**Lens:** data-flow

**Problem:** The hook scans raw `last_assistant_message` for `docs/holtz/*.md` paths without code-fence masking. Paths mentioned in code examples could trigger false-positive warnings. Impact is limited since the hook only warns (exit 1, not block).

**Evidence:** Line 28: `paths = re.findall(r'docs/holtz/[^\s"\')\]]+\.md', message)` — raw text, no masking.

**Discovery Chain:** Justine Phase 3 → regex on raw message → paths in code examples could false-positive → mitigated by warn-only behavior

**Acceptance Criteria:**
- [x] Either add fence masking or document the false-positive risk as acceptable in the docstring
- [x] Validation: confirmed

**Validation Command:**
```bash
grep -c 'mask_code_fences\|_iterate_fences' hooks/subagent_findings_check.py
```

**Resolution:** Documented false-positive risk as acceptable in the hook docstring. The hook only warns (exit 1), so false positives don't block operations.

### BH-010: hooks/ not included in mypy configuration
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `pyproject.toml:15`
**Status:** RESOLVED
**Lens:** contract

**Problem:** pyproject.toml `[tool.mypy]` sets `files = ["skills/holtz/scripts"]` but does not include `hooks/`. Hooks use type annotations but are never type-checked.

**Evidence:** pyproject.toml line 15: `files = ["skills/holtz/scripts"]` — hooks/ absent.

**Discovery Chain:** Justine recon → mypy config excludes hooks/ → type errors could exist uncaught

**Acceptance Criteria:**
- [x] `hooks/` added to mypy files list and passes
- [x] Validation: mypy hooks/ clean

**Validation Command:**
```bash
source .venv/bin/activate && mypy hooks/ 2>&1
```

**Resolution:** Added `hooks/` to mypy files list in pyproject.toml and ruff src list. mypy now checks 9 source files (up from 4). All pass clean.


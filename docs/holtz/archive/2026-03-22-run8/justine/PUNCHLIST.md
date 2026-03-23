# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 235 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1 | 0 | 0 |
| HIGH | 5 | 0 | 0 |
| MEDIUM | 4 | 0 | 0 |
| LOW | 2 | 0 | 0 |
| **Total** | **12** | **0** | **0** |

*Note: Items use BH-1xx namespace to avoid collision with Holtz's BH-0xx findings. See BH-112 for the BJ- prefix parser limitation.*

## Patterns

## Pattern: PAT-001: Untested hooks subsystem
**Instances:** BH-101, BH-102, BH-103, BH-104, BH-105, BH-106
**Root Cause:** hooks/ directory added in single commit without accompanying test suite
**Systemic Fix:** Add comprehensive hook test coverage before any further hook changes
**Detection Rule:** `find hooks/ -name "*.py" | while read f; do basename=$(basename "$f" .py); grep -rq "test_${basename}\|test_hook" tests/ || echo "UNTESTED: $f"; done`

## Items

### BH-101: impact_graph_gate.py gates a path nobody writes to
**Severity:** CRITICAL
**Category:** bug/logic
**Location:** `hooks/impact_graph_gate.py:30-35`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** The impact graph gate checks for writes to `docs/holtz/audit/` and `docs/holtz/justine/audit/`, but neither the Holtz nor Justine SKILL.md ever writes to a subdirectory named `audit/`. All punchlist items, recon files, and findings are written directly under `docs/holtz/` and `docs/holtz/justine/`. The gate is a complete no-op: it will never block anything because its path filter matches a directory that does not exist in the protocol. This means the HARD-GATE requirement ("Audit phases require a live impact graph") is unenforced despite the hook existing.

**Evidence:** Lines 30-35 of `hooks/impact_graph_gate.py`:
```python
if "docs/holtz/justine/audit/" in normalized:
    required = "docs/holtz/justine/impact-graph.json"
elif "docs/holtz/audit/" in normalized:
    required = "docs/holtz/impact-graph.json"
else:
    exit_ok()
```
The SKILL.md specifies these output paths: `docs/holtz/justine/PUNCHLIST.md`, `docs/holtz/justine/recon/`, `docs/holtz/justine/STATUS.md`. None contain `/audit/`.

**Discovery Chain:** Read impact_graph_gate.py path conditions → compared to SKILL.md output directory spec → `/audit/` subdirectory does not exist in protocol → gate is a no-op

**Acceptance Criteria:**
- [ ] Gate triggers on writes to `docs/holtz/justine/PUNCHLIST.md` and `docs/holtz/PUNCHLIST.md`
- [ ] Gate does NOT trigger on recon files (Phase 0 runs before graph exists)
- [ ] Gate does NOT trigger on STATUS.md writes
- [ ] Test verifies gate blocks punchlist write when impact-graph.json is missing
- [ ] Test verifies gate allows punchlist write when impact-graph.json exists

**Validation Command:**
```bash
python -m pytest tests/ --override-ini="addopts=" -k "test_impact_graph_gate" -v
```

### BH-102: hooks/ has zero test coverage
**Severity:** HIGH
**Category:** test/missing
**Location:** `hooks/`
**Status:** OPEN
**Lens:** integration
**Predicted:** Prediction 3 (confidence: HIGH)
**Pattern:** PAT-001

**Problem:** The entire hooks/ directory (5 Python files: _common.py, artifact_verification.py, impact_graph_gate.py, status_staleness_gate.py, subagent_findings_check.py) has zero test coverage. No test file exists for any hook module. These hooks enforce critical safety properties (impact graph gate, status staleness, artifact verification) and their correctness is assumed but never verified.

**Evidence:** `ls tests/test_*hook* tests/test_*artifact* tests/test_*gate* tests/test_*subagent* tests/test_*common*` returns no results. The hooks/ directory does not appear in any import statement in tests/.

**Discovery Chain:** Listed test files → no hook-related test files found → confirmed zero test coverage for entire hooks subsystem

**Acceptance Criteria:**
- [ ] Test file exists for each hook module
- [ ] Tests cover happy path and error paths for each hook
- [ ] Tests verify exit codes (0=allow, 1=warn, 2=block)
- [ ] Tests mock stdin to provide event JSON

**Validation Command:**
```bash
python -m pytest tests/ --override-ini="addopts=" -k "hook or gate or artifact or subagent or common" -v
```

### BH-103: artifact_verification.py has dead code (unused stdout variable)
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/artifact_verification.py:43`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Predicted:** Prediction 2 (confidence: HIGH)
**Pattern:** PAT-001

**Problem:** Line 43 assigns `stdout = tool_response.get("stdout", "")` but the variable is never used. The hook only checks stderr for error context. This means if impact_graph.py reports an error via stdout (which it does for non-existent node errors — `print(json.dumps(result), file=sys.stderr)` on line 362-363 uses stderr, but the main success output goes to stdout), the diagnostic information is incomplete.

**Evidence:** ruff F841 error: `hooks/artifact_verification.py:43: Local variable 'stdout' is assigned to but never used`. Lines 41-46:
```python
if isinstance(tool_response, dict):
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")
    if stderr:
        extra = f" Script stderr: {stderr[:200]}"
```

**Discovery Chain:** ruff F841 flagged unused variable → code review confirmed stdout is assigned but never referenced → dead code

**Acceptance Criteria:**
- [ ] Either use stdout in the error message or remove the assignment
- [ ] If retained, include stdout excerpt in the block message for debugging

**Validation Command:**
```bash
cd /Users/jonr/Documents/non-nitro-repos/holtz && .venv/bin/python -m ruff check hooks/artifact_verification.py
```

### BH-104: status_staleness_gate.py STATUS.md exemption is too broad
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `hooks/status_staleness_gate.py:39`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Predicted:** Prediction 4 (confidence: MEDIUM)
**Pattern:** PAT-001

**Problem:** The staleness gate exempts any file whose normalized path ends with `STATUS.md` from the staleness check. This is correct for `docs/holtz/STATUS.md` and `docs/holtz/justine/STATUS.md`, but it would also exempt `docs/holtz/NOT_A_STATUS.md`, `anywhere/STATUS.md`, or any file crafted to end with that suffix. The exemption should be scoped to the specific STATUS.md files the protocol uses.

**Evidence:** Line 39: `if normalized.endswith("STATUS.md"):` — no path prefix validation.

**Discovery Chain:** Read status_staleness_gate.py exemption logic → `endswith("STATUS.md")` matches any path → too broad

**Acceptance Criteria:**
- [ ] Exemption checks for specific paths (`docs/holtz/STATUS.md` and `docs/holtz/justine/STATUS.md`) rather than any path ending with `STATUS.md`
- [ ] Test verifies that `docs/holtz/recon/STATUS.md` (hypothetical) would NOT be exempted

**Validation Command:**
```bash
python -m pytest tests/ --override-ini="addopts=" -k "test_status_staleness" -v
```

### BH-105: subagent_findings_check.py scans raw text without code-fence awareness
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/subagent_findings_check.py:28`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction 5 (confidence: MEDIUM)
**Pattern:** PAT-001

**Problem:** The subagent findings check scans the raw `last_assistant_message` for `docs/holtz/*.md` paths using a regex. It does not use `mask_code_fences` or any code-fence awareness. If a subagent's message includes a markdown code example showing a docs/holtz path (e.g., explaining how to create a file), the hook will false-positive by checking for the existence of a path that was mentioned in documentation, not as an actual output.

**Evidence:** Line 28: `paths = re.findall(r'docs/holtz/[^\s"\')\]]+\.md', message)` — operates on raw message text.

**Discovery Chain:** Read subagent_findings_check.py → regex scans raw message → no code-fence masking → paths in code examples will false-positive

**Acceptance Criteria:**
- [ ] Hook either masks code fences before scanning or documents the false-positive risk as acceptable
- [ ] If false positives are acceptable (the hook only warns, exit code 1), document this explicitly in the hook docstring

**Validation Command:**
```bash
python -m pytest tests/ --override-ini="addopts=" -k "test_subagent" -v
```

### BH-106: Seven ruff lint errors in hooks/ directory
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/`
**Status:** OPEN
**Lens:** component
**Pattern:** PAT-001

**Problem:** The hooks/ directory has 7 ruff errors (4 import ordering I001, 2 ternary suggestions SIM108, 1 unused variable F841) while the scripts/ and tests/ directories are clean. This indicates the hooks were not run through the same quality gates as the rest of the codebase.

**Evidence:** `ruff check .` output shows 7 errors, all in hooks/*.py. Zero errors in skills/ or tests/.

**Discovery Chain:** Ran ruff → 7 errors all in hooks/ → hooks not linted before commit

**Acceptance Criteria:**
- [ ] All 7 ruff errors resolved
- [ ] `ruff check .` returns 0 errors
- [ ] hooks/ added to ruff src config in pyproject.toml

**Validation Command:**
```bash
cd /Users/jonr/Documents/non-nitro-repos/holtz && .venv/bin/python -m ruff check hooks/
```

### BH-107: pyproject.toml references pytest-cov but it is not installed
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `pyproject.toml:20`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract
**Predicted:** Prediction 7 (confidence: HIGH)

**Problem:** The pyproject.toml addopts includes `--cov=skills/holtz/scripts --cov-report=term-missing --cov-fail-under=0` but pytest-cov is not installed in the virtual environment. Running `pytest` without the workaround `--override-ini="addopts="` will fail with a plugin error. This creates a broken default: anyone cloning the repo and running `pytest` will hit an immediate failure that has nothing to do with the code being tested.

**Evidence:** pyproject.toml line 20: `addopts = "--cov=skills/holtz/scripts --cov-report=term-missing --cov-fail-under=0"`. Running `.venv/bin/python -m pytest` without override fails.

**Discovery Chain:** Attempted to run pytest → failed due to missing pytest-cov → required --override-ini workaround → broken default for all users

**Acceptance Criteria:**
- [ ] Either install pytest-cov as a dev dependency OR remove cov options from addopts
- [ ] Running `pytest` with no extra flags succeeds

**Validation Command:**
```bash
cd /Users/jonr/Documents/non-nitro-repos/holtz && .venv/bin/python -m pytest 2>&1 | head -5
```

### BH-108: hooks/ not included in ruff src configuration
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `pyproject.toml:4`
**Status:** OPEN
**Lens:** contract

**Problem:** pyproject.toml `[tool.ruff]` sets `src = ["skills/holtz/scripts", "tests"]` but does not include `hooks/`. This means ruff's import resolution does not know about hooks as a source root, which contributed to the 4 I001 import ordering errors.

**Evidence:** pyproject.toml line 4: `src = ["skills/holtz/scripts", "tests"]` — hooks/ absent.

**Discovery Chain:** Observed ruff I001 errors in hooks/ → checked ruff config → hooks/ not in src list → import resolver lacks context

**Acceptance Criteria:**
- [ ] `hooks/` added to ruff src list in pyproject.toml
- [ ] I001 errors resolved after src update (or import blocks manually sorted)

**Validation Command:**
```bash
cd /Users/jonr/Documents/non-nitro-repos/holtz && .venv/bin/python -m ruff check hooks/ --select I001
```

### BH-109: hooks/ not included in mypy configuration
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `pyproject.toml:15`
**Status:** OPEN
**Lens:** contract

**Problem:** pyproject.toml `[tool.mypy]` sets `files = ["skills/holtz/scripts"]` but does not include `hooks/`. The hooks are Python 3.12 code with type annotations (e.g., `dict[str, Any]` in _common.py) but are never type-checked.

**Evidence:** pyproject.toml line 15: `files = ["skills/holtz/scripts"]` — hooks/ absent.

**Discovery Chain:** Reviewed mypy config → hooks/ excluded → type errors could exist uncaught

**Acceptance Criteria:**
- [ ] `hooks/` added to mypy files list
- [ ] `mypy hooks/` passes or errors are documented

**Validation Command:**
```bash
cd /Users/jonr/Documents/non-nitro-repos/holtz && .venv/bin/python -m mypy hooks/
```

### BH-110: No integration test validates hook event contract
**Severity:** HIGH
**Category:** test/integration-gap
**Location:** `hooks/`
**Status:** OPEN
**Lens:** integration
**Pattern:** PAT-001

**Problem:** The hooks read JSON events from stdin with a specific contract (tool_input, file_path, command, cwd, tool_response, last_assistant_message fields). There is no integration test that validates the contract between the Claude Code plugin system (which generates these events) and the hook code (which parses them). If the event format changes, all four hooks would silently degrade to exit_ok (due to _common.py's defensive fallback), making the safety hooks invisible failures.

**Evidence:** `_common.py:read_event()` returns `{}` on parse failure. Every hook checks `event.get("tool_input", {})` or similar — if the event is empty, all conditional paths fall through to `exit_ok()`. There is no schema validation of the event, and no test that exercises the actual event format.

**Discovery Chain:** Read _common.py fallback behavior → empty dict on failure → all hooks fall through to exit_ok → safety hooks would silently disable on event format change

**Acceptance Criteria:**
- [ ] At least one integration test constructs a realistic event JSON and pipes it through each hook
- [ ] Tests verify that hooks produce the correct exit code for known event shapes
- [ ] Tests verify that malformed events produce exit_ok (graceful degradation) rather than crashes

**Validation Command:**
```bash
python -m pytest tests/ --override-ini="addopts=" -k "test_hook_integration" -v
```

### BH-111: Empty types=[] treated as no filter in neighbors() and blast_radius()
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/impact_graph.py:148-149,165-166`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract

**Problem:** In `neighbors()` and `blast_radius()`, the `types` parameter is checked with `set(types) if types else None`. An empty list `[]` is falsy in Python, so `types=[]` is treated as `None` (no filter), returning ALL neighbors/radius regardless of edge type. The documented behavior says "filtered by edge type" but passing an explicit empty list says "filter to no types" — which should logically return an empty result, not all results. The existing test (`test_neighbors_empty_types_is_no_filter`) tests this behavior and documents it as intentional, but the behavior violates the principle of least surprise and the method signatures.

**Evidence:** `impact_graph.py:148`: `type_set = set(types) if types else None`. Lines 165-166 repeat the same pattern. `test_impact_graph.py:719-736` tests confirm this is the current behavior.

**Discovery Chain:** Read neighbors() code → `if types` is falsy for empty list → `types=[]` means "all types" not "no types" → semantic mismatch

**Acceptance Criteria:**
- [ ] Either change behavior so `types=[]` returns empty results (strict interpretation) OR document the "falsy list = no filter" convention explicitly in the docstring
- [ ] If behavior changes, update the existing tests that depend on it
- [ ] CLI `--type ""` (empty string) behavior documented

**Validation Command:**
```bash
python -m pytest tests/test_impact_graph.py --override-ini="addopts=" -k "empty_types" -v
```

### BH-112: validate_punchlist.py and convergence_check.py hardcoded to BH- prefix
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:84`, `skills/holtz/scripts/convergence_check.py:43`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration

**Problem:** Both `parse_punchlist()` and `count_items()` use hardcoded regex patterns that only match `BH-\d+` item headers. The architecture-baseline.md documents that Justine uses the `BJ-NNN` namespace, but neither parser will recognize Justine's items. This means Justine's punchlist would be invisible to the validator (reports "No punchlist items found") and the convergence tracker (counts zero items), making convergence tracking and validation impossible for Justine's parallel audit output.

**Evidence:** `validate_punchlist.py:84`: `item_pattern = re.compile(r'^### (BH-\d+):[ \t]*(.*)$', re.MULTILINE)`. `convergence_check.py:43`: `item_pattern = re.compile(r'^### BH-\d+:', re.MULTILINE)`. Architecture-baseline.md line 35: `Punchlist items: BH-NNN namespace (Holtz), BJ-NNN namespace (Justine)`.

**Discovery Chain:** Attempted to validate BJ-prefixed punchlist → validator returned "No punchlist items found" → regex only matches BH- → Justine's items invisible to tooling

**Acceptance Criteria:**
- [ ] Both parsers accept `BH-\d+` and `BJ-\d+` item headers (or a configurable prefix)
- [ ] Test verifies BJ-prefixed items are parsed correctly
- [ ] Test verifies convergence tracker counts BJ-prefixed items

**Validation Command:**
```bash
python -m pytest tests/ --override-ini="addopts=" -k "test_bj_prefix" -v
```

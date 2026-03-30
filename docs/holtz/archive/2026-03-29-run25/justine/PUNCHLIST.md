# Justine Punchlist
> Generated: 2026-03-28 | Project: holtz v0.57.9 | Baseline: 758 pass, 3 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 3    | 0        | 0        |
| MEDIUM   | 3    | 0        | 0        |
| LOW      | 1    | 0        | 0        |
| **Total**| **7**| **0**    | **0**    |

## Patterns

(none yet -- pattern analysis after fixes)

## Items

### BJ-001: test_readme_metrics_match_actual crashes on pytest --co -q output format
**Severity:** HIGH
**Category:** bug/logic
**Location:** `tests/test_integration.py:288`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** The test runs `pytest --co -q` and parses the last line with `re.search(r"(\d+) test", test_line)`. With `-q`, pytest emits per-file test counts (e.g., "tests/test_verify_hooks.py: 3") instead of a summary "N tests collected" line. The regex returns None and `.group(1)` raises `AttributeError: 'NoneType' object has no attribute 'group'`. This test has been failing since the format changed.

**Evidence:** Direct reproduction: `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual` fails with `AttributeError: 'NoneType' object has no attribute 'group'`. Running `pytest --co -q` shows the last line is a per-file count, not "N tests collected". Running `pytest --co` (without -q) shows the summary line `761 tests collected in 0.16s`.

**Discovery Chain:** test failure output shows NoneType on `.group(1)` -> regex expects "N test" in last line of `--co -q` -> `--co -q` output ends with per-file counts, not summary -> regex never matches

**Acceptance Criteria:**
- [ ] Test parses actual test count correctly regardless of pytest `-q` flag behavior
- [ ] Test passes: `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual`

**Validation Command:**
```bash
python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v
```

### BJ-002: TestStopGate tests leak live session state
**Severity:** HIGH
**Category:** test/integration-gap
**Location:** `tests/test_sahjhan_integration.py:346-357`
**Status:** OPEN
**Lens:** integration
**Predicted:** Prediction 3 (confidence: HIGH)

**Problem:** `test_allows_without_sahjhan_binary` and `test_allows_without_active_run` call `run_enforcement_hook("stop_gate.py", {})` with an empty event dict. The hook reads `event.get("cwd", os.getcwd())` which defaults to the repo root, finds `docs/holtz/.sahjhan/active-run` with live audit state, and blocks. The tests assume no binary/no active run, but the live environment has both. These tests pass only when no Sahjhan audit is active.

**Evidence:** Direct reproduction: both tests fail with `assert {'decision': 'block', 'reason': "Audit is in state 'recon'..."} == {}`. The hook falls through to the blocking path because it finds a real active audit in the working directory.

**Discovery Chain:** test failure output shows 'block' decision with 'recon' state -> stop_gate uses `os.getcwd()` fallback -> repo has live `.sahjhan/active-run` marker -> test is not isolated from live environment

**Acceptance Criteria:**
- [ ] Tests use `tmp_path` with no `.sahjhan/` directory, passing an isolated `cwd` to the event
- [ ] Tests pass even during an active Sahjhan audit session
- [ ] Both tests pass: `python -m pytest tests/test_sahjhan_integration.py::TestStopGate -v`

**Validation Command:**
```bash
python -m pytest tests/test_sahjhan_integration.py::TestStopGate::test_allows_without_sahjhan_binary tests/test_sahjhan_integration.py::TestStopGate::test_allows_without_active_run -v
```

### BJ-003: README "What's inside" line counts stale -- PAT-005
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:7,190,214`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** README claims on multiple lines diverge from actual filesystem state:
- Line 7: badge says "759 tests" (actual: 761)
- Line 190: "759 tests across 21,120 lines of code" (actual: 761 tests, 17,577 lines in counted dirs)
- Line 190: "After 25 runs" (actual: 24 archived runs + this run in progress)
- The LOC discrepancy of 3,543 lines is significant; the counting methodology may differ between the test and the README.

This is PAT-005, recurring for 7+ consecutive runs.

**Evidence:** `python -m pytest --co 2>&1 | tail -1` shows "761 tests collected". Filesystem counts: enforcement hooks (non-private): 9, skill scripts: 6, test files: 28. Counted LOC across tests/, skills/holtz/scripts/, hooks/, enforcement/hooks/: 17,577.

**Discovery Chain:** README line 214 claims "759 tests across 21,120 lines" -> pytest collection shows 761 tests -> filesystem LOC count shows 17,577 -> drift confirmed on all metrics

**Acceptance Criteria:**
- [ ] README line 7 badge reflects actual test count
- [ ] README line 190 reflects actual test count and LOC
- [ ] README run count matches actual archived runs
- [ ] `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual` passes after counts are updated

**Validation Command:**
```bash
python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v
```

### BJ-004: CI persistent failure on TestBootstrapHook::test_blocks_binary_modification
**Severity:** MEDIUM
**Category:** test/fragile
**Location:** `tests/test_sahjhan_integration.py:73-81`
**Status:** OPEN
**Determinism:** intermittent
**Lens:** integration
**Predicted:** Prediction 4 (confidence: MEDIUM)

**Problem:** CI has failed on `test_blocks_binary_modification` for 3+ consecutive runs. The test passes locally on macOS. CI runs on ubuntu-latest. The test passes path `bin/sahjhan-aarch64-apple-darwin` (a macOS binary name) and expects the bootstrap hook to block it. On CI, `os.path.realpath("bin/sahjhan")` resolves through the symlink `bin/sahjhan -> sahjhan-aarch64-apple-darwin`, but the target binary is gitignored and absent on CI. The behavior of `realpath` on a dangling symlink may differ, or the hook's path comparison may fail for a platform-specific reason.

**Evidence:** CI status: 3 consecutive failures on dev branch. Error: `assert True is False` (hook allowed instead of blocking). Test passes locally because the real binary exists and `realpath` resolves correctly.

**Discovery Chain:** CI red for 3 runs on same test -> test uses macOS binary path -> binary files are gitignored -> CI has only the symlink, not the target -> `realpath` on dangling symlink may behave differently on Linux CI

**Acceptance Criteria:**
- [ ] Test is either platform-agnostic or properly skipped on CI when binaries are absent
- [ ] CI passes consistently on ubuntu-latest
- [ ] `python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_binary_modification -v` passes locally

**Validation Command:**
```bash
python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_binary_modification -v
```

### BJ-005: _sahjhan_bootstrap.py Bash redirect detection has false positives
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:43-58`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** The Bash command check uses `if p in command` to detect protected paths in shell commands. This is substring matching, not argument-position checking. Two false positive vectors confirmed:
1. Commands that mention protected paths in strings or comments: `echo "checking enforcement/ status" > /tmp/log.txt` would be blocked because "enforcement/" appears in the command string and ">" appears.
2. `cp` commands that READ FROM protected paths: `cp enforcement/hooks/primer.py /tmp/backup.py` would be blocked because "enforcement/" is in the command and the command starts with "cp ". The intent is to block writes TO protected paths, but the check cannot distinguish source from destination in a cp command.

Both are defense-in-depth issues (the primary path protection via `os.path.realpath` handles Write/Edit correctly), so the impact is limited to Bash commands being unnecessarily blocked.

**Evidence:** Python simulation confirms both false positive vectors fire:
- `echo "checking enforcement/ status" > /tmp/log.txt` triggers "enforcement/" + ">" match
- `cp enforcement/hooks/primer.py /tmp/backup.py` triggers "enforcement/" + "cp " match

**Discovery Chain:** code reading of line 44 shows `p in command` substring check -> constructed false-positive command strings -> both fire the block path -> defense-in-depth but user impact is unnecessary blocking

**Acceptance Criteria:**
- [ ] Bash redirect detection checks whether the protected path is the TARGET of the redirect, not just present in the command
- [ ] `cp` detection checks whether protected path is the destination argument, not the source
- [ ] False positives eliminated: `echo "enforcement/" > /tmp/log.txt` is allowed

**Validation Command:**
```bash
python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook -v
```

### BJ-006: verify_answer_freshness uses substring matching on short answer parts
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:153-161`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 6 (confidence: MEDIUM)

**Problem:** `verify_answer_freshness` splits the correct answer text on commas and checks `any(part in window)`. If answer parts are very short (e.g., a single letter like "a" or "b" from an option like "a, b, c, d"), they would match any file content containing that letter, giving a spurious "fresh" result. The function would falsely report a stale answer as fresh.

In practice, current quiz bank options tend to be multi-word (e.g., "OSError,TimeoutExpired"), so the parts are long enough to be meaningful. The theoretical risk is if future quiz bank entries use short option text.

**Evidence:** Code reading: line 160 splits on comma: `answer_parts = [p.strip() for p in answer_text.split(",") if p.strip()]`. Line 161: `any(part in window for part in answer_parts)`. A 1-character part like "a" would match almost any file content.

**Discovery Chain:** `verify_answer_freshness` checks answer validity via substring -> answer text split on comma -> short parts match spuriously -> "fresh" result is incorrect -> quiz scoring accepts stale answers

**Acceptance Criteria:**
- [ ] Short answer parts (< 3 characters) are either skipped or the matching threshold requires minimum part length
- [ ] Test with a quiz question whose answer option is "a, b" confirms the function handles short parts correctly

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz.py -v
```

### BJ-007: enforcement/hooks/_common.py bridge does not validate API surface
**Severity:** LOW
**Category:** design/coupling
**Location:** `enforcement/hooks/_common.py:1-29`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 8 (confidence: LOW)

**Problem:** The enforcement `_common.py` bridge re-exports 7 specific names from `hooks/_common.py` via importlib. If a new public function is added to `hooks/_common.py` and enforcement hooks try to import it, the import will fail at runtime with an AttributeError. No test validates that the bridge's export list stays in sync with the source module's public API.

**Evidence:** Code reading: lines 22-28 explicitly list 7 names: `read_event`, `exit_ok`, `exit_warn`, `exit_block`, `exit_stop_allow`, `exit_stop_block`, `mask_fenced_blocks`. The source module `hooks/_common.py` defines exactly these 7 public functions. Currently in sync, but brittle by design.

**Discovery Chain:** enforcement `_common.py` uses importlib to re-export from `hooks/_common.py` -> export list is manually maintained -> no test verifies sync -> future additions to source module break enforcement hooks silently

**Acceptance Criteria:**
- [ ] Either: (a) a test validates that all public functions in hooks/_common.py are re-exported by enforcement/hooks/_common.py, or (b) the bridge uses `getattr` to dynamically forward all names

**Validation Command:**
```bash
python -c "import importlib.util; spec = importlib.util.spec_from_file_location('hc', 'hooks/_common.py'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print([n for n in dir(mod) if not n.startswith('_')])"
```

# Punchlist (Merged)

**Protocol:** holtz v1.0.0
**Merge date:** 2026-03-30
**Holtz findings:** 7 (BH-001 through BH-007)
**Justine findings:** 8 (BJ-001 through BJ-008)
**Merged total:** 14

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:6 | public-contract | Badge URL says 869_total but actual test count is 874. Alt text says 874 but shield URL is stale. PAT-005 recurrence. | OPEN |
| BH-009 | bug/logic | enforcement/hooks/stop_gate.py:65 | integration | stop_gate hard-coded allow-list missing safe between-steps states. States like converged, merge_ready, merge_done, perspective_clean, all_perspectives_clean, and final_sweep_clean are not terminal and not in the allow-list. Critically, converged blocks exit — an operator who has converged cannot stop without completing three more finalize steps. Allow-list was built incrementally rather than derived from a principled rule about the state machine. | OPEN |
| BH-012 | test/missing | tests/test_integration.py:237 | contract | test_readme_metrics_match_actual checks "What's inside" prose counts but does NOT check the shields.io badge URLs. The badge at line 6 is not parsed or checked by any test. Badge is the most visible metric element and drifts most often (PAT-005), yet the test that should prevent README drift has a blind spot for the most prominent metric display. | OPEN |

## MEDIUM

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-002 | doc/drift | README.md:104 | public-contract | Prediction accuracy claims 65%/38%/0% but living punchlist tracks ~69%/~45%/0%. Stale numbers from earlier research epoch. | OPEN |
| BH-003 | doc/drift | README.md:190,161 | public-contract | Run count inconsistent: line 161 says twenty-seven, line 190 says 28, actual completed runs is 28 (run 29 in progress). LOC claim 19766 is stale, actual Python LOC ~23626. | OPEN |
| BH-004 | bug/error-handling | enforcement/hooks/_common.py:62 | error-propagation | _get_session_key_path uses except Exception: pass which swallows all exceptions including programming bugs (AttributeError, TypeError, NameError). The original error is destroyed and replaced with a downstream misleading FileNotFoundError when compute_event_proof tries to open the nonexistent default key file. Function is used by security-critical HMAC operations. | OPEN |
| BH-007 | design/duplication | enforcement/hooks/_sahjhan_bootstrap.py:66-76 | contract | _sahjhan_bootstrap.py._platform_triple() duplicates the platform triple logic from _resolve.py.sahjhan_binary(). Both independently map platform.machine() and platform.system() to a Rust target triple. If one is updated the other must be updated in lockstep or they diverge — bootstrap hook would protect a different binary path than the one _resolve.py returns. | OPEN |
| BH-008 | bug/security | enforcement/hooks/lens_quiz.py:48 | security | Quiz answer bypass via fence info string. _ANSWERS_RE lacks ^ anchor, so LENS:...ANSWERS: on a code fence opener line survives mask_fenced_blocks and matches. A subagent could embed answers in a fence info string to bypass quiz scoring. | OPEN |
| BH-010 | test/bogus | enforcement/scripts/validate_merge_report.py:20-35 | contract | validate_merge_report.py checks only that section headers exist via regex. It does not verify that sections contain any content. A merge report with four empty headers passes validation, gates the merge_complete transition, and allows the protocol to proceed to the fix loop with zero merge data. Anti-pattern #12 (Permissive Validator). | OPEN |
| BH-011 | design/duplication | scripts/token_profiler/pricing.py:51-80,115-136 | contract | get_pricing() and _custom_pricing() independently implement longest-prefix model name matching. Same algorithm, two copies. If one is updated without the other, they diverge on which pricing table entry matches a given model name. | OPEN |

## LOW

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-005 | bug/logic | enforcement/hooks/_protocol_cache.py:159-178 | security | is_git_commit() false negative for env-prefix commands. VAR=x git commit -m test is a valid bash commit command but the regex re.match(r"git\s+commit\b", seg) requires "git" as the first token, returning False. The commit tracker would miss this commit, leaving it unregistered in the enforcement cache. | OPEN |
| BH-006 | bug/logic | enforcement/hooks/_protocol_cache.py:197 | contract | is_sahjhan_cmd fails for bare platform binary names (sahjhan-aarch64-apple-darwin without path prefix). Third condition checks for /sahjhan- but not sahjhan- at start. Low impact — binary is always invoked with path. | OPEN |
| BH-013 | test/fragile | tests/test_sahjhan_integration.py:516 | component | Choose Your Own Adventure anti-pattern: or-disjunction lets test pass whether hook warned OR silently allowed a chained command. Should assert specifically for warning behavior. | OPEN |
| BH-014 | test/fragile | tests/test_token_profiler_integration.py:30 | component | Mystery Guest anti-pattern: hardcoded path to specific JSONL on one developer machine. Test skips if file absent but is a dead test in CI and for any other developer. | OPEN |

---

## Item Details

### BH-001: README badge test count stale (869 displayed vs 874 actual)
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:6`
**Perspective:** public-contract
**Status:** OPEN
**Found by:** both auditors
**Severity disagreement:** Holtz=MEDIUM, Justine=HIGH. Using HIGH.
<!-- Was: Holtz BH-001 + Justine BJ-001 -->

**Problem:** Badge URL says 869_total but actual test count is 874. Alt text says 874 but shield URL is stale. PAT-005 recurrence.

**Evidence:** `![874 tests](https://img.shields.io/badge/tests-869_total-brightgreen.svg)` — alt text "874 tests" vs URL "869_total". `python -m pytest` reports `873 passed, 1 skipped` = 874 total.

---

### BH-002: Prediction accuracy claims stale
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:104`
**Perspective:** public-contract
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-003 -->

**Problem:** Prediction accuracy claims 65%/38%/0% but living punchlist tracks ~69%/~45%/0%. Stale numbers from earlier research epoch.

---

### BH-003: Run count and LOC claims inconsistent
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:190,161`
**Perspective:** public-contract
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-002 -->

**Problem:** Run count inconsistent: line 161 says twenty-seven, line 190 says 28, actual completed runs is 28 (run 29 in progress). LOC claim 19766 is stale, actual Python LOC ~23626.

---

### BH-004: _get_session_key_path bare except swallows programming bugs
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/_common.py:62`
**Perspective:** error-propagation
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-004 -->

**Problem:** `_get_session_key_path` uses `except Exception: pass` which swallows all exceptions including programming bugs (AttributeError, TypeError, NameError). If the code in lines 48-61 has a bug, it will be silently swallowed and the function falls back to the default path. The actual error surfaces later as a misleading FileNotFoundError when `compute_event_proof` tries to open the nonexistent default key file. This is the "error destruction" anti-pattern — the original error is destroyed and replaced with a downstream symptom.

**Evidence:** Line 62: `except Exception: pass` — this catches AttributeError, TypeError, NameError, etc. The function is used by `compute_event_proof` and `record_authed_event` which are security-critical HMAC operations.

**Acceptance Criteria:**
- [ ] Exception handler narrowed to (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ImportError) or equivalent specific exceptions
- [ ] Programming bugs (AttributeError, TypeError, etc.) propagate instead of being swallowed

**Validation Command:**
```bash
python -m pytest tests/test_hmac_helpers.py -v --tb=short
```

---

### BH-005: is_git_commit false negative for env-prefix commands
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:159-178`
**Perspective:** security
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-007 -->

**Problem:** `is_git_commit()` splits on `[;&|]+` and checks each segment for `git commit` at the start. But `VAR=x git commit -m test` is a valid bash commit command (sets VAR in the environment for the git process). The regex `re.match(r"git\s+commit\b", seg)` requires "git" as the first token, so `VAR=x git commit` returns False. The commit tracker would miss this commit, leaving it unregistered in the enforcement cache.

**Evidence:** `is_git_commit('VAR=x git commit -m test')` returns False. This is a valid bash command that performs a git commit.

**Acceptance Criteria:**
- [ ] `is_git_commit('VAR=x git commit -m test')` returns True
- [ ] OR documented as a known limitation with rationale for not fixing

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from _protocol_cache import is_git_commit
print(is_git_commit('VAR=x git commit -m test'))
"
```

---

### BH-006: is_sahjhan_cmd false negative for bare binary names
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:197`
**Perspective:** contract
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-005 -->

**Problem:** is_sahjhan_cmd fails for bare platform binary names (sahjhan-aarch64-apple-darwin without path prefix). Third condition checks for /sahjhan- but not sahjhan- at start. Low impact — binary is always invoked with path.

---

### BH-007: _sahjhan_bootstrap.py duplicates platform triple logic from _resolve.py
**Severity:** MEDIUM
**Category:** design/duplication
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:66-76`
**Perspective:** contract
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-005 -->

**Problem:** `_sahjhan_bootstrap.py._platform_triple()` duplicates the platform triple logic from `_resolve.py.sahjhan_binary()`. Both independently map platform.machine() and platform.system() to a Rust target triple. If one is updated (e.g., to add Windows support), the other must be updated in lockstep or they diverge — producing a situation where the bootstrap hook protects a different binary path than the one `_resolve.py` returns.

**Evidence:** `_resolve.py:14-21` and `_sahjhan_bootstrap.py:66-76` contain identical platform detection logic. `_sahjhan_bootstrap.py` does not import from `_resolve.py`.

**Acceptance Criteria:**
- [ ] Single source of truth for platform triple computation (either import from _resolve or share a helper)
- [ ] OR explicit test that both implementations agree (equivalence test)

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from _resolve import sahjhan_binary
from _sahjhan_bootstrap import _platform_triple
binary = sahjhan_binary()
triple = _platform_triple()
assert triple in binary, f'{triple} not in {binary}'
print('OK: platform triple agrees')
"
```

---

### BH-008: Quiz answer bypass via fence info string
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/lens_quiz.py:48`
**Perspective:** security
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-004 -->

**Problem:** Quiz answer bypass via fence info string. _ANSWERS_RE lacks ^ anchor, so LENS:...ANSWERS: on a code fence opener line survives mask_fenced_blocks and matches. A subagent could embed answers in a fence info string to bypass quiz scoring.

---

### BH-009: stop_gate hard-coded allow-list missing safe between-steps states
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/stop_gate.py:65`
**Perspective:** integration
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-002 -->

**Problem:** The stop_gate allows exit from terminal states + (awaiting_clear, idle, recon). The state machine defines 14 states. States like `converged`, `merge_ready`, `merge_done`, `perspective_clean`, `all_perspectives_clean`, and `final_sweep_clean` are all "between steps" states with no active work at risk, but the stop_gate blocks exit from them. Critically, `converged` blocks exit — an operator who has converged but hasn't finalized cannot stop without completing three more steps. The hard-coded allow-list was built incrementally rather than derived from a principled rule about the state machine.

**Evidence:** stop_gate.py:65: `if is_terminal or current_state in ("awaiting_clear", "idle", "recon"):` — states.toml defines 14 states, only 4 are in the allow-list (finalized + 3). The `converged` state is reachable via confirm_convergence but is not terminal and not in the allow-list.

**Acceptance Criteria:**
- [ ] stop_gate allows exit from `converged` state (at minimum)
- [ ] Decision about other between-steps states is explicit (allow or block with documented rationale)
- [ ] Test covers the converged state specifically

**Validation Command:**
```bash
python -m pytest tests/test_sahjhan_integration.py -k "stop_gate" -v --tb=short
```

---

### BH-010: validate_merge_report.py is a Permissive Validator
**Severity:** MEDIUM
**Category:** test/bogus
**Location:** `enforcement/scripts/validate_merge_report.py:20-35`
**Perspective:** contract
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-008 -->

**Problem:** `validate_merge_report.py` checks only that section headers exist (Agreement, Holtz-Only, Justine-Only, Blind Spot Analysis) via regex. It does not verify that sections contain any content. A merge report with four empty headers passes validation, gates the `merge_complete` transition, and allows the protocol to proceed to the fix loop with zero merge data. This is anti-pattern #12 (Permissive Validator) — overly broad validation accepting wrong answers.

**Evidence:** `validate('file_with_only_headers.md')` returns `[]` (no missing sections) for a file containing just `## Agreement\n## Holtz-Only\n## Justine-Only\n## Blind Spot Analysis\n`.

**Acceptance Criteria:**
- [ ] Validator checks that at least one section has non-whitespace content below its header
- [ ] Test covers the headers-only case and expects it to fail
- [ ] OR validator checks for specific content patterns (e.g., table rows, finding IDs)

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/scripts')
from validate_merge_report import validate
import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
    f.write('## Agreement\n## Holtz-Only\n## Justine-Only\n## Blind Spot Analysis\n')
    path = f.name
missing = validate(path)
os.unlink(path)
assert len(missing) > 0, 'Headers-only report should not pass validation'
"
```

---

### BH-011: pricing.py duplicates longest-prefix matching logic
**Severity:** MEDIUM
**Category:** design/duplication
**Location:** `scripts/token_profiler/pricing.py:51-80,115-136`
**Perspective:** contract
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-006 -->

**Problem:** `get_pricing()` (lines 51-80) and `_custom_pricing()` (lines 115-136) independently implement longest-prefix model name matching. Same algorithm, two copies. If one is updated without the other, they diverge on which pricing table entry matches a given model name.

**Evidence:** Both functions contain: iterate PRICING keys skipping "unknown", check model.startswith(key), track best_len, return best match. The `_custom_pricing` closure captures a `merged` table but uses the same algorithm.

**Acceptance Criteria:**
- [ ] Single lookup function used by both code paths (extract the prefix-matching into a shared helper)
- [ ] OR equivalence test that both paths produce same results for all known model names

**Validation Command:**
```bash
python -m pytest tests/test_token_profiler_cli.py -v --tb=short
```

---

### BH-012: README badge not covered by test_readme_metrics_match_actual
**Severity:** HIGH
**Category:** test/missing
**Location:** `tests/test_integration.py:237`
**Perspective:** contract
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-003 -->

**Problem:** `test_readme_metrics_match_actual` checks the "What's inside" prose counts in the README body but does NOT check the shields.io badge URLs at the top of the file. The badge is the most visible metric element — the first thing a user sees — and it's the one that drifts most often (PAT-005). The test is supposed to prevent README drift but has a blind spot for the most prominent metric display.

**Evidence:** Test regex at line 252 matches "N skills, N agents, N reference docs, N examples, N Python scripts, N seed patterns, N enforcement hooks, N tests across N lines" — this is the "What's inside" line. The badge at line 6 (`tests-869_total`) is not parsed or checked by any test.

**Acceptance Criteria:**
- [ ] A test verifies the badge URL test count matches `pytest --collect-only` output
- [ ] A test verifies the badge URL coverage percentage matches actual coverage
- [ ] Badge drift is caught automatically in CI

**Validation Command:**
```bash
python -m pytest tests/test_integration.py -k "readme" -v --tb=short
```

---

### BH-013: Choose Your Own Adventure anti-pattern in stop_gate test
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_sahjhan_integration.py:516`
**Perspective:** component
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-006 -->

**Problem:** Choose Your Own Adventure anti-pattern: or-disjunction lets test pass whether hook warned OR silently allowed a chained command. Should assert specifically for warning behavior.

---

### BH-014: Mystery Guest anti-pattern in token profiler integration test
**Severity:** LOW
**Category:** test/fragile
**Location:** `tests/test_token_profiler_integration.py:30`
**Perspective:** component
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-007 -->

**Problem:** Mystery Guest anti-pattern: hardcoded path to specific JSONL on one developer machine. Test skips if file absent but is a dead test in CI and for any other developer.

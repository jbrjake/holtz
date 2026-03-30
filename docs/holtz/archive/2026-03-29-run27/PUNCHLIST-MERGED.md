# Punchlist (Merged)

**Protocol:** holtz v1.0.0
**Run:** 27
**Merge date:** 2026-03-29
**Holtz findings:** 5
**Justine findings:** 10 (BJ-007 discarded as false positive; 9 remaining after discard, 1 additional per verification)
**Merged total:** 11

## CRITICAL

### BH-001: Bash redirects to Sahjhan-managed files bypass both guards
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:16-21` and `enforcement/hooks/write_guard.py:20-26`
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-002 -->

**Problem:** Sahjhan-rendered files (STATUS.md, PUNCHLIST.md, SUMMARY.md, MERGE-REPORT.md, PUNCHLIST-MERGED.md) in docs/holtz/ are protected from Write/Edit tool calls by write_guard.py. However, they are NOT protected from Bash command writes because _sahjhan_bootstrap.py's PROTECTED list only covers enforcement/, bin/sahjhan, hooks/hooks.json, and _sahjhan_bootstrap.py — none of which are docs/holtz/ paths. A Bash command like `echo "hacked" > docs/holtz/STATUS.md` passes through the bootstrap hook unchecked. The bash_guard.py (manifest verify) detects modifications post-hoc but does not prevent them. An agent could corrupt audit state by writing directly to these files via Bash.

**Evidence:**
```
P3 Test Results:
  Bootstrap: echo > docs/holtz/STATUS.md: ALLOWED (BYPASS!)
  Bootstrap: echo > docs/holtz/PUNCHLIST.md: ALLOWED (BYPASS!)
  Bootstrap: echo > docs/holtz/SUMMARY.md: ALLOWED (BYPASS!)
  WriteGuard: Write to docs/holtz/STATUS.md: BLOCKED (correct)
  WriteGuard: Write to docs/holtz/PUNCHLIST.md: BLOCKED (correct)
  WriteGuard: Write to docs/holtz/SUMMARY.md: BLOCKED (correct)
```
The integration gap: write_guard.py handles Write/Edit tools correctly. _sahjhan_bootstrap.py handles Bash writes to enforcement/ correctly. Neither handles Bash writes to docs/holtz/ managed files.

**Acceptance Criteria:**
- [ ] `echo "..." > docs/holtz/STATUS.md` command is blocked by the bootstrap hook
- [ ] `echo "..." > docs/holtz/PUNCHLIST.md` command is blocked
- [ ] All 5 managed files from write_guard.py's list are also protected against Bash writes
- [ ] Regression tests cover Bash redirect/tee/cp writes to managed files

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

---

### BH-002: Interpreter execution bypass via dd, wget, python -c, xargs, find -exec
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:141-196`
**Status:** OPEN
**Found by:** both auditors
<!-- Was: Holtz BH-003 + Justine BJ-001 -->

**Problem:** The Bash command write-protection in _sahjhan_bootstrap.py uses an allowlist of specific command prefixes (sed, perl, patch, cp, mv, install, tee, redirect operators) to detect writes to protected enforcement/ paths. Commands not on this list bypass the guard entirely. python -c open(), ruby -e, node -e, dd, wget, xargs -I{} cp, and find -exec can all write to protected enforcement/ paths. BH-008 from run 26 listed python -c as a vector but the fix only addressed sed/perl/patch.

**Evidence:**
```
Justine P1 Test Results:
  dd write to enforcement: ALLOWED (BYPASS!)
  python open().write() to enforcement: ALLOWED (BYPASS!)
  wget to enforcement: ALLOWED (BYPASS!)
  xargs cp to enforcement: ALLOWED (BYPASS!)
  find -exec cp to enforcement: ALLOWED (BYPASS!)
```
The hook checks only: redirect (>, >>), tee, cp/mv/install (as first word), sed/perl (as substring), patch (as substring). All other write mechanisms pass through.

**Acceptance Criteria:**
- [ ] `dd of=enforcement/states.toml` command is blocked by the bootstrap hook
- [ ] `wget -O enforcement/hooks/primer.py` command is blocked
- [ ] `python3 -c "open('enforcement/...','w')"` command is blocked
- [ ] `ruby -e` and `node -e` writes to enforcement/ are blocked
- [ ] `xargs` and `find -exec` writes to enforcement/ are blocked
- [ ] All new bypass vectors have regression tests

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

---

## HIGH

### BH-003: Redirect guard bypass via first-occurrence check
**Severity:** HIGH
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:142-153`
**Status:** OPEN
**Found by:** both auditors
<!-- Was: Holtz BH-002 + Justine BJ-009 -->

**Problem:** Redirect guard bypass: command.find(op) returns only the first occurrence of `>` or `>>`. A quoted `>` before the real redirect (e.g., `echo '>' > enforcement/file`) causes the guard to check the wrong position, allowing protected paths to be overwritten. In multi-command chains (`echo foo > /tmp/safe && echo bar > enforcement/states.toml`), the second redirect to enforcement/ is never checked. Similarly, `cat enforcement/quiz-bank.json > /tmp/copy` is blocked because the first `>` has "enforcement/" after it in the source argument, not the target.

**Evidence:**
```python
# Line 143-150: finds FIRST redirect operator only
for op in (">", ">>"):
    idx = command.find(op)  # finds FIRST occurrence
    if idx >= 0:
        after_op = command[idx + len(op):].strip()
        if after_op.startswith(p):  # only checks text after FIRST redirect
```
A command with multiple redirects only has the first one checked.

**Acceptance Criteria:**
- [ ] All redirect operators in a command are checked, not just the first
- [ ] Quoted `>` in arguments no longer triggers false-positive blocks
- [ ] Test covers multi-redirect command chains
- [ ] Test covers `&&`-chained commands with redirect in second segment

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

---

### BH-004: CI pipeline does not enforce coverage gate
**Severity:** HIGH
**Category:** test/integration-gap
**Location:** `.github/workflows/ci.yml:33`
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-008 -->

**Problem:** The CI pipeline runs `python -m pytest --tb=short -q` without `--cov` flags. The 60% coverage gate documented in CLAUDE.md is only enforced locally. A PR could merge code that drops coverage below 60% because CI does not check it. The CLAUDE.md explains this is intentional (concurrent pytest deadlocks on .coverage SQLite), but the README and badges imply coverage is enforced. No alternative CI enforcement mechanism exists.

**Evidence:**
```yaml
# .github/workflows/ci.yml line 33:
python -m pytest --tb=short -q
# No --cov, no --cov-fail-under
```
CLAUDE.md says: "Coverage is excluded from default addopts because concurrent pytest processes (subagents, parallel sessions) deadlock on the SQLite .coverage file."

**Acceptance Criteria:**
- [ ] CI enforces the 60% coverage gate, OR
- [ ] README/badges note that coverage is local-only, OR
- [ ] An alternative CI coverage mechanism is implemented (e.g., coverage in a separate job)

**Validation Command:**
```bash
grep "cov" .github/workflows/ci.yml
```

---

## MEDIUM

### BH-005: README LOC count stale
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:190,214`
**Status:** OPEN
**Found by:** both auditors
**Severity disagreement:** Holtz=MEDIUM, Justine=HIGH. Using MEDIUM per Holtz verification (run count was correct when written; LOC drift is cosmetic).
<!-- Was: Holtz BH-001 + Justine BJ-003 -->

**Problem:** LOC count stale: 19,129 in README vs 23,585 actual (23% drift). Justine also flagged "Twenty-six runs and counting" (line 160) as stale — this is now run 27. Both instances of the LOC figure appear at lines 190 and 214.

**Evidence:**
```
README.md line 160: "Twenty-six runs and counting."  (actual: run 27)
README.md line 190: "847 tests across 19,129 lines of code"  (actual LOC: 23,585)
README.md line 214: "847 tests across 19,129 lines of code"  (same stale figure)
wc -l total: 23,585
```

**Acceptance Criteria:**
- [ ] Run count updated to reflect current run number
- [ ] Lines of code figure updated to match actual wc -l count
- [ ] Both instances of LOC figure updated (lines 190 and 214)

**Validation Command:**
```bash
grep -n "19,129\|Twenty-six" README.md
```

---

### BH-006: Chained command bypass via startsWith check
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:164-175`
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-004 -->

**Problem:** Chained command bypass: cp/mv/install check uses cmd_stripped.startswith() which only matches at command start. Chained commands (`true && cp file enforcement/`) bypass the guard because the cp does not appear at the start of the stripped command string.

**Acceptance Criteria:**
- [ ] cp/mv/install guard handles chained commands (&&, ||, ;)
- [ ] Test covers chained command bypass scenario

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v -k "chained"
```

---

### BH-007: subagent_findings_check.py regex misses non-.md audit artifacts
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/subagent_findings_check.py:33`
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-005 -->

**Problem:** The regex `docs/holtz/[^\s"')\]]+\.md` only matches files ending in `.md`. Subagent audit artifacts that are NOT markdown — impact-graph.json, .sahjhan/active-run, enforcement-cache.json — will not trigger the existence check. A subagent that claims to have written `docs/holtz/justine/impact-graph.json` but failed silently would not be flagged by this hook. The hook's entire purpose is to catch subagents that claim writes they didn't make.

**Evidence:**
```
Regex test results:
  docs/holtz/justine/impact-graph.json: matched=False (should catch)
  docs/holtz/.sahjhan/active-run: matched=False (should catch)
  docs/holtz/impact-graph.json: matched=False (should catch)
  docs/holtz/justine/PUNCHLIST.md: matched=True (correct)
```

**Acceptance Criteria:**
- [ ] Regex also matches `.json` files in docs/holtz/
- [ ] Test exists that verifies non-.md audit artifacts are checked
- [ ] 0% test coverage addressed with at least basic unit tests

**Validation Command:**
```bash
python -m pytest tests/ -k subagent -v
```

---

### BH-008: score_answers returns (0,0) for both count mismatch and all-stale scenarios
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:276-277`
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-006 -->

**Problem:** score_answers returns (0, 0) for two different failure modes: (1) answer count mismatch (line 277), (2) all questions stale (loop produces total=0). The caller at line 453 checks `len(given_answers) != len(questions)` to distinguish case 1, but if both conditions are true simultaneously (wrong answer count AND all questions stale), the mismatch check fires first and the user gets "answer count mismatch" instead of "questions stale" — the wrong error message and the wrong remediation guidance.

**Evidence:**
```python
# score_answers returns (0, 0) for BOTH:
# 1. len(questions) != len(answers) -> return 0, 0
# 2. All questions stale (total never increments) -> return 0, 0

# Caller at lines 453-465:
if len(given_answers) != len(questions):  # fires first
    exit_stop_block("Answer count mismatch...")  # wrong msg if stale
if total == 0 or total < len(questions) - MAX_STALE_QUESTIONS:  # never reached
    exit_stop_block("Too many stale questions...")
```
Confirmed: both cases return identical (0, 0) tuple.

**Acceptance Criteria:**
- [ ] score_answers returns a distinguishable signal for count mismatch vs all-stale
- [ ] Or: caller checks staleness before count mismatch
- [ ] Test verifies correct error message when all questions are stale AND answer count mismatches

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz.py -v -k "score"
```

---

## LOW

### BH-009: Test tautology: exit-zero and stderr-empty tests add no mutation value
**Severity:** LOW
**Category:** test/bogus
**Location:** `tests/test_hooks.py:114-211`
**Status:** OPEN
**Found by:** Holtz only
<!-- Was: Holtz BH-005 -->

**Problem:** 10 tautology tests: 5 exit-zero tests and 5 stderr-empty tests add zero mutation detection value. Exit code is 0 for all hook output paths. Sibling tests already cover substantive assertions.

**Acceptance Criteria:**
- [ ] Tautology tests either removed or replaced with meaningful assertions
- [ ] Mutation coverage of covered code paths is not reduced

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -v -k "exit_zero or stderr"
```

---

### BH-010: _protocol_cache.py broad exception catches mask programming errors
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `enforcement/hooks/_protocol_cache.py:35,75`
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-004 — downgraded MEDIUM→LOW per Holtz verification (fallback value 13 IS correct; code quality concern, not a bug) -->

**Problem:** _read_perspectives_total() catches `(OSError, Exception)` at line 35, which includes TypeError, ValueError, KeyError, and other programming errors. If the TOML parsing code has a bug (e.g., malformed key access), the error is silently swallowed and the function returns 13 as default. The fallback value 13 is correct, so this is a code quality concern rather than a functional bug. Separately, write_cache() catches `BaseException` at line 75 — the re-raise is correct, but the broad catch temporarily intercepts KeyboardInterrupt and SystemExit during cleanup code.

**Evidence:**
```python
# Line 35: catches ALL exceptions, not just expected ones
except (OSError, Exception):
    return 13

# Line 75: catches BaseException including KeyboardInterrupt
except BaseException:
    import contextlib
    with contextlib.suppress(OSError):
        os.unlink(tmp)
    raise
```
The `(OSError, Exception)` catch is equivalent to `except Exception` since OSError is a subclass of Exception.

**Acceptance Criteria:**
- [ ] _read_perspectives_total catches only (OSError, tomllib.TOMLDecodeError) not Exception
- [ ] write_cache BaseException catch has been reviewed for safety (re-raise is present, which is correct)
- [ ] Test exists that verifies correct behavior when TOML has unexpected structure

**Validation Command:**
```bash
python -c "from enforcement.hooks._protocol_cache import _read_perspectives_total; print(_read_perspectives_total())"
```

---

### BH-011: 0% test coverage on hooks/subagent_findings_check.py
**Severity:** LOW
**Category:** test/missing
**Location:** `hooks/subagent_findings_check.py`
**Status:** OPEN
**Found by:** Justine only
<!-- Was: Justine BJ-010 -->

**Problem:** hooks/subagent_findings_check.py has 0% line coverage per the coverage report (27/27 lines uncovered). While test_hooks.py TestSubagentFindingsCheck class exists and tests the hook via subprocess invocation, these subprocess tests do NOT contribute to the `--cov=hooks` coverage measurement because the code runs in a child process. The coverage report accurately shows 0% because no in-process test exercises the module's functions directly. Functional coverage exists but metric coverage is 0%.

**Evidence:**
```
Coverage report line:
hooks/subagent_findings_check.py    27    27    0%   14-59
```
test_hooks.py does test via subprocess (lines 306-359) but subprocess-based tests don't count toward coverage.

**Acceptance Criteria:**
- [ ] Either: add in-process unit tests that import and call main() directly, OR
- [ ] Document that subprocess-based tests cover this module but don't appear in coverage metrics

**Validation Command:**
```bash
python -m pytest --cov=hooks --cov-report=term-missing -k subagent
```

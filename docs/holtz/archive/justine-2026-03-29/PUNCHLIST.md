# Holtz Punchlist
> Generated: 2026-03-29 | Project: holtz v0.72.0 | Baseline: 847 pass, 0 fail, 0 skip
> Auditor: Justine (breadth-first adversarial)

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 2 | 0 | 0 |
| HIGH | 3 | 0 | 0 |
| MEDIUM | 4 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

(none yet)

## Items

### BJ-001: _sahjhan_bootstrap.py Bash write bypass via dd, wget, python -c, xargs, find -exec
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:141-195`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Predicted:** Prediction P1 (confidence: HIGH)

**Problem:** The Bash command write-protection in _sahjhan_bootstrap.py uses an allowlist of specific command prefixes (sed, perl, patch, cp, mv, install, tee, redirect operators) to detect writes to protected enforcement/ paths. Commands not on this list bypass the guard entirely. Confirmed bypass vectors: `dd of=enforcement/...`, `wget -O enforcement/...`, `python3 -c "open('enforcement/...','w').write(...)"`, `xargs -I{} cp {} enforcement/...`, `find -exec cp {} enforcement/... \;`. An agent or subagent could use any of these to modify enforcement hooks, states.toml, or other protected infrastructure during an audit session.

**Evidence:**
```
P1 Test Results:
  dd write to enforcement: ALLOWED (BYPASS!)
  python open().write() to enforcement: ALLOWED (BYPASS!)
  wget to enforcement: ALLOWED (BYPASS!)
  xargs cp to enforcement: ALLOWED (BYPASS!)
  find -exec cp to enforcement: ALLOWED (BYPASS!)
```
The hook checks only: redirect (>, >>), tee, cp/mv/install (as first word), sed/perl (as substring), patch (as substring). All other write mechanisms pass through.

**Discovery Chain:** Holtz's recon flagged bash_guard/write_guard as cold security-critical files -> read _sahjhan_bootstrap.py Bash filtering code (lines 141-195) -> enumerated checked commands (redirect, tee, cp/mv/install, sed/perl, patch) -> tested unchecked commands (dd, wget, python -c, xargs, find -exec) -> 5 of 7 bypass vectors confirmed

**Acceptance Criteria:**
- [ ] `dd of=enforcement/states.toml` command is blocked by the bootstrap hook
- [ ] `wget -O enforcement/hooks/primer.py` command is blocked
- [ ] `python3 -c "open('enforcement/...','w')"` command is blocked
- [ ] `xargs` and `find -exec` writes to enforcement/ are blocked
- [ ] All new bypass vectors have regression tests

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

### BJ-002: Bash redirects to Sahjhan-managed files bypass both guards
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:16-21` and `enforcement/hooks/write_guard.py:20-26`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Predicted:** Prediction P3 (confidence: HIGH)

**Problem:** Sahjhan-rendered files (STATUS.md, PUNCHLIST.md, SUMMARY.md, MERGE-REPORT.md, PUNCHLIST-MERGED.md) in docs/holtz/ are protected from Write/Edit tool calls by write_guard.py. However, they are NOT protected from Bash command writes because _sahjhan_bootstrap.py's PROTECTED list only covers enforcement/, bin/sahjhan, hooks/hooks.json, and _sahjhan_bootstrap.py -- none of which are docs/holtz/ paths. A Bash command like `echo "hacked" > docs/holtz/STATUS.md` passes through the bootstrap hook unchecked. The bash_guard.py (manifest verify) detects modifications post-hoc but does not prevent them. An agent could corrupt audit state by writing directly to these files via Bash.

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

**Discovery Chain:** Recon noted write_guard.py protects 5 specific files via Write/Edit -> read _sahjhan_bootstrap.py PROTECTED list -> docs/holtz/ paths absent from PROTECTED -> tested Bash redirect to each managed file -> all 3 pass through bootstrap unchecked

**Acceptance Criteria:**
- [ ] `echo "..." > docs/holtz/STATUS.md` command is blocked by the bootstrap hook
- [ ] `echo "..." > docs/holtz/PUNCHLIST.md` command is blocked
- [ ] All 5 managed files from write_guard.py's list are also protected against Bash writes
- [ ] Regression tests cover Bash redirect/tee/cp writes to managed files

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

### BJ-003: README claims stale: run count, lines of code
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160,190,214`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction P5 (confidence: MEDIUM)

**Problem:** README.md contains stale metrics: (1) "Twenty-six runs and counting" but this is run 27. (2) "19,129 lines of code" but actual count is 23,585 lines (23% larger than claimed). (3) "847 tests across 19,129 lines of code" repeated at line 214 with same stale LOC figure. The test count (847) and pattern count (16) are currently accurate.

**Evidence:**
```
README.md line 160: "Twenty-six runs and counting."  (actual: 27)
README.md line 190: "847 tests across 19,129 lines of code"  (actual LOC: 23,585)
README.md line 214: "847 tests across 19,129 lines of code"  (same stale figure)
wc -l total: 23,585
```

**Discovery Chain:** Recon prediction P5 flagged README drift -> counted lines with wc -l -> 23,585 vs claimed 19,129 -> also checked run count claim -> "twenty-six" vs actual run 27

**Acceptance Criteria:**
- [ ] Run count updated to reflect current run number
- [ ] Lines of code figure updated to match actual wc -l count
- [ ] Both instances of LOC figure updated (lines 190 and 214)

**Validation Command:**
```bash
grep -n "19,129\|Twenty-six" README.md
```

### BJ-004: _protocol_cache.py broad exception catches mask programming errors
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/_protocol_cache.py:35,75`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** error-propagation
**Predicted:** Prediction P2 (confidence: HIGH)

**Problem:** _read_perspectives_total() catches `(OSError, Exception)` at line 35, which includes TypeError, ValueError, KeyError, and other programming errors. If the TOML parsing code has a bug (e.g., malformed key access), the error is silently swallowed and the function returns 13 as default. Downstream code (empty_cache, protocol_tracker, primer) treats this as the actual perspective count. Separately, write_cache() catches `BaseException` at line 75 -- the re-raise is correct, but the broad catch temporarily intercepts KeyboardInterrupt and SystemExit during cleanup code that itself could fail.

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
The `(OSError, Exception)` catch is equivalent to `except Exception` since OSError is a subclass of Exception. This masks unexpected errors like TypeError from accessing a key that doesn't exist in the TOML structure.

**Discovery Chain:** Recon flagged broad exception catches in _protocol_cache.py -> inspected _read_perspectives_total line 35 -> `(OSError, Exception)` catches all non-BaseException errors -> tested: function returns 13 silently on any failure -> downstream code treats 13 as authoritative perspective count

**Acceptance Criteria:**
- [ ] _read_perspectives_total catches only (OSError, tomllib.TOMLDecodeError) not Exception
- [ ] write_cache BaseException catch has been reviewed for safety (re-raise is present, which is correct)
- [ ] Test exists that verifies correct behavior when TOML has unexpected structure

**Validation Command:**
```bash
python -c "from enforcement.hooks._protocol_cache import _read_perspectives_total; print(_read_perspectives_total())"
```

### BJ-005: subagent_findings_check.py regex misses non-.md audit artifacts
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/subagent_findings_check.py:33`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Predicted:** Prediction P4 (confidence: MEDIUM)

**Problem:** The regex `docs/holtz/[^\s"')\]]+\.md` only matches files ending in `.md`. Subagent audit artifacts that are NOT markdown -- impact-graph.json, .sahjhan/active-run, enforcement-cache.json -- will not trigger the existence check. A subagent that claims to have written `docs/holtz/justine/impact-graph.json` but failed silently would not be flagged by this hook. The hook's entire purpose is to catch subagents that claim writes they didn't make.

**Evidence:**
```
Regex test results:
  docs/holtz/justine/impact-graph.json: matched=False (should catch)
  docs/holtz/.sahjhan/active-run: matched=False (should catch)
  docs/holtz/impact-graph.json: matched=False (should catch)
  docs/holtz/justine/PUNCHLIST.md: matched=True (correct)
```

**Discovery Chain:** Recon noted 0% coverage on subagent_findings_check.py -> read source -> regex hardcodes `.md` suffix -> tested against non-.md audit artifacts -> JSON and extensionless files not caught

**Acceptance Criteria:**
- [ ] Regex also matches `.json` files in docs/holtz/
- [ ] Test exists that verifies non-.md audit artifacts are checked
- [ ] 0% test coverage addressed with at least basic unit tests

**Validation Command:**
```bash
python -m pytest tests/ -k subagent -v
```

### BJ-006: score_answers returns (0,0) for both count mismatch and all-stale scenarios
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:276-277`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction P6 (confidence: MEDIUM)

**Problem:** score_answers returns (0, 0) for two different failure modes: (1) answer count mismatch (line 277), (2) all questions stale (loop produces total=0). The caller at line 453 checks `len(given_answers) != len(questions)` to distinguish case 1, but if both conditions are true simultaneously (wrong answer count AND all questions stale), the mismatch check fires first and the user gets "answer count mismatch" instead of "questions stale" -- the wrong error message and the wrong remediation guidance.

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

**Discovery Chain:** Read lens_quiz.py score_answers -> noted (0,0) return for count mismatch at L277 -> traced call site at L450-465 -> mismatch check precedes staleness check -> when both conditions true, mismatch error shadows staleness error

**Acceptance Criteria:**
- [ ] score_answers returns a distinguishable signal for count mismatch vs all-stale
- [ ] Or: caller checks staleness before count mismatch
- [ ] Test verifies correct error message when all questions are stale AND answer count mismatches

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz.py -v -k "score"
```

### BJ-007: README claims four non-existent lenses and wrong counts
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:38,50,114,146,214`
**Status:** OPEN
**Lens:** contract

**Problem:** Multiple README claims are factually wrong: (1) "seventeen anti-patterns across three tiers" (line 50) -- actual count is 12 anti-patterns (4+4+4). The 7-item "Audit Checklist" is a scoring rubric, not additional anti-patterns. (2) "thirteen analytical lenses" (lines 38, 114, 146) -- the lens-registry.md defines 9 lenses. Protocol.toml lists 13 perspective values, but 4 (concurrency, resource-lifecycle, idempotency, observability) have no lens definition in the registry. The convergence loop references lenses that don't exist as documented entities. (3) "24 reference docs" (line 214) -- actual count is 17 reference docs.

**Evidence:**
```
Anti-patterns: 12 numbered entries in anti-patterns.md (Tier 1: 4, Tier 2: 4, Tier 3: 4)
Lens registry: 9 ## headings in lens-registry.md (component through public-contract)
Protocol.toml: 13 perspective values (adds concurrency, resource-lifecycle, idempotency, observability)
Reference docs: 17 .md files in skills/holtz/references/
```

**Discovery Chain:** README claims "seventeen anti-patterns" -> counted anti-patterns.md -> 12 entries not 17 -> checked lens count -> 9 in registry vs 13 claimed -> checked reference doc count -> 17 not 24

**Acceptance Criteria:**
- [ ] Anti-pattern count corrected to 12 (or README explains the 7 checklist items are counted)
- [ ] Lens count corrected or missing 4 lens definitions added to registry
- [ ] Reference doc count corrected to 17

**Validation Command:**
```bash
grep -c "^## " skills/holtz/references/lens-registry.md
```

### BJ-008: CI pipeline does not enforce coverage gate
**Severity:** HIGH
**Category:** test/integration-gap
**Location:** `.github/workflows/ci.yml:33`
**Status:** OPEN
**Lens:** integration

**Problem:** The CI pipeline runs `python -m pytest --tb=short -q` without `--cov` flags. The 60% coverage gate documented in CLAUDE.md is only enforced locally. A PR could merge code that drops coverage below 60% because CI does not check it. The CLAUDE.md explains this is intentional (concurrent pytest deadlocks on .coverage SQLite), but the README and badges imply coverage is enforced.

**Evidence:**
```yaml
# .github/workflows/ci.yml line 33:
python -m pytest --tb=short -q
# No --cov, no --cov-fail-under
```
CLAUDE.md says: "Coverage is excluded from default addopts because concurrent pytest processes (subagents, parallel sessions) deadlock on the SQLite .coverage file."

**Discovery Chain:** Holtz's recon flagged CI missing coverage gate -> read ci.yml -> confirmed no --cov flags -> read CLAUDE.md for rationale -> valid technical reason exists BUT no alternative enforcement mechanism

**Acceptance Criteria:**
- [ ] CI enforces the 60% coverage gate, OR
- [ ] README/badges note that coverage is local-only, OR
- [ ] An alternative CI coverage mechanism is implemented (e.g., coverage in a separate job)

**Validation Command:**
```bash
grep "cov" .github/workflows/ci.yml
```

### BJ-009: _sahjhan_bootstrap.py redirect check misses multi-command redirect chains
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:143-150`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** The redirect check uses `command.find(op)` to find the FIRST occurrence of `>` or `>>` in the command string. In a multi-command chain like `echo foo > /tmp/safe && echo bar > enforcement/states.toml`, the check finds the first `>` (targeting /tmp/safe), sees it doesn't target a protected path, and allows the command. The second redirect to enforcement/ is never checked. Similarly, `cat enforcement/quiz-bank.json > /tmp/copy` is blocked because the first `>` has "enforcement/" after it (in the source argument, not the target).

**Evidence:**
```python
# Line 143-150: finds FIRST redirect operator only
for op in (">", ">>"):
    idx = command.find(op)  # finds FIRST occurrence
    if idx >= 0:
        after_op = command[idx + len(op):].strip()
        if after_op.startswith(p):  # only checks text after FIRST redirect
```
A command with multiple redirects would only check the first one.

**Discovery Chain:** Read _sahjhan_bootstrap.py redirect logic -> `command.find(op)` returns first index only -> multi-redirect commands have second redirect unchecked -> constructed bypass: `echo x > /tmp/safe && echo y > enforcement/states.toml`

**Acceptance Criteria:**
- [ ] All redirect operators in a command are checked, not just the first
- [ ] Test covers multi-redirect command chains
- [ ] Test covers `&&`-chained commands with redirect in second segment

**Validation Command:**
```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

### BJ-010: 0% test coverage on hooks/subagent_findings_check.py
**Severity:** LOW
**Category:** test/missing
**Location:** `hooks/subagent_findings_check.py`
**Status:** OPEN
**Lens:** component

**Problem:** hooks/subagent_findings_check.py has 0% line coverage per the coverage report (27/27 lines uncovered). While test_hooks.py TestSubagentFindingsCheck class exists and tests the hook via subprocess invocation, these subprocess tests do NOT contribute to the `--cov=hooks` coverage measurement because the code runs in a child process. The coverage report accurately shows 0% because no in-process test exercises the module's functions directly.

**Evidence:**
```
Coverage report line:
hooks/subagent_findings_check.py    27    27    0%   14-59
```
test_hooks.py does test via subprocess (lines 306-359) but subprocess-based tests don't count toward coverage.

**Discovery Chain:** Recon flagged 0% coverage -> found test_hooks.py has 5 subprocess tests for this module -> realized subprocess tests don't contribute to --cov measurement -> confirmed: functional coverage exists but metric coverage is 0%

**Acceptance Criteria:**
- [ ] Either: add in-process unit tests that import and call main() directly, OR
- [ ] Document that subprocess-based tests cover this module but don't appear in coverage metrics

**Validation Command:**
```bash
python -m pytest --cov=hooks --cov-report=term-missing -k subagent
```

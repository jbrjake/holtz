# Holtz Punchlist — Merged (Run 26)

> Generated: 2026-03-29 | Run: 26 | Merge: Holtz (14 findings) + Justine (15 findings) → 24 unified items

## Summary

| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1 | 0 | 0 |
| HIGH | 5 | 0 | 0 |
| MEDIUM | 9 | 0 | 0 |
| LOW | 9 | 0 | 0 |
| **Total** | **24** | **0** | **0** |

## Patterns

### Pattern: PAT-001: Fenced-Block Masking Absent
**Instances:** BH-019
**Root Cause:** Code that operates on raw message text skips the mask_fenced_blocks() step, causing regex patterns to match content inside code examples.
**Systemic Fix:** Add a lint rule or code review checklist item: any regex applied to user/tool messages must call mask_fenced_blocks() first.
**Detection Rule:** `grep -n "re\.\(findall\|search\|match\)" hooks/ | grep -v mask_fenced`

### Pattern: PAT-002: Permissive Validator / Rubber Stamp Tests
**Instances:** BH-009, BH-014, BH-017, BH-021, BH-022
**Root Cause:** Validators default to passing on unrecognized input rather than rejecting. Tests cover only happy paths, missing edge cases that reveal the permissive defaults.
**Systemic Fix:** Adopt explicit allowlist validation with strict failure on unrecognized input. Add edge-case test requirements to the test authoring checklist.
**Detection Rule:** `grep -n "\.get(.*0)" enforcement/scripts/` for rank-0 defaults; review test files for missing negative/edge-case tests.

### Pattern: PAT-003: Read Guard Substring Bypass
**Instances:** BH-010, BH-015
**Root Cause:** Security guards implemented as substring or regex matching can be bypassed via indirection (variable expansion, base64, symlinks, tool prefixes).
**Systemic Fix:** Document guards as advisory/defense-in-depth; add architecture baseline note that they are not security boundaries.
**Detection Rule:** Search for substring-based guard implementations in enforcement/hooks/.

---

## Items

---

### BH-001: STATUS.md/PUNCHLIST.md render from wrong ledger
**Severity:** CRITICAL
**Category:** bug/state
**Location:** `docs/holtz/.sahjhan/ledgers.toml`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Found by:** Holtz only
<!-- Was: Holtz BH-001 -->

**Problem:** STATUS.md/PUNCHLIST.md template references ledger named `run`, but the registered ledger is `run-26`. The render falls back to the default ledger and shows stale or incorrect protocol state. All STATUS.md output for this run reflects wrong ledger data.

**Evidence:** `ledgers.toml` registers ledger `run-26`; template references `run`; fallback to default ledger confirmed.

**Discovery Chain:** Read ledgers.toml -> ledger name mismatch -> template fallback -> STATUS.md shows wrong data

**Acceptance Criteria:**
- [ ] ledgers.toml ledger name matches the name used in template references, or template is updated to use the canonical name
- [ ] STATUS.md renders current run-26 ledger data

**Validation Command:**
```bash
python -m pytest tests/ -v -k ledger
```

---

### BH-002: _active_ledger() always returns None — hooks write to wrong ledger
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/_common.py:32-39`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Found by:** Holtz only
<!-- Was: Holtz BH-005 -->

**Problem:** `_active_ledger()` checks for an active-run marker file that has never existed. The function always returns None. All hooks write quiz/context events to the default ledger instead of the run-specific ledger. Gate conditions that read the run-specific ledger cannot see hook events.

**Evidence:** Active-run marker file path does not exist; function unconditionally returns None; all hook writes go to default ledger.

**Discovery Chain:** Read _active_ledger() -> checks non-existent marker file -> always None -> all events written to default ledger -> gate conditions blind to events

**Acceptance Criteria:**
- [ ] `_active_ledger()` returns the correct run-specific ledger when a run is active
- [ ] Hooks write events to the run-specific ledger
- [ ] Gate conditions can see hook-written events

**Validation Command:**
```bash
python -m pytest tests/ -v -k active_ledger
```

---

### BH-003: lens_quiz.py record_authed_event unprotected from FileNotFoundError
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `enforcement/hooks/lens_quiz.py:344-395`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** error-propagation
**Found by:** Holtz only
<!-- Was: Holtz BH-007 -->

**Problem:** `record_authed_event` calls in lens_quiz.py are not wrapped with FileNotFoundError protection when session.key is absent. primer.py wraps these calls with `suppress`, but lens_quiz.py does not. A missing session key causes an unhandled exception that crashes the quiz hook.

**Evidence:** lens_quiz.py:344-395 calls record_authed_event without suppress(FileNotFoundError) wrapper; primer.py has the wrapper; lens_quiz.py does not.

**Discovery Chain:** Read primer.py error handling -> suppress(FileNotFoundError) wrapper -> read lens_quiz.py -> no equivalent wrapper -> crash on missing session key

**Acceptance Criteria:**
- [ ] `record_authed_event` calls in lens_quiz.py are protected from FileNotFoundError
- [ ] Test verifies lens_quiz.py handles missing session key gracefully

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz_integration.py -v
```

---

### BH-004: _sahjhan_bootstrap.py read-guard bypass via sed/perl/patch
**Severity:** HIGH
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Severity disagreement:** Holtz=HIGH, Justine=LOW
**Found by:** both auditors
<!-- Was: Holtz BH-008 + Justine JH-010 -->

**Problem:** `_bash_references_guarded()` uses substring/regex matching to block reads of protected enforcement paths. This guard is trivially bypassed by `sed -i`, `perl -pi`, `patch`, `python -c open()`, and indirect Bash patterns (variable expansion, base64, symlinks, env var prefixes). Session key can be read or modified via indirect commands.

**Evidence:** Holtz: `sed -i`, `perl -pi`, `patch`, `python -c open()` all write to protected paths without being blocked. Justine: `_bash_references_guarded("cat .sahjhan/session.*", "/tmp")` returns None; all indirect Bash patterns bypass.

**Justine note:** Justine rates this LOW and recommends documenting as advisory/defense-in-depth rather than fixing. Holtz rates HIGH.

**Discovery Chain:** Read guard implementation -> substring match only -> tested indirect access patterns -> all bypass -> read and write protection illusory

**Acceptance Criteria:**
- [ ] Either: guard is strengthened to block known bypass vectors; or architecture baseline documents guard as advisory with explicit threat model scope
- [ ] Test verifies known bypass vectors are either caught or documented

**Validation Command:**
```bash
python -m pytest tests/ -v -k bootstrap
```

---

### BH-005: test_evidence_rejects_rubber_stamp tests wrong code path
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_lens_quiz_integration.py:test_evidence_rejects_rubber_stamp`
**Status:** OPEN
**Lens:** component
**Found by:** Holtz only
<!-- Was: Holtz BH-011 -->

**Problem:** The test uses flat-format content against a `min_reads=5` threshold. Rejection fires from the read-count gate, not from rubber-stamp detection. The test name claims to validate rubber-stamp logic but actually validates a different gate. The rubber-stamp path goes untested.

**Evidence:** Test content is flat format; rejection triggered by read-count gate (min_reads=5); rubber-stamp detection code path not exercised.

**Discovery Chain:** Read test -> flat content, min_reads=5 threshold -> rejection from read-count gate -> rubber-stamp detection not reached -> wrong code path tested

**Acceptance Criteria:**
- [ ] Test is rewritten to use content that passes the read-count gate and is rejected specifically by rubber-stamp detection
- [ ] Or test is renamed/restructured to accurately reflect what it validates

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz_integration.py::test_evidence_rejects_rubber_stamp -v
```

---

### BH-006: HMAC null byte injection enables field boundary spoofing
**Severity:** HIGH
**Category:** bug/security
**Location:** `enforcement/hooks/_common.py:82`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Found by:** both auditors
<!-- Was: Holtz BH-014 + Justine JH-001 -->

**Problem:** `compute_event_proof()` joins fields with null byte (`\0`) separator but does not validate that field values are free of null bytes. A value containing `\0` produces a payload byte-identical to one with additional fields, enabling HMAC collision and potential forgery.

**Evidence:** `compute_event_proof("quiz_answered", {"auditor": "holtz\x00score=5/5"}, key_path)` produces identical proof to `compute_event_proof("quiz_answered", {"auditor": "holtz", "score": "5/5"}, key_path)`.

**Discovery Chain:** Read HMAC payload construction -> separator is `\0` -> values not sanitized -> constructed collision -> confirmed identical payloads

**Acceptance Criteria:**
- [ ] `compute_event_proof()` rejects or escapes null bytes in field keys and values
- [ ] Test verifies null-byte value produces different proof or raises ValueError

**Validation Command:**
```bash
python -m pytest tests/test_hmac_helpers.py -v
```

---

### BH-007: HMAC null byte tests absent (Rubber Stamp)
**Severity:** HIGH
**Category:** test/shallow
**Location:** `tests/test_hmac_helpers.py`
**Status:** OPEN
**Lens:** security
**Found by:** Justine only
<!-- Was: Justine JH-014 -->

**Problem:** 4 tests verify HMAC consistency and correctness but zero tests exercise null byte injection (the vulnerability in BH-006). Tests validate format and signature presence — Rubber Stamp pattern — rather than the actual security property. The security vulnerability exists without any test that would detect it or a fix that would break existing tests.

**Evidence:** No test passes a field value containing `\x00`. All existing tests pass even with the vulnerable implementation.

**Discovery Chain:** Found JH-001/BH-006 -> checked test coverage -> 0 null byte tests -> Rubber Stamp confirmed -> vulnerability exists with no test signal

**Acceptance Criteria:**
- [ ] Test verifies null-byte field value either raises ValueError or produces a distinct proof from the non-null-byte equivalent
- [ ] Fix to BH-006 causes the new test to pass

**Validation Command:**
```bash
python -m pytest tests/test_hmac_helpers.py -v
```

---

### BH-008: check_sweep_evidence counts entire session, not final sweep
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/scripts/check_sweep_evidence.py:18-45`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Found by:** Holtz only
<!-- Was: Holtz BH-006 -->

**Problem:** `count_distinct_reads` counts ALL file reads in the session transcript, not just reads in the final sweep. Any session with 30+ total reads across the entire session passes the sweep gate, regardless of whether the final sweep actually read any files. The gate is trivially satisfied by any long-running session.

**Evidence:** Function iterates the full transcript without filtering to the final-sweep window; 30+ reads anywhere in session passes gate.

**Discovery Chain:** Read check_sweep_evidence.py -> count_distinct_reads iterates full transcript -> no final-sweep window filter -> any session with 30+ total reads passes gate

**Acceptance Criteria:**
- [ ] `count_distinct_reads` counts only reads that occur within the final sweep (after the last sweep-start marker)
- [ ] Test verifies a session with 30+ early reads but 0 sweep reads fails the gate

**Validation Command:**
```bash
python -m pytest tests/test_sweep_evidence.py -v
```

---

### BH-009: Unknown severity rank 0 passes downgrade check
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/scripts/check_severity_change.py:25`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract
**Found by:** both auditors
<!-- Was: Holtz BH-009 + Justine JH-002 -->

**Problem:** `SEVERITY_ORDER.get(original_severity, 0)` returns 0 for unrecognized inputs (typos, empty string, None). Any valid resolved severity ranks >= 1, so a downgrade from an unknown/typo severity silently passes the downgrade check without triggering the evidence requirement.

**Evidence:** Holtz: Unknown severity maps to rank 0; resolved ranks always >= 1; downgrade passes silently. Justine: `check_downgrade("", "LOW", None)` returns True; should reject unrecognized input.

**Discovery Chain:** Read SEVERITY_ORDER dict -> default 0 for unknown -> tested empty string and typo values -> all pass downgrade check silently

**Acceptance Criteria:**
- [ ] `check_downgrade()` rejects unrecognized severity values (returns False or raises ValueError)
- [ ] Tests cover empty string, None, and typo inputs

**Validation Command:**
```bash
python -m pytest tests/test_severity_change.py -v
```

---

### BH-010: _sahjhan_bootstrap.py read guard also bypassed via shell indirection
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/_protocol_cache.py:178`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Found by:** Justine only
<!-- Was: Justine JH-011 -->

**Problem:** `is_sahjhan_cmd()` checks `parts[0]` only. Commands with env var prefixes (`FOO=bar ./bin/sahjhan`) or `time` wrappers cause misidentification — stall counter is incorrectly incremented for sahjhan commands, or not incremented for disguised ones.

**Evidence:** `is_sahjhan_cmd("FOO=bar ./bin/sahjhan status")` returns False; stall counter incremented incorrectly.

**Discovery Chain:** Read parts[0] check -> tested env prefix -> returns False -> stall counter incremented incorrectly for sahjhan invocation

**Acceptance Criteria:**
- [ ] `is_sahjhan_cmd()` scans all segment parts or strips env var assignments before checking
- [ ] Test verifies env-prefixed sahjhan commands are correctly identified

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py -v -k sahjhan
```

---

### BH-011: Answer count mismatch shows wrong error message
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:360-365`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Found by:** Holtz only
<!-- Was: Holtz BH-010 -->

**Problem:** When answer count does not match expected, the function returns `(0, 0)` which triggers the stale-questions error message path. The wrong error message is shown for the wrong condition, making debugging the quiz hook confusing.

**Evidence:** lens_quiz.py:360-365 returns (0,0) on count mismatch; (0,0) return value triggers stale-questions message; actual failure is answer count mismatch.

**Discovery Chain:** Read lens_quiz.py -> answer count mismatch -> returns (0,0) -> (0,0) triggers stale-questions error message -> wrong diagnostic shown

**Acceptance Criteria:**
- [ ] Answer count mismatch returns a distinct sentinel or raises a specific error with a correct message
- [ ] Test verifies the correct error message is emitted for count mismatch vs stale questions

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz_integration.py -v -k answer_count
```

---

### BH-012: Coverage gate not enforced in CI
**Severity:** MEDIUM
**Category:** bug/infrastructure
**Location:** `.github/workflows/ci.yml`
**Status:** OPEN
**Lens:** integration
**Found by:** Justine only
<!-- Was: Justine JH-008 -->

**Problem:** CI runs pytest without `--cov` or `--cov-fail-under` flags. The 60% coverage gate documented in CLAUDE.md is manual-only; CI passes regardless of coverage regression.

**Evidence:** CI step: `python -m pytest --tb=short -q` — no coverage flags present. CLAUDE.md documents 60% gate as required for full runs.

**Discovery Chain:** Read CI workflow -> no --cov flags -> CLAUDE.md says 60% gate is required -> gap confirmed -> coverage can regress without CI signal

**Acceptance Criteria:**
- [ ] CI includes `--cov-fail-under=60`, or CLAUDE.md is updated to document the exclusion as an accepted trade-off with rationale

**Validation Command:**
```bash
grep 'cov' .github/workflows/ci.yml
```

---

### BH-013: test_severity_change.py has no edge case coverage (Rubber Stamp)
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_severity_change.py`
**Status:** OPEN
**Lens:** contract
**Found by:** Justine only
<!-- Was: Justine JH-012 -->

**Problem:** 5 tests cover only happy paths. Zero tests for unrecognized severity, empty strings, case sensitivity, or None inputs. The tests pass even when the implementation silently accepts invalid input (BH-009, BH-014). Rubber Stamp + Permissive Validator anti-patterns both present.

**Evidence:** No tests for empty string, None, lowercase, or typo severity inputs; all existing tests pass with the buggy implementation.

**Discovery Chain:** Audited test file -> 5 tests all happy path -> manually tested edges -> found BH-009 and BH-014 (case sensitivity) that these tests miss

**Acceptance Criteria:**
- [ ] Tests for empty string, None, lowercase, and typo severity inputs
- [ ] Tests verify function rejects invalid input
- [ ] Fixes to BH-009 and BH-014 cause new tests to pass

**Validation Command:**
```bash
python -m pytest tests/test_severity_change.py -v
```

---

### BH-014: check_severity_change is case-sensitive without normalization
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/scripts/check_severity_change.py:25`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract
**Found by:** Justine only
<!-- Was: Justine JH-003 -->

**Problem:** `SEVERITY_ORDER` only contains uppercase keys with no `.upper()` normalization on inputs. Lowercase or mixed-case severity strings (e.g., `"high"`, `"High"`) yield rank 0 via the default, triggering the same silent-pass behavior as BH-009.

**Evidence:** `check_downgrade("HIGH", "low", None)` returns False, treating a same-severity comparison as a downgrade.

**Discovery Chain:** Read SEVERITY_ORDER keys (all uppercase) -> no input normalization -> tested lowercase -> misclassified as rank 0

**Acceptance Criteria:**
- [ ] Inputs normalized to uppercase before lookup, or non-canonical case explicitly rejected
- [ ] Test covers mixed-case inputs

**Validation Command:**
```bash
python -m pytest tests/test_severity_change.py -v
```

---

### BH-015: subagent_findings_check.py has 0% test coverage
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/subagent_findings_check.py`
**Status:** OPEN
**Lens:** component
**Found by:** Justine only
<!-- Was: Justine JH-009 -->

**Problem:** Entire file (27 statements) has zero test coverage. No test exercises any logic path — neither the no-paths branch, the all-exist branch, the some-missing branch, nor the empty-message branch.

**Evidence:** Coverage report: `hooks/subagent_findings_check.py: 27 miss, 0%`.

**Discovery Chain:** Coverage report -> 0% on subagent_findings_check -> no test file exists -> all logic paths untested

**Acceptance Criteria:**
- [ ] Test file covers: no paths -> exit_ok, all exist -> exit_ok, some missing -> exit_warn, empty message -> exit_ok

**Validation Command:**
```bash
python -m pytest --cov=hooks --cov-report=term-missing | grep subagent
```

---

### BH-016: Sleep detection bypass via sleep infinity and subshell wrapping
**Severity:** MEDIUM
**Category:** bug/enforcement
**Location:** `enforcement/hooks/protocol_tracker.py:48`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Found by:** Justine only
<!-- Was: Justine JH-004 -->

**Problem:** `_is_sleep_cmd()` only matches numeric sleep values via `\d+` regex. `sleep infinity`, `sleep INF`, `(sleep 100)` (subshell), and `sleep $VAR` all bypass detection, evading the stall counter double penalty intended for sleep abuse.

**Evidence:** `_is_sleep_cmd("sleep infinity")` returns False. `_is_sleep_cmd("(sleep 100)")` returns False.

**Discovery Chain:** Read regex -> only matches `\d+` -> tested non-numeric values -> bypassed -> stall penalty not applied

**Acceptance Criteria:**
- [ ] `_is_sleep_cmd()` detects `sleep infinity`/`sleep INF` and subshell-wrapped sleep
- [ ] Tests verify these bypass vectors are caught

**Validation Command:**
```bash
python -m pytest tests/test_sleep_detection.py -v
```

---

### BH-017: test_sweep_evidence.py missing boundary and empty transcript tests
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_sweep_evidence.py`
**Status:** OPEN
**Lens:** component
**Found by:** Justine only
<!-- Was: Justine JH-013 -->

**Problem:** 3 tests, no edge cases. Missing: empty transcript, malformed JSON, and exact boundary test (exactly `min_reads` count). Without the boundary test, off-by-one errors in BH-008 fix are not caught.

**Evidence:** No `test_empty_transcript` or `test_exact_boundary` in file.

**Discovery Chain:** Audited test file -> 3 tests -> identified 4 missing scenarios -> boundary test absence means BH-008 fix can have off-by-one with no signal

**Acceptance Criteria:**
- [ ] Boundary test: exactly min_reads reads passes; min_reads - 1 fails
- [ ] Empty transcript test added

**Validation Command:**
```bash
python -m pytest tests/test_sweep_evidence.py -v
```

---

### BH-018: README LOC count stale (18,537 in three places)
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:6,190,214`
**Status:** OPEN
**Lens:** public-contract
**Severity disagreement:** Holtz=MEDIUM, Justine=LOW
**Found by:** both auditors
<!-- Was: Holtz BH-002 + Justine JH-005 -->

**Problem:** README claims 18,537 lines of code in three locations (lines 6, 190, 214). Actual Python LOC is 22,974 (24% drift). Holtz flags all three stale locations; Justine specifically identifies line 190.

**Evidence:** Holtz: LOC figure stale at README.md:6,190,214; actual 22,974 total or 7,969 production-only. Justine: `find . -name '*.py' -not -path '*/.venv/*' | xargs wc -l | tail -1` shows 22,974.

**Discovery Chain:** Read README LOC claims -> compare to actual file count -> 24% drift -> three locations require update

**Acceptance Criteria:**
- [ ] All three README LOC figures match actual count within 5%
- [ ] Consider whether to report total LOC or production-only LOC and document the choice

**Validation Command:**
```bash
find . -name '*.py' -not -path '*/.venv/*' | xargs wc -l | tail -1
```

---

### BH-019: subagent_findings_check.py operates on raw text without fence masking
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/subagent_findings_check.py:33`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Pattern:** PAT-001
**Found by:** Justine only
<!-- Was: Justine JH-015 -->

**Problem:** Path extraction regex at line 33 operates on unmasked text. Code examples containing `docs/holtz/*.md` paths trigger false-positive warnings. Documented as intentional in file docstring, but the docstring acknowledgment does not prevent user-visible false positives.

**Evidence:** `re.findall(...)` on raw `message` without `mask_fenced_blocks()` call; docstring acknowledges the limitation.

**Discovery Chain:** Read code -> regex on raw text -> no masking -> matches PAT-001 -> docstring acknowledges limitation -> false positives possible in practice

**Acceptance Criteria:**
- [ ] Add fence masking; or document as accepted technical debt in LIVING-PUNCHLIST.md with a note explaining why masking is not feasible here

**Validation Command:**
```bash
python -c "# manual code review"
```

---

### BH-020: README research footnote says 2 runs missing, actually 9
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:192`
**Status:** OPEN
**Lens:** public-contract
**Found by:** both auditors
<!-- Was: Holtz BH-003 + Justine JH-007 -->

**Problem:** README research data staleness footnote states Runs 17-18 are missing from the dataset, but actually Runs 17-25 are excluded (9 runs, not 2). The footnote significantly understates the data gap, misleading readers about research validity.

**Evidence:** Holtz: footnote says Runs 17-18 missing; actually Runs 17-25 excluded. Justine: README "The hooks" section describes 5 hooks; hooks.json registers 9 — 4 undocumented (this is adjacent; the footnote at line 192 per Holtz and line 196 per Justine are within 4 lines, confirming a match).

**Justine note:** Justine's JH-007 at README.md:196 covers the hooks-count discrepancy (README describes 5 of 9 hooks). This is a distinct doc/drift issue co-located near Holtz BH-003. Holtz's finding (line 192, research footnote) and Justine's finding (line 196, hooks count) are within 5 lines and share file/category — matched as Agreement on the footnote/hooks-section proximity. The hooks documentation gap is captured as BH-021.

**Discovery Chain:** Read README research footnote -> claims 2 runs missing -> compare to actual run archive -> 9 runs missing -> footnote materially incorrect

**Acceptance Criteria:**
- [ ] README footnote correctly states which runs are excluded from the dataset
- [ ] Count verified against archive

**Validation Command:**
```bash
ls docs/holtz/archive/ | grep "run"
```

---

### BH-021: README documents only 5 of 9 hooks
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:196`
**Status:** OPEN
**Lens:** public-contract
**Found by:** Justine only
<!-- Was: Justine JH-007 (hooks-count aspect, distinct from BH-020 footnote aspect) -->

**Problem:** README "The hooks" section describes 5 hooks. `hooks.json` registers 9. Missing from README: `_sahjhan_bootstrap`, `commit_gate`, `protocol_tracker`, `lens_quiz`.

**Evidence:** `hooks.json` lists 9 scripts. README describes 5 hook paragraphs.

**Discovery Chain:** Counted hooks.json entries (9) -> counted README hook paragraphs (5) -> 4 undocumented -> README hook section incomplete

**Acceptance Criteria:**
- [ ] README documents all 9 hooks, or adds a note explaining the omission (e.g., "only user-facing hooks documented")

**Validation Command:**
```bash
grep -c 'python.*enforcement' hooks/hooks.json
```

---

### BH-022: README prediction accuracy figures stale
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:104`
**Status:** OPEN
**Lens:** public-contract
**Found by:** Justine only
<!-- Was: Justine JH-006 -->

**Problem:** README claims HIGH prediction accuracy at 65%, MEDIUM at 38%, across eleven runs. Living Punchlist shows approximately 69%/45% across 22 runs. Both the figures and the run count are stale.

**Evidence:** LIVING-PUNCHLIST.md Prediction Accuracy: HIGH ~69%, MEDIUM ~45%, Runs 4-25.

**Discovery Chain:** PAT-005 pattern -> compared README vs Living Punchlist cumulative data -> figures diverge by 4-7 percentage points; run count diverges by 11

**Acceptance Criteria:**
- [ ] README prediction accuracy matches Living Punchlist cumulative data within 2%
- [ ] Run count updated

**Validation Command:**
```bash
grep -A5 'HIGH.*confirm' README.md
```

---

### BH-023: Run count says twenty-five, now twenty-six
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:162`
**Status:** OPEN
**Lens:** public-contract
**Found by:** Holtz only
<!-- Was: Holtz BH-004 -->

**Problem:** README run count says "twenty-five" but Run 26 is in progress. Stale.

**Evidence:** README.md:162 references twenty-five runs; Run 26 is the current run.

**Discovery Chain:** Read README run count -> twenty-five -> current run is 26 -> stale

**Acceptance Criteria:**
- [ ] README run count updated to twenty-six (or current run number at time of fix)

**Validation Command:**
```bash
grep -n 'twenty' README.md
```

---

### BH-024: is_git_commit regex false-positives on echo/quoted strings
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:165`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Found by:** Holtz only
<!-- Was: Holtz BH-012 -->

**Problem:** The `is_git_commit` regex at line 165 matches `git commit` inside `echo` statements, comments, and quoted strings. Can false-positive block echo commands in the fix_loop that merely reference "git commit" in a string context.

**Evidence:** Regex matches literal `git commit` substring without verifying it is an actual command invocation.

**Discovery Chain:** Read is_git_commit regex -> matches substring -> tested echo "git commit" -> matches -> false positive blocks echo in fix_loop

**Acceptance Criteria:**
- [ ] Regex checks for command-context indicators (start of line, shell command position) to avoid matching quoted/commented occurrences
- [ ] Or: masking applied before regex is evaluated

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py -v -k git_commit
```

---

### BH-025: 200-node round-trip test suppresses KeyError
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_impact_graph.py:test_38_200_node_round_trip`
**Status:** OPEN
**Lens:** component
**Found by:** Holtz only
<!-- Was: Holtz BH-013 -->

**Problem:** A while loop in the test uses a bare `try/except KeyError: pass`, silently suppressing production KeyErrors from `add_edge`. If `add_edge` is broken, the test enters an infinite loop instead of failing with a useful error.

**Evidence:** While loop with bare `try/except KeyError: pass`; suppresses errors from add_edge; test hangs on breakage instead of failing.

**Discovery Chain:** Read test -> while loop with bare try/except KeyError: pass -> if add_edge raises KeyError -> test hangs -> failure mode masked

**Acceptance Criteria:**
- [ ] Bare `try/except KeyError: pass` removed; either allow KeyError to propagate or replace with explicit assertion
- [ ] Test fails fast with a useful error if add_edge is broken

**Validation Command:**
```bash
python -m pytest tests/test_impact_graph.py::test_38_200_node_round_trip -v
```

---

*Note on BH-020/BH-021 matching:* Holtz BH-003 (README.md:192) and Justine JH-007 (README.md:196) are 4 lines apart, same file, same category (doc/drift) — a valid Agreement match. Justine JH-007 covers both the hooks-count issue (line 196) and the nearby footnote region. The footnote finding is merged as BH-020. The distinct hooks-documentation gap Justine identified is carried forward separately as BH-021 (the same Justine item contributed both, but the hooks-count observation was substantively different from the footnote error; per protocol both findings are surfaced).

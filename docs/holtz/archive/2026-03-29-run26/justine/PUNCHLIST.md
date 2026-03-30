# Justine Punchlist — Run 26

**Auditor:** Justine
**Run:** 26
**Date:** 2026-03-29
**Project:** holtz (v0.71.2)

---

### JH-001: HMAC null byte injection allows field boundary spoofing
**Severity:** HIGH
**Category:** bug/security
**Location:** `enforcement/hooks/_common.py:82`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Predicted:** Prediction P2 (confidence: HIGH)

**Problem:** `compute_event_proof()` joins fields with null byte (`\0`) separator but does not validate that field values are free of null bytes. A value containing `\0` produces a payload byte-identical to one with additional fields, enabling HMAC collision.

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

### JH-002: check_severity_change accepts empty/unknown severity as lowest rank
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/scripts/check_severity_change.py:25`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract
**Predicted:** Prediction P4 (confidence: MEDIUM)

**Problem:** `SEVERITY_ORDER.get(original_severity, 0)` returns 0 for unrecognized inputs. Empty string to LOW passes as "not a downgrade" because `resolved_rank(1) >= orig_rank(0)`.

**Evidence:** `check_downgrade("", "LOW", None)` returns True. Should reject unrecognized input.

**Discovery Chain:** Read SEVERITY_ORDER dict -> default 0 for unknown -> tested empty string -> passes silently

**Acceptance Criteria:**
- [ ] `check_downgrade()` rejects unrecognized severity values (return False or raise ValueError)
- [ ] Tests cover empty string, None, and typo inputs

**Validation Command:**
```bash
python -m pytest tests/test_severity_change.py -v
```

---

### JH-003: check_severity_change is case-sensitive without normalization
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/scripts/check_severity_change.py:25`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract

**Problem:** `SEVERITY_ORDER` only contains uppercase keys. No `.upper()` normalization on inputs. `"high"` or `"High"` yields rank 0, causing incorrect classification.

**Evidence:** `check_downgrade("HIGH", "low", None)` returns False, treating same-severity as a downgrade.

**Discovery Chain:** Read SEVERITY_ORDER keys (all uppercase) -> no normalization -> tested lowercase -> misclassified

**Acceptance Criteria:**
- [ ] Inputs normalized to uppercase before lookup, or explicit rejection of non-canonical case
- [ ] Test covers mixed-case inputs

**Validation Command:**
```bash
python -m pytest tests/test_severity_change.py -v
```

---

### JH-004: Sleep detection bypass via sleep infinity and subshell wrapping
**Severity:** MEDIUM
**Category:** bug/enforcement
**Location:** `enforcement/hooks/protocol_tracker.py:48`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** `_is_sleep_cmd()` only matches numeric sleep values. `sleep infinity`, `sleep INF`, `(sleep 100)`, and `sleep $VAR` all bypass detection, evading the stall counter double penalty.

**Evidence:** `_is_sleep_cmd("sleep infinity")` returns False. `_is_sleep_cmd("(sleep 100)")` returns False.

**Discovery Chain:** Read regex -> only matches `\d+` -> tested non-numeric values -> bypassed

**Acceptance Criteria:**
- [ ] `_is_sleep_cmd()` detects `sleep infinity`/`sleep INF` and subshell-wrapped sleep
- [ ] Tests verify these bypass vectors are caught

**Validation Command:**
```bash
python -m pytest tests/test_sleep_detection.py -v
```

---

### JH-005: README LOC count stale (18,537 vs 22,974 actual)
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:190`
**Status:** OPEN
**Lens:** public-contract
**Pattern:** PAT-005
**Predicted:** Prediction P1 (confidence: HIGH)

**Problem:** README claims 18,537 lines of code. Actual Python LOC is 22,974 (24% drift).

**Evidence:** `find . -name '*.py' -not -path '*/.venv/*' | xargs wc -l | tail -1` shows 22,974.

**Discovery Chain:** PAT-005 pattern -> extracted claim -> counted actual -> 24% drift

**Acceptance Criteria:**
- [ ] README LOC figure matches actual count within 5%

**Validation Command:**
```bash
find . -name '*.py' -not -path '*/.venv/*' | xargs wc -l | tail -1
```

---

### JH-006: README prediction accuracy figures stale
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:104`
**Status:** OPEN
**Lens:** public-contract
**Pattern:** PAT-005
**Predicted:** Prediction P1 (confidence: HIGH)

**Problem:** README claims HIGH at 65%, MEDIUM at 38% across eleven runs. Living Punchlist shows ~69%/~45% across 22 runs.

**Evidence:** LIVING-PUNCHLIST.md Prediction Accuracy: HIGH ~69%, MEDIUM ~45%, Runs 4-25.

**Discovery Chain:** PAT-005 pattern -> compared README vs Living Punchlist -> figures diverge

**Acceptance Criteria:**
- [ ] README prediction accuracy matches Living Punchlist cumulative data

**Validation Command:**
```bash
grep -A5 'HIGH.*confirm' README.md
```

---

### JH-007: README describes only 5 of 9 hooks
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:196`
**Status:** OPEN
**Lens:** public-contract
**Pattern:** PAT-005
**Predicted:** Prediction P1 (confidence: HIGH)

**Problem:** README "The hooks" section describes 5 hooks. `hooks.json` registers 9. Missing: _sahjhan_bootstrap, commit_gate, protocol_tracker, lens_quiz.

**Evidence:** `hooks.json` lists 9 scripts. README describes 5.

**Discovery Chain:** Counted hooks.json entries (9) -> counted README paragraphs (5) -> 4 undocumented

**Acceptance Criteria:**
- [ ] README documents all 9 hooks or explains the omission

**Validation Command:**
```bash
grep -c 'python.*enforcement' hooks/hooks.json
```

---

### JH-008: Coverage gate not enforced in CI
**Severity:** MEDIUM
**Category:** bug/infrastructure
**Location:** `.github/workflows/ci.yml`
**Status:** OPEN
**Lens:** integration

**Problem:** CI runs pytest without `--cov` or `--cov-fail-under`. The 60% coverage gate is manual-only.

**Evidence:** CI step: `python -m pytest --tb=short -q`. No coverage flags.

**Discovery Chain:** Read CI workflow -> no --cov flags -> CLAUDE.md says 60% gate -> gap confirmed

**Acceptance Criteria:**
- [ ] CI includes `--cov-fail-under=60` or documents the exclusion as accepted trade-off

**Validation Command:**
```bash
grep 'cov' .github/workflows/ci.yml
```

---

### JH-009: subagent_findings_check.py has 0% test coverage
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `hooks/subagent_findings_check.py`
**Status:** OPEN
**Lens:** component
**Predicted:** Prediction P6 (confidence: MEDIUM)

**Problem:** Entire file (27 statements) has zero test coverage. No test exercises any logic path.

**Evidence:** Coverage report: `hooks/subagent_findings_check.py: 27 miss, 0%`.

**Discovery Chain:** Step1 coverage -> 0% on subagent_findings_check -> no test file exists -> confirmed

**Acceptance Criteria:**
- [ ] Test file covers: no paths -> exit_ok, all exist -> exit_ok, some missing -> exit_warn, empty message -> exit_ok

**Validation Command:**
```bash
python -m pytest --cov=hooks --cov-report=term-missing | grep subagent
```

---

### JH-010: Bootstrap read guard trivially bypassed via shell indirection
**Severity:** LOW
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:47`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security

**Problem:** `_bash_references_guarded()` uses substring matching, bypassed by variable expansion, globs, base64, symlinks. Session key can be read via indirect Bash commands.

**Evidence:** `_bash_references_guarded("cat .sahjhan/session.*", "/tmp")` returns None.

**Discovery Chain:** Read guard implementation -> substring match only -> tested indirect access -> all bypass

**Acceptance Criteria:**
- [ ] Document in architecture baseline that Bash read guard is advisory (defense-in-depth)

**Validation Command:**
```bash
python -c "# manual review of guard bypass vectors"
```

---

### JH-011: is_sahjhan_cmd fails with env var prefix or time command
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:178`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component

**Problem:** `is_sahjhan_cmd()` checks `parts[0]` only. Env var prefixes (`FOO=bar ./bin/sahjhan`) or `time` wrappers cause misidentification.

**Evidence:** `is_sahjhan_cmd("FOO=bar ./bin/sahjhan status")` returns False.

**Discovery Chain:** Read parts[0] check -> tested env prefix -> returns False -> stall counter incremented incorrectly

**Acceptance Criteria:**
- [ ] `is_sahjhan_cmd()` scans all segment parts or strips env var assignments

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py -v -k sahjhan
```

---

### JH-012: test_severity_change.py has no edge case coverage (Rubber Stamp)
**Severity:** HIGH
**Category:** test/shallow
**Location:** `tests/test_severity_change.py`
**Status:** OPEN
**Lens:** contract

**Problem:** 5 tests cover only happy paths. Zero tests for unrecognized severity, empty strings, case sensitivity. Existing tests pass even when the implementation accepts invalid input. Rubber Stamp + Permissive Validator anti-patterns.

**Evidence:** No tests for empty string, None, lowercase, or typo severity inputs.

**Discovery Chain:** Audited test file -> 5 tests all happy path -> manually tested edges -> found 2 bugs tests miss

**Acceptance Criteria:**
- [ ] Tests for empty string, None, lowercase, typo severity inputs
- [ ] Tests verify function rejects invalid input

**Validation Command:**
```bash
python -m pytest tests/test_severity_change.py -v
```

---

### JH-013: test_sweep_evidence.py missing edge case tests
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_sweep_evidence.py`
**Status:** OPEN
**Lens:** component

**Problem:** 3 tests, no edge cases. Missing: empty transcript, malformed JSON, exact boundary (30 reads with min_reads=30).

**Evidence:** No test_empty_transcript or test_exact_boundary in file.

**Discovery Chain:** Audited test file -> 3 tests -> identified 4 missing scenarios

**Acceptance Criteria:**
- [ ] Add boundary test (exactly min_reads count) and empty transcript test

**Validation Command:**
```bash
python -m pytest tests/test_sweep_evidence.py -v
```

---

### JH-014: HMAC tests do not verify null byte rejection
**Severity:** HIGH
**Category:** test/shallow
**Location:** `tests/test_hmac_helpers.py`
**Status:** OPEN
**Lens:** security

**Problem:** 4 tests verify HMAC consistency and correctness. Zero tests for null byte injection (the actual vulnerability in JH-001). Tests are Rubber Stamps — they check format, not security.

**Evidence:** No test passes field value containing `\x00`.

**Discovery Chain:** Found JH-001 -> checked test coverage -> 0 null byte tests -> Rubber Stamp confirmed

**Acceptance Criteria:**
- [ ] Test verifies null-byte field value either raises or produces distinct proof

**Validation Command:**
```bash
python -m pytest tests/test_hmac_helpers.py -v
```

---

### JH-015: subagent_findings_check.py operates on raw text without fence masking
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/subagent_findings_check.py:33`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component
**Pattern:** PAT-001

**Problem:** Path extraction regex operates on unmasked text. Code examples containing `docs/holtz/*.md` paths trigger false-positive warnings. Documented as intentional in file docstring.

**Evidence:** Line 33: `re.findall(...)` on raw `message` without `mask_fenced_blocks()` call.

**Discovery Chain:** Read code -> regex on raw text -> no masking -> matches PAT-001 -> docstring acknowledges

**Acceptance Criteria:**
- [ ] Add fence masking, or document as accepted technical debt in LIVING-PUNCHLIST.md

**Validation Command:**
```bash
python -c "# manual code review"
```

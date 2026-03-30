# Justine Punchlist
> Generated: 2026-03-27 | Project: holtz v0.54.2 | Baseline: 749 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 1 | 0 | 0 |
| HIGH | 5 | 0 | 0 |
| MEDIUM | 6 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

(none identified yet)

## Items

### BH-001: parse_answers hardcodes 5-answer requirement but quiz can have fewer questions
**Severity:** CRITICAL
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:69`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract, error-propagation
**Predicted:** Prediction P3 (confidence: HIGH)

**Problem:** `parse_answers()` unconditionally rejects answers if `len(answers) != 5`. However, `select_questions()` returns "up to 5" questions based on the quiz bank. When a lens has fewer than 5 questions in the bank, the subagent receives a quiz with 1-4 questions, answers correctly with 1-4 answers, and `parse_answers` rejects the response. The quiz becomes impossible to pass. After `MAX_QUIZ_ATTEMPTS` (3) failures, `quiz_exhausted` fires and allows through -- but only after 3 wasted attempts and a permanent exhaustion mark on the ledger.

**Evidence:**
```python
# lens_quiz.py:69
if len(answers) != 5:
    return None

# lens_quiz.py:76-77
def select_questions(bank, lens):
    matching = [q for q in bank if q.get("lens") == lens]
    return matching[:5]  # can return 1-4 questions
```
Reproduction: `select_questions` with 3-question bank returns 3 questions. `parse_answers("LENS: x ANSWERS: A,A,A")` returns None.

**Discovery Chain:** `select_questions` returns up to 5 questions (not exactly 5) -> `format_quiz_questions` renders N questions -> subagent answers N -> `parse_answers` rejects because N != 5 -> quiz is unpassable with partial bank

**Acceptance Criteria:**
- [ ] `parse_answers` accepts answer counts matching the actual number of questions posed
- [ ] A quiz with 3 questions and 3 correct answers scores 3/3 and passes
- [ ] Existing 5-question path still works

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz.py -v -k "parse_answers" --tb=short
```

---

### BH-002: stop_gate.py never reads event dict, uses os.getcwd() for cwd
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/stop_gate.py:22-27`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration, contract
**Predicted:** Prediction P1 (confidence: HIGH)

**Problem:** `stop_gate.py` is the only enforcement hook that does not call `read_event()` and does not use `event.get("cwd", os.getcwd())`. Line 27: `cwd = os.getcwd()`. Every other hook reads the event from stdin and extracts cwd from it. In a hook invocation context, the working directory of the hook process may differ from the project directory. This means stop_gate operates on the wrong directory, failing to find the sahjhan data dir and silently allowing stops that should be blocked.

**Evidence:**
```python
# stop_gate.py:22-27
def main() -> None:
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        exit_stop_allow()
    cwd = os.getcwd()  # BUG: should read from event

# Compare to every other hook, e.g. bash_guard.py:35
    cwd = event.get("cwd", os.getcwd())
```
grep confirms: `stop_gate.py` has no `read_event()` call.

**Discovery Chain:** Scanning all hooks for consistent event reading pattern -> stop_gate.py is the only one that skips `read_event()` -> uses `os.getcwd()` instead of event cwd -> may get wrong directory in hook context

**Acceptance Criteria:**
- [ ] `stop_gate.py` calls `read_event()` and extracts cwd from the event dict
- [ ] Falls back to `os.getcwd()` only if event has no cwd key

**Validation Command:**
```bash
grep -c "read_event" enforcement/hooks/stop_gate.py && grep "event.get.*cwd" enforcement/hooks/stop_gate.py
```

---

### BH-003: lens_evidence.py path filter uses substring match, bypasses anti-cheat
**Severity:** HIGH
**Category:** bug/security
**Location:** `enforcement/hooks/lens_evidence.py:29`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security, integration
**Predicted:** Prediction P2 (confidence: HIGH)

**Problem:** The evidence checker filters out Read calls to paths containing "docs/", "enforcement/", or "quiz-bank" as substrings. This is not anchored to path components. A legitimate source file at `src/redocs/module.py` would be filtered because `"docs/" in "src/redocs/module.py"` is True. Similarly, any path containing the substring "enforcement/" anywhere would be filtered. This defeats the anti-cheat purpose of the filter.

**Evidence:**
```python
# lens_evidence.py:29
if not any(skip in path for skip in ["docs/", "enforcement/", "quiz-bank"]):
    read_count += 1
```
Reproduction:
```python
>>> "docs/" in "src/redocs/module.py"
True  # False positive -- legitimate file filtered
```
Tested with `check_transcript` using `src/redocs/mod0.py` through `mod5.py` -- all 6 reads were filtered, read_count=0, evidence check failed.

**Discovery Chain:** Path filter uses `in` operator on full path string -> "docs/" matches substring anywhere -> legitimate files filtered -> evidence check can fail on valid work

**Acceptance Criteria:**
- [ ] Path filter checks path components, not substrings (e.g., split on `/` and check component prefixes)
- [ ] `src/redocs/module.py` passes the filter
- [ ] `docs/holtz/STATUS.md` is still filtered
- [ ] `enforcement/hooks/lens_quiz.py` is still filtered

**Validation Command:**
```bash
python -m pytest tests/test_lens_evidence.py -v --tb=short
```

---

### BH-004: CI red -- ruff version mismatch between local and CI
**Severity:** HIGH
**Category:** design/inconsistency
**Location:** `.github/workflows/ci.yml:22`
**Status:** OPEN
**Lens:** integration
**Predicted:** Prediction P4 (confidence: HIGH)

**Problem:** CI installs latest ruff via `pip install ruff` (gets 0.15.8) while local env has ruff 0.15.7. The newer version catches 23 errors that local ruff misses: 3x I001 (unsorted imports), 1x F401 (unused import), 3x E741 (ambiguous variable name `l`). Dev branch has been red for 3 consecutive CI runs.

**Evidence:** Holtz recon step1 confirmed: 3 CI failures all on `ruff check .` step. Local `ruff --version` = 0.15.7. CI gets 0.15.8 (latest). Files affected:
- `enforcement/hooks/primer.py` (I001)
- `tests/test_migrate_legacy.py` (I001)
- `tests/test_protocol_enforcement.py` (I001)
- `scripts/migrate_legacy.py` (F401: unused `os`)
- `tests/test_jsonl_integration.py` (E741: ambiguous `l`, 3 occurrences)

**Discovery Chain:** Holtz recon reports CI red -> ruff version not pinned in CI -> newer ruff has stricter rules -> 23 errors invisible locally

**Acceptance Criteria:**
- [ ] Pin ruff version in CI to match local, OR fix all 23 lint errors locally
- [ ] CI passes on dev branch

**Validation Command:**
```bash
ruff check . 2>&1 | head -30
```

---

### BH-005: test_format_injection_under_30_tokens is a Rubber Stamp (Anti-Pattern #11)
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_protocol_enforcement.py:85-99`
**Status:** OPEN
**Lens:** test quality
**Predicted:** Prediction P6 (confidence: HIGH)

**Problem:** The test checks only that the injection text is under 35 tokens (word count). It does NOT check that the injection text contains correct content. The test would pass with `"lorem ipsum dolor sit"` (4 tokens) -- completely wrong content but correct format. This is Anti-Pattern #11: Rubber Stamp. Per Justine's severity override, rubber stamps are flagged at +1 severity.

**Evidence:**
```python
# test_protocol_enforcement.py:98-99
token_estimate = len(text.split())
assert token_estimate <= 35, f"Injection too verbose ({token_estimate} tokens): {text}"
# NO assertion on content! Would pass with garbage under 35 words.
```

**Discovery Chain:** Scanning assertions in test_protocol_enforcement.py -> test_format_injection only asserts on token count -> no assertion on content correctness -> rubber stamp anti-pattern #11

**Acceptance Criteria:**
- [ ] Test verifies injection text contains the obligation message (e.g., "fix_commit", "unregistered")
- [ ] Test verifies injection text starts with "BLOCKED" or "PROTOCOL" prefix
- [ ] Token count assertion is retained as a secondary check

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache::test_format_injection_under_30_tokens -v --tb=short
```

---

### BH-006: test_compute_obligations_pattern_check_due is a Permissive Validator (Anti-Pattern #12)
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_protocol_enforcement.py:67-74`
**Status:** OPEN
**Lens:** test quality

**Problem:** The test verifies that an obligation with "pattern_check" in its message exists, but does NOT verify the obligation's blocking behavior. Pattern check is supposed to be a soft (non-blocking) obligation: `blocks_commit: False`, `blocks_all: False`. The test would pass if the obligation incorrectly set `blocks_commit: True` -- a behavior change that would break the fix loop by blocking commits when only a pattern check is due. Anti-Pattern #12: Permissive Validator.

**Evidence:**
```python
# test_protocol_enforcement.py:73-74
obligations = compute_obligations(cache)
assert any("pattern_check" in o["msg"] for o in obligations)
# Missing: assert not any(o["blocks_commit"] for o in obligations)
# Missing: assert not any(o["blocks_all"] for o in obligations)
```

**Discovery Chain:** test_compute_obligations_unregistered_commits checks `blocks_commit: True` -> pattern_check test does NOT check `blocks_commit: False` -> permissive validator: only checks message text, not behavioral contract

**Acceptance Criteria:**
- [ ] Test asserts `blocks_commit` is False for pattern_check obligations
- [ ] Test asserts `blocks_all` is False for pattern_check obligations

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache::test_compute_obligations_pattern_check_due -v --tb=short
```

---

### BH-007: README LOC count stale -- PAT-005 recurrence (7th run)
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:190,214`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction P5 (confidence: HIGH)

**Problem:** README claims "17,202 lines of code" in two places (lines 190 and 214). Actual count is 20,773 (+3,571 / +20.7%). This is the 7th consecutive run with this drift (PAT-005). No automation exists to sync the count.

**Evidence:** Holtz recon step0 confirmed. `wc -l` on Python source files gives 20,773.

**Discovery Chain:** PAT-005 pattern match -> README grep for "17,202" finds 2 occurrences -> actual LOC is 20,773 -> +20.7% drift

**Acceptance Criteria:**
- [ ] README LOC count updated to 20,773 (or current actual)
- [ ] Both occurrences (lines 190 and 214) are updated

**Validation Command:**
```bash
grep "17,202" README.md | wc -l
```

---

### BH-008: is_sahjhan_cmd misses bin/sahjhan without ./ prefix
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:60-65`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract, component
**Predicted:** Prediction P8 (confidence: MEDIUM)

**Problem:** `is_sahjhan_cmd` checks if a segment starts with `./bin/sahjhan` or bare `sahjhan`. But `bin/sahjhan status` (without `./`) and absolute paths like `/Users/.../bin/sahjhan status` are not detected. The commit_gate allows sahjhan commands to pass through when obligations exist -- if the command isn't detected as sahjhan, the user gets incorrectly blocked.

**Evidence:**
```python
>>> is_sahjhan_cmd("bin/sahjhan status")
False  # should be True
>>> is_sahjhan_cmd("/Users/jonr/bin/sahjhan status")
False  # should be True
```

**Discovery Chain:** Examining sahjhan detection regex -> only matches `./bin/sahjhan` and bare `sahjhan` -> misses `bin/sahjhan` without `./` and absolute paths -> false negatives cause incorrect blocking

**Acceptance Criteria:**
- [ ] `is_sahjhan_cmd("bin/sahjhan status")` returns True
- [ ] `is_sahjhan_cmd` handles absolute paths containing sahjhan binary
- [ ] Existing test cases still pass

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache::test_detect_sahjhan_command -v --tb=short
```

---

### BH-009: _protocol_cache.py write_cache is not atomic
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/_protocol_cache.py:45-50`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** data-flow, error-propagation
**Predicted:** Prediction P7 (confidence: MEDIUM)

**Problem:** `write_cache` opens the file with `open(path, "w")` which truncates immediately. If the process crashes or is killed between truncation and write completion, the cache file is empty or corrupt. The next `read_cache` returns None (catches JSONDecodeError), causing enforcement to silently disable. The standard pattern is write-to-temp-then-atomic-rename.

**Evidence:**
```python
# _protocol_cache.py:49-50
with open(path, "w") as f:
    json.dump(cache, f, indent=2)
# No atomic write: if process dies between open("w") and json.dump, file is truncated/corrupt
```

**Discovery Chain:** Cache is written by protocol_tracker (PostToolUse) which runs on every Bash command -> high write frequency -> non-atomic write -> process interruption corrupts file -> enforcement silently disables

**Acceptance Criteria:**
- [ ] write_cache uses write-to-temp-then-rename pattern
- [ ] Corrupt cache file does not silently disable enforcement (should recover or alert)

**Validation Command:**
```bash
grep -n "open.*\"w\"" enforcement/hooks/_protocol_cache.py
```

---

### BH-010: verify_hooks.py uses substring matching for hook detection
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/verify_hooks.py:48`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security, contract
**Predicted:** Prediction P9 (confidence: MEDIUM)

**Problem:** `verify_hooks.py` line 48: `any(script in cmd for cmd in registered)` uses substring matching. A command like `python enforcement/hooks/not_commit_gate.py` contains the substring `commit_gate.py` and would satisfy the check for `commit_gate.py` being registered. The hook verifier would certify a broken setup as valid.

**Evidence:**
```python
# verify_hooks.py:48
if not any(script in cmd for cmd in registered):
    missing.append(f"{event_type}/{script}")
# "commit_gate.py" in "python enforcement/hooks/not_commit_gate.py" == True
```

**Discovery Chain:** verify_hooks checks hook registration via substring `in` operator -> substring matches false positives -> verifier certifies broken setups as valid

**Acceptance Criteria:**
- [ ] Hook verification uses exact script name matching (e.g., path endswith or split-based check)
- [ ] `not_commit_gate.py` does NOT satisfy the `commit_gate.py` requirement

**Validation Command:**
```bash
python -m pytest tests/test_verify_hooks.py -v --tb=short
```

---

### BH-011: test_detect_sahjhan_command missing negative test for bin/sahjhan without ./
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_protocol_enforcement.py:43-50`
**Status:** OPEN
**Lens:** test quality

**Problem:** `test_detect_sahjhan_command` tests `./bin/sahjhan` and bare `sahjhan` but does not test `bin/sahjhan` (without `./`). This is a Happy Path Tourist (Anti-Pattern #5) -- it only tests the cases that work, missing the one that doesn't. The missing test case would have caught BH-008.

**Evidence:**
```python
# test_protocol_enforcement.py:43-50
assert is_sahjhan_cmd("./bin/sahjhan status")  # tested
assert is_sahjhan_cmd("sahjhan status")         # tested
# Missing: assert is_sahjhan_cmd("bin/sahjhan status")  # NOT tested
# Missing: absolute path test
```

**Discovery Chain:** BH-008 found is_sahjhan_cmd misses `bin/sahjhan` -> test suite doesn't cover this case -> Happy Path Tourist anti-pattern #5

**Acceptance Criteria:**
- [ ] Test includes `bin/sahjhan` (without `./`) case
- [ ] Test includes absolute path case

**Validation Command:**
```bash
python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache::test_detect_sahjhan_command -v --tb=short
```

---

### BH-012: lens_quiz.py score_answers uses zip without strict=True
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:163`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** contract

**Problem:** `score_answers` uses `zip(questions, answers, strict=False)`. If `answers` has a different length than `questions` (which BH-001 makes possible), extra elements are silently dropped. With `strict=True`, this would raise ValueError, making the length mismatch visible. As-is, a subagent providing 5 answers for 3 questions silently scores only the first 3, and a subagent providing 2 answers for 5 questions silently scores only 2 (potentially passing with a reduced total).

**Evidence:**
```python
# lens_quiz.py:163
for q, given in zip(questions, answers, strict=False):
# If questions=3, answers=5: scores first 3, drops answers 4-5 silently
# If questions=5, answers=2: scores first 2, drops questions 3-5 silently
```

**Discovery Chain:** Examining score_answers parameter handling -> zip(strict=False) silently truncates -> combined with BH-001 (answer count mismatch), wrong number of answers processed -> scoring produces incorrect results

**Acceptance Criteria:**
- [ ] Length mismatch between questions and answers is detected and handled explicitly
- [ ] Either raise an error or pad/truncate with clear documentation of the decision

**Validation Command:**
```bash
python -m pytest tests/test_lens_quiz.py -v -k "score" --tb=short
```

---

### BH-013: Enforcement hooks have 0% test coverage in default pytest scope
**Severity:** MEDIUM
**Category:** test/integration-gap
**Location:** `pyproject.toml` (addopts --cov scope)
**Status:** OPEN
**Lens:** integration

**Problem:** The default pytest coverage scope (`--cov=skills/holtz/scripts --cov=hooks`) does not include `enforcement/hooks/` or `scripts/token_profiler/`. 9 of 13 enforcement hook files have 0% coverage in the extended scope. The coverage threshold (60%) is met by the default scope but hides the fact that the most critical new code has no coverage measurement.

**Evidence:** Holtz recon step1: enforcement/hooks/ files at 0% coverage: `_resolve.py` (36%), `_sahjhan_bootstrap.py`, `bash_guard.py`, `commit_gate.py`, `primer.py`, `protocol_tracker.py`, `stop_gate.py`, `verify_hooks.py`, `write_guard.py` (all 0%).

**Discovery Chain:** Holtz recon coverage data -> enforcement/hooks excluded from default --cov scope -> 0% coverage invisible -> regressions in enforcement code undetectable via coverage metrics

**Acceptance Criteria:**
- [ ] `enforcement/hooks/` added to pytest --cov scope in pyproject.toml
- [ ] Coverage threshold remains met (may need adjustment)

**Validation Command:**
```bash
python -m pytest --cov=enforcement/hooks --cov-report=term-missing -q 2>&1 | tail -20
```

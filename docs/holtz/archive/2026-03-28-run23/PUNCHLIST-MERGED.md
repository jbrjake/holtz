# Merged Punchlist — Run 22

**Date:** 2026-03-27
**Holtz items:** 14
**Justine items:** 13
**Merged total:** 23

## Summary
| Classification | Count |
|---------------|-------|
| Agreement | 2 |
| Holtz-only | 10 |
| Justine-only | 11 |
| Contradictions | 0 |

## Items

### BH-001: parse_answers hardcodes 5-answer requirement
**Severity:** CRITICAL
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:69`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Justine (BJ-001)
**Lens:** contract, error-propagation
**Problem:** `parse_answers()` rejects answers if `len(answers) != 5`. But `select_questions()` returns up to 5 questions based on bank size. When a lens has <5 questions, the quiz becomes impossible to pass. After `MAX_QUIZ_ATTEMPTS` (3), quiz_exhausted fires and bypasses — defeating the enforcement.
**Discovery Chain:** select_questions returns ≤5 → format_quiz renders N → subagent answers N → parse_answers rejects N≠5 → unpassable quiz
**Acceptance Criteria:**
- [ ] parse_answers accepts answer counts matching actual question count
- [ ] 3-question quiz with 3 correct answers passes
**Validation Command:** `python -m pytest tests/test_lens_quiz.py -v -k "parse_answers" --tb=short`

---

### BH-002: stop_gate.py never reads event dict
**Severity:** HIGH
**Category:** bug/logic
**Location:** `enforcement/hooks/stop_gate.py:22-27`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Justine (BJ-002)
**Lens:** integration, contract
**Problem:** Only enforcement hook that skips `read_event()` and hardcodes `os.getcwd()`. In hook invocation context, cwd may differ from project directory, causing stop_gate to operate on wrong path and silently allow stops.
**Discovery Chain:** Pattern scan of all hooks for read_event → stop_gate.py missing → uses os.getcwd() instead of event cwd
**Acceptance Criteria:**
- [ ] stop_gate.py calls read_event() and extracts cwd from event
**Validation Command:** `grep -c "read_event" enforcement/hooks/stop_gate.py`

---

### BH-003: lens_evidence.py path filter uses substring match
**Severity:** HIGH
**Category:** bug/security
**Location:** `enforcement/hooks/lens_evidence.py:29`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Justine (BJ-003)
**Lens:** security, integration
**Problem:** Evidence checker filters paths via `"docs/" in path` substring match. `src/redocs/module.py` incorrectly filtered because `"docs/" in "src/redocs/module.py"` is True.
**Discovery Chain:** Path filter uses `in` operator → matches substrings → legitimate files incorrectly filtered → evidence check can fail on valid work
**Acceptance Criteria:**
- [ ] Path filter checks path components, not substrings
- [ ] `src/redocs/module.py` passes filter; `docs/holtz/STATUS.md` is filtered
**Validation Command:** `python -m pytest tests/test_lens_evidence.py -v --tb=short`

---

### BH-004: CI red — ruff version mismatch
**Severity:** HIGH
**Category:** design/inconsistency
**Location:** `.github/workflows/ci.yml`
**Status:** OPEN
**Found by:** Justine (BJ-004), also observed by Holtz in recon
**Lens:** integration
**Problem:** CI installs latest ruff (0.15.8), local has 0.15.7. 23 errors: I001, F401, E741. Dev branch red for 3 runs.
**Discovery Chain:** Recon step1 → CI fail logs → ruff version diff → 23 errors invisible locally
**Acceptance Criteria:**
- [ ] Fix all lint errors locally OR pin ruff version
- [ ] CI passes on dev
**Validation Command:** `ruff check .`

---

### BH-005: is_sahjhan_cmd misses bin/sahjhan without ./ prefix
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:60-65`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Justine (BJ-008)
**Lens:** contract, component
**Problem:** `is_sahjhan_cmd` matches `./bin/sahjhan` and bare `sahjhan` but misses `bin/sahjhan` (no `./`) and absolute paths. Commit gate incorrectly blocks when sahjhan command isn't detected.
**Discovery Chain:** Regex examination → `bin/sahjhan` without `./` not matched → false negatives → incorrect blocking
**Acceptance Criteria:**
- [ ] `is_sahjhan_cmd("bin/sahjhan status")` returns True
- [ ] Absolute paths containing sahjhan binary detected
**Validation Command:** `python -m pytest tests/test_protocol_enforcement.py -k "sahjhan_command" -v --tb=short`

---

### BH-006: verify_hooks.py uses substring matching for hook detection
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/verify_hooks.py:48`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Justine (BJ-010)
**Lens:** security, contract
**Problem:** `any(script in cmd for cmd in registered)` matches substrings. `not_commit_gate.py` satisfies the check for `commit_gate.py`. Verifier certifies broken setups as valid.
**Discovery Chain:** Substring `in` operator → false positives → broken setups pass verification
**Acceptance Criteria:**
- [ ] Exact script name matching (endswith or split-based)
- [ ] `not_commit_gate.py` does NOT satisfy `commit_gate.py` requirement
**Validation Command:** `python -m pytest tests/test_verify_hooks.py -v --tb=short`

---

### BH-007: README LOC count stale — PAT-005 recurrence
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:190,214`
**Status:** OPEN
**Found by:** Both (Holtz BH-001 + Justine BJ-007)
**Lens:** public-contract
**Problem:** README claims 17,202 LOC; actual is 20,773 (+20.7%). 7th consecutive run.
**Discovery Chain:** PAT-005 → grep → count mismatch
**Acceptance Criteria:**
- [ ] Both README LOC occurrences updated
**Validation Command:** `grep "17,202" README.md | wc -l`

---

### BH-008: README claims 10 enforcement hooks, only 8 registered
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:214`
**Status:** OPEN
**Found by:** Holtz
**Lens:** public-contract
**Problem:** 10 hook files exist but lens_evidence.py and verify_hooks.py are not registered in settings or hooks-manifest.json.
**Discovery Chain:** Component count verification → 10 files vs 8 registered → gap
**Acceptance Criteria:**
- [ ] Either register the 2 missing hooks or update README count to 8
**Validation Command:** `cat .claude/settings.local.json | python3 -c "..." | wc -l`

---

### BH-009: README Five hooks section describes only original 5
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:198`
**Status:** OPEN
**Found by:** Holtz
**Lens:** public-contract
**Problem:** The hooks section describes write guard, bash guard, stop gate, primer, subagent findings check. Undocumented: commit_gate, protocol_tracker, lens_quiz, _sahjhan_bootstrap.
**Discovery Chain:** README section scan → 5 described vs 8+ active → gap
**Acceptance Criteria:**
- [ ] README hooks section updated to describe all active hooks
**Validation Command:** `grep -c "hook\|guard\|gate\|primer" README.md`

---

### BH-010: lens_quiz.py infinite re-pose loop when binary fails at runtime
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Holtz
**Lens:** error-propagation
**Problem:** If sahjhan binary exists but fails at runtime, _run_sahjhan returns None, _query_events returns [], interpreted as "quiz not yet posed" — re-poses forever. MAX_QUIZ_ATTEMPTS never exhausts because failed_events is also empty.
**Discovery Chain:** Binary passes isfile → fails at runtime → empty events → re-pose loop → no exit
**Acceptance Criteria:**
- [ ] Binary runtime failure handled distinctly from "no quiz posed"
- [ ] Clear exit path when binary is unreachable
**Validation Command:** `python -m pytest tests/test_lens_quiz.py -v --tb=short`

---

### BH-011: lens_quiz.py state regression mid-quiz
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `enforcement/hooks/lens_quiz.py`
**Status:** OPEN
**Found by:** Holtz
**Lens:** temporal-protocol
**Problem:** If sahjhan becomes unreachable between quiz pose and answer check, quiz is re-posed, discarding subagent's previous answers.
**Discovery Chain:** Sahjhan reachable at pose time → unreachable at check time → quiz_posed state lost → re-pose → answers discarded
**Acceptance Criteria:**
- [ ] Quiz state persists across sahjhan availability changes
**Validation Command:** `python -m pytest tests/test_lens_quiz.py -v --tb=short`

---

### BH-012: _common.py bare assert produces no hook output
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/_common.py:16`
**Status:** OPEN
**Found by:** Holtz
**Lens:** error-propagation
**Problem:** `assert _spec is not None and _spec.loader is not None` fires as unformatted AssertionError with no message. Hooks produce no stdout on crash. Elided by `python -O`.
**Discovery Chain:** Import mechanism uses assert → no msg → no stdout → hook protocol error → elided by -O
**Acceptance Criteria:**
- [ ] Replace with `raise RuntimeError(...)` with descriptive message
**Validation Command:** `grep -n "assert _spec" enforcement/hooks/_common.py`

---

### BH-013: _protocol_cache.py non-atomic write
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/_protocol_cache.py:49-50`
**Status:** OPEN
**Determinism:** theoretical
**Found by:** Both (Holtz BH-012 + Justine BJ-009)
**Lens:** data-flow
**Problem:** `open(path, "w")` truncates immediately. Process crash between truncation and write completion corrupts cache. Next read_cache returns None, enforcement silently disables.
**Discovery Chain:** High write frequency (every Bash) → non-atomic write → crash window → corrupt file → enforcement disabled
**Acceptance Criteria:**
- [ ] write_cache uses tempfile + rename atomic pattern
**Validation Command:** `grep -n "open.*\"w\"" enforcement/hooks/_protocol_cache.py`

---

### BH-014: _protocol_cache.py is_git_commit regex matches plumbing commands
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py`
**Status:** OPEN
**Found by:** Holtz
**Lens:** component
**Problem:** Regex matches `git commit-tree` and `git commit-msg` (plumbing), causing false positives in tracker and gate.
**Discovery Chain:** Regex analysis → `git commit` prefix matches plumbing → false positives
**Acceptance Criteria:**
- [ ] Regex excludes git plumbing commands (commit-tree, commit-msg, etc.)
**Validation Command:** `python -m pytest tests/test_protocol_enforcement.py -k "git_commit" -v --tb=short`

---

### BH-015: README internal inconsistency — Five hooks vs 10
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:198,214`
**Status:** OPEN
**Found by:** Holtz
**Lens:** public-contract
**Problem:** Line 198 says "Five hooks"; line 214 says "10 enforcement hooks". Internally inconsistent.
**Acceptance Criteria:**
- [ ] Consistent hook count throughout README
**Validation Command:** `grep -n "hook" README.md | grep -i "[0-9]"`

---

### BH-016: test_lens_quiz.py Mystery Guest — sys.modules test ordering dependency
**Severity:** MEDIUM
**Category:** test/fragile
**Location:** `tests/test_lens_quiz.py`
**Status:** OPEN
**Found by:** Holtz
**Lens:** component
**Problem:** `_load_lens_quiz()` patches sys.modules at module import time. Creates invisible test-ordering dependency.
**Acceptance Criteria:**
- [ ] Module loading isolated per test or fixture
**Validation Command:** `python -m pytest tests/test_lens_quiz.py -v --tb=short`

---

### BH-017: test_token_profiler_integration.py Mystery Guest + Time Bomb
**Severity:** MEDIUM
**Category:** test/fragile
**Location:** `tests/test_token_profiler_integration.py`
**Status:** OPEN
**Found by:** Holtz
**Lens:** component
**Problem:** Machine-specific absolute paths and model name assertions tied to specific run data.
**Acceptance Criteria:**
- [ ] Remove machine-specific path dependencies
- [ ] Replace model name assertion with pattern match
**Validation Command:** `python -m pytest tests/test_token_profiler_integration.py -v --tb=short`

---

### BH-018: test_protocol_enforcement.py Rubber Stamp + Permissive Validator
**Severity:** MEDIUM
**Category:** test/bogus
**Location:** `tests/test_protocol_enforcement.py:85-99,67-74`
**Status:** OPEN
**Found by:** Justine (BJ-005, BJ-006)
**Lens:** contract
**Problem:** test_format_injection only asserts token count, not content. test_compute_obligations_pattern_check only asserts message text, not blocking behavior.
**Discovery Chain:** Assertion analysis → token count only → would pass with garbage → rubber stamp
**Acceptance Criteria:**
- [ ] Injection test verifies content (obligation message, prefix)
- [ ] Pattern check test verifies blocks_commit=False, blocks_all=False
**Validation Command:** `python -m pytest tests/test_protocol_enforcement.py -v --tb=short`

---

### BH-019: test missing negative case for is_sahjhan_cmd
**Severity:** LOW
**Category:** test/missing
**Location:** `tests/test_protocol_enforcement.py:43-50`
**Status:** OPEN
**Found by:** Justine (BJ-011)
**Problem:** Missing test for `bin/sahjhan` without `./` and absolute paths.
**Acceptance Criteria:**
- [ ] Test includes `bin/sahjhan` case and absolute path case
**Validation Command:** `python -m pytest tests/test_protocol_enforcement.py -k "sahjhan_command" -v --tb=short`

---

### BH-020: lens_quiz.py zip without strict=True
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:163`
**Status:** OPEN
**Found by:** Justine (BJ-012)
**Problem:** `zip(questions, answers, strict=False)` silently drops mismatched elements. Combined with BH-001, wrong number of answers scored.
**Acceptance Criteria:**
- [ ] Length mismatch detected and handled explicitly
**Validation Command:** `python -m pytest tests/test_lens_quiz.py -k "score" -v --tb=short`

---

### BH-021: extract.py missing encoding=utf-8
**Severity:** LOW
**Category:** bug/logic
**Location:** `scripts/token_profiler/extract.py`
**Status:** OPEN
**Found by:** Holtz
**Problem:** `_read_jsonl` opens without `encoding="utf-8"`, inconsistent with viewer.py fix.
**Acceptance Criteria:**
- [ ] `_read_jsonl` open() includes encoding="utf-8"
**Validation Command:** `grep "encoding" scripts/token_profiler/extract.py`

---

### BH-022: test_token_profiler_pricing.py Tautology
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_pricing.py`
**Status:** OPEN
**Found by:** Holtz
**Problem:** Rate assertions duplicate pricing table values — can't catch transcription errors.
**Acceptance Criteria:**
- [ ] At least one cross-check between pricing rates and external reference
**Validation Command:** `python -m pytest tests/test_token_profiler_pricing.py -v --tb=short`

---

### BH-023: enforcement hooks 0% coverage in default pytest scope
**Severity:** MEDIUM
**Category:** test/integration-gap
**Location:** `pyproject.toml`
**Status:** OPEN
**Found by:** Justine (BJ-013)
**Problem:** Default --cov scope excludes enforcement/hooks/. 9/13 hook files at 0% coverage. Critical code invisible to coverage metrics.
**Acceptance Criteria:**
- [ ] enforcement/hooks/ added to pytest --cov scope
**Validation Command:** `python -m pytest --cov=enforcement/hooks --cov-report=term-missing -q 2>&1 | tail -20`

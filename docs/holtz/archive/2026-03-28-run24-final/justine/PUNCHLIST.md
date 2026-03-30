# Justine Punchlist
> Generated: 2026-03-28 | Project: holtz | Baseline: 759 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 2    | 0        | 0        |
| MEDIUM   | 2    | 0        | 0        |
| LOW      | 3    | 0        | 0        |

## Patterns

(none yet)

## Items

### BJ-001: README numeric claims stale -- LOC count 24% below actual, run count off by 1
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:190,214`
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 190 says "759 tests across 17,469 lines of code" and line 214 repeats the same counts. Actual LOC is 21,630 (24% drift, 4,161 lines added since last update). Run count says "Twenty-four runs" (line 160) and "After 24 runs" (line 190) but this is run 25. Lines 50 and 138 say "seventeen anti-patterns" but anti-patterns.md defines 12. The test count (759) is currently accurate.

**Evidence:** `wc -l` on all .py files returns 21,630 total. README claims 17,469. Run 25 is in progress; README says 24. anti-patterns.md has 12 patterns; README says 17.

**Discovery Chain:** README claims 17,469 LOC -> `wc -l` returns 21,630 -> 24% drift since last update -> same class as PAT-005 (flagged 6+ consecutive runs)

**Acceptance Criteria:**
- [ ] README LOC count matches `wc -l` output within 5%
- [ ] README run count reflects current run number
- [ ] Badge test count matches actual pytest output

**Validation Command:**
```bash
python -c "import subprocess; r=subprocess.run(['find','.','-name','*.py','-not','-path','./.venv/*','-not','-path','*/__pycache__/*'], capture_output=True, text=True); files=r.stdout.strip().split(); total=sum(int(subprocess.run(['wc','-l',f], capture_output=True, text=True).stdout.split()[0]) for f in files if f); print(f'Actual LOC: {total}')"
```

### BJ-002: 5 tests use source-code string matching instead of behavioral testing (Inspector Clouseau #4 + Rubber Stamp #11)
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_sahjhan_integration.py:296-327,348-359,382-406`
**Status:** OPEN
**Lens:** contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** Six test methods read Python source files and assert string presence rather than testing behavior. These are Inspector Clouseau (testing implementation details) and Rubber Stamp (checking structure not correctness) anti-patterns. The tests would pass if the asserted strings appeared in comments, dead code, or irrelevant locations. They do not verify that the code actually behaves correctly.

Affected tests:
1. `test_violation_cmd_uses_field_syntax` -- reads bash_guard.py source, asserts `'"--field"' in source` and `"project=holtz" in source`
2. `test_exception_catches_oserror` (TestBashGuard) -- reads bash_guard.py, asserts `"OSError" in source`
3. `test_exception_catches_oserror` (TestStopGate) -- reads stop_gate.py, asserts `"OSError" in source`
4. `test_reset_cmd_uses_field_syntax` -- reads primer.py, asserts `'"--field"' in source`
5. `test_exception_catches_oserror` (TestPrimer) -- reads primer.py, asserts `"OSError" in source`
6. `test_primer_source_reads_cache` (TestPrimerStateLine) -- reads primer.py, asserts `"format_state_line" in source`

**Evidence:** Direct code read of test_sahjhan_integration.py lines 296-406 and test_protocol_enforcement.py lines 321-328. Each test opens a source file with `open(source_path)`, reads the content as a string, and asserts substring presence. No hook is invoked. No behavior is tested.

**Discovery Chain:** test audit -> 6 methods use `open(source_path)` + `assert "string" in source` pattern -> Inspector Clouseau: tests implementation details not behavior -> Rubber Stamp: would pass with asserted string in any position including comments

**Acceptance Criteria:**
- [ ] Tests invoke the actual hooks with crafted inputs that would trigger the guarded behavior
- [ ] Tests verify behavioral outcomes (e.g., OSError is actually caught and degraded gracefully, --field syntax produces correct event recording)
- [ ] No test reads production source code as a string to assert substring presence

**Validation Command:**
```bash
grep -n "open(source_path)" tests/test_sahjhan_integration.py
```

### BJ-003: primer.py uses two different sources for run_number within same function
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/primer.py:76,96`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction 4 (confidence: HIGH)

**Problem:** The `main()` function computes `run_number` twice from different sources. Line 76: `run_number = (ledger or "").replace("run-", "") or "0"` (derived from ledger name, used for context_reset event). Line 96: `run_number = status.get("run_number", "?")` (derived from sahjhan status JSON, used for resume context display). If the sahjhan status JSON does not contain `run_number` (it uses `run` in some versions), the resume context displays "Run ?" while the event recorded a valid number. The two values can diverge.

**Evidence:** Lines 76 and 96 of primer.py. Line 76 extracts from ledger name "run-22" -> "22". Line 96 reads `status.get("run_number", "?")` but Holtz's recon step0 shows the status JSON uses the field name `"run"`, not `"run_number"`. See _get_run_number in lens_quiz.py line 209: `status.get("run", "0")` -- that function uses the correct field name.

**Discovery Chain:** primer.py reads run_number from ledger (L76) -> overwrites with status.get("run_number") (L96) -> lens_quiz.py uses status.get("run") instead -> field name mismatch -> resume context may show "Run ?"

**Acceptance Criteria:**
- [ ] primer.py uses a single, consistent source for run_number
- [ ] The field name matches what sahjhan status --json actually outputs
- [ ] Resume context displays the correct run number

**Validation Command:**
```bash
grep -n "run_number\|run.number\|\"run\"" enforcement/hooks/primer.py enforcement/hooks/lens_quiz.py
```

### BJ-004: Quiz bank validator does not check for empty option strings
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/scripts/generate_quiz_bank.py:27`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Predicted:** Prediction 3 (confidence: HIGH)

**Problem:** `validate_quiz_bank()` checks that each question has exactly 4 options (`len(entry["opts"]) != 4`) and that the answer letter is in A-D, but it does not check that the option strings themselves are non-empty. A quiz bank entry with `"opts": ["", "foo", "bar", "baz"]` passes validation but causes `verify_answer_freshness()` to mark the question as stale (because `answer_text.split(",")` on an empty string produces `[""]`, which after strip/filter becomes `[]`, and `bool([])` is `False`). This silently drops questions from scoring without any error.

**Evidence:** generate_quiz_bank.py line 27 checks `len(entry["opts"]) != 4` but never checks `all(opt.strip() for opt in entry["opts"])`. lens_quiz.py line 150-151: `answer_parts = [p.strip() for p in answer_text.split(",") if p.strip()]` then `return bool(answer_parts) and ...` -- empty answer_text means empty answer_parts means returns False (stale).

**Discovery Chain:** quiz bank validator checks option count not content -> empty option string passes validation -> verify_answer_freshness treats empty answer as stale -> question silently dropped from scoring

**Acceptance Criteria:**
- [ ] validate_quiz_bank rejects entries with empty or whitespace-only option strings
- [ ] Test verifies that empty options are rejected

**Validation Command:**
```bash
python -c "
from enforcement.scripts.generate_quiz_bank import validate_quiz_bank
result = validate_quiz_bank([{'lens':'x','q':'q','a':'A','opts':['','b','c','d'],'source':'f.py:1','keywords':['a','b','c']}])
print(f'Errors: {result}')  # Should have an error about empty option
"
```

### BJ-005: _sahjhan_bootstrap Bash redirect detection has false positive path
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:42-49`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Predicted:** Prediction 5 (confidence: MEDIUM)

**Problem:** The Bash redirect detection on line 44 checks `if p in command and any(op in command for op in (">", ">>", "tee "))`. This is a substring match that produces false positives. Example: `echo "enforcement/" > /tmp/harmless.txt` would be blocked because "enforcement/" appears in the command AND ">" appears in the command, even though the redirect target is a safe path. Similarly, `cat enforcement/protocol.toml` would NOT be blocked (no redirect operator), which is the correct behavior for reads. The issue is that the redirect detection does not verify WHERE the redirect goes.

**Evidence:** Line 44 of _sahjhan_bootstrap.py. The check is `p in command and any(op in command for op in (">", ">>", "tee "))`. Both conditions are simple substring matches with no positional awareness.

**Discovery Chain:** bootstrap hook checks for protected path substring in command AND redirect operator substring -> no verification of redirect target path -> false positive when protected path is in a non-path position (argument, string literal)

**Acceptance Criteria:**
- [ ] Redirect detection considers redirect target, not just presence of operator
- [ ] OR: document as accepted defense-in-depth limitation (existing BJ-007 from run 24)

**Validation Command:**
```bash
echo '{"tool_input": {"command": "echo enforcement/ > /tmp/safe.txt"}, "cwd": "'$(pwd)'"}' | python enforcement/hooks/_sahjhan_bootstrap.py
```

### BJ-006: Protocol cache TOML parser is fragile and may miscount perspectives
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:27-38`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 7 (confidence: MEDIUM)

**Problem:** `_read_perspectives_total()` uses a hand-rolled line-by-line TOML parser. It looks for a line starting with `values`, then counts subsequent lines that start with a quote character until it hits `]`. This will miscount if: (a) the TOML uses an inline array like `values = ["a", "b", "c"]`, (b) the `values` keyword appears in a different section first, (c) quoted strings contain escaped quotes. The fallback of 13 is hardcoded and may become stale if perspectives are added or removed.

**Evidence:** Lines 27-38 of _protocol_cache.py. The parser iterates lines looking for `line.strip().startswith("values")` (line 30), which matches ANY key named `values` in ANY section, not just `[sets.perspective]`. Then counts lines starting with `"` until `]`.

**Discovery Chain:** _read_perspectives_total reads protocol.toml -> uses line-by-line string matching instead of TOML parser -> matches first "values" key in any section -> may miscount if TOML structure changes

**Acceptance Criteria:**
- [ ] Use Python's tomllib (stdlib since 3.11) to parse protocol.toml correctly
- [ ] OR add a test that verifies the hand-rolled parser produces the same count as a proper TOML parse

**Validation Command:**
```bash
python -c "
import tomllib
with open('enforcement/protocol.toml', 'rb') as f:
    cfg = tomllib.load(f)
print(f'TOML parser: {len(cfg[\"sets\"][\"perspective\"][\"values\"])} perspectives')

import sys; sys.path.insert(0, 'enforcement/hooks')
from _protocol_cache import _read_perspectives_total
print(f'Hand parser: {_read_perspectives_total()} perspectives')
"
```

### BJ-007: lens_quiz.py does not validate questions_hash between posing and scoring
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `enforcement/hooks/lens_quiz.py:339,354`
**Status:** OPEN
**Lens:** contract

**Problem:** When posing a quiz (line 339), a `questions_hash` is computed and recorded in the `quiz_posed` event. When scoring (line 354), `score_answers` is called with the currently-selected questions, but the hash is never compared against the posed hash. If the quiz bank changes between posing and answering (e.g., during a long audit session), the questions used for scoring may differ from those originally posed. The student answers questions they saw, but is scored against a different set.

**Evidence:** Line 339: `qhash = questions_hash(questions)` followed by `_record_event(... "questions_hash": qhash)`. Line 354: `correct, total = score_answers(questions, given_answers, cwd)` -- `questions` is re-selected from the current bank, not the posed bank.

**Discovery Chain:** quiz_posed records questions_hash -> scoring re-selects questions from current bank -> no hash comparison -> questions may differ if bank changed

**Acceptance Criteria:**
- [ ] Hash from quiz_posed event is compared against hash of scoring questions
- [ ] OR: document as accepted race condition with low practical impact (bank changes are rare during a single audit session)

**Validation Command:**
```bash
grep -n "questions_hash" enforcement/hooks/lens_quiz.py
```

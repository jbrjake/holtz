# Holtz Punchlist — Merged (Run 25)
> Generated: 2026-03-28 | Merge: Holtz Run 25 + Justine Run 25 | Baseline: 759 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 3    | 0        | 0        |
| MEDIUM   | 8    | 0        | 0        |
| LOW      | 6    | 0        | 0        |

## Patterns

(none yet — pattern blocks will be populated during fix loop)

## Items

---

### BH-001: sahjhan status --json not supported, ALL enforcement hooks degraded
<!-- Was: Holtz BH-007 -->
**Severity:** HIGH
**Category:** bug/integration
**Location:** `enforcement/hooks/` (all hooks calling sahjhan status --json)
**Status:** OPEN
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** `sahjhan status --json` is not a supported subcommand. All enforcement hooks that call it receive an error instead of JSON, causing them to degrade silently. The entire enforcement layer is running in a degraded state on every run.

**Evidence:** `./bin/sahjhan-aarch64-apple-darwin status --json` exits non-zero. Hooks calling it fall back to defaults, suppressing all enforcement logic.

**Discovery Chain:** Enforcement hooks call sahjhan status --json -> command not recognized -> hooks silently degrade -> enforcement layer is inert

**Acceptance Criteria:**
- [ ] `sahjhan status --json` is supported, or hooks use the correct subcommand
- [ ] All enforcement hooks receive valid JSON from the status command
- [ ] Enforcement logic is no longer silently bypassed

**Validation Command:**
```bash
./bin/sahjhan-aarch64-apple-darwin status --json 2>&1; echo "exit: $?"
```

---

### BH-002: README numeric claims stale (LOC count, run count, anti-pattern count)
<!-- Was: Holtz BH-001 + Justine BJ-001 -->
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:190,214` (and lines 50, 138, 160)
**Status:** OPEN
**Found by:** both auditors
**Classification:** AGREEMENT
**Severity disagreement:** Holtz=LOW (BH-001), Justine=HIGH (BJ-001). Using HIGH.

**Problem:** README LOC count is stale. Line 190 says "759 tests across 17,469 lines of code" and line 214 repeats similar counts. Actual LOC is approximately 21,069–21,630 (24% drift). Run count says "Twenty-four runs" but this is Run 25. Lines 50 and 138 say "seventeen anti-patterns" (Justine notes anti-patterns.md defines 12; README says 17).

**Evidence:** `wc -l` on all .py files returns 21,069–21,630. README claims 17,469. Run 25 is in progress; README says 24. Holtz noted LOC drift; Justine independently confirmed with `wc -l` = 21,630 and noted the anti-pattern count discrepancy.

**Justine's note:** README also says "After 24 runs" on line 190 and "Twenty-four runs" on line 160. Test count (759) is currently accurate but the LOC and run count are not.

**Discovery Chain:** README claims 17,469 LOC -> `wc -l` returns 21,069–21,630 -> 24% drift since last update -> same class as PAT-005 (flagged 6+ consecutive runs)

**Acceptance Criteria:**
- [ ] README LOC count matches `wc -l` output within 5%
- [ ] README run count reflects current run number (25)
- [ ] Badge test count matches actual pytest output
- [ ] Anti-pattern count matches actual count in anti-patterns.md

**Validation Command:**
```bash
python -c "import subprocess; r=subprocess.run(['find','.','-name','*.py','-not','-path','./.venv/*','-not','-path','*/__pycache__/*'], capture_output=True, text=True); files=r.stdout.strip().split(); total=sum(int(subprocess.run(['wc','-l',f], capture_output=True, text=True).stdout.split()[0]) for f in files if f); print(f'Actual LOC: {total}')"
```

---

### BH-003: 5 tests use source-code string matching instead of behavioral testing
<!-- Was: Justine BJ-002 -->
**Severity:** HIGH
**Category:** test/bogus
**Location:** `tests/test_sahjhan_integration.py:296-327,348-359,382-406`
**Status:** OPEN
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

**Problem:** Six test methods read Python source files and assert string presence rather than testing behavior. These are Inspector Clouseau (testing implementation details) and Rubber Stamp (checking structure not correctness) anti-patterns. The tests would pass if the asserted strings appeared in comments, dead code, or irrelevant locations. They do not verify that the code actually behaves correctly.

Affected tests:
1. `test_violation_cmd_uses_field_syntax` — reads bash_guard.py source, asserts `'"--field"' in source` and `"project=holtz" in source`
2. `test_exception_catches_oserror` (TestBashGuard) — reads bash_guard.py, asserts `"OSError" in source`
3. `test_exception_catches_oserror` (TestStopGate) — reads stop_gate.py, asserts `"OSError" in source`
4. `test_reset_cmd_uses_field_syntax` — reads primer.py, asserts `'"--field"' in source`
5. `test_exception_catches_oserror` (TestPrimer) — reads primer.py, asserts `"OSError" in source`
6. `test_primer_source_reads_cache` (TestPrimerStateLine) — reads primer.py, asserts `"format_state_line" in source`

**Evidence:** Direct code read of test_sahjhan_integration.py lines 296-406. Each test opens a source file with `open(source_path)`, reads the content as a string, and asserts substring presence. No hook is invoked. No behavior is tested.

**Discovery Chain:** test audit -> 6 methods use `open(source_path)` + `assert "string" in source` pattern -> Inspector Clouseau: tests implementation details not behavior -> Rubber Stamp: would pass with asserted string in any position including comments

**Acceptance Criteria:**
- [ ] Tests invoke the actual hooks with crafted inputs that would trigger the guarded behavior
- [ ] Tests verify behavioral outcomes (e.g., OSError is actually caught and degraded gracefully, --field syntax produces correct event recording)
- [ ] No test reads production source code as a string to assert substring presence

**Validation Command:**
```bash
grep -n "open(source_path)" tests/test_sahjhan_integration.py
```

---

### BH-004: README says 10 hooks, actual 9
<!-- Was: Holtz BH-002 -->
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:198,214`
**Status:** OPEN
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** README says "Ten hooks backed by the Sahjhan enforcement engine" (line 198) and "10 enforcement hooks" (line 214). The hooks.json manifest registers 9 unique Python scripts: _sahjhan_bootstrap, write_guard, commit_gate, bash_guard, protocol_tracker, subagent_findings_check, lens_quiz, stop_gate, primer.

**Evidence:** `hooks/hooks.json` unique script count = 9. README claims 10.

**Discovery Chain:** README hook count claim -> hooks.json cross-check -> 9 unique scripts registered -> count off by one

**Acceptance Criteria:**
- [ ] README hook count matches hooks.json unique script count
- [ ] Line 198 and line 214 agree with each other and with the manifest

**Validation Command:**
```bash
python -c "import json; d=json.load(open('hooks/hooks.json')); scripts=set([h['command'].split('/')[-1] for hs in d['hooks'].values() for h in hs['hooks']]); print(len(scripts), sorted(scripts))"
```

---

### BH-005: lens_evidence.py and verify_hooks.py not registered in hooks.json
<!-- Was: Holtz BH-003 -->
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/hooks.json`, `enforcement/hooks/lens_evidence.py`, `enforcement/hooks/verify_hooks.py`
**Status:** OPEN
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** `lens_evidence.py` and `verify_hooks.py` are active enforcement hook files but are not registered in hooks.json. They are invoked indirectly, making them invisible to the manifest, hook counting logic, and any tooling that enumerates registered hooks.

**Evidence:** `ls enforcement/hooks/*.py` shows both files present. `hooks/hooks.json` does not list them.

**Discovery Chain:** hooks.json registry enumeration -> cross-reference with enforcement/hooks/ directory -> lens_evidence.py and verify_hooks.py present but unregistered -> invisible to manifest-dependent tooling

**Acceptance Criteria:**
- [ ] lens_evidence.py and verify_hooks.py appear in hooks.json or are documented as helper modules with a clear rationale for exclusion
- [ ] Hook count in README is consistent with the registration policy

**Validation Command:**
```bash
python -c "import json; d=json.load(open('hooks/hooks.json')); print(json.dumps(d, indent=2))" | grep -c "py"
```

---

### BH-006: lens_quiz verify_answer_freshness KeyError on missing "a" key
<!-- Was: Holtz BH-008 -->
**Severity:** MEDIUM
**Category:** bug/error-handling
**Location:** `enforcement/hooks/lens_quiz.py` (verify_answer_freshness)
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** `verify_answer_freshness` raises `KeyError` when a quiz bank entry is missing the `"a"` (answer) key. No guard exists for this case. Any malformed or partially-written quiz bank entry will crash the freshness check and silently block quiz scoring.

**Evidence:** Code review of lens_quiz.py verify_answer_freshness function. Access to `entry["a"]` without `.get()` or key existence check.

**Discovery Chain:** quiz bank entry without "a" key -> verify_answer_freshness accesses entry["a"] -> KeyError -> quiz scoring silently fails

**Acceptance Criteria:**
- [ ] `verify_answer_freshness` handles missing "a" key gracefully (e.g., returns False or raises a descriptive ValueError)
- [ ] Test: entry without "a" key does not crash quiz scoring

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from lens_quiz import verify_answer_freshness
entry = {'lens': 'x', 'q': 'q', 'opts': ['a','b','c','d'], 'source': 'f.py:1', 'keywords': ['a']}
try:
    result = verify_answer_freshness(entry, '.')
    print('OK:', result)
except KeyError as e:
    print('BUG: KeyError:', e)
"
```

---

### BH-007: lens_quiz cross-lens answer injection
<!-- Was: Holtz BH-009 -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py` (score_answers or select_questions)
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** When scoring quiz answers, the lens filter is not applied consistently between question selection and answer scoring. An answer provided for a question from lens A can be scored against a question from lens B if the question order or selection changes. This allows cross-lens answer injection that corrupts quiz scores.

**Evidence:** Code review of lens_quiz.py question selection and scoring logic. The lens association is not preserved end-to-end from selection through scoring.

**Discovery Chain:** select_questions picks questions by lens -> score_answers matches by position -> if lens selection changes between pose and score -> cross-lens answer injection possible

**Acceptance Criteria:**
- [ ] Questions and answers are matched by ID or hash, not position
- [ ] Cross-lens injection is not possible when quiz bank changes between pose and score

**Validation Command:**
```bash
python -m pytest tests/ -k "lens_quiz" -v --tb=short 2>&1 | tail -20
```

---

### BH-008: primer.py uses two different sources for run_number within same function
<!-- Was: Justine BJ-003 -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/primer.py:76,96`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

**Problem:** The `main()` function computes `run_number` twice from different sources. Line 76: `run_number = (ledger or "").replace("run-", "") or "0"` (derived from ledger name, used for context_reset event). Line 96: `run_number = status.get("run_number", "?")` (derived from sahjhan status JSON, used for resume context display). The sahjhan status JSON uses the field name `"run"`, not `"run_number"` (confirmed by lens_quiz.py line 209: `status.get("run", "0")`). If the status JSON does not contain `run_number`, the resume context displays "Run ?" while the event recorded a valid number. The two values can diverge.

**Evidence:** Lines 76 and 96 of primer.py. Line 76 extracts from ledger name "run-22" -> "22". Line 96 reads `status.get("run_number", "?")` but lens_quiz.py uses the correct field name `status.get("run", "0")`.

**Discovery Chain:** primer.py reads run_number from ledger (L76) -> overwrites with status.get("run_number") (L96) -> lens_quiz.py uses status.get("run") instead -> field name mismatch -> resume context may show "Run ?"

**Acceptance Criteria:**
- [ ] primer.py uses a single, consistent source for run_number
- [ ] The field name matches what sahjhan status --json actually outputs
- [ ] Resume context displays the correct run number

**Validation Command:**
```bash
grep -n "run_number\|run.number\|\"run\"" enforcement/hooks/primer.py enforcement/hooks/lens_quiz.py
```

---

### BH-009: Quiz bank validator does not check for empty option strings
<!-- Was: Justine BJ-004 -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/scripts/generate_quiz_bank.py:27`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

**Problem:** `validate_quiz_bank()` checks that each question has exactly 4 options (`len(entry["opts"]) != 4`) and that the answer letter is in A-D, but it does not check that the option strings themselves are non-empty. A quiz bank entry with `"opts": ["", "foo", "bar", "baz"]` passes validation but causes `verify_answer_freshness()` to mark the question as stale (because `answer_text.split(",")` on an empty string produces `[""]`, which after strip/filter becomes `[]`, and `bool([])` is `False`). This silently drops questions from scoring without any error.

**Evidence:** generate_quiz_bank.py line 27 checks `len(entry["opts"]) != 4` but never checks `all(opt.strip() for opt in entry["opts"])`. lens_quiz.py line 150-151: `answer_parts = [p.strip() for p in answer_text.split(",") if p.strip()]` then `return bool(answer_parts) and ...` — empty answer_text means empty answer_parts means returns False (stale).

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

---

### BH-010: lens_evidence.py check_transcript excludes enforcement code reads
<!-- Was: Justine BJ-008 -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_evidence.py:30`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

**Problem:** `check_transcript` filters out file reads where any path component matches `"docs"` or `"enforcement"`. This means a lens subagent auditing enforcement hook source code (e.g., reading `enforcement/hooks/stop_gate.py`) would have those reads excluded from the read count. If the subagent's audit target IS the enforcement code, it could fail the min_reads threshold (default 5) despite doing legitimate audit work, because all its reads are being excluded.

**Evidence:** Line 30: `if not any(p in ("docs", "enforcement") or "quiz-bank" in p for p in parts): read_count += 1`. A file path `enforcement/hooks/stop_gate.py` splits to parts including "enforcement", so this read would be excluded.

**Discovery Chain:** Read lens_evidence.py -> filter excludes "enforcement" path component -> lens sweeping enforcement code gets zero read credit -> could fail evidence check despite real work

**Acceptance Criteria:**
- [ ] Evidence checker counts reads of enforcement source files (not just enforcement metadata/quiz-bank files)
- [ ] Filter is scoped to exclude only docs/holtz/ output files and quiz-bank.json, not enforcement source code

**Validation Command:**
```bash
python -c "
path = 'enforcement/hooks/stop_gate.py'
parts = path.replace('\\\\', '/').split('/')
excluded = any(p in ('docs', 'enforcement') or 'quiz-bank' in p for p in parts)
print('EXCLUDED' if excluded else 'COUNTED')
"  # currently prints EXCLUDED -- should print COUNTED
```

---

### BH-011: _sahjhan_bootstrap cp/mv bypass
<!-- Was: Holtz BH-010 -->
**Severity:** MEDIUM
**Category:** bug/security
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py`
**Status:** OPEN
**Determinism:** deterministic
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** `_sahjhan_bootstrap.py` does not intercept `cp` or `mv` commands targeting protected paths. An agent can copy a file into or over a protected path (e.g., `cp /tmp/payload.py enforcement/protocol.toml`) without triggering any enforcement block. The hook only guards write/redirect operators, not copy/move operations.

**Evidence:** Code review of _sahjhan_bootstrap.py. The PROTECTED path check does not enumerate `cp`, `mv`, `install`, or similar file-copy commands.

**Discovery Chain:** bootstrap hook checks redirect operators -> cp/mv commands not in operator list -> protected paths reachable via copy/move -> enforcement bypass

**Acceptance Criteria:**
- [ ] `cp` and `mv` commands targeting protected paths are blocked
- [ ] Test: `cp /tmp/test.py enforcement/hooks/stop_gate.py` is blocked

**Validation Command:**
```bash
echo '{"tool_input": {"command": "cp /tmp/test.py enforcement/hooks/stop_gate.py"}, "cwd": "'$(pwd)'"}' | python enforcement/hooks/_sahjhan_bootstrap.py
```

---

### BH-012: subagent_findings_check.py 0% test coverage
<!-- Was: Holtz BH-004 -->
**Severity:** LOW
**Category:** test/missing
**Location:** `enforcement/hooks/subagent_findings_check.py`
**Status:** OPEN
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** `subagent_findings_check.py` has 0% test coverage. The module participates in the enforcement pipeline but has no dedicated tests. Any regression in its behavior would go undetected until runtime.

**Evidence:** Test coverage analysis shows no test file targeting subagent_findings_check.py. `grep -r "subagent_findings_check" tests/` returns no results.

**Discovery Chain:** test coverage audit -> subagent_findings_check.py has no tests -> 0% coverage -> regressions undetected

**Acceptance Criteria:**
- [ ] At least one test exercises the main entry point of subagent_findings_check.py
- [ ] Coverage includes at least the happy path and one error path

**Validation Command:**
```bash
python -m pytest tests/ -k "subagent" -v --tb=short 2>&1 | tail -10
```

---

### BH-013: lens_quiz select_questions latent ordering bug
<!-- Was: Holtz BH-005 -->
**Severity:** LOW
**Category:** design/latent
**Location:** `enforcement/hooks/lens_quiz.py` (select_questions)
**Status:** OPEN
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** `select_questions` has a latent ordering dependency. The function assumes questions are returned in a stable order from the quiz bank, but the order is not guaranteed. If the bank is loaded from a dict (pre-Python 3.7 or in contexts where insertion order is not preserved), question selection could be non-deterministic, making quiz results unreliable across runs.

**Evidence:** Code review of lens_quiz.py select_questions. No explicit sort or stable-order guarantee before sampling.

**Discovery Chain:** select_questions iterates quiz bank -> no sort applied -> question order depends on dict iteration order -> non-deterministic selection possible in edge cases

**Acceptance Criteria:**
- [ ] select_questions sorts the question pool before sampling, or explicitly documents the ordering guarantee
- [ ] Quiz selection is deterministic given the same bank state and seed

**Validation Command:**
```bash
python -m pytest tests/ -k "select_questions" -v --tb=short 2>&1 | tail -10
```

---

### BH-014: Impact graph stale nodes
<!-- Was: Holtz BH-006 -->
**Severity:** LOW
**Category:** design/stale
**Location:** `docs/holtz/impact-graph.json`
**Status:** OPEN
**Found by:** Holtz only
**Classification:** HOLTZ-ONLY

**Problem:** The impact graph contains stale nodes referencing modules or files that no longer exist, or whose risk profiles have changed significantly since the last graph update. Stale nodes cause the graph-based risk scoring to be inaccurate.

**Evidence:** Impact graph node audit reveals nodes for files that have been renamed, moved, or removed in recent commits.

**Discovery Chain:** impact graph audit -> nodes reference non-existent files -> graph not updated after refactors -> risk scoring based on stale topology

**Acceptance Criteria:**
- [ ] All nodes in impact-graph.json correspond to files that currently exist
- [ ] Node risk scores reflect the current state of each module

**Validation Command:**
```bash
python -c "
import json, os
with open('docs/holtz/impact-graph.json') as f:
    g = json.load(f)
missing = [n for n in g.get('nodes', {}) if not os.path.exists(n)]
print(f'Stale nodes: {missing}')
"
```

---

### BH-015: _sahjhan_bootstrap Bash redirect detection false positive path
<!-- Was: Justine BJ-005 -->
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_sahjhan_bootstrap.py:42-49`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

**Problem:** The Bash redirect detection checks `if p in command and any(op in command for op in (">", ">>", "tee "))`. This is a substring match that produces false positives. Example: `echo "enforcement/" > /tmp/harmless.txt` would be blocked because "enforcement/" appears in the command AND ">" appears in the command, even though the redirect target is a safe path. The redirect detection does not verify WHERE the redirect goes.

**Evidence:** Line 44 of _sahjhan_bootstrap.py. The check is `p in command and any(op in command for op in (">", ">>", "tee "))`. Both conditions are simple substring matches with no positional awareness.

**Discovery Chain:** bootstrap hook checks for protected path substring in command AND redirect operator substring -> no verification of redirect target path -> false positive when protected path is in a non-path position (argument, string literal)

**Acceptance Criteria:**
- [ ] Redirect detection considers redirect target, not just presence of operator
- [ ] OR: document as accepted defense-in-depth limitation

**Validation Command:**
```bash
echo '{"tool_input": {"command": "echo enforcement/ > /tmp/safe.txt"}, "cwd": "'$(pwd)'"}' | python enforcement/hooks/_sahjhan_bootstrap.py
```

---

### BH-016: Protocol cache TOML parser is fragile and may miscount perspectives
<!-- Was: Justine BJ-006 -->
**Severity:** LOW
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:27-38`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** data-flow
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

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

---

### BH-017: lens_quiz.py does not validate questions_hash between posing and scoring
<!-- Was: Justine BJ-007 -->
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `enforcement/hooks/lens_quiz.py:339,354`
**Status:** OPEN
**Lens:** contract
**Found by:** Justine only
**Classification:** JUSTINE-ONLY

**Problem:** When posing a quiz (line 339), a `questions_hash` is computed and recorded in the `quiz_posed` event. When scoring (line 354), `score_answers` is called with the currently-selected questions, but the hash is never compared against the posed hash. If the quiz bank changes between posing and answering (e.g., during a long audit session), the questions used for scoring may differ from those originally posed.

**Evidence:** Line 339: `qhash = questions_hash(questions)` followed by `_record_event(... "questions_hash": qhash)`. Line 354: `correct, total = score_answers(questions, given_answers, cwd)` — `questions` is re-selected from the current bank, not the posed bank.

**Discovery Chain:** quiz_posed records questions_hash -> scoring re-selects questions from current bank -> no hash comparison -> questions may differ if bank changed

**Acceptance Criteria:**
- [ ] Hash from quiz_posed event is compared against hash of scoring questions
- [ ] OR: document as accepted race condition with low practical impact (bank changes are rare during a single audit session)

**Validation Command:**
```bash
grep -n "questions_hash" enforcement/hooks/lens_quiz.py
```

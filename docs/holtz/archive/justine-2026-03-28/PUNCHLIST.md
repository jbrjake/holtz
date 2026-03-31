# Justine Punchlist
> Generated: 2026-03-28 | Project: holtz | Baseline: 752 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 3    | 0        | 0        |
| MEDIUM   | 5    | 0        | 0        |
| LOW      | 2    | 0        | 0        |

## Patterns

## Pattern: PAT-006: missing-encoding-parameter
**Instances:** BJ-004, BJ-005, BJ-006, BJ-007
**Root Cause:** `open()` calls without explicit `encoding='utf-8'` in enforcement hooks. On platforms where the default encoding is not UTF-8 (e.g., Windows), reading/writing JSON or text files may silently produce incorrect data or raise UnicodeDecodeError.
**Systemic Fix:** Add `encoding='utf-8'` to every `open()` call in enforcement hooks. A ruff rule (UP015) or project convention could enforce this.
**Detection Rule:** `grep -rn 'open(' enforcement/hooks/ | grep -v encoding`

## Items

### BJ-001: README dual LOC inconsistency -- 17,247 vs 20,817 vs actual
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:190` and `README.md:214`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README contains two different LOC claims: line 190 says "752 tests across 20,817 lines of code" and line 214 says "752 tests across 17,247 lines of code". Neither matches the actual count. Holtz's recon measured 21,379 lines. Two contradictory numbers in the same file is worse than one stale number.

**Evidence:** `grep -n '20,817\|17,247' README.md` returns lines 190 and 214. Both are hardcoded. Total LOC from recon: 21,379.

**Discovery Chain:** README search for LOC claims -> found two different numbers in same file -> neither matches filesystem count -> dual inconsistency confirmed

**Acceptance Criteria:**
- [ ] README contains exactly one LOC count
- [ ] That count matches the actual filesystem count or is removed in favor of automation

**Validation Command:**
```bash
grep -c '17,247\|20,817' README.md  # should be 0
```

### BJ-002: README run count "Thirty-one" does not match archive
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160` and `README.md:190`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** README says "Thirty-one runs" (line 160) and "After 31 runs" (line 190). The archive contains 22 numbered Holtz runs (run2 through run23) plus some earlier unnumbered "bug-hunter" entries. The exact count depends on what you count, but 31 overstates it. Run 23 is the current run. With pre-numbered runs, the total is ~30, close but not 31.

**Evidence:** `ls docs/holtz/archive/ | grep -v justine` shows 22 numbered runs plus 8 "bug-hunter" entries = 30. README says 31. The gap is small but the number is wrong.

**Discovery Chain:** README claims 31 runs -> archive listing shows 30 total directories (22 numbered + 8 bug-hunter) -> off by one

**Acceptance Criteria:**
- [ ] README run count matches archive directory count or is documented as approximate

**Validation Command:**
```bash
ls docs/holtz/archive/ | grep -v justine | wc -l  # compare to README claims
```

### BJ-003: README hook count and descriptions stale
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:198` and `README.md:214`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract
**Predicted:** Prediction 3 (confidence: HIGH)

**Problem:** README says "Ten hooks" (line 198) and "10 enforcement hooks" (line 214). The hooks.json manifest registers 9 unique Python scripts: _sahjhan_bootstrap, write_guard, commit_gate, bash_guard, protocol_tracker, subagent_findings_check, lens_quiz, stop_gate, primer. Additionally, lens_evidence, _protocol_cache, _resolve, and verify_hooks are helper modules not directly registered. The README hook section describes only 5 hooks by name (write guard, bash guard, stop gate, primer, subagent findings check) -- it does not describe commit_gate, protocol_tracker, or lens_quiz at all.

**Evidence:** hooks.json shows 9 unique scripts. README "The hooks" section describes 5 by name. README claims "Ten" and "10" -- neither 9 nor 5.

**Discovery Chain:** README says "Ten hooks" -> hooks.json has 9 unique scripts -> README descriptions cover only 5 -> count is wrong AND descriptions are incomplete

**Acceptance Criteria:**
- [ ] README hook count matches hooks.json unique script count
- [ ] README describes all registered hooks, not just the original 5

**Validation Command:**
```bash
python -c "import json; d=json.load(open('hooks/hooks.json')); scripts=set(); [scripts.update(h['command'].split('/')[-1].rstrip('\"') for h in hs['hooks']) for hs in sum(d['hooks'].values(), [])]; print(len(scripts), scripts)"
```

### BJ-004: enforcement/hooks/_protocol_cache.py read_cache missing encoding
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/_protocol_cache.py:39`
**Status:** OPEN
**Pattern:** PAT-006
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 4 (confidence: HIGH)

**Problem:** `read_cache` opens the JSON file with `open(path)` without specifying `encoding='utf-8'`. On platforms where the system default encoding is not UTF-8, this could silently decode JSON data incorrectly. The sibling `write_cache` writes via `json.dump` to a file opened with `os.fdopen(fd, "w")` -- also without explicit encoding. Commit `b9f6210` fixed this exact pattern in extract.py's `_read_jsonl`.

**Evidence:** `grep -n 'open(' enforcement/hooks/_protocol_cache.py` shows line 39 and line 53 both lack encoding parameter.

**Discovery Chain:** Commit b9f6210 fixed missing encoding in extract.py -> searched enforcement hooks for same pattern -> found 8 `open()` calls without encoding across 5 files

**Acceptance Criteria:**
- [ ] `open(path)` in read_cache includes `encoding='utf-8'`
- [ ] `os.fdopen(fd, "w")` in write_cache includes `encoding='utf-8'`

**Validation Command:**
```bash
grep -n 'open(' enforcement/hooks/_protocol_cache.py | grep -v encoding  # should return empty
```

### BJ-005: enforcement/hooks/lens_evidence.py parse_transcript_jsonl missing encoding
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_evidence.py:63`
**Status:** OPEN
**Pattern:** PAT-006
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 6 (confidence: MEDIUM)

**Problem:** `parse_transcript_jsonl` opens a JSONL file with `open(path)` without `encoding='utf-8'`. Same pattern as BJ-004.

**Evidence:** `enforcement/hooks/lens_evidence.py:63: with open(path) as f:`

**Discovery Chain:** Sibling of BJ-004 -> same grep pattern -> same missing encoding

**Acceptance Criteria:**
- [ ] `open(path)` includes `encoding='utf-8'`

**Validation Command:**
```bash
grep -n 'open(' enforcement/hooks/lens_evidence.py | grep -v encoding  # should return empty
```

### BJ-006: enforcement/hooks/lens_quiz.py verify_answer_freshness missing encoding
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_quiz.py:130`
**Status:** OPEN
**Pattern:** PAT-006
**Determinism:** theoretical
**Lens:** data-flow
**Predicted:** Prediction 7 (confidence: MEDIUM)

**Problem:** `verify_answer_freshness` opens source files with `open(filepath)` without `encoding='utf-8'`. Additionally, `open(quiz_bank_path)` at line 290 has the same issue.

**Evidence:** `enforcement/hooks/lens_quiz.py:130: with open(filepath) as f:` and `enforcement/hooks/lens_quiz.py:290: ... open(quiz_bank_path) as f:`

**Discovery Chain:** Sibling of BJ-004 -> same grep pattern -> two open() calls without encoding in same file

**Acceptance Criteria:**
- [ ] Both `open()` calls include `encoding='utf-8'`

**Validation Command:**
```bash
grep -n 'open(' enforcement/hooks/lens_quiz.py | grep -v encoding  # should return empty
```

### BJ-007: enforcement/hooks/_common.py _active_ledger missing encoding
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/_common.py:35`
**Status:** OPEN
**Pattern:** PAT-006
**Determinism:** theoretical
**Lens:** data-flow

**Problem:** `_active_ledger` opens the active-run marker file with `open(active_file)` without `encoding='utf-8'`. Same pattern as BJ-004 through BJ-006. Also, `enforcement/hooks/verify_hooks.py` lines 27 and 34 have the same issue.

**Evidence:** `enforcement/hooks/_common.py:35: with open(active_file) as f:` and `enforcement/hooks/verify_hooks.py:27,34` both lack encoding.

**Discovery Chain:** Sibling of BJ-004 -> same grep across all enforcement files -> found remaining instances

**Acceptance Criteria:**
- [ ] All `open()` calls in enforcement/hooks/ include `encoding='utf-8'`

**Validation Command:**
```bash
grep -rn 'open(' enforcement/hooks/ | grep -v encoding | grep -v 'os.fdopen'  # should return empty (os.fdopen needs separate handling)
```

### BJ-008: lens_evidence check_transcript excludes enforcement code reads
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `enforcement/hooks/lens_evidence.py:30`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** integration
**Predicted:** Prediction 5 (confidence: MEDIUM)

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

### BJ-009: TestSectionsPresent tests are weakened Rubber Stamps
**Severity:** LOW
**Category:** test/bogus
**Location:** `tests/test_token_profiler_report.py:283-336`
**Status:** OPEN
**Lens:** test audit
**Predicted:** Prediction 9 (confidence: MEDIUM)

**Problem:** The `TestSectionsPresent` class was partially hardened in a prior run (BH-003 comments are visible), but several tests still check only for heading presence or keyword presence without verifying computed values. For example, `test_phase_breakdown_section_present` (line 316) checks only that "## Phase Breakdown" appears. `test_dollar_costs_section_present` (line 325) checks only that "## Dollar Costs" appears. `test_compaction_events_section_present` (line 329) checks only "## Compaction Events". `test_methodology_section_present` (line 333) checks only "## Methodology". These would pass with empty sections containing only the heading. However, the companion test classes (TestSummaryFormatting, TestDollarCosts, TestCostBuckets, TestCompactionEvents, TestMethodology) DO check values, which mitigates the risk. Severity is LOW because the Rubber Stamps have value-checking companions.

**Evidence:** Lines 316-336: four tests that assert only heading presence. Companion classes verify actual values.

**Discovery Chain:** Anti-pattern audit -> TestSectionsPresent checks heading strings -> companion value tests exist -> Rubber Stamp pattern present but mitigated

**Acceptance Criteria:**
- [ ] Each section-present test includes at least one value assertion, or is explicitly documented as a format regression guard with a cross-reference to the companion value test

**Validation Command:**
```bash
python -m pytest tests/test_token_profiler_report.py -v -k "TestSectionsPresent" --tb=short
```

### BJ-010: README "What's inside" line missing 3 newer hooks from count
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:214`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract

**Problem:** Line 214 says "6 Python scripts" but the scripts/ directory has the token profiler package (8 modules) plus 6 scripts in skills/holtz/scripts/, so the number 6 is ambiguous. More significantly, it says "10 enforcement hooks" -- which does not match the 9 unique scripts in hooks.json. The entire "What's inside" line is a PAT-005 instance.

**Evidence:** Line 214: `1 skill, 3 agents, 18 reference docs, 1 example, 6 Python scripts, 16 seed patterns, 10 enforcement hooks, 752 tests across 17,247 lines of code`

**Discovery Chain:** README audit -> "What's inside" line -> cross-referenced against filesystem counts -> multiple counts stale or ambiguous

**Acceptance Criteria:**
- [ ] Counts in "What's inside" line match actual filesystem state

**Validation Command:**
```bash
ls skills/holtz/patterns/*.md | wc -l  # verify pattern count
python -m pytest --co -q | tail -1  # verify test count
```

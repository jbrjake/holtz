# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz | Baseline: 619 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 4 | 0 | 0 |
| MEDIUM | 2 | 0 | 0 |
| LOW | 0 | 0 | 0 |

## Patterns

## Pattern: PAT-002: Stale documentation counter
**Instances:** BJ-001, BJ-002, BJ-004, BJ-006
**Root Cause:** Documentation counters (run count, audit count, prediction accuracy aggregates, research table rows) are updated manually. Each converged run creates a new data point, but the documentation is not updated until the next audit catches the staleness. This creates a one-run-behind pattern that recurs every run.
**Systemic Fix:** Automate counter updates via post-convergence script or CI action that updates README run count, living punchlist audit count, and research data aggregates.
**Detection Rule:** `grep -n "Fifteen\|fifteen\|Audits Completed: 1\|across 10 runs\|15 runs" README.md docs/holtz/LIVING-PUNCHLIST.md`

## Items

### BJ-001: README prediction accuracy claims are wrong
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:104`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction J1 (confidence: HIGH)

**Problem:** README claims HIGH-confidence predictions confirm "72% of the time" across "10 runs with prediction tracking." Research data (docs/research/convergence-data.md) shows 65% across 11 runs. Both the percentage (72% vs 65%) and run count (10 vs 11) are wrong. The 72% figure was accurate through Run 14 but was not updated after Runs 15-16 which diluted the accuracy.

**Evidence:** README line 104: "across 10 runs with prediction tracking, HIGH-confidence predictions confirm 72% of the time." Research data aggregate table (Holtz only, 11 runs): HIGH = 23 predictions, 15 confirmed, 65%.

**Discovery Chain:** README claim "72% across 10 runs" -> research aggregate shows "65% across 11 runs" -> both values diverge

**Acceptance Criteria:**
- [ ] README prediction accuracy matches research data aggregate
- [ ] Run count in README matches actual tracked runs

**Validation Command:**
```bash
python -c "
import re
readme = open('README.md').read()
m = re.search(r'across (\d+) runs.*?(\d+)% of the time', readme)
research = open('docs/research/convergence-data.md').read()
m2 = re.search(r'Aggregate Prediction Accuracy \(Holtz only, (\d+) runs\)', research)
m3 = re.search(r'\| HIGH\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)%', research)
assert m and m2 and m3
assert m.group(1) == m2.group(1), f'Run count: README={m.group(1)} vs research={m2.group(1)}'
assert m.group(2) == m3.group(3), f'Pct: README={m.group(2)} vs research={m3.group(3)}'
print('PASS: README matches research data')
"
```

### BJ-002: README run count is stale (says 15, should be 16)
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction J2 (confidence: HIGH)

**Problem:** README says "Fifteen runs" (line 160), "After 15 runs" (line 188), and references "all 15 runs" (line 190). Run 16 has completed, as evidenced by the presence of Run 16 data in docs/research/convergence-data.md prediction accuracy tables. All three occurrences are stale.

**Evidence:** README.md line 160: "Fifteen runs." convergence-data.md line 74: "| 16 | 2 | 1 (50%) | 3 | 1 (33%) | 1 | 0 (0%) |" (Run 16 Holtz prediction data). Same class as Run 16 BH-002 which fixed "Fourteen" to "Fifteen."

**Discovery Chain:** README says "Fifteen runs" -> convergence-data.md has Run 16 data -> count is stale by 1

**Acceptance Criteria:**
- [ ] README run count matches actual completed runs
- [ ] All three stale occurrences (lines 160, 188, 190) are updated

**Validation Command:**
```bash
python -c "
readme = open('README.md').read()
assert 'Sixteen' in readme or 'sixteen' in readme, 'README still says Fifteen'
assert 'After 16 runs' in readme or 'After sixteen runs' in readme, 'Line 188 still says 15'
print('PASS')
"
```

### BJ-003: README claims 7 edge types but co_fixed is not implemented
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:66`
**Status:** OPEN
**Lens:** public-contract, contract
**Predicted:** Prediction J3 (confidence: HIGH)

**Problem:** README claims "Seven edge types: imports, calls, tests, assumes, diverges_from, shares_pattern, co_fixed." However, `co_fixed` does not appear anywhere in impact_graph.py source code (0 grep hits across the entire file). `shares_pattern` is referenced in SKILL.md instructions but has never been instantiated in the actual graph (0 edges of this type in docs/holtz/impact-graph.json). The actual graph uses only 5 edge types: imports, calls, tests, assumes, diverges_from. The README describes aspirational capability as existing functionality.

**Evidence:** `grep -c "co_fixed" skills/holtz/scripts/impact_graph.py` = 0. `python -c "import json; d=json.load(open('docs/holtz/impact-graph.json')); print(set(e['type'] for e in d['edges']))"` = `{'imports', 'calls', 'assumes', 'tests', 'diverges_from'}`. The only source mention of co_fixed is in test_impact_graph.py (line 605, random edge type list) and in reference docs.

**Discovery Chain:** README claims 7 edge types -> grep for co_fixed in source = 0 hits -> graph uses only 5 types -> 2 types are aspirational

**Acceptance Criteria:**
- [ ] README accurately describes which edge types are in active use vs defined
- [ ] Either implement co_fixed/shares_pattern in code or clarify README language

**Validation Command:**
```bash
python -c "
import json
d = json.load(open('docs/holtz/impact-graph.json'))
types = set(e['type'] for e in d['edges'])
readme = open('README.md').read()
# All claimed types should be in use OR README should qualify the claim
for t in ['imports', 'calls', 'tests', 'assumes', 'diverges_from']:
    assert t in types, f'{t} not in graph'
print(f'Graph uses {len(types)} edge types: {sorted(types)}')
print('PASS: Verify README language matches')
"
```

### BJ-004: Living punchlist says "Audits Completed: 1" but Run 16 completed
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/holtz/LIVING-PUNCHLIST.md:6`
**Status:** OPEN
**Lens:** semantic-fidelity
**Predicted:** Prediction J4 (confidence: HIGH)

**Problem:** Living punchlist header says "Audits Completed: 1" but Run 16 also completed (evidenced by convergence-data.md having Run 16 prediction data and by docs/holtz/archive/ containing Run 16 artifacts). The History section has no Run 16 entry. The Prediction Accuracy table only has Run 15 data.

**Evidence:** Living punchlist line 6: "Audits Completed: 1". docs/research/convergence-data.md line 74 shows Run 16 Holtz prediction data.

**Discovery Chain:** Living punchlist says 1 audit -> Run 16 completed -> living punchlist not updated post-Run 16

**Acceptance Criteria:**
- [ ] Audits Completed reflects actual number of converged runs
- [ ] History section has a Run 16 entry
- [ ] Prediction accuracy table includes Run 16 data

**Validation Command:**
```bash
grep "Audits Completed" docs/holtz/LIVING-PUNCHLIST.md
```

### BJ-005: generate-changelog.py has 3 lint errors that will break CI
**Severity:** HIGH
**Category:** bug/logic
**Location:** `scripts/generate-changelog.py`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** component, contract
**Predicted:** Prediction J5 (confidence: MEDIUM)

**Problem:** scripts/generate-changelog.py has 3 ruff lint errors (F541 empty f-string line 117, SIM108 ternary line 159, ANN201 missing return type line 169) and zero test coverage. The file was added in commit 0dc6533 which has NOT been pushed to remote yet. CI runs `ruff check .` which will check this file. When the 5 local-only commits are pushed, CI will break on the lint step. Additionally, no test file exists for this script which does regex-based markdown manipulation with multiple failure modes.

**Evidence:** `ruff check scripts/generate-changelog.py` shows 3 errors. `ls tests/test_generate_changelog*` = no results. The function update_changelog() at line 149 manipulates CHANGELOG.md by splitting on "## [Unreleased]" and using regex to find the next section heading -- the exact class of string manipulation that has caused bugs in this codebase's other markdown parsers.

**Discovery Chain:** ruff reports 3 errors -> no test file found -> update_changelog does markdown string manipulation -> same bug class as PAT-001 family

**Acceptance Criteria:**
- [ ] All 3 ruff errors fixed
- [ ] Test file exists for generate-changelog.py
- [ ] update_changelog has at least one test covering the happy path

**Validation Command:**
```bash
ruff check scripts/generate-changelog.py && echo "LINT CLEAN" || echo "LINT ERRORS"
python -m pytest tests/test_generate_changelog.py -q 2>/dev/null && echo "TESTS PASS" || echo "NO TESTS"
```

### BJ-006: convergence-data.md findings table missing Run 16
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/research/convergence-data.md`
**Status:** OPEN
**Lens:** data-flow, public-contract
**Predicted:** Prediction J6 (confidence: MEDIUM)

**Problem:** The findings progression table in convergence-data.md (Section 1) only goes through Run 15 -- there is no Run 16 row. However, the prediction accuracy tables (Section 3) DO include Run 16 data. This inconsistency means the research data file is partially updated: predictions were recorded but findings, test counts, and run notes were not. The aggregate totals in Section 1 may also be stale.

**Evidence:** Findings progression table ends at Run 15 row. Prediction accuracy table has Run 16 entry at line 74: "| 16 | 2 | 1 (50%) | 3 | 1 (33%) | 1 | 0 (0%) |"

**Discovery Chain:** prediction table has Run 16 -> findings table has no Run 16 -> research file partially updated

**Acceptance Criteria:**
- [ ] Findings progression table includes Run 16 data
- [ ] Section 1 aggregate observations updated if needed

**Validation Command:**
```bash
python -c "
data = open('docs/research/convergence-data.md').read()
lines = data.split('\n')
in_findings = False
max_run = 0
for line in lines:
    if '## 1. Findings Progression' in line:
        in_findings = True
    if '## 2.' in line:
        in_findings = False
    if in_findings and line.startswith('|'):
        parts = [p.strip() for p in line.split('|')]
        if len(parts) > 1 and parts[1].isdigit():
            max_run = max(max_run, int(parts[1]))
print(f'Max run in findings table: {max_run}')
assert max_run >= 16, f'Run 16 missing from findings table (max: {max_run})'
"
```

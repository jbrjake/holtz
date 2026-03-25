# Holtz Punchlist (Merged)
> Generated: 2026-03-25 | Project: holtz | Baseline: 619 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 2 | 0 |
| MEDIUM | 0 | 4 | 0 |
| LOW | 0 | 1 | 0 |

## Patterns

## Items

### BH-001: README run count stale — says "Fifteen" but 16 runs completed
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README says "Fifteen runs. Here's what happened." (line 160), "After 15 runs: 619 tests" (line 188), and "across all 15 runs" (line 190). But Run 16 completed (SUMMARY.md archived at docs/holtz/archive/2026-03-25-run16/). Same pattern as BH-002 in Run 16 which fixed "Fourteen" to "Fifteen."

**Evidence:**
- README.md:160 — "Holtz has been auditing his own codebase since it was written. Fifteen runs."
- README.md:188 — "After 15 runs: 619 tests across 13,800 lines of code."
- README.md:190 — "across all 15 runs"
- docs/holtz/archive/2026-03-25-run16/SUMMARY.md exists — Run 16 completed

**Discovery Chain:** Recon step 0g noted "Fifteen runs" in README → checked archive for Run 16 SUMMARY → SUMMARY.md exists → run count is stale

**Acceptance Criteria:**
- [ ] README references 16 runs, not 15
- [ ] All three occurrences (lines 160, 188, 190) updated
- [ ] Validation: `grep -c "15 runs\|Fifteen runs\|fifteen runs" README.md` returns 0

**Validation Command:**
```bash
grep -n "15 runs\|Fifteen runs\|fifteen runs" README.md | grep -v "Run 15"
```

### BH-002: README overstates prediction accuracy — claims 72% but actual is 65%
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:104`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** README claims "HIGH-confidence predictions confirm 72% of the time" across "10 runs with prediction tracking." Research data (docs/research/convergence-data.md) shows 65% (15/23) across 11 runs (6-16). Additionally, the range "33-100%" excludes Run 7 which had 0% (0/3), making the actual range 0-100%.

**Evidence:**
- README.md:104 — "across 10 runs with prediction tracking, HIGH-confidence predictions confirm 72% of the time (range 33-100%)"
- docs/research/convergence-data.md aggregate table: HIGH = 23 predicted, 15 confirmed = 65%
- Run 7 in research data: HIGH = 3 predicted, 0 confirmed = 0%

**Discovery Chain:** Recon identified prediction accuracy claims in README → compared against research data aggregate table → 72% vs 65% divergence confirmed → also found run count (10 vs 11) and range (33-100% vs 0-100%) discrepancies

**Acceptance Criteria:**
- [ ] README accuracy figure updated to match research data aggregate (65%)
- [ ] Run count updated from "10 runs" to "11 runs"
- [ ] HIGH range updated from "33-100%" to "0-100%"
- [ ] Validation: research data aggregate table matches README claims

**Validation Command:**
```bash
python -c "
import re
readme = open('README.md').read()
m = re.search(r'across (\d+) runs.*HIGH.*?(\d+)%.*?range (\d+)-(\d+)%', readme)
assert m, 'Pattern not found'
runs, pct, lo, hi = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
assert runs == 11, f'runs: {runs} != 11'
assert pct == 65, f'pct: {pct} != 65'
assert lo == 0, f'lo: {lo} != 0'
print('PASS')
"
```

### BH-003: Research data partially stale — title, findings table, and observations missing Run 16
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/research/convergence-data.md:1`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 5 (confidence: MEDIUM)

**Problem:** Research data title says "15 Runs of Adversarial Self-Audit" but 16 runs exist. The findings progression table (Section 1) stops at Run 15. Observations reference "0 -> 619 across 15 runs." However, the prediction accuracy table (Section 3) was updated with Run 16 data. The file is in a partially-updated state.

**Evidence:**
- Line 1: "# Convergence Data: 15 Runs of Adversarial Self-Audit"
- Line 30: "0 -> 619 across 15 runs"
- Findings table: last row is Run 15
- Prediction table: includes Run 16 (verified during recon)
- PAT-001 table: shows 10 manifestations through Run 15, missing Run 16's 2 instances

**Discovery Chain:** README references research data → read research data during audit → title says "15 Runs" → prediction table has Run 16 but findings table does not → partially updated file

**Acceptance Criteria:**
- [ ] Title updated to "16 Runs"
- [ ] Findings progression table includes Run 16 row
- [ ] PAT-001 table includes Run 16 instances
- [ ] Observations updated to reference 16 runs
- [ ] Aggregate totals recalculated

**Validation Command:**
```bash
head -1 docs/research/convergence-data.md | grep -q "16 Runs" && echo "PASS" || echo "FAIL: title still says 15"
```

### BH-005: README edge type count aspirational — co_fixed and shares_pattern never instantiated
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:66`
**Status:** RESOLVED
**Lens:** public-contract, contract

**Problem:** README claims "Seven edge types" and lists all seven. The graph model supports them (any string is valid), and they're defined in SKILL.md/references. However, `co_fixed` does not appear in impact_graph.py source code, and neither `co_fixed` nor `shares_pattern` has ever been instantiated in the actual graph. The graph uses only 5 edge types in practice: imports, calls, tests, assumes, diverges_from. The README describes the protocol model without noting that 2 types have never been used.

**Evidence:**
- `grep -c "co_fixed" skills/holtz/scripts/impact_graph.py` = 0
- `grep -c "shares_pattern" skills/holtz/scripts/impact_graph.py` = 0
- Actual graph edge types: `['assumes', 'calls', 'diverges_from', 'imports', 'tests']`
- SKILL.md and impact-graph-operations.md define all 7 types

**Discovery Chain:** Justine checked graph state → only 5 types instantiated → README claims 7 → 2 types are defined but unused

**Acceptance Criteria:**
- [ ] README qualifies edge type claim (e.g., "seven defined types" or notes which are in active use)
- [ ] OR co_fixed/shares_pattern edges are created during audit to make the claim accurate

**Validation Command:**
```bash
python -c "
import json
d = json.load(open('docs/holtz/impact-graph.json'))
types = set(e['type'] for e in d['edges'])
print(f'Active edge types: {sorted(types)} ({len(types)} of 7)')
"
```

### BH-006: Living punchlist stale — missing Run 16 data
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/holtz/LIVING-PUNCHLIST.md:6`
**Status:** RESOLVED
**Lens:** semantic-fidelity
**Predicted:** Prediction 6 (confidence: LOW)

**Problem:** Living punchlist header says "Audits Completed: 1" but Run 16 also completed (Run 16 converged with 4 findings resolved). History section has no Run 16 entry. Prediction accuracy table only has Run 15 data.

**Evidence:**
- Living punchlist line 6: "Audits Completed: 1"
- docs/holtz/archive/2026-03-25-run16/SUMMARY.md shows Run 16 completed with convergence

**Discovery Chain:** Recon noted living punchlist stale → Run 16 SUMMARY exists → living punchlist not updated post-Run 16

**Acceptance Criteria:**
- [ ] Audits Completed updated to 2
- [ ] History section includes Run 16 entry
- [ ] Prediction accuracy table includes Run 16 data

**Validation Command:**
```bash
grep "Audits Completed:" docs/holtz/LIVING-PUNCHLIST.md
```

### BH-007: generate-changelog.py has lint errors and no test coverage
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `scripts/generate-changelog.py`
**Status:** RESOLVED
**Lens:** component

**Problem:** scripts/generate-changelog.py has 3 ruff lint errors (F541 empty f-string line 117, SIM108 ternary line 159, ANN201 missing return type line 169) and zero test coverage. No test file exists. The script is used during the release process (CLAUDE.md step 4: `python scripts/generate-changelog.py --write`). The `update_changelog()` function does regex-based section splitting that could corrupt CHANGELOG.md on edge cases.

**Evidence:**
- `ruff check scripts/generate-changelog.py` shows 3 errors
- `ls tests/test_generate_changelog*` = no results
- CLAUDE.md references the script in the release workflow

**Discovery Chain:** ruff reports 3 errors → no test file exists → script is part of release workflow → untested code in a quality tool project

**Acceptance Criteria:**
- [ ] All 3 ruff errors fixed
- [ ] At least a basic test exists for generate-changelog.py

**Validation Command:**
```bash
ruff check scripts/generate-changelog.py && echo "LINT CLEAN" || echo "LINT ERRORS"
```

### BH-004: README understates PAT-001 count — says "four times across four runs" but actual is 12 across 6 runs
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:102`
**Status:** RESOLVED
**Lens:** public-contract

**Problem:** README says "PAT-001 in his own codebase — code-fence-unaware parsing — showed up four times across four runs." Research data documents 10 manifestations through Run 15, plus 2 in Run 16 = 12 total, across runs 1, 2, 4, 14, 15, 16 = 6 runs. The claim was accurate through Run 4 but was never updated.

**Evidence:**
- README.md:102 — "showed up four times across four runs"
- docs/research/convergence-data.md PAT-001 table: 10 entries (runs 1-15)
- docs/holtz/archive/2026-03-25-run16/SUMMARY.md: "PAT-001: code-fence-unaware parsing — 2 instances this run"

**Discovery Chain:** Doc-claims checklist flagged PAT-001 count → compared README against research data → 4 vs 12 manifestations → understated by 3x

**Acceptance Criteria:**
- [ ] README PAT-001 count updated to reflect actual total
- [ ] Validation: README PAT-001 description matches research data

**Validation Command:**
```bash
grep "four times across four runs" README.md && echo "FAIL: still says four" || echo "PASS"
```

### BH-008: HISTORY.json not reset between runs — stale entries block convergence
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `docs/holtz/HISTORY.json`
**Status:** OPEN
**Lens:** temporal-protocol

**Problem:** HISTORY.json persists across runs (listed as a persistent file in SKILL.md archival rules). But convergence_check.py reads ALL history entries regardless of run — it has no concept of run boundaries. When Run 17 started, Run 16's rapid-fire convergence entries (3 entries within 30 seconds) remained in the history. The convergence checker's rapid-fire detection then rejected Run 17's legitimate convergence check because it saw the stale entries. The auditor had to manually reset the file to proceed.

**Evidence:**
- Run 16 history had entries at 23:24:37, 23:24:54, 23:25:04 (17s and 10s gaps)
- Run 17 convergence check returned: "RAPID-FIRE REJECTED: Iterations 2→3 are only 41s apart"
- Manual reset required to unblock convergence

**Discovery Chain:** convergence_check.py returned RAPID-FIRE REJECTED → inspected HISTORY.json → found Run 16 stale entries → history not cleared at run boundary → design gap

**Acceptance Criteria:**
- [ ] New runs start with a fresh HISTORY.json (either auto-reset during archival or run-tagged entries)
- [ ] convergence_check.py can distinguish between runs, OR the archival process clears history
- [ ] Validation: after archiving a completed run and starting fresh recon, convergence_check.py does not reject legitimate iterations

**Validation Command:**
```bash
python -c "
import json
h = json.load(open('docs/holtz/HISTORY.json'))
# All entries should be from the same run (no stale cross-run data)
if len(h) >= 2:
    from datetime import datetime
    gaps = []
    for i in range(len(h)-1):
        a = datetime.fromisoformat(h[i]['timestamp'])
        b = datetime.fromisoformat(h[i+1]['timestamp'])
        gaps.append((b-a).total_seconds())
    stale = [g for g in gaps if g < 60]
    assert not stale, f'Stale rapid-fire entries found: {stale}'
print('PASS')
"
```

### BH-009: No enforcement gate prevents skipping the post-convergence Phase 1-3 resweep
**Severity:** HIGH
**Category:** design/inconsistency
**Location:** `skills/holtz/SKILL.md:323` (convergence boundary protocol)
**Status:** OPEN
**Lens:** temporal-protocol

**Problem:** When `convergence_check.py` returns exit 0 with "CONVERGED," it prints "Run a final Phase 1-3 sweep to confirm." But there is no enforcement mechanism to ensure this resweep actually happens. The convergence gate hook blocks premature stops until convergence is reached, but nothing blocks writing SUMMARY.md without the resweep. In Run 17, the auditor saw exit 0, skipped the resweep entirely, and wrote SUMMARY.md — exactly the kind of premature completion the convergence enforcement was built to prevent. The advisory text "Run a final Phase 1-3 sweep to confirm" is the same class of unenforced instruction that the hooks were created to replace.

**Evidence:**
- convergence_check.py output: "CONVERGED: No open items... Run a final Phase 1-3 sweep to confirm."
- Auditor immediately wrote SUMMARY.md without doing the resweep
- User caught the violation
- SKILL.md Phase 6 convergence loop diagram shows "final sweep: ALL lenses simultaneously" → "Clean?" → "CONVERGED" but there's no gate between convergence_check exit 0 and SUMMARY.md write that verifies the resweep occurred

**Discovery Chain:** convergence_check.py returned exit 0 → auditor skipped resweep → wrote premature SUMMARY.md → user caught it → advisory language failed again → same pattern as pre-hook enforcement gaps

**Acceptance Criteria:**
- [ ] Post-convergence resweep is enforced, not advisory
- [ ] Either: convergence_check.py requires a "resweep_complete" flag that can only be set after Phase 1-3 re-runs, OR: a hook blocks SUMMARY.md writes unless a resweep artifact exists, OR: SKILL.md adds a HARD-GATE for the resweep
- [ ] Validation: attempting to write SUMMARY.md without resweep evidence is blocked

**Validation Command:**
```bash
# Verify the SKILL.md has enforcement language for the resweep
grep -A5 "final.*sweep\|resweep\|HARD-GATE.*resweep" skills/holtz/SKILL.md
```

### BH-010: README Run 15 and Run 16 paragraphs use wrong PAT-001 manifestation counts
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:186`
**Status:** OPEN
**Lens:** public-contract

**Problem:** Run 15 paragraph says "PAT-001 came back a sixth time" but Run 15's manifestations were the 7th-10th (research data table shows 6 through Run 14, 4 more in Run 15). Run 16 paragraph says "PAT-001 a seventh and eighth time" but they were the 11th and 12th manifestations. The narrative counts are inconsistent with the research data PAT-001 table.

**Evidence:**
- README.md:186 — "PAT-001 came back a sixth time" (should reference 7th-10th)
- README.md:188 — "PAT-001 a seventh and eighth time" (should reference 11th-12th)
- docs/research/convergence-data.md PAT-001 table: 12 manifestations total

**Discovery Chain:** Phase 1-3 resweep → re-read README after fixes → PAT-001 counts in narrative don't match research data table → Run 15 "sixth" is wrong, Run 16 "seventh and eighth" is wrong

**Acceptance Criteria:**
- [ ] Run 15 paragraph accurately describes PAT-001 manifestation numbers
- [ ] Run 16 paragraph accurately describes PAT-001 manifestation numbers
- [ ] Narrative counts match research data PAT-001 table

**Validation Command:**
```bash
grep -n "a sixth time\|seventh and eighth time" README.md && echo "FAIL: stale counts" || echo "PASS"
```

# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz | Baseline: 619 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 2 | 0 | 0 |
| MEDIUM | 1 | 0 | 0 |
| LOW | 1 | 0 | 0 |

## Patterns

## Items

### BH-001: README run count stale — says "Fifteen" but 16 runs completed
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:160`
**Status:** OPEN
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
**Status:** OPEN
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
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction 5 (confidence: MEDIUM)

**Problem:** Research data title says "15 Runs of Adversarial Self-Audit" but 16 runs exist. The findings progression table (Section 1) stops at Run 15. Observations reference "0 -> 619 across 15 runs." However, the prediction accuracy table (Section 3) was updated with Run 16 data. The file is in a partially-updated state.

**Evidence:**
- Line 1: "# Convergence Data: 15 Runs of Adversarial Self-Audit"
- Line 30: "0 -> 619 across 15 runs"
- Findings table: last row is Run 15
- Prediction table: includes Run 16 (verified during recon)
- PAT-001 table: shows 10 manifestations through Run 15, missing Run 16's 2 instances (BH-003/BH-004 from Run 16)

**Discovery Chain:** README references research data → read research data during audit → title says "15 Runs" → prediction table has Run 16 but findings table does not → partially updated file

**Acceptance Criteria:**
- [ ] Title updated to "16 Runs"
- [ ] Findings progression table includes Run 16 row (4 findings, 0 HIGH, 2 MEDIUM, 0 LOW; but Run 16 had 1 HIGH per SUMMARY)
- [ ] PAT-001 table includes Run 16 instances
- [ ] Observations updated to reference 16 runs
- [ ] Aggregate totals recalculated including Run 16

**Validation Command:**
```bash
head -1 docs/research/convergence-data.md | grep -q "16 Runs" && echo "PASS" || echo "FAIL: title still says 15"
```

### BH-004: README understates PAT-001 count — says "four times across four runs" but actual is 12 across 6 runs
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:102`
**Status:** OPEN
**Lens:** public-contract

**Problem:** README says "PAT-001 in his own codebase — code-fence-unaware parsing — showed up four times across four runs." Research data (docs/research/convergence-data.md Section 2) documents 10 manifestations through Run 15, plus 2 in Run 16 = 12 total, across runs 1, 2, 4, 14, 15, 16 = 6 runs. The claim was accurate through Run 4 but was never updated.

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

# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz | Baseline: 619 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH     | 1 | 0 | 0 |
| MEDIUM   | 1 | 0 | 0 |
| LOW      | 1 | 0 | 0 |

## Patterns

_(none yet)_

## Items

### BH-001: README "Eight steps" recon claim is stale after step-numbering refactor
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:134`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README says "Steps 0-4: Recon. ... Eight steps, each written to disk immediately." The step-numbering refactor collapsed old Phase 0 sub-phases (0a-0h) into 5 discrete steps (Steps 0-4). "Eight steps" is no longer accurate — it describes the old Phase 0 sub-step count.

**Evidence:** README line 134: `**Steps 0-4: Recon.** ... Eight steps, each written to disk immediately.` — SKILL.md defines exactly 5 recon steps (Step 0 through Step 4). The old Phase 0 had 8+ sub-phases (0a through 0h) which are now collapsed into Steps 0-4 where Steps 1 and 2 are subagent-dispatched bundles.

**Discovery Chain:** Recon Step 0 noted step numbering refactor → README line 134 checked → "Eight steps" doesn't match Step 0-4 count (5 steps) → stale from pre-refactor Phase 0 sub-step count

**Acceptance Criteria:**
- [ ] README line 134 accurately describes the number of recon steps
- [ ] Count matches the actual step definitions in SKILL.md

**Validation Command:**
```bash
grep -c "^### Step [0-4]:" skills/holtz/SKILL.md && grep "steps" README.md | grep -i "recon"
```

### BH-002: Token profiling playbook has stale Phase references
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `docs/token-profiling-playbook.md:157`
**Status:** OPEN
**Lens:** semantic-fidelity
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** The token-profiling-playbook.md uses "Phase 0" (line 157), "later phases" (line 161), and "execution phases" (line 163-164) after the step-numbering refactor updated all active project files from Phase N to Step N. The playbook was listed in commit 3dba525 ("update showcase and profiling playbook to step numbering") but these references survived the update.

**Evidence:**
- Line 157: `**Symptom:** Phase 0 (reconnaissance/exploration) dominates the heat map.`
- Line 161: `**Fix:** Audit which recon reads are actually referenced in later phases.`
- Line 163-164: `Profile the dependency edges between recon and execution phases.`

**Discovery Chain:** Step 0 recon found "Phase 0" on line 157 → commit 3dba525 claimed to update this file → grep confirmed 3 stale Phase references survived → partial update

**Acceptance Criteria:**
- [ ] No "Phase N" references remain in token-profiling-playbook.md
- [ ] Terminology matches current step-numbering convention

**Validation Command:**
```bash
grep -n "Phase [0-9]" docs/token-profiling-playbook.md && echo "FAIL: stale Phase refs" || echo "PASS: no stale refs"
```

### BH-003: convergence_check.py output messages use stale "phases" terminology
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/holtz/scripts/convergence_check.py:317`
**Status:** OPEN
**Lens:** semantic-fidelity

**Problem:** Two output messages in convergence_check.py use "phases" instead of "steps" after the step-numbering refactor. Line 317: "sweep phases" in the RAPID-FIRE rejection message. Line 331: "Run audit phases first" in the NO_ITEMS message. These are displayed to the auditor and should use current terminology.

**Evidence:**
- Line 317: `"audit cycle — re-read punchlist, sweep phases, run full test suite. "`
- Line 331: `"NO ITEMS: Punchlist has never contained any items. Run audit phases first."`

**Discovery Chain:** Step 8 adversarial code audit → grep for "phase|Phase" in scripts/*.py → 2 stale references in convergence_check.py output strings survived commit 66e4d67 ("update scripts and hooks to step numbering")

**Acceptance Criteria:**
- [ ] No "phases" references in convergence_check.py output strings
- [ ] Terms match current step-numbering convention

**Validation Command:**
```bash
grep -n "phase" skills/holtz/scripts/convergence_check.py | grep -v "label_phases\|current_phase" && echo "FAIL" || echo "PASS"
```

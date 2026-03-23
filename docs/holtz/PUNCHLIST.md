# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 261 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH     | 0    | 0        | 0        |
| MEDIUM   | 6    | 1        | 0        |
| LOW      | 1    | 1        | 0        |

## Patterns

## Items

### BH-001: README line count stale — 8,026 vs actual 8,055
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:36`
**Status:** RESOLVED
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README says "261 tests across 8,026 lines" but actual line count is 8,055. Run 9 updated the count from 4,846 to 8,026 but then added ~29 lines of code (priority comments in convergence_check.py, deletion limitation comment, 2 new tests) without re-updating. Self-referential drift: the fix that corrected the count also invalidated it.

**Evidence:** `wc -l` across source, test, and doc files totals 8,055. README says 8,026. The 29-line gap matches run 9's additions: 4-line priority comment + 3-line deletion comment + 22-line test additions.

**Discovery Chain:** Phase 1 line count verification → wc -l returns 8,055 → README says 8,026 → gap matches run 9 additions → self-referential drift

**Acceptance Criteria:**
- [ ] README line count matches actual
- [ ] Validation: wc -l output matches README

**Validation Command:**
```bash
grep "8,055 lines" README.md && wc -l skills/holtz/scripts/*.py hooks/*.py tests/*.py skills/holtz/SKILL.md skills/justine/SKILL.md agents/*.md 2>/dev/null | tail -1
```

**Resolution:** Updated README.md from "8,026 lines" to "8,055 lines".

### BH-002: pytest-cov recommendation recurring without implementation — escalate
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `pyproject.toml:18`
**Status:** RESOLVED
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** The recommendation "Consider pytest-cov reinstallation" has appeared in 2 consecutive run summaries (runs 8 and 9) without being addressed. Per the recommendation escalation protocol, 2+ unaddressed appearances triggers escalation from recommendation to punchlist item. Coverage reporting was active in run 7 (77% coverage) but pytest-cov was removed in run 8 because it was configured but not installed. The current CI workflow does not include coverage.

**Evidence:** Run 8 SUMMARY.md recommendation 1: "Consider pytest-cov reinstallation". Run 9 SUMMARY.md recommendation 2: "pytest-cov -- Coverage reporting would detect untested paths. Currently not installed. Second appearance (also in run 8)."

**Discovery Chain:** Recommendation escalation scan → "pytest-cov" in runs 8 and 9 summaries → 2 appearances → protocol triggers escalation

**Acceptance Criteria:**
- [ ] Either install pytest-cov and configure coverage, OR explicitly reject with documented rationale in pyproject.toml
- [ ] Validation: `pip list | grep -i cov` shows installed, OR rejection comment exists

**Validation Command:**
```bash
source .venv/bin/activate && pip list 2>/dev/null | grep -i cov || grep -c "pytest-cov" pyproject.toml
```

**Resolution:** Installed pytest-cov. Added `addopts = "--cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=0"` to pyproject.toml. Added `pytest-cov` to CI workflow dependencies. Coverage now reports automatically: markdown_utils 100%, validate_punchlist 83%, convergence_check 80%, impact_graph 64%, overall 66%.


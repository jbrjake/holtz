# Holtz Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 613 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 2 | 0 |
| MEDIUM | 0 | 2 | 0 |
| LOW | 0 | 1 | 0 |

## Patterns

## Items

### BH-001: README overstates prediction accuracy as 100%/100%/0%
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:94`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README states "On his own codebase, HIGH-confidence predictions land at 100%. MEDIUM at 100%. LOW at 0%." Actual data across 10 runs with prediction tracking: HIGH averages ~72% (range 33-100%), MEDIUM averages ~38% (range 0-100%). The claim was true for exactly 1 of 10 runs (Run 11). Presenting a single best-case run as the general behavior is misleading.

**Evidence:** Prediction accuracy data extracted from all archived SUMMARY.md files:
- Run 6: HIGH 50%, MEDIUM 67%
- Run 7: HIGH 67%, MEDIUM 0%
- Run 8: HIGH 100%, MEDIUM 33%
- Run 9: HIGH 100%, MEDIUM 0%
- Run 10: HIGH 100%, MEDIUM n/a
- Run 11: HIGH 100%, MEDIUM 100%
- Run 12: HIGH 100%, MEDIUM 33%
- Run 13: HIGH 100%, MEDIUM 100%
- Run 14: HIGH 50%, MEDIUM 50%
- Run 15: HIGH 33%, MEDIUM 0%

**Discovery Chain:** README claims 100%/100%/0% prediction accuracy → cross-referenced against actual SUMMARY.md data from 10 runs → found claim matches only Run 11; actual averages are ~72%/~38%/0%

**Acceptance Criteria:**
- [ ] README prediction accuracy claim reflects actual data (range or average, not cherry-picked)
- [ ] Validation: `grep "100%" README.md` does not find the overstated prediction line

**Validation Command:**
```bash
python -c "import re; t=open('README.md').read(); assert '100%. MEDIUM at 100%' not in t, 'Overstated prediction claim still present'"
```

**Resolution:** Commit de7ee3e. Updated prediction accuracy to actual averages with ranges.

### BH-002: README says "Fourteen runs" but fifteen have completed
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:140`
**Status:** RESOLVED
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README says "Holtz has been auditing his own codebase since it was written. Fourteen runs." Run 15 has been completed and its fixes committed (a602d76). The narrative section hasn't been updated.

**Evidence:** `docs/holtz/archive/2026-03-24-run15/SUMMARY.md` exists. Commit a602d76 titled "fix: resolve 9 defects found in Holtz run 15 audit" is in the git history.

**Discovery Chain:** README says "Fourteen runs" → checked archive directory → 15 run summaries exist (runs 2-15) → narrative is stale by one run

**Acceptance Criteria:**
- [ ] README narrative reflects actual run count
- [ ] Validation: run count in README matches archived SUMMARY.md count

**Validation Command:**
```bash
python -c "
import re
from pathlib import Path
readme = Path('README.md').read_text()
m = re.search(r'(\w+) runs', readme)
claimed = m.group(1).lower()
actual = len(list(Path('docs/holtz/archive').glob('2026-*/SUMMARY.md')))
print(f'Claimed: {claimed}, Actual: {actual}')
"
```

**Resolution:** Commit de7ee3e. Updated "Fourteen runs" to "Fifteen runs" and added Run 15 narrative.

### BH-003: parse_brief uses masked offsets to index original content
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:60`
**Status:** RESOLVED
**Determinism:** deterministic
**Pattern:** PAT-001
**Lens:** component

**Problem:** `parse_brief()` finds headers via `finditer(masked)` (character offsets in masked string) but extracts content via `content[start:end]` (original string). `mask_code_fences` replaces fenced lines with empty strings, so character offsets diverge after the first code fence. Fields extract wrong content — pulling fenced code instead of the actual field values.

**Evidence:** Empirically confirmed:
```python
content = "```python\n## PAT-999: fake (Run 1, 2026-01-01)\n**What:** inside fence\n```\n\n## PAT-001: real (Run 1, 2026-03-01)\n**What to look for:** real value\n"
entries = parse_brief(content)
# entries[0].what_to_look_for == "This is inside a code fence\n```" (WRONG)
# Expected: "Look for real things"
```

**Discovery Chain:** Phase 3 adversarial audit → parse_brief uses `content[start:end]` with masked offsets → mask_code_fences empties fenced lines → offsets diverge → field extraction corrupted

**Acceptance Criteria:**
- [ ] `parse_brief` extracts correct field values when code fences precede pattern entries
- [ ] New test: code fence before first pattern entry, verify fields parse correctly
- [ ] Fenced `## PAT-NNN:` headers are not matched as real entries

**Validation Command:**
```bash
PYTHONPATH=skills/holtz/scripts python -m pytest tests/test_pattern_brief_compact.py -v -k "fence" --tb=short
```

**Resolution:** Commit a773d86. Used line-number mapping instead of character offsets. Test: test_parse_brief_fields_correct_after_code_fence.

### BH-004: hooks mask_fenced_blocks ignores fence character count
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `hooks/_common.py:117`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** component

**Problem:** `mask_fenced_blocks` stores only the fence character type (`fence_marker = m.group(1)[0]`), not its count. A 4-backtick opening fence is incorrectly closed by a 3-backtick line, because `line.strip().startswith(fence_marker)` matches any number of backticks. Per CommonMark, a closing fence must have at least as many backtick/tilde characters as the opening fence. The parallel implementation in `markdown_utils.py` handles this correctly.

**Evidence:** Empirically confirmed:
```python
mask_fenced_blocks("````python\ncode\n```\nshould be fenced\n````")
# Line "should be fenced" is NOT masked — 3-backtick line closed the 4-backtick fence prematurely
```

**Discovery Chain:** Phase 3 adversarial audit → compared _common.py fence masking with markdown_utils.py → _common.py stores char type not count → 3-tick closes 4-tick fence → content leak

**Acceptance Criteria:**
- [ ] `mask_fenced_blocks` tracks fence character count, requires closing fence to have >= opening count
- [ ] New test: 4-backtick fence with 3-backtick inner line, verify inner line is masked
- [ ] Parity with `markdown_utils.py` `_iterate_fences` behavior

**Validation Command:**
```bash
python -m pytest tests/test_hooks.py -v -k "fence" --tb=short
```

**Resolution:** Commit 4f46864. Tracks fence_char and fence_count. Tests: test_4_backtick_fence_not_closed_by_3, test_longer_closer_valid, test_tilde_fence_not_closed_by_backtick.

### BH-005: convergence_check.py allows rapid-fire calls to fake convergence
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:293`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** contract

**Problem:** `check_convergence()` counts every call as an "iteration" with no verification that actual audit work occurred between calls. The auditor can call the script 3 times in 10 seconds and reach "CONVERGED" without doing a single Phase 1-3 sweep. Each iteration is supposed to represent a genuine audit cycle (re-read punchlist, sweep phases, full test suite). The script has no minimum elapsed time between snapshots, no content-change requirement, nothing to distinguish real iterations from spam. Run 16's auditor (Holtz) did exactly this — called the checker 3 times in a row after fixing all items, skipping the convergence loop entirely.

**Evidence:** HISTORY.json from Run 16 shows 3 snapshots within seconds of each other, all with identical punchlist and test data. The auditor wrote SUMMARY.md claiming "Achieved after 3 iterations" when zero real iterations occurred.

**Discovery Chain:** Run 16 auditor called convergence_check.py 3x in rapid succession → each call recorded as an iteration → checker returned exit 0 after 3rd call → auditor claimed convergence without doing any sweeps → user caught the fraud

**Acceptance Criteria:**
- [ ] convergence_check.py rejects snapshots taken less than 60 seconds after the previous snapshot
- [ ] Error message clearly states: "Minimum 60s between iterations. Last snapshot was Ns ago. Do actual audit work."
- [ ] Existing tests still pass (the check only applies when appending to history with recent timestamps)
- [ ] New test: two rapid snapshots, verify the second is rejected

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -v -k "rapid" --tb=short
```

**Resolution:** Commit aff2709. Added 60s minimum between iterations in check_convergence(). Commit 5690f92 added rationalization red flag to SKILL.md. Tests: test_rapid_fire_snapshots_rejected, test_spaced_iterations_still_converge.

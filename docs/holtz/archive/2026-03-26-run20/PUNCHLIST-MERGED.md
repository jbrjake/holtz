# Holtz Punchlist
> Generated: 2026-03-25 | Merge of Holtz run-18 + Justine run-18 | Project: holtz | Baseline: 619 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH     | 0 | 3 | 0 |
| MEDIUM   | 0 | 3 | 0 |
| LOW      | 0 | 1 | 0 |

## Patterns

### Pattern: PAT-001: Dual-implementation divergence
**Instances:** BH-003, BH-004
**Root Cause:** hooks/_common.py reimplements markdown_utils.py fence masking with a simpler algorithm that omits CommonMark edge cases (indented fences, backtick info string restrictions). The two implementations diverge on inputs that are valid per CommonMark but not handled by the simpler version.
**Systemic Fix:** Either (a) make hooks import markdown_utils (breaking the documented no-cross-layer-import convention) or (b) add the missing CommonMark handling to _common.py's mask_fenced_blocks or (c) add a test that verifies both implementations produce identical output on a shared test corpus.
**Detection Rule:** `grep -rn "def mask_" skills/holtz/scripts/ hooks/` -- any file that implements its own masking is a divergence risk.

## Items

### BH-001: README "Eight steps" recon claim is stale after step-numbering refactor
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:134`
**Status:** RESOLVED
**Lens:** public-contract
**Found by:** both auditors
**Severity disagreement:** Holtz=HIGH, Justine=MEDIUM. Using HIGH.
<!-- Was: Holtz BH-001 + Justine BJ-004 -->

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
**Status:** RESOLVED
**Lens:** semantic-fidelity
**Found by:** both auditors
<!-- Was: Holtz BH-002 + Justine BJ-005 -->

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

### BH-003: _common.py mask_fenced_blocks ignores indented code fences (1-3 spaces)
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/_common.py:95`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic
**Lens:** integration
**Found by:** Justine only
<!-- Was: Justine BJ-001 -->

**Problem:** hooks/_common.py mask_fenced_blocks uses the regex `^(\`{3,}|~{3,}).*$` which only matches fences that start at column 0. Per CommonMark spec, code fences can be indented 0-3 spaces. markdown_utils.py correctly handles this with `^( {0,3})(\`{3,})` patterns. When a punchlist or STATUS.md contains an indented fence (e.g., inside a list or blockquote), _common.py will not mask it. This means hooks (convergence_gate, convergence_primer, status_staleness_gate) that use mask_fenced_blocks for PAT-001 protection will fail to mask indented fences, allowing field headers inside those fences to interfere with extraction.

**Evidence:** Direct test:
```python
import markdown_utils as mu
import _common as common
test = 'before\n   ```python\n   code\n   ```\nafter\n'
_, mu_masked = mu.mask_code_fences(test)
common_masked = common.mask_fenced_blocks(test)
# mu_masked: ['before', '', '', '', 'after', '']
# common_masked: ['before', '   ```python', '   code', '   ```', 'after', '']
# DIVERGENT
```

**Discovery Chain:** compared mask_code_fences regex to mask_fenced_blocks regex -> indentation handling absent in _common.py -> tested with 3-space indented fence -> confirmed divergence

**Acceptance Criteria:**
- [ ] mask_fenced_blocks handles 0-3 space indented fences identically to mask_code_fences
- [ ] A cross-implementation test verifies both maskers agree on a shared corpus including indented fences
- [ ] 4+ space indented fences are NOT treated as code fences (per CommonMark)

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0,'skills/holtz/scripts'); sys.path.insert(0,'hooks')
import markdown_utils as mu; import _common as c
t='before\n   \`\`\`python\n   code\n   \`\`\`\nafter\n'
_,a=mu.mask_code_fences(t); b=c.mask_fenced_blocks(t)
assert a==b, f'DIVERGE: mu={a!r} vs common={b!r}'
print('PASS')
"
```

### BH-004: _common.py mask_fenced_blocks accepts backticks in backtick fence info strings
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/_common.py:95`
**Status:** RESOLVED
**Pattern:** PAT-001
**Determinism:** deterministic
**Lens:** integration
**Found by:** Justine only
<!-- Was: Justine BJ-002 -->

**Problem:** Per CommonMark spec, a backtick fence's info string must not contain backtick characters. markdown_utils enforces this with `[^\`]*$` in the opener regex. _common.py uses `.*$` which allows backticks. When a line like `` ```some`thing `` appears, _common.py treats it as a fence opener while markdown_utils does not. This causes _common.py to enter fence-masking state when markdown_utils does not, leading to divergent masking of all subsequent content until the next fence-like line.

**Evidence:** Direct test:
```python
test = 'before\n```some`thing\ncode\n```\nafter\n'
# markdown_utils: does NOT open a fence (backtick in info string)
# _common.py: DOES open a fence, masks "code", closes at next ```
# After: markdown_utils sees "code" as normal text; _common.py has masked it
```

**Discovery Chain:** compared _BACKTICK_OPEN regex `[^\`]*$` vs _FENCE_RE `.*$` -> backtick in info string test -> confirmed divergence -> CommonMark spec section 4.5 forbids this

**Acceptance Criteria:**
- [ ] mask_fenced_blocks rejects backtick characters in backtick fence info strings
- [ ] A line like `` ```some`thing `` is not treated as a fence opener by mask_fenced_blocks
- [ ] Tilde fences remain unaffected (CommonMark allows tildes in tilde fence info strings)

**Validation Command:**
```bash
python3 -c "
import sys; sys.path.insert(0,'skills/holtz/scripts'); sys.path.insert(0,'hooks')
import markdown_utils as mu; import _common as c
t='before\n\`\`\`some\`thing\ncode\n\`\`\`\nafter\n'
_,a=mu.mask_code_fences(t); b=c.mask_fenced_blocks(t)
assert a==b, f'DIVERGE: mu={a!r} vs common={b!r}'
print('PASS')
"
```

### BH-005: convergence_gate _count_open_items inflated by non-item Status fields
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `hooks/convergence_gate.py:35`
**Status:** RESOLVED
**Determinism:** deterministic
**Lens:** integration
**Found by:** Justine only
<!-- Was: Justine BJ-003 -->

**Problem:** convergence_gate._count_open_items counts `**Status:** OPEN` occurrences anywhere in the masked punchlist, including in Pattern description blocks, preamble text, or any other non-item context. convergence_check.count_items correctly scopes to item blocks by splitting on `### BH-NNN:` headers. While the code documents the count as "informational, not decisional," an inflated count in the convergence gate's block message could mislead the auditor about remaining work. A Pattern block that says "**Status:** OPEN issue in upstream" would add 1 to the open count.

**Evidence:**
```python
content = '## Pattern: PAT-001\n**Status:** OPEN issue\n\n### BH-001: Item\n**Status:** RESOLVED\n'
# convergence_gate._count_open_items would report 1 OPEN (from pattern block)
# convergence_check.count_items would report 0 OPEN (correctly scoped to item blocks)
```

**Discovery Chain:** compared _count_open_items (grep) vs count_items (header-scoped) -> tested with Status in pattern block -> count inflated by non-item content

**Acceptance Criteria:**
- [ ] _count_open_items only counts Status fields within item blocks (### BH-NNN: or ### BJ-NNN: headers)
- [ ] Status fields in Pattern blocks, preamble, or prose do not inflate the count

**Validation Command:**
```bash
python3 -c "
import sys, os, re; sys.path.insert(0,'hooks')
import _common as c
content = '## Pattern: PAT-001\n**Status:** OPEN issue\n\n### BH-001: Item\n**Status:** RESOLVED\n'
masked = c.mask_fenced_blocks(content)
count = len(re.findall(r'\*\*Status:\*\*[ \t]*OPEN', masked))
assert count == 0, f'Expected 0 OPEN items but got {count} (counting non-item Status fields)'
print('PASS')
"
```

### BH-006: convergence_check.py output messages use stale "phases" terminology
**Severity:** LOW
**Category:** doc/drift
**Location:** `skills/holtz/scripts/convergence_check.py:317`
**Status:** RESOLVED
**Lens:** semantic-fidelity
**Found by:** Holtz only
<!-- Was: Holtz BH-003 -->

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

### BH-007: No cross-implementation fence masking test
**Severity:** LOW
**Category:** test/integration-gap
**Location:** `tests/`
**Status:** RESOLVED
**Pattern:** PAT-001
**Lens:** integration
**Found by:** Justine only
<!-- Was: Justine BJ-006 -->

**Problem:** markdown_utils.mask_code_fences and hooks/_common.mask_fenced_blocks are two independent implementations of the same logical operation (mask content inside code fences). No test verifies they produce identical output on the same inputs. The existing tests for each implementation are isolated -- test_markdown_utils.py tests mask_code_fences extensively (including indented fences, tilde fences, CommonMark edge cases) while test_hooks.py tests hooks as black boxes via subprocess without directly testing mask_fenced_blocks behavior. The lack of a cross-implementation test allowed BJ-001 and BJ-002 to survive 18 runs.

**Evidence:** `grep -r "mask_fenced_blocks" tests/` returns no results. `grep -r "mask_code_fences" tests/` finds only test_markdown_utils.py. No test imports both.

**Discovery Chain:** searched tests for cross-implementation coverage -> none found -> divergence bugs BJ-001 and BJ-002 survived 18 runs undetected

**Acceptance Criteria:**
- [ ] A test exists that feeds identical inputs to both mask_code_fences and mask_fenced_blocks
- [ ] Test corpus includes: plain fences, indented fences (1-3 spaces), 4-space indent (not a fence), tilde fences, backtick-in-info-string, nested fences, unclosed fences

**Validation Command:**
```bash
grep -r "mask_fenced_blocks.*mask_code_fences\|mask_code_fences.*mask_fenced_blocks" tests/
```

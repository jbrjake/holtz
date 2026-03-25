# Flatten Phase Numbering to Step 0-20 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all phase/subphase/letter numbering (Phase 0a.1, Pre-Phase 4, etc.) with a flat Step 0-20 list across the entire Holtz plugin.

**Architecture:** Sweeping rename touching ~25 files. Ordered by dependency: SKILL.md first (source of truth), then reference docs, then code/tests, then diagrams, then consumer-facing docs. Each tier committed independently.

**Tech Stack:** Markdown (SKILL.md, references), Python (scripts, hooks, tests), Graphviz DOT (diagrams), SVG (rendered diagrams)

**Spec:** `docs/superpowers/specs/2026-03-25-flatten-step-numbering-design.md`

---

### Task 1: Create feature branch

**Files:**
- None (git operation only)

- [ ] **Step 1: Create and checkout feature branch**

```bash
git checkout -b feat/flatten-steps dev
```

- [ ] **Step 2: Verify clean state**

```bash
git status
```

Expected: clean working tree on `feat/flatten-steps`

---

### Task 2: Rewrite SKILL.md process flow

This is the largest single change. SKILL.md is the source of truth — every other file follows it.

**Files:**
- Modify: `skills/holtz/SKILL.md`

**Reference:** Read the spec's Canonical Step List and Old-to-New Mapping before starting.

- [ ] **Step 1: Read the current SKILL.md completely**

Read: `skills/holtz/SKILL.md`

- [ ] **Step 2: Rewrite Phase 0 section to Steps 0-4**

Replace the Phase 0 section (~lines 134-142) with the new recon steps:

```markdown
### Step 0: Project Overview + Drift Detection

Read [references/recon-procedures.md](references/recon-procedures.md) for detailed procedures.

Read project structure, docs, CLAUDE.md, architecture. Compare against architecture baseline (drift detection). Initialize impact graph.

Output: `docs/holtz/recon/step0-project-overview.md`

### Step 1: Run Toolchain (Subagent)

Dispatch a subagent to run in parallel:
- Test suite (capture pass/fail/skip/coverage)
- CI pipeline status (if CI exists)
- Linters/type checkers

Output: `docs/holtz/recon/step1-toolchain.md`

### Step 2: Code Signals (Subagent)

Dispatch a subagent to run in parallel:
- Git churn analysis (top 20 most-changed files in last 50 commits)
- Mutation scan (optional — auto-detected)
- Skipped/disabled test scan

Output: `docs/holtz/recon/step2-code-signals.md`

### Step 3: Recon Summary

Synthesize Steps 0-2 into mental model. Load pattern library. Run recommendation escalation.

Output: `docs/holtz/recon/step3-recon-summary.md`

### Step 4: Predictions

Use extended thinking (ultrathink). Rank where bugs are likely to be found using six input sources: pattern brief, impact graph risk scores, impact graph edges, git churn, prior run findings, recon observations.

Output: `docs/holtz/recon/step4-predictions.md`
```

- [ ] **Step 3: Rewrite Dispatch Justine section to Step 5**

Replace ~lines 144-158. Critical: update the embedded path description in the dispatch prompt.

Old: `"Holtz's Phase 0 recon data is at docs/holtz/recon/ (files 0a through 0f)."`
New: `"Holtz's recon data is at docs/holtz/recon/ (step0-project-overview.md, step1-toolchain.md, step2-code-signals.md)."`

Section header: `### Step 5: Dispatch Justine`

- [ ] **Step 4: Rewrite Phase 1 section to Step 6**

Replace ~lines 160-177. Update HARD-GATE block:

Old paths in HARD-GATE:
- `docs/holtz/recon/0g-recon-summary.md` -> `docs/holtz/recon/step3-recon-summary.md`
- `docs/holtz/recon/0h-predictions.md` -> `docs/holtz/recon/step4-predictions.md`

Section header: `### Step 6: Doc-to-Implementation Audit`

- [ ] **Step 5: Rewrite Phase 2 section to Step 7**

Replace ~lines 178-190. Update recon file reads:

Old: `Read recon summary (0g) and predictions (0h)`
New: `Read recon summary (Step 3) and predictions (Step 4)`

Old path refs: `0g-recon-summary.md`, `0h-predictions.md`
New: `step3-recon-summary.md`, `step4-predictions.md`

Section header: `### Step 7: Test Quality Audit`

- [ ] **Step 6: Rewrite Phase 3 section to Step 8**

Replace ~lines 191-203. Update all recon file reads:

Old: `0g-recon-summary.md`, `0h-predictions.md`, `0e-churn.md`, `step 0e.1`
New: `step3-recon-summary.md`, `step4-predictions.md`, `step2-code-signals.md`, `Step 2 (mutation scan)`

Section header: `### Step 8: Adversarial Code Audit`

- [ ] **Step 7: Rewrite Pre-Phase 4 to Step 9**

Replace ~lines 204-218.

Section header: `### Step 9: Merge Justine Findings (Subagent)`

- [ ] **Step 8: Rewrite Phase 4 to Step 10**

Replace ~lines 219-234. Update reference link:

Old: `[references/phase-4-fix-loop.md](references/phase-4-fix-loop.md)`
New: `[references/step-10-fix-loop.md](references/step-10-fix-loop.md)`

Section header: `### Step 10: TDD Fix Loop`

- [ ] **Step 9: Rewrite Phase 5 to Step 11 (recurring)**

Replace ~lines 235-265.

Section header: `### Step 11: Pattern Analysis [recurring: every 3-5 fixes during Step 10]`

- [ ] **Step 10: Add Steps 12-13 (recurring)**

These were previously unnamed activities embedded in the fix loop. Give them their own sections:

```markdown
### Step 12: Per-Fix Hardening [recurring: after each fix in Step 10]

After each fix: edge case variants (null, empty, boundary, concurrent), regression tests for similar code paths.

### Step 13: Blast Radius Check [recurring: after each fix in Step 10]

After each fix: impact graph 2-hop query. Check downstream assumptions. If an assumption is violated, create a new punchlist item.
```

- [ ] **Step 11: Rewrite Phase 6 to Steps 14-16**

Replace ~lines 266-335. Split into three distinct steps:

```markdown
### Step 14: Lens Rotation

Re-run Steps 6-8 scoped to the current analytical lens. After completing, return to Step 10 (fix loop) for any new findings.

### Step 15: Convergence Check

Run: `python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/convergence_check.py`

- exit 1 -> back to Step 10 with next lens
- exit 0 -> proceed to Step 16

### Step 16: Resweep

Full re-run of Steps 6-8 to confirm convergence. This is NOT optional — it catches errors introduced by prior fixes.
```

Move circuit breakers into Step 14 or a shared "Convergence Loop" preamble.

- [ ] **Step 12: Add Steps 17-20 (post-convergence)**

These were previously unnamed activities. Give them sections:

```markdown
### Step 17: Architecture Baseline Update (Subagent)

Dispatch background subagent to update `docs/holtz/architecture-baseline.md`.

### Step 18: Pattern Library Contribution (Subagent)

Provide list of new patterns discovered this run. Subagent formats and writes to pattern library.

### Step 19: Living Punchlist Update (Subagent)

Mechanical transform from PUNCHLIST.md to LIVING-PUNCHLIST.md.

### Step 20: Write SUMMARY.md

Final synthesis with prediction accuracy table. This is the LAST step — nothing comes after it.
```

- [ ] **Step 13: Update resume logic section**

~Lines 93-131. Replace all `Phase N` references with `Step N` equivalents. Update the lifecycle diagram to use step numbers. Replace all `docs/holtz/recon/0*.md` path references.

- [ ] **Step 14: Search for any remaining "Phase" references in SKILL.md**

Run: `grep -n -i "phase" skills/holtz/SKILL.md`

Fix any remaining references. Expected: zero matches (except possibly in historical context notes).

- [ ] **Step 15: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat: rewrite SKILL.md process flow to Step 0-20"
```

---

### Task 3: Rename and update recon procedures reference

**Files:**
- Rename: `skills/holtz/references/phase-0-recon.md` -> `skills/holtz/references/recon-procedures.md`

- [ ] **Step 1: Read the current file**

Read: `skills/holtz/references/phase-0-recon.md`

- [ ] **Step 2: Rename the file**

```bash
git mv skills/holtz/references/phase-0-recon.md skills/holtz/references/recon-procedures.md
```

- [ ] **Step 3: Update the title and header**

Old: `# Phase 0: Recon -- Detailed Procedures`
New: `# Recon Procedures (Steps 0-4)`

Old: `Read this file at the start of Phase 0.`
New: `Read this file at the start of Step 0.`

- [ ] **Step 4: Update the recon steps table**

Replace the step table (~lines 9-18) with new step-aligned naming:

| Step | Action | Output File |
|------|--------|-------------|
| 0 | Read project structure, docs, CLAUDE.md, architecture + drift detection | `docs/holtz/recon/step0-project-overview.md` |
| 1 (subagent) | Run test suite, check CI, run linters | `docs/holtz/recon/step1-toolchain.md` |
| 2 (subagent) | Git churn, mutation scan, skipped tests | `docs/holtz/recon/step2-code-signals.md` |
| 3 | Recon summary (synthesis of Steps 0-2) | `docs/holtz/recon/step3-recon-summary.md` |
| 4 | Predictive recon (ranked predictions) | `docs/holtz/recon/step4-predictions.md` |

- [ ] **Step 5: Update all internal step references**

Replace throughout:
- `step 0e.1` -> `Step 2 (mutation scan)`
- `step 0c` -> `Step 1 (test baseline)`
- `step 0e` -> `Step 2 (churn)`
- `step 0g` -> `Step 3`
- `step 0h` -> `Step 4`
- `step 0a` -> `Step 0`
- `Phase 0` -> `Steps 0-4`
- `Phase 1` -> `Step 6`
- `Phase 2` -> `Step 7`
- `Phase 3` -> `Step 8`
- `Phase 4` -> `Step 10`

- [ ] **Step 6: Update output file paths in detailed sections**

All `0a-project-overview.md` -> `step0-project-overview.md`, etc. through the file. Use the Recon Output File Renaming table from the spec.

- [ ] **Step 7: Update STATUS.md initialization reference**

Old: `## STATUS.md Initialization` referencing Phase-based checklist
New: Step-based checklist

- [ ] **Step 8: Verify no remaining Phase references**

```bash
grep -n -i "phase" skills/holtz/references/recon-procedures.md
```

Expected: zero matches.

- [ ] **Step 9: Commit**

```bash
git add skills/holtz/references/recon-procedures.md
git commit -m "feat: rename phase-0-recon.md to recon-procedures.md with step numbering"
```

---

### Task 4: Rename and update fix loop reference

**Files:**
- Rename: `skills/holtz/references/phase-4-fix-loop.md` -> `skills/holtz/references/step-10-fix-loop.md`

- [ ] **Step 1: Read the current file**

Read: `skills/holtz/references/phase-4-fix-loop.md`

- [ ] **Step 2: Rename the file**

```bash
git mv skills/holtz/references/phase-4-fix-loop.md skills/holtz/references/step-10-fix-loop.md
```

- [ ] **Step 3: Update title and header**

Old: `# Phase 4: Fix Loop (TDD) -- Detailed Procedures`
New: `# Step 10: TDD Fix Loop -- Detailed Procedures`

Old: `Read this file at the start of Phase 4.`
New: `Read this file at the start of Step 10.`

- [ ] **Step 4: Replace all Phase references throughout**

- `Phase 4` -> `Step 10`
- `Phase 5` -> `Step 11`
- `Phase 1+` -> `Step 6+`
- `Phase 1` -> `Step 6`
- `Phase 2` -> `Step 7`
- `Phase 3` -> `Step 8`
- `Phases 1-3` -> `Steps 6-8`
- `Phase 0` -> `Steps 0-4`

- [ ] **Step 5: Verify no remaining Phase references**

```bash
grep -n -i "phase" skills/holtz/references/step-10-fix-loop.md
```

- [ ] **Step 6: Commit**

```bash
git add skills/holtz/references/step-10-fix-loop.md
git commit -m "feat: rename phase-4-fix-loop.md to step-10-fix-loop.md with step numbering"
```

---

### Task 5: Update justine-skill.md

**Files:**
- Modify: `skills/holtz/references/justine-skill.md`

- [ ] **Step 1: Read the current file**

Read: `skills/holtz/references/justine-skill.md`

- [ ] **Step 2: Rewrite Inherited Recon Mode (lines ~161-179)**

Update guard condition:
Old: `If docs/holtz/recon/0g-recon-summary.md does not exist`
New: `If docs/holtz/recon/step0-project-overview.md and docs/holtz/recon/step1-toolchain.md do not exist`

Update file references:
Old: `Read docs/holtz/recon/0a through 0f`
New: `Read docs/holtz/recon/step0-project-overview.md, step1-toolchain.md, step2-code-signals.md (if exists)`

- [ ] **Step 3: Rewrite Solo Recon Mode (lines ~181-195)**

Update reference path:
Old: `${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/phase-0-recon.md`
New: `${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/recon-procedures.md`

- [ ] **Step 4: Rewrite Phase sections to J-steps**

- Phase 0 -> `J0: Inherit Recon + Own Summary/Predictions`
- Phases 1-3 (Non-Sequential Audit) -> `J2: Multi-Lens Audit` (with J1: Immediate Prediction Testing before it)
- Phase 4 -> `J3: TDD Fix Loop`
- Phase 5 -> `J4: Pattern Analysis [recurring]`
- Phase 6 -> `J5: Single-Pass Convergence`
- Post-convergence summary -> `J6: Write Summary`

- [ ] **Step 5: Update HARD-GATE blocks**

Lines ~199-205: Update recon file paths in the audit prerequisite gate:
Old: `docs/holtz/justine/recon/0g-recon-summary.md`, `0h-predictions.md`
New: `docs/holtz/justine/recon/step3-recon-summary.md`, `step4-predictions.md`

- [ ] **Step 6: Update fix loop reference link**

Old: `references/phase-4-fix-loop.md`
New: `references/step-10-fix-loop.md`

- [ ] **Step 7: Replace all remaining Phase references**

Replace throughout: `Phase 0` -> `J0`, `Phase 1` -> part of `J2`, `Phase 2` -> part of `J2`, `Phase 3` -> part of `J2`, `Phase 4` -> `J3`, `Phase 5` -> `J4`, `Phase 6` -> `J5`.

Also replace Holtz cross-references: `Phase 1` (Holtz) -> `Step 6`, etc.

- [ ] **Step 8: Verify**

```bash
grep -n -i "phase" skills/holtz/references/justine-skill.md
```

- [ ] **Step 9: Commit**

```bash
git add skills/holtz/references/justine-skill.md
git commit -m "feat: rewrite justine-skill.md to J0-J6 step numbering"
```

---

### Task 6: Update status-file-format.md

**Files:**
- Modify: `skills/holtz/references/status-file-format.md`

- [ ] **Step 1: Read the current file**

Read: `skills/holtz/references/status-file-format.md`

- [ ] **Step 2: Rewrite the template**

Replace the Current Position section (lines 15-18):

Old:
```markdown
## Current Position
**Phase:** {0-6}
**Step:** {e.g., 0c, Phase 2 batch 3, Phase 4 item BH-012}
**Status:** {IN PROGRESS | BLOCKED | CONVERGING | COMPLETE}
```

New:
```markdown
## Current Position
**Step:** {0-20}
**Status:** {IN PROGRESS | BLOCKED | CONVERGING | COMPLETE}
```

- [ ] **Step 3: Rewrite the Completed checklist**

Old (lines 21-29):
```markdown
## Completed
- [x] Phase 0a: Project overview
- [x] Phase 0b: Test infrastructure
- [ ] Phase 0c: Test baseline
...
```

New:
```markdown
## Completed
- [ ] Step 0: Project overview + drift detection
- [ ] Step 1: Run toolchain (subagent)
- [ ] Step 2: Code signals (subagent)
- [ ] Step 3: Recon summary
- [ ] Step 4: Predictions
- [ ] Step 5: Dispatch Justine
- [ ] Step 6: Doc-to-implementation audit
- [ ] Step 7: Test quality audit
- [ ] Step 8: Adversarial code audit
- [ ] Step 9: Merge Justine findings (subagent)
- [ ] Step 10: TDD fix loop
- [ ] Step 11: Pattern analysis [recurring]
- [ ] Step 12: Per-fix hardening [recurring]
- [ ] Step 13: Blast radius check [recurring]
- [ ] Step 14: Lens rotation
- [ ] Step 15: Convergence check
- [ ] Step 16: Resweep
- [ ] Step 17: Architecture baseline update (subagent)
- [ ] Step 18: Pattern library contribution (subagent)
- [ ] Step 19: Living punchlist update (subagent)
- [ ] Step 20: Write SUMMARY.md
```

- [ ] **Step 4: Update Rules section**

Replace "every phase" with "every step", "phase transition" with "step transition".

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/references/status-file-format.md
git commit -m "feat: rewrite STATUS.md template to Step 0-20 numbering"
```

---

### Task 7: Update remaining reference docs

**Files:**
- Modify: `skills/holtz/references/impact-graph-operations.md` (18 phase refs)
- Modify: `skills/holtz/references/lens-registry.md` (1 phase ref)
- Modify: `skills/holtz/references/punchlist-format.md` (2 phase refs)
- Modify: `skills/holtz/references/living-punchlist-format.md`
- Modify: `skills/holtz/references/investigation-format.md`
- Modify: `skills/holtz/references/architecture-baseline-format.md`

- [ ] **Step 1: Read all files**

Read each file listed above.

- [ ] **Step 2: Update impact-graph-operations.md**

This file has the most changes (18 references). Apply these replacements throughout:

- `Phase 0` -> `Steps 0-4` (or `Step 0` when specifically about project overview)
- `Phase 1` -> `Step 6`
- `Phase 2` -> `Step 7`
- `Phase 3` -> `Step 8`
- `Phase 4` -> `Step 10`
- `Phase 5` -> `Step 11`
- `Phases 1-3` -> `Steps 6-8`
- `Phase 1+` -> `Step 6+`
- `audit phase (1, 2, 3)` -> `audit steps (6, 7, 8)`
- `each audit phase` -> `each audit step`
- Section: `## Adding Edges During Audit Phases` -> `## Adding Edges During Audit Steps`
- Section: `## Blast Radius Queries (Phase 4)` -> `## Blast Radius Queries (Step 10)`
- Section: `## Risk Score Updates (Phase 4)` -> `## Risk Score Updates (Step 10)`
- Comments in CLI examples: `# Relationship edges (Phase 0)` -> `# Relationship edges (Steps 0-4)`
- `# Test coverage edges (Phase 2)` -> `# Test coverage edges (Step 7)`
- `# Semantic edges (Phases 1-3)` -> `# Semantic edges (Steps 6-8)`
- `# Pattern edges (Phase 5)` -> `# Pattern edges (Step 11)`
- `# Co-fix edges (Phase 4 blast radius)` -> `# Co-fix edges (Step 10 blast radius)`

- [ ] **Step 3: Update lens-registry.md**

Line 11: `Standard Phases 1-3` -> `Standard Steps 6-8`

- [ ] **Step 4: Update punchlist-format.md**

Line 50: `assess determinism during Phase 3 (adversarial audit)` -> `assess determinism during Step 8 (adversarial code audit)`
Line 56: `reproduction strategy in Phase 4` -> `reproduction strategy in Step 10`

- [ ] **Step 5: Update living-punchlist-format.md, investigation-format.md, architecture-baseline-format.md**

Search each for any Phase references and update. These may have zero references — verify with grep.

- [ ] **Step 6: Verify all reference docs are clean**

```bash
grep -rn -i "phase" skills/holtz/references/ | grep -v "step-10-fix-loop.md:1" | head -20
```

Expected: zero matches (except the file title of step-10-fix-loop.md if it still says "Phase" in a historical context note).

- [ ] **Step 7: Commit**

```bash
git add skills/holtz/references/
git commit -m "feat: update all reference docs to step numbering"
```

---

### Task 8: Update profiler_plugin.py

**Files:**
- Modify: `skills/holtz/scripts/profiler_plugin.py:20-52`
- Test: `tests/test_token_profiler_plugin.py`

- [ ] **Step 1: Read the current code**

Read: `skills/holtz/scripts/profiler_plugin.py` lines 20-55

- [ ] **Step 2: Replace _PHASE_PATTERNS with _STEP_PATTERNS**

Old (lines 20-32):
```python
# ---------------------------------------------------------------------------
# Phase detection patterns (order matters: later = higher priority)
# ---------------------------------------------------------------------------

_PHASE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("recon", re.compile(r"Phase[ \t]*0|recon|phase-0-recon", re.IGNORECASE)),
    ("phase-1", re.compile(r"Phase[ \t]*1|Doc.*Audit|doc.*claim", re.IGNORECASE)),
    ("phase-2", re.compile(r"Phase[ \t]*2|Test.*Quality|Test.*Audit", re.IGNORECASE)),
    ("phase-3", re.compile(r"Phase[ \t]*3|Adversarial.*Code|Adversarial.*Audit", re.IGNORECASE)),
    ("merge", re.compile(r"Merge|Justine.*findings|classify.*findings", re.IGNORECASE)),
    ("fix-loop", re.compile(r"Phase[ \t]*4|TDD|fix[ \t]*loop|failing[ \t]*test", re.IGNORECASE)),
    ("convergence", re.compile(r"converg|SUMMARY\.md|final[ \t]*commit", re.IGNORECASE)),
]
```

New:
```python
# ---------------------------------------------------------------------------
# Step detection patterns (order matters: later = higher priority)
# ---------------------------------------------------------------------------

_STEP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("step-0-4", re.compile(r"Step[ \t]*[01234](?!\d)|recon|recon-procedures", re.IGNORECASE)),
    ("step-6", re.compile(r"Step[ \t]*6|Doc.*Audit|doc.*claim", re.IGNORECASE)),
    ("step-7", re.compile(r"Step[ \t]*7|Test.*Quality|Test.*Audit", re.IGNORECASE)),
    ("step-8", re.compile(r"Step[ \t]*8|Adversarial.*Code|Adversarial.*Audit", re.IGNORECASE)),
    ("step-9", re.compile(r"Step[ \t]*9|Merge|Justine.*findings|classify.*findings", re.IGNORECASE)),
    ("step-10", re.compile(r"Step[ \t]*10|TDD|fix[ \t]*loop|failing[ \t]*test", re.IGNORECASE)),
    ("step-14-15", re.compile(r"Step[ \t]*1[45]|converg|SUMMARY\.md|final[ \t]*commit", re.IGNORECASE)),
]
```

- [ ] **Step 3: Update _DETECT_PATTERNS**

Old (lines 48-52):
```python
_DETECT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"holtz", re.IGNORECASE),
    re.compile(r"phase[ \t]*0", re.IGNORECASE),
    re.compile(r"full[ \t]+audit", re.IGNORECASE),
]
```

New:
```python
_DETECT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"holtz", re.IGNORECASE),
    re.compile(r"step[ \t]*0", re.IGNORECASE),
    re.compile(r"full[ \t]+audit", re.IGNORECASE),
]
```

- [ ] **Step 4: Update all references to _PHASE_PATTERNS in the rest of the file**

Search for `_PHASE_PATTERNS` and replace with `_STEP_PATTERNS` throughout `profiler_plugin.py`.

```bash
grep -n "_PHASE_PATTERNS" skills/holtz/scripts/profiler_plugin.py
```

Replace every occurrence.

- [ ] **Step 5: Run existing tests to see what breaks**

```bash
python -m pytest tests/test_token_profiler_plugin.py -v
```

Expected: failures in `test_full_phase_progression` and `test_phase_detected_by_regex_patterns` due to old labels.

- [ ] **Step 6: Update test_token_profiler_plugin.py**

Read: `tests/test_token_profiler_plugin.py`

In `test_full_phase_progression` (~lines 87-111):
- Update turn text strings from `"Starting Phase 0 reconnaissance"` to `"Starting Step 0 reconnaissance"`
- Update turn text from `"Phase 1 Doc Audit"` to `"Step 6 Doc Audit"`, etc.
- Update expected label assertions from `"recon"` to `"step-0-4"`, `"phase-1"` to `"step-6"`, etc.

In `test_phase_detected_by_regex_patterns` (~lines 129-148):
- Update regex test strings and expected labels to match new patterns.

Rename test functions:
- `test_full_phase_progression` -> `test_full_step_progression`
- `test_phase_detected_by_regex_patterns` -> `test_step_detected_by_regex_patterns`

- [ ] **Step 7: Run tests to verify**

```bash
python -m pytest tests/test_token_profiler_plugin.py -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add skills/holtz/scripts/profiler_plugin.py tests/test_token_profiler_plugin.py
git commit -m "feat: rename profiler phase detection to step detection"
```

---

### Task 9: Update convergence_check.py and impact_graph_gate.py

**Files:**
- Modify: `skills/holtz/scripts/convergence_check.py:482`
- Modify: `hooks/impact_graph_gate.py:4`

- [ ] **Step 1: Update convergence_check.py**

Line 482, old:
```python
print("\nThe fix loop has converged. Run a final Phase 1-3 sweep to confirm.")
```

New:
```python
print("\nThe fix loop has converged. Run a final Steps 6-8 sweep to confirm.")
```

- [ ] **Step 2: Update impact_graph_gate.py**

Line 4, old:
```python
Blocks writing Phase 1+ audit files unless the corresponding
```

New:
```python
Blocks writing Step 6+ audit files unless the corresponding
```

- [ ] **Step 3: Run hook tests**

```bash
python -m pytest tests/test_hooks.py -v -k "impact_graph_gate or convergence"
```

Expected: PASS (these tests don't assert on the specific string content).

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/scripts/convergence_check.py hooks/impact_graph_gate.py
git commit -m "fix: update phase references in convergence_check.py and impact_graph_gate.py"
```

---

### Task 10: Update test_hooks.py

**Files:**
- Modify: `tests/test_hooks.py`

- [ ] **Step 1: Read the relevant test functions**

Read: `tests/test_hooks.py` lines 640-950

- [ ] **Step 2: Update _make_status() default and all Phase field references**

Every `"**Phase:** N"` string becomes `"**Step:** N"` with the new step number:

- `"**Phase:** 0"` -> `"**Step:** 0"`
- `"**Phase:** 3"` -> `"**Step:** 8"`
- `"**Phase:** 4"` -> `"**Step:** 10"`
- `"**Phase:** 6"` -> `"**Step:** 15"` (convergence check) or `"**Step:** 20"` (complete)

For COMPLETE/CONVERGED status tests: use `"**Step:** 20"` (the final step).
For IN PROGRESS tests: use the step number that matches the test's intent.

- [ ] **Step 3: Update assertion strings**

Line 732: `"Phase: 4"` in assertion -> `"Step: 10"`
Line 891: `"Phase 3"` in assertion -> `"Step 8"`
Line 947: `"Phase 4"` in assertion -> `"Step 10"`

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_hooks.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_hooks.py
git commit -m "test: update hook tests to step numbering"
```

---

### Task 11: Run full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

```bash
python -m pytest --tb=short -q
```

Expected: all PASS.

- [ ] **Step 2: Run linter**

```bash
ruff check .
```

Expected: clean.

- [ ] **Step 3: Run type checker**

```bash
mypy skills/holtz/scripts/ hooks/
```

Expected: clean.

---

### Task 12: Update diagram .dot files

**Files:**
- Rename + modify: `docs/diagrams/phase4-triage.dot` -> `docs/diagrams/step10-triage.dot`
- Modify: `docs/diagrams/holtz-convergence.dot`
- Modify: `docs/diagrams/justine-convergence.dot`
- Modify: `docs/diagrams/resume-lifecycle.dot`
- Modify: `docs/diagrams/impact-graph.dot`

- [ ] **Step 1: Read all 5 .dot files**

Read each file completely.

- [ ] **Step 2: Rename phase4-triage.dot**

```bash
git mv docs/diagrams/phase4-triage.dot docs/diagrams/step10-triage.dot
```

- [ ] **Step 3: Update step10-triage.dot labels**

Replace all `Phase 4` and `Phase 5` labels with `Step 10` and `Step 11`. Replace `Phase 4 (next batch)` with `Step 10 (next batch)`. Replace `Phase 5 (every 3-5)` with `Step 11 (every 3-5)`.

- [ ] **Step 4: Update holtz-convergence.dot labels**

Replace phase labels:
- `Phase 4 (next batch)` -> `Step 10 (next batch)`
- `Phase 5 (every 3-5)` -> `Step 11 (every 3-5)`
- `Phase 6 lens rotation` -> `Step 14 lens rotation`
- `convergence_check.py` label text referencing phases
- Any `Phase 1-3` -> `Steps 6-8`

Preserve all colors, fonts, strokes, sizes — only change label text.

- [ ] **Step 5: Update justine-convergence.dot labels**

Replace Justine's phase labels with J-step equivalents:
- `Phase 4` -> `J3`
- `Phase 5` -> `J4`
- `Phase 6` -> `J5`
- Any `Phase 1-3` -> `J2`

- [ ] **Step 6: Update resume-lifecycle.dot labels**

Replace any phase references in node labels with step numbers.

- [ ] **Step 7: Update impact-graph.dot labels**

Replace any phase references. This diagram shows module dependencies, so it may have few/no phase labels — verify and update as needed.

- [ ] **Step 8: Delete old SVG files**

```bash
rm docs/diagrams/phase4-triage.svg
```

- [ ] **Step 9: Re-render all SVGs**

```bash
dot -Tsvg docs/diagrams/step10-triage.dot -o docs/diagrams/step10-triage.svg
dot -Tsvg docs/diagrams/holtz-convergence.dot -o docs/diagrams/holtz-convergence.svg
dot -Tsvg docs/diagrams/justine-convergence.dot -o docs/diagrams/justine-convergence.svg
dot -Tsvg docs/diagrams/resume-lifecycle.dot -o docs/diagrams/resume-lifecycle.svg
dot -Tsvg docs/diagrams/impact-graph.dot -o docs/diagrams/impact-graph.svg
```

- [ ] **Step 10: Verify SVGs render correctly**

Open each SVG in a browser to verify labels are correct and theming is preserved.

- [ ] **Step 11: Commit**

```bash
git add docs/diagrams/
git commit -m "feat: update diagrams to step numbering and re-render SVGs"
```

---

### Task 13: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read README.md**

Read: `README.md`

- [ ] **Step 2: Update "The seven phases" section**

Lines ~131-147. Rename section header and all phase descriptions:

Old: `## The seven phases`
New: `## The twenty-one steps`

Replace each phase paragraph:
- `**Phase 0: Recon.**` -> `**Steps 0-4: Recon.**`
- `**Phase 1: Doc-to-implementation audit.**` -> `**Step 6: Doc-to-implementation audit.**`
- `**Phase 2: Test quality audit.**` -> `**Step 7: Test quality audit.**`
- `**Phase 3: Adversarial code audit.**` -> `**Step 8: Adversarial code audit.**`
- `**Phase 4: Fix loop.**` -> `**Step 10: Fix loop.**`
- `**Phase 5: Pattern analysis.**` -> `**Step 11: Pattern analysis.**`
- `**Phase 6: Convergence.**` -> `**Steps 14-16: Convergence.**` Update text: `Repeat Phases 4-5` -> `Repeat Steps 10-11`

- [ ] **Step 3: Update intro paragraph**

Line ~37: `seven-phase audit` -> `twenty-one-step audit`

- [ ] **Step 4: Update Phase 4 triage image path**

Line 93, old:
```html
<p align="center"><img src="docs/diagrams/phase4-triage.svg" alt="Phase 4 triage flowchart"></p>
```

New:
```html
<p align="center"><img src="docs/diagrams/step10-triage.svg" alt="Step 10 triage flowchart"></p>
```

- [ ] **Step 5: Update impact graph gate description**

Line ~199: `Phase 1+` -> `Step 6+`

- [ ] **Step 6: Replace all remaining Phase references**

```bash
grep -n -i "phase" README.md
```

Fix any remaining references.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: update README to step numbering"
```

---

### Task 14: Update agent definitions

**Files:**
- Modify: `agents/holtz.md`
- Modify: `agents/justine.md`

- [ ] **Step 1: Read both files**

Read: `agents/holtz.md` and `agents/justine.md`

- [ ] **Step 2: Update holtz.md**

Replace all Phase references with Step equivalents. Key areas:
- Agent description (~lines 3-4): update any phase mentions
- "How you work" section (~lines 29-38): update methodology description

- [ ] **Step 3: Update justine.md**

Replace all Phase references with J-step equivalents.

- [ ] **Step 4: Verify**

```bash
grep -n -i "phase" agents/holtz.md agents/justine.md
```

Expected: zero matches.

- [ ] **Step 5: Commit**

```bash
git add agents/holtz.md agents/justine.md
git commit -m "feat: update agent definitions to step numbering"
```

---

### Task 15: Update holtz-showcase.md and token-profiling-analysis-playbook.md

**Files:**
- Modify: `docs/holtz-showcase.md` (~13 phase refs)
- Modify: `docs/token-profiling-analysis-playbook.md` (~11 phase refs)

- [ ] **Step 1: Read both files**

Read: `docs/holtz-showcase.md` and `docs/token-profiling-analysis-playbook.md`

- [ ] **Step 2: Update holtz-showcase.md**

Key replacements:
- Lines 890-899: The seven-phase methodology block -> Step 0-20 equivalents
- Lines 554, 566-567, 575: `Phases 0-5` -> `Steps 0-11`, `Phase 0` -> `Steps 0-4`, etc.
- Line 378, 388: "One Phase Behind Reality" — this is a case study title/description about a bug in another project (Giles), not about Holtz's phases. Leave as-is — "phase" here means project phase, not Holtz audit phase.
- Line 933: "Kanban states one phase late" — same, leave as-is.

- [ ] **Step 3: Update token-profiling-analysis-playbook.md**

Key replacements:
- Line 112: `## Step 6: Phase Breakdown` -> `## Step 6: Step Breakdown`
- Lines 118-126: Phase cost table labels:
  - `recon` -> `step-0-4`
  - `phase-1` -> `step-6`
  - `phase-2` -> `step-7`
  - `phase-3` -> `step-8`
  - `fix-loop` -> `step-10`
  - `merge` -> `step-9`
  - `convergence` -> `step-14-15`
- Lines 129-130: `Recon should be the costliest phase` -> `Recon should be the costliest step group`
- Line 157: `Phase 0 (reconnaissance/exploration)` -> `Steps 0-4 (reconnaissance/exploration)`

- [ ] **Step 4: Commit**

```bash
git add docs/holtz-showcase.md docs/token-profiling-analysis-playbook.md
git commit -m "docs: update showcase and profiling playbook to step numbering"
```

---

### Task 16: Final verification and cleanup

**Files:** None (verification only)

- [ ] **Step 1: Search entire codebase for remaining Phase references**

```bash
grep -rn -i "phase[ \t]*[0-6]" skills/holtz/ agents/ hooks/ tests/ README.md docs/holtz-showcase.md docs/token-profiling-analysis-playbook.md | grep -v "docs/holtz/archive/" | grep -v "docs/runs/" | grep -v "docs/superpowers/"
```

Expected: zero matches (or only matches in historical/frozen files).

- [ ] **Step 2: Search for old recon file paths**

```bash
grep -rn "0[a-h]-\|0c1-\|0e1-\|0g-\|0h-" skills/holtz/ agents/ hooks/ tests/ README.md
```

Expected: zero matches.

- [ ] **Step 3: Run full test suite one final time**

```bash
python -m pytest --tb=short -q && ruff check . && mypy skills/holtz/scripts/ hooks/
```

Expected: all clean.

- [ ] **Step 4: Review git log for the branch**

```bash
git log feat/flatten-steps --not dev --oneline
```

Verify all commits follow conventional commit format and the logical grouping makes sense.

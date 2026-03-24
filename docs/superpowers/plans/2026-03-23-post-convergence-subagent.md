# Post-Convergence Subagent Implementation Plan (Conservative Scope)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Holtz's late-run context load by delegating the most mechanical post-convergence tasks to a subagent, while keeping judgment-heavy work with Holtz.

**Architecture:** A general-purpose subagent handles only the architecture baseline Structural Snapshot update — the one post-convergence task that is purely structural code analysis (trace imports, list dependencies, identify entry points) with zero audit judgment required. Everything else stays with Holtz.

**Tech Stack:** Skill file updates only. No new agent definitions — uses general-purpose subagent.

---

## Scope Analysis: What's Mechanical vs What's Judgment

Before defining tasks, here's the honest breakdown of post-convergence work:

### Stays with Holtz (requires judgment)

| Task | Why it needs Holtz |
|------|-------------------|
| **Living Punchlist: Derive proactive checks** (step 5) | Requires understanding which patterns predict future bugs and what areas to watch — this is the most valuable part of the living punchlist |
| **Living Punchlist: Write run summary** (step 7) | Narrative about what happened, what was surprising, what changed — needs Holtz's accumulated understanding |
| **Living Punchlist: Add patterns** (step 2) | Deciding which patterns are architecturally significant vs one-off requires Holtz's judgment |
| **Pattern contribution: Generalize & PII scrub** | Understanding what's project-specific requires knowing the project |
| **Pattern contribution: Ask user permission** | Interactive — cannot be delegated to background subagent |
| **SUMMARY.md** | Requires Holtz's accumulated metrics, narrative, recommendations |
| **Living Punchlist: Risk hotspots** (step 1) | Simple graph query, but interpreting risk_score in context requires seeing the full run |
| **Living Punchlist: Architectural risks** (step 3) | Copying drift log entries, but judging which are MEDIUM+ requires run context |
| **Living Punchlist: Prediction accuracy** (step 4) | Simple counting, but Holtz already has the numbers in context |
| **Living Punchlist: Move cooled hotspots** (step 6) | Requires judgment about whether a "cooled" area is truly stable |

### Delegatable (purely structural)

| Task | Why it's mechanical |
|------|-------------------|
| **Architecture baseline: Structural Snapshot update** | Trace imports, list module dependencies, identify entry points. This is code analysis — read files, follow imports, build an adjacency list. No audit context needed. |
| **Architecture baseline: Documented Intent comparison** | Compare current project docs against baseline. This is diff-like work — read current docs, read baseline, note what changed. |

### Estimated savings

**Conservative scope (Structural Snapshot + Documented Intent only):**
- `architecture-baseline-format.md` (221 lines / ~1,100 tokens) stays out of Holtz's context
- Code reads for structural analysis (variable, ~500-2,000 tokens) stay in subagent
- Total: **~1,600-3,100 tokens** freed from Holtz's late-run context

This is smaller than the original design's ~4,080-5,080 estimate because the living punchlist and pattern contribution stay with Holtz. The savings are real but modest.

---

### Task 1: Update SKILL.md post-convergence section to dispatch baseline subagent

**Files:**
- Modify: `skills/holtz/SKILL.md:299-324` (Post-Convergence section)

- [ ] **Step 1: Read current post-convergence section**

Read: `skills/holtz/SKILL.md:299-324`

- [ ] **Step 2: Add subagent dispatch for baseline update before living punchlist work**

Insert after "After convergence, read references/pattern-contribution-protocol.md..." and before "Living Punchlist Update:":

```markdown
**Architecture Baseline Update:** Dispatch a subagent to update the Structural Snapshot and compare Documented Intent:

```
Agent(prompt="Update the architecture baseline at docs/holtz/architecture-baseline.md.
Read the format spec at ${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/architecture-baseline-format.md.

1. STRUCTURAL SNAPSHOT: Re-infer the current module dependency graph from code (trace imports/requires across all significant modules). Update the Module Dependencies table, Entry Points list, and Export Surface. Only update what changed — do not rewrite unchanged sections.

2. DOCUMENTED INTENT: Read current project docs (CLAUDE.md, README, ARCHITECTURE.md if they exist). Compare against the Documented Intent section of the baseline. If documented rules changed, update Layering Rules, Boundaries, Conventions, and Invariants to match. Note any changes.

Do NOT modify the Drift Log — it was already updated during Phase 0 step 0a.1.

Write changes to docs/holtz/architecture-baseline.md. Report what sections changed and why.")
```

**After the subagent returns:** Proceed with Living Punchlist Update and Pattern Library Contribution. The baseline is now current for the living punchlist's architectural risk assessment (step 3).
```

- [ ] **Step 3: Verify the post-convergence flow is coherent**

The sequence should be:
1. Dispatch baseline update subagent (runs while Holtz reads pattern contribution protocol)
2. Pattern Library Contribution (Holtz — interactive, asks user permission)
3. Living Punchlist Update (Holtz — judgment-heavy, references updated baseline)
4. SUMMARY.md (Holtz — narrative)

The baseline subagent can run in parallel with step 2 (pattern contribution) since they don't share output files. By the time Holtz reaches step 3, the baseline is updated.

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): dispatch subagent for architecture baseline update post-convergence"
```

---

### Task 2: Update justine-skill.md post-convergence section

**Files:**
- Modify: `skills/holtz/references/justine-skill.md:308-322` (Post-Convergence section)

Justine does NOT update the architecture baseline or living punchlist (Holtz owns those). Justine's post-convergence is only: pattern contribution + SUMMARY.md. No changes needed — but verify.

- [ ] **Step 1: Read Justine's post-convergence section**

Read: `skills/holtz/references/justine-skill.md:308-322`
Confirm Justine does NOT reference architecture-baseline-format.md or living-punchlist-format.md.

- [ ] **Step 2: Verify — no changes needed**

Justine's post-convergence section should only reference `pattern-contribution-protocol.md` and SUMMARY.md. If it references baseline or living punchlist, add a note: "Justine does NOT update the architecture baseline or living punchlist — Holtz owns these documents."

- [ ] **Step 3: Commit (if changes were needed)**

```bash
git add skills/holtz/references/justine-skill.md
git commit -m "docs(skill): clarify Justine does not update baseline or living punchlist"
```

---

### Task 3: Add timing note for parallel execution

**Files:**
- Modify: `skills/holtz/SKILL.md` (Post-Convergence section)

- [ ] **Step 1: Add parallel execution note**

After the baseline subagent dispatch, add:

```markdown
**Timing:** The baseline subagent can run in the background while you handle Pattern Library Contribution (which requires user interaction). By the time you reach Living Punchlist Update, the baseline will be current.

```
Agent(run_in_background=true, prompt="Update the architecture baseline...")
```
```

Update the Agent call to include `run_in_background=true`.

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): run baseline update subagent in background during pattern contribution"
```

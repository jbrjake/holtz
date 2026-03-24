# Justine Recon Inheritance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow Justine to inherit Holtz's Phase 0 raw recon data (steps 0a-0f) when dispatched in parallel, eliminating ~5,000-7,000 tokens of duplicate data collection while preserving her independent summary and predictions.

**Architecture:** Add a two-mode Phase 0 to `justine-skill.md`: "solo mode" (standalone invocation, runs full recon) and "inherited mode" (dispatched by Holtz, reads his recon data). The mode is controlled by the dispatch prompt. Justine still writes her own recon summary (0g) and predictions (0h) with her different lens ordering and confidence calibration. Holtz's dispatch prompt is updated to signal inherited mode and point to his recon output.

**Tech Stack:** Markdown skill files only — no code changes, purely skill/prompt engineering.

---

### Task 1: Add Inherited Recon section to justine-skill.md

**Files:**
- Modify: `skills/holtz/references/justine-skill.md:157-169` (Phase 0 section)

Currently Justine's Phase 0 says "Follow the same recon procedure as Holtz" and lists Justine-specific overrides. We need to add an inherited mode that skips data collection.

- [ ] **Step 1: Read current Phase 0 section**

Read: `skills/holtz/references/justine-skill.md:155-170`
Note the current content and structure.

- [ ] **Step 2: Add inherited mode to Phase 0**

After the existing Phase 0 header and before the Justine-specific overrides, add:

```markdown
### Phase 0: Recon

**Two modes — determined by dispatch prompt:**

#### Inherited Recon Mode (default when dispatched by Holtz)

When dispatched by Holtz after his Phase 0 completes, his raw recon data is already on disk. Skip data collection and inherit his work:

1. **Create output directories:** `docs/holtz/justine/` and `docs/holtz/justine/recon/`
2. **Read Holtz's raw recon data:** Read `docs/holtz/recon/0a-project-overview.md` through `docs/holtz/recon/0f-skipped-tests.md`. Do NOT copy these files — read them for context, then write your own outputs.
3. **Read Holtz's recon summary:** Read `docs/holtz/recon/0g-recon-summary.md` for his synthesis.
4. **Read shared resources:** Read `docs/holtz/patterns-brief.md` (if it exists), `docs/holtz/architecture-baseline.md` (if it exists, read-only), and `docs/holtz/LIVING-PUNCHLIST.md` (if it exists, read-only).
5. **Run global pattern library scan:** Read pattern files at `${CLAUDE_PLUGIN_ROOT}/skills/holtz/patterns/*.md`, filter by detected language (from Holtz's 0a/0b), run detection heuristics. This step is NOT inherited — Justine runs her own heuristic checks because her lens ordering (integration-first) may prioritize different heuristic hits.
6. **Initialize impact graph:** Create `docs/holtz/justine/impact-graph.json` — reconcile against project structure per [impact-graph-operations.md](${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/impact-graph-operations.md) (Justine's Graph section).
7. **Write your own recon summary (0g):** Write `docs/holtz/justine/recon/0g-recon-summary.md` with YOUR synthesis — emphasize integration boundaries, cross-module contracts, and data-flow paths (your lens ordering). This may differ significantly from Holtz's summary.
8. **Write your own predictions (0h):** Write `docs/holtz/justine/recon/0h-predictions.md` using YOUR confidence calibration (aggressive: HIGH = one strong signal) and YOUR lens ordering (integration-first). These predictions will differ from Holtz's — that is the point.
9. **Recommendation escalation:** Scan `docs/holtz/archive/justine-*/SUMMARY.md` for recurring recommendations per [recommendation-escalation.md](${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/recommendation-escalation.md).
10. **Update STATUS.md** after each completed step.

**What is inherited:** Raw data collection (0a-0f) — project structure, test infra, test baseline, lint results, churn analysis, skipped tests. This data is objective and does not benefit from a second independent collection.

**What is NOT inherited:** Recon summary (0g), predictions (0h), pattern library scan, impact graph initialization, architecture drift detection, recommendation escalation. These involve judgment, perspective, and Justine's specific calibration.

#### Solo Recon Mode (standalone invocation)

When invoked standalone (not by Holtz), run the full Phase 0 procedure:
```

Then keep the existing content that follows (the Justine-specific overrides), indented under this section.

- [ ] **Step 3: Verify the updated skill reads coherently**

Read the full Phase 0 section end-to-end to confirm:
- Solo mode falls through to the existing procedure
- Inherited mode is clear about what's read vs what's written
- The Justine-specific overrides (aggressive confidence, mutation data override, temporal awareness, lens order, recommendation escalation) apply to BOTH modes

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/references/justine-skill.md
git commit -m "feat(skill): add inherited recon mode to Justine for parallel dispatch"
```

---

### Task 2: Update Holtz's dispatch prompt

**Files:**
- Modify: `skills/holtz/SKILL.md:141-149` (Dispatch Justine section)

The dispatch prompt needs to signal inherited mode and point Justine to Holtz's recon output.

- [ ] **Step 1: Read current dispatch section**

Read: `skills/holtz/SKILL.md:141-149`

- [ ] **Step 2: Update the dispatch prompt**

Replace the current Agent call with:

```markdown
### Dispatch Justine

After Phase 0 completes, dispatch Justine as a background subagent to run her own parallel audit. Use the Agent tool with the `justine` agent:

```
Agent(subagent_type="justine", run_in_background=true, prompt="Run a full audit on this codebase. You are being dispatched in parallel with Holtz.

INHERITED RECON: Holtz's Phase 0 recon data is at docs/holtz/recon/ (files 0a through 0f). Read these for context but write your own recon summary (0g) and predictions (0h) to docs/holtz/justine/recon/ with your own lens ordering and confidence calibration.

Write all output to docs/holtz/justine/ and use docs/holtz/justine/impact-graph.json for your impact graph. Leave docs/holtz/architecture-baseline.md and docs/holtz/LIVING-PUNCHLIST.md untouched. Run through convergence, then stop. Report completion by writing docs/holtz/justine/SUMMARY.md. Holtz handles the merge and fix loop. This is an autonomous execution context — choose the most conservative default for ambiguities and proceed. Report NEEDS_CONTEXT only if the task is genuinely impossible without human input.")
```

The key addition is the `INHERITED RECON:` block that signals inherited mode and tells Justine where to find Holtz's data.
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): update Justine dispatch prompt for inherited recon mode"
```

---

### Task 3: Add guard for missing recon data

**Files:**
- Modify: `skills/holtz/references/justine-skill.md` (inherited recon section)

If Holtz's recon data is missing or incomplete (dispatch happened before Phase 0 finished, or files were deleted), Justine should fall back to solo mode rather than proceeding with no data.

- [ ] **Step 1: Add guard to inherited recon mode**

In the inherited recon section, after step 2 ("Read Holtz's raw recon data"), add:

```markdown
   **Guard:** If `docs/holtz/recon/0g-recon-summary.md` does not exist, Holtz's recon is incomplete. Fall back to Solo Recon Mode — run the full Phase 0 procedure. Do not proceed with partial inheritance.
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/references/justine-skill.md
git commit -m "fix(skill): add fallback guard for missing recon data in inherited mode"
```

---

### Task 4: Update justine.md agent definition

**Files:**
- Modify: `agents/justine.md:29-37` (How you work section)

The agent definition's "How you work" section should mention inherited recon so the agent doesn't skip it when reading just the agent file (before reading the full skill).

- [ ] **Step 1: Update How you work section**

In `agents/justine.md`, update step 1:

```markdown
## How you work

1. Check for prior run state (`docs/holtz/justine/STATUS.md`). Resume if found.
2. **Phase 0 — two modes:** If dispatched by Holtz (dispatch prompt contains "INHERITED RECON"), read Holtz's raw recon data from `docs/holtz/recon/` and write your own summary and predictions. If standalone, run full Phase 0. Either way, write to `docs/holtz/justine/recon/`.
3. Phases are non-sequential. Jump from recon straight to whatever looks suspicious. Test predictions before you finish scanning.
```

- [ ] **Step 2: Commit**

```bash
git add agents/justine.md
git commit -m "docs(agents): update Justine agent definition for inherited recon"
```

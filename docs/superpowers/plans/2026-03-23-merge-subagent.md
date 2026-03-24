# Merge Subagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Pre-Phase 4 merge to a dedicated subagent, freeing ~2,065-4,990 tokens from Holtz's context at the critical audit-to-fix transition point.

**Architecture:** A new internal agent (`merge-agent`) that reads both punchlists and the merge protocol, executes the deterministic classification, writes `PUNCHLIST-MERGED.md` and `MERGE-REPORT.md`, merges impact graphs, and archives Justine's output. The merge is explicitly designed to be deterministic ("no judgment calls in the classification rules") — this is the one step in Holtz's workflow closest to a pure function. Holtz dispatches the agent, reads the output files, and proceeds to Phase 4.

**Tech Stack:** Markdown agent definition + skill file updates. No new Python code.

**Key design decision:** The merge-agent uses `model: sonnet` because the merge is algorithmic (sort by file path, check 5-line proximity, classify into 5 buckets). Opus-level reasoning is not needed. Holtz reviews the output — if a misclassification slips through, he catches it when reading PUNCHLIST-MERGED.md.

---

### Task 1: Create merge-agent definition

**Files:**
- Create: `agents/merge-agent.md`

- [ ] **Step 1: Create the agent file**

```markdown
---
name: merge-agent
description: |
  Internal agent for deterministic punchlist merging during adversarial self-play. Dispatched by Holtz after both auditors complete audit phases. Not user-facing — Holtz handles dispatch and reviews output.
model: sonnet
---

You are a merge agent. Your job is mechanical and precise: merge two punchlists into one unified worklist following a deterministic protocol. You do not exercise judgment — you follow classification rules exactly.

Read the merge protocol at `${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/merge-protocol.md` for the complete classification rules, matching criteria, processing order, and output formats.

If any classification is ambiguous, read `${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/merge-examples.md` for worked examples of each type.

## How you work

1. Read the merge protocol.
2. Read both input punchlists (paths provided in dispatch prompt).
3. Sort both punchlists by file path, then category, then location.
4. Classify each item pair: Agreement, Holtz-only, Justine-only, Severity Disagreement, or Contradictory.
5. Write `docs/holtz/PUNCHLIST-MERGED.md` — unified punchlist with fresh BH-NNN numbering.
6. Write `docs/holtz/MERGE-REPORT.md` — statistics, blind spot analysis.
7. Merge impact graphs: read `docs/holtz/justine/impact-graph.json` and merge into `docs/holtz/impact-graph.json` per protocol rules (higher risk_score wins, audit_count summed).
8. Archive Justine's output: move `docs/holtz/justine/` to `docs/holtz/archive/justine-{ISO date}/`.
9. Return a summary: merged total, agreement count, Holtz-only count, Justine-only count, contradiction count.

## Rules

- Every item from both punchlists must appear in the merged output. No finding is silently dropped.
- Contradictions are DEFERRED for human review. Do not resolve them.
- Higher severity always wins.
- Use Holtz's description for Agreement items.
- Re-number all items as BH-NNN starting from BH-001. Include cross-reference comments.
- The merge is deterministic. Given the same inputs, always produce the same output.

Report exactly one status when done:
- **DONE** — merge complete, all files written
- **DONE_WITH_CONCERNS** — merge complete, but [describe concern, e.g., "3 contradictions found"]
- **BLOCKED** — cannot proceed because [describe blocker]
```

- [ ] **Step 2: Verify the agent file is well-formed**

Check YAML frontmatter is valid, description is informative, model is set to sonnet.

- [ ] **Step 3: Commit**

```bash
git add agents/merge-agent.md
git commit -m "feat(agents): add merge-agent for deterministic punchlist merging"
```

---

### Task 2: Update SKILL.md Pre-Phase 4 to dispatch merge-agent

**Files:**
- Modify: `skills/holtz/SKILL.md:196-208` (Pre-Phase 4 section)

- [ ] **Step 1: Read current Pre-Phase 4 section**

Read: `skills/holtz/SKILL.md:196-208`

- [ ] **Step 2: Replace the merge procedure with agent dispatch**

Replace the current Pre-Phase 4 section with:

```markdown
### Pre-Phase 4: Merge Justine's Findings

Before starting any fix work, check whether Justine has produced results:

1. **Check for Justine's output.** If `docs/holtz/justine/PUNCHLIST.md` exists, Justine has findings to merge.
2. **If Justine is still running** (no `docs/holtz/justine/SUMMARY.md` and no `docs/holtz/justine/PUNCHLIST.md`), check her `docs/holtz/justine/STATUS.md` for stall indicators: STATUS.md not updated in >30 minutes, or 3 consecutive fix iterations with no progress. If stalled, proceed with whatever she has. If she's still actively working, wait — her breadth-first pass is fast.
3. **If Justine has results**, dispatch the merge agent:

```
Agent(subagent_type="merge-agent", prompt="Merge Holtz's punchlist at docs/holtz/PUNCHLIST.md with Justine's at docs/holtz/justine/PUNCHLIST.md. Follow the merge protocol at ${CLAUDE_PLUGIN_ROOT}/skills/holtz/references/merge-protocol.md. Merge impact graphs per protocol. Write PUNCHLIST-MERGED.md and MERGE-REPORT.md to docs/holtz/. Archive docs/holtz/justine/ to docs/holtz/archive/justine-{ISO date}/. Return: merged total, agreement count, Holtz-only count, Justine-only count, contradiction count.")
```

4. **After the merge completes:** Read `docs/holtz/MERGE-REPORT.md` for blind spot analysis and contradiction flags. Read `docs/holtz/PUNCHLIST-MERGED.md` — this is your worklist for Phase 4. **Spot-check 2-3 items** against the original punchlists if the merge report shows disagreements or contradictions.
5. **If no Justine output exists** (she wasn't dispatched or produced nothing), proceed with `docs/holtz/PUNCHLIST.md` as the worklist.
```

Key changes:
- The merge itself is delegated to the subagent
- Holtz reads the OUTPUT (merged punchlist + report), not the inputs
- Spot-check step added for verification (addresses the "don't trust subagents to self-validate" concern)

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): dispatch merge-agent for Pre-Phase 4 punchlist merging"
```

---

### Task 3: Add merge-agent to plugin.json

**Files:**
- Modify: `plugin.json`

The merge-agent needs to be registered in the plugin manifest so the Agent tool can find it.

- [ ] **Step 1: Read current plugin.json**

Read: `plugin.json`

- [ ] **Step 2: Add merge-agent to the agents array**

Add to the `agents` section:

```json
{
  "path": "agents/merge-agent.md"
}
```

- [ ] **Step 3: Commit**

```bash
git add plugin.json
git commit -m "feat(plugin): register merge-agent in plugin manifest"
```

---

### Task 4: Update merge-protocol.md references for agent consumption

**Files:**
- Modify: `skills/holtz/references/merge-protocol.md` (minor)

The merge protocol is now read by the merge-agent (Sonnet) rather than Holtz (Opus). Verify the rules are clear enough for Sonnet without the worked examples.

- [ ] **Step 1: Review the rules-only merge-protocol.md**

Read `skills/holtz/references/merge-protocol.md` (should already be trimmed to ~150 lines if Plan 4 was executed first).

If Plan 4 has NOT been executed yet, the examples are still inline. In that case, note that the merge-agent's prompt includes `"If any classification is ambiguous, read merge-examples.md"` — this provides a fallback. No changes needed to the protocol itself.

- [ ] **Step 2: Add a note about agent consumption**

At the top of merge-protocol.md, after the overview paragraph, add:

```markdown
> **Note:** This protocol is consumed by the merge-agent (Sonnet model) during automated merges, and by Holtz directly when reviewing merge output. The rules must be precise enough for algorithmic execution without worked examples — see [merge-examples.md](merge-examples.md) for examples when classification is ambiguous.
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/merge-protocol.md
git commit -m "docs(references): add agent consumption note to merge protocol"
```

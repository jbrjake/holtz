# Token Optimization Phase 2: Architectural Wins

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Holtz session token cost by an additional 20-35% through three medium-effort optimizations: write-then-forget discipline, subagent isolation for reference doc reads, and strategic compaction via session splitting.

**Architecture:** Skill instruction changes (Tasks 1-2) + new orchestration harness (Task 3). Tasks 1 and 2 are independent and can be done in any order. Task 3 depends on both being validated first.

**Prerequisite:** Phase 1 optimizations implemented and validated. Run the profiler after Phase 1 to establish the new baseline before implementing Phase 2.

**Tech Stack:** Markdown (skill edits), Python (session-splitting harness)

**Profiler data source:** `docs/runs/profiles/run-14/profile.json` (and post-Phase-1 profile for updated baselines)

**Expected combined savings:** 19-25M session-cost tokens (33-43% of Run 14's 57.7M main session cost). Note: savings compound — Phase 2 runs on top of Phase 1's reduced baseline.

---

## Task 1: Write-Then-Forget Discipline

**Files:**
- Modify: `skills/holtz/SKILL.md` (Context Survival Protocol section and Core Rules)

**Why:** Holtz's design philosophy is "write to disk immediately." But after writing an artifact, the model often restates its contents in the next assistant turn ("I've written the recon summary. It contains: [repeats everything]"). This restated content enters context permanently alongside the original tool results that produced it. The information is now triple-represented: raw tool output + artifact file + assistant summary.

Run 14 data: assistant overhead (text/thinking not attributable to tool results) accounts for 9.8% of total context growth — 33,980 tokens. The write-then-forget directive targets the subset of this that is redundant with on-disk artifacts.

**Estimated savings:** 1-2M session-cost tokens (2-4%). Conservative because not all overhead is redundant — some is necessary reasoning.

**Risk:** Low. The model may occasionally need information it didn't restate, but that information is on disk and re-readable. Holtz already has "re-read before every phase" in the Context Survival Protocol.

- [ ] **Step 1: Add write-then-forget rule to Core Rules**

In `skills/holtz/SKILL.md`, in the Core Rules section (after rule 7), add:

```markdown
8. **Write once, don't echo.** After writing an artifact to disk (recon file, punchlist item, status update), do not summarize or restate its contents in your next response. Reference the file path instead. The artifact IS the record. Restating it in assistant text causes the information to be cached twice — once as the Write result and once as your text — on every subsequent API call.
```

- [ ] **Step 2: Add to Rationalization Red Flags table**

Add a new row:

```markdown
| "Let me summarize what I just wrote..." | The file IS the summary. Restating it doubles the context cost. Reference the path. |
```

- [ ] **Step 3: Add to Context Survival Protocol**

After the "One step, one file" bullet, add:

```markdown
- **Don't echo artifacts.** After writing to disk, say only: "Written to `<path>`." Do not restate contents. If you need to reference the contents later, re-read the file — it's cheaper than carrying the summary in context for 200+ turns.
```

- [ ] **Step 4: Verify integration**

Read the full SKILL.md top-to-bottom and confirm the new rules are consistent with existing ones. The existing rule 6 ("Write to disk first, think later") supports this — rule 8 extends it to say "and don't repeat yourself after writing."

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "perf(skill): add write-then-forget discipline to reduce context echo

After writing artifacts to disk, don't restate contents in assistant text.
This eliminates double-caching of the same information (raw tool output +
echoed summary). Estimated savings: 1-2M session-cost tokens (2-4%)."
```

---

## Task 2: Subagent Isolation for Reference Doc Reads

**Files:**
- Modify: `skills/holtz/SKILL.md` (Phase 0 section and References section)
- Modify: `skills/holtz/references/phase-0-recon.md`

**Why:** Holtz reads 10+ reference docs during recon. These docs add 15,519 tokens to the main context at high `remaining` multipliers, costing 3.5M session-cost tokens. But the docs are consumed once to make decisions, then never re-accessed — the decisions are captured in recon artifacts.

Six of these docs are "read-once, consume, and discard" — their content is not cross-referenced in later phases:
- `references/recommendation-escalation.md` (2,046 chars, 1.55M cost)
- `references/punchlist-format.md` (5,102 chars, 231K cost)
- `references/status-file-format.md` (3,592 chars, 9K cost)
- `references/investigation-format.md` (not read in Run 14)
- `references/architecture-baseline-format.md` (not read in Run 14)
- `references/phase-0-recon.md` (9,074 chars, 22K cost — read early but low remaining by the time it matters)

Four docs MUST stay in main context because they're cross-referenced during later phases:
- `references/anti-patterns.md` — used during Phase 2 test audit
- `references/lens-registry.md` — used for lens selection throughout
- `references/merge-protocol.md` — used during merge phase
- `references/impact-graph-operations.md` — used throughout for graph commands

**Technique:** Dispatch a "reference reader" subagent at the start of recon that reads the consumable docs, extracts the key information, and returns a structured brief. The full doc content stays in the subagent's isolated context. The main session receives only the brief.

**Estimated savings:** ~3.4M session-cost tokens (6%). The subagent itself costs ~31K tokens (doc content in its short session), so net savings are ~3.37M.

**Risk:** Medium. If the brief misses a critical detail, the main session would need to re-read the original doc. Mitigation: the brief includes a "for full protocol, read `<path>`" escape hatch.

- [ ] **Step 1: Create the reference reader subagent prompt**

In `skills/holtz/SKILL.md`, Phase 0 section, after the existing "Phase 0 summary" paragraph, add a new subsection:

```markdown
#### Reference Reader Subagent

Before starting recon steps, dispatch a reference reader subagent to pre-digest consumable reference docs. This keeps full doc content out of the main context.

```
Agent(subagent_type="general-purpose", model="sonnet", prompt="
Read the following reference docs and return a structured brief for each.
Return ONLY the brief — do not include the full doc text.

For each doc, extract:
1. The key rules/requirements (numbered list, 1-2 sentences each)
2. Any format templates or required fields
3. Any decision criteria or thresholds

Docs to read:
- skills/holtz/references/recommendation-escalation.md
- skills/holtz/references/punchlist-format.md
- skills/holtz/references/status-file-format.md
- skills/holtz/references/phase-0-recon.md
- skills/holtz/references/architecture-baseline-format.md
- skills/holtz/references/living-punchlist-format.md

Format your response as:
## <doc-name>
<extracted brief>
(Full protocol: `<path>` — re-read only if the brief is insufficient.)
")
```

Use the returned brief as your working reference for Phase 0. Do NOT read the full docs in the main session unless the brief is insufficient for a specific decision.

**Keep in main context** (do NOT move to the reader subagent):
- `references/anti-patterns.md` — cross-referenced during Phase 2
- `references/lens-registry.md` — cross-referenced throughout
- `references/merge-protocol.md` — cross-referenced during merge
- `references/impact-graph-operations.md` — cross-referenced throughout for graph CLI commands
```

- [ ] **Step 2: Update the References section**

In the References section at the top of SKILL.md (~line 30), annotate which docs are "main context" vs "subagent digested":

```markdown
## References

**Main context** (read directly when needed — cross-referenced across phases):
- [references/anti-patterns.md](references/anti-patterns.md) — test quality detection
- [references/lens-registry.md](references/lens-registry.md) — analytical lens definitions
- [references/merge-protocol.md](references/merge-protocol.md) — merge protocol for adversarial self-play
- [references/impact-graph-operations.md](references/impact-graph-operations.md) — knowledge graph CLI

**Subagent-digested** (consumed via reference reader subagent during Phase 0):
- [references/punchlist-format.md](references/punchlist-format.md) — punchlist format
- [references/status-file-format.md](references/status-file-format.md) — STATUS.md format
- [references/recommendation-escalation.md](references/recommendation-escalation.md) — escalation protocol
- [references/phase-0-recon.md](references/phase-0-recon.md) — Phase 0 procedure
- [references/architecture-baseline-format.md](references/architecture-baseline-format.md) — baseline format
- [references/living-punchlist-format.md](references/living-punchlist-format.md) — living punchlist format

**Always in main context** (not reference docs):
- [examples/sample-punchlist.md](examples/sample-punchlist.md) — example punchlist
- Scripts: `validate_punchlist.py`, `convergence_check.py`, `impact_graph.py`, `pattern_brief_compact.py`
- `patterns/*.md` — global pattern library
```

- [ ] **Step 3: Update Phase 0 recon reference doc**

Read `skills/holtz/references/phase-0-recon.md`. At the top, add:

```markdown
> **Note:** This document is consumed via the reference reader subagent during Phase 0. The main session receives a structured brief, not the full text. If the brief is insufficient for a specific step, re-read this document directly.
```

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/SKILL.md skills/holtz/references/phase-0-recon.md
git commit -m "perf(skill): isolate consumable reference doc reads to subagent

Six reference docs are read-once during recon and never cross-referenced later.
Moving them to a Sonnet subagent keeps 15K tokens out of main context.
Estimated savings: 3.4M session-cost tokens (6%).

Cross-referenced docs (anti-patterns, lens-registry, merge-protocol,
impact-graph-operations) remain in main context."
```

---

## Task 3: Strategic Compaction via Session Splitting

**Files:**
- Create: `scripts/holtz_split_session.sh` (orchestration harness)
- Modify: `skills/holtz/SKILL.md` (add session split guidance)

**Why:** After Phase 0 completes, context is at ~103K tokens and all recon data is persisted to disk. The remaining 203 turns carry this 103K of accumulated recon context as dead weight — it's re-cached on every subsequent API call but never re-accessed (the model reads from disk artifacts). If context were reset at this boundary, post-recon turns would use `remaining` values from ~200 instead of ~276, cutting the multiplier by ~73 for every subsequent turn.

**Estimated savings:** 15-20M session-cost tokens (26-35%). This is the single highest-leverage optimization.

**How it works:** After Phase 0 + Justine dispatch, exit the session. Start a fresh session that reads only the artifact paths needed for Phases 1-4. The fresh session has a clean ~32K context (system prompt only) instead of ~103K.

**Risk:** Medium. The fresh session loses any implicit context the model built during recon — observations, hunches, mental models. Mitigation: Holtz already writes predictions (0h) and a recon summary (0g) that capture the synthesized understanding. The fresh session reads these.

**Complication:** Justine was dispatched as a background subagent from the first session. Her results arrive asynchronously. The second session needs to wait for or check for Justine's completion. Mitigation: Justine writes `docs/holtz/justine/SUMMARY.md` when done. The second session polls for this file before entering the merge phase.

- [ ] **Step 1: Create the session-splitting harness**

Create `scripts/holtz_split_session.sh`:

```bash
#!/usr/bin/env bash
# holtz_split_session.sh — Run Holtz in two sessions for token efficiency.
#
# Session 1: Phase 0 (recon) + Justine dispatch
# Session 2: Phases 1-4 (audit, merge, fix loop, convergence)
#
# The split point is after Phase 0 completes and all recon artifacts are on disk.
# This resets the context window from ~103K back to ~32K, eliminating the
# accumulated recon context from being re-cached on every subsequent API call.
#
# Usage:
#   ./scripts/holtz_split_session.sh [project-path]
#
# Prerequisites:
#   - Claude Code CLI (claude) on PATH
#   - Holtz skill installed

set -euo pipefail

PROJECT="${1:-.}"
cd "$PROJECT"

echo "=== Holtz Split-Session Audit ==="
echo "Phase 1/2: Recon + Justine dispatch"
echo ""

# Session 1: Recon
claude --print "Run Holtz Phase 0 only on this codebase. Complete all recon steps (0a-0h), write all artifacts to docs/holtz/recon/, initialize/reconcile the impact graph, write STATUS.md and PUNCHLIST.md with any escalated items, and dispatch Justine as a background subagent. After dispatching Justine and verifying all Phase 0 artifacts exist on disk, STOP. Do not proceed to Phase 1. Report: 'Phase 0 complete. Justine dispatched. Ready for session split.'"

echo ""
echo "Phase 0 complete. Starting fresh session for Phases 1-4."
echo ""

# Verify Phase 0 artifacts exist
for f in docs/holtz/recon/0g-recon-summary.md docs/holtz/recon/0h-predictions.md docs/holtz/STATUS.md docs/holtz/impact-graph.json; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Missing artifact: $f"
        echo "Phase 0 may not have completed. Check docs/holtz/STATUS.md."
        exit 1
    fi
done

echo "All Phase 0 artifacts verified."
echo ""

# Session 2: Audit phases
# Wait for Justine if needed (she runs ~15 min, recon takes ~20 min, so she may already be done)
claude --print "Resume Holtz from Phase 1. This is a FRESH SESSION after a deliberate context split for token efficiency.

READ THESE FILES FIRST to recover state:
1. docs/holtz/STATUS.md (your program counter)
2. docs/holtz/recon/0g-recon-summary.md (recon synthesis)
3. docs/holtz/recon/0h-predictions.md (predictions to test)
4. docs/holtz/PUNCHLIST.md (any escalated items from recon)

Phase 0 (recon) is COMPLETE. Justine has been dispatched and may still be running.

Proceed through: Phase 1 (doc audit) -> Phase 2 (test audit) -> Phase 3 (adversarial audit) -> check for Justine results at docs/holtz/justine/SUMMARY.md -> merge if available -> Phase 4 (fix loop) -> convergence.

If Justine's SUMMARY.md does not exist when you reach the merge point, note it in STATUS.md and proceed with Holtz-only findings. The merge can be done in a follow-up if Justine is still running."

echo ""
echo "=== Holtz Split-Session Audit Complete ==="
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/holtz_split_session.sh
```

- [ ] **Step 3: Add session split guidance to SKILL.md**

In `skills/holtz/SKILL.md`, after the Context Survival Protocol section, add:

```markdown
## Session Splitting (Optional, for Token Efficiency)

For maximum token efficiency, Holtz can be run in two sessions with a context reset between Phase 0 and Phase 1. This is orchestrated by `scripts/holtz_split_session.sh`.

**Why:** After Phase 0, context is ~103K tokens. All recon data is on disk. The remaining ~200 turns re-cache this 103K on every API call, costing ~15-20M session-cost tokens of dead weight. Splitting resets context to ~32K.

**How:** Session 1 runs Phase 0 + dispatches Justine. Session 2 reads the recon artifacts from disk and runs Phases 1-4 with a clean context. Justine runs independently across both sessions.

**When NOT to split:** If the codebase is small (<100 files) and the audit will be short (<100 turns), the overhead of session splitting exceeds the savings. Split only when the total session is expected to exceed 200 turns.
```

- [ ] **Step 4: Test the harness on a small codebase**

Run the harness on a small project to verify:
1. Session 1 completes Phase 0 and stops
2. Artifact verification passes
3. Session 2 picks up from Phase 1 correctly
4. Justine's results are found (or gracefully skipped)

- [ ] **Step 5: Profile both sessions and compare**

```bash
# Profile session 1 (recon)
python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py -o token-profile-split-s1/

# Profile session 2 (audit)
python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py -o token-profile-split-s2/

# Compare total session cost of split sessions vs a single-session baseline
```

- [ ] **Step 6: Commit**

```bash
git add scripts/holtz_split_session.sh skills/holtz/SKILL.md
git commit -m "perf: add session-splitting harness for Holtz token efficiency

Splits Holtz into two sessions at the Phase 0/Phase 1 boundary.
Session 1: recon + Justine dispatch (~103K context).
Session 2: audit + fix loop (fresh ~32K context).
Estimated savings: 15-20M session-cost tokens (26-35%).

The harness verifies Phase 0 artifacts before starting Session 2
and handles Justine's async completion gracefully."
```

---

## Validation

After implementing all three tasks, run Holtz (using the split harness for Task 3) and profile:

```bash
# Run with split session
./scripts/holtz_split_session.sh .

# Profile both sessions
python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py -o token-profile-post-phase2/

# Key metrics to compare against Run 14 baseline:
# 1. Total session cost across both sessions — target: <40M (down from 57.7M)
# 2. Session 2 Q1 cost — should be dramatically lower (clean context)
# 3. Assistant overhead % — should decrease (write-then-forget)
# 4. Reference doc tokens in main context — should be near zero for consumable docs
```

**Success criteria:**
- Combined session cost <40M (30%+ reduction from Run 14's 57.7M)
- Session 2 starts with context <35K (vs Run 14's 103K at Phase 1 start)
- No regression in audit quality (same or more findings)
- Justine completion handled gracefully (found or noted as pending)

**Rollback:** If quality degrades:
- Task 1 (write-then-forget): Remove rule 8 from SKILL.md, remove Rationalization Red Flag row
- Task 2 (subagent reference reader): Remove the subagent dispatch block, revert References section annotations
- Task 3 (session split): Stop using the harness, run as a single session

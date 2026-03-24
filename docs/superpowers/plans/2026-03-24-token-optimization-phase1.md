# Token Optimization Phase 1: Immediate Wins

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Holtz session token cost by ~12% through three low-risk, low-effort optimizations: tool call batching, Tool Search threshold tuning, and model routing for subagents.

**Architecture:** Skill instruction edits + environment configuration. No code changes to the profiler or analysis pipeline. Changes are to the Holtz skill (`skills/holtz/SKILL.md`), reference docs, and project settings.

**Tech Stack:** Markdown (skill edits), JSON (settings)

**Spec:** `docs/superpowers/specs/2026-03-24-token-profiler-design.md` (Optimization Patterns section)

**Profiler data source:** `docs/runs/profiles/run-14/profile.json`

**Expected combined savings:** ~6.7M session-cost tokens (12% of Run 14's 57.7M main session cost) + $1.70/run from model routing.

**Validation:** Run Holtz on any codebase after these changes. Profile the session. Compare Q1 cost percentage and total session cost against Run 14 baselines.

---

## Task 1: Tool Call Batching Directives

**Files:**
- Modify: `skills/holtz/SKILL.md` (Context Survival Protocol section, ~line 81)
- Modify: `skills/holtz/references/phase-0-recon.md` (recon step instructions)

**Why:** Run 14 has 201 single-tool turns out of 276 total. Each single-tool turn adds a full round-trip to context (assistant reasoning + tool call + result). Consecutive independent operations should be batched into parallel tool calls within a single turn. This eliminates narration overhead between calls (~350 tokens/turn × ~100 eliminable turns × avg 138 remaining = 4.8M session-cost savings).

**What the data shows:** Turns 14-17 in recon run 4 sequential single-tool Bash calls (file listing, line counts, pytest, git churn). These are completely independent and could be 1 batched turn. Turns 18 runs 6 pattern heuristics — already batched. The recon phase has the most batching opportunities because it runs many independent checks.

- [ ] **Step 1: Add batching directive to Context Survival Protocol**

In `skills/holtz/SKILL.md`, after the existing "Subagents for heavy scanning" bullet in the Context Survival Protocol section (~line 86), add:

```markdown
- **Batch independent tool calls.** When multiple checks are independent (no data dependency between them), execute them as parallel tool calls in a single turn. Do not narrate between independent operations. Each eliminated turn saves its narration text from being cached on every subsequent API call.
- **Terse within phases.** Between tool calls within a phase, do not explain what you are about to do. Execute, then report findings. Save narrative for phase boundaries and significant discoveries. Every sentence of narration enters context permanently.
```

- [ ] **Step 2: Verify the edit reads naturally in context**

Read the full Context Survival Protocol section and confirm the new bullets integrate cleanly with the existing ones.

- [ ] **Step 3: Add batching guidance to Phase 0 recon reference**

Read `skills/holtz/references/phase-0-recon.md`. Find the section that describes recon steps 0a-0f. Add a note at the top of the Phase 0 procedure:

```markdown
**Batching:** Steps 0a-0f involve many independent checks (line counts, test run, lint, churn, skipped tests). Execute independent checks as parallel tool calls in a single turn. For example: run pytest, ruff, and mypy in one batched turn rather than three sequential turns. The pattern heuristic greps (step 0e) are already independent and should be a single batched call.
```

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/SKILL.md skills/holtz/references/phase-0-recon.md
git commit -m "perf(skill): add tool call batching and terse narration directives

Estimated savings: 4.8M session-cost tokens (8%) based on Run 14 profile.
201 of 276 turns were single-tool; batching independent operations eliminates
~100 round-trips of narration overhead from context accumulation."
```

---

## Task 2: Tool Search Threshold Configuration

**Files:**
- Modify: `.claude/settings.local.json`

**Why:** Run 14's ToolSearch at turn 10 loaded TaskCreate/TaskUpdate tool definitions for 7,302 tokens at remaining=266, costing 1.94M session-cost tokens. The `ENABLE_TOOL_SEARCH=auto:5` environment variable makes Claude Code defer MCP tool definition loading until tool definitions exceed 5% of context. This delays loading of tool definitions that aren't immediately needed, reducing the early-session cache burden.

- [ ] **Step 1: Check current settings**

Read `.claude/settings.local.json` to understand current configuration.

- [ ] **Step 2: Add env configuration**

Add the environment variable to the project settings. In `.claude/settings.local.json`, add an `env` key if not present:

```json
{
  "permissions": { ... },
  "env": {
    "ENABLE_TOOL_SEARCH": "auto:5"
  }
}
```

If `.claude/settings.local.json` doesn't support `env`, create or update the user-level settings at `~/.claude/settings.json` instead. Alternatively, add the export to a project-level `.envrc` or document it in the CLAUDE.md.

Note: If settings.json doesn't support `env` natively, the alternative is to document this as a shell export the user should set:

```bash
export ENABLE_TOOL_SEARCH=auto:5
```

Add this to the project's CLAUDE.md or a setup script.

- [ ] **Step 3: Verify Tool Search behavior**

Start a new Claude Code session. Check `/context` output to see if tool definitions are deferred vs preloaded. Verify that tools are still available when called (they load on-demand).

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json  # or wherever the config landed
git commit -m "perf: set ENABLE_TOOL_SEARCH=auto:5 for deferred tool loading

Tool definitions consumed 7,302 tokens at turn 10 in Run 14, costing 1.94M
session-cost tokens. Deferring loading until 5% threshold reduces early-session
cache burden."
```

---

## Task 3: Model Routing for Audit Subagents

**Files:**
- Modify: `skills/holtz/SKILL.md` (Phase 2 and Phase 3 subagent dispatch sections)

**Why:** Run 14 dispatched 5 subagents, all on Opus. The Phase 2 test-audit subagent (8 turns, 526K billed tokens) and Phase 3 source-audit subagent (16 turns, 899K billed tokens) did mechanical scanning — reading files, checking anti-patterns against a rubric. The real bugs were found by Holtz's main context, not the subagents. Sonnet handles mechanical scanning tasks at 5× lower input pricing ($3 vs $15/MTok). Justine stays on Opus because her independent synthesis requires full reasoning capability.

**Dollar savings:** 1.42M tokens × ($15 - $3)/MTok = $1.70/run for the two audit subagents.

- [ ] **Step 1: Read current Phase 2 subagent dispatch**

Read `skills/holtz/SKILL.md` Phase 2 section (~line 176-187). Find where subagents are mentioned for test file audit batches.

- [ ] **Step 2: Add model routing guidance to Phase 2**

In the Phase 2 section, after the subagent brief instructions, add:

```markdown
**Model routing:** Dispatch test audit subagents with `model: "sonnet"`. Test quality auditing against a rubric is mechanical pattern-matching work that Sonnet handles well at 5x lower cost. Reserve Opus for the main session where architectural reasoning and cross-referencing happen.
```

- [ ] **Step 3: Add model routing guidance to Phase 3**

In the Phase 3 section (~line 189-198), add the same guidance:

```markdown
**Model routing:** Dispatch source module audit subagents with `model: "sonnet"`. File-level code review against known patterns is a Sonnet-grade task. The main session's adversarial reasoning (testing predictions, confirming bugs) stays on Opus.
```

- [ ] **Step 4: Confirm Justine dispatch remains on Opus**

Read the Justine dispatch section (~line 142-154). Verify it does NOT specify `model: "sonnet"`. Justine's independent synthesis, prediction generation, and adversarial analysis require Opus-level reasoning. Add a comment if not already clear:

```markdown
<!-- Justine stays on Opus — her independent synthesis and prediction require full reasoning capability. Do not downgrade. -->
```

- [ ] **Step 5: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "perf(skill): route Phase 2/3 audit subagents to Sonnet

Mechanical pattern-matching subagents (test audit, source audit) use Sonnet
at 5x lower input pricing. Justine and main session stay on Opus.
Estimated savings: $1.70/run based on Run 14 subagent token volumes."
```

---

## Validation

After implementing all three tasks, run Holtz on any codebase and profile the result:

```bash
# Run Holtz
# (normal invocation)

# Profile the session
python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py -o token-profile-post-phase1/

# Compare against Run 14 baseline
# Key metrics to check:
# 1. Total session cost — should be lower
# 2. Q1 cost percentage — should decrease (fewer early single-tool turns)
# 3. ToolSearch overhead — should be lower or zero in early turns
# 4. Subagent dollar cost — should be lower (Sonnet pricing)
# 5. Single-tool turn count — should decrease (more batched turns)
```

**Success criteria:**
- Total session cost <52M (down from 57.7M = ~10% reduction)
- OR subagent dollar cost reduced by >$1.00
- AND no regression in audit quality (same or more findings, same prediction accuracy)

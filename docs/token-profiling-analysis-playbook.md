# Token Profiling Analysis Playbook

> **What this is:** A repeatable process for analyzing the token cost profile of any Claude Code session, identifying optimization opportunities, and making actionable recommendations. This playbook assumes the `token_profiler` script exists as a durable artifact and focuses on the *analytical methodology* — how to read the output, what to look for, and how to reason about tradeoffs.
>
> **Who this is for:** Anyone who wants to reduce the token cost of a Claude Code workflow — whether it's a Holtz audit, a coding session, or any agentic tool that runs long.

---

## Step 1: Generate the Profile

```bash
# Basic — profile most recent session for current project
python -m token_profiler --latest -o token-profile/ --open

# With Holtz plugin (adds phase detection, subagent naming)
python -m token_profiler --latest --plugin skills/holtz/scripts/profiler_plugin.py -o token-profile/ --open

# Cross-project
python -m token_profiler --latest --project ~/repos/other-project -o token-profile/ --open

# Specific session
python -m token_profiler ~/.claude/projects/-Users-foo-my-project/SESSION_ID.jsonl -o token-profile/
```

Outputs: `profile.json` (canonical data), `profile.md` (markdown report), `profile.html` (cyberpunk viewer).

---

## Step 2: Read the Summary — Establish Baselines

Open `profile.md` or the HTML viewer. Read the Summary table first.

**Key numbers to anchor on:**

| Metric | What it tells you |
|--------|-------------------|
| Total API calls | Session length — more calls = higher cost multiplier for early content |
| Total billed tokens | Raw API spend — the billing meter |
| Total session cost (heat) | The profiler's primary metric: `sum(delta × remaining)` across all turns |
| Total dollars | Actual spend at model pricing |
| Per-session breakdown | Where subagents fit in — are they a rounding error or a significant cost center? |

**Baselines from Run 14 (Holtz full audit):**
- 276 main calls + 92 subagent calls = 368 total
- 57.8M session-cost tokens in main session
- 87% of billed tokens in main, 11% in Justine, 2% in smaller subagents

If your numbers are wildly different from these baselines, understand why before proceeding. A 50-call session has very different optimization levers than a 276-call session.

---

## Step 3: Quartile Analysis — Where is the Cost?

The single most important structural insight: **session cost is front-loaded.** In Run 14:

| Quartile | % of Session Cost |
|----------|------------------|
| Q1 (first 25% of turns) | 63% |
| Q2 | 18% |
| Q3 | 15% |
| Q4 (last 25%) | 5% |

This is the fundamental shape of the `delta × remaining` formula. Early turns have high `remaining` multipliers. A token added at turn 10 of a 276-turn session has 267× the per-turn impact of a token added at turn 270.

**What to look for:** If Q1 is >50% of session cost, the biggest optimization opportunities are in what happens early — system prompt, initial reads, tool loading, recon. If the cost is more evenly distributed, the problem is more likely chatty tool loops or large tool results throughout.

**How to compute:** Sort turns by index, split into quartiles, sum `session_cost_tokens` per quartile. The profiler's JSON has all the data; the viewer's heat strip visualizes it (bright bars on the left = front-loaded cost).

---

## Step 4: Attribution Analysis — Tools vs Overhead

**Compute the tool-vs-overhead split:**

| Category | Run 14 Baseline |
|----------|----------------|
| Tool results (measurable content) | 90.2% of delta |
| Assistant overhead (text, thinking, system) | 9.8% of delta |

Tool results are the dominant context growth driver. The assistant's own text is a smaller but non-trivial tax — every time the model says "Let me check this" before calling a tool, that narration enters context permanently.

**What to look for:**
- If overhead >15%, the model is too verbose. Skill instructions should add terse-mode directives.
- If overhead is low but cost is still high, the problem is tool result sizes or tool call count.
- Look for turns where overhead is 80-100% of delta with delta >500 — these are turns where the model is adding significant reasoning text without useful tool results. Turn 10 in Run 14 is the classic example: ToolSearch added 7,302 tokens of tool definitions, all attributed to overhead because ToolSearch results aren't measurable from JSONL.

---

## Step 5: Tool Type Ranking — What's Expensive?

Read the "Heat Map — Top 20 Hottest Tools" table. This is aggregated across all turns.

**Run 14 baselines:**

| Tool | % of Session Cost | Avg Cost/Call |
|------|------------------|---------------|
| Bash | 60.4% | 201K |
| Read | 17.1% | 175K |
| Write | 7.0% | 151K |
| Edit | 5.7% | 46K |
| Grep | 4.0% | 119K |
| Agent | 1.7% | 212K |

**What to look for:**
- **Bash dominance** is normal for audit/recon workflows. Bash results are small but frequent and early. The cost-per-call is high because of the `remaining` multiplier, not result size.
- **Read with high cost-per-call** means large files being read early. Check the Top 20 Hottest Turns for which specific files.
- **Agent with high cost-per-call** is expected — subagent dispatch prompts are large and return large results. But if Agent is >5% of session cost, consider whether those subagents could use cheaper models.
- **ToolSearch at 0 attributed cost** is misleading — it adds tool definitions to context, but the JSONL can't measure this. The cost shows up as `_assistant_overhead`. If you see a high-overhead turn that coincides with ToolSearch, that's the real cost.

---

## Step 6: Phase Breakdown — Which Phase Costs Most?

For Holtz sessions (or any workflow with a plugin that provides phase labels):

**Run 14 baselines:**

| Phase | Turns | Session Cost | % |
|-------|-------|-------------|---|
| recon | 63 | 22.3M | 39% |
| convergence | 53 | 7.2M | 13% |
| fix-loop | 45 | 4.4M | 8% |
| phase-2 | 67 | 4.1M | 7% |
| merge | 19 | 4.1M | 7% |
| phase-1 | 11 | 3.6M | 6% |
| phase-3 | 17 | 3.2M | 6% |

**What to look for:**
- Recon should be the costliest phase in a Holtz audit (it's the earliest and longest). If another phase exceeds it, something unusual happened.
- Phases with few turns but high cost indicate large context additions per turn (e.g., merge reads Justine's full output).
- The system prompt cost (turn 0, phase "unknown") is its own category — 15.2% in Run 14.

---

## Step 7: Deep Dive — Hottest Individual Turns

Read the "Heat Map — Top 20 Hottest Turns" with their tool attribution sub-rows. For each hot turn, answer:

1. **What entered context?** — which tool results, how large?
2. **Was it necessary at that point?** — could this have been deferred to a later turn (lower remaining)?
3. **Is the content still needed later?** — or was it consumed once and never revisited?
4. **Could it have been done in a subagent?** — subagent context is isolated from main.

**Pattern recognition from the deep dive:**

| Pattern | Signature | Optimization |
|---------|-----------|-------------|
| Heavy Early Read | Large file read in Q1 with high remaining | Defer, summarize, or subagent-isolate |
| Tool Definition Loading | ToolSearch turn with 100% overhead, large delta | Defer tool loading, use `ENABLE_TOOL_SEARCH=auto:5` |
| Chatty Single-Tool Turns | Many consecutive turns with 1 tool each | Batch parallel calls in skill instructions |
| Consumed-but-Cached Results | Large tool result that was written to disk immediately after | Candidate for stale result clearing (when available) |
| Reference Doc in Main Context | Read of a reference/methodology doc early in session | Subagent reader returns summary, full doc stays isolated |
| Narration Tax | Turns where assistant text is 80%+ of delta | Terse-mode directives in skill |

---

## Step 8: Scenario Modeling — Quantify the Opportunities

For each identified optimization, estimate the savings:

```
savings = sum(attributed_session_cost for affected tool calls)
```

For structural changes (compaction, session splitting):
```
# If compaction at turn X:
pre_X_cost = sum(session_cost for turns before X)
post_X_turns = total_turns - X
# Post-compaction cost uses remaining from post_X_turns, not total_turns
estimated_new_cost = sum(delta[i] * (post_X_turns - i) for i in range(post_X_turns))
savings = pre_X_cost - estimated_new_cost
```

**Build a ranked portfolio:**

| Optimization | Estimated Savings | Complexity | Risk |
|-------------|------------------|-----------|------|
| ... | ... | Low/Med/High | Low/Med/High |

Sort by savings/complexity ratio. Implement high-savings/low-complexity first.

---

## Step 9: Tradeoff Resolution

For each optimization, resolve the tradeoff explicitly. Don't leave open questions.

**Framework:**

1. **What information is lost?** If a tool result is summarized or cleared, what can't the model do anymore?
2. **Is the information recoverable?** Can it be re-fetched from disk, re-computed, or re-read?
3. **How often is it actually re-accessed?** Check the session — does any later turn reference this content?
4. **What's the failure mode?** If the optimization goes wrong, what breaks? Is it recoverable?

**Decision rules:**
- If content is written to disk AND never re-accessed in context: safe to clear/summarize.
- If content is cross-referenced in later phases: keep in context or ensure the reference is available.
- If the optimization requires architectural changes: worth it only if savings >5% of session cost.
- If the optimization is a config/env change: do it regardless of savings magnitude (zero risk).

---

## Step 10: Write Recommendations

Structure recommendations in two tiers:

**Tier 1 — Implement Now:** Low-risk, low-effort, immediate payoff. Config changes, skill instruction edits, env vars.

**Tier 2 — Implement Next:** Medium-effort, requires validation. Architectural changes to tool usage patterns, subagent delegation changes, session structure changes.

For each recommendation, include:
- **What to change** (specific file, line, config)
- **Expected savings** (session-cost tokens and/or dollars)
- **How to validate** (run the profiler on the next session, compare)
- **Rollback plan** (how to undo if it doesn't work)

---

## Step 11: Validate After Implementation

After implementing optimizations, run the profiler on the next session and compare:

```bash
# Profile the new session
python -m token_profiler --latest -o token-profile-after/

# Compare key metrics
# - Did total session cost decrease?
# - Did Q1 percentage decrease? (if targeting early-session optimizations)
# - Did the targeted tool/phase costs decrease?
# - Did any other costs increase unexpectedly? (waterbed effect)
```

Track optimization effectiveness over time. The profiler's JSON output is diff-friendly — you can build a simple comparison script that reads two `profile.json` files and reports the delta in each metric.

---

## Appendix: Cost Model Reference

```
session_cost = delta × remaining_calls_in_segment  (inclusive, min 1)
context_window = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
delta = context_window[N] - context_window[N-1]
remaining = (last_turn_in_segment - current_turn) + 1
```

**Anthropic API pricing (Opus 4.6, as of March 2026):**

| Bucket | $/MTok | Relative |
|--------|--------|----------|
| Input | $15.00 | 1× |
| Cache creation | $18.75 | 1.25× |
| Cache read | $1.50 | 0.1× |
| Output | $75.00 | 5× |

Cache reads dominate billing in long sessions. In Run 14: 57.3M cache_read tokens vs 348K cache_creation. The same content is re-read ~165× on average.

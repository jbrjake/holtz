# Token & Context Optimization Designs

**Date:** 2026-03-23
**Status:** Initial designs — each has a separate implementation plan

**Goal:** Reduce total token usage across a full adversarial self-play run and reduce context pressure on the main Holtz agent, especially during Phase 6 convergence which scales linearly with lens count (currently 6, growing to 9-10+).

**Estimation baseline:** A full adversarial self-play run uses ~180,000-311,000 tokens across Holtz (~95,000-161,000), Justine (~65,000-110,000), and Phase 2/3 subagents (~20,000-40,000).

---

## Token Usage Reductions

### Design 1: Filtered Punchlist Reads with Recency Window

**Category:** Context on main agent (also reduces total tokens)
**Priority:** Highest — scales with lens count

**Problem:** Phases 4, 5, and 6 re-read the full punchlist every iteration. With 10 lenses and 20-35 convergence iterations, each re-reading a 12+ item punchlist (360+ lines), resolved items dominate the reads without contributing to fix work.

**Design:** Add `--filter-status` and `--resolved-before N` flags to `validate_punchlist.py`. The recency twist: `--resolved-before 3` filters out items resolved more than 3 fixes ago, keeping recently-fixed items visible for cross-item pattern recognition during the fix loop.

**Estimated savings:** 31,500-55,125 tokens of context freed across Phase 6 at 10 lenses. Grows linearly with lens count.

**Key tradeoff:** Pattern recognition between OPEN and recently-RESOLVED items is preserved. Items resolved long ago (stable fixes) are filtered — they're available in Phase 5 when pattern analysis explicitly reads RESOLVED items.

---

### Design 2: Compact Pattern Brief for Subagents

**Category:** Total token usage
**Priority:** High — multiplied across 6-12 subagents per run

**Problem:** Every Phase 2/3 subagent loads `patterns-brief.md` (~500 lines at 20-entry cap). Most subagents need one-line detection heuristics, not full entries with examples and discovery history.

**Design:** Create `pattern_brief_compact.py` that reads `patterns-brief.md` and emits a lookup table (~40 lines). Requires dev testing to empirically determine the right prompt length and format that produces useful pattern matching without full context.

**Estimated savings:** 13,800-27,600 tokens/run at pattern maturity (run 5+). Hits upper range sooner as more lenses produce more patterns.

**Key tradeoff:** One-line heuristics are lossy for subtle patterns. Subagents that hit a match can read the full entry on demand. The real question is: what's the minimum context a subagent needs to reliably recognize a pattern? Requires empirical testing.

---

### Design 3: Justine Recon Inheritance

**Category:** Total token usage
**Priority:** Medium — clear win, moderate savings

**Problem:** Justine runs a full Phase 0 (steps 0a-0h) identical to Holtz's. Since Holtz finishes Phase 0 before dispatching her, all raw data is already on disk.

**Design:** Two-mode Phase 0 in justine-skill.md: solo mode (standalone) and inherited mode (dispatched by Holtz). Inherited mode reads Holtz's 0a-0f data, writes her own 0g summary and 0h predictions with her different calibration.

**Estimated savings:** 5,000-7,000 tokens/run (15-20 tool calls of duplicate I/O eliminated).

**Key tradeoff:** Justine may notice things in raw data that Holtz's summary didn't capture. Mitigated by: Justine still writes her own summary and predictions where her perspective matters; the raw data (file lists, git log) is objective.

---

### Design 4: Merge Protocol Example Extraction

**Category:** Total tokens + context on main agent
**Priority:** Low — small savings, near-zero risk

**Problem:** `merge-protocol.md` is 385 lines. Lines 146-385 (240 lines) are 6 worked examples. The rules section (145 lines) is self-contained and the protocol is explicitly designed to be deterministic.

**Design:** Move examples to `references/merge-examples.md`. Keep rules-only merge-protocol at ~150 lines. Examples available on demand for ambiguous cases.

**Estimated savings:** ~1,200 tokens/run.

**Key tradeoff:** Near-miss cases (Example 6: 5-line threshold) lose their anchor. If the rules need examples to be followed, the rules aren't clear enough.

---

## Context Usage Reductions (Main Holtz Agent)

### Design 5: Merge as Deterministic Subagent

**Category:** Context on main agent
**Priority:** Medium — significant context savings at a critical transition point

**Problem:** Pre-Phase 4 merge loads merge-protocol + both punchlists into Holtz's context (~2,065-4,990 tokens) at the audit-to-fix transition.

**Design:** A `merge-agent` (model: sonnet) that reads both punchlists + protocol, writes PUNCHLIST-MERGED.md and MERGE-REPORT.md, merges impact graphs. Holtz reads the output files. The merge is explicitly deterministic ("no judgment calls in the classification rules").

**Estimated savings:** 2,065-4,990 tokens freed from Holtz's context.

**Key tradeoff:** Holtz loses the structured walkthrough of Justine's findings vs his own. The merge-report summarizes blind spots, but seeing items side-by-side builds intuition about his own blind spots. Also: requires trusting a subagent with a deterministic procedure — the output is verifiable by reading the merged punchlist, but errors propagate into Phase 4.

---

### Design 6: Post-Convergence Bookkeeping Subagent (Conservative Scope)

**Category:** Context on main agent
**Priority:** Medium — saves context at the most strained point in the run

**Problem:** After convergence, Holtz loads living-punchlist-format.md (239 lines), architecture-baseline-format.md (221 lines), and pattern-contribution-protocol.md (56 lines) for three update tasks. These are format-following tasks at the worst possible time — late in a context-strained run.

**Design:** Subagent handles the most mechanical tasks only. Conservative scoping: only delegate pattern-contribution-protocol (truly mechanical: read brief, generalize, PII-scrub, stage) and architecture-baseline Structural Snapshot updates (objective: list modules, dependencies, entry points). Keep living punchlist update with Holtz — it requires judgment on pattern significance and risk assessment.

**Estimated savings:** ~1,500-2,000 tokens freed (pattern-contribution + baseline snapshot only, not full 4,080-5,080).

**Key tradeoff:** More conservative than originally proposed. Living punchlist update stays with Holtz because it involves judgment about which patterns are architecturally significant. The subagent gets only the tasks where the format spec IS the judgment — there's no interpretation needed.

# Tier 1: Foundational Protocol Changes

**Date:** 2026-03-20
**Status:** Draft
**Source:** `docs/holtz-self-reflection.md` Sections II, V, VII, X, XI
**Scope:** Four independent format/protocol changes that later tiers build on

## Overview

Four changes to Holtz's existing file formats and SKILL.md protocol, derived from the self-reflection essay's analysis of six self-audit runs. These are foundational — Tiers 2-4 (lens registry, Justine, predictive patterns, adversarial self-play) depend on them.

No new Python scripts are created. Changes extend the existing `validate_punchlist.py` validator and modify reference docs + SKILL.md.

## 1. Discovery Chain (Required Punchlist Field)

**Problem:** After context compaction, the auditor has findings but not the reasoning that produced them. Pattern analysis (Phase 5) depends on understanding *why* bugs exist, not just *what* they are. Two bugs with different symptoms but the same root cause are only recognizable as a pattern if the reasoning chain connecting symptom to cause is preserved.

**Change:** Add a required `**Discovery Chain:**` field to every punchlist item, positioned between `**Evidence:**` and `**Acceptance Criteria:**`.

### Format

A sequence of short statements connected by `→`, showing the auditor's reasoning from observation to conclusion. 1-4 steps, each step one clause.

```markdown
**Discovery Chain:** `_section_from_original` calls `re.search` on `original_block`
→ `original_block` contains code fences with bold text
→ `section_re` stops at bold text
→ section content silently truncated
```

### Files Changed

| File | Change |
|------|--------|
| `references/punchlist-format.md` | Add `**Discovery Chain:**` to item template between Evidence and Acceptance Criteria. Add format description and example. |
| `examples/sample-punchlist.md` | Add Discovery Chain to all sample items. |
| `scripts/validate_punchlist.py` | Add `Discovery Chain` to `_field_names` tuple (section boundary terminator list). Add Discovery Chain to required fields check — presence check only (header exists in masked content), no minimum content length threshold. |
| `skills/holtz/SKILL.md` | Add to Core Rules or Phase 4: each finding must include a Discovery Chain. |
| `tests/test_validate_punchlist.py` | Add tests: item missing Discovery Chain produces error; item with Discovery Chain passes. |

### Acceptance Criteria

- [ ] `validate_punchlist.py` reports an error for items missing `**Discovery Chain:**`
- [ ] `validate_punchlist.py` passes for items that include `**Discovery Chain:**`
- [ ] Discovery Chain field is correctly extracted from masked content (not poisoned by code-fence content)
- [ ] Sample punchlist passes validation with new field
- [ ] Punchlist format spec documents the field, its position, and its format
- [ ] Discovery Chain is required for all items regardless of status (OPEN, RESOLVED, DEFERRED) — it documents how the finding was discovered, which doesn't change after resolution

### Test Cases

1. **Missing Discovery Chain:** Punchlist with one item that has all fields except Discovery Chain → validator reports error naming the item and field.
2. **Present Discovery Chain:** Punchlist with complete item including Discovery Chain → validator passes with no errors.
3. **Discovery Chain inside code fence (poisoning):** Punchlist where `**Discovery Chain:**` appears inside a code fence but not as a real field → validator correctly reports it missing (masked content check works).
4. **Multi-step chain format:** Discovery Chain with 4 `→`-connected steps → validator accepts it.

---

## 2. Strategy Journal (STATUS.md Expansion)

**Problem:** After context compaction, the auditor recovers *where* it was but not *how it was thinking about the problem*. The current STATUS.md is a program counter — phase, step, next action. It doesn't capture which analytical lens is active, what patterns have been discovered, what areas are high-risk, or what tactical approach is being used.

**Change:** Add three new sections to the STATUS.md template: Active Lens, Pattern Library, and Strategy.

### New Sections (appended after `## Notes`)

```markdown
## Active Lens
**Current:** {component | integration | security | error-propagation | data-flow | contract}
**Lenses Completed This Run:** {comma-separated list}
**Finding Rate (current lens):** {N findings in M minutes}

## Pattern Library
{Compact list of all patterns discovered so far, current run + prior runs}
- **PAT-001:** {one-line description} ({N instances}, run {R})
- **PAT-002:** ...

## Strategy
**High-Risk Areas:** {from recon, updated as audit progresses}
**Last Insight:** {the most recent non-obvious observation — what the auditor learned that should inform the next step}
**Approach:** {current tactical approach, e.g., "checking extraction paths after each masking fix"}
```

### Files Changed

| File | Change |
|------|--------|
| `references/status-file-format.md` | Add three new sections to template. Add rules: Active Lens updates on lens switch, Pattern Library updates on PAT-NNN discovery, Strategy updates after each fix or insight. |
| `skills/holtz/SKILL.md` | Update Context Survival Protocol: "After compaction, re-read STATUS.md to recover position *and strategy*." Default Active Lens is `component` for current runs (prep for Tier 2 lens registry). |

### Acceptance Criteria

- [ ] Status file format spec includes Active Lens, Pattern Library, and Strategy sections with field descriptions
- [ ] SKILL.md Context Survival Protocol references strategy recovery, not just position recovery
- [ ] SKILL.md Phase 0 sets initial Active Lens to `component`
- [ ] SKILL.md Phase 5 updates Pattern Library section when a new pattern is identified
- [ ] Strategy section has a `Last Insight` field that captures non-obvious observations

### Test Cases

No script changes for this item — STATUS.md is not programmatically validated. Testing is via review of the format spec for completeness and consistency.

---

## 3. Recommendation Escalation

**Problem:** Every summary across six runs included the same recommendation ("add mypy and ruff") that was never implemented. Recommendations are advisory output that the process doesn't act on. The same recommendation appearing 2+ times indicates a persistent gap that should be treated as a finding.

**Change:** Add a step to Phase 0 recon that reads prior run summaries and escalates repeated recommendations to punchlist items.

### Protocol

Recommendation escalation is a prose instruction in the Phase 0 "After all steps" block (alongside the existing 0g recon summary instruction), not a table row. It does not produce its own output file — its output goes directly into `docs/holtz/PUNCHLIST.md` as punchlist items.

**After step 0f, before writing 0g recon summary:** Read `docs/holtz-prior-*/SUMMARY.md` Recommendations sections. Identify any recommendation that appears in substance (semantic match, not verbatim) in 2 or more prior summaries. For each match, create a `design/inconsistency` punchlist item at MEDIUM severity.

> **Note:** The self-reflection essay (Section X) suggested a threshold of 3 consecutive appearances. Reduced to 2 to catch persistent recommendations earlier, per design discussion.

### Escalated Item Format

````markdown
### BH-{NNN}: {recommendation title}
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** docs/holtz-prior-*/SUMMARY.md
**Status:** OPEN

**Problem:** This recommendation has appeared in {N} consecutive audit summaries
without being implemented: "{recommendation text}".

**Evidence:** Found in: {list of summary files with dates}

**Discovery Chain:** Prior summary scan → recommendation "{X}" found in {N} summaries
→ 2+ appearances triggers escalation per recommendation escalation protocol

**Acceptance Criteria:**
- [ ] Recommendation is implemented OR explicitly rejected with rationale
- [ ] Validation: the recommended tooling/change is in place

**Validation Command:**
```bash
{command that checks whether the recommendation was addressed}
```
````

### Severity Logic

Default severity is MEDIUM. The auditor may upgrade if the recommendation addresses a HIGH or CRITICAL risk (e.g., "add input sanitization" recurring across security-focused audits).

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Add recommendation escalation instruction to Phase 0 "After all steps" block. Add description of recommendation escalation protocol. |

### Why No Script Change

Recommendation matching requires semantic understanding ("add mypy" and "configure a type checker" are the same recommendation). This is LLM judgment work, not regex work. A script would be either brittle (exact string matching) or redundant (calling an LLM). The protocol lives in SKILL.md where the LLM is already reading the summary files.

### Acceptance Criteria

- [ ] SKILL.md Phase 0 includes recommendation scanning instruction in the "After all steps" block
- [ ] The escalation protocol specifies: threshold (2+ appearances), default severity (MEDIUM), category (`design/inconsistency`), and the punchlist item format
- [ ] Escalated items include Discovery Chain per Section 1
- [ ] The protocol uses semantic matching, not verbatim string comparison

### Test Cases

No script changes — this is a SKILL.md protocol addition. Testing is behavioral (verified by running Holtz on a project with prior summaries containing repeated recommendations).

---

## 4. Subagent Pattern Brief

**Problem:** Subagents don't inherit accumulated pattern knowledge. A subagent auditing module C doesn't know that modules A and B had code-fence-related bugs unless the parent explicitly briefs it. Pattern knowledge lives in the parent's context, which can't be fully communicated via task descriptions.

**Change:** Maintain a persistent `docs/holtz/patterns-brief.md` file that subagents read before starting audit work. Patterns are appended as discovered. The file persists across runs and is never archived.

### File Format

```markdown
# Holtz Pattern Brief

> Read this before starting any audit work. These patterns were discovered
> in prior audits of this project. Check for them in the code you're reviewing.

## PAT-001: {name} (Run {R}, {date})
**What to look for:** {1-2 sentences: the specific code shape or practice that indicates this bug class}
**Detection heuristic:** {grep pattern, structural check, or question to ask about the code}
**Example:** {one concrete instance from a prior finding, anonymized to the pattern level}

## PAT-002: ...
```

### Rolling Policy

The brief has a **cap of 20 active entries**. When a new pattern would push the count past 20, the 5 oldest entries (by discovery date) are moved in a single batch to `docs/holtz/patterns-brief-archive.md`. The archive has the same format but is not read by subagents by default — it's reference material available for investigation when a specific historical pattern may be relevant.

### Relationship to STATUS.md Pattern Library

The Pattern Library in STATUS.md (Section 2) is a compact index for context recovery — one line per pattern (PAT-NNN + description + instance count). The patterns-brief.md is a detailed briefing document with detection heuristics and examples, designed for subagent consumption. Phase 5 updates both: one-liner to STATUS.md Pattern Library, full entry to patterns-brief.md.

### Persistence Rules

- **Persists across runs.** When Holtz archives a run to `docs/holtz-prior-*/`, the patterns-brief stays in `docs/holtz/`. It is never archived.
- **Append-only for patterns.** New patterns are added. Existing patterns are never removed, though they can be updated with new detection heuristics or examples if a later run reveals a new manifestation.
- **Deduplicated.** If a new pattern is a refinement of an existing one (e.g., PAT-001 manifesting differently), the existing entry is updated rather than a new entry added.

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Phase 0: read patterns-brief if it exists. Phase 2/3: instruct subagents to read it. Phase 5: append new patterns to it and enforce rolling policy. Lifecycle: do not archive patterns-brief when archiving runs. |

### Acceptance Criteria

- [ ] SKILL.md Phase 0 reads `docs/holtz/patterns-brief.md` if it exists
- [ ] SKILL.md Phase 0 reads `docs/holtz/patterns-brief-archive.md` optionally for investigation
- [ ] SKILL.md Phases 2/3 instruct subagents to read the brief before starting
- [ ] SKILL.md Phase 5 appends new patterns to the brief with the specified format
- [ ] Rolling policy: brief capped at 20, oldest 5 roll to archive when cap exceeded
- [ ] Lifecycle section excludes patterns-brief from run archival
- [ ] Each brief entry includes: name, date, what to look for, detection heuristic, example
- [ ] Brief entries are deduplicated (refinements update existing entries)

### Test Cases

No script changes — the patterns-brief is maintained by the LLM per SKILL.md instructions. Testing is behavioral (verified by running Holtz and confirming the brief is created, read by subagents, and rolls correctly).

---

## Implementation Order

All four items are independent and can be implemented in parallel. However, the natural order for a single implementer is:

1. **Discovery Chain** — touches the most files (format spec, sample, validator, tests, SKILL.md)
2. **Strategy Journal** — format spec + SKILL.md only
3. **Recommendation Escalation** — SKILL.md only
4. **Subagent Pattern Brief** — SKILL.md only

Items 2-4 are SKILL.md-only changes and could be done in a single commit. Item 1 requires validator changes and new tests.

**Sequencing caveat:** Section 3 (Recommendation Escalation) references Discovery Chain in its escalated item template. If implementing 3 before 1, the Discovery Chain field in escalated items will not be validated until Section 1's validator changes are in place. For clean implementation, do Section 1 first.

## Dependencies

- **Tier 2 depends on this spec:** Lens Registry (Section II + VI) uses the Active Lens field from the Strategy Journal. Predictive Recon (Section IV) uses Discovery Chains for hypothesis generation. Blast Radius Analysis (Section III) uses Discovery Chains + Pattern Brief.
- **Tier 3 depends on Tier 2:** Justine uses the Lens Registry. Predictive Pattern Library uses the Pattern Brief.
- **Tier 4 depends on Tier 3:** Adversarial Self-Play uses Justine + Lens Registry.

## Out of Scope

- Automatic lens switching (Tier 2)
- Multi-lens convergence gates (Tier 2)
- New Python scripts (Approach C: extend existing only)
- Justine secondary auditor (Tier 3)
- Cross-project pattern transfer (Tier 3)
- Mutation-guided auditing, temporal auditing, living punchlist (Tier 4)

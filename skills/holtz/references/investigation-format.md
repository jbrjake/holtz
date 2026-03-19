# Investigation File Format

For complex punchlist items where the root cause is not obvious from the finding, create a per-item investigation file at `docs/holtz/investigations/BH-{NNN}.md`. The punchlist item links to it via the `**Investigation:**` field. Most punchlist items do not need this — only items that require the investigation protocol in Phase 4.

## When to create

Create an investigation file when:
- The item is categorized `bug/logic`, `bug/state`, `bug/security`, or `bug/type`
- The reproduction test does not fail on the first attempt (can't-reproduce path)
- The root cause is not obvious from the Problem and Evidence sections
- Multiple hypotheses need to be tested before fixing

Do NOT create investigation files for `test/*`, `doc/*`, or `design/*` items. These have straightforward fixes.

## Template

```markdown
# Investigation: BH-{NNN} — {title}

**Punchlist Item:** BH-{NNN}
**Started:** {ISO timestamp}
**Updated:** {ISO timestamp}
**Root Cause Confidence:** NONE | LOW | MEDIUM | HIGH

## Investigation Layers

Check each layer foundational-to-application. Mark as checked, not-applicable, or pending.

| Layer | Status | Finding |
|-------|--------|---------|
| Data | {checked / n/a / pending} | {what was found, or "as expected"} |
| Dependencies | {checked / n/a / pending} | {what was found} |
| State | {checked / n/a / pending} | {what was found} |
| Logic | {checked / n/a / pending} | {what was found} |
| Integration | {checked / n/a / pending} | {what was found} |
| Timing | {checked / n/a / pending} | {what was found} |

## Evidence

Append-only. Never edit or delete past entries.

- [{timestamp}] Checked: {what}. Expected: {x}. Got: {y}. Conclusion: {z}
- [{timestamp}] ...

## Theories

Ranked by confidence. Move disproven theories to Ruled Out — never delete.

| # | Hypothesis | Confidence | Supporting Evidence | Would Refute |
|---|-----------|------------|--------------------|--------------|
| 1 | {description} | HIGH/MED/LOW | {evidence refs} | {what check} |

## Ruled Out

Append-only. Hypotheses tested and disproven. Prevents re-investigation after compaction.

- {hypothesis} — disproven by: {evidence entry reference}

## Root Cause

Filled when confidence reaches HIGH. One paragraph max.

**Confidence:** {LOW/MEDIUM/HIGH}
**Evidence:** {references to Evidence section entries}
**Layer:** {which investigation layer revealed it}
```

## Rules

- **Append-only for Evidence and Ruled Out.** Never edit or delete past entries.
- **Theories can be reranked** but never deleted — move disproven ones to Ruled Out with the evidence that disproved them.
- **Update timestamps on every write.**
- **Do not proceed to fix until Root Cause Confidence is HIGH.** If below HIGH, design one more check to raise it.
- Keep entries terse. The file must stay readable after many entries.
- After context compaction, re-read this file before resuming investigation on this item.

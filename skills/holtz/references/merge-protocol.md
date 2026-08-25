# Merge Protocol

This file defines the merge classification rules and protocol for Adversarial Self-Play — the mode where Holtz and Justine audit the same codebase in parallel and their findings are merged into a unified punchlist. The parent process orchestrates the merge after both auditors reach convergence (or one stalls).

> **Note:** This protocol is consumed by the merge-agent (Sonnet model) during automated merges, and by Holtz directly when reviewing merge output. The rules must be precise enough for algorithmic execution without worked examples — see [merge-examples.md](merge-examples.md) for examples when classification is ambiguous.

## Overview

Adversarial Self-Play dispatches both auditors simultaneously against the same codebase. Each auditor works independently through their full audit methodology — Holtz with depth-first analysis, Justine with breadth-first analysis. Neither auditor sees the other's findings during the audit.

After both auditors reach convergence (or one stalls), the parent process merges their punchlists into a unified result. The merge is mechanical — it follows the classification rules below without judgment calls, except for contradictions which are flagged for human review.

**Inputs:**
- Holtz's findings — on the ledger. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/findings.py list --all`.
- `docs/holtz/justine/PUNCHLIST.md` — the only copy of Justine's findings; she keeps no ledger.

**Outputs:**
- Justine's unmatched findings, recorded as `finding` events. `docs/holtz/PUNCHLIST.md` is then the unified worklist.
- `docs/holtz/MERGE-REPORT.md` — statistics, blind spot analysis, flagged items.

## Stall Conditions

An auditor is considered **stalled** if either condition is met:

1. **Inactivity:** Its `STATUS.md` has not been updated in more than 30 minutes.
2. **No progress:** It has completed 3 consecutive fix loop iterations with no reduction in open punchlist items.

If one auditor stalls, the parent proceeds with the merge using whatever findings the stalled auditor produced up to that point. The merge report notes which auditor stalled, at what step, and how many findings it produced before stalling.

## Merge Classification Rules

For each item in either punchlist, classify it into exactly one of the five categories below. Process all items from both punchlists — do not skip any.

| Classification | Condition | Action |
|----------------|-----------|--------|
| **Agreement** | Same bug found by both auditors | Nothing to record. List the pair in the report. |
| **Holtz-only** | Found by Holtz, not by Justine | Nothing to record. |
| **Justine-only** | Found by Justine, not by Holtz | One `sahjhan event finding`, keeping her `BJ-NNN` id. |
| **Severity disagreement** | Same bug found by both, different severity | If Justine's is higher, re-file Holtz's id at her severity. List in the report. |
| **Contradictory** | One auditor says X is a bug, the other explicitly verified X as correct | Record per its class, and flag: `**Contradictory:** Holtz says {X}, Justine says {Y}`. Do not auto-resolve. |

Keep ids as filed. Re-filing an existing id supersedes it: the punchlist keeps the last filing per id.

**Note:** Severity disagreement is a sub-case of Agreement — both auditors found the same bug, they just disagree on severity. In the merge report, severity disagreements are counted in the Agreement section total (e.g., "5 items found by both auditors, including 2 with severity disagreements") and listed individually in the Severity Disagreements section for visibility. They are NOT double-counted in the merged total.

Contradictions stay OPEN. Do not run a deferral transition on one.

### "Same Bug" Matching Criteria

Two findings are considered the "same bug" when ALL of the following hold:

1. **Same file** — both findings reference the same source file path.
2. **Same category** — both findings use the same category (e.g., `bug/logic`, `test/missing`).
3. **Location proximity** — at least one of:
   - Both specify line numbers and the lines are **within 5 of each other** (inclusive).
   - Both specify a function or class name and the **name matches exactly**.
   - One specifies a line number, the other specifies a function/class — the line number falls **within the function/class body**.

If conditions 1 and 2 match but condition 3 does not, the items are **not** the same bug — they are separate findings that happen to be in the same file and category.

### Processing Order

1. Sort both punchlists by file path, then by category, then by location (line numbers sort numerically; function names sort alphabetically; items with line numbers sort before items with only function names).
2. **Matching is one-to-one.** For each Holtz item, scan all unmatched Justine items for a match using the criteria above. If multiple Justine items match, select the closest by line number (smallest absolute difference). If line distances are equal, select the Justine item with the lower item number. Once a Justine item is matched, it is removed from the candidate pool and cannot match another Holtz item.
3. **Location-free fallback.** If neither finding in a candidate pair specifies a line number or function/class name, they match on file path + category alone (conditions 1 and 2 are sufficient).
4. Matched pairs are classified as Agreement (or Severity disagreement if severities differ).
5. Unmatched Holtz items are classified as Holtz-only.
6. Unmatched Justine items are classified as Justine-only.
7. Check for contradictions: scan Justine's notes/evidence for explicit statements that a Holtz finding is "not a bug" or "correct behavior" (and vice versa). These override the Holtz-only/Justine-only classification.

## Running the Merge

Steps 1–6 above, the recording, the report and the impact-graph merge are one command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/scripts/merge_punchlists.py" \
  --justine docs/holtz/justine/PUNCHLIST.md
```

Add `--dry-run` to classify and write the report without touching the ledger.

It prints the contradiction candidates step 7 asks for — a finding whose text calls a defect the other auditor filed correct behavior — to stderr. Each is already recorded under its own class. Read both findings, decide, and rewrite the report's `## Contradictions` section with the ones that hold.

## Output File

### Merge Report: `docs/holtz/MERGE-REPORT.md`

The merge's only file. `merge_complete` gates on it existing with all four sections non-empty.

````markdown
# Adversarial Self-Play Merge Report

**Date:** {ISO date}
**Holtz findings:** {N total items from Holtz's punchlist}
**Justine findings:** {N total items from Justine's punchlist}
**Merged total:** {N items in unified punchlist}

## Agreement
{N} items found by both auditors

{List each agreed item with its merged ID and original IDs}

## Holtz-only
{N} items — suggests depth-first analysis found subtle bugs

{List each Holtz-only item with its merged ID and original ID}

## Justine-only
{N} items — suggests breadth-first analysis found surface bugs

{List each Justine-only item with its merged ID and original ID}

## Severity Disagreements
{N} items — listed with both ratings

{For each:}
- **BH-{NNN}:** Holtz={severity}, Justine={severity}. Using {higher severity}.

## Contradictions
{N} items — flagged for human review

{For each:}
- **BH-{NNN}:** Holtz says {X}. Justine says {Y}. Deferred pending human review.

## Blind Spot Analysis
Based on what each auditor missed:
- **Holtz's blind spots:** {pattern in Justine-only findings — e.g., "missed 3 surface-level doc/drift items in README paths"}
- **Justine's blind spots:** {pattern in Holtz-only findings — e.g., "missed 2 deep bug/state issues requiring multi-step data flow analysis"}
````

## Post-Merge Fix Ownership

**Holtz owns the merged punchlist and runs the fix loop.** Justine's role ends at convergence of her audit — she finds bugs, she does not fix them.

Post-merge sequence:

1. Holtz's worklist is `docs/holtz/PUNCHLIST.md`.
2. Holtz runs Steps 10-16 (fix loop, pattern analysis, convergence, resweep) on the merged items.
3. Parent process archives `docs/holtz/justine/` to `docs/holtz/archive/justine-{ISO date}/`, then deletes the archived `impact-graph.json` (its data has already been merged into the canonical graph — the archive retains all other files for reference).
4. Justine is not re-dispatched for the fix loop.
5. If a full re-audit is needed after fixes, a new adversarial self-play round can be initiated.

## Impact Graph Merge

`merge_punchlists.py` folds Justine's impact graph (`docs/holtz/justine/impact-graph.json`) into the canonical graph (`docs/holtz/impact-graph.json`) by these rules:

| Conflict | Resolution |
|----------|-----------|
| **Same node updated by both** | Keep the higher `risk_score`. Merge `audit_count` by summing both values. Use the most recent `last_audited` timestamp. |
| **Same edge added by both with different metadata** | Keep the edge with the more recent timestamp. Append the other auditor's `note` to the metadata. |
| **Different edges between same nodes** | Keep both edges. Different relationship types or observations are distinct data. |
| **Node exists in one graph only** | Add it to the canonical graph unchanged. |
| **Edge exists in one graph only** | Add it to the canonical graph unchanged. |

After the merge, delete `docs/holtz/justine/impact-graph.json` — the canonical graph is the single source of truth.

## Worked Examples

See [merge-examples.md](merge-examples.md) for worked examples of each classification type (Agreement, Holtz-only, Justine-only, Severity Disagreement, Contradictory, Near-Miss Location Match).

Consult examples when:
- A specific item pair is ambiguous under the matching criteria above
- The 5-line proximity threshold produces a borderline match
- A contradiction is suspected but not certain

## Rules

- **Every finding from both auditors ends up on the ledger.**
- **Never auto-resolve a contradiction.** Flag in the report, leave OPEN.
- **Higher severity wins.** Re-file Holtz's id at the higher one.
- **Use Holtz's description for agreements.** If Justine observed something he did not, re-file his id with it appended.
- **Never renumber.**
- **Do not merge patterns here.** Note any Justine pattern in the report; it enters `docs/holtz/patterns-brief.md` at the next pattern round.

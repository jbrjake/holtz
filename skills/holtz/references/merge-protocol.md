# Merge Protocol

This file defines the merge classification rules and protocol for Adversarial Self-Play — the mode where Holtz and Justine audit the same codebase in parallel and their findings are merged into a unified punchlist. The parent process orchestrates the merge after both auditors reach convergence (or one stalls).

## Overview

Adversarial Self-Play dispatches both auditors simultaneously against the same codebase. Each auditor works independently through their full audit methodology — Holtz with depth-first analysis, Justine with breadth-first analysis. Neither auditor sees the other's findings during the audit.

After both auditors reach convergence (or one stalls), the parent process merges their punchlists into a unified result. The merge is mechanical — it follows the classification rules below without judgment calls, except for contradictions which are flagged for human review.

**Inputs:**
- `docs/holtz/PUNCHLIST.md` — Holtz's findings
- `docs/justine/PUNCHLIST.md` — Justine's findings

**Outputs:**
- `docs/holtz/PUNCHLIST-MERGED.md` — unified punchlist (Holtz's worklist going forward)
- `docs/holtz/MERGE-REPORT.md` — merge statistics, blind spot analysis, and flagged items

## Stall Conditions

An auditor is considered **stalled** if either condition is met:

1. **Inactivity:** Its `STATUS.md` has not been updated in more than 30 minutes.
2. **No progress:** It has completed 3 consecutive fix loop iterations with no reduction in open punchlist items.

If one auditor stalls, the parent proceeds with the merge using whatever findings the stalled auditor produced up to that point. The merge report notes which auditor stalled, at what phase, and how many findings it produced before stalling.

## Merge Classification Rules

For each item in either punchlist, classify it into exactly one of the five categories below. Process all items from both punchlists — do not skip any.

| Classification | Condition | Action |
|----------------|-----------|--------|
| **Agreement** | Same bug found by both auditors | Keep one copy. Tag `**Found by:** both auditors`. Use the higher severity. |
| **Holtz-only** | Found by Holtz, not by Justine | Keep. Tag `**Found by:** Holtz only`. |
| **Justine-only** | Found by Justine, not by Holtz | Keep. Tag `**Found by:** Justine only`. |
| **Severity disagreement** | Same bug found by both, different severity | Keep one copy. Tag `**Found by:** both auditors`. Flag: `**Severity disagreement:** Holtz={X}, Justine={Y}`. Use the higher severity. |
| **Contradictory** | One auditor says X is a bug, the other explicitly verified X as correct | Flag for human review: `**Contradictory:** Holtz says {X}, Justine says {Y}`. Do not auto-resolve. |

**Note:** Severity disagreement is a sub-case of Agreement — both auditors found the same bug, they just disagree on severity. In the merge report, severity disagreements are counted in the Agreement section total (e.g., "5 items found by both auditors, including 2 with severity disagreements") and listed individually in the Severity Disagreements section for visibility. They are NOT double-counted in the merged total.

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

## Output Files

### Unified Punchlist: `docs/holtz/PUNCHLIST-MERGED.md`

This file follows the standard punchlist format (see `punchlist-format.md`) with these additions:

- Each item includes a `**Found by:**` tag after the standard fields.
- Items with severity disagreements include a `**Severity disagreement:**` annotation.
- Contradictory items include a `**Contradictory:**` annotation and are set to `**Status:** DEFERRED` until human review.
- Item IDs are re-numbered sequentially as `BH-{NNN}` (Holtz's namespace, since Holtz owns the fix loop).
- A cross-reference comment maps each merged ID to the original ID(s): `<!-- Was: Holtz BH-003 + Justine BJ-007 -->` for agreements, `<!-- Was: Holtz BH-005 -->` for Holtz-only, `<!-- Was: Justine BJ-012 -->` for Justine-only.

### Merge Report: `docs/holtz/MERGE-REPORT.md`

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

1. Holtz reads `PUNCHLIST-MERGED.md` as his worklist.
2. Holtz runs Phases 4-6 (fix loop, pattern analysis, convergence) on the merged items.
3. Parent process archives `docs/justine/` to `docs/justine-prior-{ISO date}/`, then deletes `docs/justine-prior-{ISO date}/impact-graph.json` from the archive (its data has already been merged into the canonical graph — the archive retains all other files for reference).
4. Justine is not re-dispatched for the fix loop.
5. If a full re-audit is needed after fixes, a new adversarial self-play round can be initiated.

## Impact Graph Merge

After both auditors complete, merge Justine's impact graph (`docs/justine/impact-graph.json`) into the canonical graph (`docs/holtz/impact-graph.json`). Conflict resolution rules:

| Conflict | Resolution |
|----------|-----------|
| **Same node updated by both** | Keep the higher `risk_score`. Merge `audit_count` by summing both values. Use the most recent `last_audited` timestamp. |
| **Same edge added by both with different metadata** | Keep the edge with the more recent timestamp. Append the other auditor's `note` to the metadata. |
| **Different edges between same nodes** | Keep both edges. Different relationship types or observations are distinct data. |
| **Node exists in one graph only** | Add it to the canonical graph unchanged. |
| **Edge exists in one graph only** | Add it to the canonical graph unchanged. |

After the merge, delete `docs/justine/impact-graph.json` — the canonical graph is the single source of truth.

## Worked Examples

The examples below demonstrate each of the five classification types. All examples assume a Python web application codebase.

### Example 1: Agreement (same bug, same severity)

**Holtz finding:**
```markdown
### BH-011: Missing input validation in user registration
**Severity:** HIGH
**Category:** bug/security
**Location:** `app/routes/auth.py:47`
**Problem:** The `register_user` endpoint accepts email input without validation,
allowing malformed or malicious email strings to reach the database layer.
```

**Justine finding:**
```markdown
### BJ-004: No email validation on registration endpoint
**Severity:** HIGH
**Category:** bug/security
**Location:** `app/routes/auth.py:49`
**Problem:** The registration handler does not validate the email field before
passing it to `create_user()`. Invalid emails are stored without error.
```

**Classification decision:** Same file (`app/routes/auth.py`), same category (`bug/security`), line numbers within 5 of each other (47 and 49, difference = 2). **Agreement.**

**Merged output:**
```markdown
### BH-003: Missing input validation in user registration
**Severity:** HIGH
**Category:** bug/security
**Location:** `app/routes/auth.py:47`
**Found by:** both auditors
<!-- Was: Holtz BH-011 + Justine BJ-004 -->

**Problem:** The `register_user` endpoint accepts email input without validation,
allowing malformed or malicious email strings to reach the database layer.
```

### Example 2: Holtz-only

**Holtz finding:**
```markdown
### BH-015: Race condition in session token refresh
**Severity:** CRITICAL
**Category:** bug/state
**Location:** `app/auth/tokens.py:112`
**Problem:** Concurrent requests can trigger simultaneous token refreshes. The second
refresh invalidates the first's new token, causing an authenticated user to be logged
out. Requires multi-step data flow analysis to detect — only observable under concurrent
request load.
```

**Justine finding:** (none — no Justine item references `app/auth/tokens.py` with category `bug/state`)

**Classification decision:** No matching Justine item for this file + category combination. **Holtz-only.**

**Merged output:**
```markdown
### BH-007: Race condition in session token refresh
**Severity:** CRITICAL
**Category:** bug/state
**Location:** `app/auth/tokens.py:112`
**Found by:** Holtz only
<!-- Was: Holtz BH-015 -->

**Problem:** Concurrent requests can trigger simultaneous token refreshes. The second
refresh invalidates the first's new token, causing an authenticated user to be logged
out.
```

### Example 3: Justine-only

**Holtz finding:** (none — no Holtz item references `README.md` with category `doc/drift`)

**Justine finding:**
```markdown
### BJ-019: README install instructions reference removed dependency
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:34`
**Problem:** The install instructions include `pip install redis` but redis was removed
as a dependency in requirements.txt three months ago. The caching layer was replaced
with an in-memory LRU cache.
```

**Classification decision:** No matching Holtz item. **Justine-only.**

**Merged output:**
```markdown
### BH-012: README install instructions reference removed dependency
**Severity:** LOW
**Category:** doc/drift
**Location:** `README.md:34`
**Found by:** Justine only
<!-- Was: Justine BJ-019 -->

**Problem:** The install instructions include `pip install redis` but redis was removed
as a dependency in requirements.txt three months ago. The caching layer was replaced
with an in-memory LRU cache.
```

### Example 4: Severity Disagreement

**Holtz finding:**
```markdown
### BH-022: Unchecked return value from database write
**Severity:** CRITICAL
**Category:** bug/error-handling
**Location:** `app/models/order.py:88` (function `save_order`)
**Problem:** The `save_order` function calls `db.execute(insert_query)` without checking
the return value. If the insert fails silently (connection timeout, constraint violation),
the order is reported as saved but is not persisted.
```

**Justine finding:**
```markdown
### BJ-008: save_order ignores db.execute result
**Severity:** HIGH
**Category:** bug/error-handling
**Location:** `app/models/order.py:91` (function `save_order`)
**Problem:** `save_order` does not check whether `db.execute` succeeded. A failed write
would go unnoticed.
```

**Classification decision:** Same file (`app/models/order.py`), same category (`bug/error-handling`), same function name (`save_order`), line numbers within 5 (88 and 91, difference = 3). Same bug. Severities differ: Holtz says CRITICAL, Justine says HIGH. **Severity disagreement.** Use CRITICAL (the higher severity).

**Merged output:**
```markdown
### BH-005: Unchecked return value from database write
**Severity:** CRITICAL
**Category:** bug/error-handling
**Location:** `app/models/order.py:88` (function `save_order`)
**Found by:** both auditors
**Severity disagreement:** Holtz=CRITICAL, Justine=HIGH
<!-- Was: Holtz BH-022 + Justine BJ-008 -->

**Problem:** The `save_order` function calls `db.execute(insert_query)` without checking
the return value. If the insert fails silently (connection timeout, constraint violation),
the order is reported as saved but is not persisted.
```

### Example 5: Contradictory

**Holtz finding:**
```markdown
### BH-009: Default timeout of 0 disables request timeouts
**Severity:** HIGH
**Category:** bug/logic
**Location:** `app/client/http.py:23`
**Problem:** The HTTP client sets `timeout=0` as the default. In the `requests` library,
timeout=0 means "no timeout," allowing requests to hang indefinitely. Should be a
positive value like 30.
```

**Justine finding:**
```markdown
(In BJ-015 Evidence section):
"Verified: `app/client/http.py:23` sets `timeout=0`. Confirmed this is intentional —
the project uses `httpx`, not `requests`. In httpx, `timeout=0` means 'use the default
timeout' (5 seconds), not 'no timeout'. This is correct behavior."
```

**Classification decision:** Holtz says `timeout=0` is a bug. Justine explicitly verified `timeout=0` as correct. **Contradictory.** Do not auto-resolve — flag for human review.

**Merged output:**
```markdown
### BH-009: Default timeout of 0 disables request timeouts [CONTRADICTORY]
**Severity:** HIGH
**Category:** bug/logic
**Location:** `app/client/http.py:23`
**Status:** DEFERRED
**Found by:** Holtz only (Justine contradicts)
**Contradictory:** Holtz says timeout=0 disables timeouts (requests library behavior).
Justine says timeout=0 is correct (httpx library behavior, uses default 5s timeout).
<!-- Was: Holtz BH-009 — contradicted by Justine BJ-015 evidence -->

**Problem:** The HTTP client sets `timeout=0` as the default. Holtz interprets this as
"no timeout" (requests library semantics). Justine interprets this as "use default
timeout" (httpx library semantics). Human review required to determine which library
is actually in use.
```

### Example 6: Near-Miss Location Match

This example demonstrates the 5-line proximity threshold.

**Scenario A — Match (4 lines apart):**

**Holtz finding:**
```markdown
### BH-031: Unsafe string concatenation in SQL query
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:47`
```

**Justine finding:**
```markdown
### BJ-022: SQL injection in query builder
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:51`
```

Lines 47 and 51 — difference is 4. **Within 5 lines.** Same file, same category. **This is a match → Agreement.**

---

**Scenario B — No match (6 lines apart):**

**Holtz finding:**
```markdown
### BH-031: Unsafe string concatenation in SQL query
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:47`
```

**Justine finding:**
```markdown
### BJ-023: Unescaped user input in delete query
**Severity:** CRITICAL
**Category:** bug/security
**Location:** `app/db/queries.py:53`
```

Lines 47 and 53 — difference is 6. **Outside 5 lines.** Even though same file and same category, these are classified independently. Holtz's item is **Holtz-only**, Justine's item is **Justine-only** (they are likely two separate SQL injection instances in different queries).

## Rules

- **All items from both punchlists must appear in the merged output.** No finding is silently dropped. Every Holtz item and every Justine item is either merged with a counterpart or carried forward independently.
- **Contradictions are never auto-resolved.** The merge process flags them and defers to human judgment. The contradictory item is included in the merged punchlist with `DEFERRED` status.
- **Higher severity always wins.** When two findings match and have different severities, the merged item uses the higher severity. The disagreement is noted but does not prevent the merge.
- **Holtz's description is preferred for agreements.** When merging two descriptions of the same bug, use Holtz's wording for the Problem and Evidence fields (Holtz is the primary auditor). Justine's additional observations can be appended as a note.
- **Re-numbering is mandatory.** The merged punchlist uses a fresh `BH-{NNN}` sequence starting from BH-001. Cross-reference comments preserve the mapping to original IDs.
- **Pattern blocks are merged.** If both auditors identified patterns, merge them. Same pattern = combine instance lists. Different patterns = keep both. Pattern IDs are re-numbered in the merged punchlist.
- **The merge is deterministic.** Given the same two punchlists, the merge always produces the same output. There are no judgment calls in the classification rules (except contradiction detection, which is flagged rather than resolved).

# Gap Analysis: bug-fixer vs Holtz Phase 4

Source: `docs/references/bug-fixer/SKILL.md` and `journal-format.md`

Bug-fixer is a single-bug debugger with a 7-step protocol. Holtz is a codebase-wide auditor with a 7-phase lifecycle. They overlap in Phase 4 (Fix Loop), where Holtz fixes individual punchlist items using TDD. The comparison below focuses on that overlap — what bug-fixer does during individual bug resolution that Holtz currently doesn't.

## What Holtz already covers

These are in both and don't need porting:

- **No fix without a failing test.** Both enforce this. Holtz's Core Rule #2.
- **Minimal fix, no drive-by changes.** Both enforce this.
- **Atomic commits with scope and description.** Both enforce this.
- **Full test suite after each fix.** Both enforce this.
- **Context survival via durable files.** Holtz has the more sophisticated version (STATUS.md as program counter, phase-specific output files, subagent delegation). Bug-fixer has a single DEBUG-JOURNAL.md.
- **Resume from prior state.** Both check for existing state files and resume.
- **Pattern/sibling detection.** Holtz does this in Phase 5 at a batch level. Bug-fixer's Step 6 does it per-fix ("Are there sibling cases?"). Different granularity, same intent.

## Gaps worth porting

### 1. Bottom-up investigation layers

**Bug-fixer has it:** Step 3 defines a structured layer-by-layer investigation protocol — Data, Dependencies, State, Logic, Integration, Timing — working foundational to application. Each layer is checked before moving up.

**Holtz lacks it:** Phase 4 says "Write failing test. Verify it fails. Minimal fix." This assumes the root cause is obvious from the punchlist finding. For straightforward items (missing test, bogus assertion, doc drift) it usually is. For complex bugs found during Phase 3 adversarial audit (race conditions, state corruption, integration failures), there's no structured investigation method.

**What to port:** Add a conditional investigation protocol to Phase 4 for items categorized as `bug/state`, `bug/logic`, or `bug/security` — bugs where the symptom is clear but the root cause may not be. The bottom-up layer order is the valuable part. Holtz doesn't need the full 7-step ceremony for every punchlist item, but he needs it for the hard ones.

### 2. Root cause confidence gating

**Bug-fixer has it:** Step 4 requires a confidence level (LOW/MEDIUM/HIGH) on the root cause hypothesis. Won't proceed to fix until confidence is HIGH. If below HIGH, designs one more check to raise it.

**Holtz lacks it:** Core Rule #3 says "Fix root causes. Follow the thread upstream." But there's no mechanism to verify that the identified root cause is actually correct before writing the fix. For a straightforward missing-test item this doesn't matter. For a complex state bug, fixing the wrong root cause wastes a fix cycle and may introduce new issues.

**What to port:** For non-trivial items, require a root cause statement with confidence level in the punchlist item's Resolution section before the fix is applied. If confidence is below HIGH, investigate further before coding. This doesn't need a separate journal — it fits in the punchlist item's Evidence section.

### 3. Can't-reproduce protocol

**Bug-fixer has it:** A dedicated protocol for when Step 2 (reproduction test) fails: widen conditions, check environment differences, add instrumentation, statistical reproduction (run test 100-1000x for intermittent failures), git bisect.

**Holtz lacks it:** Phase 4 says "Write failing test. Verify it fails." Full stop. No fallback if the test doesn't fail. Holtz finds issues during Phases 1-3 by reading code and docs, not by running the system. Some of those findings may not be reproducible in the test environment — environment-specific issues, timing-dependent bugs, or conditions that only manifest under load.

**What to port:** Add a can't-reproduce branch to Phase 4. If the reproduction test passes (bug not triggered), don't skip the item — escalate the investigation. Widen conditions, check for environment dependencies, try statistical reproduction for intermittent cases. If still not reproducible after structured attempts, mark the item DEFERRED with evidence of reproduction attempts, not silently dropped. This is important because Holtz's adversarial audit (Phase 3) will find theoretical bugs that may be hard to trigger in practice.

### 4. Per-fix hardening

**Bug-fixer has it:** Step 6 explicitly asks after each fix: Are there sibling cases (same pattern, different inputs)? Could this regress? Does the fix handle edge cases (null, empty, boundary, concurrent)? Additional tests are written for these.

**Holtz lacks it:** Holtz does sibling detection at the batch level in Phase 5 (every 3-5 fixes), which catches systemic patterns. But per-fix hardening — checking that the specific fix handles null/empty/boundary/concurrent — is not part of Phase 4. The reproduction test proves the original bug is fixed, but doesn't prove the fix is robust.

**What to port:** After each fix passes the reproduction test and full suite, add a hardening check: does the fix handle the obvious edge variants of the same input path? Write tests for those. This is not the same as Phase 5 pattern analysis (which looks across fixes for systemic issues). This is per-fix robustness — making sure the fix itself isn't fragile. Particularly important for `bug/error-handling` and `bug/security` categories where edge cases are the entire point.

### 5. Ruled-out tracking

**Bug-fixer has it:** The journal has an append-only "Ruled Out" section where disproven hypotheses are recorded with the evidence that disproved them. Hypotheses in "Theories" are moved to "Ruled Out" when disproven, never deleted.

**Holtz lacks it:** The punchlist has Evidence and Problem sections per item, but no structured way to track what was investigated and eliminated during the fix process. For a simple item this doesn't matter. For a complex bug where three hypotheses are tested before finding the root cause, the investigation history is lost.

**What to port:** For complex items (those requiring the investigation protocol from gap #1), add a `**Ruled Out:**` subsection to the punchlist item, listing hypotheses tested and disproven. This prevents re-investigation of the same dead ends if the item is revisited after context compaction, and provides an audit trail of the investigation process. Only needed for items that require investigation, not for straightforward fixes.

### 6. Determinism assessment

**Bug-fixer has it:** Step 1 asks upfront: "Is it deterministic or intermittent?" and adjusts the entire investigation strategy based on the answer. Intermittent bugs get statistical reproduction (loop 100-1000x) and instrumentation.

**Holtz lacks it:** The punchlist format has no field for determinism. Some bugs found in Phase 3 (adversarial audit) may be identified from code review as theoretically possible but may not manifest deterministically — race conditions, ordering-dependent state, cache timing issues.

**What to port:** Add an optional `**Determinism:**` field to punchlist items in the `bug/*` categories. Values: deterministic, intermittent, theoretical (identified from code analysis, not observed in practice). This informs how the reproduction test should be structured — a theoretical race condition needs a different reproduction strategy than a deterministic logic error.

### 7. Git bisect as an explicit tool

**Bug-fixer has it:** Git bisect is explicitly mentioned for regressions ("If it used to work, find the breaking commit") in both the main protocol and the can't-reproduce protocol.

**Holtz lacks it:** Phase 0 does git churn analysis, and the punchlist records file locations, but git bisect is never mentioned as a tool for investigation or reproduction. For items where the punchlist shows a working behavior that regressed, git bisect is the fastest path to root cause.

**What to port:** In Phase 4, when a punchlist item describes behavior that previously worked (detectable from git history or test suite changes), use git bisect as a first-pass investigation tool before writing the reproduction test. The bisect identifies the breaking commit, which narrows the fix to a specific change rather than the entire file.

### 8. Per-bug investigation workspace

**Bug-fixer has it:** Each bug gets its own DEBUG-JOURNAL.md (or DEBUG-JOURNAL-{slug}.md for multi-bug). This is a dedicated investigation workspace with structured sections for evidence, theories, ruled-out hypotheses, and next steps.

**Holtz lacks it:** All findings go into the single PUNCHLIST.md. For straightforward items this is fine — the punchlist format has Problem, Evidence, Acceptance Criteria, and Resolution. But for complex bugs requiring extended investigation (the ones that need gaps #1, #2, and #5), the punchlist item format is too compact to hold a full investigation trail.

**What to port:** For punchlist items that require investigation (not simple missing-test or doc-drift fixes), create a per-item investigation file at `docs/holtz/investigations/BH-{NNN}.md` using a format adapted from the debug journal. The punchlist item links to it. This keeps the punchlist scannable while providing workspace for complex bugs. Only create investigation files when needed — most punchlist items won't need them.

## What NOT to port

- **Bug-fixer's Step 1 (Understand the Report).** Holtz doesn't receive bug reports — he finds bugs himself during Phases 1-3. By the time an item reaches Phase 4, Holtz already has the Problem and Evidence sections filled in. The "gather symptoms" step is redundant.
- **Bug-fixer's Step 7 close-out ceremony.** Holtz already updates the punchlist with resolution, commit hash, and validating test immediately after each fix. The close-out is already built into the fix loop.
- **Bug-fixer's journal as the primary tracking mechanism.** Holtz has a better system — the punchlist IS the tracking mechanism, with STATUS.md as the program counter. The journal format is useful only as a supplementary investigation workspace for complex items (gap #8).
- **Bug-fixer's invocation modes.** These are for a different use case (user-reported bugs vs systematic audit). Holtz already has his own invocation modes.

## Implementation priority

If these gaps were addressed, the order that would deliver the most value:

1. **Can't-reproduce protocol (#3)** — Holtz will find theoretical bugs in Phase 3 that can't be trivially reproduced. Without a protocol, these get silently dropped or incorrectly fixed. Highest risk of wasted work or false confidence.
2. **Per-fix hardening (#4)** — Every fix Holtz makes should be robust, not just correct for the original case. Cheap to add, high return.
3. **Bottom-up investigation layers (#1)** — Only needed for complex bugs, but when needed, the absence is expensive. Prevents Holtz from guessing at root causes.
4. **Root cause confidence gating (#2)** — Natural companion to #1. Small addition to the fix protocol.
5. **Determinism assessment (#6)** — Informs reproduction strategy. One punchlist field plus a sentence in Phase 4.
6. **Git bisect (#7)** — Useful for regressions specifically. One paragraph in Phase 4.
7. **Ruled-out tracking (#5)** — Only matters for complex investigations. Depends on #8.
8. **Per-bug investigation workspace (#8)** — Infrastructure for the other investigation gaps. Most value when combined with #1, #2, and #5.

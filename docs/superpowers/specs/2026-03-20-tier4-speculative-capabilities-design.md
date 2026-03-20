# Tier 4: Adversarial Self-Play, Mutation-Guided Auditing, Temporal Awareness

**Date:** 2026-03-20
**Status:** Draft
**Source:** `docs/holtz-self-reflection.md` Sections IX, XII
**Depends on:** Tier 1 (all), Tier 2 (all), Tier 3 (Justine, Pattern Library)
**Scope:** Three components: Adversarial Self-Play (parallel audit + merge), Mutation-Guided Auditing (external tool integration), Temporal Awareness (architectural drift + living punchlist)

## Overview

Tier 4 adds the most experimental capabilities from the self-reflection essay. Adversarial Self-Play combines Holtz and Justine for maximum coverage. Mutation-Guided Auditing integrates with existing mutation testing tools to identify undertested code. Temporal Awareness adds the time dimension — detecting architectural drift and maintaining a persistent vulnerability model across audits.

All three are optional enhancements. The core audit process (Tiers 1-3) works without them. They activate when conditions are met (both auditors available, mutation tool installed, prior runs exist).

---

## 1. Adversarial Self-Play

**Problem:** Each auditor has blind spots determined by their analytical approach. Holtz is depth-first and misses surface-level bugs. Justine is breadth-first and misses subtle bugs. Running them sequentially is slower than running them in parallel, and their findings are more valuable when compared than when combined.

**Change:** A new invocation mode where both auditors run in parallel on the same codebase. The parent process dispatches both, waits for completion, and merges their punchlists into a unified result. Holtz owns the merged punchlist and runs the fix loop.

### Dispatch Protocol

The parent process (user's session or coordinator) dispatches both auditors simultaneously using Claude Code's Agent tool with parallel invocation:

```
Agent(prompt="Run full Holtz audit", subagent_type="general-purpose")
Agent(prompt="Run full Justine audit", subagent_type="general-purpose")
```

Both run independently. Holtz writes to `docs/holtz/`. Justine writes to `docs/justine/`. Both read and write the shared impact graph and pattern brief — concurrent writes are mostly disjoint because they examine different areas first (different lens ordering).

### Merge Protocol

After both auditors reach convergence (or one converges and the other stalls), the parent process runs the merge:

1. Read `docs/holtz/PUNCHLIST.md` and `docs/justine/PUNCHLIST.md`
2. For each item in either punchlist, classify:

| Classification | Condition | Action |
|---------------|-----------|--------|
| **Agreement** | Same bug found by both (same location within ~5 lines AND same category) | Keep one, note `**Found by:** both auditors`, use the higher severity |
| **Holtz-only** | Found by Holtz, not by Justine | Keep. Tag `**Found by:** Holtz only`. Likely a deep/subtle bug that breadth-first scanning missed. |
| **Justine-only** | Found by Justine, not by Holtz | Keep. Tag `**Found by:** Justine only`. Likely a surface/obvious bug or an aggressively-rated risk that depth-first auditing walked past. |
| **Severity disagreement** | Same bug, different severity | Flag: `**Severity disagreement:** Holtz={X}, Justine={Y}`. Use the higher severity but note the disagreement. |
| **Contradictory** | One auditor says X is a bug, the other explicitly verified X as correct | Flag for human review: `**Contradictory:** Holtz says {X}, Justine says {Y}`. Do not auto-resolve. |

3. Write unified punchlist to `docs/holtz/PUNCHLIST-MERGED.md`
4. Write merge report to `docs/holtz/MERGE-REPORT.md`

### Merge Report Format

```markdown
# Adversarial Self-Play Merge Report

**Date:** {date}
**Holtz findings:** {N}
**Justine findings:** {N}

## Agreement
{N} items found by both auditors

## Holtz-only
{N} items — suggests depth-first analysis found subtle bugs

## Justine-only
{N} items — suggests breadth-first analysis found surface bugs

## Severity Disagreements
{N} items — listed with both ratings

## Contradictions
{N} items — flagged for human review

## Blind Spot Analysis
Based on what each auditor missed:
- Holtz's blind spots: {pattern in Justine-only findings}
- Justine's blind spots: {pattern in Holtz-only findings}
```

### Post-Merge Fix Ownership

**Holtz owns the merged punchlist and runs the fix loop.** Justine's role ends at convergence of her audit — she finds bugs, she doesn't fix them.

This matches the personas: Holtz is methodical and thorough, which is what you want for the careful work of TDD fix loops and blast radius analysis. Justine is fast and broad, which is what you want for finding things, not for the patience of writing minimal fixes and hardening them.

Justine's severity ratings are preserved in the merged list (the higher rating wins per the merge protocol), so her aggressive calibration influences fix priority even though Holtz does the fixing. Her urgency shapes the work order; his discipline shapes the execution.

**Post-merge sequence:**

1. Holtz reads `PUNCHLIST-MERGED.md` as his worklist
2. Holtz runs Phases 4-6 (fix loop, pattern analysis, convergence) on the merged items
3. `docs/justine/` is archived to `docs/justine-prior-{date}/` — Justine's run is complete
4. Justine is not re-dispatched for the fix loop
5. If a full re-audit is needed after fixes, a new adversarial self-play round can be initiated

### Impact Graph Conflict Resolution

Both auditors write to `docs/holtz/impact-graph.json`. Since they examine different areas first (different lens ordering), their graph writes are mostly disjoint. For conflicts:

- **Same node updated by both:** Keep the higher `risk_score`, merge `audit_count` (sum of both increments), use the most recent `last_audited`.
- **Same edge added by both with different metadata:** Keep the edge with the more recent timestamp, append the other's `note` to the metadata field.
- **Different edges between same nodes:** Both edges are kept (they may represent different relationship types or observations).

### Files Created

| File | Purpose |
|------|---------|
| `skills/holtz/references/merge-protocol.md` | Merge classification rules, matching criteria, output format, post-merge ownership, conflict resolution |

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Add "Adversarial Self-Play" invocation mode. Document dispatch + merge protocol. Document post-merge fix ownership. |
| `skills/justine/SKILL.md` | Note that Justine can be dispatched in parallel with Holtz. Note that her role ends at convergence — she does not run the fix loop on merged items. |

### Acceptance Criteria

- [ ] Merge protocol document defines all 5 classification types (Agreement, Holtz-only, Justine-only, Severity disagreement, Contradictory)
- [ ] "Same bug" matching uses Location (within 5 lines) AND Category
- [ ] Merged punchlist written to `docs/holtz/PUNCHLIST-MERGED.md`
- [ ] Merge report written to `docs/holtz/MERGE-REPORT.md` with blind spot analysis
- [ ] Severity disagreements use the higher severity with both ratings noted
- [ ] Contradictory findings flagged for human review, not auto-resolved
- [ ] Post-merge: Holtz owns the merged punchlist and runs Phases 4-6
- [ ] Post-merge: Justine's output archived to `docs/justine-prior-{date}/`
- [ ] Post-merge: Justine is not re-dispatched for the fix loop
- [ ] Impact graph conflict resolution defined (higher risk_score wins, notes merged, audit_count summed)
- [ ] SKILL.md documents adversarial self-play as an invocation mode
- [ ] Both auditors can be dispatched in parallel via Agent tool
- [ ] Merge report includes worked examples of each classification type

### Test Cases

No script changes — the merge is performed by the parent process reading two markdown files. Testing is behavioral, plus:

1. **Merge protocol examples:** The merge protocol document includes worked examples showing each of the 5 classification types applied to sample findings.

---

## 2. Mutation-Guided Auditing

**Problem:** The anti-patterns reference mentions "mutation resilience" as an audit dimension, but checking it is currently manual — the auditor reads a test and judges whether it would catch a mutation. Existing mutation testing tools can automate this, directing the audit toward functions where tests are weakest.

**Change:** Integrate with existing mutation testing tools during Phase 0 recon. Mutation survival data feeds into predictions, impact graph risk scores, and anti-pattern scoring.

### Supported Tools (Auto-Detected)

| Language | Tool | Detection |
|----------|------|-----------|
| Python | mutmut | `mutmut` in PATH or `[tool.mutmut]` in `pyproject.toml` |
| JavaScript/TypeScript | Stryker | `stryker.conf.js` / `stryker.conf.mjs` or `@stryker-mutator` in `package.json` |
| Rust | cargo-mutants | `cargo-mutants` in PATH |
| Go | go-mutesting | `go-mutesting` in PATH |
| Java/Kotlin | PIT | `pitest` in `pom.xml` or `build.gradle` |

**When no mutation tool is available:** Skip step 0e.1 entirely. No error, no warning — mutation-guided auditing is an optional enhancement. The audit proceeds normally.

### New Recon Step

**Step 0e.1: Mutation scan.** Between step 0e (churn) and 0f (skipped tests). Run the detected mutation tool with a time cap. Capture per-function mutation survival rates.

**Time cap:** Based on test suite runtime from step 0c. If test suite runs in under 30 seconds: 5 minute cap. If 30s-5min: 10 minute cap. If over 5 minutes: 15 minute cap. If the tool times out, report partial results with a note.

**Output:** `docs/holtz/recon/0e1-mutation-scan.md`

```markdown
# Mutation Scan Results

**Tool:** mutmut
**Duration:** 3m 42s
**Timeout:** No
**Total mutants:** 147
**Killed:** 98 (67%)
**Survived:** 49 (33%)

## Survival by Function (worst first)

| Function | File | Mutants | Survived | Rate |
|----------|------|---------|----------|------|
| `parse_items` | `validate_punchlist.py` | 12 | 8 | 67% |
| `count_items` | `convergence_check.py` | 8 | 5 | 63% |
| `detect_runner` | `convergence_check.py` | 6 | 3 | 50% |
| ... | ... | ... | ... | ... |

## Surviving Mutations (top 20)

| Function | Mutation | Description |
|----------|----------|-------------|
| `parse_items` | Line 47: `<=` → `<` | Boundary change survived |
| `parse_items` | Line 52: delete `if` guard | Guard deletion survived |
| ... | ... | ... |
```

### How Mutation Data Feeds the Pipeline

| Consumer | How it uses mutation data |
|----------|-------------------------|
| **Predictions (0h)** | Functions with >40% mutation survival become HIGH-confidence predictions for `test/shallow` or `test/missing` findings. Specific surviving mutations become predicted issues with concrete descriptions (e.g., "boundary check at line 47 is not tested"). |
| **Impact graph** | `update_risk` on nodes based on survival rate: >50% survival → +0.3, 30-50% → +0.2, 10-30% → +0.1. |
| **Phase 2 (test audit)** | When auditing a test file, check whether the tests for a function kill its mutations. A test that passes but doesn't kill mutations is a Rubber Stamp (#11) or Permissive Validator (#12). Mutation data provides concrete evidence for these anti-pattern classifications. |
| **Phase 4 (fix loop)** | After writing a reproduction test and fix, re-run mutations on the changed function to verify the new test improves the kill rate. This is a post-fix quality check, not a gate — a fix can proceed even if mutation score doesn't improve, but it should be noted. |

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Phase 0: add step 0e.1 (mutation scan with auto-detection and time cap). Phase 2: reference mutation data for anti-pattern scoring. Phase 4: post-fix mutation verification. |
| `skills/justine/SKILL.md` | Same Phase 0 mutation scan integration. |

### Acceptance Criteria

- [ ] SKILL.md Phase 0 includes step 0e.1 for mutation scan with auto-detection of 5 supported tools
- [ ] Mutation scan has a time cap determined by test suite runtime (5/10/15 minutes)
- [ ] Output file `docs/holtz/recon/0e1-mutation-scan.md` includes survival by function and top surviving mutations
- [ ] Functions with >40% mutation survival become HIGH-confidence predictions
- [ ] Impact graph risk scores updated based on mutation survival rates (+0.3/>50%, +0.2/30-50%, +0.1/10-30%)
- [ ] Phase 2 references mutation data when scoring Rubber Stamp and Permissive Validator anti-patterns
- [ ] Phase 4 includes post-fix mutation re-run on changed functions (quality check, not gate)
- [ ] When no mutation tool is available, step 0e.1 is silently skipped
- [ ] Partial results reported with a note when the tool times out
- [ ] Justine's SKILL.md includes the same mutation scan integration

### Test Cases

No script changes — mutation tool integration is a SKILL.md protocol addition. Testing is behavioral (verified by running Holtz on a project with a supported mutation tool installed).

---

## 3. Temporal Awareness (Architectural Drift + Living Punchlist)

**Problem:** The current process audits the codebase at a point in time. It doesn't detect *architectural drift* — the slow accumulation of structural violations that no single commit introduces. And each audit's findings are ephemeral — archived after the run, not carried forward as institutional knowledge about the project's specific vulnerability profile.

**Change:** Two related capabilities merged into one feature. Architectural drift detection compares current structure against both documented intent and prior structural snapshots. The living punchlist maintains a persistent vulnerability model that grows across audits and generates proactive checks.

### Architecture Baseline

On the first run, Holtz establishes a baseline by capturing both documented intent and actual structure. On subsequent runs, drift is detected by comparing against this baseline.

**Baseline file:** `docs/holtz/architecture-baseline.md`

**Documented intent** (extracted from existing docs):
- Read `CLAUDE.md`, `ARCHITECTURE.md`, design docs, README architectural sections
- Extract: stated module boundaries, layering rules, dependency direction, naming conventions, stated invariants
- Note: if no architecture docs exist, this section is marked "No documented architecture found — baseline is structural snapshot only"

**Actual structure** (inferred from code):
- Module dependency graph (who imports whom)
- Layering patterns (which modules call which — is there a clear direction?)
- Naming conventions (are there consistent patterns in file/function/class naming?)
- Boundary patterns (are there clear interfaces, or do modules reach into each other's internals?)

### Baseline File Format

```markdown
# Architecture Baseline

**Project:** {name}
**Established:** {date}
**Last Updated:** {date}

## Documented Intent
{extracted from project docs}

- **Layering rule:** {e.g., "scripts/ depends on markdown_utils but not vice versa"}
- **Boundary:** {e.g., "validate_punchlist handles parsing, convergence_check handles tracking"}
- **Convention:** {e.g., "test files mirror source files: test_{name}.py"}
- **Invariant:** {e.g., "all field extraction uses masked content, never raw"}
- ...

## Structural Snapshot
{inferred from code at baseline time}

### Module Dependencies
{adjacency list or table showing who imports whom}

### Layering Direction
{which layers call which — clean top-down, or spaghetti?}

### Naming Conventions
{observed patterns in file, function, class naming}

### Boundary Clarity
{how clean are the module boundaries? do modules reach into each other?}

## Drift Log
{appended on subsequent runs}

### {date}: {drift description}
**Type:** boundary-erosion | dependency-reversal | convention-violation | layering-breach
**Evidence:** {what changed and when, from git history}
**Severity:** LOW | MEDIUM | HIGH
**Punchlist item:** BH-{NNN} (if escalated)
```

### Drift Detection (Phase 0, Step 0a.1)

After reading project structure (step 0a), if `docs/holtz/architecture-baseline.md` exists:

1. Re-infer current structural snapshot (same analysis as baseline creation)
2. Compare against baseline's Structural Snapshot for structural drift:
   - **Dependency reversal:** Module A used to not depend on B, now it does
   - **Boundary erosion:** Module A's functions used to be called only by B, now C and D call them too
   - **Convention violation:** New files/functions don't follow the naming pattern established at baseline
   - **Layering breach:** A lower layer now calls a higher layer (dependency inversion)
3. Compare against Documented Intent for intent drift:
   - Any stated invariant that's now violated
   - Any stated boundary that's been crossed
   - Any stated layering rule that's been broken
4. For each detected drift:
   a. Append to the Drift Log in the baseline file
   b. If significant (MEDIUM+), create a punchlist item

**Note:** Intent drift (step 3) overlaps with Phase 1 (doc-to-implementation audit). The difference: Phase 1 checks specific testable claims. Step 0a.1 checks structural/architectural claims that Phase 1's claim-by-claim approach may not catch — e.g., "the dependency graph has shifted direction" is architectural, not a single doc claim.

### Drift Types and Severities

| Drift Type | Description | Default Severity |
|-----------|-------------|-----------------|
| `dependency-reversal` | A new dependency exists in the opposite direction of the established pattern | MEDIUM |
| `boundary-erosion` | A module's public surface has expanded beyond its intended scope | MEDIUM |
| `convention-violation` | New code doesn't follow established naming/structural conventions | LOW |
| `layering-breach` | A lower-level module now depends on a higher-level one | HIGH |

### Baseline Updates

The baseline is not immutable. When drift is detected and determined to be intentional (architecture evolved deliberately):

1. Update the Structural Snapshot to reflect the new reality
2. Update the Documented Intent if docs were also updated
3. The Drift Log retains the history — it records that the change happened, even if it was accepted
4. Update `Last Updated` date

This prevents false positives on future runs for intentional architectural changes.

---

### Living Punchlist

A persistent document at `docs/holtz/LIVING-PUNCHLIST.md` that tracks the project's known vulnerability model across all audits. Unlike per-run punchlists (which get archived), the living punchlist is cumulative.

### What Goes In

| Content | Source | Purpose |
|---------|--------|---------|
| **Active patterns** | Pattern brief (PAT-NNN entries) | Known bug classes this project is susceptible to |
| **Risk hotspots** | Impact graph nodes with risk_score > 0.5 | Code areas that have produced bugs repeatedly |
| **Architectural risks** | Drift log entries at MEDIUM+ severity | Structural weaknesses that could produce future bugs |
| **Recurring recommendations** | Recommendation escalation (Tier 1) | Tooling/process gaps that persist across runs |
| **Prediction accuracy** | Summary prediction tables | Calibration data — which risk signals are reliable for this project |

### Living Punchlist Format

```markdown
# Living Punchlist

**Project:** {name}
**Established:** {date}
**Last Updated:** {date}
**Audits Completed:** {N}

## Active Vulnerability Model

### Patterns This Project Is Susceptible To
{from pattern brief — patterns that have manifested here}

### Risk Hotspots
{from impact graph — functions/modules with risk_score > 0.5}
| Node | Risk Score | Last Bug | Audit Count |
|------|-----------|----------|-------------|

### Architectural Risks
{from drift log — active drifts at MEDIUM+ severity}

### Persistent Gaps
{from recommendation escalation — unaddressed recommendations}

## Proactive Checks

Detection heuristics that should be run on every new commit or PR
to this project. Derived from patterns and risk hotspots.

### Check 1: {name}
**Trigger:** {what to look for — new file, changed function, etc.}
**Heuristic:** {grep command or structural check}
**If triggered:** {what to do — flag for review, run specific tests, etc.}

### Check 2: ...

## History
{append-only log of changes to the living punchlist}

### {date}: Run {N} completed
- Added: {patterns, hotspots, risks added}
- Removed: {patterns resolved, hotspots cooled, risks addressed}
- Calibration: prediction accuracy was {X}%
```

### How the Living Punchlist Is Maintained

| When | Action |
|------|--------|
| End of each converged run | Update all sections: refresh hotspots from graph, add new patterns, update drift risks, record prediction accuracy, derive new proactive checks |
| Start of each run (Phase 0) | Read living punchlist. Proactive checks feed into 0h predictions as HIGH-confidence items. |
| Risk hotspot cools (risk_score drops below 0.3) | Move from Risk Hotspots to History: "resolved after {N} clean audits" |
| Pattern addressed architecturally | Move from Active Patterns to History: "addressed by {architectural change}" |

### Proactive Checks

The most forward-looking part of the living punchlist. Derived from the project's specific vulnerability model:

- **From patterns:** If this project is susceptible to regex-newline-leak, add a proactive check: "On any new regex in a file that processes multi-line text, check for `\s` where `[ \t]` is intended."
- **From hotspots:** If `parse_punchlist` is a risk hotspot, add a proactive check: "Any change to `validate_punchlist.py` should re-run the mutation scan on `parse_punchlist`."
- **From drift:** If a layering breach was detected, add a proactive check: "Any new import in `scripts/` should be checked for layering direction."

These checks could eventually be integrated into CI or Snyder (the real-time code watcher), but for now they're documented for manual use or for the auditor to run during Phase 0.

### Persistence Rules

- Living punchlist persists across runs (never archived to `docs/holtz-prior-*/`)
- Architecture baseline persists across runs (never archived)
- Both are updated at the end of each converged run, not during the run
- History sections are append-only
- Justine reads both documents during Phase 0 but does not update them — updates happen post-merge by Holtz

### Files Created

| File | Purpose |
|------|---------|
| `skills/holtz/references/architecture-baseline-format.md` | Format spec for `docs/holtz/architecture-baseline.md` |
| `skills/holtz/references/living-punchlist-format.md` | Format spec for `docs/holtz/LIVING-PUNCHLIST.md` |

### Files Changed

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Phase 0: establish or read architecture baseline, run drift check (step 0a.1), read living punchlist and feed proactive checks to predictions. Post-convergence: update living punchlist with run results. Lifecycle: baseline and living punchlist persist across runs. |
| `skills/justine/SKILL.md` | Phase 0: read architecture baseline and living punchlist (same as Holtz). Justine does not update either — updates happen post-merge by Holtz. |

### Acceptance Criteria

- [ ] Architecture baseline format spec defines Documented Intent, Structural Snapshot, and Drift Log sections
- [ ] Phase 0 step 0a.1 establishes baseline on first run, performs drift check on subsequent runs
- [ ] Drift detection compares both documented intent and structural snapshot against current state
- [ ] Four drift types defined with default severities (dependency-reversal MEDIUM, boundary-erosion MEDIUM, convention-violation LOW, layering-breach HIGH)
- [ ] Significant drifts (MEDIUM+) create punchlist items
- [ ] Baseline can be updated when drift is determined intentional, with history preserved in Drift Log
- [ ] Living punchlist format spec defines Active Vulnerability Model, Proactive Checks, and History sections
- [ ] Living punchlist updated at end of each converged run (not during)
- [ ] Living punchlist read during Phase 0, proactive checks feed into predictions as HIGH-confidence items
- [ ] Risk hotspots populated from impact graph nodes with risk_score > 0.5
- [ ] Hotspots that cool below 0.3 are moved to History with note
- [ ] Proactive checks derived from patterns, hotspots, and drift
- [ ] Both living punchlist and architecture baseline persist across runs (never archived)
- [ ] Justine reads but does not update either document

### Test Cases

No script changes — both features are SKILL.md protocol additions with format specs. Testing is behavioral, plus:

1. **Baseline format validation:** A sample architecture baseline file conforms to the format spec (all required sections and fields present).
2. **Living punchlist format validation:** A sample living punchlist file conforms to the format spec (all required sections present).
3. **Drift type coverage:** The architecture baseline format spec includes examples of all 4 drift types with sample evidence and punchlist items.

---

## Implementation Order

1. **Mutation-Guided Auditing** — SKILL.md protocol addition, no dependencies beyond Tier 2 (impact graph for risk updates, predictions for feeding mutation data)
2. **Temporal Awareness** — format specs + SKILL.md protocol, depends on impact graph (risk hotspots), pattern brief (active patterns), recommendation escalation (persistent gaps)
3. **Adversarial Self-Play** — merge protocol + SKILL.md, depends on Justine (Tier 3) being fully operational

Items 1 and 2 are independent and can be parallelized. Item 3 must come last.

## Dependencies

- **Tier 2 → Tier 4:** Impact Graph (mutation updates risk scores, living punchlist reads hotspots), Predictive Recon (mutation data feeds predictions), Lens Registry (adversarial self-play uses different lens defaults per auditor)
- **Tier 3 → Tier 4:** Justine (adversarial self-play dispatches her), Pattern Library (living punchlist references active patterns)
- **Tier 1 → Tier 4:** Recommendation Escalation (living punchlist includes persistent gaps), Strategy Journal (drift check results update strategy), Pattern Brief (living punchlist references it)

## Out of Scope

- Custom mutation engine (uses existing tools only)
- CI integration for proactive checks (documented for manual use, CI integration is future work)
- Snyder integration (proactive checks could feed Snyder, but that's a separate project)
- Automated baseline generation from git history (baseline is established by reading current code + docs on first run)

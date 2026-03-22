# Living Punchlist Format

This file defines the format for `docs/holtz/LIVING-PUNCHLIST.md` — the document Holtz uses to maintain a persistent vulnerability model across all audit runs. Unlike per-run punchlists (which get archived to `docs/holtz-prior-*/` after each run), the living punchlist is cumulative and persists indefinitely.

The living punchlist provides institutional memory. It records which bug classes the project is susceptible to, which code areas repeatedly produce bugs, what structural weaknesses exist, and what detection heuristics should be applied to every new change. Over time, it becomes a calibrated risk model: the prediction accuracy section tracks which signals are reliable for this specific project.

## File Location

`docs/holtz/LIVING-PUNCHLIST.md` in the target project.

## Template

````markdown
# Living Punchlist

**Project:** {name}
**Established:** {ISO date — when the living punchlist was first created}
**Last Updated:** {ISO date — when the living punchlist was last modified}
**Audits Completed:** {N — total number of converged Holtz runs}

## Active Vulnerability Model

### Patterns This Project Is Susceptible To

{From pattern briefs (PAT-NNN entries) — known bug classes this project has exhibited.
Each pattern stays here until the root cause is addressed architecturally.
When addressed, move to History with a note explaining the architectural change.}

- **PAT-{NNN}:** {pattern name} — {one-line description of the bug class}
  - Instances: {BH-NNN, BH-NNN, ...}
  - Root cause: {why this class exists in this project}
  - Detection rule: {grep/lint rule for future instances}
  - First seen: Run {N} ({ISO date})

### Risk Hotspots

{From impact graph nodes with risk_score > 0.5 — code areas that have produced bugs
repeatedly. A hotspot is a file, function, or module where findings cluster across runs.

When a hotspot cools (risk_score drops below 0.3 for two consecutive runs), move it
to History: "resolved after {N} clean audits".}

| Node | Risk Score | Last Bug | Audit Count | Notes |
|------|-----------|----------|-------------|-------|
| {`path/to/file.py:function_name`} | {0.0–1.0} | {BH-NNN (Run N)} | {how many audits found bugs here} | {brief context} |

### Architectural Risks

{From drift log entries at MEDIUM or higher severity — structural weaknesses in the
codebase that could produce future bugs. These are not bugs themselves but conditions
that make bugs more likely.

When a risk is addressed (the drift is resolved or the architecture is intentionally
changed), move to History with a note explaining the resolution.}

- **{drift type}:** {description of the structural weakness}
  - Source: Drift log entry {ISO date}
  - Severity: {MEDIUM | HIGH}
  - Why it matters: {what class of bugs this could produce}
  - Punchlist items produced: {BH-NNN, ... | none yet}

### Persistent Gaps

{From recommendation escalation (Tier 1) — tooling, process, or infrastructure gaps
that persist across runs. These are systemic issues that individual bug fixes cannot
address.

When a gap is closed, move to History with a note explaining what was done.}

- **{gap description}**
  - First identified: Run {N} ({ISO date})
  - Still present as of: Run {N} ({ISO date})
  - Impact: {what this gap causes — missed bugs, slow feedback, etc.}
  - Recommended fix: {what would close this gap}

## Proactive Checks

{Detection heuristics that should be run on every new commit or PR. Each check is
derived from a specific pattern, hotspot, or drift entry in the Active Vulnerability
Model. When the source is retired (pattern addressed, hotspot cooled, drift resolved),
the derived proactive check is also moved to History with a note linking to the
source retirement.}

### Check {N}: {name}
**Source:** {PAT-NNN | Hotspot: path/to/file | Drift: description}
**Trigger:** {what to look for — new file matching a glob, changed function, new import, etc.}
**Heuristic:** {grep command, structural check, or analysis step}
**If triggered:** {what to do — flag for review, run specific tests, escalate, etc.}

## Prediction Accuracy

{Calibration data showing which risk signals are reliable for this project. Updated
at the end of each converged run by comparing 0h predictions against actual findings.

This section tracks prediction accuracy across all runs, not just the most recent one.
The per-run breakdown is recorded in History.}

### Cumulative Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | {N}       | {N}       | {N%}     |
| MEDIUM     | {N}       | {N}       | {N%}     |
| LOW        | {N}       | {N}       | {N%}     |
| **Total**  | **{N}**   | **{N}**   | **{N%}** |

### Calibration Notes

{Observations about prediction reliability for this project. Which types of predictions
tend to be accurate? Which are unreliable? What adjustments should be made?}

- {e.g., "HIGH-confidence predictions from hotspots are 90% accurate — keep weighting these heavily"}
- {e.g., "MEDIUM-confidence predictions from pattern matching are only 40% accurate — consider downgrading to LOW"}
- {e.g., "Drift-based predictions have not yet produced confirmed findings — too early to calibrate"}

## History

{Append-only log of changes to the living punchlist. Each entry records what was
added, removed, or updated at the end of a converged run. Entries are never deleted
or edited — the history is the audit trail of how the vulnerability model evolved.}

### {ISO date}: Run {N} completed
- Added: {patterns, hotspots, risks, gaps, or proactive checks added}
- Removed: {patterns resolved, hotspots cooled, risks addressed, gaps closed, checks retired}
- Calibration: prediction accuracy was {X}% ({N} of {M} predictions confirmed)
- Notes: {any other significant changes to the vulnerability model}
````

## Proactive Check Derivation

Proactive checks are derived from three sources in the Active Vulnerability Model. Each check must cite its source so it can be retired when the source is resolved.

### From Patterns

If the project is susceptible to a pattern, derive a check that detects new instances of that pattern before they become bugs.

**Example:** If susceptible to PAT-003 (regex-newline-leak) — the pattern where `\s` in a regex matches newlines when only spaces/tabs were intended:

```markdown
### Check 1: Regex newline leak in multi-line text processing
**Source:** PAT-003
**Trigger:** New or modified regex in files that process multi-line text
**Heuristic:** `grep -rn '\\\\s' --include='*.py' | grep -v '#.*\\\\s'` — look for `\s` in regex patterns, excluding comments
**If triggered:** Review whether `\s` should be `[ \t]`. Flag for review if the regex operates on multi-line input.
```

### From Hotspots

If a code area is a risk hotspot, derive a check that ensures changes to that area receive extra scrutiny.

**Example:** If `parse_punchlist` in `validate_punchlist.py` is a hotspot (risk_score 0.8, bugs in 3 of 4 audits):

```markdown
### Check 2: Hotspot change in validate_punchlist.py
**Source:** Hotspot: validate_punchlist.py:parse_punchlist
**Trigger:** Any change to `validate_punchlist.py`, especially `parse_punchlist` or its helpers
**Heuristic:** `git diff --name-only HEAD~1 | grep validate_punchlist`
**If triggered:** Re-run mutation scan on punchlist parsing. Review change against known bug patterns (PAT-001, PAT-003).
```

### From Drift

If an architectural drift has been detected, derive a check that prevents the drift from spreading.

**Example:** If a layering breach was detected (scripts/ importing from core/):

```markdown
### Check 3: Layering direction in scripts/
**Source:** Drift: layering-breach in scripts/ (2026-02-15)
**Trigger:** Any new import statement added to files in `scripts/`
**Heuristic:** `grep -rn '^from core\|^import core' scripts/`
**If triggered:** Flag for architectural review. scripts/ should depend on utils/ only, not core/.
```

## Maintenance Rules

The living punchlist is updated at specific points in the Holtz workflow — never ad hoc. These rules define when each action occurs.

| When | Action |
|------|--------|
| End of each converged run | Update all sections: refresh hotspots from impact graph, add new patterns from pattern briefs, update architectural risks from drift log, record prediction accuracy from 0h predictions vs. actual findings, derive new proactive checks from any new model entries, append History entry |
| Start of each run (Phase 0) | Read living punchlist. Proactive checks feed into 0h predictions as HIGH-confidence items. Known patterns and hotspots inform where to focus the audit |
| Risk hotspot cools (risk_score drops below 0.3 for two consecutive clean runs) | Move from Risk Hotspots table to History: "resolved after {N} clean audits" |
| Pattern addressed architecturally | Move from Patterns to History: "addressed by {architectural change}" |
| Architectural risk resolved | Move from Architectural Risks to History: "resolved — {what changed}" |
| Persistent gap closed | Move from Persistent Gaps to History: "closed — {what was done}" |
| Proactive check's source retired | When a hotspot cools, pattern is addressed, or drift is resolved, the proactive check derived from it is also moved to History with a note linking to the source retirement |

## Persistence Rules

The living punchlist and the architecture baseline are the two documents that persist across runs. All other Holtz artifacts (per-run punchlist, STATUS.md, investigation files, 0h-predictions.md, etc.) get archived to `docs/holtz-prior-*/` at the start of each new run.

- **Living punchlist persists across runs.** It is never archived to `docs/holtz-prior-*/`.
- **Architecture baseline persists across runs.** It is never archived.
- **Living punchlist is updated at the end of each converged run, not during the run.** The auditor reads it during Phase 0 but does not modify it until the run has converged and findings are finalized.
- **Architecture baseline drift log is appended during Phase 0** as drift is detected (step 0a.1). The baseline's Structural Snapshot and Documented Intent sections are updated only at convergence when drift is accepted. This distinction matters: drift log entries are raw observations (safe to write immediately), while snapshot/intent updates are acceptance decisions (deferred until findings are confirmed).
- **History sections are append-only.** Entries are never deleted or edited. The history is the audit trail.
- **Justine reads both documents during Phase 0 but does not update them.** Updates happen post-merge by Holtz. This prevents the living punchlist from being modified by in-flight work that might not converge.

## First-Run Behavior

If no `docs/holtz/LIVING-PUNCHLIST.md` exists when a run starts:

1. **Do not create it during the run.** Complete the audit normally.
2. **Create it at the end of the first converged run.** Populate it from the run's findings:
   - Patterns from the punchlist's pattern blocks
   - Risk hotspots from the impact graph (if generated)
   - Architectural risks from the drift log in the architecture baseline
   - Persistent gaps from recommendation escalation
   - Prediction accuracy from 0h predictions vs. actual findings
   - Proactive checks derived from the above
3. **Set `Audits Completed` to 1** and `Established` to today's date.
4. **History gets its first entry** documenting what was added.

## Subsequent-Run Behavior

If `docs/holtz/LIVING-PUNCHLIST.md` exists when a run starts:

1. **Read it during Phase 0.** Use proactive checks as HIGH-confidence inputs to 0h predictions. Use known patterns and hotspots to focus the audit.
2. **Do not modify it during the run.**
3. **At end of converged run, update all sections:**
   - Add new patterns, hotspots, risks, and gaps discovered this run
   - Cool or retire entries that are no longer active
   - Update prediction accuracy with this run's calibration data
   - Derive new proactive checks from any new entries
   - Retire proactive checks whose sources were retired
   - Increment `Audits Completed`
   - Update `Last Updated`
   - Append History entry

## Rules

- **Update only at convergence.** The living punchlist reflects converged findings, not in-progress work. Never update it mid-run.
- **History is append-only.** Never delete or edit history entries. They are the permanent record of how the vulnerability model evolved.
- **Every proactive check must cite its source.** This is how checks get retired — when the source is retired, the check goes with it.
- **Risk scores are relative to this project.** A 0.7 in one project is not comparable to a 0.7 in another. Calibrate based on the project's own history.
- **Prediction accuracy drives calibration.** If HIGH-confidence predictions are only 50% accurate, something is wrong with the model. Use the calibration notes to record what adjustments are needed.
- **Cooldown requires two consecutive clean runs.** A hotspot does not cool after a single clean run — it takes two. This prevents premature retirement of checks for areas that produce bugs intermittently.
- **Moved items retain their history.** When an item moves from an active section to History, record what it was, when it was added, and why it was retired. The History entry should be self-contained.

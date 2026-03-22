# Recommendation Escalation Protocol

Before writing the recon summary, read the Recommendations section of every `docs/holtz-prior-*/SUMMARY.md` file (or `docs/justine-prior-*/SUMMARY.md` for Justine). Identify any recommendation that appears *in substance* (semantic match, not verbatim — e.g., "add mypy" and "configure a type checker" are the same recommendation) in 2 or more prior summaries. For each match, create a punchlist item. If the punchlist file does not exist yet, create it with proper file structure first (see punchlist-format.md File Structure section).

## Escalated Item Template

````markdown
### {ID}: {recommendation title}
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** docs/{auditor}-prior-*/SUMMARY.md
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

## Severity Rules

- Default severity is MEDIUM.
- Upgrade to HIGH if the recommendation addresses a HIGH or CRITICAL risk (e.g., "add input sanitization" recurring across security-focused audits).
- If no prior summaries exist, skip this step entirely.
- Update STATUS.md with recommendation escalation completion (how many items escalated, or "skipped — no prior summaries").

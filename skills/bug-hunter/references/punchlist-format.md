# Punchlist Format

## Item Template

```markdown
### BH-{NNN}: {title}
**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Category:** {from taxonomy below}
**Location:** `path/to/file.py:NN`
**Status:** OPEN | IN PROGRESS | RESOLVED | DEFERRED
**Pattern:** {PAT-NNN if applicable}

**Problem:** {What's wrong. Actual vs expected behavior. 1-3 sentences.}

**Evidence:** {How found. Code snippet, doc quote, or grep result.}

**Acceptance Criteria:**
- [ ] {Testable condition that must be true when fixed}
- [ ] {Validation: the test that proves it}

**Validation Command:**
```bash
{exact command to verify}
```

**Resolution:** {After fix: commit hash, test name, brief description}
```

## Severities
- **CRITICAL:** Data loss, security vuln, crash in production path. Fix immediately.
- **HIGH:** Incorrect documented behavior, test hiding bugs. This cycle.
- **MEDIUM:** Edge case failures, missing tests, doc drift. Next cycle.
- **LOW:** Code quality, minor inconsistencies. As time permits.

## Categories
`bug/logic` `bug/state` `bug/error-handling` `bug/security` `bug/type`
`test/missing` `test/bogus` `test/mock-abuse` `test/fragile` `test/shallow` `test/integration-gap`
`doc/drift` `doc/missing`
`design/coupling` `design/duplication` `design/dead-code` `design/inconsistency`

## Pattern Block
```markdown
## Pattern: PAT-{NNN}: {name}
**Instances:** BH-003, BH-007, BH-012
**Root Cause:** {Why this class exists}
**Systemic Fix:** {What prevents the entire class}
**Detection Rule:** {grep/lint rule for future instances}
```

## File Structure
```markdown
# Bug Hunter Punchlist
> Generated: {date} | Project: {name} | Baseline: {N pass, M fail, K skip}

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|

## Patterns
{pattern blocks}

## Items
{items ordered by severity then ID}
```

## Rules
- Resolved items stay (audit trail). Update status + fill Resolution field.
- After status change: update summary table counts and pattern block if applicable.

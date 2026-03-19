# Punchlist Format

## Item Template

````markdown
### BH-{NNN}: {title}
**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Category:** {from taxonomy below}
**Location:** `path/to/file.py:NN`
**Status:** OPEN | IN PROGRESS | RESOLVED | DEFERRED
**Pattern:** {PAT-NNN if applicable}
**Determinism:** {deterministic | intermittent | theoretical} ← bug/* categories only, optional for others
**Investigation:** {`docs/holtz/investigations/BH-{NNN}.md` if complex, omit if straightforward}

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
**Root Cause Confidence:** {LOW/MEDIUM/HIGH — for items that went through investigation}
````

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

## Determinism Values

For `bug/*` categories, assess determinism during Phase 3 (adversarial audit):

- **deterministic** — reliably triggered by a specific input or sequence
- **intermittent** — occurs under some conditions but not all (timing, load, ordering)
- **theoretical** — identified from code analysis, not yet observed in practice (race conditions, uncovered paths)

This informs the reproduction strategy in Phase 4. Deterministic bugs get a standard reproduction test. Intermittent bugs get statistical reproduction (loop test N times). Theoretical bugs may require the can't-reproduce protocol.

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
# Holtz Punchlist
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
- Determinism, Investigation, and Root Cause Confidence fields are optional. Only add them when relevant.
- Items deferred due to can't-reproduce must include evidence of reproduction attempts in the Evidence section or the linked investigation file.

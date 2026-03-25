# Architecture Baseline Format

This file defines the format for `docs/holtz/architecture-baseline.md` — the document Holtz uses to record a project's architectural structure at baseline time and track structural drift across audit runs. It is created during Steps 0-4 (recon) on the first run and compared against on subsequent runs.

The baseline captures two kinds of information: what the project *says* its architecture is (from docs) and what the code *actually does* (from structural analysis). Drift is the gap between what was true at baseline and what is true now.

## File Location

`docs/holtz/architecture-baseline.md` in the target project.

## Template

````markdown
# Architecture Baseline

**Project:** {name}
**Established:** {ISO date — when the baseline was first created}
**Last Updated:** {ISO date — when the baseline was last modified}

## Documented Intent

{Extracted from project docs: CLAUDE.md, ARCHITECTURE.md, design docs, README.
If no architecture docs exist, write: "No documented architecture found — baseline is structural snapshot only."}

### Layering Rules
{Rules about which layers/modules may depend on which. One bullet per rule.}

- {e.g., "scripts/ depends on markdown_utils but not vice versa"}
- {e.g., "CLI layer calls business logic; business logic never imports CLI"}

### Boundaries
{Which modules own which responsibilities. One bullet per boundary.}

- {e.g., "validate_punchlist handles parsing, convergence_check handles tracking"}
- {e.g., "auth/ owns all authentication; no auth logic exists outside auth/"}

### Conventions
{Naming, structural, and organizational conventions documented or implied by project docs.}

- {e.g., "test files mirror source files: test_{name}.py"}
- {e.g., "all API endpoints defined in routes/, handlers in controllers/"}

### Invariants
{Properties the codebase promises to maintain. Statements that should always be true.}

- {e.g., "all field extraction uses masked content, never raw"}
- {e.g., "every public function has a docstring"}

## Structural Snapshot

{Inferred from code analysis at baseline time. This section reflects what the code
actually does, regardless of what the docs say.}

### Module Dependencies

{Adjacency list or table showing who imports whom. Cover all significant modules.
Minor utility imports (stdlib, common helpers) can be omitted for clarity.}

| Module | Depends On |
|--------|-----------|
| {module_a} | {module_b, module_c} |
| {module_b} | {module_d} |
| {module_c} | {module_d, module_e} |
| {module_d} | {(none)} |

### Layering Direction

{Assessment of the dependency graph's directionality. Is it clean top-down,
circular, or spaghetti? Identify the layers and their order.}

**Assessment:** {clean top-down | mostly clean with exceptions | circular dependencies present | no clear layering}

**Layers (top to bottom):**
1. {e.g., CLI / entry points}
2. {e.g., business logic / core}
3. {e.g., utilities / data access}

**Exceptions:**
- {e.g., "module_b imports from module_a (reverse of expected direction)"}

### Naming Conventions

{Observed patterns in file, function, class, and variable naming. Record what the code
actually does, not what the docs say it should do.}

- **Files:** {e.g., "snake_case, test files prefixed with test_"}
- **Functions:** {e.g., "snake_case, private functions prefixed with _"}
- **Classes:** {e.g., "PascalCase, no prefix/suffix conventions observed"}
- **Modules/Packages:** {e.g., "snake_case, one word preferred"}

### Boundary Clarity

{How clean are the module boundaries? Do modules reach into each other's internals?
Are responsibilities well-separated or blurred?}

**Assessment:** {clean boundaries | mostly clean | some boundary erosion | significant overlap}

**Observations:**
- {e.g., "parsing logic is well-contained in parser/"}
- {e.g., "config.py is imported by 15 modules — potential god object"}
- {e.g., "utils.py contains unrelated functions from multiple domains"}

## Drift Log

{Appended on subsequent runs. Each entry records a detected deviation from the
baseline. Entries are never deleted, even if the drift is accepted and the baseline
is updated — the log is the historical record.}

### {ISO date}: {drift description}
**Type:** {dependency-reversal | boundary-erosion | convention-violation | layering-breach}
**Evidence:** {what changed and when, from git history or code analysis}
**Severity:** {LOW | MEDIUM | HIGH}
**Punchlist item:** {BH-NNN if escalated, "not escalated" if intentional or trivial}
````

## Drift Types and Severities

| Drift Type | Description | Default Severity |
|-----------|-------------|-----------------|
| `dependency-reversal` | A new dependency exists in the opposite direction of the established pattern | MEDIUM |
| `boundary-erosion` | A module's public surface has expanded beyond its intended scope, or a responsibility has leaked into a module that should not own it | MEDIUM |
| `convention-violation` | New code does not follow established naming or structural conventions | LOW |
| `layering-breach` | A lower-level module now depends on a higher-level one, breaking the layer hierarchy | HIGH |

**Severity escalation:** The default severity should be increased when:
- The drift is in a critical path (error handling, security, data integrity)
- The drift creates a circular dependency where none existed
- Multiple drift entries of the same type accumulate in the same area

**Severity reduction:** The default severity can be decreased when:
- The drift is in test code, scripts, or non-production paths
- The drift is a single, isolated instance with no systemic risk

## Baseline Update Rules

The baseline is not immutable. When drift is detected and determined to be intentional (the project's architecture has deliberately changed), update the baseline:

1. **Update Structural Snapshot** to reflect the new reality. Change the Module Dependencies table, Layering Direction, Naming Conventions, or Boundary Clarity sections as needed.
2. **Update Documented Intent** if the project's docs were also updated to reflect the change. If the docs were NOT updated, file a `doc/drift` punchlist item — the architecture changed but the docs did not.
3. **Drift Log retains the history.** The entry stays in the log even after the baseline is updated. The log records that the change happened, when, and why it was accepted. This is the audit trail.
4. **Update `Last Updated` date** to today's date.
5. **Do NOT update `Established` date.** That records when the baseline was originally created.

## Worked Examples

### Example 1: Dependency Reversal (escalated)

```markdown
### 2026-02-15: utils.py now imports from cli.py
**Type:** dependency-reversal
**Evidence:** Commit a1b2c3d (2026-02-10) added `from cli import parse_args` to utils.py.
Previously utils.py had zero imports from the CLI layer. git log --oneline utils.py
shows this is the first CLI import in the file's 18-month history.
**Severity:** HIGH
**Punchlist item:** BH-042
```

The established baseline showed `cli.py → utils.py` (CLI depends on utils). The new import reverses this direction. Default severity for dependency-reversal is MEDIUM, escalated to HIGH because this creates a circular dependency where none existed (per the escalation rules above). Utility modules should not depend on the CLI layer.

### Example 2: Boundary Erosion (escalated)

```markdown
### 2026-03-01: auth logic added to routes/api.py
**Type:** boundary-erosion
**Evidence:** Commit d4e5f6a (2026-02-28) added a 40-line token validation function
directly in routes/api.py. The Documented Intent states "auth/ owns all authentication;
no auth logic exists outside auth/". git diff d4e5f6a shows the function duplicates
logic already present in auth/tokens.py.
**Severity:** MEDIUM
**Punchlist item:** BH-051
```

The boundary between `auth/` and `routes/` has eroded. The new code duplicates existing auth logic in a module that should delegate to `auth/`. Escalated because duplicated auth logic is a security risk (fixes to one copy may not be applied to the other).

### Example 3: Convention Violation (not escalated — intentional)

```markdown
### 2026-03-10: new test file uses class-based tests
**Type:** convention-violation
**Evidence:** Commit b7c8d9e (2026-03-09) added test_optimizer.py using unittest.TestCase
classes. The established convention is function-based pytest tests (observed in 23 of
24 existing test files). However, the commit message states "using TestCase for setUp/
tearDown lifecycle in optimizer tests" and the project's CONTRIBUTING.md was updated
in the same commit to note this exception.
**Severity:** LOW
**Punchlist item:** not escalated
```

This is an intentional convention violation. The baseline was updated: Naming Conventions now notes "test files use function-based pytest, except test_optimizer.py which uses TestCase for lifecycle management." The Drift Log entry remains as a historical record.

**Baseline update performed:**
- Naming Conventions updated to document the exception
- Documented Intent updated (CONTRIBUTING.md was already updated by the developer)
- `Last Updated` set to 2026-03-10

### Example 4: Layering Breach (escalated)

```markdown
### 2026-03-18: data access layer imports business logic
**Type:** layering-breach
**Evidence:** Commit c9d0e1f (2026-03-17) added `from core.pricing import calculate_discount`
to db/queries.py. The Structural Snapshot shows a clean three-layer architecture:
routes → core → db. This import makes db depend on core, creating a circular
dependency (core → db → core). git log --all --oneline -- db/queries.py confirms
this is the first import from core/ in any db/ file.
**Severity:** HIGH
**Punchlist item:** BH-063
```

This is a layering breach — the data access layer now depends on the business logic layer, violating the established top-down layering. Severity is HIGH because layering breaches create circular dependencies and make the system harder to reason about. Escalated to the punchlist for resolution.

## Rules

- **Create once, append forever.** The baseline is created on the first Holtz run. Subsequent runs append to the Drift Log and may update the Structural Snapshot and Documented Intent per the update rules above.
- **Drift Log is append-only.** Never delete or edit drift entries. They are the historical record of architectural changes.
- **Evidence must be specific.** Cite commit hashes, file names, line counts, and git history. "Something changed" is not evidence.
- **Structural Snapshot reflects code, not docs.** If the code disagrees with the docs, the snapshot records what the code does. The disagreement itself may be a `doc/drift` punchlist item.
- **Two kinds of drift.** Structural drift is measured as change from the prior Structural Snapshot (dependency graph, layering, boundaries). Intent drift is measured as deviation from the Documented Intent (stated invariants, boundaries, layering rules). Both are checked during Step 0. Structural drift detects changes the code has undergone; intent drift detects promises the code has broken. Step 6 (doc-to-implementation audit) checks specific testable claims — Step 0 checks architectural-level claims that Step 6's claim-by-claim approach may not catch.
- **Baseline updates require justification.** When updating the baseline to accept drift, the drift log entry should explain why the change was accepted. Do not silently update the baseline.
- **First-run behavior:** If no `docs/holtz/architecture-baseline.md` exists, create one during Steps 0-4 recon. Populate Documented Intent from project docs and Structural Snapshot from code analysis. The Drift Log starts empty.
- **Subsequent-run behavior:** If the baseline exists, compare the current code structure against the Structural Snapshot. Any differences become Drift Log entries. Then proceed with the normal audit steps.

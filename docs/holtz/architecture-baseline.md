# Architecture Baseline

**Project:** holtz
**Established:** 2026-03-22
**Last Updated:** 2026-03-22

## Documented Intent

README describes a two-layer architecture:
1. Markdown protocol layer (SKILL.md, references, patterns) consumed by the LLM
2. Python tool layer (CLI scripts) called by the LLM for concrete operations

No CLAUDE.md or ARCHITECTURE.md exists. Intent is inferred from README, SKILL.md, and pyproject.toml.

### Layering Rules

- `markdown_utils.py` is the shared leaf module — imported by validators and convergence tracker but imports nothing from the project
- `validate_punchlist.py` and `convergence_check.py` depend on `markdown_utils.py` but not on each other
- `impact_graph.py` is standalone — no internal imports
- Tests depend on source modules (one-way); source never imports from tests

### Boundaries

- `markdown_utils.py` owns all CommonMark fence state tracking
- `validate_punchlist.py` owns punchlist parsing and validation
- `convergence_check.py` owns convergence tracking, test runner detection, and output parsing
- `impact_graph.py` owns knowledge graph operations
- All JSON persistence uses atomic writes (tempfile + rename)

### Conventions

- Source files: `snake_case.py` in `skills/holtz/scripts/`
- Test files: `test_{name}.py` in `tests/`, using pytest function-based style
- Support files: `conftest.py` (shared fixtures), `runner_fixtures.py` (test runner output samples)
- Punchlist items: `BH-NNN` namespace (Holtz), `BJ-NNN` namespace (Justine)
- Patterns: `PAT-NNN` namespace
- All regex in source uses `[ \t]` not `\s` for horizontal whitespace

### Invariants

- All punchlist field extraction uses masked content for boundary detection, original content for extraction
- `mask_code_fences` preserves line count (masked line N = original line N)
- Both `count_items` and `parse_punchlist` split on `### BH-NNN:` headers in masked content
- `save_history` and `ImpactGraph.save` use atomic writes (no partial-write corruption)
- Test runner parsers return `None` for unparseable output (not zero-count dicts)

## Structural Snapshot

### Module Dependencies

| Module | Depends On |
|--------|-----------|
| `validate_punchlist.py` | `markdown_utils.py` |
| `convergence_check.py` | `markdown_utils.py` |
| `impact_graph.py` | (none — standalone) |
| `markdown_utils.py` | (none — leaf) |
| `hooks/_common.py` | (none — hook leaf) |
| `hooks/impact_graph_gate.py` | `hooks/_common.py` |
| `hooks/status_staleness_gate.py` | `hooks/_common.py` |
| `hooks/artifact_verification.py` | `hooks/_common.py` |
| `hooks/subagent_findings_check.py` | `hooks/_common.py` |

### Layering Direction

**Assessment:** clean top-down

**Layers (top to bottom):**
1. Application layer: `validate_punchlist.py`, `convergence_check.py`, `impact_graph.py`
2. Hook layer: `impact_graph_gate.py`, `status_staleness_gate.py`, `artifact_verification.py`, `subagent_findings_check.py`
3. Utility layer: `markdown_utils.py`, `hooks/_common.py`

**Exceptions:**
- Scripts and hooks are independent — no cross-layer imports between them.
- Hooks use `sys.path.insert` for intra-directory imports (not a package).

### Naming Conventions

- **Files:** snake_case, test files prefixed with `test_`
- **Functions:** snake_case, private functions prefixed with `_`
- **Classes:** PascalCase (`PunchlistItem`, `ValidationResult`, `ImpactGraph`)
- **Constants:** UPPER_SNAKE_CASE (`VALID_SEVERITIES`, `FIELD_NAMES`, `DRIFT_LINE_THRESHOLD`)

### Boundary Clarity

**Assessment:** clean boundaries

**Observations:**
- Parsing logic well-contained in `validate_punchlist.py`
- Fence state machine cleanly isolated in `markdown_utils.py`
- Impact graph fully self-contained with no leaked internals
- `convergence_check.py` contains both test runner detection AND convergence logic — two responsibilities, but they're cohesive (convergence depends on test results)

## Drift Log

### 2026-03-22 (Run 8)

**1. New component: `hooks/` layer** — Severity: LOW
- 4 Python hook files + `hooks.json` manifest + `_common.py` shared utilities added since baseline
- Not documented in Structural Snapshot or Module Dependencies
- Uses `sys.path.insert` for intra-directory imports (not a package)
- Layering: hooks import `_common.py` only (flat, no upward deps) — clean

**2. Broken dependency: pytest-cov** — Severity: MEDIUM
- `pyproject.toml` `addopts` references `--cov=skills/holtz/scripts` but pytest-cov is not installed
- Violates invariant: default `pytest` command should work
- Convention violation: documented test runner convention broken

**3. Linter scope gap** — Severity: LOW
- `ruff` and `mypy` are configured for `skills/holtz/scripts/` only
- `hooks/` has 7 ruff errors, not covered by mypy
- Convention violation: new code not under established linting

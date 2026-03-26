# Architecture Baseline

**Project:** holtz
**Established:** 2026-03-22
**Last Updated:** 2026-03-26 (Run 20)

## Documented Intent

README describes a two-layer architecture:
1. Markdown protocol layer (SKILL.md, references, patterns) consumed by the LLM
2. Python tool layer (CLI scripts) called by the LLM for concrete operations

README also documents: 16 seed patterns, 13 analytical lenses, 19 runs of self-audit history, and a summary count of "1 skill, 3 agents, 18 reference docs, 1 example, 6 Python scripts, 16 seed patterns, 6 enforcement hooks, 647 tests across 14,300 lines of code." Counts verified accurate as of Run 20 (647 tests confirmed by `python -m pytest`).

CLAUDE.md defines branch model (main/dev/feature), conventional commit format, release workflow, and test commands. Intent is also inferred from README, SKILL.md, and pyproject.toml.

### Layering Rules

- `markdown_utils.py` is the shared leaf module for scripts — imported by validators and convergence tracker but imports nothing from the project
- `hooks/_common.py` is the shared leaf module for hooks — imported by all hook scripts but imports nothing from the project (parallel to `markdown_utils.py` for the scripts layer)
- `validate_punchlist.py`, `convergence_check.py`, and `pattern_brief_compact.py` depend on `markdown_utils.py` but not on each other
- `impact_graph.py` and `profiler_plugin.py` are standalone — no internal imports
- Tests depend on source modules (one-way); source never imports from tests

### Boundaries

- `markdown_utils.py` owns all CommonMark fence state tracking for scripts
- `hooks/_common.py` owns hook I/O protocol (JSON stdin/stdout), exit helpers, and fence masking for hooks (`mask_fenced_blocks` — parallel to `mask_code_fences` in `markdown_utils.py`, kept separate to avoid cross-layer imports)
- `validate_punchlist.py` owns punchlist parsing and validation
- `convergence_check.py` owns convergence tracking, test runner detection, output parsing, and punchlist path resolution (`_resolve_punchlist_path` with merged-file preference, argparse CLI)
- `impact_graph.py` owns knowledge graph operations
- `convergence_gate.py` owns stop-event blocking until audit converges (reads STATUS.md, checks staleness)
- `convergence_primer.py` owns resume-context injection on UserPromptSubmit (reads STATUS.md fields, primes model to continue)
- `pattern_brief_compact.py` owns pattern brief parsing and compact formatting for subagent consumption (reads `patterns-brief.md`, outputs oneliner/twoliner/structured formats)
- `profiler_plugin.py` owns Holtz-specific session-type detection and step patterns for the token profiler (standalone plugin loaded at runtime; detection uses `isinstance` against `@runtime_checkable` `ProfilerPlugin` Protocol in `plugin_protocol.py`)
- `scripts/token_profiler/` package owns session token-usage analysis: extraction (`extract.py`), analysis pipeline (`analyze.py`), pricing (`pricing.py`), report generation (`report.py`), interactive HTML viewer (`viewer.py`), CLI orchestration (`cli.py`), plugin protocol (`plugin_protocol.py`), and data models (`models.py`)
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
- Default `python -m pytest` command works (pytest-cov installed; `addopts` covers both `skills/holtz/scripts/` and `hooks/`)

## Structural Snapshot

### Module Dependencies

| Module | Depends On |
|--------|-----------|
| `validate_punchlist.py` | `markdown_utils.py` |
| `convergence_check.py` | `markdown_utils.py` |
| `pattern_brief_compact.py` | `markdown_utils.py` (deferred/in-function import) |
| `profiler_plugin.py` | (none — standalone; TYPE_CHECKING-only ref to `token_profiler.models`) |
| `impact_graph.py` | (none — standalone) |
| `markdown_utils.py` | (none — leaf) |
| `hooks/_common.py` | (none — hook leaf) |
| `hooks/impact_graph_gate.py` | `hooks/_common.py` |
| `hooks/status_staleness_gate.py` | `hooks/_common.py` |
| `hooks/artifact_verification.py` | `hooks/_common.py` |
| `hooks/subagent_findings_check.py` | `hooks/_common.py` |
| `hooks/convergence_gate.py` | `hooks/_common.py` |
| `hooks/convergence_primer.py` | `hooks/_common.py` |
| `token_profiler/models.py` | (none — leaf) |
| `token_profiler/plugin_protocol.py` | `token_profiler/models.py` |
| `token_profiler/extract.py` | `token_profiler/models.py` |
| `token_profiler/pricing.py` | `token_profiler/models.py` |
| `token_profiler/analyze.py` | `token_profiler/models.py` |
| `token_profiler/report.py` | `token_profiler/models.py` |
| `token_profiler/viewer.py` | `token_profiler/models.py` |
| `token_profiler/__main__.py` | `token_profiler/cli.py` |
| `token_profiler/cli.py` | `token_profiler/analyze.py`, `token_profiler/extract.py`, `token_profiler/plugin_protocol.py`, `token_profiler/pricing.py`, `token_profiler/report.py`, `token_profiler/viewer.py` (deferred) |

### Layering Direction

**Assessment:** clean top-down

**Layers (top to bottom):**
1. Application layer: `validate_punchlist.py`, `convergence_check.py`, `impact_graph.py`, `pattern_brief_compact.py`, `profiler_plugin.py`
2. Hook layer: `impact_graph_gate.py`, `status_staleness_gate.py`, `artifact_verification.py`, `subagent_findings_check.py`, `convergence_gate.py`, `convergence_primer.py`
3. Utility layer: `markdown_utils.py`, `hooks/_common.py`

**Independent package (separate tree):**
- `scripts/token_profiler/`: `__main__.py` is a thin entry-point wrapper (`python -m token_profiler`) that imports only `cli.py`; `cli.py` is the sole orchestrator importing `analyze.py`, `extract.py`, `plugin_protocol.py`, `pricing.py`, `report.py` (all top-level) and `viewer.py` (deferred, inside a function); all sibling modules depend only on `models.py` as the shared leaf; no cross-tree imports at runtime

**Exceptions:**
- Scripts and hooks are independent — no cross-layer imports between them.
- Hooks use `sys.path.insert` for intra-directory imports (not a package).
- `profiler_plugin.py` (scripts layer) has a TYPE_CHECKING-only reference to `token_profiler.models` — not a runtime import, not a layering violation.

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
- `pattern_brief_compact.py` well-contained: parses one input format, produces compact output, depends only on `markdown_utils` for fence masking
- `profiler_plugin.py` fully standalone: implements `@runtime_checkable` `ProfilerPlugin` Protocol, no runtime project imports (TYPE_CHECKING-only reference to external `token_profiler.models`)
- `scripts/token_profiler/` package is fully self-contained: clean internal star topology, no imports from `skills/holtz/scripts/` or `hooks/`, loaded externally via CLI `--plugin` flag

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

### 2026-03-24 (Run 16)

**1. Line drift in convergence_check.py** — Severity: LOW
- `check_convergence` shifted from line 280 to 293 (+13 lines)
- `save_history` shifted from line 247 to 260 (+13 lines)
- Cause: Run 15 fixes added ~13 lines of validation logic upstream
- No structural or behavioral change — function signatures and dependencies unchanged
- Impact graph nodes updated via drift_check

**2. No new dependency reversals, boundary erosions, convention violations, or layering breaches detected.**
- All modules maintain established dependency directions
- No cross-layer imports between hooks/ and scripts/
- Linter and type checker gaps from Run 8 drift #3 remain addressed (mypy now covers hooks/)

### 2026-03-25 (Run 19)

**1. README hardcoded counts stale after pattern/lens additions** — Severity: MEDIUM
- "Fourteen seed patterns" / "14 seed patterns" → actually 16 (numeric-precision-exhaustion, cross-language-dead-interface added)
- "nine analytical lenses" / "all nine lenses" → actually 13 (concurrency, resource-lifecycle, idempotency, observability added)
- "Sixteen runs" → 18+ runs completed
- Cause: 5 feat commits (6a79f0f, 92e9e5f, 4e4cf0a, d77ba1d, b85a98a) added patterns and lenses without updating README counts
- Recurring drift class: README count staleness has appeared in Runs 13, 14, 16, 18, now 19

**2. Continuing line drift in convergence_check.py** — Severity: LOW
- `check_convergence` shifted from line 280→296 (+16 from baseline)
- `save_history` shifted from line 247→260 (+13 from baseline)
- Same drift as Run 16, no further structural change — 5 recent feat commits are all markdown

**3. No new dependency reversals, boundary erosions, convention violations, or layering breaches detected.**
- No Python source changed since Run 18 — all 5 recent commits are markdown (patterns, lenses, SKILL.md)
- All modules maintain established dependency directions
- No cross-layer imports between hooks/ and scripts/

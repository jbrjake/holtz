# Architecture Baseline

**Project:** holtz
**Established:** 2026-03-29
**Last Updated:** 2026-03-29 (structural snapshot refresh)

## Documented Intent

From CLAUDE.md and README: Holtz is a Claude Code plugin providing adversarial TDD-driven bug identification and resolution. Dual auditors (Holtz + Justine) run parallel audits with convergence enforcement via the Sahjhan protocol engine.

### Layering Rules

- `skills/holtz/scripts/` are standalone Python utilities with no cross-imports to `enforcement/` or `hooks/`; `markdown_utils` is the only intra-scripts dependency (used by `validate_punchlist` and `convergence_check`)
- `enforcement/hooks/` hook scripts depend on internal shared modules (`_common.py` bridge, `_protocol_cache.py`, `_resolve.py`); they never import from `skills/holtz/scripts/`
- `hooks/_common.py` is the single owner of hook I/O protocol helpers; `enforcement/hooks/_common.py` re-exports it via importlib — the dependency is one-directional (enforcement → hooks, never hooks → enforcement)
- `enforcement/` config files (TOML, JSON) are consumed by the Sahjhan binary, not imported by Python
- `scripts/token_profiler/` is a self-contained dev package; `models.py` is the leaf all other submodules depend on; no runtime imports flow outward to other project modules
- `skills/holtz/scripts/profiler_plugin.py` uses a TYPE_CHECKING guard to prevent any runtime import of `token_profiler`; at runtime it is stdlib-only

### Boundaries

- `impact_graph.py` owns graph operations (nodes, edges, risk scores, blast radius); no `skills/` module imports from it
- `validate_punchlist.py` owns punchlist parsing, validation, filtering, and rendering; `convergence_check.py` calls `count_items()` which reads the file directly — it does not re-parse items
- `convergence_check.py` owns test runner detection and convergence gate checks
- `pattern_brief_compact.py` owns pattern library formatting
- `markdown_utils.py` owns code-fence parsing and masking for the scripts layer; fence masking is independently replicated in `hooks/_common.py` to avoid cross-layer imports (intentional, documented)
- `_protocol_cache.py` owns all Sahjhan state: cache read/write, status parsing, obligation computation, command detection; no other module writes to the enforcement cache
- `_resolve.py` owns Sahjhan binary path resolution; no other module hardcodes the binary path
- `_sahjhan_bootstrap.py` owns Sahjhan process lifecycle (ensure binary present before guarded tools)
- `lens_quiz.py` owns quiz lifecycle (pose, score, evidence); it depends on `lens_evidence.py`
- `lens_evidence.py` owns transcript analysis for lens evidence; no hook depends on it except `lens_quiz.py`
- `primer.py` owns resume context injection after /clear; it reads enforcement cache via `_protocol_cache.py`
- `token_profiler/models.py` owns all token profiler data structures; it is a pure leaf with no intra-package imports

### Conventions

- Test files mirror source: `test_{name}.py`; integration tests named `test_{scope}_integration.py`; test infrastructure in `tests/conftest.py` and `tests/runner_fixtures.py`
- Conventional commits required (feat/fix/perf bump `.claude-plugin/plugin.json` version via post-commit hook)
- Branch model: `main` (releases only), `dev` (integration), feature branches (`feat/name`, `fix/name`) target dev; no direct pushes to main
- Plugin markdown (SKILL.md, references/, agents/, patterns/) are functional deliverables — changes use `feat:`/`fix:`, not `docs:`; `docs:` is reserved for README, CHANGELOG, CONTRIBUTING
- Hook scripts are invoked as standalone Python scripts (`if __name__ == "__main__":`) with no package structure; each hook file is self-contained at invocation time
- Internal/private modules prefixed with `_` (e.g., `_common.py`, `_protocol_cache.py`, `_resolve.py`, `_sahjhan_bootstrap.py`)
- Coverage flag (`--cov`) is excluded from default pytest `addopts` to prevent deadlock from concurrent subagent sessions sharing the SQLite `.coverage` file

### Invariants

- All protocol state mediated by Sahjhan CLI — no direct writes to STATUS.md or PUNCHLIST.md; `write_guard.py` enforces this at hook level
- Impact graph uses atomic writes (tempfile + os.replace)
- `_REQUIRED_NODE_KEYS` enforces `{id, type, file}` on load; `_REQUIRED_EDGE_KEYS` enforces `{source, target, type}`
- Quiz bank entries reference source file paths for answer verification
- All punchlist parsing uses masked content (`mask_code_fences`) before applying regex; raw content is never parsed for structured fields
- All hook scripts exit 0; control signals are encoded in the stdout JSON payload, not the exit code
- `hooks/_common.py` is the single implementation of hook I/O protocol helpers; enforcement hooks re-export these via the bridge — no duplication of exit logic

## Structural Snapshot

### Module Dependencies

| Module | Depends On |
|--------|-----------|
| `skills/holtz/scripts/markdown_utils.py` | (none — stdlib only) |
| `skills/holtz/scripts/validate_punchlist.py` | `markdown_utils` |
| `skills/holtz/scripts/convergence_check.py` | `markdown_utils` |
| `skills/holtz/scripts/impact_graph.py` | (none — stdlib only) |
| `skills/holtz/scripts/pattern_brief_compact.py` | (none — stdlib only) |
| `skills/holtz/scripts/profiler_plugin.py` | `token_profiler.models` (TYPE_CHECKING only — no runtime import) |
| `hooks/_common.py` | (none — stdlib only) |
| `hooks/subagent_findings_check.py` | `hooks/_common.py` |
| `enforcement/hooks/_common.py` | `hooks/_common.py` (via importlib dynamic load) |
| `enforcement/hooks/_protocol_cache.py` | (none — stdlib only; tomllib optional) |
| `enforcement/hooks/_resolve.py` | (none — stdlib only) |
| `enforcement/hooks/_sahjhan_bootstrap.py` | (none — stdlib only) |
| `enforcement/hooks/lens_evidence.py` | (none — stdlib only) |
| `enforcement/hooks/write_guard.py` | `enforcement/hooks/_common.py` |
| `enforcement/hooks/verify_hooks.py` | (none — stdlib only) |
| `enforcement/hooks/bash_guard.py` | `enforcement/hooks/_resolve.py`, `enforcement/hooks/_common.py` |
| `enforcement/hooks/commit_gate.py` | `enforcement/hooks/_protocol_cache.py`, `enforcement/hooks/_common.py` |
| `enforcement/hooks/lens_quiz.py` | `enforcement/hooks/_resolve.py`, `enforcement/hooks/lens_evidence.py`, `enforcement/hooks/_common.py` |
| `enforcement/hooks/primer.py` | `enforcement/hooks/_protocol_cache.py`, `enforcement/hooks/_resolve.py`, `enforcement/hooks/_common.py` |
| `enforcement/hooks/protocol_tracker.py` | `enforcement/hooks/_protocol_cache.py`, `enforcement/hooks/_resolve.py`, `enforcement/hooks/_common.py` |
| `enforcement/hooks/stop_gate.py` | `enforcement/hooks/_protocol_cache.py`, `enforcement/hooks/_resolve.py`, `enforcement/hooks/_common.py` |
| `scripts/token_profiler/models.py` | (none — stdlib only) |
| `scripts/token_profiler/pricing.py` | `token_profiler.models` |
| `scripts/token_profiler/plugin_protocol.py` | `token_profiler.models` |
| `scripts/token_profiler/extract.py` | `token_profiler.models` |
| `scripts/token_profiler/analyze.py` | `token_profiler.models` |
| `scripts/token_profiler/report.py` | `token_profiler.models` |
| `scripts/token_profiler/viewer.py` | `token_profiler.models` |
| `scripts/token_profiler/cli.py` | `token_profiler.analyze`, `token_profiler.extract`, `token_profiler.plugin_protocol`, `token_profiler.pricing`, `token_profiler.report`, `token_profiler.viewer` (lazy) |
| `scripts/token_profiler/__main__.py` | `token_profiler.cli` |
| `scripts/migrate_legacy.py` | `markdown_utils` (sys.path cross-tree, dev-only) |
| `enforcement/scripts/generate_quiz_bank.py` | (none — stdlib only) |

### Entry Points

**Plugin artifacts (not Python):**
- `bin/sahjhan` — Sahjhan CLI binary (platform-specific, resolved by `_resolve.py`)
- `skills/holtz/SKILL.md` — main skill entry point (loaded by Claude Code harness)
- `agents/holtz.md`, `agents/justine.md`, `agents/merge-agent.md` — agent definitions

**Hook entry points (invoked by Claude Code harness via `hooks/hooks.json`):**
- `enforcement/hooks/_sahjhan_bootstrap.py` — PreToolUse(Write|Edit|Read)
- `enforcement/hooks/write_guard.py` — PreToolUse(Write|Edit)
- `enforcement/hooks/commit_gate.py` — PreToolUse(Bash)
- `enforcement/hooks/bash_guard.py` — PostToolUse(Bash)
- `enforcement/hooks/protocol_tracker.py` — PostToolUse(Bash)
- `enforcement/hooks/stop_gate.py` — Stop
- `enforcement/hooks/primer.py` — UserPromptSubmit
- `hooks/subagent_findings_check.py` — SubagentStop
- `enforcement/hooks/lens_quiz.py` — SubagentStop

**Script entry points (invoked by audit skill or SKILL.md):**
- `skills/holtz/scripts/validate_punchlist.py` (`main()`) — punchlist validation CLI
- `skills/holtz/scripts/convergence_check.py` — convergence assessment (script-mode, no `main()`)
- `skills/holtz/scripts/impact_graph.py` (`main()`) — impact graph operations CLI
- `skills/holtz/scripts/pattern_brief_compact.py` (`main()`) — compact pattern brief for subagents
- `scripts/token_profiler/__main__.py` → `cli.main()` — token profiler CLI (`python -m token_profiler`)

**Dev/maintenance entry points:**
- `scripts/generate-changelog.py` — changelog generation from git log
- `scripts/migrate_legacy.py` — migrate legacy run data formats
- `enforcement/scripts/generate_quiz_bank.py` — generate quiz bank from protocol definition
- `enforcement/hooks/verify_hooks.py` — verify hooks manifest integrity

### Export Surface

**`skills/holtz/scripts/markdown_utils.py`** (imported by `validate_punchlist`, `convergence_check`, `migrate_legacy`):
- `mask_code_fences(content: str) -> tuple[str, str]`
- `has_unclosed_fence(content: str) -> bool`

**`skills/holtz/scripts/validate_punchlist.py`** (imported by tests):
- `PunchlistItem` (dataclass), `ValidationResult` (dataclass)
- `parse_punchlist(content: str, ...) -> list[PunchlistItem]`
- `filter_items(...)`, `render_items(...) -> str`
- `validate(items, content, masked_content) -> ValidationResult`

**`skills/holtz/scripts/convergence_check.py`** (imported by tests):
- `count_items(punchlist_path: Path) -> dict`
- `detect_test_runner(project_root) -> str | None`
- `get_test_counts(runner) -> dict | None`

**`skills/holtz/scripts/impact_graph.py`** (imported by tests):
- `ImpactGraph` class with `add_node`, `add_edge`, `update_risk`, `blast_radius`, `prune_stale`, `save`, `load` methods

**`hooks/_common.py`** (imported by `hooks/subagent_findings_check.py`; re-exported by `enforcement/hooks/_common.py`):
- `read_event() -> dict`
- `exit_ok(event_name)`, `exit_warn(msg)`, `exit_block(msg)`, `exit_stop_allow()`, `exit_stop_block(reason)`
- `mask_fenced_blocks(text: str) -> str`

**`enforcement/hooks/_protocol_cache.py`** (imported by `commit_gate`, `primer`, `protocol_tracker`, `stop_gate`):
- `read_cache`, `write_cache`, `empty_cache`, `parse_status_text`
- `is_git_commit`, `is_sahjhan_cmd`, `compute_obligations`, `format_injection`, `format_state_line`

**`enforcement/hooks/_resolve.py`** (imported by `bash_guard`, `lens_quiz`, `primer`, `protocol_tracker`, `stop_gate`):
- `sahjhan_binary() -> str`

**`scripts/token_profiler/models.py`** (imported by all token_profiler submodules):
- `RawTurn`, `ContentBlock`, `ToolResult`, `Usage`, `DollarCost`, `SessionProfile`, `RunProfile` (dataclasses)

**`enforcement/hooks/lens_evidence.py`** (imported by `lens_quiz`):
- Transcript analysis functions for lens evidence; no public class

## Drift Log

| Date | Type | Description | Severity | Punchlist Items |
|------|------|-------------|----------|-----------------|
| 2026-03-29 | Node key enforcement | `_REQUIRED_NODE_KEYS` expanded from {type, file} to {id, type, file} — fixes defensive gap where load() allowed nodes that crashed downstream | LOW | BH-017 |
| 2026-03-29 | Parser output | `parse_status_text` now extracts current_perspective from bracket content instead of defaulting to "unknown" | LOW | BH-018 |

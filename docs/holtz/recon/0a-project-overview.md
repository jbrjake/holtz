# 0a: Project Overview

**Project:** holtz — Adversarial TDD audit loop plugin for Claude Code
**Language:** Python 3.12+
**Branch:** dev (integration branch, main is for releases)

## Architecture

Two-layer architecture:
1. **Markdown protocol layer** — SKILL.md, 17 reference docs, 6 seed patterns, examples, agents. Consumed by the LLM.
2. **Python tool layer** — 6 CLI scripts in `skills/holtz/scripts/`, 6 enforcement hooks in `hooks/`, standalone token profiler in `scripts/token_profiler/`.

### Source Files (non-venv, non-test)
- `skills/holtz/scripts/` — convergence_check.py, impact_graph.py, markdown_utils.py, pattern_brief_compact.py, profiler_plugin.py, validate_punchlist.py
- `hooks/` — _common.py, artifact_verification.py, convergence_gate.py, convergence_primer.py, impact_graph_gate.py, status_staleness_gate.py, subagent_findings_check.py
- `scripts/` — generate-changelog.py, session-to-cast.py, token_profiler/ (8 modules)

### Key Docs
- CLAUDE.md: branch model, conventional commits, release workflow, test commands
- README.md: full product documentation with concrete claims
- SKILL.md: the audit skill definition (rigid, 7 phases)

### Dependencies
- `markdown_utils.py` is leaf for scripts (imported by validators/convergence)
- `hooks/_common.py` is leaf for hooks (parallel to markdown_utils, no cross-layer imports)
- `impact_graph.py` is standalone
- Tests depend on source (one-way)

### Build/Config
- `pyproject.toml`: ruff (E/F/W/I/UP/B/SIM/ANN), mypy, pytest with coverage
- Coverage: `--cov=skills/holtz/scripts --cov=hooks --cov-fail-under=60`
- CI: GitHub Actions on push/PR to dev and main
- Post-commit hook: auto version bump on feat/fix/perf commits

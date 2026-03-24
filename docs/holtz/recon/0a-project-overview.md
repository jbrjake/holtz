# Step 0a: Project Overview

**Project:** holtz — Claude Code plugin for TDD-driven codebase auditing
**Language:** Python 3.12
**Run:** 14 (full audit)
**Date:** 2026-03-24

## Structure

- `skills/holtz/scripts/` — 5 Python CLI scripts (1,697 lines)
  - `validate_punchlist.py` (584) — punchlist parsing, validation, filtering, rendering
  - `convergence_check.py` (429) — convergence tracking, test runner detection, history
  - `impact_graph.py` (435) — knowledge graph: nodes, edges, risk scores, blast radius
  - `markdown_utils.py` (81) — CommonMark fence state machine
  - `pattern_brief_compact.py` (168) — pattern brief parser and compact output
- `hooks/` — 4 enforcement hooks + shared utilities (339 lines)
  - `_common.py` (79) — shared hook helpers (read_event, exit_ok/warn/block)
  - `impact_graph_gate.py` (57) — blocks audit writes without graph
  - `status_staleness_gate.py` (86) — blocks writes if STATUS.md is stale
  - `artifact_verification.py` (58) — verifies graph file exists after commands
  - `subagent_findings_check.py` (59) — verifies subagent output files exist
- `tests/` — 8 test files + fixtures (6,509 lines)
  - `test_validate_punchlist.py` (2,578) — largest test file
  - `test_convergence_check.py` (1,289)
  - `test_impact_graph.py` (983)
  - `test_hooks.py` (531)
  - `test_integration.py` (252)
  - `test_markdown_utils.py` (233)
  - `test_pattern_brief_compact.py` (76)
  - `test_pattern_brief_compact_structure.py` (83)
- Total: 21 Python files, 8,545 lines

## Recent Activity (since run 13)

5 commits since run 13 (all docs/config):
- 828f7e1: docs: remove 9 orphan nodes from impact graph
- ed3416b: docs: update impact graph for current codebase state
- 30f4dfc: docs(readme): update for v0.4.0 — new lens descriptions, inherited recon, run 13
- 7c63c65: chore: remove .claude/ from git tracking
- a3e35e9: docs: add implementation plans for token context optimizations

No source code changes since run 13. All 5 commits are docs/config only.

## Architecture

Two-layer design:
1. Markdown protocol layer (SKILL.md, references, patterns) — consumed by LLM
2. Python tool layer (CLI scripts) — called by LLM for operations

Dependencies: `markdown_utils.py` is leaf, imported by `validate_punchlist.py` and `convergence_check.py`. `impact_graph.py` standalone. Hooks import `_common.py` only.

## Configuration

- `pyproject.toml`: ruff + mypy configured for scripts and hooks
- pytest: `--cov` for scripts + hooks, no coverage threshold enforced
- Python 3.12 target (running 3.10.9)

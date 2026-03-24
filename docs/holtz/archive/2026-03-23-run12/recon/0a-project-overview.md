# Phase 0a: Project Overview

**Project:** holtz (Claude Code plugin)
**Version:** 0.3.3
**Date:** 2026-03-23
**Run:** 12

## Structure

```
.claude-plugin/plugin.json   — manifest
README.md                    — primary docs
agents/holtz.md              — Holtz agent definition
agents/justine.md            — Justine agent definition (internal-only as of 0.3.3)
hooks/                       — 4 enforcement hooks + _common.py shared utils
  _common.py                 — read_event, exit_ok, exit_warn, exit_block (JSON output format)
  hooks.json                 — hook registration (PreToolUse:Write|Edit, PostToolUse:Bash, SubagentStop)
  impact_graph_gate.py       — gates Phase 1+ writes on impact-graph.json existence
  status_staleness_gate.py   — gates findings writes on STATUS.md freshness (5 min)
  artifact_verification.py   — post-Bash verification of impact_graph.py artifacts
  subagent_findings_check.py — SubagentStop file path verification
skills/holtz/                — skill files (SKILL.md, references, patterns, examples, scripts)
tests/                       — 8 test files (pytest, function-based)
pyproject.toml               — ruff, mypy, pytest config
```

## Key Changes Since Run 11 (2026-03-22)

1. **Hook modernization** (4049532): `_common.py` rewritten — all hooks now output modern JSON format (`{"continue": bool, ...}`) instead of legacy exit codes. `exit_ok()` for PreToolUse includes `hookSpecificOutput` with `permissionDecision`. All hooks exit 0.
2. **Justine internal-only** (bc165b2): Justine agent made non-user-invokable (dispatched only by Holtz).
3. **README updates**: multiple doc commits expanding audit scope, fix loop, pattern learning sections.
4. **Version bump**: 0.3.1 → 0.3.2 → 0.3.3.

## Architecture

Two-layer: Markdown protocol (skills, references, patterns) + Python tools (CLI scripts, hooks).

**Scripts:** `validate_punchlist.py`, `convergence_check.py`, `impact_graph.py`, `markdown_utils.py`
**Hooks:** 4 enforcement hooks sharing `_common.py` utilities
**Tests:** pytest with coverage, ruff linting, mypy type checking

## README Claims (to verify in Phase 1)

- "286 tests across 8,200 lines"
- "14 reference docs"
- "6 seed patterns"
- "4 enforcement hooks"
- "2 skills, 2 agents"
- Seven phases described
- Twelve anti-patterns in test quality
- Seven edge types in impact graph
- Six analytical lenses
- Resume-not-restart default behavior

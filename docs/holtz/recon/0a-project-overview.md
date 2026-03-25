# Step 0a: Project Overview

**Project:** holtz
**Version:** 0.5.2
**Language:** Python 3.12
**Branch:** dev
**Date:** 2026-03-24

## Description

Claude Code plugin for TDD-driven codebase auditing. Dual-auditor system (Holtz depth-first, Justine breadth-first) with adversarial self-play, impact graph, pattern library, and convergence loop.

## Architecture

### Top-Level Structure
- `.claude-plugin/plugin.json` — plugin manifest (v0.5.2)
- `skills/holtz/SKILL.md` — main skill definition (rigid, 394 lines)
- `skills/holtz/references/` — 17 reference docs (process specs, formats, protocols)
- `skills/holtz/scripts/` — 6 Python scripts (convergence_check, impact_graph, markdown_utils, pattern_brief_compact, profiler_plugin, validate_punchlist)
- `skills/holtz/patterns/` — 6 seed pattern files
- `skills/holtz/examples/` — 1 sample punchlist
- `agents/` — 3 agent defs (holtz.md, justine.md, merge-agent.md)
- `hooks/` — 6 enforcement hooks + _common.py + hooks.json
- `scripts/` — install-hooks.sh, session-to-cast.py, token_profiler/
- `tests/` — 17 test files + conftest + fixtures
- `docs/` — design docs, run walkthroughs, superpowers plans/specs, holtz runtime data

### Key Modules
| Module | Purpose |
|--------|---------|
| `skills/holtz/scripts/validate_punchlist.py` | Parse and validate punchlist format, filtered reads |
| `skills/holtz/scripts/convergence_check.py` | Track convergence (clean iterations, open items) |
| `skills/holtz/scripts/impact_graph.py` | Knowledge graph (nodes, edges, risk scores, blast radius) |
| `skills/holtz/scripts/markdown_utils.py` | Markdown parsing (mask code fences, section extraction) |
| `skills/holtz/scripts/pattern_brief_compact.py` | Compact pattern brief for subagent consumption |
| `hooks/_common.py` | Shared hook utilities (mask_fenced_blocks, etc.) |
| `hooks/convergence_gate.py` | Block premature audit stops |
| `hooks/convergence_primer.py` | Inject resume context after /clear |
| `hooks/impact_graph_gate.py` | Block audit writes without impact graph |
| `hooks/status_staleness_gate.py` | Block writes with stale STATUS.md |
| `hooks/artifact_verification.py` | Verify claimed artifacts exist |
| `hooks/subagent_findings_check.py` | Verify subagent output files exist |

### Documentation
- `CLAUDE.md` — dev guide (branch model, conventional commits, test/lint commands)
- `README.md` — comprehensive user-facing docs (~230 lines)
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `SECURITY.md`, `SUPPORT.md` — community docs
- `docs/runs/run-14-walkthrough.md` — detailed run walkthrough
- `docs/design/` — design docs for bug-fixer gap analysis, terminal output improvements
- `docs/superpowers/` — implementation plans and specs

### Recent Changes (since last audit)
- `a602d76` fix: resolve 9 defects found in Holtz run 15 audit
- `b412c16` fix: replace commit-msg hook with post-commit for reliable version bumping
- `5d0fd62` feat: add convergence gate and primer hooks to enforce loop-until-converged
- `74ba1e6` docs: add community docs and GitHub templates
- `76abb91` docs: update README test and line counts

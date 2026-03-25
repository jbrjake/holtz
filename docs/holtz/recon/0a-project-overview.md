# Step 0a: Project Overview

**Date:** 2026-03-24
**Run:** 15

## Project Structure

Plugin for Claude Code: TDD-driven bug identification and resolution engine.

### Source Modules (skills/holtz/scripts/)
| File | Role |
|------|------|
| `markdown_utils.py` | Shared leaf: fence masking, section extraction |
| `validate_punchlist.py` | Punchlist parsing, validation, filtering |
| `convergence_check.py` | Convergence tracking, test runner detection |
| `impact_graph.py` | Knowledge graph operations (standalone) |
| `pattern_brief_compact.py` | Pattern brief parsing for subagent consumption |
| `profiler_plugin.py` | Token profiler integration for Holtz phase detection |

### Hooks (hooks/)
| File | Role |
|------|------|
| `_common.py` | Shared hook utilities (leaf) |
| `impact_graph_gate.py` | Blocks Phase 1+ writes without impact graph |
| `status_staleness_gate.py` | Blocks findings writes if STATUS.md stale |
| `artifact_verification.py` | Verifies graph file exists after script runs |
| `subagent_findings_check.py` | Verifies Justine's claimed output files |
| `convergence_gate.py` | Blocks premature stops before convergence |
| `convergence_primer.py` | Injects resume context on user messages |

### Token Profiler (scripts/token_profiler/)
9 modules: CLI, extraction, analysis, models, pricing, report, viewer, plugin protocol, __main__.

### Tests (tests/)
15 test files covering all source modules, hooks, integration, and token profiler.

### Other
- 3 agent definitions (agents/)
- 17 reference docs (skills/holtz/references/)
- 6 seed patterns (skills/holtz/patterns/)
- 1 example (skills/holtz/examples/)
- CI workflows (.github/workflows/ci.yml, release.yml)
- Community docs (CODE_OF_CONDUCT, CONTRIBUTING, GOVERNANCE, SECURITY, SUPPORT)
- Git hooks (scripts/install-hooks.sh, git-hooks/post-commit)
- CLAUDE.md with branch model and release workflow

## Changes Since Run 14

Recent commits on dev:
1. `b412c16` fix: replace commit-msg hook with post-commit for reliable version bumping
2. `5d0fd62` feat: add convergence gate and primer hooks to enforce loop-until-converged
3. `74ba1e6` docs: add community docs and GitHub templates
4. `76abb91` docs: update README test and line counts
5. `d8e4064` docs: add CLAUDE.md with branch model and release workflow
6. `8acacd1` ci: add release workflow for automatic tagging and GitHub Releases
7. `25d3a86` ci: add dev branch to CI triggers
8. `3d12cf3` chore: add install-hooks script for git hook setup
9. `a4c77e8` feat: add commit-msg hook with automatic version bumping
10. `7afc962` fix: resolve ruff lint errors in merge-session-cast.py

New components since run 14:
- `hooks/convergence_gate.py` — NEW
- `hooks/convergence_primer.py` — NEW
- `scripts/install-hooks.sh` — NEW
- `git-hooks/post-commit` — NEW (replaced commit-msg)
- `CLAUDE.md` — NEW
- `.github/workflows/release.yml` — NEW
- Community docs (5 files) — NEW

## Architecture Baseline Notes
- Baseline says "No CLAUDE.md or ARCHITECTURE.md exists" — CLAUDE.md now exists (drift)
- Baseline Module Dependencies table missing convergence_gate.py, convergence_primer.py
- Baseline established 2026-03-22, not updated since

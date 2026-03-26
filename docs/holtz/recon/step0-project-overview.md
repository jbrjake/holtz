# Step 0: Project Overview — Run 21

**Date:** 2026-03-26
**Target:** holtz (self-audit, dev mode — local SKILL.md)
**Branch:** dev
**Prior run:** Run 20 (converged, 27 items all resolved, all 13 lenses)

---

## Project Purpose

Holtz is a Claude Code plugin (v0.33.1, MIT) that implements an adversarial TDD audit loop for codebases. Its core promise: dispatch two auditors with different methodologies (Holtz depth-first, Justine breadth-first), merge their findings into a unified punchlist, fix every item using strict TDD discipline, and iterate until two consecutive passes find nothing new across thirteen analytical lenses.

The plugin audits itself — this is Run 21 of Holtz auditing Holtz.

Repository: `https://github.com/jbrjake/holtz`
Plugin install: `/plugin install holtz@jbrjake`

---

## Architecture

The codebase has two primary layers plus a standalone package:

### Layer 1: Markdown Protocol Layer (LLM-consumed)

The instructions the LLM follows. Lives in `skills/holtz/`:

- `SKILL.md` — main skill entry point; type RIGID, triggers on bug-hunt/audit/punchlist requests
- `references/` — 18 reference documents (lens registry, anti-patterns, fix loop, punchlist format, etc.)
- `patterns/` — 16 seed patterns (PAT-NNN), each with executable detection heuristics
- `agents/` — 3 subagent instruction files: `holtz.md`, `justine.md`, `merge-agent.md`
- `examples/` — 1 worked example

### Layer 2: Python Tool Layer (called by the LLM via Bash)

Deterministic scripts the LLM executes to do concrete operations. Lives in `skills/holtz/scripts/`:

| Module | Purpose |
|--------|---------|
| `impact_graph.py` | Knowledge graph: nodes, edges, risk scores, blast radius queries |
| `convergence_check.py` | Test runner detection, output parsing, convergence tracking |
| `validate_punchlist.py` | Punchlist parsing, validation, item extraction |
| `markdown_utils.py` | Shared leaf — CommonMark fence state machine |
| `pattern_brief_compact.py` | Pattern brief parsing, compact output for subagents |
| `profiler_plugin.py` | Holtz-specific plugin for the token profiler |

### Layer 3: Enforcement Hooks

Deterministic gates that block operations when the protocol isn't followed. Two hook trees coexist:

**Legacy hooks (`hooks/`)** — pre-Sahjhan, partially replaced:
- `_common.py` — shared I/O utilities (JSON stdin/stdout), exit helpers, fence masking
- `subagent_findings_check.py` — verifies subagent file claims

**Sahjhan hooks (`enforcement/hooks/`)** — Sahjhan-backed, current enforcement layer:
- `write_guard.py` — blocks direct writes to `docs/holtz/` managed paths
- `stop_gate.py` — blocks stop unless Sahjhan state is terminal
- `primer.py` — injects resume context on UserPromptSubmit, records `context_reset` event
- `bash_guard.py` — guards against unsafe bash operations
- `_common.py` — hook I/O shared utilities (parallel to legacy `hooks/_common.py`)
- `_resolve.py` — resolves Sahjhan binary path
- `_sahjhan_bootstrap.py` — Sahjhan bootstrap utilities

### Layer 4: Sahjhan Enforcement Engine (`enforcement/`)

A vendored state machine engine (binary in `bin/`) that tracks protocol state across the audit lifecycle. Configured via TOML:

- `protocol.toml` — top-level config: name, paths, namespaces, aliases, finding/resolve events
- `states.toml` — 13 states: idle → recon → audit → merge_ready → merge_done → fix_loop → awaiting_clear → pattern_analysis → perspective_clean → all_perspectives_clean → final_sweep → final_sweep_clean → converged → finalized
- `transitions.toml` — transition rules with gate conditions (file existence, command success, snapshot comparison, ledger event counts, minimum elapsed time)
- `events.toml`, `renders.toml`, `templates/` — event definitions and Tera rendering templates for STATUS.md, PUNCHLIST.md, SUMMARY.md

The Sahjhan integration is new as of the commits immediately preceding this run. The old hook layer (`hooks/`) is partially replaced; `subagent_findings_check.py` and `_common.py` remain.

### Independent Package: Token Profiler (`scripts/token_profiler/`)

A standalone Claude session token-usage analyzer. No imports from the main codebase.

| Module | Purpose |
|--------|---------|
| `models.py` | Data models (leaf) |
| `extract.py` | Session log extraction |
| `analyze.py` | Analysis pipeline |
| `pricing.py` | Dollar cost computation |
| `report.py` | Report generation |
| `viewer.py` | Interactive HTML viewer |
| `cli.py` | CLI orchestration |
| `plugin_protocol.py` | `@runtime_checkable` Protocol for plugins |
| `__main__.py` | Entry point (`python -m token_profiler`) |

`profiler_plugin.py` in `skills/holtz/scripts/` implements the `ProfilerPlugin` Protocol for Holtz-specific session analysis.

---

## Key Components Summary

### Impact Graph

The semantic knowledge graph is the analytical core. Current state from `docs/holtz/impact-graph.json`:

```
nodes: 87 | edges: 76
edge types: imports(26), calls(10), assumes(17), diverges_from(9), tests(14)
```

Seven edge types, five in active use. Semantic edges (`assumes`, `diverges_from`) encode implicit contracts not visible in import statements. Persists across runs; nodes carry risk scores (0.0–1.0) that accumulate from findings.

### Analytical Lenses

13 lenses, all covered in Run 20: component, integration, security, error-propagation, data-flow, contract, semantic-fidelity, temporal-protocol, public-contract, concurrency, resource-lifecycle, idempotency, observability.

### Pattern Library

5 named patterns tracked in STATUS.md:
- PAT-001: code-fence-unaware parsing (12+ instances across 16 runs, recurrence machine)
- PAT-002: incomplete code-fence isolation (1 instance)
- PAT-003: regex convention violation (`\s` instead of `[ \t]`)
- PAT-004: dual-implementation divergence (fence masking in `_common.py` vs `markdown_utils.py`)
- PAT-005: README-count-drift (6 consecutive runs; integration test now guards it but not pre-commit)

---

## Current State

### Branch: `dev`

### Recent Commits (most relevant first)

```
f026860 fix(enforcement): align TOML config with Sahjhan v0.1.0 type system
7f48718 style(enforcement): fix ruff lint issues in enforcement hooks
4651d66 chore: add enforcement/hooks/ to mypy check paths (E13)
08c1ea8 refactor(enforcement): remove old hooks replaced by Sahjhan enforcement
9314c1c test(enforcement): add Sahjhan integration tests, update hook tests for cutover
2b9e207 feat(skill): update SKILL.md to reference Sahjhan enforcement commands
fc8a3c4 feat(enforcement): update hooks.json to use Sahjhan-backed enforcement hooks
2d6dca1 feat(enforcement): add Sahjhan binary vendoring and install script
149780b feat(enforcement): add Sahjhan hook scripts
c4ff023 feat(enforcement): add Tera templates for STATUS.md, PUNCHLIST.md, SUMMARY.md
6d123d7 feat(enforcement): add Holtz protocol definition as Sahjhan TOML config
d814e64 docs: complete Run 20 post-convergence — SUMMARY, baseline, living punchlist
```

The Sahjhan enforcement engine integration is the dominant recent change — 11 commits, all post-Run-20.

### Working Tree

Modified (unstaged): docs artifacts (MERGE-REPORT.md, PUNCHLIST-MERGED.md, impact-graph.json), hooks (artifact_verification.py, convergence_gate.py, convergence_primer.py), scripts (token_profiler extract/report/viewer), and tests (test_hooks.py, all token_profiler test files).

Deleted: `docs/holtz/run-18-postmortem.md`

Untracked: `docs/holtz/archive/2026-03-25-run18/`, `docs/holtz/archive/2026-03-25-run19/`, `docs/holtz/archive/justine-2026-03-25-run19/`, `docs/holtz/archive/justine-2026-03-25-run20/`, and new superpowers plan/spec documents.

### Test Results (current)

**1 test failure.** The README metrics integration test is failing:

```
FAILED tests/test_integration.py::test_readme_metrics_match_actual
AssertionError: assert not ['enforcement hooks: README says 6, actual 1',
                            'tests: README says 647, actual 585',
                            'lines: README says 14300, actual 12728']
```

Three README claims are stale:
1. "6 enforcement hooks" — actual count is 1 (Sahjhan cutover removed 5 old hooks)
2. "647 tests" — actual is 585 (13 fewer than README claims; note: full suite run earlier shows 584+1 failing = 585 total, but README baseline was 647 from Run 20 final)
3. "14,300 lines" — actual is 12,728

Suite otherwise: 584 passing, 1 failing, 0 skipped, 76% coverage (hooks and scripts only).

**Note on test count discrepancy:** The git status shows `M tests/test_hooks.py` and multiple token profiler test files as modified. The current test count of ~585 appears to diverge from the Run 20 final of 647. This warrants investigation — either the working tree modifications reduced test count, or the README count was incorrect at Run 20's end.

### Toolchain Status (from Run 20 Step 1)

- pytest: 641 passed (Run 20 baseline), now 584 passing / 1 failing
- ruff: clean (Run 20)
- mypy: clean (Run 20); `enforcement/hooks/` now added to mypy scope

---

## Architecture Baseline (from `docs/holtz/architecture-baseline.md`)

Last updated: 2026-03-26 (Run 20). Key documented invariants:

- `markdown_utils.py` — shared leaf for scripts; `hooks/_common.py` — shared leaf for hooks (parallel, kept separate to avoid cross-layer imports)
- All punchlist field extraction uses masked content for boundary detection, original for extraction
- `mask_code_fences` preserves line count
- Both `count_items` and `parse_punchlist` split on `### BH-NNN:` headers in masked content
- All atomic writes via tempfile + rename
- Test runner parsers return `None` for unparseable output (not zero-count dicts)

Documented drift as of Run 20:
- `check_convergence` shifted from line 280 to 296 (+16 from baseline) — no structural change
- README count staleness (MEDIUM, recurring) — now guarded by integration test but not pre-commit

---

## Prior Run Artifacts

`docs/holtz/archive/` contains 30+ archived run directories from Runs 2–20 (2026-03-19 through 2026-03-25).

`docs/holtz/recon/` contains prior-run recon files that will be overwritten this run:
- `step0-project-overview.md` (this file)
- `step1-toolchain.md`
- `step2-code-signals.md`
- `step2-cold-files.md`
- `step3-recon-summary.md`
- `step4-predictions.md`

---

## Areas of Concern for Auditing

### HIGH PRIORITY

**1. Test count collapse: 647 → 585 (-62 tests)**
The most significant signal. Working tree has modified test files for hooks and token profiler. Either tests were deleted, or test files were refactored. Modified files: `test_hooks.py`, `test_token_profiler_analyze.py`, `test_token_profiler_cli.py`, `test_token_profiler_integration.py`, `test_token_profiler_models.py`, `test_token_profiler_report.py`. This needs full accounting — were tests legitimately consolidated, or were they lost?

**2. README metrics stale after Sahjhan cutover**
The enforcement hook count changed from 6 to 1 (Sahjhan replaced 5 hooks). The integration test `test_readme_metrics_match_actual` is now failing. The README, test expectations, and actual counts are out of sync. PAT-005 pattern recurrence. This is a known class; the enforcement integration is the new trigger.

**3. Sahjhan integration correctness**
11 commits of new enforcement engine integration landed after Run 20. The `enforcement/` directory, `hooks.json`, `enforcement/hooks/*.py` — none of this has been audited. The transitions.toml gate conditions are complex (snapshot comparisons, `ledger_has_event_since` with `since = "last_event_of_type:..."` syntax, `min_elapsed` gate). Gate conditions that are too lenient let the protocol be bypassed; too strict and they deadlock the audit. Accuracy of gate conditions is a correctness concern.

**4. Dual hook layer architecture**
`hooks/` (legacy) and `enforcement/hooks/` (Sahjhan) coexist. `hooks/artifact_verification.py` and `hooks/convergence_gate.py` and `hooks/convergence_primer.py` are in the modified working tree. The old `convergence_gate.py` and `convergence_primer.py` have been superseded by `enforcement/hooks/stop_gate.py` and `enforcement/hooks/primer.py` — but the old files still exist and are being modified. This is a PAT-004 (dual-implementation divergence) variant.

### MEDIUM PRIORITY

**5. PAT-004: Dual fence masking**
`hooks/_common.py::mask_fenced_blocks` and `skills/holtz/scripts/markdown_utils.py::mask_code_fences` remain as parallel implementations. Documented in architecture baseline; not yet consolidated. The delimiter-line handling divergence is documented and tested. Run 20 deferred this (BH-018). New code using either implementation may create new divergence instances.

**6. Token profiler modified files**
`scripts/token_profiler/extract.py`, `report.py`, `viewer.py` are modified. Their test files are also modified. The nature of these changes (additions? refactors? behavior changes?) is unknown from git status alone. Run 20 fixed several profiler issues (BH-011 pricing wired up, BH-020 @property fields injected, BH-019 milestones propagated, BH-018 viewer column renamed). These unstaged changes may be post-fix cleanup or may contain new defects.

**7. PAT-005: README count automation still not pre-committed**
The integration test catches drift in CI, but a pre-commit hook or count generator would prevent it entirely. Escalation count: 6 consecutive runs. The Sahjhan cutover just triggered it again.

### LOW PRIORITY

**8. Cold file coverage reset**
Run 20 brought cold file ratio from 30% to 0%. The new Sahjhan enforcement hooks in `enforcement/hooks/` are all cold — never audited. These are new code with no audit history, which was the condition Holtz flagged as high-risk when hooks were first added in Run 8.

**9. `docs/holtz/archive/` untracked Justine runs**
`justine-2026-03-25-run19/` and `justine-2026-03-25-run20/` are untracked. These may contain findings that weren't fully merged, or may simply be archival. Worth confirming they're captured in the merged punchlist.

**10. `docs/superpowers/` untracked plans and specs**
New untracked files under `docs/superpowers/plans/` and `docs/superpowers/specs/` describing Holtz-Sahjhan integration. These represent intended behavior — a source of testable claims if they specify observable behavior.

---

## Impact Graph Reconciliation

Current graph (`python skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats`):

```json
{
  "nodes": 87,
  "edges": 76,
  "edge_types": {
    "imports": 26,
    "calls": 10,
    "assumes": 17,
    "diverges_from": 9,
    "tests": 14
  }
}
```

Compared to Run 20 Step 0 (63 nodes, 63 edges): significant growth. The Sahjhan integration and token profiler expansion added nodes and edges. No pruning analysis done yet — that's Step 1's job.

---

## Summary

Holtz v0.33.1 is a mature self-auditing plugin (20 prior runs) that just underwent significant architectural surgery: the Sahjhan state machine enforcement engine replaced 5 of 6 legacy hooks. This is the highest-risk recent change. The test count dropped by 62, README metrics are stale (one test failing), and the old hook files are still present in a modified state alongside the new enforcement hooks. The Sahjhan TOML gate conditions are untested in adversarial conditions. PAT-005 is recurring. Cold file ratio is back up (new enforcement hooks).

Audit priority order: (1) test count accounting, (2) README metrics / integration test failure, (3) Sahjhan enforcement hooks correctness, (4) dual hook layer cleanup, (5) token profiler modified files.

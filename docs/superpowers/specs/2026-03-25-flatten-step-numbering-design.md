# Flatten Phase Numbering to Step 0-20

**Date:** 2026-03-25
**Status:** Draft
**Motivation:** The current phase/subphase/letter numbering (Phase 0a.1, Pre-Phase 4, Phase 5-as-recurring-activity, Phase 6-reruns-1-3) is confusing and was a contributing factor in the Run 17 failure where Holtz misunderstood the convergence protocol's structure. Flattening to a single sequential step list (0-20) makes the process legible, removes ambiguity, and creates natural points to offload mechanical work to subagents.

## The Canonical Step List

| Step | Name | Owner | Notes |
|------|------|-------|-------|
| **0** | Project overview + drift detection | Holtz | Read project structure, docs, architecture. Compare against baseline. |
| **1** | Run toolchain | Subagent | Tests + CI + lint in parallel. Returns structured results. |
| **2** | Code signals | Subagent | Churn + mutation scan + skipped tests in parallel. Returns ranked lists. |
| **3** | Recon summary | Holtz | Synthesize Steps 0-2, load pattern library, recommendation escalation. |
| **4** | Predictions | Holtz | Risk ranking by confidence from 6 input sources. Uses ultrathink. |
| **5** | Dispatch Justine | Holtz | Launch parallel auditor with inherited recon. |
| **6** | Doc-to-implementation audit | Holtz | Extract doc claims, verify against code. |
| **7** | Test quality audit | Holtz | Audit tests against 12 anti-patterns. |
| **8** | Adversarial code audit | Holtz | Depth-first source review for bugs. |
| **9** | Merge Justine findings | Subagent | Merge punchlists via merge protocol. |
| **10** | TDD fix loop | Holtz | Triage -> test -> fix -> commit, iterate. |
| **11** | Pattern analysis | Holtz | [recurring: every 3-5 fixes during Step 10] |
| **12** | Per-fix hardening | Holtz | [recurring: after each fix in Step 10] |
| **13** | Blast radius check | Holtz | [recurring: after each fix in Step 10] |
| **14** | Lens rotation | Holtz | Re-run Steps 6-8 scoped to current lens, then back to Step 10. |
| **15** | Convergence check | Holtz | Run convergence_check.py, evaluate exit code. |
| **16** | Resweep | Holtz | Full re-run of Steps 6-8 to confirm convergence. |
| **17** | Architecture baseline update | Subagent | Background dispatch. |
| **18** | Pattern library contribution | Subagent | Holtz provides list, subagent formats. |
| **19** | Living punchlist update | Subagent | Mechanical transform from PUNCHLIST to LIVING-PUNCHLIST. |
| **20** | Write SUMMARY.md | Holtz | Final synthesis with prediction accuracy table. |

### Justine's Parallel Track

Dispatched at Step 5, merged at Step 9.

| Step | Name | Notes |
|------|------|-------|
| **J0** | Inherit recon + write own summary/predictions | Aggressive confidence calibration |
| **J1** | Immediate prediction testing | Write tests for top predictions |
| **J2** | Multi-lens audit | Steps 6-8 equivalent, all lenses simultaneously |
| **J3** | TDD fix loop | Same protocol, severity = potential impact |
| **J4** | Pattern analysis | [recurring: every 3-5 fixes during J3] |
| **J5** | Single-pass convergence | All lenses simultaneously, 10 iteration cap |
| **J6** | Write summary | justine/SUMMARY.md |

## Subagent Collapse Rationale

Steps 1, 2, 9, 17, 18, 19 are delegated to subagents. The principle: **Holtz only holds context for work that builds his holistic systems understanding. Mechanical data collection and formatting are offloaded.**

- **Step 1 (Run toolchain):** Collapses old 0b (test infra), 0c (test baseline), 0c.1 (CI status), 0d (lint). All are "run a command, capture output." Subagent runs in parallel, returns structured results. Holtz never needs raw pytest/ruff output. Estimated savings: 5-8k tokens.
- **Step 2 (Code signals):** Collapses old 0e (churn), 0e.1 (mutation scan), 0f (skipped tests). All are git/AST analysis. Subagent returns ranked lists. Estimated savings: 3-5k tokens.
- **Step 9 (Merge Justine):** Already a subagent dispatch in current process.
- **Steps 17-19 (Post-convergence):** Architecture baseline update already dispatched as subagent. Pattern library contribution and living punchlist update are mechanical formatting tasks.

## Old-to-New Mapping

For reference during migration and for understanding historical audit artifacts.

| Old Name | New Step | Notes |
|----------|----------|-------|
| Phase 0a | Step 0 | Merged with 0a.1 (drift detection) |
| Phase 0a.1 | Step 0 | Merged into Step 0 |
| Phase 0b | Step 1 (subagent) | Part of "Run toolchain" |
| Phase 0c | Step 1 (subagent) | Part of "Run toolchain" |
| Phase 0c.1 | Step 1 (subagent) | Part of "Run toolchain" |
| Phase 0d | Step 1 (subagent) | Part of "Run toolchain" |
| Phase 0e | Step 2 (subagent) | Part of "Code signals" |
| Phase 0e.1 | Step 2 (subagent) | Part of "Code signals" |
| Phase 0f | Step 2 (subagent) | Part of "Code signals" |
| Phase 0g | Step 3 | Recon summary |
| Phase 0h | Step 4 | Predictions |
| Dispatch Justine | Step 5 | Unchanged |
| Phase 1 | Step 6 | Doc-to-implementation audit |
| Phase 2 | Step 7 | Test quality audit |
| Phase 3 | Step 8 | Adversarial code audit |
| Pre-Phase 4 | Step 9 | Merge Justine findings |
| Phase 4 | Step 10 | TDD fix loop |
| Phase 5 | Step 11 | Pattern analysis (now marked recurring) |
| Per-fix hardening | Step 12 | Now has its own step number (recurring) |
| Blast radius analysis | Step 13 | Now has its own step number (recurring) |
| Phase 6 | Step 14 | Lens rotation |
| Convergence check | Step 15 | Was unnamed sub-step of Phase 6 |
| Resweep | Step 16 | Was unnamed post-convergence activity |
| Arch baseline update | Step 17 | Was unnamed post-convergence activity |
| Pattern library contribution | Step 18 | Was unnamed post-convergence activity |
| Living punchlist update | Step 19 | Was unnamed post-convergence activity |
| Write SUMMARY.md | Step 20 | Was unnamed post-convergence activity |

## Recon Output File Renaming

New naming convention for runtime artifacts written during each audit:

| Old Path | New Path |
|----------|----------|
| `docs/holtz/recon/0a-project-overview.md` | `docs/holtz/recon/step0-project-overview.md` |
| `docs/holtz/recon/0b-test-infra.md` | `docs/holtz/recon/step1-toolchain.md` |
| `docs/holtz/recon/0c-test-baseline.md` | (merged into step1-toolchain.md) |
| `docs/holtz/recon/0c1-ci-status.md` | (merged into step1-toolchain.md) |
| `docs/holtz/recon/0d-lint-results.md` | (merged into step1-toolchain.md) |
| `docs/holtz/recon/0e-churn.md` | `docs/holtz/recon/step2-code-signals.md` |
| `docs/holtz/recon/0e1-mutation-scan.md` | (merged into step2-code-signals.md) |
| `docs/holtz/recon/0f-skipped-tests.md` | (merged into step2-code-signals.md) |
| `docs/holtz/recon/0g-recon-summary.md` | `docs/holtz/recon/step3-recon-summary.md` |
| `docs/holtz/recon/0h-predictions.md` | `docs/holtz/recon/step4-predictions.md` |

## Blast Radius

### Tier 1: Process definitions

| File | Change |
|------|--------|
| `skills/holtz/SKILL.md` | Complete rewrite of process flow to use Step 0-20. |
| `skills/holtz/references/phase-0-recon.md` | Rename to `step-0-4-recon.md`. Rewrite to use step numbering. |
| `skills/holtz/references/phase-4-fix-loop.md` | Rename to `step-10-fix-loop.md`. Update internal refs. |
| `skills/holtz/references/justine-skill.md` | Rewrite to use J0-J6 numbering. |
| `skills/holtz/references/status-file-format.md` | Rewrite STATUS.md template with step numbering. |
| `skills/holtz/references/lens-registry.md` | Update phase refs to step numbers. |
| `skills/holtz/references/impact-graph-operations.md` | Update phase refs. |
| `skills/holtz/references/living-punchlist-format.md` | Update phase refs. |
| `skills/holtz/references/punchlist-format.md` | Update phase refs. |
| `skills/holtz/references/investigation-format.md` | Update phase refs. |
| `skills/holtz/references/architecture-baseline-format.md` | Update phase refs. |

### Tier 2: Code

| File | Change |
|------|--------|
| `skills/holtz/scripts/profiler_plugin.py` | `_PHASE_PATTERNS` -> `_STEP_PATTERNS`. Update regex patterns and labels. |
| `skills/holtz/scripts/convergence_check.py` | "Phase 1-3 sweep" -> "Steps 6-8 sweep" |
| `hooks/impact_graph_gate.py` | Comment: "Phase 1+" -> "Step 6+" |
| `tests/test_hooks.py` | Update phase references in assertions. |
| `tests/test_token_profiler_plugin.py` | Update phase labels in expectations. |

### Tier 3: Agent definitions

| File | Change |
|------|--------|
| `agents/holtz.md` | Update phase references. |
| `agents/justine.md` | Update phase references. |

### Tier 4: Diagrams + README

| File | Change |
|------|--------|
| `docs/diagrams/phase4-triage.dot` | Rename to `step10-triage.dot`. Update labels. |
| `docs/diagrams/holtz-convergence.dot` | Update phase labels to step numbers. |
| `docs/diagrams/justine-convergence.dot` | Update to J-step numbers. |
| `docs/diagrams/resume-lifecycle.dot` | Update phase refs. |
| `docs/diagrams/impact-graph.dot` | Update phase refs if any. |
| All `.svg` files | Re-render from `.dot` via `dot -Tsvg`. Same theming (defined in `.dot` sources). |
| `README.md` | Update text + `<img>` paths for renamed diagrams. |

### Not touched

- `docs/holtz/archive/*` -- historical artifacts, frozen in time
- `docs/runs/*` -- historical run data
- `docs/superpowers/specs/*` and `docs/superpowers/plans/*` -- historical design docs
- `docs/holtz/STATUS.md`, `PUNCHLIST*.md` -- runtime artifacts from run 17, archived before work begins

## Migration Strategy

All work on a single `feat/flatten-steps` branch off `dev`. One commit per logical group:

1. **SKILL.md** -- new canonical step list (source of truth)
2. **Reference docs** -- update + rename all `references/*.md`
3. **Scripts + hooks** -- update Python, run tests
4. **Diagrams** -- update `.dot`, re-render `.svg`
5. **README + agents** -- update consumer-facing docs
6. **Tests** -- update any phase-label assertions

## Design Decisions

**Why Step 0 instead of Step 1:** Recon is setup work before the "real" audit. Starting at 0 preserves this semantic.

**Why recurring steps get their own numbers:** Pattern analysis (Step 11), per-fix hardening (Step 12), and blast radius (Step 13) are real activities that deserve visibility. Marking them `[recurring]` is honest about execution order without hiding them inside another step's description.

**Why Justine uses J-prefix instead of shared numbering:** Justine runs in parallel with different convergence rules, different lens application, and different severity calibration. Forcing her into Holtz's sequential numbering would be misleading. The J-prefix makes clear she's a parallel track that syncs at defined points (dispatch at Step 5, merge at Step 9).

**Why not collapse Steps 6-8 into one "Audit" step:** They use different techniques (doc verification vs. anti-pattern matching vs. adversarial review), reference different docs, and Holtz needs to know which mode he's in. Keeping them separate aids resumption after context compaction.

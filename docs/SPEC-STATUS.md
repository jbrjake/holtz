# Spec/plan status

> Last verified: 2026-04-04

Plans and specs live in `docs/superpowers/plans/` and `docs/superpowers/specs/`. They never get updated when work ships, so their status fields are lies. This table is the truth.

For the current architecture (what's actually built), see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Done

| Spec/Plan | Date | Key Files |
|-----------|------|-----------|
| Code-Fence Awareness | 2026-03-19 | `markdown_utils.py`, integrated into both validators |
| Tier 1: Foundational Protocol | 2026-03-20 | Discovery Chain in punchlist format, impact graph, lens registry |
| Tier 2: Impact Graph + Lens Registry | 2026-03-20 | `impact_graph.py` (56 tests), `parse_lens_registry.py`, 13 lenses |
| Tier 3: Justine | 2026-03-20 | `agents/justine.md`, `justine-skill.md`, 100+ archive runs |
| Tier 3: Pattern Library | 2026-03-20 | 16 patterns, contribution protocol, `pattern_brief_compact.py` |
| Tier 4: Adversarial Self-Play | 2026-03-20 | `merge-protocol.md`, `merge-agent.md`, `phase-merge.md` |
| Tier 4: Temporal Awareness | 2026-03-20 | `architecture-baseline.md`, `LIVING-PUNCHLIST.md`, drift detection |
| Hooks & Extended Thinking (thinking part) | 2026-03-22 | `ultrathink` in phase-fix-loop, phase-recon, justine-skill |
| Token Optimization (all 6 plans) | 2026-03-23 | Filtered reads, compact briefs, recon inheritance, merge extraction, merge subagent, post-convergence subagent |
| Token Profiler (on branch) | 2026-03-24 | `feature/token-profiler` branch — not merged to dev |
| Release Workflow | 2026-03-24 | `generate-changelog.py`, post-commit hook |
| Flatten Step Numbering | 2026-03-25 | Phase reference files use flat numbering |
| Consolidated Additions | 2026-03-25 | 16 patterns, 17 anti-patterns, 13 lenses |
| Lens Pattern Integration | 2026-03-25 | Lenses reference patterns, patterns reference lenses |
| Sahjhan Engine (v0.1-0.9) | 2026-03-25+ | Full enforcement layer in `enforcement/` |
| JSONL Migration | 2026-03-26 | JSONL ledger, `migrate_legacy.py` |
| Protocol Enforcement | 2026-03-26 | State machine, gates, obligations |
| Lens Enforcement | 2026-03-27 | Lens quiz, evidence checking, sweep validation |
| Enforcement Hardening (Phase 1+2) | 2026-03-29 | Shell parsing, freshness gating, convergence gaming prevention |
| Sahjhan Self-Bootstrap | 2026-03-30 | `_resolve.py`, `_sahjhan_bootstrap.py` |
| Front-Loaded Lens Audit | 2026-03-31 | Scope field, `parse_lens_registry.py`, gap-fill Step 14 |
| Sahjhan 0.7.0 Runtime Hooks | 2026-03-31 | Hook rules in `hooks.toml` |
| Freshness-Gated Enforcement | 2026-04-01 | `is_enforcement_fresh()`, 30-min threshold |
| Issue #29 Enforcement Chain Fix | 2026-04-02 | `_split_shell_segments()`, stop hook fix, primer fix |
| Terminal Output Improvements | 2026-03-24 | `output-format.md` with phase banners, finding callouts, verdicts |
| Bug-Fixer Gap Analysis | 2026-03-20 | Investigation protocol, can't-reproduce path, per-fix hardening |

## Partially done

| Spec/Plan | What's Done | What's Not |
|-----------|-------------|------------|
| Tier 2: Predictive Recon | 6/7 components | Accuracy rollup table/script |
| Tier 2: Blast Radius | Script + protocol + Sahjhan gate | Unvalidated in live run post-gate |
| Tier 4: Mutation-Guided Auditing | Spec + reference procedures | Not wired into recon workflow |
| Hooks spec (hooks part) | 1/4 hooks built | 3 superseded by Sahjhan (not a gap) |

## Remaining work

Concrete tasks from the partially implemented specs.

### Prediction accuracy rollup

**Spec:** Tier 2, Section 3.10
**What works:** Predictions are generated in Step 4, used to prioritize audit phases, tracked with CONFIRMED/UNCONFIRMED outcomes in `0h-predictions.md`, and linked to punchlist items via the `**Predicted:**` field.
**What's missing:** The accuracy rollup table for SUMMARY.md (confidence level -> predicted -> confirmed -> accuracy %). Run 10 had it, later runs didn't. No script automates the calculation.

- [ ] Script `predict_accuracy.py`: read predictions file, count by confidence x outcome, output markdown table
- [ ] Integrate into Step 17 (finalize) in `phase-finalize.md`

### Blast radius execution enforcement

**Spec:** Tier 2, Section 4
**What works:** `impact_graph.py blast_radius` does bidirectional BFS. Phase-fix-loop.md documents the 5-step protocol. Risk score updates work. The Sahjhan `fix_commit` gate requires a `blast_radius` event.
**What's missing:** Despite the gate, Run 19 executed zero blast radius queries. The Sahjhan gate should catch this now (it was added after Run 19), but this hasn't been validated in a live run.

- [ ] Validate blast radius enforcement gate works in a live audit run
- [ ] Consider adding blast radius output verification (not just event existence)

### Mutation-guided auditing

**Spec:** Tier 4, Section 2
**What works:** Full spec with tool detection (mutmut, Stryker, cargo-mutants, go-mutesting, PIT), output format, time caps, and integration points. Reference procedures in `recon-procedures.md` describe the optional Step 2b.
**What's missing:** The recon workflow (`phase-recon.md`) never mentions mutation scanning. No subagent prompt includes it. No archive run has ever produced a `0e1-mutation-scan.md`. The feature is documented but never activated.

- [ ] Add Step 2b to `phase-recon.md` (after churn, before skipped tests) with auto-detection logic
- [ ] Update Step 2 subagent prompt in `phase-audit.md` to include mutation scanning when tool detected
- [ ] Test with a project that has mutmut installed

### Three planned enforcement hooks (superseded)

**Spec:** Hooks & Extended Thinking design, Section 2.9
**Original plan:** Four hooks — `impact_graph_gate.py`, `status_staleness_gate.py`, `artifact_verification.py`, `subagent_findings_check.py`.
**What happened:** Only `subagent_findings_check.py` was built. The other three were superseded by Sahjhan, which provides the same guarantees through state machine gates instead of per-tool-use Python hooks. The impact graph gate became a `file_exists` gate on the `recon_complete` transition. Status staleness became the managed-path guard in `pre_tool_hook.py`.
**Remaining work:** None. Deliberate architectural decision, not a gap. Listed here because the 2026-03-22 spec still claims they're planned.

## Not started

Nothing. Everything has at least partial implementation. Whether that's comforting or alarming depends on your perspective.

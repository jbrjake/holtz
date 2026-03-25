# Step 0h: Predictive Recon

**Date:** 2026-03-24
**Run:** 16

## Predictions

### Prediction 1
**Target:** README.md — "What's inside" line and semantic claims throughout
**Predicted Issue:** doc/drift — README counts stale after Run 15 added tests/fixed code, or semantic claims overstated
**Confidence:** HIGH
**Basis:** README has highest churn (10/50), Run 15 added 18 tests (595→613). Integration test checks counts but not semantic accuracy of descriptive claims. Prior runs found README drift.
**Lens:** public-contract
**Graph Support:** diverges_from edges exist between README and implementation nodes
**Outcome:** CONFIRMED — BH-001 (prediction accuracy overstated), BH-002 (run count stale)

### Prediction 2
**Target:** skills/holtz/SKILL.md — `${CLAUDE_PLUGIN_ROOT}` references in dev mode
**Predicted Issue:** doc/drift — SKILL.md contains `${CLAUDE_PLUGIN_ROOT}` path references that don't resolve in dev mode (running from local clone). Process instructions may be incorrect for the current execution context.
**Confidence:** HIGH
**Basis:** SKILL.md has 5 changes in 50 commits. Run 15 found process gaps (BH-008, BH-009). The skill is designed for installed plugin context but being tested in dev mode. `${CLAUDE_PLUGIN_ROOT}` appears in CLI commands throughout.
**Lens:** contract
**Graph Support:** assumes edges between SKILL.md and script CLI interfaces
**Outcome:** UNCONFIRMED — ${CLAUDE_PLUGIN_ROOT} is a runtime variable resolved by Claude Code; SKILL.md references are correct by design

### Prediction 3
**Target:** scripts/token_profiler/ — new module with moderate coverage
**Predicted Issue:** test/shallow or bug/logic — Token profiler is newest code, less battle-tested. Coverage gaps in CLI edge cases.
**Confidence:** MEDIUM
**Basis:** Token profiler added in last 15 commits. 8 test files but new code often has shallow tests. Not previously audited by Holtz. Living punchlist has no entries for this module.
**Lens:** component
**Graph Support:** No prior risk scores — new nodes with no history
**Outcome:** UNCONFIRMED — Phase 2 found minor anti-patterns (time bomb, permissive validator) but no actual bugs; Phase 3 found no bugs in token profiler

### Prediction 4
**Target:** hooks/convergence_gate.py, hooks/convergence_primer.py
**Predicted Issue:** design/inconsistency — Hooks may have edge cases around STATUS.md format parsing after Run 15's process changes
**Confidence:** MEDIUM
**Basis:** Run 15 found 4 PAT-001 instances in hooks (BH-003/004/005/006, all fixed). Convergence hooks parse STATUS.md which changed format during Run 15. Hooks now use mask_fenced_blocks but edge cases may remain.
**Lens:** integration
**Graph Support:** assumes edges between hooks and STATUS.md format; risk_score lowered by Run 15 fixes
**Outcome:** CONFIRMED — BH-004 (mask_fenced_blocks ignores fence count, weaker than markdown_utils.py implementation)

### Prediction 5
**Target:** skills/holtz/scripts/impact_graph.py — CLI entry points
**Predicted Issue:** test/missing or bug/logic — 65% coverage, lowest among core scripts. CLI subcommands (blast_radius, update_risk, prune_missing, drift_check) may have edge cases not covered
**Confidence:** MEDIUM
**Basis:** Coverage data shows 97 uncovered statements. Lines 320-431 (blast_radius, CLI main) uncovered. Prior runs haven't found bugs here but coverage gap is real.
**Lens:** component
**Graph Support:** impact_graph node has moderate risk score from coverage-based assessment
**Outcome:** UNCONFIRMED — Phase 3 found O(D*N*E) blast_radius performance concern but no actual bugs in CLI paths

### Prediction 6
**Target:** README.md — "nine analytical lenses" claim
**Predicted Issue:** doc/drift — README says "nine analytical lenses" but lens registry may have a different count
**Confidence:** LOW
**Basis:** Lens registry has been expanded over time. README narrative may not have been updated to reflect current count. The integration test checks component counts but not the lens count.
**Lens:** public-contract
**Graph Support:** —
**Outcome:** UNCONFIRMED — lens registry has exactly 9 lenses, README is accurate

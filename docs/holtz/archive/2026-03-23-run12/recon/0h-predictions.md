# Phase 0h: Predictive Recon

**Run:** 12
**Date:** 2026-03-23

## Predictions

### Prediction 1
**Target:** README.md (reference doc count, line count)
**Predicted Issue:** doc/drift — README claims "14 reference docs" but actual count is 16 (Justine files moved into references/). README claims "8,200 lines" but actual is ~7,631.
**Confidence:** HIGH
**Basis:** README highest churn (15 changes), Justine refactor moved files into references/, wc -l confirms line count mismatch. Same pattern as BH-002 run 11 (ref doc count drift). Prediction 1 from run 11 was CONFIRMED.
**Lens:** component
**Graph Support:** README node, prior doc/drift pattern
**Outcome:** CONFIRMED — BH-001 (skills count 2→1, ref docs 14→16, lines 8200→8308)

### Prediction 2
**Target:** hooks/_common.py:exit_block (line 63-79)
**Predicted Issue:** bug/logic or design/inconsistency — `exit_block()` hardcodes `hookEventName: "PreToolUse"` but has no guard preventing it from being called in a PostToolUse context. The docstring says "For PreToolUse hooks only" but this is advisory, not enforced. If a PostToolUse hook path ever calls `exit_block()`, the output would contain `"hookEventName": "PreToolUse"` which is semantically incorrect.
**Confidence:** MEDIUM
**Basis:** Hook modernization rewrote all functions. `exit_ok()` takes an `event_name` parameter for conditional behavior but `exit_block()` does not. Asymmetric API design after refactor.
**Lens:** contract
**Graph Support:** _common.py node, hooks layer 0% coverage
**Outcome:** UNCONFIRMED — exit_block() is only called from PreToolUse hooks (impact_graph_gate, status_staleness_gate). PostToolUse/SubagentStop hooks use exit_warn(). Current code is correct; design concern but not a bug.

### Prediction 3
**Target:** hooks/_common.py:read_event (line 20-31)
**Predicted Issue:** test/shallow — `read_event()` silently returns `{}` on empty stdin or parse error. Hook callers that receive `{}` may proceed without the expected event data. Tests may not verify behavior when event data is missing/malformed.
**Confidence:** MEDIUM
**Basis:** Hook modernization changed the input contract. All hooks call `read_event()` first. If stdin is empty (which can happen in certain Claude Code invocations), hooks would operate on empty dict. Tests need to verify this path.
**Lens:** error-propagation
**Graph Support:** _common.py → all 4 hook files (imports)
**Outcome:** UNCONFIRMED — existing tests (test_empty_stdin_does_not_crash, test_malformed_json_does_not_crash) verify hooks handle empty/bad stdin gracefully. Hooks degrade correctly to allow when event data is empty (exit_ok). Tests could be stronger but behavior is correct.

### Prediction 4
**Target:** skills/holtz/scripts/impact_graph.py (node/edge loading)
**Predicted Issue:** bug/error-handling — Global pattern library scan found that `impact_graph.py` loads edges and nodes from JSON without validating individual dict structure. Missing `id`, `source`, `target`, or `type` keys would cause `KeyError`.
**Confidence:** MEDIUM
**Basis:** Global pattern match (missing-edge-case-handling.md) + detection heuristic hit
**Lens:** error-propagation
**Graph Support:** impact_graph.py node, risk_score from prior runs
**Outcome:** CONFIRMED — BH-003 (malformed edge/node entries cause KeyError in load())

### Prediction 5
**Target:** hooks/artifact_verification.py, hooks/status_staleness_gate.py
**Predicted Issue:** test/shallow — Hook modernization changed output format but tests may only verify JSON structure without testing actual gate logic (block vs allow decisions based on file state).
**Confidence:** LOW
**Basis:** 0% coverage on hook files. test_hooks.py is 18KB which suggests substance, but the modernization was recent. Tests may verify format but not semantics.
**Lens:** component
**Graph Support:** hooks layer 0% coverage
**Outcome:** PARTIALLY CONFIRMED — Tests do verify gate logic (block vs allow), not just format. However, Justine found 3 specific untested code paths (BH-004/005/006) that the prediction was directionally correct about. The prediction's concern was about format-only testing, but the actual gap was untested branches, not shallow assertions.

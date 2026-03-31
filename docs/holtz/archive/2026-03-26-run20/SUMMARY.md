# Holtz Run 20 — Summary

**Project:** holtz (self-audit, dev mode)
**Date:** 2026-03-26
**Run type:** Full adversarial self-play, all 13 lenses
**Convergence:** Iteration 8

## Results

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 641 | 647 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Coverage | 65% | 66% |
| Ruff | clean | clean |
| Mypy | clean | clean |
| Punchlist items found | — | 27 |
| Punchlist resolved | — | 27 |
| Punchlist deferred | — | 0 |
| Punchlist open | — | 0 |
| New patterns | — | 0 |
| Convergence iterations | — | 8 |

## Lens Coverage

All 13 lenses audited. Finding distribution:

| Lens | Findings | Resolved | Notes |
|------|----------|----------|-------|
| component | 15 | 15 | Initial pass: 21 items (incl. Justine merge), 17 resolved, 4 deferred → all later resolved |
| integration | 6 | 6 | Dead protocol methods, test fixture gap, third parser |
| security | 1 | 1 | Viewer innerHTML XSS |
| error-propagation | 2 | 2 | extract_session crash, ImpactGraph silent reset |
| contract | 1 | 1 | ImpactGraph error sentinel dicts |
| semantic-fidelity | 2 | 2 | artifact_verification "BLOCKED", count_items sys.exit |
| data-flow | 0 | — | Extensions of existing items only |
| temporal-protocol | 0 | — | Clean |
| public-contract | 0 | — | Clean (count drift already tracked) |
| concurrency | 0 | — | Clean (single-threaded) |
| resource-lifecycle | 0 | — | Clean |
| idempotency | 0 | — | Clean |
| observability | 0 | — | Clean (overlap with error-propagation) |

## Key Fixes

1. **Pricing module wired up (BH-011):** `apply_pricing_to_usage` now called in the pipeline. Phase-level dollar costs computed from real token usage and model-specific pricing. Reports show actual costs instead of $0.00.

2. **Viewer XSS hardened (BH-022):** Added `esc()` HTML-encoding helper applied to all 17 data-derived innerHTML injection points. Tooltip switched from innerHTML to textContent.

3. **Dead protocol methods activated (BH-016):** `enrich_profile()` and `name_subagent()` now called in the CLI pipeline. Plugin authors' implementations are no longer silently ignored.

4. **ImpactGraph API modernized (BH-024):** `add_edge`, `update_risk`, `prune_node` raise `KeyError`/`ValueError` instead of returning `{"error": ...}` sentinel dicts. CLI dispatcher catches exceptions.

5. **Error handling tightened:** `extract_session()` crashes caught in CLI (BH-023), `ImpactGraph.load()` warns on corrupt JSON (BH-025), `count_items()` raises `FileNotFoundError` instead of `sys.exit(2)` (BH-027).

6. **Integration test improvements:** Added IN PROGRESS item to shared fixture (BH-017), gate↔canonical parser agreement test (BH-021).

7. **Token profiler completeness:** Subagent milestones now propagated (BH-019), `@property` fields included in profile.json (BH-020), viewer column label corrected (BH-018).

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 2 | 2 | 100% |
| MEDIUM | 5 | 4 | 80% |
| LOW | 2 | 2 | 100% |
| **Total** | **9** | **8** | **89%** |

P4 (models.py contract assumptions) was the only unconfirmed prediction — the module was clean and well-structured. P5 (viewer.py dead code) partially confirmed: no dead code, but encoding gap and test coverage gap found.

### Cumulative Accuracy (Runs 15-20)

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH | 12 | 9 | 75% |
| MEDIUM | 24 | 15 | 63% |
| LOW | 5 | 3 | 60% |
| **Total** | **41** | **27** | **66%** |

## Recommendations

1. **PAT-005 still recurring:** README count drift appeared for the 7th consecutive run. The integration test now catches it, but a pre-commit hook or generator would prevent it from recurring entirely. Escalation count: 6.

2. **PAT-004 still present:** Dual fence-masking implementations (`_common.py` vs `markdown_utils.py`) remain. The divergence (delimiter line handling) is documented and tested but architecturally unresolved. Consider consolidating to a single implementation with a thin wrapper for the hook layer.

3. **Custom pricing not integrated:** The `--pricing` flag loads a JSON file but the custom rates aren't merged with built-in pricing. The infrastructure is in place; the merge logic is the remaining work.

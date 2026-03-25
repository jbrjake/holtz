# Step 0h: Justine Predictions

**Date:** 2026-03-24
**Run:** 16
**Calibration:** Aggressive (HIGH = one strong signal)

## Predictions

### Prediction 1
**Target:** README.md -- semantic claims about features, counts, capabilities
**Predicted Issue:** doc/drift -- README makes specific claims (test count, line count, component counts, feature descriptions) that may not match current implementation. Prior test only checks test count.
**Confidence:** HIGH
**Basis:** Appeared in ALL 4 prior Justine runs. test_readme_metrics_match_actual extracts 9 fields but only fully validates test count. One strong signal: 4/4 recurring recommendation. The test that checks format but not value is a rubber stamp.
**Lens:** integration + contract
**Outcome:** UNCONFIRMED -- test_readme_metrics_match_actual now validates all 9 component counts plus line count (within 100 tolerance). The test is not a rubber stamp for the "What's inside" line. Other README semantic claims (lens count, edge types, iterations) verified manually -- all accurate.

### Prediction 2
**Target:** Token profiler module (scripts/token_profiler/) -- test quality
**Predicted Issue:** test/shallow or test/bogus -- New module (8 source files, 8 test files) never audited by Justine. Tests may check format/structure without checking computed values. Rubber Stamp risk at +1 severity per Justine override.
**Confidence:** HIGH
**Basis:** New code that has not been through a Justine audit. One strong signal: zero prior Justine coverage of this module. 8 test files = large surface for anti-patterns.
**Lens:** component + contract
**Outcome:** UNCONFIRMED -- Token profiler tests are excellent. They check computed values (delta * remaining = session_cost, pricing at $15/MTok, context_window = input + cache_creation + cache_read). No rubber stamps found. No Tautology Tests, Green Bar Addicts, or Permissive Validators. The test suite earns a clean bill on anti-pattern scan.

### Prediction 3
**Target:** hooks/ -- enforcement scope after Run 15 fixes
**Predicted Issue:** bug/logic or test/missing -- Run 15 claimed to fix hook enforcement scope (BJ-001, BJ-002 from prior runs). The fix may be incomplete or may have introduced new edge cases.
**Confidence:** HIGH
**Basis:** Hook enforcement gaps appeared in 2/4 prior Justine runs. Fixes were applied in a602d76. One strong signal: fixing boundary enforcement is where new boundary bugs appear.
**Lens:** integration + security
**Outcome:** PARTIALLY CONFIRMED -- Hook enforcement scope was widened in Run 15 (tests verify PUNCHLIST.md, PUNCHLIST-MERGED.md, justine/ paths for impact_graph_gate; status deletion detection for staleness_gate). However, BJ-002 found a new bug in mask_fenced_blocks that affects ALL hooks using it. The boundary enforcement fix introduced a new boundary bug -- exactly as predicted.

### Prediction 4
**Target:** convergence_check.py + validate_punchlist.py -- header regex alignment
**Predicted Issue:** bug/logic -- Both modules split on `### B[HJ]-\d+:` but the regex details may diverge subtly (anchoring, whitespace handling, multiline flags).
**Confidence:** MEDIUM
**Basis:** This seam has been identified in 2 prior runs as an `assumes` edge. Integration test verifies count agreement. But count agreement does not verify that both parsers extract the same items in the same order -- it is a rubber stamp of the seam.
**Lens:** integration + data-flow
**Outcome:** CONFIRMED via BJ-001 -- parse_brief has the same offset divergence bug. The seam between masking and extraction is exactly where the bug lives. Not in convergence_check/validate_punchlist (which was the predicted target) but in pattern_brief_compact, which uses the same masked-offset-to-original-content pattern. Same class, different location.

### Prediction 5
**Target:** validate_punchlist.py -- filter/render with edge-case punchlists
**Predicted Issue:** bug/logic -- filter_items + render_items are newer code (added for filtered reads). Edge cases: empty punchlist, single item, all-resolved, mixed BH/BJ namespaces, items with code fences containing fake headers.
**Confidence:** MEDIUM
**Basis:** render_items was added to support convergence loop filtered reads. It maps between masked and original content using line-number offsets. Offset mapping is a known fragile pattern.
**Lens:** data-flow + error-propagation
**Outcome:** UNCONFIRMED -- filter_items and render_items in validate_punchlist.py use line-number mapping (not character offsets) for masked-to-original conversion. This was fixed in Run 13. The approach is correct and tested.

### Prediction 6
**Target:** SKILL.md and justine-skill.md -- `${CLAUDE_PLUGIN_ROOT}` references
**Predicted Issue:** doc/drift -- Process docs contain `${CLAUDE_PLUGIN_ROOT}` path references in CLI commands. In dev mode, these don't resolve. Some references may point to files that don't exist or have been renamed.
**Confidence:** MEDIUM
**Basis:** SKILL.md has 5 changes in 50 commits. justine-skill.md references multiple script paths. File renames or reorganizations may not have updated all references.
**Lens:** contract
**Outcome:** UNCONFIRMED -- SKILL.md and justine-skill.md use ${CLAUDE_PLUGIN_ROOT} throughout, which is expected for installed plugin context. In dev mode, callers use local paths per CLAUDE.md instructions. Not a bug, design intent.

### Prediction 7
**Target:** impact_graph.py -- blast_radius and drift_check edge cases
**Predicted Issue:** bug/logic -- blast_radius BFS with depth=0 returns empty (tested). But: what about nodes with no edges? Nodes that don't exist? Self-edges? drift_check with entities that have special regex characters in names?
**Confidence:** LOW
**Basis:** 65% coverage. Lines 320-431 (CLI) uncovered. Core logic tested but edge cases may remain. Prior run said "CLI entrypoints and some subcommands uncovered."
**Lens:** component + error-propagation
**Outcome:** UNCONFIRMED -- blast_radius correctly handles: nodes with no edges (returns []), nodes that don't exist (returns []), self-edges (includes origin), depth=0 (returns []). drift_check uses re.escape on entity names. Coverage is 65% but the uncovered code is CLI glue, not algorithm.

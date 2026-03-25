# Step 0h: Predictive Recon

**Date:** 2026-03-24
**Run:** 15

## Input Sources
1. Pattern brief: no project-level patterns-brief.md (global patterns only)
2. Impact graph: 52 nodes, 52 edges — convergence_gate and convergence_primer are new with risk_score 0.0
3. Git churn: README highest (9), SKILL.md (4), plugin.json (3)
4. Prior run findings: run 14 found 2 code bugs in pattern_brief_compact.py (both PAT-001/PAT-003 family)
5. Recon observations: 9 broken tests, 2 new hooks with 0% coverage, architecture drift

## Predictions

### Prediction 1
**Target:** `tests/test_commit_msg_hook.py`
**Predicted Issue:** test/bogus — Tests reference deleted file `git-hooks/commit-msg`, creating dangling symlink. All version-bump tests are non-functional.
**Confidence:** HIGH
**Basis:** Direct observation during 0c (9 failures), confirmed by file listing (commit-msg absent, post-commit present)
**Lens:** component
**Graph Support:** No graph node for test_commit_msg_hook.py yet
**Outcome:** CONFIRMED — BH-001

### Prediction 2
**Target:** `hooks/convergence_gate.py`, `hooks/convergence_primer.py`
**Predicted Issue:** test/missing — New hooks with zero test coverage (not counted by pytest-cov, not tested in test_hooks.py)
**Confidence:** HIGH
**Basis:** New components (5d0fd62), not present in test_hooks.py, 0% coverage in 0c baseline
**Lens:** component
**Graph Support:** Nodes added in recon, risk_score 0.0 (never audited)
**Outcome:** UNCONFIRMED — Both hooks have extensive tests in test_hooks.py (13+ convergence_gate tests, 9+ convergence_primer tests). Coverage shows 0% because hooks are tested via subprocess, which pytest-cov doesn't track.

### Prediction 3
**Target:** README.md "What's inside" section
**Predicted Issue:** doc/drift — "13,302 lines of code" claim is stale. Actual Python line count is ~16,225.
**Confidence:** HIGH
**Basis:** Commit 76abb91 updated counts but Python alone is 16,225 lines (including tests). No counting method yields 13,302.
**Lens:** public-contract
**Graph Support:** —
**Outcome:** UNCONFIRMED — The 13,302 line count is correct. test_readme_metrics_match_actual counts lines in tests/ + skills/holtz/scripts/ + hooks/ only (.py files), which sums to exactly 13,302. The prediction was based on counting all Python (which includes token_profiler/ source). The counting scope is consistent and validated by integration test.

### Prediction 4
**Target:** `hooks/convergence_gate.py:89`
**Predicted Issue:** bug/logic — `re.search(r'\*\*Status:\*\*[ \t]*(.*)', content)` reads STATUS.md without masking code fences. A code example containing `**Status:**` would match instead of the real field.
**Confidence:** MEDIUM
**Basis:** Global pattern library: code-fence-unaware-parsing. STATUS.md contains markdown with potential code examples. Same pattern family as PAT-001 (5 manifestations across 14 runs).
**Lens:** component
**Graph Support:** convergence_gate → assumes STATUS.md format stability
**Outcome:** UNCONFIRMED — STATUS.md is machine-generated with a well-defined format. It does not contain code fences in practice. The regex finds the first `**Status:**` in the file, which is always the real field under "Current Position". Theoretical risk only.

### Prediction 5
**Target:** `hooks/convergence_primer.py:33`
**Predicted Issue:** bug/logic — Same code-fence-unaware regex pattern as Prediction 4. Reads STATUS.md fields without masking.
**Confidence:** MEDIUM
**Basis:** Same as Prediction 4 — both hooks parse STATUS.md with bare regex
**Lens:** component
**Graph Support:** convergence_primer → assumes STATUS.md format stability
**Outcome:** UNCONFIRMED — Same reasoning as Prediction 4. STATUS.md format is controlled.

### Prediction 6
**Target:** `hooks/convergence_gate.py:45-46`
**Predicted Issue:** bug/logic — `_count_open_items` counts `**Status:** OPEN` and `**Status:** IN PROGRESS` via bare regex in punchlist. Code fences containing punchlist examples would inflate the count.
**Confidence:** MEDIUM
**Basis:** Global pattern library: code-fence-unaware-parsing. Punchlists often contain code examples.
**Lens:** component
**Graph Support:** —
**Outcome:** UNCONFIRMED — Developer explicitly documented this limitation in the docstring: "NOTE: Counts Status fields via simple regex, not scoped to item blocks. Acceptable here because the count is informational (for the block reason message), not decisional." The gate decision is based on STATUS.md/SUMMARY.md existence, not the count.

### Prediction 7
**Target:** README.md "What this looks like in practice" section
**Predicted Issue:** doc/drift — "324 tests across 8,600 lines of code" was accurate at run 14 but counts may have changed since convergence_gate/primer hooks and CLAUDE.md were added.
**Confidence:** LOW
**Basis:** 595 passing tests (excluding 9 broken) suggests the 324 count refers to core Holtz scripts only. May still be correct depending on counting scope.
**Lens:** public-contract
**Graph Support:** —
**Outcome:** UNCONFIRMED — "After 14 runs: 324 tests across 8,600 lines of code" is historical narrative describing the state at run 14's completion. New code was added after run 14, which increased the counts. The README is describing what happened, not claiming current state. The "What's inside" section has the current counts.

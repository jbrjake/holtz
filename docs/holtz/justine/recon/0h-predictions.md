# Justine Predictions (0h)

**Date:** 2026-03-24
**Run:** 15

## Input Sources
1. Holtz's recon data (0a-0f, 0g-0h)
2. Pattern library: code-fence-unaware-parsing, doc-spec-drift
3. Architecture baseline: drift detected
4. Impact graph: 7 nodes, 4 edges (Justine's graph)
5. Direct code reading: convergence_gate.py, convergence_primer.py, test_commit_msg_hook.py

## Predictions

### Prediction J1
**Target:** `hooks/convergence_gate.py:89`
**Predicted Issue:** bug/logic — `re.search(r'\*\*Status:\*\*[ \t]*(.*)', content)` on unmasked STATUS.md. A code fence containing `**Status:** CONVERGED` before the real field bypasses the convergence gate.
**Confidence:** HIGH
**Basis:** Code-fence-unaware-parsing pattern (PAT-001 family). Confirmed by reproduction test.
**Lens:** integration
**Outcome:** CONFIRMED

### Prediction J2
**Target:** `hooks/convergence_primer.py:33`
**Predicted Issue:** bug/logic — Same bare-regex parsing on unmasked content. Code fence before real fields injects wrong Phase/Status/Step into resume context.
**Confidence:** HIGH
**Basis:** Same pattern as J1. Both hooks share the same parsing approach.
**Lens:** integration
**Outcome:** CONFIRMED

### Prediction J3
**Target:** `tests/test_commit_msg_hook.py:7`
**Predicted Issue:** test/bogus — `HOOK_PATH` points to `git-hooks/commit-msg` which does not exist. All version-bump tests create dangling symlinks and silently produce no-op hooks.
**Confidence:** HIGH
**Basis:** Direct observation (9 failures in test baseline). File `git-hooks/commit-msg` deleted in b412c16.
**Lens:** integration
**Outcome:** CONFIRMED

### Prediction J4
**Target:** README.md "What's inside" section
**Predicted Issue:** doc/drift — "13,302 lines of code" claim is stale. Actual Python: 15,662 lines.
**Confidence:** HIGH
**Basis:** Direct measurement. No counting method yields 13,302 for the current codebase.
**Lens:** public-contract
**Outcome:** CONFIRMED

### Prediction J5
**Target:** `hooks/convergence_gate.py:45-46`
**Predicted Issue:** bug/logic — `_count_open_items` counts `**Status:** OPEN` via bare regex on unmasked punchlist content. Code fence examples inflate count.
**Confidence:** MEDIUM
**Basis:** Same code-fence-unaware-parsing pattern. However, docstring explicitly states count is "informational, not decisional."
**Lens:** data-flow
**Outcome:** CONFIRMED (but LOW severity — informational only)

### Prediction J6
**Target:** `tests/test_hooks.py` convergence hook tests
**Predicted Issue:** test/shallow — Convergence hook test fixtures use clean markdown without code fences. The code-fence bypass vulnerability is not tested.
**Confidence:** HIGH
**Basis:** Read all 24 convergence hook tests. No fixture includes fenced blocks. The tests verify the hook works when STATUS.md is well-formed but never test the adversarial case.
**Lens:** integration
**Outcome:** CONFIRMED

### Prediction J7
**Target:** `tests/test_commit_msg_hook.py` "NoBump" tests
**Predicted Issue:** test/bogus — Tests in `TestNoBump` and `TestGuards` pass because the hook never fires (dangling symlink), not because the hook correctly skips non-bumping commits. They assert the version is unchanged, which is trivially true when no hook runs.
**Confidence:** HIGH
**Basis:** Same root cause as J3. If the hook symlink is broken, ALL tests that assert "version unchanged" pass vacuously.
**Lens:** component
**Outcome:** CONFIRMED

### Prediction J8
**Target:** `docs/holtz/architecture-baseline.md`
**Predicted Issue:** doc/drift — Baseline says "No CLAUDE.md or ARCHITECTURE.md exists" but CLAUDE.md was added in d8e4064. Baseline Module Dependencies table missing convergence_gate.py and convergence_primer.py.
**Confidence:** HIGH
**Basis:** Direct comparison of baseline content vs current project state.
**Lens:** contract
**Outcome:** CONFIRMED

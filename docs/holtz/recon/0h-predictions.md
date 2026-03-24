# Phase 0h: Predictive Recon (Run 13)

### Prediction 1
**Target:** `validate_punchlist.py::render_items` (line 317-357)
**Predicted Issue:** Character offset mismatch between masked and original content — items after code fences extracted from wrong positions
**Confidence:** HIGH
**Basis:** Code review shows `match.start()` from `masked` regex used to index `original_content`. `mask_code_fences` replaces fenced lines with empty strings, shifting character offsets. PAT-003 (code-fence-unaware parsing) pattern match. Impact graph `assumes` edge confirms the assumption.
**Lens:** data-flow
**Graph Support:** `assumes` edge: render_items → parse_punchlist (offset assumption)
**Outcome:** CONFIRMED — BH-001

### Prediction 2
**Target:** `README.md:164` ("What's inside" counts)
**Predicted Issue:** Reference doc count (15) and line count (7,800) are stale after today's additions
**Confidence:** HIGH
**Basis:** Counted 17 reference docs (merge-examples.md added today). Total lines 8,494. README highest churn file (rank 5, 9 touches). Prior run 12 also found README drift (BH-001).
**Lens:** public-contract
**Graph Support:** —
**Outcome:** CONFIRMED — BH-002

### Prediction 3
**Target:** `tests/test_pattern_brief_compact.py`
**Predicted Issue:** Ruff lint failures (4 errors) indicate the file was committed without lint checking
**Confidence:** HIGH
**Basis:** Ruff output shows 4 errors. Other test files are clean. This file is new today.
**Lens:** contract
**Graph Support:** —
**Outcome:** CONFIRMED — BH-003

### Prediction 4
**Target:** `validate_punchlist.py::render_items` test coverage
**Predicted Issue:** Existing render_items tests don't exercise items after code fences — the offset bug is untested
**Confidence:** MEDIUM
**Basis:** Reviewed 5 render_items tests — all either render the first item only or check metadata not content. No test has multiple items where a later item is filtered and rendered while earlier items contain code fences.
**Lens:** component
**Graph Support:** —
**Outcome:** CONFIRMED — render_items tests only exercise first-item rendering; no test renders an item after a code-fence-containing item

### Prediction 5
**Target:** SKILL.md Phase 1 and justine-skill.md Phases 1-3
**Predicted Issue:** Subagent compact brief instruction references `pattern_brief_compact.py` but file may not exist on early runs — missing guard
**Confidence:** LOW
**Basis:** The subagent brief says "read the compact pattern brief by running python ... pattern_brief_compact.py docs/holtz/patterns-brief.md". The script exits 0 when the brief doesn't exist (line 156), but the instruction says "if a finding matches a pattern ID, reference it" — subagent may be confused by the error message on stderr.
**Lens:** error-propagation
**Graph Support:** —
**Outcome:** UNCONFIRMED — script exits cleanly with exit 0 and empty stdout; subagent handles gracefully

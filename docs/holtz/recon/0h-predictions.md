# 0h: Predictive Recon

Run 17 predictions — ranked by expected yield.

## Input Sources
1. Pattern Brief: no patterns-brief.md exists (no project-specific patterns to match)
2. Impact Graph: 14 `assumes` edges, 2 `diverges_from` edges — all verified in Run 16
3. Git churn: README.md (15), SKILL.md (10), pattern_brief_compact.py (6)
4. Prior run findings: Run 16 found README doc drift (BH-001, BH-002) and PAT-001 instances (BH-003, BH-004)
5. Recon observations: stale run count, overstated prediction accuracy, generate-changelog.py lint
6. Living punchlist: PAT-001 proactive check clean, no hotspots above 0.5

---

### Prediction 1
**Target:** README.md lines 160, 186-190
**Predicted Issue:** README says "Fifteen runs" but 16 have completed. "After 15 runs: 619 tests" is also stale (Run 16 added tests). Same pattern as BH-002 (Run 16) which fixed "Fourteen" to "Fifteen."
**Confidence:** HIGH
**Basis:** Direct observation during recon (lines 160, 188, 190). Same issue recurred every run since Run 15.
**Lens:** public-contract
**Graph Support:** —
**Outcome:** CONFIRMED — BH-001

### Prediction 2
**Target:** README.md prediction accuracy claims (line ~104)
**Predicted Issue:** README claims HIGH predictions confirm "72% of the time" across "10 runs." Research data (docs/research/convergence-data.md) shows 65% across 11 runs. Both the percentage and run count are wrong.
**Confidence:** HIGH
**Basis:** Direct comparison between README text and research data aggregate table. Run 15 diluted the accuracy (1/3 confirmed) and Run 16 held at 50% (1/2). The 72% figure was accurate through Run 14 but not updated since.
**Lens:** public-contract
**Graph Support:** diverges_from edge between README and convergence-data.md (if one existed)
**Outcome:** CONFIRMED — BH-002

### Prediction 3
**Target:** scripts/generate-changelog.py
**Predicted Issue:** 3 ruff lint errors (F541 empty f-string, SIM108 ternary, ANN201 missing return type). Not in core source but potentially signals less review rigor on this newer file.
**Confidence:** MEDIUM
**Basis:** ruff output during recon step 0d. File was added recently (commit 0dc6533).
**Lens:** component
**Graph Support:** —
**Outcome:** UNCONFIRMED — lint errors exist but no code bugs found. Script logic is correct.

### Prediction 4
**Target:** SKILL.md `${CLAUDE_PLUGIN_ROOT}` references
**Predicted Issue:** In dev mode, `${CLAUDE_PLUGIN_ROOT}` paths in SKILL.md reference the installed plugin location, not the local repo. If any script path is wrong or a script was renamed/moved, the SKILL.md instructions would break in production.
**Confidence:** MEDIUM
**Basis:** SKILL.md has 10+ references to `${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/`. High churn (10 changes). Scripts have been renamed/added over time.
**Lens:** contract
**Graph Support:** —
**Outcome:** UNCONFIRMED — all paths verified, all referenced scripts and reference docs exist**

### Prediction 5
**Target:** docs/research/convergence-data.md
**Predicted Issue:** Research data may not include Run 16 results, or may have stale aggregate totals if Run 16 data was appended without updating the aggregates.
**Confidence:** MEDIUM
**Basis:** Research file was updated (Run 16 data exists in the table) but aggregate tables may not include Run 16.
**Lens:** public-contract
**Graph Support:** —
**Outcome:** CONFIRMED — BH-003 (title, findings table, observations stale; prediction table was updated)

### Prediction 6
**Target:** Living punchlist (docs/holtz/LIVING-PUNCHLIST.md)
**Predicted Issue:** Says "Audits Completed: 1" but Run 16 completed. Prediction accuracy table may not include Run 16 data. History section doesn't have a Run 16 entry.
**Confidence:** LOW
**Basis:** Observation during recon — living punchlist wasn't updated at Run 16 convergence.
**Lens:** semantic-fidelity
**Graph Support:** —
**Outcome:** CONFIRMED — "Audits Completed: 1" should be 2, no Run 16 entry in History. Will be updated at Run 17 convergence.**

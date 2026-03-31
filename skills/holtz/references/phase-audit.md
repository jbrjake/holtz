# Phase: Audit (Steps 5-8)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

### Step 5: Dispatch Justine

After Steps 0-4 complete, dispatch Justine as a background subagent to run her own parallel audit. Use the Agent tool with the `justine` agent:
<!-- Justine stays on Opus — her independent synthesis and prediction require full reasoning capability. Do not downgrade. -->

```
Agent(subagent_type="justine", run_in_background=true, prompt="Run a full audit on this codebase. You are being dispatched in parallel with Holtz.

INHERITED RECON: Holtz's recon data is at docs/holtz/recon/ (step0-project-overview.md, step1-toolchain.md, step2-code-signals.md). Read these for context but write your own recon summary and predictions to docs/holtz/justine/recon/ with your own lens ordering and confidence calibration.

Write all output to docs/holtz/justine/ and use docs/holtz/justine/impact-graph.json for your impact graph. Leave docs/holtz/architecture-baseline.md and docs/holtz/LIVING-PUNCHLIST.md untouched. Run through convergence, then stop. Report completion by writing docs/holtz/justine/SUMMARY.md. Holtz handles the merge and fix loop. This is an autonomous execution context — choose the most conservative default for ambiguities and proceed. Report NEEDS_CONTEXT only if the task is genuinely impossible without human input.")
```

After dispatching, record: `sahjhan event justine_dispatched --mode full` (or `--mode skipped` for targeted audits).

Continue immediately with Step 6. Justine runs in parallel — that is the point. Check for her results before entering Step 9.

**When reviewing Justine's findings during the merge:** Verify her findings by reading actual code and running actual tests. Justine may have flagged false positives (by design — she prefers false positives over missed bugs). Confirm each finding before it enters the merged worklist. If a finding cannot be reproduced, classify it as Justine-only with a note, not as an Agreement.

### Step 6: Doc-to-Implementation Audit

<HARD-GATE>
Step 6 requires completed recon AND a live impact graph. Verify ALL THREE exist before proceeding:
1. `docs/holtz/recon/step3-recon-summary.md`
2. `docs/holtz/recon/step4-predictions.md`
3. `docs/holtz/impact-graph.json`
If any is missing, STOP and complete Steps 0-4 first. Run `ls docs/holtz/impact-graph.json` to verify — do not assume it exists.
</HARD-GATE>

1. Read project docs, `docs/holtz/recon/step3-recon-summary.md`, and `docs/holtz/recon/step4-predictions.md`
2. Extract testable claims into a checklist file: `docs/holtz/audit/1-doc-claims.md`
3. **README.md is mandatory.** If a README exists, extract every concrete claim into the doc-claims checklist. README claims outrank internal doc claims. Classify each as: VERIFIED, OVERSTATED (code does something weaker), FABRICATED (code doesn't do this — HIGH severity), or UNDERSTATED (code does more).
4. **Prioritize predicted areas first** — process claims matching HIGH-confidence predictions before others, then MEDIUM, then LOW, then unpredicted areas. No audit work is skipped; predictions change the order, not the scope.
5. **For each claim** (or batch of 3-5 related claims): check if a real test exists, record findings via `sahjhan event finding` IMMEDIATELY, then move to next batch. When a finding matches a prediction, include `predicted_by` in the finding event and mark the prediction CONFIRMED in `step4-predictions.md`.
6. **Add semantic edges** (`assumes`, `diverges_from`) per [references/impact-graph-operations.md](references/impact-graph-operations.md). After the step, run `stats` — if edge count did not increase and you processed 5+ claims, STOP and re-examine for missed relationships.
7. Run `sahjhan transition recon_complete` to advance protocol state. Mark unconfirmed predictions as UNCONFIRMED in `step4-predictions.md`.

### Step 7: Test Quality Audit

Use **Agent subagents** for this step when possible — each subagent audits a batch of test files and writes findings directly to a temp file. You merge them into the punchlist.

**Model routing:** Dispatch test audit subagents with `model: "sonnet"`. Test quality auditing against a rubric is mechanical pattern-matching work that Sonnet handles well at 5x lower cost. Reserve Opus for the main session where architectural reasoning and cross-referencing happen.

1. Read `docs/holtz/recon/step3-recon-summary.md` for test file locations and `docs/holtz/recon/step4-predictions.md` for predicted areas
2. Partition test files into batches (3-5 files each). **Prioritize predicted areas first.**
3. **Subagent brief:** Instruct each subagent to: (a) read the compact pattern brief by running `python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/pattern_brief_compact.py docs/holtz/patterns-brief.md` — if a finding matches a pattern ID, reference it in the punchlist item; if a pattern match seems likely but uncertain, read the full entry from `docs/holtz/patterns-brief.md` for that specific pattern ID, (b) check known patterns against the code being reviewed, (c) write findings to disk before returning, (d) report exactly one status: DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT, (e) choose the most conservative default for ambiguities — report NEEDS_CONTEXT only if genuinely impossible without human input. **When reviewing subagent output:** verify findings by reading actual code. Subagents may have missed context or misidentified patterns. Confirm each finding before it enters the punchlist.
4. For each batch: audit per [references/anti-patterns.md](references/anti-patterns.md), record findings via `sahjhan event finding` IMMEDIATELY after each batch. Tag findings matching predictions with `predicted_by` field and mark CONFIRMED in `step4-predictions.md`. When mutation data is available from Step 2 (mutation scan), use it as concrete evidence when scoring Rubber Stamp (#11) and Permissive Validator (#12) — a test that passes but doesn't kill mutations for the function it covers is a prime candidate for these anti-patterns.
5. **Add semantic edges** (`tests`, `assumes`, `diverges_from`) per [references/impact-graph-operations.md](references/impact-graph-operations.md). Run `stats` after the step to verify edges were added.
6. Mark unconfirmed predictions for this step as UNCONFIRMED.

If not using subagents: audit one file at a time, write findings before opening the next file.

### Step 8: Adversarial Code Audit

Same subagent strategy. Partition source modules into batches.

**Model routing:** Dispatch source module audit subagents with `model: "sonnet"`. File-level code review against known patterns is a Sonnet-grade task. The main session's adversarial reasoning (testing predictions, confirming bugs) stays on Opus.

1. Read `docs/holtz/recon/step3-recon-summary.md`, `docs/holtz/recon/step2-code-signals.md`, and `docs/holtz/recon/step4-predictions.md`. **Prioritize predicted areas first**, then high-churn files.
2. **Subagent brief:** Instruct each subagent to: (a) read the compact pattern brief by running `python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/pattern_brief_compact.py docs/holtz/patterns-brief.md` — if a finding matches a pattern ID, reference it in the punchlist item; if a pattern match seems likely but uncertain, read the full entry from `docs/holtz/patterns-brief.md` for that specific pattern ID, (b) check known patterns against the code being reviewed, (c) write findings to disk before returning, (d) report exactly one status: DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT, (e) choose the most conservative default for ambiguities. **When reviewing subagent output:** verify findings by reading actual code. Confirm each finding before it enters the punchlist.
3. For each module batch: review for bugs, write punchlist items IMMEDIATELY. Tag findings matching predictions with `**Predicted:**` field and mark CONFIRMED in `step4-predictions.md`. Tag findings with `**Lens:**` field identifying which analytical lens discovered them.
4. **For `bug/*` items:** assess determinism and record in the punchlist item's `**Determinism:**` field. Is this bug deterministic (specific trigger), intermittent (timing/load/ordering dependent), or theoretical (identified from code analysis, not yet observed)? This determines the reproduction strategy in Step 10.
5. **Add semantic edges** (`calls`, `assumes`, `diverges_from`) per [references/impact-graph-operations.md](references/impact-graph-operations.md). Run `stats` after the step to verify edges were added.
6. Run `sahjhan transition audit_complete` to advance protocol state. Mark remaining unconfirmed predictions as UNCONFIRMED in `step4-predictions.md`.

Priority order: error paths, boundaries, state transitions, external integrations, security.

# Phase: Recon (Steps 0-4)

> Core rules, rationalization red flags, and quick reference are in [../SKILL.md](../SKILL.md). Read that first if this is a fresh context.

## Steps (run in order, do not skip)

### Step 0: Project Overview + Drift Detection

#### Run Initialization (before anything else)

Determine the run number N (check `docs/holtz/runs/` for existing runs, or start at 1). Then initialize the run ledger and protocol state — **both commands must succeed before any events are recorded:**

```
sahjhan ledger create --from run N
sahjhan transition run_start
```

All subsequent `event` commands in this run **must** use `--ledger run-N` so findings land in the run ledger, not the default ledger. Omitting `--ledger run-N` causes render warnings and orphaned findings.

#### Reference Reader Subagent

Before starting recon steps, dispatch a reference reader subagent to pre-digest consumable reference docs. This keeps full doc content out of the main context.

```
Agent(subagent_type="general-purpose", model="sonnet", prompt="
Read the following reference docs and return a structured brief for each.
Return ONLY the brief — do not include the full doc text.

For each doc, extract:
1. The key rules/requirements (numbered list, 1-2 sentences each)
2. Any format templates or required fields
3. Any decision criteria or thresholds

Docs to read:
- skills/holtz/references/recommendation-escalation.md
- skills/holtz/references/punchlist-format.md
- skills/holtz/references/status-file-format.md
- skills/holtz/references/recon-procedures.md
- skills/holtz/references/architecture-baseline-format.md
- skills/holtz/references/living-punchlist-format.md
- skills/holtz/references/investigation-format.md
- skills/holtz/references/merge-examples.md
- skills/holtz/references/pattern-contribution-protocol.md

Format your response as:
## <doc-name>
<extracted brief>
(Full protocol: `<path>` — re-read only if the brief is insufficient.)
")
```

Use the returned brief as your working reference for Step 0. Do NOT read the full docs in the main session unless the brief is insufficient for a specific decision.

**Keep in main context** (do NOT move to the reader subagent):
- `references/anti-patterns.md` — cross-referenced during Step 7
- `references/lens-registry.md` — cross-referenced throughout
- `references/merge-protocol.md` — cross-referenced during Step 9
- `references/impact-graph-operations.md` — cross-referenced throughout for graph CLI commands
- `references/output-format.md` — cross-referenced for terminal output throughout
- `references/step-10-fix-loop.md` — cross-referenced during Step 10

Use the reference reader brief for recon procedures (Steps 0-4, mutation scanning, pattern library, architecture drift, predictive recon). If the brief is insufficient for a specific step, re-read [references/recon-procedures.md](references/recon-procedures.md) directly.

Read [references/impact-graph-operations.md](references/impact-graph-operations.md) for all graph CLI commands (initialization, reconciliation, edge operations, blast radius, risk scores).

Create `docs/holtz/` and `docs/holtz/recon/`. Read project structure, docs, CLAUDE.md, architecture. Initialize or reconcile the impact graph. Run architecture drift detection.

Output: `docs/holtz/recon/step0-project-overview.md`

**After each step:** record a `sahjhan event recon_step` with the step number and artifact path. Additionally, record significant findings as `recon_finding` events (e.g., `sahjhan event recon_finding --field topic=architecture --field content="..."`) so they are captured in the run ledger alongside the markdown artifacts.

### Step 1: Run Toolchain (Subagent)

Dispatch a subagent to run in parallel:
- Identify test framework, runner, build system
- Run test suite (capture pass/fail/skip/coverage)
- Check CI pipeline status (if CI exists)
- Run linters/type checkers if configured

Output: `docs/holtz/recon/step1-toolchain.md`

### Step 2: Code Signals (Subagent)

Dispatch a subagent to run in parallel:
- Git churn analysis (top 20 most-changed files in last 50 commits)
- Mutation scan (optional — auto-detected)
- Find skipped/disabled tests
- Cold file coverage scan: list all source files, scan `docs/holtz/archive/*/PUNCHLIST.md` for file paths mentioned in findings and `docs/holtz/LIVING-PUNCHLIST.md` if it exists. A file counts as "audited" if it appears in any prior punchlist finding. On first run (no archive), all files are cold. Compute `cold_file_ratio = files_never_audited / total_source_files`. Write inventory to `docs/holtz/recon/step2-cold-files.md`.

Output: `docs/holtz/recon/step2-code-signals.md`

### Step 3: Recon Summary

Synthesize Steps 0-2 into mental model. Load pattern library. Run recommendation escalation per [references/recommendation-escalation.md](references/recommendation-escalation.md).

Output: `docs/holtz/recon/step3-recon-summary.md`

### Step 4: Predictions

Use extended thinking (ultrathink). Rank where bugs are likely to be found using seven input sources: pattern brief, impact graph risk scores, impact graph edges, git churn, prior run findings, recon observations, and cold file inventory. When `cold_file_ratio` exceeds 40%, add at least 3 cold files to predictions as MEDIUM-confidence targets with basis "never audited — unknown risk," prioritizing files closest to entry points or with the most inbound impact graph edges. Each prediction includes: Target, Predicted Issue, Confidence (HIGH/MEDIUM/LOW), Basis, Lens, Graph Support, Outcome.

Output: `docs/holtz/recon/step4-predictions.md`

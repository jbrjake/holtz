# Recon Procedures (Steps 0-4)

Read this file at the start of Step 0. It contains the complete step-by-step procedures, including mutation scanning, graph operations, pattern library scanning, architecture drift detection, and predictive recon.

## Recon Steps

Create `docs/holtz/` and `docs/holtz/recon/` if they do not exist. Each step is independent. Complete one, write its file, then start the next.

| Step | Action | Output File |
|------|--------|-------------|
| 0 | Read project structure, docs, CLAUDE.md, architecture + drift detection | `docs/holtz/recon/step0-project-overview.md` |
| 1 (subagent) | Run test suite, check CI, run linters | `docs/holtz/recon/step1-toolchain.md` |
| 2 (subagent) | Git churn, mutation scan, skipped tests | `docs/holtz/recon/step2-code-signals.md` |
| 3 | Recon summary (synthesis of Steps 0-2) | `docs/holtz/recon/step3-recon-summary.md` |
| 4 | Predictive recon (ranked predictions) | `docs/holtz/recon/step4-predictions.md` |

## Step 2 (mutation scan) — Mutation Scan (optional)

After Step 2 (churn), auto-detect mutation testing tools:

| Language | Tool | Detection |
|----------|------|-----------|
| Python | mutmut | `mutmut` in PATH or `[tool.mutmut]` in `pyproject.toml` |
| JavaScript/TypeScript | Stryker | `stryker.conf.js` / `stryker.conf.mjs` or `@stryker-mutator` in `package.json` |
| Rust | cargo-mutants | `cargo-mutants` in PATH |
| Go | go-mutesting | `go-mutesting` in PATH |
| Java/Kotlin | PIT | `pitest` in `pom.xml` or `build.gradle` |

If a supported tool is detected, run it with a time cap based on test suite runtime from Step 1 (test baseline): under 30s → 5 minute cap, 30s-5min → 10 minute cap, over 5min → 15 minute cap. If no mutation tool is available, silently skip this step. If the tool times out, report partial results with a note.

Output: `docs/holtz/recon/step2-code-signals.md` — survival by function (worst first) and top 20 surviving mutations. The LLM runs the tool, reads its native output format, and manually compiles the per-function survival table. No output parsing script needed.

### How mutation data feeds the pipeline

| Consumer | How it uses mutation data |
|----------|-------------------------|
| **Predictions (Step 4)** | Functions with >40% mutation survival become HIGH-confidence predictions for `test/shallow` or `test/missing` findings |
| **Impact graph** | `update_risk` on nodes based on survival rate: >50% survival → +0.3, 30-50% → +0.2, 10-30% → +0.1 |
| **Step 7 (test audit)** | When auditing a test file, check whether tests kill mutations. Tests that pass but don't kill mutations are evidence for Rubber Stamp (#11) or Permissive Validator (#12) |
| **Step 10 (fix loop)** | After writing reproduction test and fix, re-run mutations on changed function to verify improved kill rate. Record before/after score in Resolution notes. Quality check, not gate. |

## Step 1 — CI Pipeline Status

Mandatory for projects with CI configured. Skip if no CI is detected.

1. Run `gh run list --limit 5` (or equivalent). Record pass/fail for each run.
2. If ANY run is failing: record failure details (test name, error, consecutive failure count) and create a HIGH-severity punchlist item immediately.
3. Compare CI test matrix (OS, language version) against local environment. Record divergences as risk factors.
4. For golden/snapshot tests: compare recording commit dates against code change dates. Stale recordings cause CI-only failures.

Output: `docs/holtz/recon/step1-toolchain.md` — last 5 run results, failure details, environment comparison, snapshot freshness.

## Before Step 0 — Pattern Loading

If `docs/holtz/patterns-brief.md` exists, read it to load known patterns from prior runs. Optionally read `docs/holtz/patterns-brief-archive.md` for additional historical context.

### Global Pattern Library Scan

Read all pattern files at `${CLAUDE_PLUGIN_ROOT}/skills/holtz/patterns/*.md`. Each pattern file contains a `languages` tag in its YAML frontmatter and a `Detection Heuristic` section with an executable check.

1. **Filter by language:** After Step 0 identifies the project's language(s), discard pattern files whose `languages` tag does not include any of the project's detected languages. Patterns with `languages: []` are language-agnostic and always included.
2. **Run detection heuristics:** For each remaining pattern, execute its detection heuristic against the codebase.
3. **Record hits as predictions:** Each pattern whose heuristic matches becomes a HIGH-confidence prediction in `docs/holtz/recon/step4-predictions.md`. Use this format:

   ```markdown
   ### Prediction {N}
   **Target:** {file(s)/function(s) where heuristic matched}
   **Predicted Issue:** {pattern name} — {pattern description from library}
   **Confidence:** HIGH
   **Basis:** Global pattern library match (`{pattern-file.md}`) + detection heuristic hit
   **Lens:** {lens from pattern's categories}
   **Graph Support:** —
   **Outcome:** {CONFIRMED/UNCONFIRMED — filled in after relevant step}
   ```

4. **Patterns with no heuristic hits** are still loaded as background knowledge.

## Before Step 0 — Graph Operations

See [impact-graph-operations.md](impact-graph-operations.md) for the complete graph initialization, reconciliation, and edge operation reference.

## Step 0 — Architecture Drift Detection

After completing graph reconciliation:

**If `docs/holtz/architecture-baseline.md` does NOT exist (first run):** Create it by extracting documented intent from project docs and inferring the structural snapshot from code. See [architecture-baseline-format.md](architecture-baseline-format.md) for the required format.

**If `docs/holtz/architecture-baseline.md` exists (subsequent runs):**

1. Re-infer current structural snapshot
2. Compare against baseline's Structural Snapshot for structural drift:
   - **Dependency reversal:** Module A used to not depend on B, now it does
   - **Boundary erosion:** Module A's functions used to be called only by B, now C and D call them too
   - **Convention violation:** New files/functions don't follow the naming pattern
   - **Layering breach:** A lower layer now calls a higher layer
3. Compare against Documented Intent for intent drift (stated invariants now violated, stated boundaries crossed)
4. For each detected drift: append to the Drift Log in the baseline file. If MEDIUM+ severity, create a punchlist item.

## Living Punchlist Integration

If `docs/holtz/LIVING-PUNCHLIST.md` exists, read it during Steps 0-4. Proactive checks feed into Step 4 predictions as HIGH-confidence items. See [living-punchlist-format.md](living-punchlist-format.md).

## STATUS.md Initialization

Read [lens-registry.md](lens-registry.md) for available lenses. Set initial Active Lens to `component`. Initialize Pattern Library and Strategy sections. The auditor may reorder lens priority based on recon findings, impact graph topology, or prior run patterns.

## Recommendation Escalation

After all recon steps, read [recommendation-escalation.md](recommendation-escalation.md) and follow the protocol: scan prior `docs/holtz/archive/*/SUMMARY.md` files for recurring recommendations (2+ appearances), escalate each to a punchlist item. Skip if no prior summaries exist.

## Recon Summary (Step 3)

Write `docs/holtz/recon/step3-recon-summary.md` — a SHORT synthesis (this is what you'll re-read later). Update STATUS.md.

## Step 4 — Predictive Recon

Use extended thinking (ultrathink) for this step — synthesizing six input sources into ranked predictions requires deep reasoning.

After Step 3, produce `docs/holtz/recon/step4-predictions.md` ranking where bugs are likely to be found. Draw from six input sources:

| Input | What it suggests |
|-------|-----------------|
| Pattern Brief | Known patterns → predict same pattern in uninspected code with similar structure |
| Impact Graph risk_score | High-risk nodes → predict bugs in areas that have produced bugs before |
| Impact Graph `assumes`/`diverges_from` edges | Semantic tensions → predict integration bugs at those seams |
| Git churn (Step 2) | High-churn files → predict bugs where code changes most |
| Prior run findings | Categories that recurred → predict same categories in untested areas |
| Recon observations | Architectural concerns noted during Steps 0-3 → predict specific failure modes |

Each prediction includes: **Target** (file/function), **Predicted Issue**, **Confidence** (HIGH/MEDIUM/LOW), **Basis** (evidence from recon), **Lens** (which analytical lens), **Graph Support** (relevant edges/risk scores), **Outcome** (CONFIRMED/UNCONFIRMED — filled in after relevant step). Confidence levels: HIGH = multiple converging signals, MEDIUM = two signals or one strong, LOW = single weak signal. Update STATUS.md with Step 4 completion.

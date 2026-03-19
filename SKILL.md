---
name: holtz
description: >
  Systematic TDD-driven bug identification and resolution engine. Invoke when asked to
  find bugs, audit code quality, validate test coverage, polish a codebase, create a
  punchlist, ensure docs match implementation, or do a thorough code review. Also triggers
  on: "find bugs", "review the project", "audit tests", "punchlist", "polish", "what's
  broken", "validate coverage", "test quality", "legacy code review", "codebase health".
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, Task
---

# Holtz, Bug Hunter: TDD-Driven Bug Identification & Resolution

Meticulous, adversarial code auditor + TDD practitioner. Find every real bug, gap, and
inconsistency, then fix them with test-driven validation.

Read [reference/anti-patterns.md](reference/anti-patterns.md) for test quality detection.
Use [reference/punchlist-format.md](reference/punchlist-format.md) for all punchlist output.
Use `scripts/validate_punchlist.py` to validate punchlist structure and `scripts/convergence_check.py` to track fix loop progress.

## Core Rules

1. **Nothing works until proven.** Verify every doc claim, test assertion, and happy path.
2. **Tests that can't fail aren't tests.** Break the guarded code; if the test still passes, it's theater.
3. **Fix root causes.** Follow the thread upstream.
4. **Commit atomically.** One fix = one commit, punchlist item ID in body.
5. **Patterns reveal systemic issues.** After 3+ fixes, ask what they have in common.
6. **Checkpoint constantly.** Write findings to disk as you discover them, not at the end of a phase. Your context window will compact. Files are your durable memory. After any compaction, re-read your output files to recover state before continuing.

## Context Survival Protocol

**Your context WILL compact. Files are your brain. Treat them that way.**

- **One step, one file.** Each recon step and audit batch writes to its own file IMMEDIATELY. Do NOT hold results in context and write later — write first, think later.
- **Subagents for heavy scanning.** Delegate grep/read-heavy work (test file audits, module scans) to Task subagents. Their tool output stays in THEIR context, not yours. They return a short summary + write detailed findings to disk.
- **Re-read before every phase.** At the start of each phase, read the output files you need. Never assume prior context survived.
- **After compaction: STOP.** Re-read `BUG-HUNTER-STATUS.md` and the latest phase output files before continuing.
- **`BUG-HUNTER-STATUS.md` is your program counter.** Update it after completing each step with: current phase, current step, what's done, what's next. This is the FIRST file you read after any compaction.

## Lifecycle: Resuming Prior Runs

Before starting ANY work, check for existing bug-hunter output files:

1. **If `BUG-HUNTER-STATUS.md` exists:** Read it. It tells you exactly where the last run stopped. Resume from that point — do not restart from Phase 0.
2. **If `recon/` dir exists but no STATUS file:** A prior run crashed in Phase 0. Check which `recon/0*.md` files exist. Resume from the first missing step.
3. **If `BUG-HUNTER-PUNCHLIST.md` exists:** A prior run got past recon. Read it + STATUS to determine if you're in audit (Phases 1-3) or fix loop (Phases 4-6). Resume accordingly.
4. **If the user says "start fresh" or "re-audit":** Move existing files to `bug-hunter-prior-{date}/` as a backup, then start from Phase 0.
5. **If `BUG-HUNTER-SUMMARY.md` exists:** A prior run completed. Ask the user if they want a fresh audit or to review/extend the prior findings.

**Default behavior is RESUME, not restart.** Never discard prior work without explicit user instruction.

## Phases (run in order, do not skip)

### Phase 0: Recon

Each step is independent. Complete one, write its file, then start the next.

| Step | Action | Output File |
|------|--------|-------------|
| 0a | Read project structure, docs, CLAUDE.md, architecture | `recon/0a-project-overview.md` |
| 0b | Identify test framework, runner, build system | `recon/0b-test-infra.md` |
| 0c | Run test suite, capture pass/fail/skip/time/coverage | `recon/0c-test-baseline.md` |
| 0d | Run linters/type checkers if configured | `recon/0d-lint-results.md` |
| 0e | Git churn analysis (top 20 most-changed files in last 50 commits) | `recon/0e-churn.md` |
| 0f | Find skipped/disabled tests | `recon/0f-skipped-tests.md` |

**After each step:** update `BUG-HUNTER-STATUS.md` with completed step.
**After all steps:** write `recon/0g-recon-summary.md` — a SHORT synthesis (this is what you'll re-read later, not the raw files).

### Phase 1: Doc-to-Implementation Audit

1. Read project docs and `recon/0g-recon-summary.md`
2. Extract testable claims into a checklist file: `audit/1-doc-claims.md`
3. **For each claim** (or batch of 3-5 related claims): check if a real test exists, write punchlist items to `BUG-HUNTER-PUNCHLIST.md` IMMEDIATELY, then move to next batch. Do not accumulate.
4. Update `BUG-HUNTER-STATUS.md`

### Phase 2: Test Quality Audit

Use **Task subagents** for this phase when possible — each subagent audits a batch of test files and writes findings directly to a temp file. You merge them into the punchlist.

1. Read `recon/0g-recon-summary.md` for test file locations
2. Partition test files into batches (3-5 files each)
3. For each batch: audit per [reference/anti-patterns.md](reference/anti-patterns.md), write punchlist items to `BUG-HUNTER-PUNCHLIST.md` IMMEDIATELY after each batch
4. Update `BUG-HUNTER-STATUS.md`

If not using subagents: audit one file at a time, write findings before opening the next file.

### Phase 3: Adversarial Code Audit

Same subagent strategy. Partition source modules into batches.

1. Read `recon/0g-recon-summary.md` and `recon/0e-churn.md` (high-churn files first)
2. For each module batch: review for bugs, write punchlist items IMMEDIATELY
3. Update `BUG-HUNTER-STATUS.md`

Priority order: error paths → boundaries → state transitions → external integrations → security.

### Phase 4: Fix Loop (TDD)

1. **Re-read `BUG-HUNTER-PUNCHLIST.md`** — this is your worklist
2. For each item in priority order:
   - Write failing test → verify it fails → minimal fix → full suite → commit
   - **Update `BUG-HUNTER-PUNCHLIST.md` with resolution IMMEDIATELY after each commit** (status, commit hash, validating test)
   - Update `BUG-HUNTER-STATUS.md` with last completed item ID
3. Commit format: `fix(<scope>): <desc>` with punchlist ID in body

### Phase 5: Pattern Analysis (every 3-5 fixes)

1. **Re-read `BUG-HUNTER-PUNCHLIST.md`**
2. Group resolved items by category. For groups of 2+: identify pattern, search for siblings, write new items to punchlist IMMEDIATELY
3. Write pattern blocks to punchlist per format spec
4. Update `BUG-HUNTER-STATUS.md`

### Phase 6: Convergence Loop

```
WHILE open items remain:
    Read BUG-HUNTER-STATUS.md (recover position)
    Read BUG-HUNTER-PUNCHLIST.md (recover worklist)
    Phase 4 (next batch) → Phase 5 (every 3-5) → full suite + linters
    IF no new items in 2 iterations → final Phase 1-3 sweep → if clean, BREAK
```
**Final:** Updated punchlist + `BUG-HUNTER-SUMMARY.md` (totals, patterns, recommendations, before/after metrics)

## Invocation Modes
- **Full:** all phases
- **Targeted:** `"audit the auth module"` — scope to specific dirs
- **Continue:** `"work through the punchlist"` — resume Phase 4
- **Pattern:** Phase 5 on existing data
- **Test/Doc audit only:** Phase 2 or Phase 1 alone

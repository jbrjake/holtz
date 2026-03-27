# Lens Enforcement Design

**Date:** 2026-03-27
**Status:** Proposed
**Problem:** Holtz can record `iteration_complete` events and cycle the state machine through all 13 lenses without actually applying any lens. Run 0 proved this — 12 of 13 perspectives were rubber-stamped with zero file reads, zero lens-specific observations, and zero findings. The convergence protocol declared success.

## Root Causes

Three layers failed simultaneously:

1. **Dev-mode hooks not loaded.** `settings.local.json` was missing UserPromptSubmit (primer), Stop (stop_gate), PreToolUse (write_guard, bootstrap), PostToolUse (bash_guard), and SubagentStop hooks. Only commit_gate and protocol_tracker were registered. The stop_gate that should have blocked premature completion was never active.

2. **No hard gate on lens evidence.** `iteration_complete` is a self-reported event. The agent fills in `items_resolved`, `items_remaining`, `tests_passed` — all self-attested. Sahjhan trusts these values. The only timing gate (`min_elapsed: 120s`) prevents rapid-fire but not fabrication.

3. **SKILL.md describes lenses in prose.** "Re-run Steps 6-8 scoped to the current analytical lens" doesn't define what evidence a sweep must produce. The model follows instructions it can operationalize. It can't operationalize "apply the error-propagation lens."

## Design

### 1. Quiz Bank — Generated During Recon, Enforced on Exit

During Step 3 (recon summary), a sonnet subagent generates a quiz bank: 5 multiple-choice questions per lens about the actual codebase. Questions are derived from facts discovered during recon — function signatures, exception types, import relationships, README claims, config values.

**Format (compact — minimizes tokens):**
```json
[
  {
    "lens": "error-propagation",
    "q": "primer.py L56 catches?",
    "a": "A",
    "opts": ["OSError,TimeoutExpired", "FileNotFoundError,TimeoutExpired", "Exception", "SubprocessError"],
    "source": "enforcement/hooks/primer.py:56",
    "keywords": ["except", "raise", "OSError", "TimeoutExpired", "catch"]
  }
]
```

Questions are short. Options are short. No prose. Each entry includes `source` (the file:line the question was derived from) and `keywords` (5-10 lens-vocabulary terms for transcript evidence checking, substring-matched, case-insensitive).

**Storage:** `enforcement/quiz-bank.json`. Protected by `_sahjhan_bootstrap.py` which must be extended to block **Read** tool calls (not just Write/Edit) to paths under `enforcement/`. The lens subagent cannot access the quiz through any Claude tool. Only the SubagentStop hook (a Python process with direct filesystem access) reads it.

**Anti-cheating:** The quiz bank is written during recon, before any lens sweep begins. The lens subagent's dispatch prompt does not include quiz content. The main Holtz context does not include quiz content. The SubagentStop hook is the only reader.

**Answer validation at scoring time:** Because fix commits may change the code between quiz generation and lens sweep execution, the SubagentStop hook re-verifies each answer against the current source file (using the `source` field) before scoring. If the code has changed such that the original answer is no longer correct, the question is dropped from scoring. Passing threshold adjusts: 5 questions → need 4, 4 questions → need 3, 3 questions → need 3. The pass rate (75-80%) is intentionally kept consistent. If more than 2 questions are stale, the quiz bank must be regenerated before the lens sweep proceeds.

### 2. Lens Subagent Dispatch — Hybrid Model

Each lens sweep is dispatched as a subagent. The main context synthesizes findings afterward.

**Dispatch prompt includes:**
- Lens definition and numbered entry-point checklist (from updated SKILL.md)
- Recon summary for context
- Priming: *"Last sweep: rubber-stamped. Findings missed. You're being quizzed on exit."*
- Instructions to write findings to `docs/holtz/audit/lens-<name>.md`
- Machine-parseable identifier: subagent must begin its final message with `LENS: <name>` so the SubagentStop hook can attribute quiz events to the correct perspective
- Answer format instruction: *"When quizzed, respond ONLY with: LENS: error-propagation ANSWERS: A,B,C,D,A"*

**Model routing:** Lens subagents run on sonnet. Mechanical checklist work at 5x lower cost. Main context (architectural reasoning, cross-lens synthesis) stays on opus.

### 3. SubagentStop Hook — Three-Phase Gate

All quiz state lives in the Sahjhan ledger. The hook is stateless — each invocation queries the ledger, reads the quiz bank, and decides.

> **PREREQUISITE:** SubagentStop blocking semantics (block stop → inject reason into subagent context → subagent continues → SubagentStop fires again) must be empirically verified before implementation. Prior designs (2026-03-22) explicitly chose warn-only for SubagentStop because blocking semantics were uncertain. If SubagentStop blocking does NOT work, use the **Fallback Architecture** described below.

**Phase 1: Evidence check**

Parse `agent_transcript_path` (the subagent's full JSONL transcript) using Python regex — no LLM calls, zero token cost:
- ≥5 Read tool calls to source files (not docs, not quiz bank)
- ≥1 Write to `docs/holtz/audit/lens-<name>.md`
- Lens-vocabulary keywords from the quiz bank's `keywords` field present in assistant messages (substring match, case-insensitive)

> **Note:** If `agent_transcript_path` is not provided in SubagentStop events, Phase 1 degrades to checking: (a) output artifact exists on disk with minimum content, (b) `last_assistant_message` contains lens-vocabulary keywords and file:line references. This is weaker but still filters pure rubber stamps.

Fail → block: *"0 files read. Blocked."*

**Phase 2: Quiz**

Extract lens name from `last_assistant_message` (expects `LENS: <name>` prefix). Select 5 questions for this lens from `enforcement/quiz-bank.json`. Record `sahjhan event quiz_posed`. Block stop with questions:

```
Quiz. Format: LENS: error-propagation ANSWERS: A,B,C,D,A
Q1: primer.py L56 catches? A) OSError,TimeoutExpired B) FileNotFoundError,TimeoutExpired C) Exception D) SubprocessError
Q2: ...
```

**Phase 3: Score**

Parse `last_assistant_message` for `LENS: <name> ANSWERS: X,X,X,X,X`. Re-verify each answer against current source (see Section 1 on staleness). Score against quiz bank.

- ≥4/5 → `sahjhan event quiz_answered --field pass=true`. Allow stop.
- <4/5 → `sahjhan event quiz_failed`. Block: *"2/5. Rejected. Read the code."*
- 3rd failure → record `quiz_failed`, then record `quiz_exhausted`. Allow stop. Blocks convergence until human review.

**Circuit breaker:** Max 3 quiz attempts per lens per run. After 3 failures, the lens is marked exhausted and escalated to the human. The `quiz_exhausted` event can be resolved by recording `quiz_exhausted_resolved --field resolution=human_reviewed` after manual review, which clears the convergence block.

### 3b. Fallback Architecture (if SubagentStop blocking is unsupported)

If empirical testing shows SubagentStop cannot block and continue a subagent:

1. Lens subagent completes and stops normally. SubagentStop hook runs Phase 1 (evidence check) only — warns if insufficient, but cannot block.
2. After subagent returns, the **main context** reads `docs/holtz/audit/lens-<name>.md` (the subagent's output artifact).
3. A **PreToolUse hook on Bash** intercepts the `sahjhan event iteration_complete` command. The hook:
   - Reads the quiz bank for this lens
   - Poses 5 questions via `additionalContext` (injected into the main context)
   - Blocks the Bash call with `permissionDecision: "block"` and the quiz questions in `permissionDecisionReason`
4. The main context answers the quiz. On the next attempt to record `iteration_complete`, the hook scores the answers from the prior blocked call's response.

> **PREREQUISITE:** The fallback architecture's anti-cheat depends entirely on Read access to `enforcement/` being blocked (Section 8). The fallback MUST NOT be activated before the bootstrap extension is verified to block Read tool calls. Without that block, the main context can read quiz-bank.json before the hook poses questions.

This is weaker — the main context has access to all files and could look up answers. But:
- The quiz questions are still hidden until the hook poses them (quiz bank is in `enforcement/`, blocked by bootstrap)
- The main context would need to Read each source file to cheat, which costs time and tokens
- Combined with Phase 1 evidence checking (did the subagent actually work?) it still raises the bar significantly above rubber-stamping

### 4. Sahjhan Event and Gate Additions

**New event types** (must be added to `enforcement/events.toml` with full field schemas):

| Event | Key Fields | Patterns |
|-------|------------|----------|
| `quiz_bank_generated` | `project`, `run`, `auditor`, `question_count`, `lens_count` | standard |
| `quiz_posed` | `project`, `run`, `auditor`, `perspective`, `questions_hash` | perspective ∈ set; `questions_hash` is SHA-256 of posed question IDs for audit trail correlation |
| `quiz_answered` | `project`, `run`, `auditor`, `perspective`, `score`, `pass` | pass ∈ `true\|false` |
| `quiz_failed` | `project`, `run`, `auditor`, `perspective`, `score` | |
| `quiz_exhausted` | `project`, `run`, `auditor`, `perspective` | |
| `quiz_exhausted_resolved` | `project`, `run`, `auditor`, `perspective`, `resolution` | resolution = `human_reviewed` |

**New gates:**

On `set complete perspective`:
```toml
# Lens quiz must pass before perspective can be marked clean
{ type = "command_succeeds", cmd = "sahjhan query \"SELECT count(*) >= 1 FROM events WHERE type='quiz_answered' AND pass='true' AND perspective={{current_perspective}}\" | grep -q true" }
```

On `converge`:
```toml
# No unresolved quiz exhaustions
{ type = "query", sql = "SELECT count(*) = 0 FROM events e WHERE e.type='quiz_exhausted' AND e.perspective NOT IN (SELECT r.perspective FROM events r WHERE r.type='quiz_exhausted_resolved')", expect = "true" }
```

> **Note:** Perspective values contain hyphens (e.g., `error-propagation`). These are valid SQL string literals. The `{{current_perspective}}` template is auto-quoted by Sahjhan's interpolation engine — do not add SQL quotes around the template variable.

### 5. Psychological Priming

Three injection points, all under 10 words:

| Point | Text |
|-------|------|
| Subagent dispatch | *"Last sweep: rubber-stamped. Findings missed. You're being quizzed on exit."* |
| Primer (lens sweep active) | *"Lens: {name}. Quiz on exit. Failures restart."* |
| Quiz failure | *"{N}/5. Rejected. Read the code."* |
| Evidence failure | *"0 files read. Blocked."* |
| Exhaustion | *"3 strikes. Escalated to human."* |

Priming is terse and consequence-focused. No explanations, no softening.

### 6. SKILL.md — Per-Lens Executable Checklists

Replace prose lens descriptions with numbered steps and actual commands:

```markdown
**error-propagation** — Trace every exception from throw to catch.
1. `grep -rn "except\|raise" <source>` — list all error sites
2. For each: trace upstream. Where caught? What does caller see?
3. Flag: bare `except:`, swallowed exceptions, type changes across boundaries
4. Write to `docs/holtz/audit/lens-error-propagation.md` with file:line
```

Each lens gets 3-5 concrete steps with grep commands or graph queries as entry points. The model follows checklists. It can't follow "apply the lens."

### 7. Dev-Mode Hook Registration

**`scripts/install-hooks.sh` extended:**
- Generates only the `hooks` section of `.claude/settings.local.json` from `hooks/hooks.json`
- Preserves existing `permissions` section untouched
- Translates `${CLAUDE_PLUGIN_ROOT}/` to relative paths
- Idempotent — safe to re-run

**SessionStart hook:**
- Compares loaded hooks against `enforcement/hooks-manifest.json` (a JSON list of expected hook script paths and their event types, created as part of this implementation)
- Missing hooks → inject via `additionalContext`: *"Hooks incomplete. Run scripts/install-hooks.sh."*

**`run_start` gate:**
```toml
{ type = "command_succeeds", cmd = "python enforcement/hooks/verify_hooks.py" }
```
Blocks audit start if enforcement hooks aren't registered.

### 8. Bootstrap Hook Extension

`_sahjhan_bootstrap.py` currently blocks Write/Edit to `enforcement/`, `bin/sahjhan*`, `hooks/hooks.json`, and itself. Extend to also block **Read** tool calls to `enforcement/` paths. This prevents lens subagents (and the main context) from reading `quiz-bank.json` through any Claude tool.

**Two changes required:**

1. **Hook registration:** Add a separate PreToolUse matcher entry for `"Read"` in both `hooks/hooks.json` and `.claude/settings.local.json`. The existing `"Write|Edit"` matcher does NOT fire for Read tool calls — Read is a distinct tool name requiring its own matcher. Example:
   ```json
   { "matcher": "Read", "hooks": [{ "type": "command", "command": "python enforcement/hooks/_sahjhan_bootstrap.py" }] }
   ```

2. **Hook code:** The `_sahjhan_bootstrap.py` code already extracts `tool_input.file_path` and checks against PROTECTED paths — this logic is identical for Read. No code change needed beyond verifying the path extraction works for Read events (Read uses `file_path` in `tool_input`, same as Write/Edit).

**Test plan for this change:**
- `Read("enforcement/quiz-bank.json")` → BLOCKED
- `Read("enforcement/hooks/primer.py")` → BLOCKED
- `Read("docs/holtz/audit/lens-error-propagation.md")` → ALLOWED
- `Read("skills/holtz/references/lens-registry.md")` → ALLOWED

## Token Budget

| Component | Tokens |
|-----------|--------|
| Quiz bank generation (Step 3, sonnet subagent) | ~5K |
| Per-lens quiz exchange in subagent (5 questions + answer line) | ~500 |
| Per-lens priming in dispatch prompt | ~50 |
| Per-lens primer injection | ~20 |
| Quiz bank JSON on disk | ~3K |
| Evidence check transcript parsing (Python regex, 0 LLM tokens) | 0 |
| **Total LLM overhead per 13-lens run** | ~12K |

Quiz exchanges happen inside subagent contexts. Zero quiz tokens in main context. Transcript parsing is pure Python — no API calls. Budget is for current 13-lens set; scales linearly if lenses are added.

## What This Does NOT Solve

- **Quiz bank quality.** If the recon subagent generates bad questions (ambiguous, wrong answers), the system breaks. The quiz bank generator needs its own validation. The staleness mitigation (re-verify answers at scoring time) handles code drift but not ambiguous questions.
- **Lens subagent capability.** A model that genuinely can't find issues through a specific lens will fail the quiz honestly. The circuit breaker (3 strikes → escalate via `quiz_exhausted`, resolvable via `quiz_exhausted_resolved` after human review) handles this.
- **Cross-lens synthesis.** The main context still needs to synthesize findings across lenses. This design doesn't enforce that synthesis is genuine — it only enforces that each lens was applied.
- **SubagentStop blocking.** If empirical testing shows SubagentStop cannot block and resume a subagent, the fallback architecture (Section 3b) must be used. This is weaker but still substantially better than the current system.

## Test Plan

| # | Scenario | Expected |
|---|----------|----------|
| 1 | `Read("enforcement/quiz-bank.json")` during lens sweep | BLOCKED by bootstrap |
| 2 | `Read("enforcement/hooks/primer.py")` during lens sweep | BLOCKED by bootstrap |
| 3 | `Read("docs/holtz/audit/lens-X.md")` during lens sweep | ALLOWED |
| 4 | Lens subagent stops with 0 Read calls in transcript | SubagentStop blocks: "0 files read. Blocked." |
| 5 | Lens subagent stops with ≥5 reads + artifact written | SubagentStop poses quiz (5 questions) |
| 6 | Subagent answers quiz 5/5 correct | `quiz_answered(pass=true)`, stop allowed |
| 7 | Subagent answers quiz 2/5 correct | `quiz_failed`, stop blocked: "2/5. Rejected." |
| 8 | Subagent fails quiz 3 times | `quiz_exhausted`, stop allowed, convergence blocked |
| 9 | `quiz_exhausted_resolved(human_reviewed)` recorded | Convergence gate unblocked |
| 10 | `set complete perspective` without `quiz_answered(pass=true)` | Transition blocked by gate |
| 11 | `converge` with unresolved `quiz_exhausted` | Transition blocked by gate |
| 12 | 1 quiz question stale (code changed since recon) | Dropped to 4 questions, need 3+ |
| 13 | 3+ quiz questions stale | Quiz bank regen required before sweep |
| 14 | SessionStart with missing hooks | Warning injected: "Hooks incomplete." |
| 15 | `run_start` with missing hooks | Transition blocked |

## Implementation Dependencies

1. **Empirical test:** Verify SubagentStop blocking semantics (dispatch test subagent, block its stop, observe if it continues). This determines whether Section 3 or 3b is implemented.
2. **`enforcement/events.toml`:** Add all 6 new event types with full field schemas
3. **`enforcement/transitions.toml`:** Add `quiz_answered(pass=true)` gate to `set complete perspective` transition
4. **`enforcement/transitions.toml`:** Add `quiz_exhausted` / `quiz_exhausted_resolved` gate to `converge` transition
5. **Bootstrap hook extension:** Add `"Read"` matcher to `hooks/hooks.json` AND `.claude/settings.local.json`; verify `_sahjhan_bootstrap.py` blocks Read to `enforcement/` paths
6. SubagentStop hook rewrite (Python, stateless, queries Sahjhan ledger)
7. Quiz bank generator script (Python, called by sonnet subagent during Step 3)
8. SKILL.md lens checklist rewrite (13 lenses × 3-5 steps each)
9. install-hooks.sh extension (hooks-only section generation, preserves permissions)
10. SessionStart hook for registration validation
11. `enforcement/hooks-manifest.json` creation

No Sahjhan binary changes required. All enforcement is config + hooks + scripts.

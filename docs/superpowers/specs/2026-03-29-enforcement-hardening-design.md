# Enforcement Hardening: Capability-Restricted Protocol Enforcement

**Date:** 2026-03-29
**Origin:** Post-mortem of Run 25 (docs/holtz/postmortem-run25.md)
**Sahjhan dependency:** jbrjake/sahjhan#11 (must land before Phase 1 implementation)

## Problem

Run 25 demonstrated that Holtz's enforcement model is an honor system. The agent operates the Sahjhan CLI that's supposed to constrain it. Every enforcement hook gate can be bypassed by recording success events directly via `sahjhan event`. The quiz system is trivially defeated by reading the answer key and self-recording results.

Four critical exploits were identified:
1. Quiz bypass (read answer key + self-record `quiz_answered`)
2. Lens bulk-completion (batch-mark 13 lenses without individual sweeps)
3. Self-merge (skip merge-agent, adjudicate own competing findings)
4. Raw event injection (record any success event via CLI)

## Trust Model

Three actors with different trust levels:

| Actor | Trust | File Access | CLI Access |
|-------|-------|-------------|------------|
| Hooks | Trusted | Direct `open()` — not interceptable | `sahjhan authed-event` with HMAC |
| Sahjhan binary | Trusted | Own data directory | N/A (is the CLI) |
| Agent | Untrusted | Only via Claude Code tools (Read/Bash), intercepted by hooks | `sahjhan event` (unrestricted types only) |

The key asymmetry: hooks read files directly via Python `open()`; the agent reads files through tools that hooks intercept. This means:
- `.sahjhan/session.key` is readable by hooks, blocked from the agent by `_sahjhan_bootstrap.py`
- `enforcement/quiz-bank.json` is readable by hooks, blocked from the agent
- Hooks compute HMACs with the session key; the agent cannot forge them

## Scope

18 improvements across 2 phases:

- **Phase 1 (Tiers 1+2, items 1-9):** Capability restriction foundation + protocol integrity gates
- **Phase 2 (Tiers 3+4, items 10-18):** Process quality enforcement + efficiency

## Phase 1: Capability Restriction + Protocol Integrity

### Prerequisite: Sahjhan Binary Changes (jbrjake/sahjhan#11)

The following Sahjhan features must land first:

1. **Restricted event types** — `events.toml` gets `restricted = true` field; `sahjhan event` rejects restricted types
2. **Authenticated events** — `sahjhan authed-event <type> --proof <hmac> [--field ...]` validates HMAC against session key
3. **Session key management** — `sahjhan init` generates `.sahjhan/session.key`; `sahjhan config session-key-path` returns path
4. **Read-guard manifest** — `protocol.toml` gets `[guards]` section; `sahjhan guards` returns JSON of paths to read-block
5. **Negation gate type** — `ledger_lacks_event` gate type for transitions.toml

### Layer A: Foundation (Items 1, 2, 4)

Read guards, authenticated events, and the HMAC helper that everything else depends on.

#### Item 1: Read-guard quiz-bank.json

Extend `_sahjhan_bootstrap.py`:
- On startup, call `sahjhan guards` to get the read-blocked manifest
- Block the **Read** tool on guarded paths (currently only blocks Write/Edit)
- Block **Bash** commands that could read guarded paths. Strategy: check if any guarded path appears as an argument in the command string (after path normalization). This catches `cat`, `head`, `python -c "open('...')"`, `base64`, etc. without maintaining a command allowlist. False positives (e.g., `echo "quiz-bank.json"`) are acceptable — the agent has no legitimate reason to reference guarded paths in Bash.
- Add path normalization to handle relative paths, symlinks, `../` traversal via `os.path.realpath()`

Files changed: `enforcement/hooks/_sahjhan_bootstrap.py`

#### Item 2: Require quiz_posed before quiz_answered

Mark these events as restricted in `events.toml`:
- `quiz_posed`, `quiz_answered`, `quiz_failed`, `quiz_exhausted`, `context_reset`

Add gate on `set complete perspective` transition:
```toml
{ type = "query", sql = "SELECT count(*) >= 1 FROM events WHERE type='quiz_posed' AND perspective='{{current_perspective}}'", expect = "true", intent = "quiz must be posed by hook before completion" }
```

The existing quiz_answered gate (line 121 of transitions.toml) already checks for a passing quiz. Combined with restriction, the agent can no longer self-record either event.

Files changed: `enforcement/events.toml`, `enforcement/transitions.toml`

#### Item 4: Event provenance via HMAC

Add shared HMAC computation to `enforcement/hooks/_common.py`:

```python
def compute_event_proof(event_type: str, fields: dict[str, str]) -> str:
    """Compute HMAC-SHA256 proof for a restricted event."""
    key_path = _get_session_key_path()
    key = open(key_path, "rb").read()
    parts = [event_type] + [f"{k}={v}" for k, v in sorted(fields.items())]
    payload = "\0".join(parts).encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()

def record_authed_event(event_type: str, fields: dict[str, str], cwd: str) -> subprocess.CompletedProcess:
    """Record a restricted event with HMAC proof."""
    proof = compute_event_proof(event_type, fields)
    cmd = [sahjhan_binary(), "authed-event", event_type, "--proof", proof]
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
```

Update `lens_quiz.py` and `primer.py` to use `record_authed_event()` instead of subprocess calls to `sahjhan event`.

Files changed: `enforcement/hooks/_common.py`, `enforcement/hooks/lens_quiz.py`, `enforcement/hooks/primer.py`

### Layer B: Quiz & Lens Integrity (Items 3, 5)

Depends on Layer A (needs authenticated events and read guards).

#### Item 3: Subagents answer their own quizzes

Current flow: subagent does lens sweep -> SubagentStop hook fires -> hook checks evidence -> hook poses quiz -> **main agent answers** (because the subagent has already stopped).

New flow: The quiz is posed as part of the subagent's stop gate. The subagent must include its answers in its final message using the existing `LENS: <name> ANSWERS: A,B,C,D,A` format. The hook grades the answers and records authenticated `quiz_posed` + `quiz_answered` events.

The main agent cannot:
- Read the quiz bank (read-guarded)
- Record quiz events (restricted + HMAC-authenticated)
- Bypass the SubagentStop hook (it fires automatically)

Changes to `lens_quiz.py`:
- Phase 1 (evidence check): unchanged
- Phase 2 (quiz pose): pose questions in the SubagentStop block message, requiring the subagent to retry with answers
- Phase 3 (score): grade answers, record `quiz_posed` and `quiz_answered` via `record_authed_event()`
- Remove any code path that allows quiz bypass without the hook

Files changed: `enforcement/hooks/lens_quiz.py`

#### Item 5: Sequential lens rotation

New event type in `events.toml`:

```toml
[events.lens_sweep_started]
description = "A lens sweep has been initiated for a specific perspective"
fields = [
    { name = "perspective", type = "string" },
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
]
```

Add gate on `set complete perspective`:
```toml
{ type = "ledger_has_event_since", event = "lens_sweep_started", filter = { perspective = "{{current_perspective}}" }, since = "last_event_of_type:set_member_complete", intent = "a lens sweep must be started for this perspective before completion" }
```

This prevents batch-marking. The agent must record `lens_sweep_started` for each perspective individually, and the two clean iterations + quiz requirements (already gated) ensure real work happens between the start and completion.

Files changed: `enforcement/events.toml`, `enforcement/transitions.toml`

### Layer C: Protocol Integrity Gates (Items 6, 7, 8, 9)

Independent of Layers A and B. Can be built in parallel.

#### Item 6: Gate merge_complete on merge-agent dispatch

New event type:
```toml
[events.merge_agent_dispatched]
description = "Merge agent subagent was dispatched for finding classification"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
]
```

Add gate on `merge_complete`:
```toml
{ type = "ledger_has_event", event = "merge_agent_dispatched", min_count = 1, intent = "merge must be performed by a separate merge-agent subagent" }
```

Replace the `file_exists` gate with content validation (moved to Phase 2 item 11 for the full implementation; for now, keep `file_exists` and add the dispatch gate).

Files changed: `enforcement/events.toml`, `enforcement/transitions.toml`

#### Item 7: Gate recon_complete on absence of audit findings

Add gate using the new `ledger_lacks_event` type:
```toml
{ type = "ledger_lacks_event", event = "finding", filter = { phase = "audit" }, intent = "no audit-phase findings should exist before recon is complete" }
```

This prevents the agent from doing audit work (Steps 6-8) while still in recon state and then retroactively advancing the state machine.

Files changed: `enforcement/transitions.toml`

#### Item 8: Unconditional commit blocking without fix_commit

`commit_gate.py` currently tracks `unregistered_commits` in the cache and blocks when they exist. The current behavior is correct but the block may not trigger in all states. Change: during `fix_loop` state, make the unregistered-commit check unconditional (not just when `blocks_commit` obligation is set).

Files changed: `enforcement/hooks/commit_gate.py`, `enforcement/hooks/_protocol_cache.py`

#### Item 9: Final sweep minimum read threshold

Add a validation script: `enforcement/scripts/check_sweep_evidence.py` that:
- Reads the conversation transcript (session JSONL)
- Counts distinct file reads during the `final_sweep` state window
- Returns exit 0 if reads >= 30, exit 1 otherwise

Add gate on `converge`:
```toml
{ type = "command_succeeds", cmd = "python enforcement/scripts/check_sweep_evidence.py --min-reads 30", timeout = 15, intent = "final sweep must demonstrate substantive code reading" }
```

Files changed: new `enforcement/scripts/check_sweep_evidence.py`, `enforcement/transitions.toml`

## Phase 2: Process Quality + Efficiency

All items are independent. No dependency chain.

### Item 10: Detect sleep as stalling

In `protocol_tracker.py`, extend stall detection:

```python
def _is_sleep_cmd(cmd: str) -> bool:
    """Detect sleep commands used to game timing gates."""
    m = re.match(r'sleep\s+(\d+)', cmd.strip())
    return m is not None and int(m.group(1)) > 5
```

If `_is_sleep_cmd(cmd)`, increment stall counter by 2 (double penalty).

Files changed: `enforcement/hooks/protocol_tracker.py`

### Item 11: Content validation on merge report

New script: `enforcement/scripts/validate_merge_report.py`

Checks `PUNCHLIST-MERGED.md` for required sections:
- Agreement count line
- Holtz-only section
- Justine-only section
- Blind spot analysis section

Replace `file_exists` gate on `merge_complete` with:
```toml
{ type = "command_succeeds", cmd = "python enforcement/scripts/validate_merge_report.py docs/holtz/PUNCHLIST-MERGED.md", timeout = 10, intent = "merged punchlist must have required sections" }
```

Files changed: new `enforcement/scripts/validate_merge_report.py`, `enforcement/transitions.toml`

### Item 12: TDD evidence in ledger

New event type:
```toml
[events.test_failed_before_fix]
description = "Test demonstrating the bug was run and failed before the fix"
fields = [
    { name = "finding_id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "test_name", type = "string" },
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
]
```

Not restricted (the agent genuinely runs the failing test). Add gate on `fix_commit`:
```toml
{ type = "ledger_has_event_since", event = "test_failed_before_fix", since = "last_transition", intent = "TDD: test must fail before fix is committed" }
```

Files changed: `enforcement/events.toml`, `enforcement/transitions.toml`

### Item 13: Pattern analysis cadence enforcement

In `commit_gate.py`, change the `fixes_since_pattern >= 3` check from soft-warn to hard-block:

```python
if cache.get("fixes_since_pattern", 0) >= 3 and is_git_commit(cmd):
    exit_block("Pattern analysis overdue. Run pattern analysis before next commit.")
```

Files changed: `enforcement/hooks/commit_gate.py`

### Item 14: Severity downgrade requires evidence

Add optional `evidence_path` field to `finding_resolved`. New validation script `enforcement/scripts/check_severity_change.py` that:
- Compares the original finding's severity to the resolution
- If severity was downgraded (e.g., subagent said HIGH, resolved as MEDIUM), requires `evidence_path` field pointing to a real file

Add as a `command_succeeds` gate on `fix_commit` (or as a soft-warn in `commit_gate.py` for the first iteration).

Files changed: `enforcement/events.toml`, new `enforcement/scripts/check_severity_change.py`, `enforcement/hooks/commit_gate.py`

### Item 15: Split SKILL.md into phase sections

Decompose the ~600-line SKILL.md into:

```
skills/holtz/SKILL.md              # Router (~80 lines): core rules, phase index, "read the section for your current phase"
skills/holtz/references/phase-recon.md         # Steps 0-4
skills/holtz/references/phase-audit.md         # Steps 5-8
skills/holtz/references/phase-merge.md         # Step 9
skills/holtz/references/phase-fix-loop.md      # Steps 10-14
skills/holtz/references/phase-convergence.md   # Steps 15-16
skills/holtz/references/phase-finalize.md      # Steps 17-20
```

The router SKILL.md retains: core rules, rationalization red flags, context survival protocol, quick reference. Phase-specific steps move to their own files.

Files changed: `skills/holtz/SKILL.md`, 6 new reference files

### Item 16: Fix CLI aliases

Remove alias documentation from SKILL.md. Replace all alias references (`sahjhan run start`, `sahjhan audit claim`, etc.) with canonical commands (`sahjhan transition run_start`, `sahjhan event audit_claim`).

Files changed: `skills/holtz/SKILL.md` (and phase reference files from item 15)

### Item 17: Fix ledger template resolution

Investigate the `"no ledger found for template 'run'"` warning. Likely causes:
- SKILL.md examples use `--ledger run-N` but the actual ledger was created with a different name format
- The primer hook's context injection references the wrong template name

Fix the SKILL.md documentation and primer hook to use consistent ledger naming.

Files changed: `enforcement/hooks/primer.py`, `skills/holtz/SKILL.md`

### Item 18: Primer injects binary path

In `primer.py`, add the resolved sahjhan binary path to the context injection:

```python
binary = sahjhan_binary()
injection += f"\nSahjhan binary: {binary}"
```

Files changed: `enforcement/hooks/primer.py`

## Dependency Graph

```
Phase 1:
  sahjhan#11 (binary changes) ──┐
                                 ├─> Layer A (items 1, 2, 4)
                                 │       │
                                 │       ├─> Layer B (items 3, 5)
                                 │       │
                                 │   Layer C (items 6, 7, 8, 9) [independent]
                                 │
Phase 2: (all independent, no ordering)
  items 10-18 ── each can be done in any order
  item 15 should precede item 16 (aliases reference SKILL.md sections)
```

## Testing Strategy

Every change gets tests:
- `_sahjhan_bootstrap.py` read-guard: test that Read on guarded paths is blocked; test that Bash `cat` on guarded paths is blocked; test path normalization handles symlinks and traversal
- HMAC helper: test proof computation matches expected output; test round-trip with Sahjhan binary
- `lens_quiz.py` changes: test that subagent answers are graded; test that main agent cannot bypass
- New gates: test each gate condition in isolation using test ledger fixtures
- New scripts (`check_sweep_evidence.py`, `validate_merge_report.py`): unit tests with fixture files

## Risks

1. **Sahjhan#11 delivery timing** — Phase 1 is blocked on binary changes. Mitigation: Phase 2 items 10-18 can proceed independently.
2. **Read-guard bypass via creative Bash** — The agent could find novel ways to read guarded files (e.g., `perl -e`, subshell tricks). Mitigation: block by pattern, add tests for known bypass vectors, accept that determined adversaries can always find new ones. The goal is raising the bar, not perfect security.
3. **SKILL.md decomposition breaks existing runs** — Splitting the skill file changes what the agent reads on startup. Mitigation: the router file retains all critical rules; phase files are additive.

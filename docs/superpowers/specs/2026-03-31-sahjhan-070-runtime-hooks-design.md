# Sahjhan 0.7.0 Runtime Hooks Upgrade — Design Spec

**Date:** 2026-03-31
**Issue:** jbrjake/sahjhan#19
**Release:** jbrjake/sahjhan v0.7.0

## Problem

Sahjhan's enforcement through v0.6.1 is static: generated hook scripts bake in managed paths at generation time, guards only block reads, and there is no mechanism for state-aware runtime enforcement. An agent can edit source files without writing a failing test first, claim the audit is complete while still in `fix_loop`, accumulate edits without committing atomically, and stall in a state indefinitely — all without Sahjhan intervening.

A holtz user reported this exact failure mode in jbrjake/sahjhan#19: the agent declared "HOLTZ AUDIT COMPLETE" while still in `fix_loop` state. The Stop hook checked state but not output. The issue proposed six enforcement patterns. Sahjhan v0.7.0 implements the infrastructure to support all of them.

## Solution

Upgrade holtz from sahjhan 0.6.1 to 0.7.0. Replace bespoke Python enforcement hooks with declarative `hooks.toml` rules evaluated by the `sahjhan hook eval` command. Add comprehensive auto-recording of all tool use to the ledger for ground-truth audit trails.

## New Config: `enforcement/hooks.toml`

### Hook 1: TDD Gate (PreToolUse)

Block source file edits in `fix_loop` without a prior `test_failed_before_fix` event since the last state transition. Filter excludes test files. Every `fix_commit` self-loop is a state transition, so the gate resets after each committed fix.

```toml
[[hooks]]
event = "PreToolUse"
tools = ["Edit", "Write"]
states = ["fix_loop"]
action = "block"
message = "TDD violation: write and run a failing test before editing source files. Record with: sahjhan event test_failed_before_fix --field finding_id=BH-NNN --field test_name=..."

[hooks.gate]
type = "ledger_has_event_since"
event = "test_failed_before_fix"
since = "last_transition"

[hooks.filter]
path_not_matches = "tests/**"
```

### Hook 2: Premature Completion Blocker (Stop)

`output_contains_any` check catches completion language in non-terminal states. This is the exact failure mode from issue #19.

```toml
[[hooks]]
event = "Stop"
states_not = ["converged", "finalized"]
action = "block"
message = "You are claiming completion but sahjhan state is {current_state}, not converged/finalized. Run `sahjhan status` to check your position. Continue the protocol."

[hooks.check]
type = "output_contains_any"
patterns = [
    "audit complete",
    "audit is complete",
    "all fixes applied",
    "CONVERGED",
    "holtz complete",
    "holtz audit complete",
    "all issues resolved",
    "punchlist complete",
    "work is done",
    "summary of everything",
    "convergence achieved",
    "no remaining items",
    "all findings resolved",
]
```

### Hook 3: Edit Accumulation Warning (PostToolUse)

Warns when many events accumulate in `fix_loop` without a state transition. Catches the "batch all fixes then summarize" anti-pattern.

```toml
[[hooks]]
event = "PostToolUse"
tools = ["Edit"]
states = ["fix_loop"]
action = "warn"
message = "High activity: {count} events since your last fix_commit. Each fix must be committed atomically. Run: sahjhan transition fix_commit --item-id BH-NNN"

[hooks.check]
type = "event_count_since_last_transition"
threshold = 8
```

### Hook 4: Auto-Record File Reads (PostToolUse)

Records every Read with file path. The thin wrapper enriches with line_start/line_end from the Read tool's offset/limit parameters.

```toml
[[hooks]]
event = "PostToolUse"
tools = ["Read"]

[hooks.auto_record]
event_type = "file_read"
fields = { file_path = "{tool.file_path}" }
```

### Hook 5: Auto-Record Source Edits (PostToolUse)

Records every Edit/Write/NotebookEdit with file path. The thin wrapper enriches with lines_changed and edit_type (partial vs full_file).

```toml
[[hooks]]
event = "PostToolUse"
tools = ["Edit", "Write", "NotebookEdit"]

[hooks.auto_record]
event_type = "source_edit"
fields = { file_path = "{tool.file_path}" }
```

### Hook 6: Auto-Record File Searches (PostToolUse)

Records Grep tool use. The thin wrapper enriches with pattern and search_path from tool_input (since `{tool.file_path}` doesn't map to Grep's `path` parameter).

```toml
[[hooks]]
event = "PostToolUse"
tools = ["Grep"]

[hooks.auto_record]
event_type = "file_search"
fields = { file_path = "{tool.file_path}" }
```

### Monitor 1: Fix Loop Stall

Warns after 20 events in `fix_loop` without state advancement.

```toml
[[monitors]]
name = "fix_loop_stall"
states = ["fix_loop"]
action = "warn"
message = "{count} events since last state transition. Run `sahjhan status`. If you have been fixing bugs without committing, stop and commit each fix atomically."

[monitors.trigger]
type = "event_count_since_last_transition"
threshold = 20
```

### Monitor 2: Audit Stall

Warns after 30 events in `audit` without state advancement.

```toml
[[monitors]]
name = "audit_stall"
states = ["audit"]
action = "warn"
message = "{count} events in audit state without advancing. Run `sahjhan status` to check progress."

[monitors.trigger]
type = "event_count_since_last_transition"
threshold = 30
```

## New Event Types in `events.toml`

### `file_read`

Auto-recorded on every Read tool use. Wrapper enriches with line span.

```toml
[events.file_read]
description = "File read by agent (auto-recorded by hook eval)"
fields = [
    { name = "file_path", type = "string" },
    { name = "line_start", type = "string", pattern = "^\\d+$", optional = true },
    { name = "line_end", type = "string", pattern = "^\\d+$", optional = true },
    { name = "tool", type = "string" },
]
```

### `source_edit`

Auto-recorded on every Edit/Write/NotebookEdit. Wrapper enriches with change metrics.

```toml
[events.source_edit]
description = "Source file modified by agent (auto-recorded by hook eval)"
fields = [
    { name = "file_path", type = "string" },
    { name = "lines_changed", type = "string", pattern = "^\\d+$", optional = true },
    { name = "edit_type", type = "string", pattern = "^(partial|full_file)$", optional = true },
    { name = "tool", type = "string" },
]
```

### `file_search`

Auto-recorded on every Grep use. Wrapper enriches with search details.

```toml
[events.file_search]
description = "File search by agent (auto-recorded by hook eval)"
fields = [
    { name = "pattern", type = "string", optional = true },
    { name = "search_path", type = "string", optional = true },
    { name = "tool", type = "string" },
]
```

### `bash_command`

Recorded directly by the thin wrapper on every Bash PostToolUse. Not in hooks.toml auto_record because `{tool.file_path}` doesn't map to command text.

```toml
[events.bash_command]
description = "Shell command executed by agent (recorded by post-tool hook)"
fields = [
    { name = "command", type = "string" },
]
```

## Thin Wrapper Hook Scripts

Three new scripts that delegate to `sahjhan hook eval`. Each follows the same pattern: parse the Claude Code hook event from stdin, call `sahjhan hook eval --json` with the appropriate arguments, parse the result, and return the appropriate hook response.

### `pre_tool_hook.py`

**Replaces:** `write_guard.py`
**Registered as:** PreToolUse (after `_sahjhan_bootstrap.py`, before `commit_gate.py`)

1. Extract tool name and file_path from event
2. Call `sahjhan hook eval --event PreToolUse --tool <tool> --file <file> --json`
3. If decision is "block": return block with first block message
4. If decision is "warn": return warn with messages
5. Otherwise: return allow

Hook eval's built-in managed path check (`paths.managed`) replaces the Python-level managed file list from write_guard.py. The TDD gate fires for Edit/Write in fix_loop.

### `post_tool_hook.py`

**Replaces:** nothing (additive)
**Registered as:** PostToolUse (before `bash_guard.py`)

1. Extract tool name, file_path, and full tool_input from event
2. Call `sahjhan hook eval --event PostToolUse --tool <tool> --file <file> --json`
3. Process auto_records: for each, enrich fields from tool_input, then call `sahjhan event <type> --field k=v`
4. For Bash tool (not in hooks.toml auto_record): extract command from tool_input, call `sahjhan event bash_command --field command=<cmd>`
5. Return warn if decision is warn (with monitor warnings), otherwise allow

**Enrichment logic per tool:**

| Tool | Auto-record event | Enrichment |
|------|------------------|------------|
| Read | file_read | `line_start` = offset (default 1), `line_end` = offset + limit - 1 |
| Edit | source_edit | `lines_changed` = newline count in old_string + 1, `edit_type` = "partial" |
| Write | source_edit | `edit_type` = "full_file" |
| NotebookEdit | source_edit | `edit_type` = "partial" |
| Grep | file_search | `pattern` from tool_input.pattern, `search_path` from tool_input.path |
| Bash | bash_command | `command` from tool_input.command (recorded directly, not via auto_record) |

### `stop_hook.py`

**Replaces:** `stop_gate.py`
**Registered as:** Stop

1. Query `sahjhan status` for current state (same logic as current stop_gate.py)
2. If state is terminal or not in active work set: allow
3. If state is in active work set (`audit`, `fix_loop`, `pattern_analysis`, `final_sweep`):
   a. Extract agent output text from event
   b. Call `sahjhan hook eval --event Stop --output-text <text> --json`
   c. If hook eval blocks (premature completion language detected): return block with message
   d. Otherwise: return block with state-based message (same as current stop_gate.py)

The state-based blocking is done in Python (same as current stop_gate.py) because hooks.toml can't express "always block when state matches" without a gate/check condition. The output pattern matching delegates to hook eval.

## Hook Manifest Update

```json
{
  "required_hooks": {
    "PreToolUse": ["_sahjhan_bootstrap.py", "pre_tool_hook.py", "commit_gate.py"],
    "PostToolUse": ["post_tool_hook.py", "bash_guard.py", "protocol_tracker.py"],
    "UserPromptSubmit": ["primer.py"],
    "Stop": ["stop_hook.py"],
    "SubagentStop": ["lens_quiz.py"]
  }
}
```

**Changes:**
- `write_guard.py` removed (replaced by `pre_tool_hook.py`)
- `stop_gate.py` removed (replaced by `stop_hook.py`)
- `pre_tool_hook.py` added to PreToolUse
- `post_tool_hook.py` added to PostToolUse

## Binary Upgrade

Update `enforcement/hooks/_resolve.py`:
- `SAHJHAN_VERSION`: `"0.6.1"` → `"0.7.0"`
- `SAHJHAN_CHECKSUMS`: all four platform checksums from release asset `checksums.sha256`

The bootstrap mechanism handles the rest: detects version mismatch via `.sahjhan-version`, downloads new binary, verifies checksum, installs atomically.

## Files Changed

### New
- `enforcement/hooks.toml` — 6 hooks + 2 monitors
- `enforcement/hooks/pre_tool_hook.py` — PreToolUse thin wrapper
- `enforcement/hooks/post_tool_hook.py` — PostToolUse thin wrapper with auto-record enrichment
- `enforcement/hooks/stop_hook.py` — Stop wrapper with state check + hook eval

### Modified
- `enforcement/hooks/_resolve.py` — version 0.7.0, new checksums
- `enforcement/events.toml` — 4 new event types (file_read, source_edit, file_search, bash_command)
- `enforcement/hooks-manifest.json` — updated hook registration
- `hooks/hooks.json` — plugin hook registration: write_guard.py → pre_tool_hook.py, stop_gate.py → stop_hook.py, add post_tool_hook.py
- `.claude/settings.local.json` — local dev hook registration: same changes as hooks.json
- `README.md` — hooks section updated, "What's inside" count updated, run history extended

### Deleted
- `enforcement/hooks/write_guard.py` — replaced by pre_tool_hook.py
- `enforcement/hooks/stop_gate.py` — replaced by stop_hook.py

### Unchanged
- `enforcement/hooks/_sahjhan_bootstrap.py` — self-protection stays as-is
- `enforcement/hooks/commit_gate.py` — cache-based logic doesn't map to hooks.toml
- `enforcement/hooks/bash_guard.py` — manifest verify is unique behavior
- `enforcement/hooks/protocol_tracker.py` — enforcement cache updates are complementary
- `enforcement/hooks/primer.py` — context injection is unchanged
- `enforcement/hooks/lens_quiz.py` — quiz enforcement is unchanged
- `enforcement/protocol.toml` — no write_gated guards needed; config seal is automatic
- `enforcement/transitions.toml` — already has `since` parameters on all `ledger_has_event_since` gates
- `enforcement/states.toml` — no state changes needed
- `enforcement/renders.toml` — no render changes needed

## What We're NOT Doing

**No write_gated guards.** All docs/holtz/* files are already blocked by `paths.managed`. Write-gated guards are for files that need conditional write access, which holtz doesn't have.

**No transitions.toml changes.** All `ledger_has_event_since` gates already have the required `since` parameter. The breaking change in 0.7.0 doesn't affect holtz.

**No protocol.toml changes.** Config seal computation in 0.7.0 automatically includes hooks.toml as the 6th hash.

## README Update

The "hooks" section gains coverage of the TDD gate, completion blocker, stall monitors, and auto-recording. Written in the existing voice — dry, direct, technically precise. The run history gains a brief mention of the 0.7.0 transition. "What's inside" count updates. No structural changes to the README — the new enforcement weaves into the existing narrative as a natural progression.

## Tests

- Update existing write_guard tests in `test_sahjhan_integration.py` → test pre_tool_hook.py managed path blocking
- Update existing stop_gate tests in `test_sahjhan_integration.py` → test stop_hook.py state + output pattern blocking
- Update `test_protocol_enforcement.py` → remove write_guard import test, add pre_tool_hook equivalents
- Update `test_verify_hooks.py` → replace write_guard.py/stop_gate.py references with new hook scripts
- Update `test_lens_quiz.py` and `test_lens_quiz_integration.py` → quiz questions reference new hook filenames
- Add tests for auto-record enrichment logic (line span extraction, lines_changed counting)
- Add test for TDD gate: Edit in fix_loop without test_failed_before_fix → block
- Add test for TDD gate: Edit in fix_loop WITH test_failed_before_fix → allow
- Add test for TDD gate: Edit to test file in fix_loop → allow (filter excludes tests)
- Add test for premature completion: Stop with "audit complete" in fix_loop → block
- Add test for premature completion: Stop with neutral text in fix_loop → state-based block only
- Add test for bash_command recording from tool_input

Note: `enforcement/quiz-bank.json` and `docs/holtz/impact-graph.json` reference write_guard/stop_gate but are regenerated each audit run — no manual update needed. Archive files are historical and left as-is.

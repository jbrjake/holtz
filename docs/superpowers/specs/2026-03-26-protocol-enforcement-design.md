# Protocol Enforcement Design — State-Driven Pacing

**Date:** 2026-03-26
**Status:** Draft
**Problem:** Agent completed entire fix loop (17 items, 8 commits) without a single sahjhan protocol event. Zero blast_radius, zero hardening, zero fix_commit, zero lens rotation, zero convergence attempts. 665 tests pass. Protocol completely bypassed.

## Root Cause Analysis

Three layers of failure, each independently sufficient:

### Layer 1: Hooks not active in dev mode

`hooks/hooks.json` defines all enforcement hooks using `${CLAUDE_PLUGIN_ROOT}`. In dev mode (local skill invocation via `Skill` tool), the plugin isn't loaded, so hooks.json is never registered. **Zero hooks fired during the entire session.** The stop_gate, write_guard, bash_guard — all silent.

Fix: register hooks in `.claude/settings.local.json` (checked in, always active).

### Layer 2: No active-run marker

Even if hooks fired, `stop_gate.py` and `bash_guard.py` check for `docs/holtz/.sahjhan/active-run` to detect an active audit. This file doesn't exist for the current run. Hooks would early-exit with "no active run — allow."

Fix: sahjhan must write the marker on `run_start`. Verify this works.

### Layer 3: No protocol pacing enforcement

Even if hooks fired AND detected an active run, no hook enforces protocol pacing. The existing hooks are purely defensive:

| Hook | What it does | What it doesn't do |
|------|-------------|-------------------|
| write_guard | Blocks writes to managed files | Nothing about protocol compliance |
| bash_guard | Checks manifest integrity | Doesn't detect git commits or missing fix_commit |
| stop_gate | Blocks premature stop | Only fires on natural stop, not "agent stops working within conversation" |
| primer | Injects resume context on /clear | Nothing during active work |

**The state machine gates are correct but passive.** fix_commit requires blast_radius + hardening. But nothing forces the agent to attempt fix_commit. Gates that never run can't fail.

## Design: State-Driven Protocol Pacer

### Architecture

Two new hooks + one enhanced hook. All stateful via a cache file.

```
PreToolUse (Bash)          PostToolUse (Bash)         UserPromptSubmit
     │                          │                          │
     ▼                          ▼                          ▼
┌─────────────┐          ┌──────────────┐          ┌──────────────┐
│ commit_gate │◄────────►│ proto_tracker│          │    primer     │
│ (block/     │  reads/  │ (update      │          │ (inject 1-   │
│  inject)    │  writes  │  cache)      │          │  line state)  │
└──────┬──────┘          └──────┬───────┘          └──────────────┘
       │                        │
       ▼                        ▼
  .sahjhan/enforcement-cache.json
```

### Cache file: `.sahjhan/enforcement-cache.json`

Maintained by `protocol_tracker` (PostToolUse). Read by `commit_gate` (PreToolUse) and `primer` (UserPromptSubmit).

```json
{
  "active": true,
  "state": "fix_loop",
  "unregistered_commits": ["abc1234"],
  "fixes_since_pattern": 5,
  "perspective": "component",
  "perspectives_done": 0,
  "perspectives_total": 13,
  "stall": 0,
  "last_refresh": "2026-03-26T18:00:00Z"
}
```

Updated after every Bash command. Full refresh (calls `sahjhan status`) only after sahjhan commands or git commits. Stall counter increments on all other Bash commands.

### Hook 1: `protocol_tracker.py` (PostToolUse on Bash)

Fires after every Bash command completes. Inspects the command and result.

Detection logic (applied to `tool_input.command`):
- **`git commit`** (and exit 0): parse commit hash from output, append to `unregistered_commits`
- **`sahjhan`**: call `sahjhan status`, refresh full cache, reset stall counter
- **anything else**: increment `stall` counter

No text injection. No blocking. Pure bookkeeping.

### Hook 2: `commit_gate.py` (PreToolUse on Bash)

Fires before every Bash command. Reads cache. Decides: allow, allow+inject, or block+inject.

Decision table:

| Condition | Command is `git commit` | Command is `sahjhan` | Other command |
|-----------|------------------------|---------------------|---------------|
| unregistered_commits > 0 | **BLOCK** + inject | allow | allow + inject (if stall > 5) |
| stall > 15 | **BLOCK** + inject | allow | **BLOCK** + inject |
| pattern check due (fixes >= 3) | allow + inject | allow | allow |
| No obligations | allow | allow | allow |

Injection format (hard maximum: 30 tokens):

**Block on unregistered commit:**
```
BLOCKED: 2 unregistered commits. sahjhan fix_commit required. State: fix_loop, component (0/13)
```

**Stall injection (soft):**
```
PROTOCOL: 2 unregistered commits pending. Run sahjhan fix_commit.
```

**Pattern check due:**
```
PROTOCOL: pattern_check due (5 fixes since last). sahjhan transition pattern_check
```

**Stall block (hard):**
```
BLOCKED: 15 commands without protocol event. Run sahjhan status.
```

All injections use `additionalContext` in the hook output. The model sees this as system context, not as conversation text. It does not accumulate — each tool call gets at most one injection, and it's attached to that tool call only.

### Hook 3: Enhanced `primer.py` (UserPromptSubmit)

Already exists. Add: read the enforcement cache and append a one-line state summary to the resume context. Max 20 tokens:

```
Protocol: fix_loop | component 0/13 | 2 pending commits | pattern_check due
```

This fires once per user message. Costs 20 tokens per turn. The model starts every turn knowing the protocol state.

### Token budget analysis

| Source | Frequency | Tokens per | Session cost (50 turns, 200 Bash calls) |
|--------|-----------|-----------|----------------------------------------|
| commit_gate injection | ~30% of Bash calls (60) | 25 avg | 1,500 |
| primer state line | 50 turns | 20 | 1,000 |
| **Total** | | | **~2,500** |

For comparison: my verbose SKILL.md "rationalization red flags" table alone is ~400 tokens, cached on every API call after it's loaded. The enforcement overhead is less than the skill's own anti-rationalization text.

### Dev mode hook registration

Add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python enforcement/hooks/commit_gate.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python enforcement/hooks/protocol_tracker.py"
          }
        ]
      }
    ]
  }
}
```

These use relative paths (resolved from cwd) instead of `${CLAUDE_PLUGIN_ROOT}`. Works in dev mode. The existing hooks in `hooks/hooks.json` (using `${CLAUDE_PLUGIN_ROOT}`) continue to work for installed-plugin mode. Both can coexist.

The primer enhancement goes into the existing `primer.py` — no new hook registration needed for UserPromptSubmit (already registered in hooks.json for plugin mode, already in settings.local.json for dev mode if we add it).

### What about hooks.json?

The plugin-mode `hooks/hooks.json` should also register these new hooks so they work when installed. Add `commit_gate` and `protocol_tracker` entries alongside the existing bash_guard, write_guard, etc.

### Active-run marker

Verify that `sahjhan transition run_start` creates `docs/holtz/.sahjhan/active-run`. If not, either:
- Add it to the run_start transition's side effects in sahjhan
- Or: have `protocol_tracker` create it when it first detects a sahjhan status response showing a non-idle state

### Command detection heuristics

The hooks need to detect `git commit` and `sahjhan` commands from the Bash `tool_input.command` string. Simple prefix/substring matching:

```python
cmd = event.get("tool_input", {}).get("command", "")
is_git_commit = "git commit" in cmd and "git commit --amend" not in cmd  # amend is different
is_sahjhan = cmd.strip().startswith("./bin/sahjhan") or cmd.strip().startswith("sahjhan")
```

Edge cases: piped commands (`git commit && sahjhan fix_commit`), aliased commands. Keep detection simple — false negatives (missing a commit) are worse than false positives (refreshing cache unnecessarily).

## Test plan

1. **Unit tests for commit_gate**: mock cache file with various states, verify block/allow/inject decisions
2. **Unit tests for protocol_tracker**: mock tool events (git commit, sahjhan, other), verify cache updates
3. **Integration test**: simulate a mini fix loop — commit without fix_commit, verify gate blocks next commit
4. **Token measurement**: count actual injected tokens across a simulated session, verify < 3,000 total
5. **Dev mode smoke test**: verify hooks fire when registered via settings.local.json

## Files to create/modify

| File | Action |
|------|--------|
| `enforcement/hooks/commit_gate.py` | Create — PreToolUse hook |
| `enforcement/hooks/protocol_tracker.py` | Create — PostToolUse hook |
| `enforcement/hooks/primer.py` | Modify — add cache read + state line |
| `.claude/settings.local.json` | Modify — add hook registrations |
| `hooks/hooks.json` | Modify — add new hooks for plugin mode |
| `tests/test_sahjhan_integration.py` | Add — unit tests for new hooks |
| `tests/test_enforcement_config.py` | Add — config validation for new hooks |

## Open questions

None — design is approved by user. Approach C (commit gate + prompt injection) with state-driven architecture, Bash-only blocking, UserPromptSubmit state line, token-minimal injections.

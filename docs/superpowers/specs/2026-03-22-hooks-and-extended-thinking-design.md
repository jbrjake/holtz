# Hooks (2.9) and Extended Thinking (3.8) Design

**Date:** 2026-03-22
**Status:** Approved
**Context:** Sineya improvement audit identified two gaps: no deterministic enforcement hooks (2.9 FAIL) and no extended thinking for complex reasoning phases (3.8 ABSENT).

## Problem

The holtz plugin relies entirely on advisory instructions (~80% compliance). Two specific compliance failures have been persistent across 10+ runs:

1. **Impact graph never gets created.** The skill describes it, the rationalization table calls it out, and it still doesn't happen. Advisory instructions cannot fix this.
2. **STATUS.md not updated after steps.** The skill says "update after every completed step" but findings get written without STATUS.md updates, causing state loss on compaction.

Additionally, complex reasoning phases (investigation, predictive recon, pattern analysis) would benefit from extended thinking but don't currently enable it.

## Design

### 2.9 — Four Enforcement Hooks

Hooks use the current Claude Code plugin format (March 2026): event-keyed object with `matcher` regex and nested `hooks` array. Defined in `hooks/hooks.json` at the plugin root (per Anthropic docs: plugin hooks go in `hooks/hooks.json`, NOT inside `.claude-plugin/`). Hook scripts are Python in `hooks/`. Exit code 2 blocks; stderr becomes the reason shown to Claude.

**Shared module:** `hooks/_common.py` provides `read_event()` (parse stdin JSON with defensive fallback), `exit_ok()`, `exit_warn(msg)`, `exit_block(msg)`.

#### Hook 1: `impact_graph_gate.py` (PreToolUse, Write|Edit)

**Purpose:** Block writing Phase 1+ audit files unless impact-graph.json exists.

**Logic:**
- Parse `file_path` from `tool_input`
- If path contains `docs/holtz/justine/audit/` → require `docs/holtz/justine/impact-graph.json`
- If path contains `docs/holtz/audit/` (not justine) → require `docs/holtz/impact-graph.json`
- If required graph file missing → exit 2: "BLOCKED: Cannot write audit findings without a live impact graph. Run impact_graph.py to create {path} first."
- All other paths → exit 0

#### Hook 2: `status_staleness_gate.py` (PreToolUse, Write|Edit)

**Purpose:** Block writing findings/recon files unless STATUS.md was recently updated.

**Logic:**
- Parse `file_path` from `tool_input`
- If file IS a STATUS.md → exit 0 (this is the update itself)
- If file is outside `docs/holtz/` → exit 0
- Determine which STATUS.md to check:
  - Path contains `docs/holtz/justine/` → check `docs/holtz/justine/STATUS.md`
  - Otherwise → check `docs/holtz/STATUS.md`
- If STATUS.md doesn't exist → exit 0 (first write of the run, STATUS.md not yet created)
- If STATUS.md mtime > 300 seconds ago → exit 2: "BLOCKED: STATUS.md has not been updated in over 5 minutes. STATUS.md is your program counter — update it before writing more findings."
- Otherwise → exit 0

**Staleness window:** 300 seconds (5 minutes). Allows Investigation Path multi-minute analysis without false positives.

#### Hook 3: `artifact_verification.py` (PostToolUse, Bash)

**Purpose:** After running impact_graph.py, verify the graph file exists on disk.

**Logic:**
- Parse `command` from `tool_input`
- If command does not contain `impact_graph.py` → exit 0
- Extract `--graph <path>` argument (regex handles quoted and unquoted paths)
- If no `--graph` flag → default path = `docs/holtz/impact-graph.json`
- Check `tool_response` for exit code if available
- If file at path does not exist → exit 2: "BLOCKED: impact_graph.py ran but {path} does not exist on disk."
- If file exists → exit 0

#### Hook 4: `subagent_findings_check.py` (SubagentStop)

**Purpose:** When a subagent completes, warn if it claimed to write files that don't exist.

**Logic:**
- Read event JSON via `_common.read_event()`
- Extract `last_assistant_message` field (defensive: if absent, exit 0 silently)
- Scan text for paths matching `docs/holtz/[^ ]*\.md`
- For each matched path → check file exists
- If any missing → exit 1 (warn)
- If all exist or no paths found → exit 0

### hooks/hooks.json

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/impact_graph_gate.py\""
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/status_staleness_gate.py\""
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
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/artifact_verification.py\""
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/subagent_findings_check.py\""
          }
        ]
      }
    ]
  }
}
```

### plugin.json

No change needed — Claude Code auto-discovers `hooks/hooks.json` at the plugin root.

### 3.8 — Extended Thinking (ultrathink)

Add `ultrathink` activation to three sections:

1. **Investigation Path** (`skills/holtz/references/phase-4-fix-loop.md`)
2. **Predictive Recon** (`skills/holtz/references/phase-0-recon.md`, Step 0h)
3. **Pattern Analysis** (`skills/holtz/SKILL.md` Phase 5, `skills/justine/SKILL.md` Phase 5)

## Review Feedback Addressed

- **C1:** Using canonical hooks/hooks.json format with event-keyed structure and matcher regex
- **C2:** SubagentStop reads `last_assistant_message`, defensive fallback if absent
- **I1:** `--graph` regex handles quoted paths
- **I2:** Staleness window increased to 300s
- **I3:** Hook 4 degrades gracefully
- **S1:** Shared `_common.py` module

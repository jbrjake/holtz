"""Shared utilities for Holtz plugin hooks.

All hooks read JSON from stdin and write modern-format JSON to stdout.
Every hook exits 0. The JSON payload controls the decision:

  PreToolUse/PostToolUse/UserPromptSubmit:
  - exit_ok:    {"continue": true,  "suppressOutput": true, ...}
  - exit_warn:  {"continue": true,  "suppressOutput": false, "additionalContext": msg}
  - exit_block: {"continue": false, "suppressOutput": false, "hookSpecificOutput": {...}}

  Stop:
  - exit_stop_allow:  (no output, exit 0)
  - exit_stop_block:  {"decision": "block", "reason": msg}

PreToolUse hooks include hookSpecificOutput with permissionDecision.
See: https://github.com/anthropics/claude-code/issues/17088
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any


def read_event() -> dict[str, Any]:
    """Read and parse the hook event JSON from stdin.

    Returns an empty dict if stdin is empty or unparseable,
    so hooks degrade gracefully rather than crashing.
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def exit_ok(event_name: str = "") -> None:
    """Allow the tool call. Modern JSON on stdout, exit 0.

    For PreToolUse hooks, pass event_name="PreToolUse" to include
    hookSpecificOutput with permissionDecision (avoids phantom
    "hook error" label in the Claude Code UI).
    """
    output: dict[str, Any] = {"continue": True, "suppressOutput": True}
    if event_name == "PreToolUse":
        output["hookSpecificOutput"] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "",
        }
    print(json.dumps(output))
    sys.exit(0)


def exit_warn(msg: str) -> None:
    """Warn but allow. Modern JSON on stdout, exit 0."""
    print(json.dumps({
        "continue": True,
        "suppressOutput": False,
        "additionalContext": msg,
    }))
    sys.exit(0)


def exit_block(msg: str) -> None:
    """Block the tool call. Modern JSON on stdout, exit 0.

    For PreToolUse hooks only — uses hookSpecificOutput with
    permissionDecision "block". PostToolUse hooks should use
    exit_warn() instead since the tool has already executed.
    """
    print(json.dumps({
        "continue": False,
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": msg,
        },
    }))
    sys.exit(0)


def exit_stop_allow() -> None:
    """Allow a Stop event. No output, exit 0.

    Stop hooks use a different protocol than PreToolUse hooks:
    no output = allow the stop. Any output with decision="block"
    prevents the stop and continues the conversation.
    """
    sys.exit(0)


_FENCE_RE = re.compile(r"^(`{3,}|~{3,}).*$", re.MULTILINE)


def mask_fenced_blocks(text: str) -> str:
    """Replace lines inside fenced code blocks with empty strings.

    Preserves line count so regex line numbers stay valid.
    Mirrors the convention from markdown_utils.py but kept here
    to avoid cross-layer imports (hooks and scripts are independent).
    """
    lines = text.split("\n")
    result = []
    fence_marker = ""
    in_fence = False
    for line in lines:
        m = _FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence = True
                fence_marker = m.group(1)[0]
                result.append(line)
            elif line.strip().startswith(fence_marker):
                in_fence = False
                fence_marker = ""
                result.append(line)
            else:
                result.append("")
        elif in_fence:
            result.append("")
        else:
            result.append(line)
    return "\n".join(result)


def exit_stop_block(reason: str) -> None:
    """Block a Stop event. Stop-format JSON on stdout, exit 0.

    The reason is shown to the model, which must then address it
    before the next stop attempt (where stop_hook_active=True
    will allow the stop through).
    """
    print(json.dumps({
        "decision": "block",
        "reason": reason,
    }))
    sys.exit(0)

"""Shared utilities for Holtz plugin hooks.

All hooks read JSON from stdin and write modern-format JSON to stdout.
Every hook exits 0. The JSON payload controls the decision:

  - exit_ok:    {"continue": true,  "suppressOutput": true, ...}
  - exit_warn:  {"continue": true,  "suppressOutput": false, "additionalContext": msg}
  - exit_block: {"continue": false, "suppressOutput": false, "hookSpecificOutput": {...}}

PreToolUse hooks include hookSpecificOutput with permissionDecision.
See: https://github.com/anthropics/claude-code/issues/17088
"""
from __future__ import annotations

import json
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

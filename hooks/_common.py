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


# CommonMark allows code fences to be indented 0-3 spaces (BH-003 run 18).
# Backtick fences must not have backticks in the info string (BH-004 run 18).
# Tilde fences may have tildes in the info string per CommonMark spec.
_BACKTICK_OPEN_RE = re.compile(r"^ {0,3}(`{3,})[^`]*$")
_TILDE_OPEN_RE = re.compile(r"^ {0,3}(~{3,}).*$")
_BACKTICK_CLOSE_TMPL = r"^ {0,3}`{%d,}[ \t]*$"
_TILDE_CLOSE_TMPL = r"^ {0,3}~{%d,}[ \t]*$"


def mask_fenced_blocks(text: str) -> str:
    """Replace lines inside fenced code blocks with empty strings.

    Preserves line count so regex line numbers stay valid.
    Mirrors the convention from markdown_utils.py but kept here
    to avoid cross-layer imports (hooks and scripts are independent).

    Per CommonMark spec:
    - Opening fences may be indented 0-3 spaces (BH-003 run 18)
    - Closing fences may be indented 0-3 spaces independently
    - Backtick info strings must not contain backtick characters (BH-004 run 18)
    - Closing fence must use same character type and at least as many chars (BH-004 run 16)
    """
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    result = []
    fence_count = 0
    close_re: re.Pattern[str] | None = None
    in_fence = False
    for line in lines:
        if not in_fence:
            m = _BACKTICK_OPEN_RE.match(line)
            if m:
                in_fence = True
                fence_count = len(m.group(1))
                close_re = re.compile(_BACKTICK_CLOSE_TMPL % fence_count)
                result.append(line)
                continue
            m = _TILDE_OPEN_RE.match(line)
            if m:
                in_fence = True
                fence_count = len(m.group(1))
                close_re = re.compile(_TILDE_CLOSE_TMPL % fence_count)
                result.append(line)
                continue
            result.append(line)
        else:
            assert close_re is not None
            if close_re.match(line):
                in_fence = False
                close_re = None
                fence_count = 0
                result.append(line)
            else:
                result.append("")
    return "\n".join(result)


def exit_stop_warn(message: str) -> None:
    """Allow a Stop event but surface a warning message.

    Used when enforcement is degraded (e.g., config not found) — the
    stop proceeds but the agent sees the warning. Outputs the warning
    as a stop-format JSON with decision "allow" so Claude Code shows
    the message (hasOutput=true) without blocking continuation.
    """
    print(json.dumps({
        "decision": "allow",
        "reason": message,
    }))
    sys.exit(0)


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

"""Shared utilities for Holtz plugin hooks.

All hooks read JSON from stdin and write modern-format JSON to stdout.
Every hook exits 0. The JSON payload controls the decision:

  PreToolUse:
  - exit_ok:    hookSpecificOutput with permissionDecision "allow"
  - exit_warn:  hookSpecificOutput with permissionDecision "allow" + additionalContext
  - exit_block: hookSpecificOutput with permissionDecision "deny"

  PostToolUse/UserPromptSubmit:
  - exit_ok:    {"continue": true,  "suppressOutput": true}
  - exit_warn:  {"continue": true,  "suppressOutput": false, "systemMessage": msg}

  Stop/SubagentStop:
  - exit_stop_allow:  (no output, exit 0)
  - exit_stop_warn:   {"systemMessage": msg}  (allows stop, shows msg to user)
  - exit_stop_block:  {"decision": "block", "reason": msg}

See: https://code.claude.com/docs/en/hooks
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, NoReturn


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


def exit_ok(event_name: str = "") -> NoReturn:
    """Allow the tool call silently, exit 0.

    For PreToolUse hooks, pass event_name="PreToolUse" to emit
    hookSpecificOutput with permissionDecision "allow".
    Other events get universal top-level fields only.

    See: https://code.claude.com/docs/en/hooks
    """
    if event_name == "PreToolUse":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
            },
            "suppressOutput": True,
        }))
    else:
        print(json.dumps({"continue": True, "suppressOutput": True}))
    sys.exit(0)


def exit_warn(msg: str, event_name: str = "") -> NoReturn:
    """Warn but allow, exit 0.

    When event_name is provided, emits hookSpecificOutput with
    additionalContext (shown to Claude). PreToolUse additionally
    requires permissionDecision.

    Without event_name: uses universal systemMessage (shown to user).

    See: https://code.claude.com/docs/en/hooks
    """
    if event_name == "PreToolUse":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "",
                "additionalContext": msg,
            },
        }))
    elif event_name:
        # PostToolUse, UserPromptSubmit, etc. — hookSpecificOutput
        # with additionalContext injects context to Claude
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": msg,
            },
        }))
    else:
        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "systemMessage": msg,
        }))
    sys.exit(0)


def exit_block(msg: str) -> NoReturn:
    """Block the tool call (PreToolUse only), exit 0.

    Emits hookSpecificOutput with permissionDecision "deny".
    The reason is shown to Claude so it can adapt.

    Valid permissionDecision values: "allow", "deny", "ask", "defer".
    Do NOT use "continue": false — that stops Claude entirely.

    See: https://code.claude.com/docs/en/hooks
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        },
    }))
    sys.exit(0)


def exit_stop_allow() -> NoReturn:
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


def exit_stop_warn(message: str) -> NoReturn:
    """Allow a Stop event but surface a warning message.

    Used when enforcement is degraded (e.g., config not found) — the
    stop proceeds but the user sees the warning. Uses the universal
    systemMessage field (shown to user). Stop hooks only support
    decision="block"; omit decision to allow.

    See: https://code.claude.com/docs/en/hooks
    """
    print(json.dumps({
        "systemMessage": message,
    }))
    sys.exit(0)


def exit_stop_block(reason: str) -> NoReturn:
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

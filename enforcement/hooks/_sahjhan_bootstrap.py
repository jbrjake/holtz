#!/usr/bin/env python3
"""Sahjhan bootstrap hook — protects enforcement infrastructure.

DO NOT MODIFY. This hook protects itself.

PreToolUse hook that blocks Write/Edit to enforcement/, bin/sahjhan*,
hooks/hooks.json, and this file. Uses correct PreToolUse output protocol
(hookSpecificOutput with permissionDecision).
"""
from __future__ import annotations

import json
import os
import sys

PROTECTED = [
    "enforcement/",
    "bin/sahjhan",
    "hooks/hooks.json",
    "_sahjhan_bootstrap.py",
]

# Resolve plugin root: enforcement/hooks/ -> enforcement/ -> repo root
_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        event = {}

    path = event.get("tool_input", {}).get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    if not path:
        _allow()
        return

    # Resolve both absolute and relative paths
    resolved = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(cwd, path))

    # Protected paths are relative to plugin root, not cwd
    for p in PROTECTED:
        full = os.path.realpath(os.path.join(_PLUGIN_ROOT, p))
        if resolved.startswith(full) or resolved == full:
            _block(
                f"BLOCKED: {path} is protected enforcement infrastructure. "
                "This file cannot be modified during an audit session."
            )
            return

    _allow()


def _allow() -> None:
    print(json.dumps({
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "",
        },
    }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({
        "continue": False,
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": reason,
        },
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()

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

    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")
    cwd = event.get("cwd", os.getcwd())

    # BH-016: Check Bash commands for shell redirections to protected paths
    # BH-011: Also block cp/mv/install targeting protected paths
    # BH-008: Check that the protected path is the TARGET, not just present
    if command and not path:
        for p in PROTECTED:
            # Redirect check: protected path must appear after the redirect operator
            for op in (">", ">>"):
                idx = command.find(op)
                if idx >= 0:
                    after_op = command[idx + len(op):].strip()
                    if after_op.startswith(p):
                        _block(
                            f"BLOCKED: Bash command redirects to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                        return
            # tee check: protected path must follow "tee"
            if "tee " in command:
                tee_idx = command.find("tee ")
                after_tee = command[tee_idx + 4:].strip()
                if any(arg.startswith(p) for arg in after_tee.split()):
                    _block(
                        f"BLOCKED: Bash command tees to protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )
                    return
            # cp/mv/install check: protected path must be the LAST argument (destination)
            cmd_stripped = command.lstrip()
            if any(cmd_stripped.startswith(c) for c in ("cp ", "mv ", "install ")):
                args = cmd_stripped.split()
                if len(args) >= 3:
                    dest = args[-1]
                    if dest.startswith(p):
                        _block(
                            f"BLOCKED: Bash command copies/moves to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                        return
        _allow()
        return

    if not path:
        _allow()
        return

    # Resolve both absolute and relative paths
    resolved = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(cwd, path))

    # Protected paths are relative to plugin root, not cwd
    for p in PROTECTED:
        full = os.path.realpath(os.path.join(_PLUGIN_ROOT, p))
        if resolved == full or resolved.startswith(full + os.sep):
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

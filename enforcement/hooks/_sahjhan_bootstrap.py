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

READ_GUARDED = [
    ".sahjhan/session.key",
    "enforcement/quiz-bank.json",
]

# Resolve plugin root: enforcement/hooks/ -> enforcement/ -> repo root
_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def _is_read_guarded(path: str, cwd: str) -> str | None:
    """Check if a resolved path matches any read-guarded path. Returns the guard or None."""
    resolved = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(cwd, path))

    # Structural guard: any session.key under a .sahjhan directory tree
    parts = resolved.replace("\\", "/").split("/")
    if "session.key" in parts and ".sahjhan" in parts:
        sahjhan_idx = parts.index(".sahjhan")
        key_idx = parts.index("session.key")
        if key_idx > sahjhan_idx:
            return ".sahjhan/**/session.key"

    for g in READ_GUARDED:
        for base in (os.path.join(cwd, "docs", "holtz"), _PLUGIN_ROOT, cwd):
            full = os.path.realpath(os.path.join(base, g))
            if resolved == full or resolved.startswith(full + os.sep):
                return g
    return None


def _bash_references_guarded(command: str, cwd: str) -> str | None:
    """Check if a Bash command references any read-guarded path."""
    cmd_lower = command.lower()
    # Structural guard: any command referencing session.key in a .sahjhan context
    if "session.key" in cmd_lower and ".sahjhan" in cmd_lower:
        return ".sahjhan/**/session.key"

    for g in READ_GUARDED:
        if g.lower() in cmd_lower:
            return g
        if g.startswith(".sahjhan/"):
            full_rel = os.path.join("docs", "holtz", g)
            if full_rel.lower() in cmd_lower:
                return g
    return None


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        event = {}

    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")
    cwd = event.get("cwd", os.getcwd())
    tool_name = event.get("tool_name", "")

    # Read guard: block Read tool on guarded paths
    if tool_name == "Read" and path:
        guard = _is_read_guarded(path, cwd)
        if guard:
            _block(
                f"BLOCKED: Cannot read '{guard}'. "
                "This file is protected enforcement infrastructure."
            )
            return

    # Read guard: block Bash commands that reference guarded paths
    if command:
        guard = _bash_references_guarded(command, cwd)
        if guard:
            _block(
                f"BLOCKED: Bash command references read-guarded path '{guard}'. "
                "This file cannot be accessed during an audit session."
            )
            return

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
            # In-place modification tools: sed -i, perl -pi, patch
            for prefix in ("sed ", "perl "):
                if prefix in command:
                    # Check if any argument references a protected path
                    args = command.split()
                    if any(arg.startswith(p) or ("/" + p) in arg for arg in args):
                        _block(
                            f"BLOCKED: Bash command modifies protected path '{p}' in-place. "
                            "This path cannot be modified during an audit session."
                        )
                        return
            if "patch " in command:
                args = command.split()
                if any(arg.startswith(p) or ("/" + p) in arg for arg in args):
                    _block(
                        f"BLOCKED: Bash command patches protected path '{p}'. "
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

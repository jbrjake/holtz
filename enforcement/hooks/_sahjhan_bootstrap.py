#!/usr/bin/env python3
"""Sahjhan bootstrap hook — protects enforcement infrastructure.

DO NOT MODIFY. This hook protects itself.

PreToolUse hook that:
- Blocks Write/Edit to enforcement/, bin/sahjhan*, hooks/hooks.json, and this file
- Blocks Bash commands that write to protected or managed paths
- Blocks Bash commands that invoke privileged sahjhan daemon commands
- Provides defense-in-depth guards for Grep/Glob tools on enforcement paths
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

# BH-001 (run 27): Sahjhan-managed files in docs/holtz/ that are rendered
# from ledger state. Direct writes (including via Bash) must be blocked.
MANAGED_DOCS = [
    "docs/holtz/STATUS.md",
    "docs/holtz/PUNCHLIST.md",
    "docs/holtz/SUMMARY.md",
    "docs/holtz/MERGE-REPORT.md",
    "docs/holtz/PUNCHLIST-MERGED.md",
]

# Issue #33: The .sahjhan data directory contains enforcement state (cache,
# ledger, active-run marker). Writes and deletes must be blocked.
MANAGED_DATA = [
    "docs/holtz/.sahjhan/",
]

# Combined set of all paths that must be protected from Bash writes.
ALL_PROTECTED = PROTECTED + MANAGED_DOCS + MANAGED_DATA

# Privileged sahjhan subcommands that the agent must not invoke directly.
# Defense-in-depth: the daemon's caller authentication is the primary boundary.
BLOCKED_DAEMON_CMDS = [
    "sahjhan sign",
    "sahjhan verify",
    "sahjhan vault",
    "sahjhan daemon stop",
]

# Resolve plugin root: enforcement/hooks/ -> enforcement/ -> repo root
_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def _bash_references_daemon_cmd(command: str) -> str | None:
    """Check if a Bash command invokes a privileged sahjhan daemon command.

    Returns the blocked command pattern if found, None otherwise.
    """
    cmd_lower = command.lower()
    for blocked in BLOCKED_DAEMON_CMDS:
        if blocked in cmd_lower:
            return blocked
    return None


def _segment_references_protected(segment: str, protected: list[str]) -> str | None:
    """Check if any argument in a shell segment references a protected path."""
    args = segment.split()
    for arg in args:
        for p in protected:
            if arg == p or arg.startswith(p) or ("/" + p) in arg:
                return p
    return None


def _check_bash_write(command: str) -> str | None:
    """Check if a bash command writes to any protected or managed path.

    Returns a block reason string if blocked, None if allowed.
    Splits on shell operators (&&, ||, ;, |, newline) and checks each segment.
    """
    import re

    # Issue #33: Pre-split interpreter check — python3 -c commands with
    # semicolons inside the string argument get split by the segment splitter,
    # causing the interpreter prefix and the path reference to appear in
    # different segments. Check the full command first.
    cmd_stripped = command.lstrip()
    for interp in ("python ", "python3 ", "ruby ", "node "):
        if cmd_stripped.startswith(interp) and " -" in cmd_stripped:
            for p in ALL_PROTECTED:
                if p in command:
                    return (
                        f"BLOCKED: Bash command uses interpreter to write to protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )

    # Split on shell operators to handle chained commands (BH-004 run 27)
    # BH-005 run 28: bare newline is a valid shell command separator — include \n
    segments = re.split(r'\s*(?:&&|\|\||[;|\n])\s*', command)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        for p in ALL_PROTECTED:
            # Redirect check: find ALL > and >> in the segment, not just first
            # BH-002 (run 27): quoted > before real redirect bypassed old check
            for op in (">>", ">"):  # check >> before > to avoid partial match
                start = 0
                while True:
                    idx = seg.find(op, start)
                    if idx < 0:
                        break
                    # Skip << (heredoc) — >> at idx means idx-1 might be >
                    if op == ">" and idx > 0 and seg[idx - 1] in "<>":
                        start = idx + 1
                        continue
                    after_op = seg[idx + len(op):].strip()
                    # Take first whitespace-delimited token as the target
                    target = after_op.split()[0] if after_op.split() else ""
                    if target == p or target.startswith(p):
                        return (
                            f"BLOCKED: Bash command redirects to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                    start = idx + len(op)

            # tee check
            if "tee " in seg:
                tee_idx = seg.find("tee ")
                after_tee = seg[tee_idx + 4:].strip()
                if any(arg == p or arg.startswith(p) for arg in after_tee.split()):
                    return (
                        f"BLOCKED: Bash command tees to protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )

            # cp/mv/install check: protected path as LAST argument
            seg_stripped = seg.lstrip()
            if any(seg_stripped.startswith(c) for c in ("cp ", "mv ", "install ")):
                args = seg_stripped.split()
                if len(args) >= 3:
                    dest = args[-1]
                    if dest == p or dest.startswith(p):
                        return (
                            f"BLOCKED: Bash command copies/moves to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )

            # Issue #33: rm/rmdir check — destructive operations on protected paths
            # Also match trailing-slash-stripped form so that
            # "rm -rf docs/holtz/.sahjhan" matches "docs/holtz/.sahjhan/".
            if any(seg_stripped.startswith(c) for c in ("rm ", "rm\t", "rmdir ")):
                p_stripped = p.rstrip("/")
                ref = _segment_references_protected(seg, [p, p_stripped])
                if ref:
                    return (
                        f"BLOCKED: Bash command removes protected path '{p}'. "
                        "This path cannot be deleted during an audit session."
                    )

            # In-place modification tools: sed -i, perl -pi, patch
            for prefix in ("sed ", "perl "):
                if prefix in seg:
                    ref = _segment_references_protected(seg, [p])
                    if ref:
                        return (
                            f"BLOCKED: Bash command modifies protected path '{p}' in-place. "
                            "This path cannot be modified during an audit session."
                        )
            if "patch " in seg:
                ref = _segment_references_protected(seg, [p])
                if ref:
                    return (
                        f"BLOCKED: Bash command patches protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )

            # BH-002 (run 27): Interpreter execution — python -c, dd, wget
            # These can write to arbitrary paths without using shell redirects.
            # Use substring match on full segment — paths may be inside quotes.
            for interp in ("python ", "python3 ", "ruby ", "node "):
                if seg_stripped.startswith(interp) and " -" in seg_stripped and p in seg:
                    return (
                            f"BLOCKED: Bash command uses interpreter to write to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
            if seg_stripped.startswith("dd ") and ("of=" + p) in seg_stripped:
                return (
                    f"BLOCKED: Bash command uses dd to write to protected path '{p}'. "
                    "This path cannot be modified during an audit session."
                )
            if seg_stripped.startswith("wget "):
                args = seg_stripped.split()
                for i, arg in enumerate(args):
                    # BH-006 run 28: handle both -O <path> and --output-document=<path>
                    if arg == "-O" and i + 1 < len(args) and args[i + 1].startswith(p):
                        return (
                            f"BLOCKED: Bash command uses wget to write to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                    if arg.startswith("--output-document="):
                        target = arg.split("=", 1)[1]
                        if target == p or target.startswith(p):
                            return (
                                f"BLOCKED: Bash command uses wget to write to protected path '{p}'. "
                                "This path cannot be modified during an audit session."
                            )
            # BH-007 run 28: curl -o / --output handler
            if seg_stripped.startswith("curl "):
                args = seg_stripped.split()
                for i, arg in enumerate(args):
                    if arg in ("-o", "--output") and i + 1 < len(args) and args[i + 1].startswith(p):
                        return (
                            f"BLOCKED: Bash command uses curl to write to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                    if arg.startswith("--output="):
                        target = arg.split("=", 1)[1]
                        if target == p or target.startswith(p):
                            return (
                                f"BLOCKED: Bash command uses curl to write to protected path '{p}'. "
                                "This path cannot be modified during an audit session."
                            )

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

    # Bash tool: check for write operations and privileged daemon commands
    if command and not path:
        # Block privileged sahjhan daemon commands (defense-in-depth)
        daemon_cmd = _bash_references_daemon_cmd(command)
        if daemon_cmd:
            _block(
                f"BLOCKED: Bash command invokes privileged sahjhan command '{daemon_cmd}'. "
                "Only trusted hook scripts may call sahjhan sign/vault/daemon commands."
            )
            return
        result = _check_bash_write(command)
        if result:
            _block(result)
            return
        _allow()
        return

    # Grep/Glob tools: defense-in-depth write protection
    # (no read guards needed — secrets live in daemon memory, not on disk)
    if tool_name in ("Grep", "Glob") and not path:
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

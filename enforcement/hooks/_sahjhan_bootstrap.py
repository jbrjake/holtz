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

# BH-001 (run 27): Sahjhan-managed files in docs/holtz/ that are rendered
# from ledger state. Direct writes (including via Bash) must be blocked.
MANAGED_DOCS = [
    "docs/holtz/STATUS.md",
    "docs/holtz/PUNCHLIST.md",
    "docs/holtz/SUMMARY.md",
    "docs/holtz/MERGE-REPORT.md",
    "docs/holtz/PUNCHLIST-MERGED.md",
]

# Combined set of all paths that must be protected from Bash writes.
ALL_PROTECTED = PROTECTED + MANAGED_DOCS

# Resolve plugin root: enforcement/hooks/ -> enforcement/ -> repo root
_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def _load_read_guards() -> list[str]:
    """Load read-guarded paths from sahjhan guards command.

    Falls back to hardcoded defaults if the binary is unavailable.
    """
    import subprocess
    try:
        binary = os.path.join(_PLUGIN_ROOT, "bin", "sahjhan-" + _platform_triple())
        if os.path.isfile(binary):
            result = subprocess.run(
                [binary, "--config-dir", os.path.join(_PLUGIN_ROOT, "enforcement"), "guards"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                guards = data.get("read_blocked", [])
                if guards:
                    return guards
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass
    return [".sahjhan/session.key", "enforcement/quiz-bank.json"]


def _platform_triple() -> str:
    """Return the platform triple for the current system.

    Delegates to _resolve.platform_triple() for single source of truth.
    """
    from _resolve import platform_triple
    return platform_triple()


READ_GUARDED = _load_read_guards()


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
    """Check if a Bash command references any read-guarded path.

    BH-016: Also blocks glob patterns that could expand to guarded paths.
    Checks parent directory references (.sahjhan/, enforcement/) with
    wildcard characters to catch glob-based bypass attempts.
    """
    cmd_lower = command.lower()
    # Structural guard: any command referencing session.key in a .sahjhan context
    if "session.key" in cmd_lower and ".sahjhan" in cmd_lower:
        return ".sahjhan/**/session.key"

    # BH-016: Block glob patterns targeting guarded directories.
    # If the command references a guarded parent dir AND contains glob chars,
    # treat it as a potential bypass.
    _GLOB_CHARS = ("*", "?", "[")
    if ".sahjhan" in cmd_lower and any(c in command for c in _GLOB_CHARS):
        return ".sahjhan/**/session.key"

    for g in READ_GUARDED:
        if g.lower() in cmd_lower:
            return g
        if g.startswith(".sahjhan/"):
            full_rel = os.path.join("docs", "holtz", g)
            if full_rel.lower() in cmd_lower:
                return g
        # BH-016: Check parent directory of guarded path with glob chars
        parent = os.path.dirname(g)
        if parent and parent.lower() in cmd_lower and any(c in command for c in _GLOB_CHARS):
            return g
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

    # BH-016, BH-011, BH-008, BH-001/002/004 (run 27): Check Bash commands
    # for write operations targeting protected or managed paths.
    # Split on shell operators first, then check each segment independently.
    if command and not path:
        result = _check_bash_write(command)
        if result:
            _block(result)
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

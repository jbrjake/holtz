#!/usr/bin/env python3
"""Commit gate — blocks git commits when protocol obligations are pending.

PreToolUse hook for Bash. Reads the enforcement cache and decides:
- BLOCK git commit when prior commits are unregistered
- BLOCK all non-sahjhan Bash when stall threshold exceeded
- INJECT terse directive when soft obligations exist (pattern check due)
- ALLOW everything else silently
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import (  # noqa: E402
    compute_obligations,
    format_injection,
    is_enforcement_fresh,
    is_fix_loop_state,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache,
)

from _common import exit_block, exit_ok, exit_warn, read_event  # noqa: E402


def _is_test_cmd(cmd: str) -> bool:
    """Detect test/pytest commands that should always be allowed.

    Checks each segment of chained commands (split on &&, ||, ;, |)
    so that ``cd /project && pytest`` is recognized.
    """
    import re as _re
    for segment in _re.split(r'&&|\|\||[;|]', cmd):
        seg = segment.strip()
        if seg.startswith("pytest") or seg.startswith("python -m pytest"):
            return True
    return False


def main() -> None:
    event = read_event()
    cmd = event.get("tool_input", {}).get("command", "")
    cwd = event.get("cwd", os.getcwd())

    cache = read_cache(cwd)

    # Sahjhan commands are always allowed
    if is_sahjhan_cmd(cmd):
        exit_ok("PreToolUse")

    # Stale enforcement: pass through without blocking
    if not is_enforcement_fresh(cache):
        exit_ok("PreToolUse")

    # Unconditional: in fix_loop, git commit requires prior fix_commit registration
    if cache and is_fix_loop_state(cache) and is_git_commit(cmd):
        commits = cache.get("unregistered_commits", [])
        if commits:
            exit_block(
                f"BLOCKED: {len(commits)} unregistered commit(s). "
                "Run sahjhan transition fix_commit before committing again."
            )

    obligations = compute_obligations(cache)

    if not obligations:
        exit_ok("PreToolUse")

    # Hard block: pattern analysis overdue after 3+ fixes
    if (cache is not None
            and cache.get("state") == "fix_loop"
            and is_git_commit(cmd)
            and cache.get("fixes_since_pattern", 0) >= 3
            and not cache.get("unregistered_commits")):
        exit_block(
            "BLOCKED: Pattern analysis overdue "
            f"({cache['fixes_since_pattern']} fixes since last analysis). "
            "Run: sahjhan transition pattern_check"
        )

    blocks_commit = any(o.get("blocks_commit") for o in obligations)
    blocks_all = any(o.get("blocks_all") for o in obligations)
    injection = format_injection(obligations, cache)

    # Hard block: stall threshold exceeded (overrides test allowance)
    if blocks_all:
        exit_block(injection)

    # Test commands are allowed unless stall threshold exceeded
    if _is_test_cmd(cmd):
        exit_ok("PreToolUse")

    # Hard block: git commit with unregistered prior commits
    if is_git_commit(cmd) and blocks_commit:
        exit_block(injection)

    # Soft injection: obligations exist but don't block this command
    if injection:
        exit_warn(injection, "PreToolUse")

    exit_ok("PreToolUse")


if __name__ == "__main__":
    main()

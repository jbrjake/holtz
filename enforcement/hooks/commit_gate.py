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

from _common import (  # noqa: E402
    exit_block,
    exit_boundary_missing,
    exit_ok,
    exit_warn,
    read_event,
    resolve_config_dir,
)
from _protocol_cache import (  # noqa: E402
    compute_obligations,
    contains_sahjhan_cmd,
    format_injection,
    is_enforcement_fresh,
    is_fix_loop_state,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache_with_boundary,
)


def _is_test_cmd(cmd: str) -> bool:
    """Detect test/pytest commands that should always be allowed.

    Checks each segment of chained commands (split on &&, ||, ;, |, newline)
    so that ``cd /project && pytest`` is recognized.
    """
    import re as _re
    for segment in _re.split(r'&&|\|\||[;|\n]', cmd):
        seg = segment.strip()
        if seg.startswith("pytest") or seg.startswith("python -m pytest"):
            return True
    return False


def main() -> None:
    event = read_event()
    cmd = event.get("tool_input", {}).get("command", "")
    cwd = event.get("cwd", os.getcwd())
    config_dir, _ = resolve_config_dir(cwd)

    cache, boundary = read_cache_with_boundary(cwd)

    # Before the sahjhan-command allowance, not after it. Without the
    # boundary the daemon serves nothing restricted, but `transition`,
    # `event` and `set` write the ledger straight to disk — so allowing them
    # through would let the run keep advancing while the enforcement that is
    # supposed to be gating it does nothing. The escape is not a command:
    # the user types `holtz-stop`, which is a prompt, not a tool call.
    if boundary:
        exit_boundary_missing(boundary)

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
                f"Run sahjhan --config-dir {config_dir} transition fix_commit before committing again."
            )

    obligations = compute_obligations(cache, config_dir=config_dir)

    if not obligations:
        exit_ok("PreToolUse")

    # Hard block: pattern analysis overdue after 3+ fixes
    if (cache is not None
            and cache.get("state") == "fix_loop"
            and is_git_commit(cmd)
            and cache.get("pattern_analysis_overdue", False)
            and not cache.get("unregistered_commits")):
        # The flag is the `pattern_analysis_overdue` named query, evaluated
        # against the ledger by protocol_tracker. `pattern_check`'s own gate is
        # that same query — so the escape printed here is ready precisely when
        # this block fires. #77 was the version where it was not. (#82 H8
        # checks this file still names the query the escape is gated on.)
        exit_block(
            "BLOCKED: Pattern analysis overdue "
            "(3+ findings resolved since the last analysis). "
            f"Run: sahjhan --config-dir {config_dir} transition pattern_check"
        )

    blocks_commit = any(o.get("blocks_commit") for o in obligations)
    blocks_all = any(o.get("blocks_all") for o in obligations)
    injection = format_injection(obligations, cache)

    # Hard block: stall threshold exceeded (overrides test allowance).
    # Exception: a line that runs a sahjhan enforcement subcommand — even
    # wrapped, e.g. ``cd repo && sahjhan status | head`` — is the legitimate
    # way to re-sync and clear the stall. The stall block is a nudge, not a
    # security gate, so let it through (never a git commit). #70 item 1.
    if blocks_all:
        if contains_sahjhan_cmd(cmd) and not is_git_commit(cmd):
            exit_ok("PreToolUse")
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

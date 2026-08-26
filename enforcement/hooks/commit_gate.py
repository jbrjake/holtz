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
    event_actor,
    format_injection,
    is_enforcement_fresh,
    is_fix_loop_state,
    is_git_commit,
    is_sahjhan_cmd,
    pending_commits_for,
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

    # Unconditional: in fix_loop, git commit requires prior fix_commit
    # registration — of *this actor's* own commits (P0.3, D41). A sibling fix
    # subagent's pending commit is not evidence about this caller, and the
    # escape named below is the orchestrator's transition, which a subagent
    # cannot run.
    if cache and is_fix_loop_state(cache) and is_git_commit(cmd):
        commits = pending_commits_for(cache, event_actor(event))
        if commits:
            exit_block(
                f"BLOCKED: {len(commits)} unregistered commit(s). "
                f"Run sahjhan --config-dir {config_dir} transition fix_commit before committing again."
            )

    # Same actor the tracker charged, so what this reads is this caller's own
    # command history and not the run's aggregate traffic (P3.2).
    obligations = compute_obligations(
        cache, config_dir=config_dir, actor=event_actor(event),
    )

    if not obligations:
        exit_ok("PreToolUse")

    # Pattern analysis is owed at the batch boundary, not at every commit:
    # `iteration_boundary` and `set complete perspective` both gate on
    # `pattern_analysis_overdue`, which is how a run cannot reach a /clear or a
    # finished lens without the round. A commit is not a boundary — it lands
    # between a fix that is already written, verified and green and the ledger
    # entry naming it, so stopping there buys nothing and interrupts the cycle
    # to run a 17.9-min median analysis on top of an uncommitted tree. It stays
    # a soft obligation here, which is what `compute_obligations` emits.

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

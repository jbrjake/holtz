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
    query_named_predicate,
    read_cache_with_boundary,
)
from _resolve import ensure_sahjhan  # noqa: E402


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


def _pattern_analysis_still_overdue(cwd: str, config_dir: str) -> bool:
    """Re-derive the pattern-analysis backlog from the ledger, right now.

    Returns True when the ledger confirms the obligation, and also when the
    question cannot be answered — the cached flag is the fallback, not a
    fabricated "all clear".
    """
    binary = ensure_sahjhan()
    if binary is None:
        return True
    # The name is spelled out here rather than imported: H8 walks the chain
    # block -> value -> query -> gate by finding the query name in this file's
    # source, so a constant from another module would hide the link it checks.
    overdue = query_named_predicate(binary, config_dir, cwd, "pattern_analysis_overdue")
    return True if overdue is None else overdue


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

    # Hard block: pattern analysis overdue after 3+ fixes.
    #
    # The flag is the `pattern_analysis_overdue` named query, evaluated against
    # the ledger by protocol_tracker. `pattern_check`'s own gate is that same
    # query — so the escape printed here is ready precisely when this block
    # fires. #77 was the version where it was not. (#82 H8 checks this file
    # still names the query the escape is gated on.)
    #
    # The cached value is a snapshot, written when protocol_tracker observes a
    # sahjhan command. A command it fails to observe, or a status refresh that
    # times out, leaves the flag describing a ledger that has since moved on —
    # and a commit blocked on a stale snapshot is unanswerable, because the
    # escape it prints has already been done. Held commits for 12-25 minutes at
    # a time. So the last conjunct re-derives the fact from the ledger now:
    # same named query, evaluated at the moment of the block. Short-circuit
    # ordering keeps it off every other path.
    if (cache is not None
            and cache.get("state") == "fix_loop"
            and is_git_commit(cmd)
            and cache.get("pattern_analysis_overdue", False)
            and not cache.get("unregistered_commits")
            and _pattern_analysis_still_overdue(cwd, config_dir)):
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

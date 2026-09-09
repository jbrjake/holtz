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
    audit_abandoned,
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
from _shell_norm import shell_segments  # noqa: E402


def _is_test_cmd(cmd: str) -> bool:
    """Detect test/pytest commands that should always be allowed.

    Checks each segment of a chained command so that ``cd /project &&
    pytest`` is recognized. Segmentation is ``_shell_norm``'s.
    """
    return any(
        seg.startswith(("pytest", "python -m pytest"))
        for seg in shell_segments(cmd)
    )


def main() -> None:
    event = read_event()
    cmd = event.get("tool_input", {}).get("command", "")
    cwd = event.get("cwd", os.getcwd())
    config_dir, _ = resolve_config_dir(cwd)

    cache, boundary, _version = read_cache_with_boundary(cwd)

    # Before the sahjhan-command allowance, not after it. Without the
    # boundary the daemon serves nothing restricted, but `transition`,
    # `event` and `set` write the ledger straight to disk — so allowing them
    # through would let the run keep advancing while the enforcement that is
    # supposed to be gating it does nothing. The escape is not a command:
    # the user types `holtz-stop`, which is a prompt, not a tool call.
    #
    # Unless the run is already over. Then that ordering costs what it was
    # buying: `_daemon_lifecycle` runs ahead of this hook, blocks a terminated
    # audit with a message that names the situation, and exempts `sahjhan
    # daemon start`/`stop` so the human can recover — and this gate revoked
    # the exemption. `audit_abandoned` is checked here rather than the
    # ordering being swapped, because freshness is False for a live audit too
    # (item 41).
    if boundary and not audit_abandoned(cwd):
        exit_boundary_missing(boundary)

    # Sahjhan commands are always allowed
    if is_sahjhan_cmd(cmd):
        exit_ok("PreToolUse")

    # Stale enforcement: pass through without blocking
    if not is_enforcement_fresh(cache):
        exit_ok("PreToolUse")

    # Unconditional: in fix_loop, git commit requires prior fix_commit
    # registration — of *this actor's* own commits (P0.3, D41). A sibling fix
    # subagent's pending commit is not evidence about this caller.
    #
    # The escape below is reachable by whichever actor this blocks, which it
    # was not before sahjhan 0.25.0/0.26.0. `fix_commit`'s two tree-reading
    # gates and its `finding_resolved` emit are anchored on the caller, so a
    # fix subagent blocked on a second commit registers the first one from its
    # own worktree: the gates read the tree holding the commit, and the emit
    # stamps that tree's hash — which is the hash the tracker charged, so this
    # charge is what discharges. The orchestrator's path is unchanged; it calls
    # from the project root, where caller and project anchor are the same
    # directory (sahjhan#46, #48; item 43).
    #
    # `item_id` is positional and required — the CLI refuses a bare
    # `transition fix_commit` — so it is named in the escape rather than left
    # for the reader to discover from a second error.
    if cache and is_fix_loop_state(cache) and is_git_commit(cmd):
        commits = pending_commits_for(cache, event_actor(event))
        if commits:
            exit_block(
                f"BLOCKED: {len(commits)} unregistered commit(s): "
                f"{', '.join(commits)}. Register from the tree holding the "
                f"commit — run sahjhan --config-dir {config_dir} transition "
                f"fix_commit BH-NNN, where BH-NNN is the finding that commit "
                f"fixes, before committing again."
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

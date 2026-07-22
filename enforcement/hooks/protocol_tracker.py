#!/usr/bin/env python3
"""Protocol tracker — updates enforcement cache after Bash commands.

PostToolUse hook for Bash. Detects git commits and sahjhan commands,
updates the enforcement cache file. Never blocks. Pure bookkeeping.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    bash_exit_code,
    bash_output,
    exit_ok,
    read_event,
    resolve_config_dir,
)
from _protocol_cache import (  # noqa: E402
    contains_sahjhan_cmd,
    empty_cache,
    is_enforcement_fresh,
    is_git_commit,
    is_sahjhan_cmd,
    parse_status_text,
    read_cache,
    update_cache,
    write_cache,
)
from _resolve import ensure_sahjhan  # noqa: E402


def _is_tdd_cmd(cmd: str) -> bool:
    """Detect test, lint, and type-check commands (TDD workflow).

    Checks each segment of chained commands (split on &&, ||, ;, |, newline)
    so that ``cd /project && python -m pytest`` is recognized.
    """
    _TDD_PREFIXES = ("pytest", "python -m pytest", "ruff check", "ruff format", "mypy")
    for segment in re.split(r'&&|\|\||[;|\n]', cmd):
        seg = segment.strip()
        if any(seg.startswith(p) for p in _TDD_PREFIXES):
            return True
    return False


def _is_sleep_cmd(cmd: str) -> bool:
    """Detect sleep commands used to game timing gates.

    Returns True for sleep >5 seconds. Short sleeps (<=5s) are allowed
    for legitimate polling. Checks each segment of chained commands
    (split on &&, ;, ||, |, newline). Handles bash sleep suffixes (s/m/h/d).
    """
    _SUFFIX_MULTIPLIER = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for segment in re.split(r'&&|\|\||[;|\n]', cmd):
        m = re.match(r"^\s*sleep\s+(\d+(?:\.\d+)?)([smhd])?", segment)
        if m:
            value = float(m.group(1))
            suffix = m.group(2)
            seconds = value * _SUFFIX_MULTIPLIER.get(suffix or "s", 1)
            if seconds > 5:
                return True
    return False


def _parse_commit_hash(output: str) -> str:
    """Extract short commit hash from git commit output."""
    m = re.search(r"\[.*?\s([0-9a-f]{7,})\]", output)
    return m.group(1) if m else "unknown"


def _runs_transition(cmd: str, command: str) -> bool:
    """True iff cmd invokes ``sahjhan ... transition <command>`` (verb-adjacent).

    Distinguishes the *mutating* transition from read-only diagnostics that
    merely mention the command name as a bare token — ``sahjhan gate check
    fix_commit``, ``sahjhan query "... 'fix_commit' ..."``, ``sahjhan status``.
    Only the actual transition should move cache bookkeeping. #77.
    """
    tokens = cmd.split()
    return any(
        tok == "transition" and tokens[i + 1] == command
        for i, tok in enumerate(tokens[:-1])
    )


# #77: the authoritative backlog for "pattern analysis overdue" is the ledger,
# NOT a hand-mirrored counter. This is the SAME query the `pattern_check`
# transition gate uses (enforcement/transitions.toml) — count finding_resolved
# events since the last pattern_analysis_complete. Deriving fixes_since_pattern
# from it means the commit gate's block condition (>= 3) and the pattern_check
# gate's readiness (>= 3) are one fact and can never disagree, so the block's
# printed escape ("run transition pattern_check") is always satisfiable.
_FIXES_SINCE_PATTERN_SQL = (
    "SELECT count(*) AS n FROM events "
    "WHERE type='finding_resolved' "
    "AND seq > COALESCE((SELECT MAX(seq) FROM events "
    "WHERE type='pattern_analysis_complete'), 0)"
)


def _query_fixes_since_pattern(binary: str, config_dir: str, cwd: str) -> int | None:
    """Ledger-derived count of finding_resolved since the last pattern analysis.

    Runs sahjhan's generic `query` primitive against the active ledger (the same
    ledger the gates evaluate). Returns None on any failure — binary/daemon
    unavailable, timeout, non-zero exit, or malformed output — so the caller
    preserves the last known counter instead of resetting it. An under-count
    only delays the pattern nudge; it never deadlocks a commit. #77.
    """
    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "query",
             _FIXES_SINCE_PATTERN_SQL, "--format", "json"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout)
        return int(rows[0]["n"])
    except (json.JSONDecodeError, KeyError, IndexError, ValueError, TypeError):
        return None


def _refresh_from_sahjhan(cwd: str, cache: dict) -> dict:
    """Query sahjhan status (text) and update cache fields.

    --no-gates (sahjhan v0.14.0): plain status evaluates transition gates,
    which can run the project's test suite — guaranteed to blow the 5s
    timeout below and silently keep stale bookkeeping (#57). The refresh
    only needs state/sets, never gate readiness.

    fixes_since_pattern is re-derived from the ledger here (only while it
    matters — fix_loop/pattern_analysis), never mirrored by token-matching the
    command text. #77.
    """
    binary = ensure_sahjhan()
    if binary is None:
        return cache
    config_dir, _ = resolve_config_dir(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir, "status", "--no-gates"]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cache

    if result.returncode != 0:
        return cache

    status = parse_status_text(result.stdout)

    cache["state"] = status.get("current_state", "")
    cache["perspective"] = status.get("current_perspective", "?")
    perspective = status.get("sets", {}).get("perspective", {})
    cache["perspectives_done"] = perspective.get("complete", 0)
    cache["perspectives_total"] = perspective.get("total", 0) or cache.get("perspectives_total", 13)
    cache["stall"] = 0
    cache["active"] = cache.get("state", "") not in ("", "idle", "finalized")

    # Derive the pattern-analysis backlog from the ledger, but only in the
    # states where it's consumed — avoids a subprocess on every recon/audit
    # sahjhan command. Query failure keeps the previous value.
    if cache.get("state") in ("fix_loop", "pattern_analysis"):
        fixes = _query_fixes_since_pattern(binary, config_dir, cwd)
        if fixes is not None:
            cache["fixes_since_pattern"] = fixes
    return cache


def _stop_daemon(cwd: str) -> None:
    """Best-effort daemon stop after audit finalization."""
    binary = ensure_sahjhan()
    if binary is None:
        return
    config_dir, _ = resolve_config_dir(cwd)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )


def _apply_sahjhan_cmd(cwd: str, cache: dict | None, cmd: str) -> dict:
    """Record the effects of a sahjhan enforcement command on the cache.

    Runs for pure sahjhan lines and for wrapped re-sync lines like
    ``cd repo && sahjhan status | head``: refresh state from the daemon,
    clear the stall counter, stamp last_sahjhan_cmd, tear the daemon down on
    finalization, and apply fix_commit / pattern-check bookkeeping. #70 item 1.
    """
    if cache is None:
        cache = empty_cache()
    cache = _refresh_from_sahjhan(cwd, cache)
    # Running any sahjhan enforcement subcommand IS the protocol event the
    # stall counter waits for — clear it deterministically, even when the
    # status refresh above could not reach the daemon.
    cache["stall"] = 0
    cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    # Stop daemon after finalization (teardown safety net)
    if cache.get("state") == "finalized":
        _stop_daemon(cwd)
    # #77: fixes_since_pattern is DERIVED from the ledger in _refresh_from_sahjhan
    # (the same query the pattern_check gate uses), not mirrored by token-matching
    # the command text — a read-only diagnostic that only mentions `fix_commit`/
    # `pattern_check` no longer moves it. The pending-commit registration is still
    # cache-tracked, but it clears solely on the mutating `transition fix_commit`
    # verb, so a diagnostic can't silently clear a real pending commit either.
    if _runs_transition(cmd, "fix_commit"):
        cache["unregistered_commits"] = []
    with contextlib.suppress(RuntimeError):
        write_cache(cwd, cache)
    return cache


def main() -> None:
    event = read_event()

    if event.get("tool_name") != "Bash":
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    cmd = event.get("tool_input", {}).get("command", "")
    # CC 2.x Bash payloads carry stdout under .stdout and omit exit_code
    # (PostToolUse fires only on success); the helpers read both shapes so
    # git-commit registration below doesn't silently die on 2.x (#75).
    exit_code = bash_exit_code(event)
    output = bash_output(event)

    cache = read_cache(cwd)

    if is_sahjhan_cmd(cmd):
        _apply_sahjhan_cmd(cwd, cache, cmd)
        exit_ok()

    if cache is None:
        exit_ok()

    # Stale enforcement: don't track stall for abandoned audits
    if not is_enforcement_fresh(cache):
        exit_ok()

    if is_git_commit(cmd) and exit_code == 0:
        commit_hash = _parse_commit_hash(output)
        commits = list(cache.get("unregistered_commits", []))
        commits.append(commit_hash)
        with contextlib.suppress(RuntimeError):
            update_cache(cwd, {"unregistered_commits": commits, "stall": 0})
        exit_ok()

    # A sahjhan enforcement subcommand ran inside a larger shell line
    # (e.g. ``cd repo && sahjhan status | head``). It still re-syncs the
    # protocol, so treat it like a bare sahjhan command rather than penalize
    # the stall counter. Checked after the git-commit branch so a
    # ``git commit && sahjhan status`` line still registers its commit. #70 item 1.
    if contains_sahjhan_cmd(cmd):
        _apply_sahjhan_cmd(cwd, cache, cmd)
        exit_ok()

    # Test/lint/type-check commands are legitimate TDD activity — don't count as stalling
    with contextlib.suppress(RuntimeError):
        if _is_sleep_cmd(cmd):
            # Sleep to game timing gates gets double stall penalty
            update_cache(cwd, {"stall": cache.get("stall", 0) + 2})
        elif not _is_tdd_cmd(cmd):
            update_cache(cwd, {"stall": cache.get("stall", 0) + 1})
    exit_ok()


if __name__ == "__main__":
    main()

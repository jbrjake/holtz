#!/usr/bin/env python3
"""Protocol tracker — updates enforcement cache after Bash commands.

PostToolUse hook for Bash. Detects git commits and sahjhan commands,
updates the enforcement cache file. Never blocks. Pure bookkeeping.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import (  # noqa: E402
    empty_cache,
    is_git_commit,
    is_sahjhan_cmd,
    parse_status_text,
    read_cache,
    write_cache,
)
from _resolve import ensure_sahjhan  # noqa: E402

from _common import _active_ledger, exit_ok, read_event  # noqa: E402


def _is_tdd_cmd(cmd: str) -> bool:
    """Detect test, lint, and type-check commands (TDD workflow)."""
    cmd_stripped = cmd.strip()
    return (
        cmd_stripped.startswith("pytest")
        or cmd_stripped.startswith("python -m pytest")
        or cmd_stripped.startswith("ruff check")
        or cmd_stripped.startswith("ruff format")
        or cmd_stripped.startswith("mypy")
    )


def _is_sleep_cmd(cmd: str) -> bool:
    """Detect sleep commands used to game timing gates.

    Returns True for sleep >5 seconds. Short sleeps (<=5s) are allowed
    for legitimate polling. Checks each segment of chained commands
    (split on &&, ;, ||, |). Handles bash sleep suffixes (s/m/h/d).
    """
    _SUFFIX_MULTIPLIER = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for segment in re.split(r'[;&|]+', cmd):
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


def _refresh_from_sahjhan(cwd: str, cache: dict) -> dict:
    """Query sahjhan status (text) and update cache fields."""
    binary = ensure_sahjhan()
    if binary is None:
        return cache
    config_dir = os.path.join(cwd, "enforcement")
    ledger = _active_ledger(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.append("status")
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
    return cache


def main() -> None:
    event = read_event()

    if event.get("tool_name") != "Bash":
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    cmd = event.get("tool_input", {}).get("command", "")
    exit_code = event.get("tool_response", {}).get("exit_code", -1)
    output = event.get("tool_response", {}).get("output", "")

    cache = read_cache(cwd)

    if is_sahjhan_cmd(cmd):
        if cache is None:
            cache = empty_cache()
        cache = _refresh_from_sahjhan(cwd, cache)
        # BH-017: match subcommand tokens, not substrings of full command
        tokens = cmd.split()
        if "fix_commit" in tokens:
            cache["unregistered_commits"] = []
            cache["fixes_since_pattern"] = cache.get("fixes_since_pattern", 0) + 1
        if "pattern_check" in tokens or "pattern_done" in tokens:
            cache["fixes_since_pattern"] = 0
        write_cache(cwd, cache)
        exit_ok()

    if cache is None:
        exit_ok()

    if is_git_commit(cmd) and exit_code == 0:
        commit_hash = _parse_commit_hash(output)
        cache.setdefault("unregistered_commits", []).append(commit_hash)
        cache["stall"] = 0
        write_cache(cwd, cache)
        exit_ok()

    # Test/lint/type-check commands are legitimate TDD activity — don't count as stalling
    if _is_sleep_cmd(cmd):
        # Sleep to game timing gates gets double stall penalty
        cache["stall"] = cache.get("stall", 0) + 2
    elif not _is_tdd_cmd(cmd):
        cache["stall"] = cache.get("stall", 0) + 1
    write_cache(cwd, cache)
    exit_ok()


if __name__ == "__main__":
    main()

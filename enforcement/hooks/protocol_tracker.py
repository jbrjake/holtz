#!/usr/bin/env python3
"""Protocol tracker — updates enforcement cache after Bash commands.

PostToolUse hook for Bash. Detects git commits and sahjhan commands,
updates the enforcement cache file. Never blocks. Pure bookkeeping.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import (  # noqa: E402
    empty_cache,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache,
    write_cache,
)
from _resolve import sahjhan_binary  # noqa: E402

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


def _parse_commit_hash(output: str) -> str:
    """Extract short commit hash from git commit output."""
    m = re.search(r"\[[\w/.-]+\s+([0-9a-f]{7,})\]", output)
    return m.group(1) if m else "unknown"


def _refresh_from_sahjhan(cwd: str, cache: dict) -> dict:
    """Query sahjhan status --json and update cache fields."""
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        return cache
    config_dir = os.path.join(cwd, "enforcement")
    ledger = _active_ledger(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.extend(["status", "--json"])
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cache

    if result.returncode != 0:
        return cache

    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        return cache

    cache["state"] = status.get("current_state", "")
    sets = status.get("sets", {})
    perspective = sets.get("perspective", {})
    cache["perspectives_done"] = perspective.get("complete", 0)
    cache["perspectives_total"] = perspective.get("total", 0)
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
        if "fix_commit" in cmd:
            cache["unregistered_commits"] = []
            cache["fixes_since_pattern"] = cache.get("fixes_since_pattern", 0) + 1
        if "pattern_check" in cmd or "pattern_done" in cmd:
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
    if not _is_tdd_cmd(cmd):
        cache["stall"] = cache.get("stall", 0) + 1
    write_cache(cwd, cache)
    exit_ok()


if __name__ == "__main__":
    main()

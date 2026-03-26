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

from _common import exit_ok, read_event  # noqa: E402
from _protocol_cache import (  # noqa: E402
    empty_cache,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache,
    write_cache,
)
from _resolve import sahjhan_binary  # noqa: E402


def _parse_commit_hash(output: str) -> str:
    """Extract short commit hash from git commit output."""
    m = re.search(r"\[[\w/.-]+\s+([0-9a-f]{7,})\]", output)
    return m.group(1) if m else "unknown"


def _refresh_from_sahjhan(cwd: str, cache: dict) -> dict:
    """Query sahjhan status and update cache fields."""
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        return cache
    config_dir = os.path.join(cwd, "enforcement")
    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "status"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cache

    if result.returncode != 0:
        return cache

    output = result.stdout
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("State:"):
            m = re.search(r"\((\w+)\)\s*$", line)
            if m:
                cache["state"] = m.group(1)
        if "perspective" in line and "/" in line and "complete" in line:
            m = re.search(r"\((\d+)/(\d+)\s+complete\)", line)
            if m:
                cache["perspectives_done"] = int(m.group(1))
                cache["perspectives_total"] = int(m.group(2))

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

    cache["stall"] = cache.get("stall", 0) + 1
    write_cache(cwd, cache)
    exit_ok()


if __name__ == "__main__":
    main()

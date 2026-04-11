#!/usr/bin/env python3
"""Protocol tracker — updates enforcement cache after Bash commands.

PostToolUse hook for Bash. Detects git commits and sahjhan commands,
updates the enforcement cache file. Never blocks. Pure bookkeeping.
"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from _common import exit_ok, read_event, resolve_config_dir  # noqa: E402
from _protocol_cache import (  # noqa: E402
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
    for segment in re.split(r'[;&|\n]+', cmd):
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
    config_dir, _ = resolve_config_dir(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir, "status"]
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
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        # Stop daemon after finalization (teardown safety net)
        if cache.get("state") == "finalized":
            _stop_daemon(cwd)
        # BH-017: match subcommand tokens, not substrings of full command
        tokens = cmd.split()
        if "fix_commit" in tokens:
            cache["unregistered_commits"] = []
            cache["fixes_since_pattern"] = cache.get("fixes_since_pattern", 0) + 1
        if "pattern_check" in tokens or "pattern_done" in tokens:
            cache["fixes_since_pattern"] = 0
        with contextlib.suppress(RuntimeError):
            write_cache(cwd, cache)
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

#!/usr/bin/env python3
"""Daemon lifecycle supervisor — ensures sahjhan daemon is running during active audits.

PreToolUse hook that:
- Detects active audit (docs/holtz/.sahjhan/ exists)
- Writes active-run marker if missing (scans docs/holtz/runs/ for highest run)
- Checks daemon health via PID probe (os.kill(pid, 0))
- Starts daemon if dead or missing
- Blocks if restart fails during an active, fresh audit (via exit_enforcement_error)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _resolve import ensure_sahjhan  # noqa: E402

from _common import (  # noqa: E402
    _active_ledger,
    exit_enforcement_error,
    exit_ok,
    read_event,
    write_active_run_marker,
)


def _find_highest_run(cwd: str) -> str | None:
    """Scan docs/holtz/runs/ for the highest-numbered run-N directory."""
    runs_dir = os.path.join(cwd, "docs", "holtz", "runs")
    if not os.path.isdir(runs_dir):
        return None
    highest = -1
    for entry in os.listdir(runs_dir):
        m = re.match(r"^run-(\d+)$", entry)
        if m and os.path.isdir(os.path.join(runs_dir, entry)):
            n = int(m.group(1))
            if n > highest:
                highest = n
    return f"run-{highest}" if highest >= 0 else None


def _daemon_pid(cwd: str) -> int | None:
    """Read the daemon PID from daemon.pid, or None if missing/invalid."""
    pid_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "daemon.pid")
    try:
        with open(pid_file, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _is_process_alive(pid: int) -> bool:
    """Check if a process is alive using signal 0."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _start_daemon(cwd: str) -> bool:
    """Attempt to start the sahjhan daemon. Returns True on success."""
    binary = ensure_sahjhan()
    if binary is None:
        return False
    try:
        from _common import resolve_config_dir
        config_dir, _ = resolve_config_dir(cwd)
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "start"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            # Verify daemon is actually alive after claiming success
            pid = _daemon_pid(cwd)
            return pid is not None and _is_process_alive(pid)
        return False
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # No active audit — nothing to do
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Ensure active-run marker exists
    ledger = _active_ledger(cwd)
    if ledger is None:
        ledger = _find_highest_run(cwd)
        if ledger is None:
            exit_ok()  # No runs exist — data dir is stale or pre-init
        try:
            write_active_run_marker(cwd, ledger)
        except OSError:
            exit_ok()

    # Check daemon health
    pid = _daemon_pid(cwd)
    if pid is not None and _is_process_alive(pid):
        exit_ok()  # Daemon is healthy

    # Daemon is down or missing — attempt start
    started = _start_daemon(cwd)
    if not started:
        # Double-check: daemon still dead after restart attempt?
        pid = _daemon_pid(cwd)
        if pid is None or not _is_process_alive(pid):
            exit_enforcement_error(
                cwd, "Daemon restart failed — enforcement cannot evaluate"
            )
    exit_ok()


if __name__ == "__main__":
    main()

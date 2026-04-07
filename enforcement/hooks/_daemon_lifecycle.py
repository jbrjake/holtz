#!/usr/bin/env python3
"""Daemon lifecycle — detects daemon death and terminates audit.

PreToolUse hook that:
- Detects active audit (docs/holtz/.sahjhan/ exists)
- Checks terminated marker (fast path for already-dead audits)
- Verifies the init-PID daemon is still alive
- If dead: writes terminated marker, blocks all tool use
- Never restarts the daemon — a new daemon has a new key

The daemon holds the HMAC session key exclusively in memory.
Daemon death = key loss = ledger unwritable = audit is over.
"""
from __future__ import annotations

import contextlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    _active_ledger,
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_block,
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


def _ensure_active_run_marker(cwd: str) -> None:
    """Write active-run marker if missing."""
    ledger = _active_ledger(cwd)
    if ledger is not None:
        return
    ledger = _find_highest_run(cwd)
    if ledger is None:
        return
    with contextlib.suppress(OSError):
        write_active_run_marker(cwd, ledger)


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Already terminated — block immediately
    terminated = os.path.join(data_dir, "terminated")
    if os.path.isfile(terminated):
        exit_block(
            "AUDIT TERMINATED: daemon died — session key lost. "
            "The audit cannot be completed. /stop to exit."
        )

    # Check init PID
    init_pid = _read_init_pid(cwd)
    if init_pid is None:
        # No init PID tracked — legacy audit or pre-init.
        exit_ok()

    # Init PID exists — is it still alive?
    if _is_process_alive(init_pid):
        _ensure_active_run_marker(cwd)
        exit_ok()

    # Init PID is dead. Audit is over.
    _write_terminated_marker(cwd, init_pid, detected_by="_daemon_lifecycle")
    exit_block(
        f"AUDIT TERMINATED: daemon (PID {init_pid}) died — session key lost, "
        "ledger unwritable. The audit cannot be completed. "
        "/stop to exit."
    )


if __name__ == "__main__":
    main()

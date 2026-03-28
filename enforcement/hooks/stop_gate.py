#!/usr/bin/env python3
"""Sahjhan stop gate — blocks stop unless state is terminal.

Stop hook that queries `sahjhan status --json`. If the current state
is not terminal (i.e., the audit hasn't converged and finalized),
blocks the stop with a convergence message.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _resolve import sahjhan_binary  # noqa: E402

from _common import _active_ledger, exit_stop_allow, exit_stop_block, read_event  # noqa: E402


def main() -> None:
    event = read_event()

    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        exit_stop_allow()

    cwd = event.get("cwd", os.getcwd())
    config_dir = os.path.join(cwd, "enforcement")

    # No active run — allow stop
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_stop_allow()

    ledger = _active_ledger(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.extend(["status", "--json"])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_stop_allow()

    if result.returncode != 0:
        exit_stop_allow()

    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        exit_stop_allow()

    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    if is_terminal:
        exit_stop_allow()

    # Build a helpful message about what's needed
    msg_parts = [
        f"Audit is in state '{current_state}' which is not terminal.",
        "You must complete the audit protocol before stopping.",
    ]

    # Add gate check hints if available
    next_transitions = status.get("available_transitions", [])
    if next_transitions:
        msg_parts.append(f"Available transitions: {', '.join(next_transitions)}")

    exit_stop_block(" ".join(msg_parts))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Sahjhan stop gate — blocks stop unless state is terminal.

Stop hook that queries `sahjhan status` (text output). If the current state
is not terminal (i.e., the audit hasn't converged and finalized),
blocks the stop with a convergence message.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import parse_status_text  # noqa: E402
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
        cmd.append("status")
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

    status = parse_status_text(result.stdout)

    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    # Allow stop in terminal states, awaiting_clear (iteration boundary —
    # the protocol requires /clear before resuming), and idle (no active
    # work — BH-020: operators need a clean exit point between runs).
    if is_terminal or current_state in ("awaiting_clear", "idle"):
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

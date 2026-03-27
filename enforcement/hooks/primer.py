#!/usr/bin/env python3
"""Sahjhan primer — injects resume context on UserPromptSubmit.

When there's an active non-terminal Sahjhan run, this hook:
1. Records a context_reset event (used by awaiting_clear gate)
2. Injects current protocol state as additional context

This replaces convergence_primer.py. The context_reset event is
critical — the awaiting_clear→fix_loop transition gates on it,
ensuring /clear boundaries are actually observed.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import format_state_line  # noqa: E402
from _protocol_cache import read_cache as read_enforcement_cache
from _resolve import sahjhan_binary  # noqa: E402

from _common import _active_ledger, exit_ok, exit_warn, read_event  # noqa: E402


def main() -> None:
    event = read_event()
    binary = sahjhan_binary()

    if not os.path.isfile(binary):
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    config_dir = os.path.join(cwd, "enforcement")

    # No active run — nothing to inject
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Get current status
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
        exit_ok()

    if result.returncode != 0:
        exit_ok()

    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError:
        exit_ok()

    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    if is_terminal or not current_state:
        exit_ok()

    # Record context_reset event (gates awaiting_clear→fix_loop)
    run_number = (ledger or "").replace("run-", "") or "0"
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        reset_cmd = [binary, "--config-dir", config_dir]
        if ledger:
            reset_cmd.extend(["--ledger", ledger])
        reset_cmd.extend([
            "event", "context_reset",
            "--field", "project=holtz",
            "--field", f"run={run_number}",
            "--field", "auditor=holtz",
            "--field", "trigger=user_prompt_submit",
        ])
        subprocess.run(
            reset_cmd,
            capture_output=True,
            timeout=5,
            cwd=cwd,
        )

    # Build resume context
    run_number = status.get("run_number", "?")
    perspective = status.get("current_perspective", "unknown")
    available = status.get("available_transitions", [])

    context = (
        f"SAHJHAN RESUME CONTEXT — Run {run_number}\n"
        f"Current state: {current_state}\n"
        f"Active perspective: {perspective}\n"
    )
    if available:
        context += f"Available transitions: {', '.join(available)}\n"

    # Add lens priming if in audit/fix_loop with active perspective
    if current_state in ("audit", "fix_loop") and perspective != "unknown":
        context += f"\nLens: {perspective}. Quiz on exit. Failures restart."

    context += (
        "\nRun `sahjhan status` for full state. "
        "Run `sahjhan gate check <transition>` to see what gates are blocking."
    )

    # Append enforcement state line if cache exists
    state_line = format_state_line(read_enforcement_cache(cwd))
    if state_line:
        context += "\n" + state_line

    exit_warn(context)


if __name__ == "__main__":
    main()

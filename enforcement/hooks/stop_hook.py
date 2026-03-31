#!/usr/bin/env python3
"""Sahjhan stop hook — blocks stop in active audit states.

Stop hook. Replaces stop_gate.py. Two enforcement layers:
1. State-based blocking: blocks stop in active work states
   (audit, fix_loop, pattern_analysis, final_sweep)
2. Output pattern matching: delegates to `sahjhan hook eval`
   to catch premature completion claims via hooks.toml rules

Falls back to allow if sahjhan binary is unavailable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import parse_status_text  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

from _common import _active_ledger, exit_stop_allow, exit_stop_block, read_event  # noqa: E402

_ACTIVE_WORK_STATES = {"audit", "fix_loop", "pattern_analysis", "final_sweep"}


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    binary = ensure_sahjhan()
    if binary is None:
        exit_stop_allow()

    config_dir = os.path.join(cwd, "enforcement")

    # No active run — allow stop
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_stop_allow()

    ledger = _active_ledger(cwd)

    # Query current state
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.append("status")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_stop_allow()

    if result.returncode != 0:
        exit_stop_allow()

    status = parse_status_text(result.stdout)
    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    # Allow stop in terminal or non-active states
    if is_terminal or current_state not in _ACTIVE_WORK_STATES:
        exit_stop_allow()

    # In active work state — try hook eval for more specific blocking
    output_text = event.get("result", "")
    if output_text:
        try:
            hook_cmd = [binary, "--config-dir", config_dir, "--json"]
            if ledger:
                hook_cmd.extend(["--ledger", ledger])
            hook_cmd.extend(["hook", "eval", "--event", "Stop"])
            hook_cmd.extend(["--output-text", output_text])
            hook_result = subprocess.run(
                hook_cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
            )
            if hook_result.returncode == 0:
                data = json.loads(hook_result.stdout)
                eval_data = data.get("data", data)
                if eval_data.get("decision") == "block":
                    messages = eval_data.get("messages", [])
                    reason = next(
                        (m["message"] for m in messages if m.get("action") == "block"),
                        None,
                    )
                    if reason:
                        exit_stop_block(reason)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
            pass

    # State-based blocking (fallback if hook eval didn't produce a more specific message)
    msg_parts = [
        f"Audit is in state '{current_state}' which is not terminal.",
        "You must complete the audit protocol before stopping.",
    ]
    next_transitions = status.get("available_transitions", [])
    if next_transitions:
        msg_parts.append(f"Available transitions: {', '.join(next_transitions)}")

    exit_stop_block(" ".join(msg_parts))


if __name__ == "__main__":
    main()

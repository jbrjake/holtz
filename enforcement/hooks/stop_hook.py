#!/usr/bin/env python3
"""Sahjhan stop hook — blocks stop in active audit states.

Stop hook. Replaces stop_gate.py. Two enforcement layers:
1. State-based blocking: blocks stop in active work states
   (audit, fix_loop, pattern_analysis, final_sweep)
2. Output pattern matching: delegates to `sahjhan hook eval`
   to catch premature completion claims via hooks.toml rules

Falls back to WARN (not silent allow) if sahjhan config is
unavailable during an active audit. See: holtz issue #19.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import parse_status_text  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

from _common import (  # noqa: E402
    _active_ledger,
    exit_stop_allow,
    exit_stop_block,
    exit_stop_warn,
    read_event,
    resolve_config_dir,
)

_ACTIVE_WORK_STATES = {"audit", "fix_loop", "pattern_analysis", "final_sweep"}


def _has_active_audit(cwd: str) -> bool:
    """Check if there's an active Sahjhan audit (data dir exists)."""
    return os.path.isdir(os.path.join(cwd, "docs", "holtz", ".sahjhan"))


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # No active run — allow stop
    if not _has_active_audit(cwd):
        exit_stop_allow()

    binary = ensure_sahjhan()
    if binary is None:
        exit_stop_warn(
            "WARNING: Sahjhan binary unavailable — enforcement is NOT active. "
            "The audit protocol is not being enforced. "
            "Run the audit skill setup to restore enforcement."
        )

    config_dir, config_found = resolve_config_dir(cwd)
    if not config_found:
        exit_stop_warn(
            f"WARNING: Sahjhan enforcement config not found at {config_dir}/protocol.toml. "
            "The audit protocol is NOT being enforced. "
            "Ensure CLAUDE_PLUGIN_ROOT is set correctly or run "
            "`sahjhan --config-dir <path> status` to verify."
        )

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
        exit_stop_warn(
            "WARNING: Sahjhan status command failed (timeout/error). "
            "Enforcement state unknown. Run `sahjhan status` manually to check."
        )

    if result.returncode != 0:
        exit_stop_warn(
            f"WARNING: Sahjhan status returned error (exit {result.returncode}). "
            f"Enforcement state unknown. stderr: {result.stderr.strip()[:200]}"
        )

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

#!/usr/bin/env python3
"""Sahjhan primer — injects resume context on UserPromptSubmit.

When there's an active non-terminal Sahjhan run, this hook:
1. Checks for terminated audit (daemon died)
2. Records a context_reset event (used by awaiting_clear gate)
3. Injects current protocol state as additional context

If the daemon is dead and the init PID confirms death, writes a
terminated marker and injects a termination message. No restart
attempts — a new daemon has a new key, the old ledger is sealed.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_ok,
    exit_warn,
    read_event,
    record_authed_event,
    resolve_config_dir,
)
from _protocol_cache import format_state_line, parse_status_text  # noqa: E402
from _protocol_cache import read_cache as read_enforcement_cache
from _resolve import ensure_sahjhan  # noqa: E402


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # No active run — nothing to inject. Check this BEFORE ensure_sahjhan()
    # so projects without an audit don't trigger the ~100MB binary download.
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Terminated audit — inject termination message, skip everything else.
    # Also precedes the binary bootstrap so a terminated audit doesn't pay
    # the download cost to announce its own death.
    terminated = os.path.join(data_dir, "terminated")
    if os.path.isfile(terminated):
        exit_warn(
            "AUDIT TERMINATED: daemon died — session key lost. "
            "The ledger is unwritable. This audit cannot be completed. "
            "Check /tmp/sahjhan-daemon.log for crash output. "
            "A new daemon has a new key and cannot resume this ledger. "
            "Disable the plugin with /plugin to restore tool access; "
            "to start a new audit, remove docs/holtz/.sahjhan/ first.",
            "UserPromptSubmit",
        )

    binary = ensure_sahjhan()
    if binary is None:
        exit_ok()

    config_dir, _ = resolve_config_dir(cwd)

    # Get current status
    try:
        cmd = [binary, "--config-dir", config_dir, "status"]
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

    status = parse_status_text(result.stdout)

    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    if is_terminal or not current_state:
        exit_ok()

    # Record context_reset event (gates awaiting_clear -> fix_loop)
    run_number = status.get("run_number", "0")
    if run_number == "0":
        # Fallback: read sahjhan's active-ledger marker directly
        active_file = os.path.join(data_dir, "active-ledger")
        try:
            with open(active_file, encoding="utf-8") as f:
                run_number = f.read().strip().replace("run-", "") or "0"
        except OSError:
            pass
    context_reset_failed = False
    audit_terminated = False
    try:
        record_authed_event(
            "context_reset",
            {
                "project": "holtz",
                "run": run_number,
                "auditor": "holtz",
                "trigger": "user_prompt_submit",
            },
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        # Don't restart. Check if daemon init PID is dead.
        init_pid = _read_init_pid(cwd)
        if init_pid is not None and not _is_process_alive(init_pid):
            _write_terminated_marker(cwd, init_pid, detected_by="primer")
            audit_terminated = True
        context_reset_failed = True

    if audit_terminated:
        exit_warn(
            "AUDIT TERMINATED: daemon died during awaiting_clear — session key lost. "
            "The ledger is unwritable. This audit cannot be completed. "
            "Check /tmp/sahjhan-daemon.log for crash output. "
            "A new daemon has a new key and cannot resume this ledger. "
            "Disable the plugin with /plugin to restore tool access; "
            "to start a new audit, remove docs/holtz/.sahjhan/ first.",
            "UserPromptSubmit",
        )

    # Build resume context
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

    # #69: paused for a human — keep conversing, session is preserved.
    if current_state == "awaiting_human":
        context += (
            "\nPAUSED (awaiting_human): you yielded the turn to answer the user. "
            "Keep replying while they converse — the daemon and session key are "
            "preserved. When they're ready to continue the audit, run "
            f"`{binary} --config-dir {config_dir} transition resume`."
        )

    context += (
        f"\nRun `{binary} --config-dir {config_dir} status` for full state. "
        f"Run `{binary} --config-dir {config_dir} gate check <transition>` "
        f"to see what gates are blocking."
    )

    # Append enforcement state line if cache exists
    state_line = format_state_line(read_enforcement_cache(cwd))
    if state_line:
        context += "\n" + state_line

    if context_reset_failed:
        context += (
            "\n\n⛔ ENFORCEMENT FAILURE — STOP IMMEDIATELY\n\n"
            "Daemon authentication failed. The context_reset event cannot be recorded, "
            "which means protocol gates are permanently blocked for this session.\n\n"
            "This is an unrecoverable state. Do NOT attempt to:\n"
            "- Reset the ledger (sahjhan reset)\n"
            "- Modify .sahjhan/ contents directly\n"
            "- Work around the blocked gate\n\n"
            "Report this failure to the user and wait for instructions."
        )

    context += f"\nSahjhan binary: {binary}"
    if run_number != "0":
        context += f"\nActive ledger: run-{run_number}"

    exit_warn(context, "UserPromptSubmit")


if __name__ == "__main__":
    main()

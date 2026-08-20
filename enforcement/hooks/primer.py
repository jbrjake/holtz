#!/usr/bin/env python3
"""Sahjhan primer — injects resume context on UserPromptSubmit.

When there's an active non-terminal Sahjhan run, this hook:
1. Checks for terminated audit (daemon died)
2. Checks that enforcement can still reach and authenticate to the daemon
3. Injects current protocol state as additional context

If the daemon is dead and the init PID confirms death, writes a
terminated marker and injects a termination message. No restart
attempts — a new daemon has a new key, the old ledger is sealed.

This hook deliberately does NOT record `context_reset`. It used to, on every
UserPromptSubmit — but UserPromptSubmit fires on ordinary typed messages and on
automated background-task notifications, neither of which resets anything, so
the awaiting_clear -> fix_loop gate opened with the full pre-reset context
intact (#79). That event now comes from session_start.py, where the host tells
us a reset actually happened.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    BOUNDARY_MESSAGE,
    DaemonError,
    _daemon_request,
    _get_daemon_socket_path,
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_ok,
    exit_warn,
    read_event,
    resolve_config_dir,
)
from _protocol_cache import BOUNDARY_REFUSED, format_state_line, parse_status_text  # noqa: E402
from _protocol_cache import read_cache as read_enforcement_cache
from _resolve import ensure_sahjhan  # noqa: E402


def _enforcement_status(cwd: str) -> tuple[bool, str]:
    """Probe the daemon over its socket without touching the ledger.

    Returns ``(healthy, boundary_refusal)``. The removed `context_reset` write
    used to prove health as a side effect: it failed loudly when the daemon was
    unreachable or when this hook's hash no longer matched trusted-callers.toml
    (which otherwise fails open and silently disables every gate).
    `enforcement_read` is the cheapest op behind the same peer-identity check,
    and it is a read — so keeping the signal costs no protocol state.

    A `not_found` refusal is healthy: the daemon authenticated this caller
    before dispatching the op, and an audit that hasn't written its cache yet
    simply has nothing stored. Only an authorization refusal is a failure.

    A `sandbox_required` refusal is neither — it is the daemon reporting that
    the boundary is down, which has a name and a one-word fix, and saying
    "enforcement is broken, report it and wait" for it would send the user
    hunting a bug that isn't there.
    """
    try:
        _daemon_request(_get_daemon_socket_path(cwd), {"op": "enforcement_read"})
    except DaemonError as exc:
        if exc.error == BOUNDARY_REFUSED:
            return False, exc.reason or BOUNDARY_REFUSED
        return exc.error != "auth_failed", ""
    except (OSError, ConnectionError, RuntimeError, ValueError):
        return False, ""
    return True, ""


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

    run_number = status.get("run_number", "0")
    if run_number == "0":
        # Fallback: read sahjhan's active-ledger marker directly
        active_file = os.path.join(data_dir, "active-ledger")
        try:
            with open(active_file, encoding="utf-8") as f:
                run_number = f.read().strip().replace("run-", "") or "0"
        except OSError:
            pass

    # Enforcement health. Death is checked directly rather than inferred from a
    # failed write, so a daemon that dies between turns is caught on the next
    # prompt whether or not anything happened to need the socket.
    enforcement_failed = False
    boundary_refusal = ""
    audit_terminated = False
    init_pid = _read_init_pid(cwd)
    if init_pid is not None and not _is_process_alive(init_pid):
        _write_terminated_marker(cwd, init_pid, detected_by="primer")
        audit_terminated = True
    else:
        healthy, boundary_refusal = _enforcement_status(cwd)
        enforcement_failed = not healthy and not boundary_refusal

    if audit_terminated:
        exit_warn(
            f"AUDIT TERMINATED: daemon died during {current_state} — session key lost. "
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

    if boundary_refusal:
        context += "\n\n" + BOUNDARY_MESSAGE.format(reason=boundary_refusal)

    if enforcement_failed:
        context += (
            "\n\n⛔ ENFORCEMENT FAILURE — STOP IMMEDIATELY\n\n"
            "The sahjhan daemon is unreachable or rejected this hook. Restricted "
            "events cannot be recorded, which means protocol gates are permanently "
            "blocked for this session.\n\n"
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

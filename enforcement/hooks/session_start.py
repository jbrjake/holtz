#!/usr/bin/env python3
"""Sahjhan session-start hook — records context_reset on a REAL context reset.

`context_reset` gates `awaiting_clear -> fix_loop` (the `resume` transition):
the punchlist is built in one context, the fixes happen in another. That gate
is only worth anything if the event behind it means what it says.

It used to be recorded by primer.py on every `UserPromptSubmit`, which fires on
ordinary typed messages and on automated background-task notifications alike —
so the gate opened on whatever prompt happened to arrive next, with the full
pre-reset context intact (#79).

`SessionStart` is the event that actually corresponds to a wiped context. It is
host-driven — no tool call can produce one, so an agent cannot manufacture the
evidence — and its `source` field says *how* the session started, which is what
separates a real reset from a restore:

    startup  new session ............................ context is empty
    clear    /clear ................................. context is wiped
    compact  auto or manual compaction .............. context replaced by a summary
    resume   --resume / --continue / /resume ........ prior transcript RESTORED
    fork     --fork-session / /fork / /branch ....... prior transcript CARRIED OVER

Only the first three are recorded. `startup` counts: a user who quits and
relaunches at `awaiting_clear` has a genuinely empty context, and refusing it
would trade #79 for an unsatisfiable gate (#73's failure mode).

Silent on success — the primer's resume banner reports position on the next
turn, so saying it twice is wasted context. Speaks only when the event could
not be recorded, because a `context_reset` that never landed means the run
cannot leave `awaiting_clear`.

Spec: https://code.claude.com/docs/en/hooks (verified 2026-07-25)
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
from _protocol_cache import parse_status_text  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

# SessionStart `source` values that mean the prior context is gone.
# `resume` and `fork` are excluded: both carry the transcript forward.
RESET_SOURCES = frozenset({"clear", "compact", "startup"})

_TERMINATED_MSG = (
    "AUDIT TERMINATED: daemon died — session key lost. "
    "The ledger is unwritable. This audit cannot be completed. "
    "Check /tmp/sahjhan-daemon.log for crash output. "
    "A new daemon has a new key and cannot resume this ledger. "
    "Disable the plugin with /plugin to restore tool access; "
    "to start a new audit, remove docs/holtz/.sahjhan/ first."
)

_AUTH_FAILURE_MSG = (
    "⛔ ENFORCEMENT FAILURE — STOP IMMEDIATELY\n\n"
    "Daemon authentication failed. The context_reset event for this session "
    "could not be recorded, so the awaiting_clear -> fix_loop gate cannot be "
    "satisfied for this run.\n\n"
    "This is an unrecoverable state. Do NOT attempt to:\n"
    "- Reset the ledger (sahjhan reset)\n"
    "- Modify .sahjhan/ contents directly\n"
    "- Work around the blocked gate\n\n"
    "Report this failure to the user and wait for instructions."
)


def _run_number(status: dict, data_dir: str) -> str:
    """Resolve the active run number for the event payload.

    Prefers `sahjhan status`; falls back to sahjhan's active-ledger marker,
    same as the primer did.
    """
    run_number = status.get("run_number", "0")
    if run_number != "0":
        return str(run_number)
    try:
        with open(os.path.join(data_dir, "active-ledger"), encoding="utf-8") as f:
            return f.read().strip().replace("run-", "") or "0"
    except OSError:
        return "0"


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # Not a context reset — a restored or forked session keeps its transcript.
    # Checked before anything else so `resume`/`fork` cost nothing.
    if event.get("source", "") not in RESET_SOURCES:
        exit_ok()

    # No active run — nothing to record. Checked BEFORE ensure_sahjhan() so
    # projects without an audit don't trigger the ~100MB binary download at
    # session start.
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Terminated audit — the primer announces it on the next prompt. Saying it
    # here too would just double the banner.
    if os.path.isfile(os.path.join(data_dir, "terminated")):
        exit_ok()

    binary = ensure_sahjhan()
    if binary is None:
        exit_ok()

    config_dir, _ = resolve_config_dir(cwd)

    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "status"],
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
    if status.get("terminal", False) or not status.get("current_state", ""):
        exit_ok()

    try:
        record_authed_event(
            "context_reset",
            {
                "project": "holtz",
                "run": _run_number(status, data_dir),
                "auditor": "holtz",
                "trigger": "session_start",
                "source": event["source"],
            },
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        # Don't restart the daemon — a new one has a new key and the old
        # ledger is sealed. Distinguish death from a live-but-rejecting daemon.
        init_pid = _read_init_pid(cwd)
        if init_pid is not None and not _is_process_alive(init_pid):
            _write_terminated_marker(cwd, init_pid, detected_by="session_start")
            exit_warn(_TERMINATED_MSG, "SessionStart")
        exit_warn(_AUTH_FAILURE_MSG, "SessionStart")

    exit_ok()


if __name__ == "__main__":
    main()

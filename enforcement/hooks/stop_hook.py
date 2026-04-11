#!/usr/bin/env python3
"""Sahjhan stop hook — blocks stop in non-terminal audit states.

Stop hook. Three enforcement layers:
1. Terminated marker: fast-path allow when daemon death already detected.
2. Daemon liveness: PID check, writes marker if dead, allows stop.
3. Cache-based state check: reads enforcement state from daemon
   (no subprocess, no timeout — fixes issue #24). Freshness gate
   only blocks when enforcement is fresh (recent sahjhan activity).

Falls back to WARN if sahjhan config is unavailable during an
active audit. See: holtz issue #19.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

from _common import (  # noqa: E402
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_stop_allow,
    exit_stop_block,
    exit_stop_warn,
    read_event,
    resolve_config_dir,
)

# Two sets because "allowed to stop" ≠ "safe to kill daemon".
# awaiting_clear allows stop (the turn is done) but the daemon must
# survive — it holds the HMAC session key for the resuming session.
# When adding states, decide: does the audit resume after this? If yes,
# put it in _STOP_ALLOWED only. If the audit is over, put it in both.
_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
_DAEMON_CLEANUP_STATES = {"idle", "finalized", ""}


def _try_stop_daemon(cwd: str) -> None:
    """Best-effort daemon stop for session cleanup."""
    binary = ensure_sahjhan()
    if binary is None:
        return
    config_dir, _ = resolve_config_dir(cwd)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )


def _has_active_audit(cwd: str) -> bool:
    """Check if there's an active Sahjhan audit (data dir exists)."""
    return os.path.isdir(os.path.join(cwd, "docs", "holtz", ".sahjhan"))


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # No active run — allow stop
    if not _has_active_audit(cwd):
        exit_stop_allow()

    # Terminated audit — always allow stop
    terminated = os.path.join(cwd, "docs", "holtz", ".sahjhan", "terminated")
    if os.path.isfile(terminated):
        _try_stop_daemon(cwd)
        exit_stop_allow()

    # Daemon liveness check: if the daemon is dead, the audit is
    # unrecoverable (session key lost). Allow stop and write marker
    # so future checks fast-path. Fixes issue #45 (stop loop escape).
    init_pid = _read_init_pid(cwd)
    if init_pid is not None and not _is_process_alive(init_pid):
        _write_terminated_marker(cwd, init_pid, detected_by="stop_hook")
        exit_stop_allow()
    if init_pid is None:
        # No daemon PID file → daemon was never started or already cleaned.
        # No session key to protect → allow stop.
        exit_stop_allow()

    # Read enforcement cache directly (no subprocess, no timeout)
    cache = read_cache(cwd)

    if cache is None:
        # .sahjhan dir exists but no enforcement cache — audit state unknown.
        # Block to prevent silent enforcement bypass (issue #29 R5).
        exit_stop_block(
            "Sahjhan data directory exists but enforcement cache is missing. "
            "Run `sahjhan status` to check audit state before stopping."
        )

    current_state = cache.get("state", "")

    # Terminal or idle — allow stop
    if current_state in _STOP_ALLOWED_STATES:
        if current_state in _DAEMON_CLEANUP_STATES:
            _try_stop_daemon(cwd)
        exit_stop_allow()

    # Non-terminal state: check freshness
    if not is_enforcement_fresh(cache):
        if current_state in _DAEMON_CLEANUP_STATES:
            _try_stop_daemon(cwd)
        exit_stop_warn(
            f"Stale Holtz audit detected (state: '{current_state}'). "
            "No recent sahjhan activity — this appears to be an abandoned audit. "
            "Consider cleaning up docs/holtz/.sahjhan/ if the audit is no longer needed."
        )

    # Active audit, non-terminal state — block
    exit_stop_block(
        f"Audit is in state '{current_state}' which is not terminal. "
        "You must complete the audit protocol before stopping. "
        "If this audit cannot be completed, the user can manually run: "
        "! sahjhan daemon stop\n"
        "(The next stop attempt will detect the dead daemon and allow exit.)"
    )


if __name__ == "__main__":
    main()

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
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

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
from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

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


def _read_status_cache_state(cwd: str) -> str | None:
    """Read state from sahjhan's status-cache.json (file-based fallback).

    Sahjhan writes this file after every init and transition (since v0.8.0).
    Used as a fallback when the daemon is alive but the enforcement cache
    is unreachable (e.g., macOS auth failure — sahjhan #26).
    """
    cache_path = os.path.join(cwd, "docs", "holtz", ".sahjhan", "status-cache.json")
    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("state", "")
    except (OSError, ValueError, KeyError):
        return None


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
        # Daemon is alive but enforcement cache is unreachable (e.g., auth
        # failure — sahjhan #26). Fall back to status-cache.json file.
        file_state = _read_status_cache_state(cwd)
        if file_state is not None:
            if file_state in _STOP_ALLOWED_STATES:
                if file_state in _DAEMON_CLEANUP_STATES:
                    _try_stop_daemon(cwd)
                exit_stop_allow()
            # Non-terminal state confirmed by file — block with guidance
            exit_stop_block(
                f"Audit is in state '{file_state}' (from status-cache.json fallback). "
                "You must complete the audit protocol before stopping. "
                "If this audit cannot be completed, the user can manually run: "
                "! sahjhan daemon stop\n"
                "(The next stop attempt will detect the dead daemon and allow exit.)"
            )
        # Both caches unavailable — warn instead of block to avoid
        # infinite loop (issue #48 bug 1). The user can decide.
        exit_stop_warn(
            "Sahjhan data directory exists but enforcement state is unavailable "
            "(daemon cache and status-cache.json both unreadable). "
            "Run `sahjhan status` to check audit state."
        )

    current_state = cache.get("state", "")

    # Terminal or idle — allow stop
    if current_state in _STOP_ALLOWED_STATES:
        if current_state in _DAEMON_CLEANUP_STATES:
            _try_stop_daemon(cwd)
        exit_stop_allow()

    # Non-terminal state: check freshness
    # Note: _DAEMON_CLEANUP_STATES is a subset of _STOP_ALLOWED_STATES,
    # so if we reach here (state not in _STOP_ALLOWED_STATES), the state
    # is never in _DAEMON_CLEANUP_STATES. No daemon cleanup needed —
    # this is a stale non-terminal audit, and the daemon may still hold
    # a session key for a potential resume.
    if not is_enforcement_fresh(cache):
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

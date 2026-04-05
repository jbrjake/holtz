#!/usr/bin/env python3
"""Sahjhan stop hook — blocks stop in non-terminal audit states.

Stop hook. Two enforcement layers:
1. Cache-based state check: reads enforcement-cache.json directly
   (no subprocess, no timeout — fixes issue #24)
2. Freshness gate: only blocks when enforcement is fresh (sahjhan
   was used recently). Stale enforcement = abandoned audit, allow
   stop with a warning.

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
    exit_stop_allow,
    exit_stop_block,
    exit_stop_warn,
    read_event,
    resolve_config_dir,
)

_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}


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
        _try_stop_daemon(cwd)
        exit_stop_allow()

    # Non-terminal state: check freshness
    if not is_enforcement_fresh(cache):
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
        "! sahjhan daemon stop"
    )


if __name__ == "__main__":
    main()

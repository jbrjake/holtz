#!/usr/bin/env python3
"""Sahjhan bash guard — manifest verification after Bash commands.

PostToolUse hook for Bash. Calls `sahjhan manifest verify` to check
that managed files haven't been modified outside Sahjhan. If
verification fails, records a protocol_violation event.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _resolve import sahjhan_binary  # noqa: E402

from _common import _active_ledger, exit_ok, exit_warn, read_event  # noqa: E402


def main() -> None:
    event = read_event()

    # Only check after Bash commands complete
    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        exit_ok()

    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        # Sahjhan not vendored yet — skip verification
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    config_dir = os.path.join(cwd, "enforcement")

    # Check if there's an active Sahjhan run (data dir exists)
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    ledger = _active_ledger(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.extend(["manifest", "verify"])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_ok()

    if result.returncode != 0:
        # Record protocol violation
        detail = result.stderr.strip() or result.stdout.strip() or "Manifest verification failed"
        # Extract run number from ledger name (e.g. "run-31" -> "31")
        run_number = (ledger or "").replace("run-", "") or "0"
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            violation_cmd = [binary, "--config-dir", config_dir]
            if ledger:
                violation_cmd.extend(["--ledger", ledger])
            violation_cmd.extend([
                "event", "protocol_violation",
                "--field", f"project=holtz",
                "--field", f"run={run_number}",
                "--field", "auditor=holtz",
                "--field", f"file_path=unknown",
                "--field", f"detail={detail}",
            ])
            subprocess.run(
                violation_cmd,
                capture_output=True,
                timeout=5,
                cwd=cwd,
            )

        exit_warn(
            f"PROTOCOL VIOLATION: Managed file integrity check failed. "
            f"Detail: {detail}. This violation is permanent and will "
            f"block convergence for this run."
        )

    exit_ok()


if __name__ == "__main__":
    main()

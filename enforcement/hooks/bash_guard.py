#!/usr/bin/env python3
"""Sahjhan bash guard — manifest verification after Bash commands.

PostToolUse hook for Bash. Calls `sahjhan manifest verify` to check
that managed files haven't been modified outside Sahjhan. If
verification fails, records a protocol_violation event.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import exit_ok, exit_warn, read_event  # noqa: E402
from _resolve import sahjhan_binary  # noqa: E402


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

    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "manifest", "verify"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        exit_ok()

    if result.returncode != 0:
        # Record protocol violation
        detail = result.stderr.strip() or result.stdout.strip() or "Manifest verification failed"
        try:
            subprocess.run(
                [
                    binary, "--config-dir", config_dir, "event", "protocol_violation",
                    "--file_path", "unknown",
                    "--detail", detail,
                ],
                capture_output=True,
                timeout=5,
                cwd=cwd,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        exit_warn(
            f"PROTOCOL VIOLATION: Managed file integrity check failed. "
            f"Detail: {detail}. This violation is permanent and will "
            f"block convergence for this run."
        )

    exit_ok()


if __name__ == "__main__":
    main()

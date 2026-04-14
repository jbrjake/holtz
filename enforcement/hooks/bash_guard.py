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

from _common import (  # noqa: E402
    exit_enforcement_error,
    exit_ok,
    exit_warn,
    read_event,
    resolve_config_dir,
)
from _protocol_cache import is_enforcement_fresh, is_sahjhan_cmd, read_cache  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402


def main() -> None:
    event = read_event()

    # Only check after Bash commands complete
    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        exit_ok()

    # BH-019: Sahjhan commands are authorized to modify managed files
    # (they render STATUS.md, PUNCHLIST.md, etc. from ledger state).
    # Skip manifest verification for pure sahjhan invocations.
    cmd = event.get("tool_input", {}).get("command", "")
    if is_sahjhan_cmd(cmd):
        exit_ok()

    cwd = event.get("cwd", os.getcwd())

    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")
    config_dir, _ = resolve_config_dir(cwd)

    # Check if there's an active Sahjhan run (data dir exists)
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Stale enforcement: skip manifest verification for abandoned audits
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok()

    try:
        verify_cmd = [binary, "--config-dir", config_dir, "manifest", "verify"]
        result = subprocess.run(
            verify_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_enforcement_error(cwd, "Manifest verify failed", "PostToolUse")

    if result.returncode != 0:
        # Record protocol violation
        detail = result.stderr.strip() or result.stdout.strip() or "Manifest verification failed"
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            violation_cmd = [
                binary, "--config-dir", config_dir,
                "event", "protocol_violation",
                "--field", "project=holtz",
                "--field", "run=0",
                "--field", "auditor=holtz",
                "--field", "file_path=unknown",
                "--field", f"detail={detail}",
            ]
            subprocess.run(
                violation_cmd,
                capture_output=True,
                timeout=5,
                cwd=cwd,
            )

        exit_warn(
            f"PROTOCOL VIOLATION: Managed file integrity check failed. "
            f"Detail: {detail}. This violation is permanent and will "
            f"block convergence for this run.",
            "PostToolUse",
        )

    exit_ok()


if __name__ == "__main__":
    main()

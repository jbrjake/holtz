#!/usr/bin/env python3
"""Sahjhan bash guard — manifest verification after Bash commands.

PostToolUse hook for Bash. Calls `sahjhan manifest verify` to check
that managed files haven't been modified outside Sahjhan. If
verification fails, records a protocol_violation event.
"""
from __future__ import annotations

import contextlib
import json
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

    # Check if there's an active Sahjhan run (data dir exists) BEFORE
    # triggering ensure_sahjhan(). Without this ordering, projects without
    # an audit pay the ~100MB binary download on the first Bash command.
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Stale enforcement: skip manifest verification for abandoned audits.
    # read_cache() talks to the daemon socket inside data_dir, so this
    # check is correct to run before the binary bootstrap too.
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok()

    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")
    config_dir, _ = resolve_config_dir(cwd)

    try:
        verify_cmd = [binary, "--json", "--config-dir", config_dir, "manifest", "verify"]
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
        # One violation event per mismatched file, with the real path and
        # hashes (#57: events used to say file_path=unknown, detail=error,
        # leaving no way to tell WHICH managed file was modified).
        mismatches = _parse_mismatches(result.stdout)
        if not mismatches:
            detail = (
                result.stderr.strip() or result.stdout.strip() or "Manifest verification failed"
            )
            mismatches = [("unknown", detail)]

        for file_path, detail in mismatches:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                violation_cmd = [
                    binary, "--config-dir", config_dir,
                    "event", "protocol_violation",
                    "--field", "project=holtz",
                    "--field", "run=0",
                    "--field", "auditor=holtz",
                    "--field", f"file_path={file_path}",
                    "--field", f"detail={detail}",
                ]
                subprocess.run(
                    violation_cmd,
                    capture_output=True,
                    timeout=5,
                    cwd=cwd,
                )

        files = ", ".join(path for path, _ in mismatches)
        exit_warn(
            f"PROTOCOL VIOLATION: Managed file integrity check failed for: "
            f"{files}. This violation is permanent and will "
            f"block convergence for this run.",
            "PostToolUse",
        )

    exit_ok()


def _parse_mismatches(stdout: str) -> list[tuple[str, str]]:
    """Extract (file_path, detail) pairs from `manifest verify --json` output.

    The JSON envelope carries data.mismatches even on the integrity-error
    exit code. Returns [] when the output isn't parseable (old binary,
    config error) so the caller can fall back to a single opaque event.
    """
    try:
        envelope = json.loads(stdout)
        entries = envelope["data"]["mismatches"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []

    mismatches: list[tuple[str, str]] = []
    for entry in entries:
        path = entry.get("path")
        if not path:
            continue
        expected = entry.get("expected", "?")[:16]
        actual = entry.get("actual")
        detail = (
            f"manifest hash mismatch: expected {expected}, "
            f"actual {(actual or 'missing')[:16]}"
        )
        mismatches.append((path, detail))
    return mismatches


if __name__ == "__main__":
    main()

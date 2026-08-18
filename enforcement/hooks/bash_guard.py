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

        # A violation is a standing condition, not an occurrence: verify runs
        # after every Bash call and reports the same mismatch until someone
        # fixes it. Recording it each time inflates the hash chain without
        # adding information and drowns the ledger's signal — #85 watched 51
        # violation events become 57 across six Bash calls, all identical in
        # substance. Ask the ledger what is already on record and add only what
        # is new. Derived at check time, never mirrored in a cache file (#77).
        already = _recorded_violations(binary, config_dir, cwd)
        for file_path, detail in mismatches:
            if (file_path, detail) in already:
                continue
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


_VIOLATION_SQL = (
    "SELECT file_path, detail FROM events WHERE type='protocol_violation'"
)


def _recorded_violations(binary: str, config_dir: str, cwd: str) -> set[tuple[str, str]]:
    """The (file_path, detail) pairs already on the ledger.

    Runs sahjhan's generic `query` primitive, which is daemon-free and resolves
    the same active ledger the gates evaluate. Returns an empty set on any
    failure, so a query that cannot run degrades to the old
    record-every-time behaviour rather than to silence — losing a real
    violation is worse than logging a duplicate.

    Only ever called on the failure path, so a clean verify pays nothing.
    """
    try:
        proc = subprocess.run(
            [binary, "--config-dir", config_dir, "query", _VIOLATION_SQL, "--format", "json"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0:
        return set()
    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return set()
    if not isinstance(rows, list):
        return set()
    return {
        (row.get("file_path") or "", row.get("detail") or "")
        for row in rows
        if isinstance(row, dict)
    }


def _parse_mismatches(stdout: str) -> list[tuple[str, str]]:
    """Extract (file_path, detail) pairs from `manifest verify --json` output.

    The JSON envelope carries data.mismatches even on the integrity-error
    exit code. Returns [] when the output isn't parseable (old binary,
    config error) so the caller can fall back to a single opaque event.

    `data.unmanaged` is deliberately NOT read: sahjhan >= 0.20.1 splits out
    entries whose key is not under any managed path, which cannot describe a
    file this manifest is responsible for and so are not integrity failures
    (#85). They stay visible in the CLI's own output.
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
        mismatches.append((path, _detail_for(entry)))
    return mismatches


def _detail_for(entry: dict) -> str:
    """One line saying what actually happened to a managed file.

    sahjhan >= 0.20.1 reports a `kind`, so a file that was edited and a file
    that was deleted stop sharing a sentence. The pre-0.20.1 wording is kept
    as the fallback for an older binary, which reports no kind at all (#85).
    """
    expected = (entry.get("expected") or "?")[:16]
    actual = entry.get("actual")
    kind = entry.get("kind")

    if kind == "modified":
        return f"managed file modified: expected {expected}, got {(actual or '?')[:16]}"
    if kind == "missing":
        return f"managed file deleted: expected {expected}, file not found"
    return (
        f"manifest hash mismatch: expected {expected}, "
        f"actual {(actual or 'missing')[:16]}"
    )


if __name__ == "__main__":
    main()

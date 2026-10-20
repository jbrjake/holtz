#!/usr/bin/env python3
"""Read the active ledger the way the gates read it, without the daemon.

``sahjhan query`` loads config, resolves the ledger through the same chain a
transition's gates resolve it through — explicit ``--ledger``, then the
``active-ledger`` marker looked up in ``ledgers.toml``, then the registry
default, then ``data_dir/ledger.jsonl`` — and runs SQL over the file. No
socket, so it is safe to call from inside a gate that a transition is
evaluating, and safe to call from the agent's sandboxed shell.

Every ``enforcement/scripts`` reader goes through here rather than parsing
``ledger.jsonl``. Reimplementing the resolution chain would be a mirror, and a
mirror that drifts points a check at a different ledger than the transition it
is meant to agree with.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def _hooks_dir() -> str:
    """``enforcement/hooks``, a sibling of this script's directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"
    )


def sahjhan_target(cwd: str) -> tuple[str | None, str | None, str]:
    """Locate the sahjhan binary and the enforcement config for ``cwd``.

    Returns ``(binary, config_dir, "")`` or ``(None, None, problem)``.
    """
    sys.path.insert(0, _hooks_dir())
    from _common import resolve_config_dir  # noqa: PLC0415
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    config_dir, found = resolve_config_dir(cwd)
    if binary is None or not found:
        return None, None, (
            f"sahjhan binary={'missing' if binary is None else binary}, "
            f"config_dir={'not found' if not found else config_dir}"
        )
    return binary, config_dir, ""


def query_ledger(
    binary: str, config_dir: str, cwd: str, sql: str
) -> tuple[list[dict] | None, str]:
    """Run SQL over the active ledger, returning ``(rows, problem)``."""
    try:
        proc = subprocess.run(
            [binary, "--config-dir", config_dir, "query", sql, "--format", "json"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"cannot query the ledger: {exc}"

    if proc.returncode != 0:
        # A ledger that has never been initialised surfaces here as an I/O
        # error rather than a zero count. Either way there is no evidence.
        return None, (
            f"ledger query failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"cannot read the ledger query result: {exc}"
    if not isinstance(rows, list):
        return None, f"ledger query returned {type(rows).__name__}, not a list"
    return rows, ""

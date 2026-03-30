#!/usr/bin/env python3
"""Sahjhan write guard — blocks direct writes to managed paths.

PreToolUse hook for Write/Edit. Blocks modifications to docs/holtz/
which are managed by Sahjhan and rendered from ledger state.
"""
from __future__ import annotations

import os
import sys

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(__file__))

from _sahjhan_bootstrap import MANAGED_DOCS as MANAGED_FILES  # noqa: E402  # BH-018: single source of truth

from _common import exit_block, exit_ok, read_event  # noqa: E402


def main() -> None:
    event = read_event()
    path = event.get("tool_input", {}).get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    if not path:
        exit_ok("PreToolUse")

    resolved = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(cwd, path))

    for managed in MANAGED_FILES:
        full = os.path.realpath(os.path.join(cwd, managed))
        if resolved == full:
            exit_block(
                f"BLOCKED: {path} is managed by Sahjhan. "
                "Use `sahjhan finding`, `sahjhan resolve`, or other CLI commands "
                "to modify managed files. Direct writes are not allowed."
            )

    exit_ok("PreToolUse")


if __name__ == "__main__":
    main()

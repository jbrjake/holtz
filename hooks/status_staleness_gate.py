#!/usr/bin/env python3
"""STATUS.md Staleness Gate — PreToolUse hook for Write|Edit.

Blocks writing findings/recon files to docs/holtz/ unless
STATUS.md was updated within the last 5 minutes. STATUS.md
is the program counter — if it's stale, the auditor has drifted
from the process.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import exit_block, exit_ok, read_event

# Maximum age in seconds before STATUS.md is considered stale.
# 300s (5 minutes) allows Investigation Path multi-minute analysis
# without false positives while catching "I'll update later" drift.
STALENESS_WINDOW = 300


def main() -> None:
    event = read_event()
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        exit_ok()

    normalized = file_path.replace("\\", "/")

    # Only gate writes inside docs/holtz/
    if "docs/holtz/" not in normalized:
        exit_ok()

    # If the write IS to a protocol STATUS.md, allow it — this is the update itself
    if normalized.endswith("docs/holtz/STATUS.md") or normalized.endswith("docs/holtz/justine/STATUS.md"):
        exit_ok()

    # Determine which STATUS.md to check
    cwd = event.get("cwd", os.getcwd())
    status_rel = (
        "docs/holtz/justine/STATUS.md"
        if "docs/holtz/justine/" in normalized
        else "docs/holtz/STATUS.md"
    )

    status_path = os.path.join(cwd, status_rel)

    # If STATUS.md doesn't exist yet, allow — first write of the run.
    # Known limitation: if STATUS.md is deleted mid-run, this also allows,
    # bypassing staleness enforcement. Distinguishing "not created yet" from
    # "deleted mid-run" would require checking for other docs/holtz/ artifacts.
    if not os.path.isfile(status_path):
        exit_ok()

    # Check modification time
    mtime = os.path.getmtime(status_path)
    age = time.time() - mtime

    if age > STALENESS_WINDOW:
        minutes = int(age // 60)
        exit_block(
            f"BLOCKED: {status_rel} has not been updated in {minutes} minutes. "
            f"STATUS.md is your program counter — update it before writing more findings."
        )

    exit_ok()


if __name__ == "__main__":
    main()

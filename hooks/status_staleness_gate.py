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
    # To distinguish "not created yet" from "deleted mid-run", check for
    # sibling artifacts that would only exist if the run has already started.
    if not os.path.isfile(status_path):
        holtz_dir = os.path.join(cwd, os.path.dirname(status_rel))
        recon_dir = os.path.join(holtz_dir, "recon")
        punchlist = os.path.join(holtz_dir, "PUNCHLIST.md")
        if os.path.isdir(recon_dir) or os.path.isfile(punchlist):
            exit_block(
                f"BLOCKED: {status_rel} is missing but other run artifacts exist "
                f"(recon/ or PUNCHLIST.md). STATUS.md may have been deleted mid-run. "
                f"Re-create STATUS.md before continuing."
            )
        exit_ok()

    # Check modification time. Wrap in try/except for TOCTOU race:
    # STATUS.md could be deleted between isfile() above and getmtime() here.
    try:
        mtime = os.path.getmtime(status_path)
    except OSError:
        exit_ok()  # File vanished — treat as "doesn't exist yet"
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

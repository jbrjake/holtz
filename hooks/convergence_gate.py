#!/usr/bin/env python3
"""Convergence Gate — Stop hook.

Blocks Holtz from stopping before convergence is reached. When blocked,
Holtz must update STATUS.md and tell the user to /clear for fresh context.
The convergence loop survives context boundaries via STATUS.md.

This is the enforcement hook that the README promised and the codebase
lacked for 14 runs. Advisory instructions said "keep coming back until
convergence." Holtz agreed. Holtz stopped anyway. The hooks section of
the README documents this pattern. Now convergence has one too.
"""
from __future__ import annotations

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import exit_stop_allow, exit_stop_block, read_event

# If STATUS.md hasn't been touched in 30 minutes, the run is likely
# from a previous session that crashed or was abandoned. Allow stop
# and let the primer handle resume on the next session.
STALENESS_THRESHOLD = 1800


def _count_open_items(cwd: str) -> int:
    """Approximate count of open punchlist items.

    NOTE: Counts Status fields via simple regex, not scoped to item
    blocks. Acceptable here because the count is informational (for
    the block reason message), not decisional. The gate decision is
    based on STATUS.md and SUMMARY.md existence.
    """
    for name in ("PUNCHLIST-MERGED.md", "PUNCHLIST.md"):
        path = os.path.join(cwd, "docs", "holtz", name)
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    content = f.read()
            except OSError:
                continue
            open_count = len(re.findall(r'\*\*Status:\*\*[ \t]*OPEN', content))
            in_progress = len(re.findall(r'\*\*Status:\*\*[ \t]*IN PROGRESS', content))
            return open_count + in_progress
    return 0


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # Second stop attempt — Holtz already received the block message
    # and should have told the user to /clear. Let him stop.
    if event.get("stop_hook_active"):
        exit_stop_allow()

    # SUMMARY.md = run completed and converged. Allow.
    summary_path = os.path.join(cwd, "docs", "holtz", "SUMMARY.md")
    if os.path.isfile(summary_path):
        exit_stop_allow()

    # No STATUS.md = no active Holtz run. Don't interfere.
    status_path = os.path.join(cwd, "docs", "holtz", "STATUS.md")
    if not os.path.isfile(status_path):
        exit_stop_allow()

    # Read STATUS.md for status field and phase info.
    try:
        with open(status_path) as f:
            content = f.read()
    except OSError:
        exit_stop_allow()
        return  # unreachable, but makes mypy happy

    # If STATUS.md is stale, this is likely from a previous session.
    # Allow stop; the primer will inform on the next session.
    try:
        mtime = os.path.getmtime(status_path)
    except OSError:
        exit_stop_allow()
        return
    if time.time() - mtime > STALENESS_THRESHOLD:
        exit_stop_allow()

    # Check if status indicates completion.
    status_match = re.search(r'\*\*Status:\*\*[ \t]*(.*)', content)
    if status_match:
        status = status_match.group(1).strip().upper()
        if status in ("COMPLETE", "CONVERGED"):
            exit_stop_allow()

    # Active run, not converged — block.
    phase_match = re.search(r'\*\*Phase:\*\*[ \t]*(.*)', content)
    phase = phase_match.group(1).strip() if phase_match else "unknown"
    open_items = _count_open_items(cwd)

    exit_stop_block(
        f"CONVERGENCE GATE: Holtz audit has not converged. "
        f"Phase: {phase}. Open items: ~{open_items}. "
        f"You MUST: "
        f"(1) Update docs/holtz/STATUS.md with your exact position and next action. "
        f"(2) Tell the user: 'Not converged. Type /clear then any message to continue "
        f"the audit.' "
        f"Do NOT continue working in this context — each convergence iteration gets "
        f"fresh context. STATUS.md carries your state across the boundary."
    )


if __name__ == "__main__":
    main()

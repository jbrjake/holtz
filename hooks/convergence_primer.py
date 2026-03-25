#!/usr/bin/env python3
"""Convergence Primer — UserPromptSubmit hook.

Detects active Holtz audits and injects resume context into the
conversation. After /clear, the user types anything and this hook
primes the model to resume from STATUS.md instead of starting fresh.

This is what makes the convergence loop "automagic" — the user
doesn't need to remember the right incantation. STATUS.md carries
the state, and this hook tells the model where to find it.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import exit_ok, exit_warn, mask_fenced_blocks, read_event


def _read_status_fields(cwd: str) -> dict[str, str]:
    """Extract key fields from STATUS.md for the primer message."""
    status_path = os.path.join(cwd, "docs", "holtz", "STATUS.md")
    fields: dict[str, str] = {}
    try:
        with open(status_path) as f:
            content = f.read()
    except OSError:
        return fields

    # Mask code fences before field extraction (PAT-001 convention).
    masked = mask_fenced_blocks(content)

    for field in ("Phase", "Step", "Status"):
        m = re.search(rf'\*\*{field}:\*\*[ \t]*(.*)', masked)
        if m:
            fields[field.lower()] = m.group(1).strip()

    # Next Action is under a ## heading, not a **field** format
    m = re.search(r'## Next Action\n(.+)', masked)
    if m:
        fields["next_action"] = m.group(1).strip()

    return fields


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    status_path = os.path.join(cwd, "docs", "holtz", "STATUS.md")
    summary_path = os.path.join(cwd, "docs", "holtz", "SUMMARY.md")

    # No active run — don't interfere
    if not os.path.isfile(status_path) or os.path.isfile(summary_path):
        exit_ok()

    fields = _read_status_fields(cwd)
    phase = fields.get("phase", "unknown")
    status = fields.get("status", "unknown")
    next_action = fields.get("next_action", "read STATUS.md for details")

    # If status indicates completion, don't inject
    if status.upper() in ("COMPLETE", "CONVERGED"):
        exit_ok()

    exit_warn(
        f"HOLTZ CONVERGENCE LOOP — ACTIVE: "
        f"Unfinished audit at Phase {phase} (status: {status}). "
        f"Next action: {next_action}. "
        f"Unless the user is explicitly asking about something else, resume the audit "
        f"by reading docs/holtz/STATUS.md and continuing from where you left off. "
        f"Do not start a new audit. This is a convergence iteration boundary."
    )


if __name__ == "__main__":
    main()

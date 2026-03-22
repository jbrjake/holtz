#!/usr/bin/env python3
"""Subagent Findings Check — SubagentStop hook.

When a subagent completes, scans its last message for references
to docs/holtz/ files and warns if any don't exist on disk.
Uses exit 1 (warn) not exit 2 (block) — the subagent is already
done, blocking can't undo its work.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import read_event, exit_ok, exit_warn


def main() -> None:
    event = read_event()

    # Extract the subagent's last message — defensive fallback
    message = event.get("last_assistant_message", "")
    if not message:
        exit_ok()

    # Scan for docs/holtz/ file references
    paths = re.findall(r'docs/holtz/[^\s"\')\]]+\.md', message)
    if not paths:
        exit_ok()

    # Deduplicate
    paths = list(dict.fromkeys(paths))

    cwd = event.get("cwd", os.getcwd())
    missing = []
    for rel_path in paths:
        full_path = os.path.join(cwd, rel_path)
        if not os.path.isfile(full_path):
            missing.append(rel_path)

    if missing:
        files = ", ".join(missing)
        exit_warn(
            f"WARNING: Subagent referenced file(s) that do not exist on disk: {files}. "
            f"Verify the subagent wrote its findings. "
            f"If it's not on disk, it doesn't exist."
        )

    exit_ok()


if __name__ == "__main__":
    main()

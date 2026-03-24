#!/usr/bin/env python3
"""Impact Graph Gate — PreToolUse hook for Write|Edit.

Blocks writing Phase 1+ audit files unless the corresponding
impact-graph.json exists on disk. Enforces the HARD-GATE that
was violated for 10+ consecutive runs despite advisory instructions.
"""
from __future__ import annotations

import os
import sys

# Allow importing _common from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import exit_block, exit_ok, read_event


def main() -> None:
    event = read_event()
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        exit_ok("PreToolUse")

    # Normalize path separators
    normalized = file_path.replace("\\", "/")

    # Only gate writes to audit directories and punchlist files.
    # ORDER MATTERS: justine check must come before holtz check because
    # "docs/holtz/audit/" is a substring of "docs/holtz/justine/audit/".
    # NOTE: Uses `in` for substring matching. Claude Code provides absolute
    # or cwd-relative paths, so these specific path components are safe from
    # false positives on embedded paths. BH-007 run 14: verified by design.
    justine_paths = ("docs/holtz/justine/audit/", )
    justine_files = ("docs/holtz/justine/PUNCHLIST.md", )
    holtz_files = ("docs/holtz/PUNCHLIST.md", "docs/holtz/PUNCHLIST-MERGED.md")
    if any(p in normalized for p in justine_paths) or normalized.endswith(justine_files):
        required = "docs/holtz/justine/impact-graph.json"
    elif "docs/holtz/audit/" in normalized or normalized.endswith(holtz_files):
        required = "docs/holtz/impact-graph.json"
    else:
        exit_ok("PreToolUse")

    # Resolve relative to cwd if path is relative
    cwd = event.get("cwd", os.getcwd())
    graph_path = os.path.join(cwd, required) if not os.path.isabs(required) else required

    if not os.path.isfile(graph_path):
        exit_block(
            f"BLOCKED: Cannot write audit findings without a live impact graph. "
            f"Run impact_graph.py to create {required} first. "
            f"\"Later\" means \"never.\" Run the command NOW."
        )

    exit_ok("PreToolUse")


if __name__ == "__main__":
    main()

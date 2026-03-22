#!/usr/bin/env python3
"""Artifact Verification — PostToolUse hook for Bash.

After running impact_graph.py, verifies the target graph file
actually exists on disk. Catches the case where the script ran
but produced no output file — "regardless of what you believe you did."
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import read_event, exit_ok, exit_block


def main() -> None:
    event = read_event()
    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only check commands that ran impact_graph.py
    if "impact_graph.py" not in command:
        exit_ok()

    # Extract --graph path (handles quoted and unquoted paths)
    match = re.search(r'--graph\s+["\']?([^"\'\s]+)["\']?', command)
    if match:
        graph_rel = match.group(1)
    else:
        graph_rel = "docs/holtz/impact-graph.json"

    # Resolve relative to cwd
    cwd = event.get("cwd", os.getcwd())
    graph_path = os.path.join(cwd, graph_rel) if not os.path.isabs(graph_rel) else graph_rel

    if not os.path.isfile(graph_path):
        # Check if the script itself failed
        tool_response = event.get("tool_response", {})
        extra = ""
        if isinstance(tool_response, dict):
            stdout = tool_response.get("stdout", "")
            stderr = tool_response.get("stderr", "")
            if stderr:
                extra = f" Script stderr: {stderr[:200]}"

        exit_block(
            f"BLOCKED: impact_graph.py ran but {graph_rel} does not exist on disk. "
            f"The graph was not created.{extra}"
        )

    exit_ok()


if __name__ == "__main__":
    main()

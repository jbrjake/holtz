#!/usr/bin/env python3
"""Subagent Findings Check — SubagentStop hook.

When a subagent completes, scans its last message for references
to docs/holtz/ files and warns if any don't exist on disk.
Warns but does not block — the subagent is already done, blocking
can't undo its work.

Note: Path extraction operates on raw message text without code-fence
masking. Paths mentioned in code examples may trigger false-positive
warnings. This is acceptable because the hook only warns (exit_stop_warn)
and false positives are preferable to missed findings.

Output format: SubagentStop uses the Stop protocol:
- Allow: no output (exit 0)
- Warn: {"decision": "approve", "reason": msg}
- Block: {"decision": "block", "reason": msg}
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import exit_stop_allow, exit_stop_warn, read_event


def main() -> None:
    event = read_event()

    # Extract the subagent's last message — defensive fallback
    message = event.get("last_assistant_message", "")
    if not message:
        exit_stop_allow()

    # Scan for docs/holtz/ file references (.md, .json, .jsonl, .toml, .txt)
    paths = re.findall(r'docs/holtz/[^\s"\')\]]+\.(?:md|json|jsonl|toml|txt)', message)
    if not paths:
        exit_stop_allow()

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
        exit_stop_warn(
            f"WARNING: Subagent referenced file(s) that do not exist on disk: {files}. "
            f"Verify the subagent wrote its findings. "
            f"If it's not on disk, it doesn't exist."
        )

    exit_stop_allow()


if __name__ == "__main__":
    main()

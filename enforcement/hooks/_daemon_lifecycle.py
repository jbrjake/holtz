#!/usr/bin/env python3
"""Daemon lifecycle — detects daemon death and terminates audit.

PreToolUse hook that:
- Detects active audit (docs/holtz/.sahjhan/ exists)
- Allows read-only tools through unconditionally (Read, Glob, Grep,
  ToolSearch, Agent, etc.) — they don't need the daemon
- Allows recovery Bash commands (sahjhan daemon start/stop) through
- Checks terminated marker (fast path for already-dead audits)
- Verifies the init-PID daemon is still alive
- If dead: writes terminated marker, blocks write-path tools
- Never restarts the daemon — a new daemon has a new key

The daemon holds the HMAC session key exclusively in memory.
Daemon death = key loss = ledger unwritable = audit is over.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_block,
    exit_ok,
    read_event,
)

# Tools that don't need the daemon — read-only or infrastructure.
# These must never be blocked, even when the audit is terminated.
_PASSTHROUGH_TOOLS = frozenset({
    "Read", "Glob", "Grep", "ToolSearch", "Agent", "LSP",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput",
    "WebFetch", "WebSearch", "SendMessage",
})

# Pattern matching sahjhan daemon start/stop commands, with optional
# nohup prefix, --config-dir flag, and shell redirections.
_DAEMON_RECOVERY_RE = re.compile(
    r"(?:nohup\s+)?(?:env\s+\S+=\S+\s+)*"
    r"sahjhan\s+(?:--config-dir\s+\S+\s+)?daemon\s+(?:start|stop)\b"
)


def _is_recovery_command(event: dict) -> bool:
    """Check if a Bash event is a sahjhan daemon start/stop command."""
    if event.get("tool_name") != "Bash":
        return False
    cmd = event.get("tool_input", {}).get("command", "")
    return bool(_DAEMON_RECOVERY_RE.search(cmd))


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())
    tool_name = event.get("tool_name", "")

    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok("PreToolUse")

    # Read-only tools pass through unconditionally — they don't need
    # the daemon and blocking them bricks the session (issue #55).
    if tool_name in _PASSTHROUGH_TOOLS:
        exit_ok("PreToolUse")

    # Already terminated — check for recovery commands, then block.
    terminated = os.path.join(data_dir, "terminated")
    if os.path.isfile(terminated):
        if _is_recovery_command(event):
            exit_ok("PreToolUse")
        exit_block(
            "AUDIT TERMINATED: daemon died — session key lost. "
            "The audit cannot be completed. Disable the plugin "
            "with /plugin or restart the daemon manually with "
            "! sahjhan daemon start"
        )

    # Check init PID
    init_pid = _read_init_pid(cwd)
    if init_pid is None:
        # No init PID tracked — legacy audit or pre-init.
        exit_ok("PreToolUse")

    # Init PID exists — is it still alive?
    if _is_process_alive(init_pid):
        exit_ok("PreToolUse")

    # Init PID is dead. Audit is over.
    _write_terminated_marker(cwd, init_pid, detected_by="_daemon_lifecycle")
    if _is_recovery_command(event):
        exit_ok("PreToolUse")
    exit_block(
        f"AUDIT TERMINATED: daemon (PID {init_pid}) died — session key lost, "
        "ledger unwritable. The audit cannot be completed. Disable the "
        "plugin with /plugin or restart the daemon manually with "
        "! sahjhan daemon start"
    )


if __name__ == "__main__":
    main()

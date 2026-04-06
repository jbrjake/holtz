#!/usr/bin/env python3
"""Sahjhan post-tool hook — auto-records tool use and evaluates monitors.

PostToolUse hook. Calls `sahjhan hook eval` which:
- Returns auto_record events to write to the ledger
- Evaluates edit accumulation warning in fix_loop
- Evaluates stall monitors

The wrapper enriches auto_record fields with data from tool_input
(line spans for Read, lines_changed for Edit, etc.) and additionally
records bash_command events for Bash tools.

Falls back to allow if sahjhan binary is unavailable.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

from _common import (  # noqa: E402
    _active_ledger,
    exit_enforcement_error,
    exit_ok,
    exit_warn,
    read_event,
    resolve_config_dir,
)


def _enrich_auto_record(
    record: dict[str, Any], tool_name: str, tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Enrich an auto_record result with data from the tool event.

    Returns a new dict with enriched fields. Does not mutate the input.
    """
    fields = dict(record.get("fields", {}))
    event_type = record.get("event_type", "")
    fields["tool"] = tool_name

    if event_type == "file_read" and tool_name == "Read":
        offset = tool_input.get("offset", "1")
        limit = tool_input.get("limit", "")
        try:
            start = int(offset) if offset else 1
            fields["line_start"] = str(start)
            if limit:
                fields["line_end"] = str(start + int(limit) - 1)
        except (ValueError, TypeError):
            pass

    elif event_type == "source_edit":
        if tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            if old_string:
                fields["lines_changed"] = str(old_string.count("\n") + 1)
            fields["edit_type"] = "partial"
        elif tool_name == "Write":
            fields["edit_type"] = "full_file"
        elif tool_name == "NotebookEdit":
            fields["edit_type"] = "partial"

    elif event_type == "file_search" and tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", "")
        if pattern:
            fields["pattern"] = pattern
        if search_path:
            fields["search_path"] = search_path

    return {"event_type": event_type, "fields": fields}


def _build_bash_event(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Build a bash_command event from Bash tool_input."""
    command = tool_input.get("command", "")
    return {"event_type": "bash_command", "fields": {"command": command}}


def _record_event(
    binary: str,
    config_dir: str,
    ledger: str | None,
    cwd: str,
    event_type: str,
    fields: dict[str, str],
) -> None:
    """Record an event via sahjhan CLI. Best-effort, failures are silent."""
    cmd = [binary, "--config-dir", config_dir]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["event", event_type])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=cwd)


def main() -> None:
    event = read_event()
    tool_name = event.get("tool_name", event.get("tool", ""))
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    # Stale enforcement: skip event recording for abandoned audits
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok()

    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")

    config_dir, config_found = resolve_config_dir(cwd)
    if not config_found:
        exit_enforcement_error(cwd, "Enforcement config not found", "PostToolUse")

    ledger = _active_ledger(cwd)

    # Call hook eval
    cmd = [binary, "--config-dir", config_dir, "--json"]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["hook", "eval", "--event", "PostToolUse"])
    if tool_name:
        cmd.extend(["--tool", tool_name])
    if file_path:
        cmd.extend(["--file", file_path])

    eval_data: dict[str, Any] = {}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            eval_data = data.get("data", data)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        exit_enforcement_error(cwd, "Hook eval failed", "PostToolUse")

    # Process auto_records
    for record in eval_data.get("auto_records", []):
        enriched = _enrich_auto_record(record, tool_name, tool_input)
        _record_event(
            binary, config_dir, ledger, cwd,
            enriched["event_type"], enriched["fields"],
        )

    # Record bash_command for Bash tools (not in hooks.toml auto_record)
    if tool_name == "Bash":
        bash_event = _build_bash_event(tool_input)
        _record_event(
            binary, config_dir, ledger, cwd,
            bash_event["event_type"], bash_event["fields"],
        )

    # Surface warnings
    decision = eval_data.get("decision", "allow")
    if decision == "warn":
        messages = eval_data.get("messages", [])
        monitor_warnings = eval_data.get("monitor_warnings", [])
        warnings = [m["message"] for m in messages if m.get("action") == "warn"]
        warnings.extend(w["message"] for w in monitor_warnings)
        if warnings:
            exit_warn(" | ".join(warnings))

    exit_ok()


if __name__ == "__main__":
    main()

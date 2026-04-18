#!/usr/bin/env python3
"""Sahjhan pre-tool hook — managed-path guard plus hook eval for TDD gate.

PreToolUse hook. Replaces write_guard.py. Performs two checks:
1. Blocks writes to sahjhan-managed files (docs/holtz/STATUS.md etc.)
2. Calls `sahjhan hook eval` which evaluates hooks.toml rules
   (TDD gate in fix_loop, etc.)

Fails closed (blocks) during active audits if the daemon is unreachable.
Falls back to allow outside active audits or when enforcement is stale.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import exit_block, exit_enforcement_error, exit_ok, exit_warn, read_event, resolve_config_dir  # noqa: E402
from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402
from _sahjhan_bootstrap import MANAGED_DOCS  # noqa: E402


def main() -> None:
    event = read_event()
    tool_name = event.get("tool_name", event.get("tool", ""))
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    # ── Managed-path guard (no binary required) ──
    if file_path:
        resolved = (
            os.path.realpath(file_path)
            if os.path.isabs(file_path)
            else os.path.realpath(os.path.join(cwd, file_path))
        )
        for managed in MANAGED_DOCS:
            full = os.path.realpath(os.path.join(cwd, managed))
            if resolved == full:
                exit_block(
                    f"BLOCKED: {file_path} is managed by Sahjhan. "
                    "Use `sahjhan finding`, `sahjhan resolve`, or other CLI commands "
                    "to modify managed files. Direct writes are not allowed."
                )

    # Stale enforcement: skip hook eval for abandoned audits
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok("PreToolUse")

    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable")

    config_dir, config_found = resolve_config_dir(cwd)
    if not config_found:
        exit_enforcement_error(cwd, "Enforcement config not found")

    cmd = [binary, "--config-dir", config_dir, "--json",
           "hook", "eval", "--event", "PreToolUse"]
    if tool_name:
        cmd.extend(["--tool", tool_name])
    if file_path:
        # hooks.toml globs (``tests/**``, ``src/**``) are evaluated against
        # what we pass here. Claude Code always sends absolute tool paths,
        # and those never match a relative glob — so the TDD gate's
        # ``path_not_matches = "tests/**"`` exemption silently fails and
        # every test-file Write in fix_loop gets blocked. Normalize to
        # cwd-relative when the file is inside the project tree.
        eval_file = file_path
        try:
            if os.path.isabs(file_path):
                rel = os.path.relpath(file_path, cwd)
                if not rel.startswith(".."):
                    eval_file = rel
        except ValueError:
            # Different drive on Windows — leave the absolute path.
            pass
        cmd.extend(["--file", eval_file])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_enforcement_error(cwd, "Hook eval subprocess failed")

    # Sahjhan's CLI exits non-zero when the eval decision is ``block``
    # (exit code as a secondary signal for wrappers that don't parse JSON).
    # The JSON payload on stdout is authoritative — parse it first and
    # only fall through to the enforcement-error path if stdout is missing
    # or unparseable.
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else None
    except (json.JSONDecodeError, ValueError):
        data = None

    if data is None:
        exit_enforcement_error(cwd, "Hook eval returned invalid JSON")

    eval_data = data.get("data", data)
    decision = eval_data.get("decision", "allow")
    messages = eval_data.get("messages", [])

    if decision == "block":
        reason = next(
            (m["message"] for m in messages if m.get("action") == "block"),
            "Blocked by sahjhan hook eval",
        )
        exit_block(reason)

    if decision == "warn":
        warnings = [m["message"] for m in messages if m.get("action") == "warn"]
        monitor_warnings = eval_data.get("monitor_warnings", [])
        warnings.extend(w["message"] for w in monitor_warnings)
        if warnings:
            exit_warn(" | ".join(warnings), "PreToolUse")

    exit_ok("PreToolUse")


if __name__ == "__main__":
    main()

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

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    audit_abandoned,
    exit_block,
    exit_boundary_missing,
    exit_enforcement_error,
    exit_ok,
    exit_warn,
    read_event,
    read_hook_eval,
    resolve_config_dir,
)
from _protocol_cache import (  # noqa: E402
    event_actor,
    is_enforcement_fresh,
    read_cache_with_boundary,
)
from _resolve import ensure_sahjhan  # noqa: E402
from _sahjhan_bootstrap import MANAGED_DOCS  # noqa: E402


def _tdd_gate_exempt(file_path: str, cwd: str) -> bool:
    """Whether the fix-loop TDD pre-edit gate should skip this Edit/Write target.

    The gate (hooks.toml) blocks Edit/Write in ``fix_loop`` until a failing test
    is recorded — its purpose is "no *source* change without a preceding failing
    test". Test files are already exempt via the hooks.toml
    ``path_not_matches = "tests/**"`` filter. But the gate also fired on writes
    that are not source and need no failing test: documentation, and files
    outside the project tree (the auditor's own session notes / the scratchpad).
    Blocking those only pushed legitimate writes onto the ``cat >`` heredoc
    bypass (#70 item 2, which feeds #71). Exempt:

      * any path outside the project root (``cwd``), and
      * ``docs/**`` inside the project.

    Managed docs (STATUS/PUNCHLIST/SUMMARY) are still protected — the
    managed-path guard runs before this and is independent of the TDD gate.
    """
    if not file_path:
        return False
    resolved = os.path.realpath(
        file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    )
    repo_root = os.path.realpath(cwd)
    rel = os.path.relpath(resolved, repo_root)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return True  # outside the project tree
    return rel.split(os.sep, 1)[0] == "docs"


def _write_target(tool_input: dict) -> str:
    """The path a write tool is about to touch, whatever it calls the key.

    `NotebookEdit` sends `notebook_path`; `Edit` and `Write` send `file_path`.
    Confirmed against the installed `claude` binary, which destructures
    `notebook_path` by name — not inferred from the tool's description.

    Reading only `file_path` is not a missing feature, it is a silent exemption:
    the managed-path guard has nothing to match, and `hook eval` is invoked with
    no `--file`, which is the argument every path filter in the TDD gate is
    written against. So the gate's `tests/**` exemption and its `src/**` scope
    both stop applying, and each does so by *allowing*.

    `file_path` wins when both are present, so no notebook key can shadow the
    path an Edit actually named.
    """
    return str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")


def main() -> None:
    event = read_event()
    tool_name = event.get("tool_name", event.get("tool", ""))
    tool_input = event.get("tool_input", {})
    file_path = _write_target(tool_input)
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

    # ── TDD gate scope (#70 item 2) ──
    # The fix-loop TDD pre-edit gate is for in-repo *source* files only. Editing
    # docs or files outside the project tree needs no failing test; blocking them
    # only pushes writes onto the bash `cat >` bypass. Exempt them before the
    # gate eval. The TDD gate is the only PreToolUse Edit/Write rule, so this
    # skips nothing else (test files are already exempt via the hooks.toml
    # filter). The managed-path guard above still applies regardless.
    if tool_name in ("Edit", "Write", "NotebookEdit") and _tdd_gate_exempt(file_path, cwd):
        exit_ok("PreToolUse")

    cache, boundary, _version = read_cache_with_boundary(cwd)

    # A refusing daemon returns no cache, so the staleness check below reads
    # it as "no audit" and allows. That inverts the fuse: the moment the
    # boundary goes missing, every gate it protects would stop applying.
    #
    # Which is why the release for an abandoned audit is a separate question
    # and not a reordering. The daemon outlives the session that started it,
    # so its refusal reaches sessions with no audit to protect; those are the
    # ones `audit_abandoned` lets past, and a live audit still blocks (41).
    if boundary and not audit_abandoned(cwd):
        exit_boundary_missing(boundary)

    # Stale enforcement: skip hook eval for abandoned audits
    if not is_enforcement_fresh(cache):
        exit_ok("PreToolUse")

    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable")

    config_dir, config_found = resolve_config_dir(cwd)
    if not config_found:
        exit_enforcement_error(cwd, "Enforcement config not found")

    # Which actor is asking. A hook gate can filter on `{{agent_id}}` since
    # sahjhan 0.23.0, and the TDD gate does: without it the gate is run-global
    # and two concurrent fix agents each pass on the other's failing test.
    # Always passed, never omitted — the orchestrator is the empty-string
    # actor, a real bucket rather than a wildcard, and omitting the flag would
    # bind the same empty value by a less obvious route.
    cmd = [binary, "--config-dir", config_dir, "--json",
           "hook", "eval", "--event", "PreToolUse",
           "--agent-id", event_actor(event)]
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

    eval_data, failure = read_hook_eval(result.stdout, result.returncode, result.stderr)
    if eval_data is None:
        exit_enforcement_error(cwd, failure)

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

"""Deny message quality tests — verify all user-facing deny messages are coherent.

Expands the TestDenyMessageQuality pattern from test_contract_commands.py
to cover all hooks that produce deny messages:

  _sahjhan_bootstrap.py — blocked subcommands, write protection
  _daemon_lifecycle.py  — terminated audit
  commit_gate.py        — unregistered commits, stall
  stop_hook.py          — non-terminal state (Stop block)

Each deny message must:
  1. Name the specific action that was blocked
  2. Not contain parse artifacts (redirect fragments, token indices, raw regex)
  3. Contain actionable guidance (what to do instead)
  4. Be grammatically coherent (LLM agent is the primary consumer)
"""
from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path

import pytest

from hook_runner import run_hook as _run_hook

REPO_ROOT = Path(__file__).parent.parent

BOOTSTRAP_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "_sahjhan_bootstrap.py")
LIFECYCLE_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "_daemon_lifecycle.py")
COMMIT_GATE = str(REPO_ROOT / "enforcement" / "hooks" / "commit_gate.py")
STOP_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "stop_hook.py")

# Shell idioms that must not leak into deny messages (issue #53 regression class)
SHELL_IDIOMS = [
    " 2>&1",
    " >/dev/null 2>&1",
    " 2>/dev/null",
    " > /tmp/out.log",
    " &>/dev/null",
    " 1>&2",
]

# Fragments that should NEVER appear in a deny message
PARSE_ARTIFACT_FRAGMENTS = [
    "'sahjhan 2'",     # redirect digit leaking as subcommand
    "'sahjhan 1'",     # fd number leaking
    "token ",          # raw token index
    "idx ",            # parser index
    "regex ",          # regex internals
    "\\d",             # regex pattern
    "\\s",             # regex pattern
]


def _get_pre_tool_reason(output: dict) -> str | None:
    """Extract permissionDecisionReason from a PreToolUse deny."""
    hso = output.get("hookSpecificOutput", {})
    if hso.get("permissionDecision") == "deny":
        return hso.get("permissionDecisionReason", "")
    return None


def _get_stop_block_reason(output: dict) -> str | None:
    """Extract reason from a Stop block."""
    if output.get("decision") == "block":
        return output.get("reason", "")
    return None


def _assert_no_parse_artifacts(reason: str, context: str) -> None:
    """Assert that a deny message contains no parse artifact fragments."""
    for fragment in PARSE_ARTIFACT_FRAGMENTS:
        assert fragment not in reason, (
            f"Parse artifact '{fragment}' found in deny message "
            f"({context}): {reason}"
        )


def _assert_actionable(reason: str, context: str) -> None:
    """Assert the message provides actionable guidance."""
    # Must contain at least one of: "Allowed", "Run", "must", "cannot", "use"
    actionable_markers = ["allowed", "run ", "must", "cannot", "use ", "stop",
                           "complete", "transition", "exit"]
    has_guidance = any(m in reason.lower() for m in actionable_markers)
    assert has_guidance, (
        f"Deny message lacks actionable guidance ({context}): {reason}"
    )


# ---------------------------------------------------------------------------
# Bootstrap hook deny messages
# ---------------------------------------------------------------------------


class TestBootstrapDenyMessages:
    """Deny messages from _sahjhan_bootstrap.py (subcommand + write guard)."""

    @pytest.mark.parametrize("subcmd", ["reset", "frobnicate", "nuke", ""])
    def test_blocked_subcommand_names_action(self, subcmd):
        """Blocked subcommand messages name the blocked action."""
        cmd = f"sahjhan {subcmd}" if subcmd else "sahjhan"
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, f"Expected block for: {cmd}"
        if subcmd:
            assert subcmd in reason.lower(), \
                f"Deny message should mention '{subcmd}': {reason}"
        assert "BLOCKED" in reason
        _assert_no_parse_artifacts(reason, f"bootstrap/{cmd}")
        _assert_actionable(reason, f"bootstrap/{cmd}")

    @pytest.mark.parametrize("idiom", SHELL_IDIOMS)
    def test_blocked_subcommand_with_shell_idioms(self, idiom):
        """Blocked subcommands with shell idioms must not leak redirect fragments."""
        cmd = f"sahjhan reset --confirm{idiom}"
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, f"Expected block for: {cmd}"
        assert "reset" in reason.lower(), \
            f"Message should mention 'reset', not redirect artifact: {reason}"
        _assert_no_parse_artifacts(reason, f"bootstrap/{cmd}")

    def test_daemon_stop_message(self, tmp_path, mock_daemon):
        """Mid-audit sahjhan daemon stop produces a coherent deny message."""
        mock_daemon.state = {"active": True, "state": "fix_loop"}
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None
        assert "stop" in reason.lower()
        assert "blocked" in reason.lower()
        _assert_no_parse_artifacts(reason, "bootstrap/daemon-stop")

    def test_write_guard_enforcement_path(self):
        """Write to enforcement/ path names the protected path."""
        # Use absolute path that resolves against the real plugin root
        protected = str(REPO_ROOT / "enforcement" / "hooks" / "evil.py")
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": protected, "content": "x"},
            "cwd": str(REPO_ROOT),
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, f"Expected block for Write to {protected}"
        assert "enforcement" in reason.lower() or "protected" in reason.lower()
        _assert_no_parse_artifacts(reason, "bootstrap/write/enforcement")

    def test_write_guard_hooks_json(self):
        """Write to hooks/hooks.json is blocked with clear message."""
        protected = str(REPO_ROOT / "hooks" / "hooks.json")
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": protected, "content": "x"},
            "cwd": str(REPO_ROOT),
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, "Expected block for Write to hooks.json"
        assert "BLOCKED" in reason
        _assert_no_parse_artifacts(reason, "bootstrap/write/hooks.json")

    def test_write_guard_managed_data(self, tmp_path):
        """Write to .sahjhan/ data dir is blocked with clear message."""
        import os
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        target = os.path.join(sahjhan_dir, "cache")
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": target, "content": "x"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, "Expected block for Write to .sahjhan/"
        assert "BLOCKED" in reason
        assert "sahjhan" in reason.lower() or "data" in reason.lower()
        _assert_no_parse_artifacts(reason, "bootstrap/write/.sahjhan")

    @pytest.mark.parametrize("cmd,protected", [
        ("cp foo.txt enforcement/hooks/evil.py", "enforcement/"),
        ("echo bad > hooks/hooks.json", "hooks/hooks.json"),
        ("tee docs/holtz/STATUS.md", "docs/holtz/STATUS.md"),
        ("rm -rf docs/holtz/.sahjhan/", "docs/holtz/.sahjhan/"),
    ])
    def test_bash_write_guard_names_path(self, cmd, protected):
        """Bash write guard messages name the protected path.

        Uses REPO_ROOT so PROTECTED plugin-relative paths (enforcement/,
        hooks/hooks.json) remain in scope — the guard only engages when the
        agent is operating inside the plugin tree. MANAGED paths
        (docs/holtz/…) are cwd-relative and engage from any cwd.
        """
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
            "cwd": str(REPO_ROOT),
        }
        output = _run_hook(BOOTSTRAP_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, f"Expected block for: {cmd}"
        assert "BLOCKED" in reason
        _assert_no_parse_artifacts(reason, f"bootstrap/bash-write/{cmd}")


# ---------------------------------------------------------------------------
# Lifecycle hook deny messages
# ---------------------------------------------------------------------------


class TestLifecycleDenyMessages:
    """Deny messages from _daemon_lifecycle.py (terminated audit)."""

    def test_terminated_marker_message(self, tmp_path):
        """Terminated audit message is clear about daemon death."""
        import os
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        with open(os.path.join(sahjhan_dir, "terminated"), "w") as f:
            f.write("reason: daemon_pid_dead\n")

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None
        assert "TERMINATED" in reason
        assert "daemon" in reason.lower()
        _assert_actionable(reason, "lifecycle/terminated")
        _assert_no_parse_artifacts(reason, "lifecycle/terminated")

    def test_dead_pid_message_includes_pid(self, tmp_path):
        """Dead daemon message includes the PID number."""
        import os
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        dead_pid = 99999
        while True:
            try:
                os.kill(dead_pid, 0)
                dead_pid += 1
            except (ProcessLookupError, OSError):
                break
        with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w") as f:
            f.write(str(dead_pid))

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None
        assert str(dead_pid) in reason, \
            f"Message should include dead PID {dead_pid}: {reason}"
        assert "TERMINATED" in reason
        _assert_actionable(reason, "lifecycle/dead-pid")


# ---------------------------------------------------------------------------
# Commit gate deny messages
# ---------------------------------------------------------------------------


class TestCommitGateDenyMessages:
    """Deny messages from commit_gate.py (protocol obligations)."""

    def test_unregistered_commits_message(self, mock_daemon, tmp_path):
        """Unregistered commits deny mentions the count and required action."""
        from datetime import datetime
        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 0,
            "unregistered_commits": ["abc1234", "def5678"],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "pattern_analysis_overdue": False,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "test"'},
            "cwd": str(tmp_path),
        }
        output = _run_hook(COMMIT_GATE, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, "Expected commit block with unregistered commits"
        assert "2" in reason, f"Message should mention commit count: {reason}"
        assert "fix_commit" in reason, \
            f"Message should mention fix_commit action: {reason}"
        _assert_no_parse_artifacts(reason, "commit-gate/unregistered")
        _assert_actionable(reason, "commit-gate/unregistered")

    def test_stall_message(self, mock_daemon, tmp_path):
        """Stall threshold deny mentions command count and required action."""
        from datetime import datetime
        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 20,
            "unregistered_commits": [],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "pattern_analysis_overdue": False,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(COMMIT_GATE, event)
        reason = _get_pre_tool_reason(output)
        assert reason is not None, "Expected stall block"
        assert "20" in reason or "stall" in reason.lower() or "commands" in reason.lower(), \
            f"Message should mention stall count: {reason}"
        _assert_no_parse_artifacts(reason, "commit-gate/stall")
        _assert_actionable(reason, "commit-gate/stall")


# ---------------------------------------------------------------------------
# Stop hook deny messages
# ---------------------------------------------------------------------------


class TestStopHookDenyMessages:
    """Deny messages from stop_hook.py (non-terminal state)."""

    def test_active_state_block_mentions_state(self, tmp_path, monkeypatch):
        """Stop block during active audit mentions the current state."""
        import os
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w") as f:
            f.write(str(os.getpid()))
        with open(os.path.join(sahjhan_dir, "status-cache.json"), "w") as f:
            json.dump({"state": "fix_loop"}, f)
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        reason = _get_stop_block_reason(output)
        assert reason is not None, "Expected stop block in fix_loop state"
        assert "fix_loop" in reason, \
            f"Message should mention current state: {reason}"
        assert "not terminal" in reason.lower() or "complete" in reason.lower(), \
            f"Message should explain why stop is blocked: {reason}"
        _assert_no_parse_artifacts(reason, "stop-hook/active")
        _assert_actionable(reason, "stop-hook/active")

    def test_file_fallback_block_mentions_fallback(self, tmp_path, monkeypatch):
        """Stop block via file fallback mentions the fallback source."""
        import os
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w") as f:
            f.write(str(os.getpid()))
        with open(os.path.join(sahjhan_dir, "status-cache.json"), "w") as f:
            json.dump({"state": "audit"}, f)
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        reason = _get_stop_block_reason(output)
        assert reason is not None
        assert "audit" in reason
        assert "status-cache.json" in reason, \
            f"Message should mention fallback source: {reason}"
        _assert_no_parse_artifacts(reason, "stop-hook/fallback")

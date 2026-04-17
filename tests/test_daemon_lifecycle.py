"""Tests for _daemon_lifecycle.py — daemon lifecycle PreToolUse hook."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")

sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestDaemonLifecycleNoAudit:
    """Exit early when no active audit exists."""

    def test_allows_when_no_sahjhan_dir(self, tmp_path):
        """No docs/holtz/.sahjhan/ → allow, no action."""
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_when_no_runs_and_no_marker(self, tmp_path):
        """Data dir exists but no runs/ and no active-run marker → allow, no action."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"


class TestDaemonDeathTerminatesAudit:
    """Daemon death with init PID tracking — audit terminated."""

    def test_blocks_when_init_pid_dead(self, tmp_path):
        """Init PID dead → writes terminated marker, blocks."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason
        assert (sahjhan_dir / "terminated").exists()

    def test_allows_when_init_pid_alive(self, tmp_path):
        """Init PID is alive → allow, no termination."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text(f"{os.getpid()}\n")
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
        assert not (sahjhan_dir / "terminated").exists()

    def test_blocks_fast_when_terminated_marker_exists(self, tmp_path):
        """Terminated marker already present → block immediately."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason

    def test_allows_legacy_no_init_pid_file(self, tmp_path):
        """No daemon-init-pid file → legacy audit, allow."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_writes_marker_not_cache(self, tmp_path):
        """Terminated marker written but no enforcement-cache.json (daemon-backed state)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        assert (sahjhan_dir / "terminated").exists()
        assert not (sahjhan_dir / "enforcement-cache.json").exists()


class TestGraduatedBlocking:
    """Read-only tools allowed, write-path tools blocked, recovery commands allowed."""

    def _make_dead_audit(self, tmp_path):
        """Create an audit dir with a dead daemon PID."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")
        return sahjhan_dir

    def _make_terminated_audit(self, tmp_path):
        """Create an audit dir with terminated marker already present."""
        sahjhan_dir = self._make_dead_audit(tmp_path)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")
        return sahjhan_dir

    # -- Read-only tools must be allowed even with dead daemon --

    def test_allows_read_when_daemon_dead(self, tmp_path):
        """Read tool should pass through even when daemon is dead."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_glob_when_daemon_dead(self, tmp_path):
        """Glob tool should pass through even when daemon is dead."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Glob", "tool_input": {"pattern": "*.py"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_grep_when_daemon_dead(self, tmp_path):
        """Grep tool should pass through even when daemon is dead."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Grep", "tool_input": {"pattern": "foo"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_toolsearch_when_daemon_dead(self, tmp_path):
        """ToolSearch should pass through — it's infrastructure, not audit activity."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "ToolSearch", "tool_input": {"query": "select:WebFetch"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    # -- Read-only tools must also be allowed when terminated marker exists --

    def test_allows_read_when_terminated(self, tmp_path):
        """Read tool should pass through even with terminated marker."""
        self._make_terminated_audit(tmp_path)
        event = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_glob_when_terminated(self, tmp_path):
        """Glob tool should pass through even with terminated marker."""
        self._make_terminated_audit(tmp_path)
        event = {"tool_name": "Glob", "tool_input": {"pattern": "*.py"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    # -- Write-path tools must still be blocked --

    def test_still_blocks_bash_when_daemon_dead(self, tmp_path):
        """Bash should still be blocked when daemon is dead."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason

    def test_still_blocks_write_when_daemon_dead(self, tmp_path):
        """Write tool should be blocked when daemon is dead."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x", "content": "y"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason

    def test_still_blocks_edit_when_daemon_dead(self, tmp_path):
        """Edit tool should be blocked when daemon is dead."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason

    # -- Recovery commands must be allowed through --

    def test_allows_sahjhan_daemon_start_when_terminated(self, tmp_path):
        """sahjhan daemon start should be allowed as a recovery path."""
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_sahjhan_daemon_stop_when_terminated(self, tmp_path):
        """sahjhan daemon stop should be allowed for cleanup."""
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_nohup_sahjhan_daemon_start_when_terminated(self, tmp_path):
        """nohup-wrapped daemon start should also be allowed."""
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "nohup sahjhan daemon start > /dev/null 2>&1 &"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    def test_allows_config_dir_daemon_start_when_terminated(self, tmp_path):
        """--config-dir variant of daemon start should be allowed."""
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan --config-dir /some/path/enforcement daemon start"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"

    # -- Recovery regex must NOT match commands that merely contain a
    #    sahjhan daemon invocation chained after arbitrary work.

    def test_blocks_chained_command_with_recovery_suffix(self, tmp_path):
        """`rm -rf /tmp/x && sahjhan daemon start` must remain blocked.

        The recovery exemption is for genuine recovery commands only, not
        for arbitrary work prepended to a recovery suffix. Allowing this
        lets a terminated audit run side-effects under the cover of
        "I'm just restarting the daemon."
        """
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/everything && sahjhan daemon start"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", (
            "Chained command with a recovery suffix bypassed the daemon-lifecycle "
            "block — only bare recovery commands should pass through."
        )

    def test_blocks_chained_command_with_recovery_prefix(self, tmp_path):
        """`sahjhan daemon start && rm -rf /tmp/x` must remain blocked.

        Symmetric to the suffix case — the recovery command alone is fine,
        but chaining destructive work after it converts a recovery into
        arbitrary execution.
        """
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start && rm -rf /tmp/everything"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", (
            "Recovery prefix followed by chained command bypassed the block."
        )

    def test_blocks_subshell_recovery_wrapping(self, tmp_path):
        """`echo pwn; sahjhan daemon start` must remain blocked."""
        self._make_terminated_audit(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo pwn; sahjhan daemon start"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny"

    # -- Recovery commands when daemon JUST died (no marker yet) --

    def test_allows_daemon_start_when_pid_just_died(self, tmp_path):
        """Recovery allowed even on first detection (before marker written)."""
        self._make_dead_audit(tmp_path)  # dead PID, no terminated marker
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
        # Marker should still be written even though we allowed the command
        assert (tmp_path / "docs" / "holtz" / ".sahjhan" / "terminated").exists()

    # -- Error message quality --

    def test_error_message_no_slash_stop(self, tmp_path):
        """/stop doesn't exist as a CC command — error must not reference it."""
        self._make_dead_audit(tmp_path)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "/stop" not in reason

    def test_terminated_marker_error_no_slash_stop(self, tmp_path):
        """/stop reference must also be absent from the fast-path message."""
        self._make_terminated_audit(tmp_path)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "/stop" not in reason

    def test_error_message_does_not_suggest_restart_as_recovery(self, tmp_path):
        """Restarting the daemon does NOT recover the audit — new daemon = new key.

        The module docstring explicitly says "Never restarts the daemon — a new
        daemon has a new key." The termination message must not tell the user
        to "restart the daemon" as if that would fix anything.
        """
        self._make_terminated_audit(tmp_path)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        # "restart the daemon" as a recovery instruction is misleading because
        # a new daemon has a new session key and cannot resume the old ledger.
        assert "restart the daemon" not in reason.lower(), (
            f"Error message suggests restarting the daemon as recovery, but a "
            f"new daemon has a new key — restart does not recover the audit. "
            f"Got: {reason!r}"
        )

    def test_error_messages_consistent_with_primer(self, tmp_path):
        """Both hooks share the same termination scenario — their guidance
        must not contradict. Issue #55 left _daemon_lifecycle.py and primer.py
        with divergent recovery instructions after the /stop fix was applied
        piecemeal. Sample both and check the core guidance aligns.
        """
        self._make_terminated_audit(tmp_path)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        lifecycle_msg = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")

        primer_event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", primer_event, cwd=str(tmp_path))
        primer_msg = output.get("hookSpecificOutput", {}).get("additionalContext", "")

        # Both must point to /plugin as the primary recovery action
        assert "/plugin" in lifecycle_msg, (
            f"_daemon_lifecycle.py message must reference /plugin as recovery. Got: {lifecycle_msg!r}"
        )
        assert "/plugin" in primer_msg, (
            f"primer.py message must reference /plugin as recovery. Got: {primer_msg!r}"
        )
        # Both must reference the daemon log for diagnosis
        assert "sahjhan-daemon.log" in lifecycle_msg, (
            f"_daemon_lifecycle.py must mention daemon log for diagnosis. Got: {lifecycle_msg!r}"
        )
        assert "sahjhan-daemon.log" in primer_msg, (
            f"primer.py must mention daemon log for diagnosis. Got: {primer_msg!r}"
        )


class TestWriteTerminatedMarker:
    """Tests for _write_terminated_marker shared helper."""

    def test_creates_marker_file(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345, detected_by="_daemon_lifecycle")
        marker = sahjhan_dir / "terminated"
        assert marker.exists()
        content = marker.read_text()
        assert "reason: daemon_pid_dead" in content
        assert "init_pid: 12345" in content
        assert "detected_by: _daemon_lifecycle" in content
        assert "detected_at:" in content

    def test_does_not_write_filesystem_cache(self, tmp_path):
        """Marker file only — no enforcement-cache.json written (daemon-backed state)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)
        cache_path = sahjhan_dir / "enforcement-cache.json"
        assert not cache_path.exists(), (
            "enforcement-cache.json should not be written — state lives in daemon memory"
        )


class TestReadInitPid:
    """Tests for _read_init_pid shared helper."""

    def test_reads_existing_pid(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon-init-pid").write_text("72578\n")
        from _common import _read_init_pid
        assert _read_init_pid(str(tmp_path)) == 72578

    def test_returns_none_when_missing(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        from _common import _read_init_pid
        assert _read_init_pid(str(tmp_path)) is None

    def test_returns_none_on_corrupt_file(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon-init-pid").write_text("not-a-number\n")
        from _common import _read_init_pid
        assert _read_init_pid(str(tmp_path)) is None

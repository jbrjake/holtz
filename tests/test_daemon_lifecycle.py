"""Tests for _daemon_lifecycle.py — daemon lifecycle PreToolUse hook."""
from __future__ import annotations

import os
import subprocess
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
        assert output.get("continue") is True

    def test_allows_when_no_runs_and_no_marker(self, tmp_path):
        """Data dir exists but no runs/ and no active-run marker → allow, no action."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True


class TestActiveRunMarker:
    """Tests for active-run marker creation when missing."""

    def test_creates_marker_from_highest_run(self, tmp_path):
        """Missing active-run marker + existing runs → writes marker for highest run."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        runs_dir = tmp_path / "docs" / "holtz" / "runs"
        (runs_dir / "run-1").mkdir(parents=True)
        (runs_dir / "run-3").mkdir(parents=True)
        (runs_dir / "run-2").mkdir(parents=True)
        # Write a daemon.pid so it doesn't try to start daemon
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        marker = sahjhan_dir / "active-run"
        assert marker.exists()
        assert marker.read_text().strip() == "run-3"

    def test_skips_marker_when_already_exists(self, tmp_path):
        """Existing active-run marker → left unchanged."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-5\n")
        # Write a daemon.pid so it doesn't try to start daemon
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        assert (sahjhan_dir / "active-run").read_text().strip() == "run-5"


class TestDaemonHealthCheck:
    """Tests for daemon PID-based health checking."""

    def test_does_not_start_when_pid_alive(self, tmp_path):
        """Daemon PID is alive → no restart attempt."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # Use our own PID — guaranteed alive
        (sahjhan_dir / "daemon.pid").write_text(f"{os.getpid()}\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True
        # Daemon.pid is not touched — hook exits before any restart attempt
        assert (sahjhan_dir / "daemon.pid").read_text().strip() == str(os.getpid())

    def test_starts_daemon_when_pid_dead(self, tmp_path):
        """Daemon PID file exists but process is dead → attempt restart."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # PID 99999999 is almost certainly not running
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        # This will attempt daemon start (which will fail since no real binary),
        # but should still allow the tool call
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_starts_daemon_when_no_pid_file(self, tmp_path):
        """No daemon.pid → daemon not running → attempt start."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # No daemon.pid file

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_never_blocks_on_failure(self, tmp_path):
        """Even if daemon start fails, the tool call is always allowed."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

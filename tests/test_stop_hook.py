"""Tests for stop_hook.py — Stop event hook."""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestStopHookDaemonLiveness:
    """Tests for daemon liveness check in stop_hook.py (issue #45)."""

    def test_dead_daemon_allows_stop(self, tmp_path):
        """Dead daemon PID → allow stop and write terminated marker."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        # Write a PID that is guaranteed to be dead
        (sahjhan_dir / "daemon-init-pid").write_text("99999999")

        # Write enforcement cache with active non-terminal state
        cache = {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        }
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        # Should allow stop (no output = allow for stop hooks)
        assert code == 0
        # Stop allow = empty output or decision != "block"
        assert output.get("decision") != "block", (
            f"Dead daemon should allow stop but got: {output}"
        )

        # Terminated marker should have been written
        assert (sahjhan_dir / "terminated").exists(), (
            "Dead daemon should write terminated marker"
        )

    def test_no_pid_file_allows_stop(self, tmp_path):
        """No daemon PID file → allow stop (daemon never started)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        # No daemon-init-pid file, but cache exists with non-terminal state
        cache = {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        }
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") != "block", (
            f"No PID file should allow stop but got: {output}"
        )

    def test_live_daemon_still_blocks(self, tmp_path):
        """Live daemon PID → still block stop in non-terminal state."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        # Write our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # Write enforcement cache with active non-terminal state
        cache = {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        }
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") == "block", (
            f"Live daemon should block stop but got: {output}"
        )


class TestStopHookRemediationMessage:
    """Tests for remediation message in stop_hook.py block output."""

    def test_block_message_explains_two_step(self, tmp_path):
        """Block message should explain the two-step escape (kill daemon, retry stop)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        # Write our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # Write enforcement cache with active non-terminal state
        cache = {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        }
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert output.get("decision") == "block"
        reason = output.get("reason", "")
        assert "next stop" in reason.lower(), (
            f"Block message should explain two-step escape, got: {reason}"
        )

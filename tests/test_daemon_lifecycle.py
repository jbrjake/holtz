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
        assert output.get("continue") is True

    def test_allows_when_no_runs_and_no_marker(self, tmp_path):
        """Data dir exists but no runs/ and no active-run marker → allow, no action."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True


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
        assert output.get("continue") is False
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
        assert output.get("continue") is True
        assert not (sahjhan_dir / "terminated").exists()

    def test_blocks_fast_when_terminated_marker_exists(self, tmp_path):
        """Terminated marker already present → block immediately."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is False
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
        assert output.get("continue") is True

    def test_writes_terminated_cache_state(self, tmp_path):
        """Terminated marker also updates enforcement-cache.json."""
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        cache_path = sahjhan_dir / "enforcement-cache.json"
        cache = json.loads(cache_path.read_text())
        assert cache["state"] == "terminated"
        assert cache["active"] is False


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

    def test_updates_enforcement_cache(self, tmp_path):
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache_path = sahjhan_dir / "enforcement-cache.json"
        cache_path.write_text(json.dumps({"state": "fix_loop", "active": True}))
        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)
        cache = json.loads(cache_path.read_text())
        assert cache["state"] == "terminated"
        assert cache["active"] is False
        assert cache["terminated_reason"] == "daemon_pid_dead"

    def test_handles_missing_cache(self, tmp_path):
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)
        cache_path = sahjhan_dir / "enforcement-cache.json"
        cache = json.loads(cache_path.read_text())
        assert cache["state"] == "terminated"
        assert cache["active"] is False

    def test_handles_corrupt_cache(self, tmp_path):
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "enforcement-cache.json").write_text("NOT JSON{{{")
        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)
        cache = json.loads((sahjhan_dir / "enforcement-cache.json").read_text())
        assert cache["state"] == "terminated"


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

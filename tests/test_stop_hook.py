"""Tests for stop_hook.py — Stop event hook."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestStopHookDaemonLiveness:
    """Tests for daemon liveness check in stop_hook.py (issue #45)."""

    def test_dead_daemon_allows_stop(self, tmp_path, mock_daemon):
        """Dead daemon PID → allow stop and write terminated marker."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        # Write a PID that is guaranteed to be dead
        (sahjhan_dir / "daemon-init-pid").write_text("99999999")

        # Write enforcement cache via daemon
        from _protocol_cache import write_cache
        write_cache(str(tmp_path), {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        })

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

    def test_no_pid_file_allows_stop(self, tmp_path, mock_daemon):
        """No daemon PID file → allow stop (daemon never started)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        # No daemon-init-pid file, but cache exists with non-terminal state
        from _protocol_cache import write_cache
        write_cache(str(tmp_path), {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        })

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") != "block", (
            f"No PID file should allow stop but got: {output}"
        )

    def test_live_daemon_still_blocks(self, tmp_path, mock_daemon):
        """Live daemon PID → still block stop in non-terminal state."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        # Write our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # Write enforcement cache via daemon
        from _protocol_cache import write_cache
        write_cache(str(tmp_path), {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        })

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") == "block", (
            f"Live daemon should block stop but got: {output}"
        )


class TestStopHookStatusCacheFallback:
    """Tests for status-cache.json fallback when daemon cache is unreachable (issue #48 bug 1)."""

    def test_fallback_to_status_cache_terminal_state(self, tmp_path, mock_daemon):
        """Live daemon + no enforcement cache + status-cache.json with terminal state → allow stop."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        # Write our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # Do NOT write enforcement cache to daemon — simulates auth failure
        # (read_cache() will return None)

        # Write status-cache.json with a terminal state
        import json
        status_cache = {"state": "awaiting_clear", "ts": "2099-01-01T00:00:00Z"}
        (sahjhan_dir / "status-cache.json").write_text(json.dumps(status_cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output == {}, (
            f"Terminal state in status-cache.json should allow stop (empty output), got: {output}"
        )

    def test_fallback_to_status_cache_nonterminal_state(self, tmp_path, mock_daemon):
        """Live daemon + no enforcement cache + status-cache.json with non-terminal state → block."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        import json
        status_cache = {"state": "fix_loop", "ts": "2099-01-01T00:00:00Z"}
        (sahjhan_dir / "status-cache.json").write_text(json.dumps(status_cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") == "block", (
            f"Non-terminal state in status-cache.json should block, got: {output}"
        )

    def test_fallback_no_status_cache_warns(self, tmp_path, mock_daemon):
        """Live daemon + no enforcement cache + no status-cache.json → warn (not block)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # No enforcement cache, no status-cache.json

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        # Should warn, not block — blocking creates infinite loop
        assert "systemMessage" in output, (
            f"Missing both caches should warn (not block) to avoid infinite loop, got: {output}"
        )
        assert "decision" not in output, f"Warn should not have decision field, got: {output}"
        msg = output.get("systemMessage", "").lower()
        assert "unavailable" in msg or "status-cache" in msg, (
            f"Warn message should mention 'unavailable' or 'status-cache', got: {output.get('systemMessage')}"
        )


class TestStopHookRemediationMessage:
    """Tests for remediation message in stop_hook.py block output."""

    def test_block_message_explains_two_step(self, tmp_path, mock_daemon):
        """Block message should explain the two-step escape (kill daemon, retry stop)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        # Write our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # Write enforcement cache via daemon
        from _protocol_cache import write_cache
        write_cache(str(tmp_path), {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        })

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert output.get("decision") == "block"
        reason = output.get("reason", "")
        assert "next stop" in reason.lower(), (
            f"Block message should explain two-step escape, got: {reason}"
        )

    def test_fix_loop_block_message_offers_pause(self, tmp_path, mock_daemon):
        """#69: the fix_loop stop-block should offer `transition pause` so the
        agent can yield to answer a question instead of abandoning the run."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))
        from _protocol_cache import write_cache
        write_cache(str(tmp_path), {
            "state": "fix_loop",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        })
        event = {"cwd": str(tmp_path)}
        _, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        reason = output.get("reason", "")
        assert "pause" in reason.lower() and "resume" in reason.lower(), (
            f"fix_loop block message should offer pause/resume, got: {reason}"
        )


class TestStopHookAwaitingHuman:
    """#69: the reversible awaiting_human pause allows stopping without killing
    the daemon, so the session survives and the run can resume."""

    def test_awaiting_human_allows_stop(self, tmp_path, mock_daemon):
        """Stop is allowed in awaiting_human — the agent may yield the turn."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))
        from _protocol_cache import write_cache
        write_cache(str(tmp_path), {
            "state": "awaiting_human",
            "active": True,
            "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00",
        })
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("decision") != "block", (
            f"awaiting_human should allow stop, got: {output}"
        )

    def test_awaiting_human_not_a_daemon_cleanup_state(self):
        """The daemon (session key) must survive a pause so resume works —
        awaiting_human is stop-allowed but NOT a cleanup state."""
        from _common import DAEMON_CLEANUP_STATES, STOP_ALLOWED_STATES
        assert "awaiting_human" in STOP_ALLOWED_STATES
        assert "awaiting_human" not in DAEMON_CLEANUP_STATES

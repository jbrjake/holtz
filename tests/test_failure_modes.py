"""Failure mode tests — verify hooks degrade gracefully under adverse conditions.

Tests daemon timeout, daemon death, corrupt cache, stale state files,
concurrent access, binary unavailability, and PID reuse edge cases.

Hook output format reference (from hooks/_common.py):
  PreToolUse allow:  {"hookSpecificOutput": {"permissionDecision": "allow", ...}}
  PreToolUse block:  {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "..."}}
  PostToolUse/UPS:   {"continue": true, ...}
  Stop allow:        (empty stdout)
  Stop warn:         {"systemMessage": "..."}
  Stop block:        {"decision": "block", "reason": "..."}
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent

# Hooks under test
LIFECYCLE_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "_daemon_lifecycle.py")
STOP_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "stop_hook.py")
PRIMER_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "primer.py")
TRACKER_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "protocol_tracker.py")


# ---------------------------------------------------------------------------
# Assertion helpers — match the actual Claude Code hook output protocol
# ---------------------------------------------------------------------------


def _run_hook(hook_path: str, event: dict, timeout: int = 10) -> dict:
    """Run a hook via subprocess (same interface Claude Code uses)."""
    result = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = result.stdout.strip()
    if not stdout:
        # Empty stdout = stop allow (or PostToolUse with no output)
        return {"_empty": True, "_returncode": result.returncode,
                "_stderr": result.stderr}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw_stdout": stdout,
                "_stderr": result.stderr, "_returncode": result.returncode}


def _assert_pre_tool_allowed(output: dict, msg: str = "") -> None:
    """Assert a PreToolUse hook allowed the action."""
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    assert decision == "allow", f"Expected PreToolUse allow, got: {output}. {msg}"


def _assert_pre_tool_blocked(output: dict, msg: str = "") -> str:
    """Assert a PreToolUse hook blocked the action. Returns the reason."""
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    assert decision == "deny", f"Expected PreToolUse deny, got: {output}. {msg}"
    return output["hookSpecificOutput"].get("permissionDecisionReason", "")


def _assert_post_tool_ok(output: dict, msg: str = "") -> None:
    """Assert a PostToolUse hook exited ok (continue: true)."""
    assert output.get("continue") is True, \
        f"Expected PostToolUse continue=true, got: {output}. {msg}"


def _assert_stop_allowed(output: dict, msg: str = "") -> None:
    """Assert a Stop hook allowed the stop (empty stdout or no block)."""
    # Stop allow = empty stdout OR systemMessage (warn = still allows)
    is_empty = output.get("_empty", False)
    is_warn = "systemMessage" in output and "decision" not in output
    assert is_empty or is_warn, \
        f"Expected stop allow (empty or warn), got: {output}. {msg}"


def _assert_stop_blocked(output: dict, msg: str = "") -> str:
    """Assert a Stop hook blocked the stop. Returns the reason."""
    assert output.get("decision") == "block", \
        f"Expected stop block, got: {output}. {msg}"
    return output.get("reason", "")


def _assert_stop_warned(output: dict, msg: str = "") -> str:
    """Assert a Stop hook warned (allows but with message)."""
    assert "systemMessage" in output, \
        f"Expected stop warn with systemMessage, got: {output}. {msg}"
    assert output.get("decision") != "block", \
        f"Expected warn (not block), got: {output}. {msg}"
    return output["systemMessage"]


def _assert_hook_did_not_crash(output: dict, msg: str = "") -> None:
    """Assert the hook produced valid output (didn't crash)."""
    assert not output.get("_parse_error"), \
        f"Hook crashed or produced invalid JSON: {output}. {msg}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sahjhan_dir(root: str) -> str:
    """Create the .sahjhan data directory structure."""
    sahjhan_dir = os.path.join(root, "docs", "holtz", ".sahjhan")
    os.makedirs(sahjhan_dir, exist_ok=True)
    return sahjhan_dir


def _write_init_pid(sahjhan_dir: str, pid: int) -> None:
    """Write a daemon-init-pid file."""
    with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w") as f:
        f.write(str(pid))


def _write_status_cache(sahjhan_dir: str, state: str) -> None:
    """Write a status-cache.json file."""
    with open(os.path.join(sahjhan_dir, "status-cache.json"), "w") as f:
        json.dump({"state": state}, f)


def _find_dead_pid() -> int:
    """Find a PID that is guaranteed to not be alive."""
    pid = 99999
    while True:
        try:
            os.kill(pid, 0)
            pid += 1
        except (ProcessLookupError, OSError):
            return pid


class SlowMockDaemon:
    """Mock daemon that delays responses to simulate timeout conditions."""

    def __init__(self, socket_path: str, delay_seconds: float = 10.0):
        self.socket_path = socket_path
        self.delay = delay_seconds
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen(5)
        self._server.settimeout(0.1)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._server:
            self._server.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                conn.makefile().readline()
                time.sleep(self.delay)
                if self._stop.is_set():
                    break
                resp = {"ok": True, "data": base64.b64encode(
                    json.dumps({"state": "fix_loop", "active": True}).encode()
                ).decode()}
                conn.sendall((json.dumps(resp) + "\n").encode())
            except Exception:
                pass
            finally:
                conn.close()


class CorruptMockDaemon:
    """Mock daemon that returns corrupt/invalid data."""

    def __init__(self, socket_path: str, corrupt_mode: str = "invalid_json"):
        self.socket_path = socket_path
        self.corrupt_mode = corrupt_mode
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen(5)
        self._server.settimeout(0.1)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._server:
            self._server.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                conn.makefile().readline()
                if self.corrupt_mode == "invalid_json":
                    conn.sendall(b"NOT JSON AT ALL\n")
                elif self.corrupt_mode == "invalid_base64":
                    conn.sendall((json.dumps(
                        {"ok": True, "data": "!!!not-base64!!!"}
                    ) + "\n").encode())
                elif self.corrupt_mode == "empty":
                    conn.sendall(b"\n")
                elif self.corrupt_mode == "error_response":
                    conn.sendall((json.dumps(
                        {"ok": False, "error": "internal", "message": "boom"}
                    ) + "\n").encode())
            except Exception:
                pass
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# 3a: Daemon socket timeout
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestDaemonSocketTimeout:
    """Hooks must not hang when the daemon is slow to respond."""

    def _make_env(self, tmp_path, monkeypatch, delay: float = 10.0):
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())
        short_dir = tempfile.mkdtemp(prefix="fm_")
        sock_path = os.path.join(short_dir, "d.sock")
        daemon = SlowMockDaemon(sock_path, delay_seconds=delay)
        daemon.start()
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", sock_path)
        return daemon, short_dir, sahjhan_dir

    def test_lifecycle_hook_does_not_hang(self, tmp_path):
        """_daemon_lifecycle doesn't connect to daemon — it checks PID only."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        _assert_pre_tool_allowed(output)

    def test_stop_hook_degrades_when_cache_unreachable(self, tmp_path, monkeypatch):
        """stop_hook falls back to status-cache.json when daemon is slow."""
        daemon, short_dir, sahjhan_dir = self._make_env(tmp_path, monkeypatch)
        try:
            _write_status_cache(sahjhan_dir, "idle")
            event = {"tool_name": "Stop", "cwd": str(tmp_path)}
            output = _run_hook(STOP_HOOK, event, timeout=15)
            _assert_stop_allowed(output)
        finally:
            daemon.stop()
            shutil.rmtree(short_dir, ignore_errors=True)

    def test_protocol_tracker_does_not_crash_on_timeout(self, tmp_path, monkeypatch):
        """protocol_tracker degrades gracefully on daemon timeout."""
        daemon, short_dir, sahjhan_dir = self._make_env(tmp_path, monkeypatch)
        try:
            event = {
                "tool_name": "Bash",
                "tool_input": {"command": "echo hello"},
                "tool_response": {"exit_code": 0, "output": "hello"},
                "cwd": str(tmp_path),
            }
            output = _run_hook(TRACKER_HOOK, event, timeout=15)
            _assert_post_tool_ok(output)
        finally:
            daemon.stop()
            shutil.rmtree(short_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3b: Daemon death mid-session
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestDaemonDeathMidSession:
    """Hooks detect and handle daemon death correctly."""

    def test_lifecycle_detects_dead_pid(self, tmp_path):
        """_daemon_lifecycle detects a dead daemon PID and writes terminated marker."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        dead_pid = _find_dead_pid()
        _write_init_pid(sahjhan_dir, dead_pid)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        reason = _assert_pre_tool_blocked(output)
        assert "TERMINATED" in reason

        # Should have written terminated marker
        marker = os.path.join(sahjhan_dir, "terminated")
        assert os.path.isfile(marker)
        with open(marker) as f:
            content = f.read()
        assert "daemon_pid_dead" in content
        assert str(dead_pid) in content

    def test_lifecycle_allows_when_no_data_dir(self, tmp_path):
        """_daemon_lifecycle passes through when no audit is active."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        _assert_pre_tool_allowed(output)

    def test_lifecycle_blocks_on_existing_terminated_marker(self, tmp_path):
        """_daemon_lifecycle fast-paths to block if terminated marker exists."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        with open(os.path.join(sahjhan_dir, "terminated"), "w") as f:
            f.write("reason: daemon_pid_dead\ninit_pid: 12345\n")

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        reason = _assert_pre_tool_blocked(output)
        assert "TERMINATED" in reason

    def test_stop_hook_allows_after_death(self, tmp_path, monkeypatch):
        """stop_hook allows stop when daemon is dead."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        dead_pid = _find_dead_pid()
        _write_init_pid(sahjhan_dir, dead_pid)
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        _assert_stop_allowed(output)

    def test_real_daemon_death_detection(self, real_daemon):
        """Kill the real daemon and verify lifecycle hook detects it."""
        project_root = real_daemon["project_root"]
        pid = real_daemon["pid"]
        proc = real_daemon["proc"]

        os.kill(pid, signal.SIGKILL)
        proc.wait(timeout=5)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": project_root,
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        reason = _assert_pre_tool_blocked(output)
        assert "TERMINATED" in reason

        marker = os.path.join(
            project_root, "docs", "holtz", ".sahjhan", "terminated"
        )
        assert os.path.isfile(marker)


# ---------------------------------------------------------------------------
# 3c: Corrupt enforcement cache
# ---------------------------------------------------------------------------


class TestCorruptEnforcementCache:
    """Hooks handle corrupt daemon responses without crashing."""

    @pytest.fixture
    def corrupt_env(self, tmp_path):
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())
        short_dir = tempfile.mkdtemp(prefix="fm_")
        yield tmp_path, sahjhan_dir, short_dir
        shutil.rmtree(short_dir, ignore_errors=True)

    def _make_corrupt(self, short_dir, monkeypatch, mode):
        sock_path = os.path.join(short_dir, "d.sock")
        daemon = CorruptMockDaemon(sock_path, corrupt_mode=mode)
        daemon.start()
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", sock_path)
        return daemon

    def test_invalid_json_from_daemon(self, corrupt_env, monkeypatch):
        """Hook handles invalid JSON from daemon socket."""
        tmp_path, sahjhan_dir, short_dir = corrupt_env
        daemon = self._make_corrupt(short_dir, monkeypatch, "invalid_json")
        try:
            # stop_hook: read_cache returns None on JSON error → file fallback
            _write_status_cache(sahjhan_dir, "idle")
            event = {"tool_name": "Stop", "cwd": str(tmp_path)}
            output = _run_hook(STOP_HOOK, event)
            _assert_hook_did_not_crash(output)
            _assert_stop_allowed(output)
        finally:
            daemon.stop()

    def test_invalid_base64_from_daemon(self, corrupt_env, monkeypatch):
        """Hook handles invalid base64 in daemon response."""
        tmp_path, sahjhan_dir, short_dir = corrupt_env
        daemon = self._make_corrupt(short_dir, monkeypatch, "invalid_base64")
        try:
            _write_status_cache(sahjhan_dir, "idle")
            event = {"tool_name": "Stop", "cwd": str(tmp_path)}
            output = _run_hook(STOP_HOOK, event)
            _assert_hook_did_not_crash(output)
            _assert_stop_allowed(output)
        finally:
            daemon.stop()

    def test_error_response_from_daemon(self, corrupt_env, monkeypatch):
        """Hook handles error response from daemon."""
        tmp_path, sahjhan_dir, short_dir = corrupt_env
        daemon = self._make_corrupt(short_dir, monkeypatch, "error_response")
        try:
            _write_status_cache(sahjhan_dir, "idle")
            event = {"tool_name": "Stop", "cwd": str(tmp_path)}
            output = _run_hook(STOP_HOOK, event)
            _assert_hook_did_not_crash(output)
            _assert_stop_allowed(output)
        finally:
            daemon.stop()

    def test_empty_response_tracker(self, corrupt_env, monkeypatch):
        """protocol_tracker handles empty daemon response."""
        tmp_path, sahjhan_dir, short_dir = corrupt_env
        daemon = self._make_corrupt(short_dir, monkeypatch, "empty")
        try:
            event = {
                "tool_name": "Bash",
                "tool_input": {"command": "echo hello"},
                "tool_response": {"exit_code": 0, "output": "hello"},
                "cwd": str(tmp_path),
            }
            output = _run_hook(TRACKER_HOOK, event)
            _assert_hook_did_not_crash(output)
            _assert_post_tool_ok(output)
        finally:
            daemon.stop()


# ---------------------------------------------------------------------------
# 3d: Stale status-cache.json
# ---------------------------------------------------------------------------


class TestStaleStatusCache:
    """stop_hook handles stale or outdated status-cache.json."""

    def test_stale_cache_with_dead_daemon(self, tmp_path, monkeypatch):
        """With dead daemon, stop_hook detects death regardless of cache."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        dead_pid = _find_dead_pid()
        _write_init_pid(sahjhan_dir, dead_pid)
        _write_status_cache(sahjhan_dir, "fix_loop")
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        # Dead daemon → PID check fires before cache → allow stop
        _assert_stop_allowed(output)

    def test_file_fallback_idle_state(self, tmp_path, monkeypatch):
        """stop_hook allows stop via file fallback in idle state."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())
        _write_status_cache(sahjhan_dir, "idle")
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        _assert_stop_allowed(output)

    def test_file_fallback_active_state_blocks(self, tmp_path, monkeypatch):
        """stop_hook blocks via file fallback in active state."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())
        _write_status_cache(sahjhan_dir, "fix_loop")
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        reason = _assert_stop_blocked(output)
        assert "fix_loop" in reason

    def test_no_caches_available_warns(self, tmp_path, monkeypatch):
        """stop_hook warns (not crashes) when both caches unavailable."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        # Should warn (allows stop) — issue #48 fix
        message = _assert_stop_warned(output)
        assert "unavailable" in message.lower()


# ---------------------------------------------------------------------------
# 3e: Concurrent cache access
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestConcurrentCacheAccess:
    """Parallel hook invocations don't corrupt shared state."""

    def test_parallel_tracker_invocations(self, mock_daemon, tmp_path):
        """Multiple protocol_tracker invocations in parallel don't corrupt state."""
        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 0,
            "unregistered_commits": [],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "fixes_since_pattern": 0,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"exit_code": 0, "output": "hello"},
            "cwd": str(tmp_path),
        }

        errors: list[str] = []

        def run_hook():
            try:
                result = _run_hook(TRACKER_HOOK, event)
                _assert_post_tool_ok(result)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=run_hook) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Concurrent hook errors: {errors}"
        assert mock_daemon.state is not None
        assert isinstance(mock_daemon.state.get("stall"), int)


# ---------------------------------------------------------------------------
# 3f: Binary unavailable
# ---------------------------------------------------------------------------


class TestBinaryUnavailable:
    """Hooks degrade gracefully when sahjhan binary is missing."""

    def test_primer_allows_without_binary(self, tmp_path, monkeypatch):
        """primer.py exits ok when binary is None."""
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        _make_sahjhan_dir(str(tmp_path))

        event = {"tool_name": "UserPromptSubmit", "cwd": str(tmp_path)}
        output = _run_hook(PRIMER_HOOK, event)
        # binary is None → early exit_ok
        _assert_hook_did_not_crash(output)
        assert output.get("continue") is True or \
            output.get("hookSpecificOutput") is not None or \
            output.get("_empty"), \
            f"Primer should allow when binary unavailable: {output}"

    def test_stop_hook_allows_without_binary(self, tmp_path, monkeypatch):
        """stop_hook doesn't crash when binary is missing during cleanup."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        with open(os.path.join(sahjhan_dir, "terminated"), "w") as f:
            f.write("reason: daemon_pid_dead\ninit_pid: 12345\n")
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        _assert_stop_allowed(output)

    def test_protocol_tracker_allows_without_binary(self, tmp_path, monkeypatch):
        """protocol_tracker exits ok when binary unavailable for refresh."""
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status 2>&1"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(TRACKER_HOOK, event)
        _assert_hook_did_not_crash(output)
        _assert_post_tool_ok(output)


# ---------------------------------------------------------------------------
# 3g: PID reuse simulation
# ---------------------------------------------------------------------------


class TestPIDReuse:
    """Document PID reuse limitations in daemon liveness detection.

    PID reuse (a different process inherits the daemon's PID after death)
    is a fundamental limitation of PID-based liveness checks. These tests
    document the behavior rather than expecting the code to handle it.
    """

    def test_own_pid_treated_as_alive(self, tmp_path):
        """A PID that is alive (our own) is treated as alive daemon."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, os.getpid())

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        _assert_pre_tool_allowed(output)

    def test_pid_1_treated_as_alive(self, tmp_path):
        """PID 1 (init/launchd) is always alive — known limitation.

        If the daemon's PID gets reused by PID 1, the lifecycle hook
        incorrectly treats the daemon as alive. Documented limitation.
        """
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        _write_init_pid(sahjhan_dir, 1)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        _assert_pre_tool_allowed(output)

    def test_missing_pid_file_allows(self, tmp_path):
        """No daemon-init-pid file → legacy/pre-init audit → allow."""
        _make_sahjhan_dir(str(tmp_path))

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        _assert_pre_tool_allowed(output)

    def test_corrupt_pid_file_allows(self, tmp_path):
        """Corrupt daemon-init-pid (non-integer) → treated as missing → allow."""
        sahjhan_dir = _make_sahjhan_dir(str(tmp_path))
        with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w") as f:
            f.write("not-a-number\n")

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(LIFECYCLE_HOOK, event)
        _assert_pre_tool_allowed(output)

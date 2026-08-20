"""Tests for boundary_check.py — the step-0 guardrail probe.

The probe answers one question: can this shell open the daemon socket? Its
value depends entirely on never answering `confined` when it can. So the
tests drive it against a *real* Unix socket rather than a mock — a mock would
be asserting that the code does what the code does, and the thing that could
break here is which errno means what.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "skills", "holtz", "scripts", "boundary_check.py")
sys.path.insert(0, os.path.join(REPO_ROOT, "skills", "holtz", "scripts"))

import boundary_check  # noqa: E402


class _Listener:
    """A throwaway Unix socket listener, the way a live daemon looks."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(4)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        self.sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except (OSError, TimeoutError):
                continue
            conn.close()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self.sock.close()


@pytest.fixture
def short_tmp():
    """A directory short enough to hold a bindable socket path.

    macOS caps `sun_path` at 104 bytes and pytest's `tmp_path` blows straight
    past it, so /tmp explicitly — not `$TMPDIR`, which resolves to
    /private/var/folders/... there. Same workaround as the `real_daemon`
    fixture in conftest.
    """
    path = tempfile.mkdtemp(prefix="bc-", dir="/tmp")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def listener(short_tmp):
    path = os.path.join(short_tmp, "d.sock")
    lis = _Listener(path)
    yield path
    lis.close()


def test_reachable_socket_is_exposed(listener):
    """A shell that CAN connect is not behind the boundary, whatever else is true."""
    assert boundary_check.probe(listener) == boundary_check.EXPOSED


def test_missing_socket_is_no_daemon(tmp_path):
    assert boundary_check.probe(str(tmp_path / "absent.sock")) == boundary_check.NO_DAEMON


def test_stale_socket_file_is_no_daemon(short_tmp):
    """A socket file left behind by a dead daemon refuses the connection.

    Reporting `confined` here would be the worst possible answer: nothing is
    protecting anything, and the audit would be waved through.
    """
    path = os.path.join(short_tmp, "stale.sock")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(path)
    sock.close()  # bound but never listening, and now gone
    assert boundary_check.probe(path) == boundary_check.NO_DAEMON


def test_a_directory_is_not_confinement(tmp_path):
    """Any unclassified OSError must fall to no-daemon, never to confined."""
    d = tmp_path / "notasocket"
    d.mkdir()
    assert boundary_check.probe(str(d)) != boundary_check.CONFINED


def test_denied_connect_is_confined(tmp_path, monkeypatch):
    """EPERM from the sandbox is the one signal that means confined.

    macOS Seatbelt answers a denied `connect()` with EPERM; Linux's seccomp
    filter blocks `socket(AF_UNIX)` outright, which surfaces the same way.
    Neither can be produced from an unsandboxed test process, so the errno
    itself is injected — the classification is what is under test.
    """
    real_connect = socket.socket.connect

    def _deny(self, address):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(socket.socket, "connect", _deny)
    try:
        assert boundary_check.probe(str(tmp_path / "any.sock")) == boundary_check.CONFINED
    finally:
        monkeypatch.setattr(socket.socket, "connect", real_connect)


def test_exit_status_gates_the_step(listener, monkeypatch):
    """Non-zero exit is what makes the skill step stop rather than continue."""
    monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", listener)
    result = subprocess.run(
        [sys.executable, SCRIPT], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert boundary_check.EXPOSED in result.stdout


def test_probe_does_not_depend_on_claude_code_sandboxed(tmp_path, monkeypatch):
    """The env-var proxy is not a proxy: 2.1.237 reads it, never sets it.

    Claude Code sets nothing in a sandboxed command's environment to say so —
    `CLAUDE_CODE_SANDBOXED` is an *input* the launcher reads to skip the trust
    dialog when Claude Code itself runs containerized. A probe keyed on it
    would report `exposed` inside a working sandbox.
    """
    monkeypatch.setenv("CLAUDE_CODE_SANDBOXED", "1")
    assert boundary_check.probe(str(tmp_path / "absent.sock")) == boundary_check.NO_DAEMON

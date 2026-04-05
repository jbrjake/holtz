"""Tests for daemon-based event provenance helpers."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest import mock

# Load enforcement/hooks/_common.py directly by path to avoid sys.path conflicts
# with hooks/_common.py (same filename, different directories).
ENFORCEMENT_HOOKS = Path(__file__).parent.parent / "enforcement" / "hooks"


def _load_enforcement_common() -> ModuleType:
    """Load enforcement/hooks/_common.py directly, bypassing sys.path."""
    path = ENFORCEMENT_HOOKS / "_common.py"
    spec = importlib.util.spec_from_file_location("_common_enforcement", str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(path)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_enforcement_common = _load_enforcement_common()


def _mock_daemon_sign(expected_proof: str = "abc123def456"):
    """Create a mock for _daemon_request that returns a sign response."""
    def _fake_request(sock_path, request):
        assert request["op"] == "sign"
        return {"ok": True, "proof": expected_proof}
    return mock.patch.object(_enforcement_common, '_daemon_request', side_effect=_fake_request)


def test_compute_event_proof_calls_daemon():
    """compute_event_proof connects to daemon and returns proof."""
    with _mock_daemon_sign("deadbeef0123"):
        proof = _enforcement_common.compute_event_proof(
            "quiz_answered",
            {"project": "holtz", "perspective": "component"},
        )
    assert proof == "deadbeef0123"


def test_compute_event_proof_sorts_fields():
    """Fields must be sorted before sending to daemon."""
    requests = []

    def _capture_request(sock_path, request):
        requests.append(request)
        return {"ok": True, "proof": "abc"}

    with mock.patch.object(_enforcement_common, '_daemon_request', side_effect=_capture_request):
        _enforcement_common.compute_event_proof(
            "test_event", {"z_field": "last", "a_field": "first"}
        )

    assert requests[0]["fields"] == {"a_field": "first", "z_field": "last"}


def test_compute_event_proof_field_order_independent():
    """Field ordering must not affect the request sent to daemon (sorted internally)."""
    requests = []

    def _capture_request(sock_path, request):
        requests.append(request)
        return {"ok": True, "proof": "abc"}

    with mock.patch.object(_enforcement_common, '_daemon_request', side_effect=_capture_request):
        _enforcement_common.compute_event_proof(
            "test_event", {"z_field": "last", "a_field": "first"}
        )
        _enforcement_common.compute_event_proof(
            "test_event", {"a_field": "first", "z_field": "last"}
        )

    assert requests[0]["fields"] == requests[1]["fields"]


def test_compute_event_proof_rejects_null_bytes_in_values():
    """Field values with null bytes must raise ValueError (BH-014)."""
    import pytest
    with pytest.raises(ValueError, match="Null byte"):
        _enforcement_common.compute_event_proof(
            "quiz_answered", {"auditor": "holtz\x00score=5/5"}
        )


def test_compute_event_proof_rejects_null_bytes_in_keys():
    """Field keys with null bytes must raise ValueError (BH-014)."""
    import pytest
    with pytest.raises(ValueError, match="Null byte"):
        _enforcement_common.compute_event_proof(
            "test", {"a\x00b": "c"}
        )


def test_compute_event_proof_daemon_error_raises():
    """RuntimeError raised when daemon returns error."""
    import pytest

    def _error_request(sock_path, request):
        raise RuntimeError("sahjhan daemon error: auth_failed")

    with mock.patch.object(
        _enforcement_common, '_daemon_request', side_effect=_error_request
    ), pytest.raises(RuntimeError, match="auth_failed"):
        _enforcement_common.compute_event_proof("test", {"a": "b"})


def test_daemon_request_sends_json():
    """_daemon_request sends newline-delimited JSON and parses response."""
    import socket as socket_mod

    mock_socket = mock.MagicMock()
    mock_file = mock.MagicMock()
    mock_file.readline.return_value = json.dumps({"ok": True, "proof": "test123"})
    mock_socket.makefile.return_value = mock_file

    with mock.patch.object(socket_mod, 'socket', return_value=mock_socket):
        result = _enforcement_common._daemon_request(
            "/tmp/test.sock",
            {"op": "sign", "event_type": "test", "fields": {}},
        )

    assert result == {"ok": True, "proof": "test123"}
    mock_socket.connect.assert_called_once_with("/tmp/test.sock")
    sent_data = mock_socket.sendall.call_args[0][0]
    parsed = json.loads(sent_data.decode().strip())
    assert parsed["op"] == "sign"


def test_daemon_request_raises_on_error_response():
    """_daemon_request raises RuntimeError when daemon returns ok=false."""
    import socket as socket_mod

    import pytest

    mock_socket = mock.MagicMock()
    mock_file = mock.MagicMock()
    mock_file.readline.return_value = json.dumps({
        "ok": False, "error": "auth_failed", "message": "not in manifest"
    })
    mock_socket.makefile.return_value = mock_file

    with mock.patch.object(
        socket_mod, 'socket', return_value=mock_socket
    ), pytest.raises(RuntimeError, match="not in manifest"):
        _enforcement_common._daemon_request(
            "/tmp/test.sock",
            {"op": "sign", "event_type": "test", "fields": {}},
        )


def test_get_daemon_socket_path():
    """Issue #35 bug 3: Socket path must use daemon.sock (binary's actual name)."""
    path = _enforcement_common._get_daemon_socket_path("/tmp/project")
    assert path == "/tmp/project/docs/holtz/.sahjhan/daemon.sock"


def test_get_daemon_socket_path_defaults_to_cwd():
    """With no argument, uses os.getcwd()."""
    with mock.patch("os.getcwd", return_value="/fake/cwd"):
        path = _enforcement_common._get_daemon_socket_path()
    assert path == "/fake/cwd/docs/holtz/.sahjhan/daemon.sock"


def test_compute_event_proof_ignores_key_path_kwarg():
    """key_path kwarg is accepted for backward compat but ignored."""
    with _mock_daemon_sign("compat_proof"):
        proof = _enforcement_common.compute_event_proof(
            "test", {"a": "b"}, key_path="/ignored/path"
        )
    assert proof == "compat_proof"


def test_compute_event_proof_uses_explicit_cwd():
    """Issue #35 bug 1: compute_event_proof must use explicit cwd for socket path.

    In worktree subagents, os.getcwd() is a temp dir. Callers must be able
    to pass cwd so the socket path resolves to the main project daemon.
    """
    def _fake_request(sock_path, request):
        assert sock_path == "/main/project/docs/holtz/.sahjhan/daemon.sock"
        return {"ok": True, "proof": "worktree_proof"}

    with mock.patch.object(_enforcement_common, '_daemon_request', side_effect=_fake_request):
        proof = _enforcement_common.compute_event_proof(
            "test", {"a": "b"}, cwd="/main/project"
        )
    assert proof == "worktree_proof"


def test_write_active_run_marker(tmp_path):
    """Issue #35 bug 2: write_active_run_marker creates the active-run file."""
    (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
    _enforcement_common.write_active_run_marker(str(tmp_path), "run-42")
    marker = tmp_path / "docs" / "holtz" / ".sahjhan" / "active-run"
    assert marker.exists()
    assert marker.read_text().strip() == "run-42"


def test_write_active_run_marker_requires_data_dir(tmp_path):
    """write_active_run_marker is a no-op when .sahjhan dir doesn't exist."""
    # Should not raise, just silently skip
    _enforcement_common.write_active_run_marker(str(tmp_path), "run-99")
    marker = tmp_path / "docs" / "holtz" / ".sahjhan" / "active-run"
    assert not marker.exists()

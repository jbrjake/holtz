"""Mock sahjhan daemon for testing enforcement state operations.

Implements enforcement_read, enforcement_write, and enforcement_update
over a Unix domain socket. Same wire protocol as the real daemon.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import threading
from datetime import datetime, timezone
from typing import Any


class MockEnforcementDaemon:
    """Lightweight mock daemon serving enforcement state over a Unix socket.

    Usage::

        daemon = MockEnforcementDaemon(socket_path)
        daemon.start()
        # ... tests connect to socket_path ...
        daemon.stop()
    """

    def __init__(self, socket_path: str | os.PathLike) -> None:
        self.socket_path = str(socket_path)
        self.state: dict[str, Any] | None = None
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen(5)
        self._server.settimeout(0.1)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._server is not None:
            self._server.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stop_event.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                data = conn.makefile().readline()
                if not data.strip():
                    continue
                request = json.loads(data)
                response = self._handle(request)
                conn.sendall((json.dumps(response) + "\n").encode())
            except Exception as exc:
                conn.sendall(
                    (json.dumps({"ok": False, "error": "internal", "message": str(exc)}) + "\n").encode()
                )
            finally:
                conn.close()

    def _handle(self, request: dict) -> dict:
        op = request.get("op", "")

        if op == "enforcement_read":
            if self.state is None:
                return {"ok": False, "error": "not_found", "message": "no enforcement state"}
            encoded = base64.b64encode(json.dumps(self.state).encode()).decode()
            return {"ok": True, "data": encoded}

        if op == "enforcement_write":
            raw = json.loads(base64.b64decode(request["data"]))
            raw["last_refresh"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
            self.state = raw
            return {"ok": True}

        if op == "enforcement_update":
            if self.state is None:
                return {"ok": False, "error": "not_found", "message": "no enforcement state to update"}
            patch = json.loads(base64.b64decode(request["patch"]))
            self.state.update(patch)
            self.state["last_refresh"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
            encoded = base64.b64encode(json.dumps(self.state).encode()).decode()
            return {"ok": True, "data": encoded}

        if op == "sign":
            # Return a dummy proof for tests that need signing support
            return {"ok": True, "proof": "deadbeef" * 8}

        return {"ok": False, "error": "unknown_op", "message": f"unknown op: {op}"}


def test_mock_daemon_round_trip(tmp_path):
    """Verify the mock daemon handles enforcement ops correctly."""
    import socket as sock_mod
    import tempfile

    # Use a short path in /tmp to stay within macOS AF_UNIX 104-char limit.
    # pytest tmp_path can be 100+ chars which exceeds the kernel limit.
    tmpdir = tempfile.mkdtemp(prefix="mked_")
    socket_path = os.path.join(tmpdir, "d.sock")
    daemon = MockEnforcementDaemon(socket_path)
    daemon.start()
    try:
        def _request(req: dict) -> dict:
            s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
            s.connect(str(socket_path))
            s.sendall((json.dumps(req) + "\n").encode())
            resp = json.loads(s.makefile().readline())
            s.close()
            return resp

        # Read before write → not_found
        resp = _request({"op": "enforcement_read"})
        assert resp["ok"] is False
        assert resp["error"] == "not_found"

        # Write state
        state = {"active": True, "state": "fix_loop", "stall": 0}
        encoded = base64.b64encode(json.dumps(state).encode()).decode()
        resp = _request({"op": "enforcement_write", "data": encoded})
        assert resp["ok"] is True

        # Read back
        resp = _request({"op": "enforcement_read"})
        assert resp["ok"] is True
        read_back = json.loads(base64.b64decode(resp["data"]))
        assert read_back["state"] == "fix_loop"
        assert "last_refresh" in read_back

        # Update
        patch = {"stall": 5}
        patch_encoded = base64.b64encode(json.dumps(patch).encode()).decode()
        resp = _request({"op": "enforcement_update", "patch": patch_encoded})
        assert resp["ok"] is True
        updated = json.loads(base64.b64decode(resp["data"]))
        assert updated["stall"] == 5
        assert updated["state"] == "fix_loop"  # unchanged field preserved

        # Update on missing state → not_found
        daemon.state = None
        resp = _request({"op": "enforcement_update", "patch": patch_encoded})
        assert resp["ok"] is False
        assert resp["error"] == "not_found"
    finally:
        daemon.stop()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

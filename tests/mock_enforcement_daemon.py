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
        # vault support: in-memory name -> bytes store, mirroring the real
        # daemon's vault_store/vault_read/vault_list/vault_delete ops.
        self.vault: dict[str, bytes] = {}
        # record_event support: log of received requests + a configurable
        # canned response. Default success returns a ledger seq in `data`.
        self.recorded_events: list[dict] = []
        self.record_event_response: dict | None = None
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

        if op == "status":
            # Health check — always allowed by the real daemon, no auth.
            return {
                "ok": True,
                "pid": os.getpid(),
                "uptime_seconds": 1,
                "vault_entries": 0,
                "enforcement_active": self.state is not None,
            }

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

        if op == "vault_store":
            name = request.get("name", "")
            if name.startswith("_"):
                return {"ok": False, "error": "reserved",
                        "message": "vault names starting with '_' are reserved"}
            try:
                self.vault[name] = base64.b64decode(request["data"])
            except (KeyError, ValueError) as exc:
                return {"ok": False, "error": "decode_error", "message": str(exc)}
            return {"ok": True}

        if op == "vault_read":
            name = request.get("name", "")
            if name.startswith("_"):
                return {"ok": False, "error": "reserved",
                        "message": "vault names starting with '_' are reserved"}
            if name not in self.vault:
                return {"ok": False, "error": "not_found",
                        "message": f"no entry named '{name}'"}
            encoded = base64.b64encode(self.vault[name]).decode()
            return {"ok": True, "data": encoded}

        if op == "vault_delete":
            name = request.get("name", "")
            self.vault.pop(name, None)
            return {"ok": True}

        if op == "vault_list":
            names = [n for n in self.vault if not n.startswith("_")]
            return {"ok": True, "names": names}

        if op == "sign":
            # Return a dummy proof for tests that need signing support
            return {"ok": True, "proof": "deadbeef" * 8}

        if op == "record_event":
            # Log the append request so tests can assert what was recorded,
            # then return the configured response (default: success with a
            # ledger seq). Tests set record_event_response to a {"ok": False,
            # ...} value to simulate a daemon-side rejection.
            self.recorded_events.append(request)
            if self.record_event_response is not None:
                return self.record_event_response
            return {"ok": True, "data": str(len(self.recorded_events))}

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

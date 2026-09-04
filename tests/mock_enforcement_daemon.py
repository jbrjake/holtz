"""Mock sahjhan daemon for testing enforcement state operations.

Implements enforcement_read, enforcement_write, enforcement_update and
enforcement_merge over a Unix domain socket. Same wire protocol as the real
daemon.

The merge and version rules below are a port of sahjhan's own
``src/daemon/enforcement.rs`` (v0.27.0, #49), not a reading of its release
note. That matters more here than for the other ops: a real daemon refuses
every enforcement mutation from a test process (``auth_failed`` —
the caller is pytest, not a hash-pinned hook), so this mock is the only place
an interleave can be driven, and a mock that merges differently from the
engine would prove the opposite of what its tests claim.
``TestTheMockMergesLikeTheEngine`` pins each rule against the case the engine
asserts it with.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


def merge_patch(target: dict[str, Any], patch: dict[str, Any]) -> None:
    """Apply an RFC 7386 JSON Merge Patch to ``target``, in place.

    Port of ``enforcement::merge_patch``. Three rules, in the engine's order:
    ``null`` deletes the key at any depth; an object over an object recurses
    (the per-actor write this exists for); anything else — scalars, arrays,
    an object over a non-object — replaces. Arrays are deliberately *not*
    merged element-wise, so a patch naming one actor's commit list sends that
    actor's whole list rather than an append.
    """
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
        elif isinstance(value, dict):
            # RFC 7386: an object patch over a non-object (or absent) target
            # applies to an empty object, which drops nested nulls rather than
            # storing them — a stored null would be served back to a consumer
            # that never wrote one.
            entry = target.get(key)
            if not isinstance(entry, dict):
                entry = {}
                target[key] = entry
            merge_patch(entry, value)
        else:
            target[key] = value


def version_of(stored: bytes) -> str:
    """The CAS token for a stored enforcement blob — ``sha256:<hex>``.

    Port of ``enforcement::version_of``. Opaque to the caller: compare it, do
    not parse it. Computed over the bytes *as stored*, which is why a ledger
    transition does not invalidate an outstanding token — only a write does.
    """
    return f"sha256:{hashlib.sha256(stored).hexdigest()}"


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
        # Sandbox-fuse simulation. When set to a reason code, every op except
        # `status` is refused with `sandbox_required` — the real daemon checks
        # its fuse before auth and exempts only the health check, so this
        # mirrors where the refusal lands rather than merely that it happens.
        self.refuse_boundary: str | None = None
        # The interleave seam. A real daemon's ops are atomic end to end, so a
        # hook subprocess cannot be caught between its read and its write from
        # outside — which is exactly the window the whole-map write loses a
        # sibling in. Setting this makes the daemon apply a sibling's change
        # *immediately after* answering a read, deterministically, instead of
        # a test racing two subprocesses and hoping. Fires once, then clears.
        self.after_read: Callable[[MockEnforcementDaemon], None] | None = None
        # (op, outcome) per request, where outcome is "ok" or the refusal code.
        # A retry is otherwise invisible: a conditional write that is refused
        # and then succeeds leaves exactly the state an unconditional write
        # would have, so "the right value is stored" cannot tell the two apart.
        # This is what lets a test assert the refusal happened.
        self.log: list[tuple[str, str]] = []
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
                self.log.append((
                    str(request.get("op", "")),
                    "ok" if response.get("ok") else str(response.get("error", "")),
                ))
                conn.sendall((json.dumps(response) + "\n").encode())
            except Exception as exc:
                conn.sendall(
                    (json.dumps({"ok": False, "error": "internal", "message": str(exc)}) + "\n").encode()
                )
            finally:
                conn.close()

    def _stored(self) -> bytes:
        """The blob as the daemon holds it — what the version token hashes."""
        return json.dumps(self.state).encode()

    def version(self) -> str | None:
        """The current CAS token, or ``None`` when nothing is stored."""
        return None if self.state is None else version_of(self._stored())

    def _version_refusal(self, expected: str | None) -> dict | None:
        """The refusal a conditional mutation gets, or ``None`` to proceed.

        Port of ``daemon::version_refusal``. An absent ``expect_version`` is an
        unconditional mutation — the pre-#49 behaviour and still the default.
        Nothing stored is a conflict rather than a create: the caller holds a
        token for a blob that no longer exists.
        """
        if expected is None:
            return None
        actual = self.version()
        if actual is None:
            return {"ok": False, "error": "version_conflict",
                    "message": "no enforcement state to match against"}
        if actual == expected:
            return None
        return {"ok": False, "error": "version_conflict", "version": actual,
                "message": "enforcement state has changed since it was read"}

    def _fire_after_read(self) -> None:
        """Let a sibling land between this read and the reader's write."""
        callback, self.after_read = self.after_read, None
        if callback is not None:
            callback(self)

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

        if self.refuse_boundary is not None:
            return {
                "ok": False,
                "error": "sandbox_required",
                "reason": self.refuse_boundary,
                "message": "the sandbox boundary is not in place",
            }

        if op == "enforcement_read":
            if self.state is None:
                return {"ok": False, "error": "not_found", "message": "no enforcement state"}
            encoded = base64.b64encode(self._stored()).decode()
            response = {"ok": True, "data": encoded, "version": self.version()}
            self._fire_after_read()
            return response

        if op == "enforcement_write":
            refusal = self._version_refusal(request.get("expect_version"))
            if refusal is not None:
                return refusal
            raw = json.loads(base64.b64decode(request["data"]))
            raw["last_refresh"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
            self.state = raw
            return {"ok": True, "version": self.version()}

        if op in ("enforcement_update", "enforcement_merge"):
            if self.state is None:
                return {"ok": False, "error": "not_found", "message": "no enforcement state to update"}
            refusal = self._version_refusal(request.get("expect_version"))
            if refusal is not None:
                return refusal
            patch = json.loads(base64.b64decode(request["patch"]))
            if op == "enforcement_merge":
                merge_patch(self.state, patch)
            else:
                self.state.update(patch)
            self.state["last_refresh"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
            encoded = base64.b64encode(self._stored()).decode()
            return {"ok": True, "data": encoded, "version": self.version()}

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


class TestTheMockMergesLikeTheEngine:
    """Each RFC 7386 rule, against the case sahjhan asserts it with.

    Every interleave test in this suite is a claim about the *engine*, driven
    against this mock because a real daemon will not take an enforcement
    mutation from a test process. So the mock's fidelity is load-bearing, and
    these are the engine's own unit cases (``enforcement.rs``, ``mod tests``)
    restated against the port. If sahjhan changes what a merge means, one of
    these should be what says so.
    """

    @staticmethod
    def _merged(state: dict, patch: dict) -> dict:
        merge_patch(state, patch)
        return state

    def test_nested_object_merge_leaves_siblings_alone(self):
        """The reported defect: naming one actor must not touch the others."""
        out = self._merged(
            {"stall": {"": 0, "agent-a": 3, "agent-b": 1}},
            {"stall": {"agent-a": 4}},
        )
        assert out["stall"] == {"": 0, "agent-a": 4, "agent-b": 1}

    def test_interleaved_actor_writes_both_survive(self):
        """#49's reproduction: b bumps, a then writes from a stale snapshot."""
        state = {"stall": {"agent-b": 1}}
        merge_patch(state, {"stall": {"agent-b": 2}})
        merge_patch(state, {"stall": {"agent-a": 1}})
        assert state["stall"] == {"agent-b": 2, "agent-a": 1}

    def test_untouched_top_level_keys_are_preserved(self):
        out = self._merged(
            {"stall": {"a": 1}, "unregistered_commits": {"a": ["abc"]}},
            {"stall": {"a": 2}},
        )
        assert out["unregistered_commits"] == {"a": ["abc"]}

    def test_null_deletes_a_nested_key(self):
        """The spelling `stall_cleared` uses — deletion, not a zero sentinel."""
        out = self._merged(
            {"stall": {"agent-a": 3, "agent-b": 1}},
            {"stall": {"agent-a": None}},
        )
        assert out["stall"] == {"agent-b": 1}

    def test_null_deletes_a_top_level_key(self):
        out = self._merged({"stall": {"a": 1}, "keep": 2}, {"stall": None})
        assert "stall" not in out
        assert out["keep"] == 2

    def test_deleting_an_absent_key_is_a_no_op(self):
        out = self._merged({"keep": 1}, {"gone": None, "nested": {"x": None}})
        assert out["keep"] == 1
        assert "gone" not in out
        # An object patch over an absent key applies to an empty object, so the
        # nested null leaves an empty map rather than a stored null.
        assert out["nested"] == {}

    def test_arrays_replace_rather_than_concatenate(self):
        """Why a commit-list merge is a per-actor write and not an append."""
        out = self._merged(
            {"unregistered_commits": {"a": ["abc", "def"]}},
            {"unregistered_commits": {"a": ["def"]}},
        )
        assert out["unregistered_commits"]["a"] == ["def"]

    def test_scalar_over_object_replaces_it(self):
        assert self._merged({"stall": {"a": 1}}, {"stall": 0})["stall"] == 0

    def test_object_over_scalar_replaces_it(self):
        """The pre-keying shape's fate: a bare int is replaced, not merged into."""
        assert self._merged({"stall": 0}, {"stall": {"a": 1}})["stall"] == {"a": 1}

    def test_deep_nesting_recurses_all_the_way_down(self):
        out = self._merged(
            {"a": {"b": {"c": {"d": 1, "keep": 9}}}},
            {"a": {"b": {"c": {"d": 2}}}},
        )
        assert out["a"]["b"]["c"] == {"d": 2, "keep": 9}

    def test_empty_patch_changes_nothing(self):
        assert self._merged({"stall": {"a": 1}}, {}) == {"stall": {"a": 1}}

    def test_a_boolean_replaces_rather_than_deleting(self):
        """`False` is not `null`. Python's falsiness is the trap this pins."""
        out = self._merged({"pattern_analysis_overdue": True},
                           {"pattern_analysis_overdue": False})
        assert out["pattern_analysis_overdue"] is False

    def test_version_is_a_prefixed_hex_digest_that_moves_with_the_bytes(self):
        assert version_of(b'{"a":1}') == version_of(b'{"a":1}')
        assert version_of(b'{"a":1}') != version_of(b'{"a":2}')
        assert version_of(b"{}").startswith("sha256:")
        assert len(version_of(b"{}")) == len("sha256:") + 64


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

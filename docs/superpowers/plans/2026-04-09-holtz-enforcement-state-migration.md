# Enforcement State Migration to Daemon Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move enforcement cache out of the filesystem into sahjhan daemon memory, closing the dynamic path construction bypass (issue #46).

**Architecture:** Replace filesystem reads/writes of `enforcement-cache.json` with daemon socket calls (`enforcement_read`, `enforcement_write`, `enforcement_update`). A mock daemon test fixture handles all test scenarios. Callers of `read_cache`/`write_cache` don't change — the functions keep the same signatures.

**Tech Stack:** Python 3.11+, Unix domain sockets, pytest, base64-encoded JSON over socket wire protocol.

**Specs:** `docs/superpowers/specs/2026-04-09-holtz-enforcement-state-migration-spec.md`, `docs/superpowers/specs/2026-04-09-sahjhan-enforcement-state-daemon-spec.md`

---

### Task 1: Create mock enforcement daemon test fixture

**Files:**
- Create: `tests/mock_enforcement_daemon.py`
- Modify: `tests/conftest.py`

This fixture is required before any other task — all subsequent tests depend on it.

- [ ] **Step 1: Write the mock daemon module**

Create `tests/mock_enforcement_daemon.py`:

```python
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
            except socket.timeout:
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
            raw["last_refresh"] = datetime.now(timezone.utc).isoformat()
            self.state = raw
            return {"ok": True}

        if op == "enforcement_update":
            if self.state is None:
                return {"ok": False, "error": "not_found", "message": "no enforcement state to update"}
            patch = json.loads(base64.b64decode(request["patch"]))
            self.state.update(patch)
            self.state["last_refresh"] = datetime.now(timezone.utc).isoformat()
            encoded = base64.b64encode(json.dumps(self.state).encode()).decode()
            return {"ok": True, "data": encoded}

        return {"ok": False, "error": "unknown_op", "message": f"unknown op: {op}"}
```

- [ ] **Step 2: Add the pytest fixture to conftest.py**

Add to `tests/conftest.py`:

```python
from mock_enforcement_daemon import MockEnforcementDaemon


@pytest.fixture
def mock_daemon(tmp_path):
    """Start a mock enforcement daemon with socket at the standard path.

    The daemon listens at tmp_path/docs/holtz/.sahjhan/daemon.sock,
    matching _get_daemon_socket_path(cwd=str(tmp_path)).
    """
    socket_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
    socket_dir.mkdir(parents=True, exist_ok=True)
    socket_path = socket_dir / "daemon.sock"
    daemon = MockEnforcementDaemon(socket_path)
    daemon.start()
    yield daemon
    daemon.stop()
```

- [ ] **Step 3: Write a self-test for the fixture**

Add to `tests/mock_enforcement_daemon.py` at the bottom (or as a separate test — keep it in the same file for co-location):

```python
def test_mock_daemon_round_trip(tmp_path):
    """Verify the mock daemon handles enforcement ops correctly."""
    import socket as sock_mod

    socket_path = tmp_path / "daemon.sock"
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
```

- [ ] **Step 4: Run tests to verify**

Run: `python -m pytest tests/mock_enforcement_daemon.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/mock_enforcement_daemon.py tests/conftest.py
git commit -m "test: add MockEnforcementDaemon fixture for daemon-backed cache tests"
```

---

### Task 2: Rewrite `_protocol_cache.py` core functions

**Files:**
- Modify: `enforcement/hooks/_protocol_cache.py:1-82` (read_cache, write_cache, imports, constants)
- Test: `tests/test_enforcement_cache_daemon.py` (new)

The old filesystem `read_cache`/`write_cache` are replaced with daemon socket calls. A new `update_cache` function is added for atomic read-modify-write.

- [ ] **Step 1: Write failing tests for daemon-backed cache functions**

Create `tests/test_enforcement_cache_daemon.py`:

```python
"""Tests for daemon-backed enforcement cache (read/write/update)."""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


class TestReadCacheDaemon:
    """read_cache returns cache from daemon or None on failure."""

    def test_returns_none_when_daemon_unreachable(self, tmp_path):
        """No daemon running → returns None (fail-open)."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None

    def test_returns_dict_when_daemon_has_state(self, tmp_path, mock_daemon):
        """Daemon has enforcement state → returns parsed dict."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "fix_loop"
        assert loaded["stall"] == 3

    def test_returns_none_when_daemon_has_no_state(self, tmp_path, mock_daemon):
        """Daemon running but no enforcement state written yet → returns None."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None


class TestWriteCacheDaemon:
    """write_cache sends state to daemon."""

    def test_round_trip_write_read(self, tmp_path, mock_daemon):
        """Write then read returns same data."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "pattern_analysis"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)

        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "pattern_analysis"
        assert loaded["unregistered_commits"] == ["abc1234"]
        assert loaded["last_refresh"] != ""  # daemon sets this

    def test_raises_when_daemon_unreachable(self, tmp_path):
        """No daemon running → raises RuntimeError."""
        from _protocol_cache import empty_cache, write_cache
        with pytest.raises(RuntimeError):
            write_cache(str(tmp_path), empty_cache())


class TestUpdateCacheDaemon:
    """update_cache atomically patches state in daemon."""

    def test_patches_single_field(self, tmp_path, mock_daemon):
        """Patch stall counter, other fields preserved."""
        from _protocol_cache import empty_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 0
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"stall": 5})
        assert updated["stall"] == 5
        assert updated["state"] == "fix_loop"  # preserved

    def test_patches_list_field(self, tmp_path, mock_daemon):
        """Patch unregistered_commits with full replacement."""
        from _protocol_cache import empty_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["aaa"]
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"unregistered_commits": ["aaa", "bbb"]})
        assert updated["unregistered_commits"] == ["aaa", "bbb"]

    def test_raises_when_no_state(self, tmp_path, mock_daemon):
        """No enforcement state in daemon → raises RuntimeError."""
        from _protocol_cache import update_cache
        with pytest.raises(RuntimeError):
            update_cache(str(tmp_path), {"stall": 1})

    def test_raises_when_daemon_unreachable(self, tmp_path):
        """No daemon running → raises RuntimeError."""
        from _protocol_cache import update_cache
        with pytest.raises(RuntimeError):
            update_cache(str(tmp_path), {"stall": 1})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_enforcement_cache_daemon.py -v`
Expected: FAIL — `read_cache` still reads from filesystem, `update_cache` doesn't exist.

- [ ] **Step 3: Implement daemon-backed cache functions**

Edit `enforcement/hooks/_protocol_cache.py`. Replace the imports section, `_cache_path`, `read_cache`, and `write_cache`. Add `update_cache`.

New imports (replace lines 1-11):

```python
"""Shared protocol enforcement cache — read/write state via daemon, detect commands, compute obligations.

Used by commit_gate.py (PreToolUse) and protocol_tracker.py (PostToolUse).
"""
from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from typing import Any
```

Delete `CACHE_FILENAME` (line 13) and `_cache_path` (lines 17-18).

Replace `read_cache` (lines 55-63):

```python
def read_cache(cwd: str) -> dict[str, Any] | None:
    """Read enforcement state from the sahjhan daemon.

    Returns None if the daemon is unreachable or has no enforcement state
    (fail-open, same behavior as the old "file not found" path).
    """
    try:
        from _common import _daemon_request, _get_daemon_socket_path
        sock_path = _get_daemon_socket_path(cwd)
        resp = _daemon_request(sock_path, {"op": "enforcement_read"})
        return json.loads(base64.b64decode(resp["data"]))
    except Exception:
        return None
```

Replace `write_cache` (lines 66-81):

```python
def write_cache(cwd: str, cache: dict[str, Any]) -> None:
    """Write enforcement state to the sahjhan daemon.

    The daemon sets last_refresh to the current UTC timestamp.
    Raises RuntimeError if the daemon is unreachable.
    """
    from _common import _daemon_request, _get_daemon_socket_path
    sock_path = _get_daemon_socket_path(cwd)
    data = base64.b64encode(json.dumps(cache).encode()).decode()
    _daemon_request(sock_path, {"op": "enforcement_write", "data": data})
```

Add `update_cache` after `write_cache`:

```python
def update_cache(cwd: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Atomically patch enforcement state in the sahjhan daemon.

    Sends a partial dict of fields to merge into current state.
    Returns the full state after merge.
    Raises RuntimeError if daemon unreachable or no state exists.
    """
    from _common import _daemon_request, _get_daemon_socket_path
    sock_path = _get_daemon_socket_path(cwd)
    data = base64.b64encode(json.dumps(patch).encode()).decode()
    resp = _daemon_request(sock_path, {"op": "enforcement_update", "patch": data})
    return json.loads(base64.b64decode(resp["data"]))
```

Also delete the `_ENFORCEMENT_FRESHNESS_MINUTES` constant from line 14 — no wait, that's still used by `is_enforcement_fresh`. Keep it.

- [ ] **Step 4: Run new tests to verify they pass**

Run: `python -m pytest tests/test_enforcement_cache_daemon.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_protocol_cache.py tests/test_enforcement_cache_daemon.py
git commit -m "feat: replace filesystem enforcement cache with daemon socket calls

read_cache/write_cache now communicate with the sahjhan daemon via
enforcement_read/enforcement_write ops. New update_cache function
provides atomic read-modify-write for stall/commit updates.

Closes #46 (dynamic path construction bypass)."
```

---

### Task 3: Update `protocol_tracker.py` to use `update_cache`

**Files:**
- Modify: `enforcement/hooks/protocol_tracker.py:18-26,128-169`

The three `write_cache` call sites where the tracker does read-modify-write become `update_cache` calls where appropriate.

- [ ] **Step 1: Write failing test for stall increment via update_cache**

Add to `tests/test_enforcement_cache_daemon.py`:

```python
class TestProtocolTrackerUpdatePatterns:
    """Verify protocol_tracker write patterns work with daemon cache."""

    def test_stall_increment(self, tmp_path, mock_daemon):
        """Stall counter increments atomically via update_cache."""
        from _protocol_cache import empty_cache, read_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"stall": 4})
        assert updated["stall"] == 4

        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["stall"] == 4

    def test_commit_registration(self, tmp_path, mock_daemon):
        """Commit hash appended and stall reset via update_cache."""
        from _protocol_cache import empty_cache, read_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
        cache["unregistered_commits"] = ["aaa"]
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {
            "unregistered_commits": ["aaa", "bbb"],
            "stall": 0,
        })
        assert updated["unregistered_commits"] == ["aaa", "bbb"]
        assert updated["stall"] == 0

    def test_sleep_double_stall(self, tmp_path, mock_daemon):
        """Sleep command gets double stall penalty via update_cache."""
        from _protocol_cache import empty_cache, update_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 3
        write_cache(str(tmp_path), cache)

        updated = update_cache(str(tmp_path), {"stall": 5})
        assert updated["stall"] == 5
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_enforcement_cache_daemon.py::TestProtocolTrackerUpdatePatterns -v`
Expected: PASS (these are testing the cache functions which already work from Task 2).

- [ ] **Step 3: Update protocol_tracker.py imports**

Edit `enforcement/hooks/protocol_tracker.py` lines 18-26 — add `update_cache` to imports:

```python
from _protocol_cache import (  # noqa: E402
    empty_cache,
    is_enforcement_fresh,
    is_git_commit,
    is_sahjhan_cmd,
    parse_status_text,
    read_cache,
    update_cache,
    write_cache,
)
```

- [ ] **Step 4: Update git commit handler (lines 155-160)**

Replace:
```python
    if is_git_commit(cmd) and exit_code == 0:
        commit_hash = _parse_commit_hash(output)
        cache.setdefault("unregistered_commits", []).append(commit_hash)
        cache["stall"] = 0
        write_cache(cwd, cache)
        exit_ok()
```

With:
```python
    if is_git_commit(cmd) and exit_code == 0:
        commit_hash = _parse_commit_hash(output)
        commits = list(cache.get("unregistered_commits", []))
        commits.append(commit_hash)
        update_cache(cwd, {"unregistered_commits": commits, "stall": 0})
        exit_ok()
```

- [ ] **Step 5: Update stall increment handlers (lines 162-168)**

Replace:
```python
    # Test/lint/type-check commands are legitimate TDD activity — don't count as stalling
    if _is_sleep_cmd(cmd):
        # Sleep to game timing gates gets double stall penalty
        cache["stall"] = cache.get("stall", 0) + 2
    elif not _is_tdd_cmd(cmd):
        cache["stall"] = cache.get("stall", 0) + 1
    write_cache(cwd, cache)
    exit_ok()
```

With:
```python
    # Test/lint/type-check commands are legitimate TDD activity — don't count as stalling
    if _is_sleep_cmd(cmd):
        # Sleep to game timing gates gets double stall penalty
        update_cache(cwd, {"stall": cache.get("stall", 0) + 2})
    elif not _is_tdd_cmd(cmd):
        update_cache(cwd, {"stall": cache.get("stall", 0) + 1})
    exit_ok()
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_enforcement_cache_daemon.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/protocol_tracker.py
git commit -m "fix(enforcement): use update_cache for atomic stall/commit updates in protocol_tracker"
```

---

### Task 4: Update existing tests to use mock daemon fixture

**Files:**
- Modify: `tests/test_protocol_enforcement.py`
- Modify: `tests/test_sahjhan_integration.py`
- Modify: `tests/test_sleep_detection.py`

Existing tests that call `write_cache(str(tmp_path), cache)` to set up state need the `mock_daemon` fixture so the daemon-backed `write_cache` has somewhere to connect. The function calls themselves don't change — only the fixture parameter is added.

**Important context:** Tests that run hooks via `subprocess.run` (e.g., `run_enforcement_hook`) run the hook in a child process. That child process will call `read_cache` which connects to the daemon socket at `tmp_path/docs/holtz/.sahjhan/daemon.sock`. The mock daemon runs in a thread in the test process, and the child process connects to the same Unix socket — this works because Unix sockets are filesystem-addressable.

- [ ] **Step 1: Update `tests/test_protocol_enforcement.py`**

Every test method that calls `write_cache` or `read_cache` needs `mock_daemon` in its signature. The pattern is mechanical:

For `TestProtocolCache`:
- `test_read_cache_missing_file`: Rename to `test_read_cache_daemon_unreachable`. No fixture needed (tests fail-open when daemon absent).
- `test_write_and_read_cache`: Add `mock_daemon` parameter.

For `TestPreToolHookFailClosed`:
- `test_blocks_when_binary_unavailable_and_fresh`: Add `mock_daemon` parameter.
- `test_allows_when_binary_unavailable_and_stale`: Add `mock_daemon` parameter.

For every test class that calls `write_cache(str(tmp_path), cache)`: add `mock_daemon` to the method signature. The `mock_daemon` fixture depends on `tmp_path` internally, and since the test also uses `tmp_path`, pytest reuses the same `tmp_path` instance — the socket path matches.

Example change (repeated for each affected method):

Before:
```python
def test_blocks_when_binary_unavailable_and_fresh(self, tmp_path):
```

After:
```python
def test_blocks_when_binary_unavailable_and_fresh(self, tmp_path, mock_daemon):
```

Apply this to ALL test methods in `test_protocol_enforcement.py` that call `write_cache` or `read_cache` (except `test_read_cache_missing_file` which tests the no-daemon path).

Also rename `test_read_cache_missing_file` to `test_read_cache_daemon_unreachable` and update its docstring:

```python
def test_read_cache_daemon_unreachable(self, tmp_path):
    """Returns None when daemon is unreachable (fail-open)."""
    from _protocol_cache import read_cache
    assert read_cache(str(tmp_path)) is None
```

- [ ] **Step 2: Update `tests/test_sahjhan_integration.py`**

Same pattern: add `mock_daemon` parameter to every test method that calls `write_cache`. The methods are in classes like `TestBootstrapReadGuard`, `TestCommitGate`, etc.

- [ ] **Step 3: Update `tests/test_sleep_detection.py`**

This file patches `read_cache` and `write_cache` at the module level using `unittest.mock.patch`. Since the patched functions override the daemon calls, the mock daemon is NOT needed here. However, the `_protocol_cache` stub (line 44) needs `update_cache` added to its attribute list:

```python
stubs: dict[str, list[str]] = {
    "_protocol_cache": ["empty_cache", "is_git_commit", "is_sahjhan_cmd",
                        "parse_status_text", "read_cache", "update_cache", "write_cache"],
    "_resolve": ["sahjhan_binary", "ensure_sahjhan"],
}
```

Also update the protocol_tracker test methods that check `write_cache` was called — they now need to check for `update_cache` calls instead for the stall/commit paths.

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest tests/test_protocol_enforcement.py tests/test_sahjhan_integration.py tests/test_sleep_detection.py tests/test_enforcement_cache_daemon.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_protocol_enforcement.py tests/test_sahjhan_integration.py tests/test_sleep_detection.py
git commit -m "test: migrate existing tests to mock enforcement daemon fixture"
```

---

### Task 5: Update remaining test files and run full suite

**Files:**
- Modify: any remaining test files that import `write_cache` or `read_cache` from `_protocol_cache`

- [ ] **Step 1: Search for remaining test files using write_cache/read_cache**

Run: `grep -rn 'write_cache\|read_cache' tests/ --include='*.py' -l`

Check each file not already updated in Task 4. Add `mock_daemon` fixture to affected test methods.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 3: Run lint and type check**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: PASS

- [ ] **Step 4: Commit any remaining changes**

```bash
git add -u
git commit -m "test: fix remaining test files for daemon-backed enforcement cache"
```

---

### Task 6: Regression test for issue #46 bypass

**Files:**
- Create: `tests/test_issue46_bypass_regression.py`

Verify the original attack vector (dynamic path construction to overwrite enforcement state) no longer works.

- [ ] **Step 1: Write the regression test**

Create `tests/test_issue46_bypass_regression.py`:

```python
"""Regression test for issue #46: dynamic path construction bypass.

Verifies that enforcement state cannot be modified by writing to the
filesystem, because the state now lives in daemon memory.
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


class TestIssue46Regression:
    """Enforcement state survives filesystem tampering."""

    def test_filesystem_write_does_not_affect_daemon_state(self, tmp_path, mock_daemon):
        """Writing enforcement-cache.json on disk does not change daemon state.

        This is the exact attack from issue #46: an agent uses pathlib to
        construct the path dynamically and overwrites the cache file. With
        daemon-backed state, the file is irrelevant.
        """
        from _protocol_cache import empty_cache, read_cache, write_cache

        # Seed legitimate state in daemon
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["active"] = True
        write_cache(str(tmp_path), cache)

        # Simulate the attack: write a forged cache file to disk
        cache_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        cache_dir.mkdir(parents=True, exist_ok=True)
        forged = {"active": False, "state": "finalized", "stall": 0}
        (cache_dir / "enforcement-cache.json").write_text(json.dumps(forged))

        # Read from daemon — should still show fix_loop, not finalized
        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "fix_loop"
        assert loaded["active"] is True

    def test_state_inaccessible_without_daemon(self, tmp_path):
        """Without a running daemon, there is no enforcement state to read.

        Even if a cache file exists on disk, read_cache returns None
        because it only reads from the daemon.
        """
        from _protocol_cache import read_cache

        # Put a file on disk (simulating leftover from old version)
        cache_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        cache_dir.mkdir(parents=True, exist_ok=True)
        old_cache = {"active": True, "state": "fix_loop"}
        (cache_dir / "enforcement-cache.json").write_text(json.dumps(old_cache))

        # read_cache ignores the file — daemon is not running
        assert read_cache(str(tmp_path)) is None
```

- [ ] **Step 2: Run the regression test**

Run: `python -m pytest tests/test_issue46_bypass_regression.py -v`
Expected: PASS

- [ ] **Step 3: Run full suite with coverage**

Run: `python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks --cov-report=term-missing --cov-fail-under=60`
Expected: PASS with coverage >= 60%

- [ ] **Step 4: Commit**

```bash
git add tests/test_issue46_bypass_regression.py
git commit -m "test: add regression test for issue #46 dynamic path bypass"
```

---

### Task 7: Final cleanup and verification

**Files:**
- Modify: `enforcement/hooks/_protocol_cache.py` (if any dead code remains)

- [ ] **Step 1: Verify no dead code in _protocol_cache.py**

Check that `CACHE_FILENAME`, `_cache_path`, and the old `tempfile`-based write logic are all removed. Run:

```bash
grep -n 'CACHE_FILENAME\|_cache_path\|tempfile\|os.replace\|os.fdopen' enforcement/hooks/_protocol_cache.py
```

Expected: no matches. If any remain, delete them.

- [ ] **Step 2: Run full lint and type check**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 4: Commit any cleanup**

```bash
git add -u
git commit -m "chore: remove dead filesystem cache code from _protocol_cache.py"
```

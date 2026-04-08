# Issue #43: Stop Hook Daemon Cleanup Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the stop hook from killing the sahjhan daemon when audit state is `awaiting_clear`, so audits can resume after `/clear`.

**Architecture:** Add a second state set `_DAEMON_CLEANUP_STATES` that excludes `awaiting_clear`. Guard both daemon-cleanup call sites in `stop_hook.py` with this set. Add tests verifying the daemon is not killed in `awaiting_clear`.

**Tech Stack:** Python, pytest

**Spec:** `docs/superpowers/specs/2026-04-07-issue-43-stop-hook-daemon-cleanup-design.md`

---

### Task 1: Add tests for awaiting_clear daemon protection

**Files:**
- Modify: `tests/test_protocol_enforcement.py:1048-1061` (existing `test_allows_stop_in_awaiting_clear_state`)
- Modify: `tests/test_protocol_enforcement.py:1064-1082` (existing `TestStopHookDaemonCleanup` class)

These tests import `stop_hook` as a module and use `unittest.mock.patch` to verify `_try_stop_daemon` is/isn't called. The existing subprocess-based tests can't observe daemon cleanup because `ensure_sahjhan()` returns `None` in test (no binary). The unit tests complement the existing integration tests.

- [ ] **Step 1: Write failing test — awaiting_clear must not trigger daemon cleanup**

Add a new test class after `TestStopHookDaemonCleanup` (after line 1082) in `tests/test_protocol_enforcement.py`:

```python
class TestStopHookDaemonCleanupGating:
    """Issue #43: awaiting_clear allows stop but must NOT kill daemon."""

    def test_awaiting_clear_does_not_kill_daemon(self, tmp_path):
        """awaiting_clear: stop allowed, daemon NOT killed (key needed for resume)."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "awaiting_clear"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        # Patch _try_stop_daemon at module level to track calls
        import stop_hook
        with patch.object(stop_hook, "_try_stop_daemon") as mock_stop:
            event = {"cwd": str(tmp_path)}
            code, output, _ = run_enforcement_hook("stop_hook.py", event)

        assert code == 0
        assert output == {}  # allow
        mock_stop.assert_not_called()

    def test_idle_still_kills_daemon(self, tmp_path):
        """idle: stop allowed AND daemon killed (no audit to resume)."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "idle"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        import stop_hook
        with patch.object(stop_hook, "_try_stop_daemon") as mock_stop:
            event = {"cwd": str(tmp_path)}
            code, output, _ = run_enforcement_hook("stop_hook.py", event)

        assert code == 0
        assert output == {}  # allow
        mock_stop.assert_called_once()

    def test_stale_awaiting_clear_does_not_kill_daemon(self, tmp_path):
        """Stale awaiting_clear: warn but do NOT kill daemon."""
        from unittest.mock import patch

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "awaiting_clear"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        import stop_hook
        with patch.object(stop_hook, "_try_stop_daemon") as mock_stop:
            event = {"cwd": str(tmp_path)}
            code, output, _ = run_enforcement_hook("stop_hook.py", event)

        assert code == 0
        # awaiting_clear is in _STOP_ALLOWED_STATES, so it hits that branch
        # before the staleness check. It should allow stop without killing daemon.
        mock_stop.assert_not_called()
```

**Note on mock approach:** `run_enforcement_hook` runs the hook as a subprocess, so `patch.object` on the imported module won't intercept the subprocess call. These tests will need to call `stop_hook.main()` directly instead. Revising:

```python
class TestStopHookDaemonCleanupGating:
    """Issue #43: awaiting_clear allows stop but must NOT kill daemon."""

    def test_awaiting_clear_does_not_kill_daemon(self, tmp_path):
        """awaiting_clear: stop allowed, daemon NOT killed (key needed for resume)."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        import pytest
        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "awaiting_clear"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        import stop_hook
        with (
            patch.object(stop_hook, "_try_stop_daemon") as mock_stop,
            patch.object(stop_hook, "read_event", return_value={"cwd": str(tmp_path)}),
            patch.object(stop_hook, "_has_active_audit", return_value=True),
        ):
            with pytest.raises(SystemExit) as exc_info:
                stop_hook.main()
            assert exc_info.value.code == 0
        mock_stop.assert_not_called()

    def test_idle_still_kills_daemon(self, tmp_path):
        """idle: stop allowed AND daemon killed (no audit to resume)."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        import pytest
        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "idle"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

        import stop_hook
        with (
            patch.object(stop_hook, "_try_stop_daemon") as mock_stop,
            patch.object(stop_hook, "read_event", return_value={"cwd": str(tmp_path)}),
            patch.object(stop_hook, "_has_active_audit", return_value=True),
        ):
            with pytest.raises(SystemExit) as exc_info:
                stop_hook.main()
            assert exc_info.value.code == 0
        mock_stop.assert_called_once()

    def test_stale_awaiting_clear_does_not_kill_daemon(self, tmp_path):
        """Stale awaiting_clear: still allows stop, does NOT kill daemon."""
        from unittest.mock import patch

        import pytest
        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "awaiting_clear"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        import stop_hook
        with (
            patch.object(stop_hook, "_try_stop_daemon") as mock_stop,
            patch.object(stop_hook, "read_event", return_value={"cwd": str(tmp_path)}),
            patch.object(stop_hook, "_has_active_audit", return_value=True),
        ):
            with pytest.raises(SystemExit) as exc_info:
                stop_hook.main()
            assert exc_info.value.code == 0
        # awaiting_clear is in _STOP_ALLOWED_STATES — hits that path before staleness
        mock_stop.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookDaemonCleanupGating -v`

Expected: `test_awaiting_clear_does_not_kill_daemon` FAILS (mock IS called because current code calls `_try_stop_daemon` for all allowed states). `test_idle_still_kills_daemon` PASSES. `test_stale_awaiting_clear_does_not_kill_daemon` FAILS (same reason as first).

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_protocol_enforcement.py
git commit -m "test(enforcement): add failing tests for issue #43 daemon cleanup gating"
```

---

### Task 2: Implement the fix in stop_hook.py

**Files:**
- Modify: `enforcement/hooks/stop_hook.py:34` (add `_DAEMON_CLEANUP_STATES`)
- Modify: `enforcement/hooks/stop_hook.py:86-88` (guard allowed-states path)
- Modify: `enforcement/hooks/stop_hook.py:91-97` (guard stale-enforcement path)

- [ ] **Step 1: Add `_DAEMON_CLEANUP_STATES` and comment**

In `enforcement/hooks/stop_hook.py`, replace line 34:

```python
_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
```

With:

```python
# Two sets because "allowed to stop" ≠ "safe to kill daemon".
# awaiting_clear allows stop (the turn is done) but the daemon must
# survive — it holds the HMAC session key for the resuming session.
# When adding states, decide: does the audit resume after this? If yes,
# put it in _STOP_ALLOWED only. If the audit is over, put it in both.
_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
_DAEMON_CLEANUP_STATES = {"idle", "finalized", ""}
```

- [ ] **Step 2: Guard the allowed-states daemon cleanup (lines 86-88)**

Replace:

```python
    if current_state in _STOP_ALLOWED_STATES:
        _try_stop_daemon(cwd)
        exit_stop_allow()
```

With:

```python
    if current_state in _STOP_ALLOWED_STATES:
        if current_state in _DAEMON_CLEANUP_STATES:
            _try_stop_daemon(cwd)
        exit_stop_allow()
```

- [ ] **Step 3: Guard the stale-enforcement daemon cleanup (lines 91-92)**

Replace:

```python
    if not is_enforcement_fresh(cache):
        _try_stop_daemon(cwd)
        exit_stop_warn(
```

With:

```python
    if not is_enforcement_fresh(cache):
        if current_state in _DAEMON_CLEANUP_STATES:
            _try_stop_daemon(cwd)
        exit_stop_warn(
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_protocol_enforcement.py -v`

Expected: ALL pass, including the new `TestStopHookDaemonCleanupGating` tests.

- [ ] **Step 5: Run linter and type checker**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`

Expected: Clean.

- [ ] **Step 6: Commit the fix**

```bash
git add enforcement/hooks/stop_hook.py
git commit -m "fix(enforcement): don't kill daemon in awaiting_clear state

Closes #43. The stop hook conflated 'allowed to stop the turn' with
'safe to kill the daemon'. awaiting_clear needs the daemon alive for
the resuming session after /clear."
```

---

### Task 3: Verify existing tests still pass

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest -v`

Expected: All tests pass. No regressions.

- [ ] **Step 2: Run linter and type checker**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`

Expected: Clean.

# Issue #39: Dead Daemon Bypass Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the enforcement bypass caused by a dead daemon silently disabling all protocol gates during active audits.

**Architecture:** Add a shared `exit_enforcement_error()` utility to `enforcement/hooks/_common.py` that replaces `exit_ok()` at every daemon-failure fallback path. During active audits with fresh enforcement, failures block (PreToolUse) or warn (PostToolUse). Fix the bootstrap path protection gap for MANAGED_DATA. Harden daemon lifecycle to block on failed restart.

**Tech Stack:** Python 3.10+, pytest, subprocess hooks, Claude Code hook protocol (JSON stdout)

**Spec:** `docs/superpowers/specs/2026-04-05-issue-39-dead-daemon-bypass-design.md`

---

### Task 1: Add `exit_enforcement_error()` to enforcement `_common.py`

**Files:**
- Modify: `enforcement/hooks/_common.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write failing tests for `exit_enforcement_error`**

Add a new test class at the end of `tests/test_protocol_enforcement.py`:

```python
class TestExitEnforcementError:
    """Tests for exit_enforcement_error() shared utility."""

    def test_blocks_pretooluse_during_active_fresh_audit(self, tmp_path, capsys):
        """Active audit + fresh enforcement + PreToolUse → block with reason."""
        import json
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        from _common import exit_enforcement_error
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is False
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "ENFORCEMENT DEGRADED" in reason
        assert "daemon unreachable" in reason

    def test_warns_posttooluse_during_active_fresh_audit(self, tmp_path, capsys):
        """Active audit + fresh enforcement + PostToolUse → warn."""
        import json
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        from _common import exit_enforcement_error
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PostToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True
        assert "ENFORCEMENT DEGRADED" in output["additionalContext"]

    def test_allows_when_no_active_audit(self, tmp_path, capsys):
        """No .sahjhan dir → allow (fail-open)."""
        import json

        from _common import exit_enforcement_error
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True

    def test_allows_when_stale_enforcement(self, tmp_path, capsys):
        """Active audit but stale enforcement → allow (fail-open)."""
        import json

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        from _common import exit_enforcement_error
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True

    def test_allows_when_sahjhan_dir_but_no_cache(self, tmp_path, capsys):
        """Data dir exists but no cache file → allow (fail-open)."""
        import json

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        # No cache file written

        from _common import exit_enforcement_error
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            exit_enforcement_error(str(tmp_path), "daemon unreachable", "PreToolUse")

        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["continue"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestExitEnforcementError -v`
Expected: FAIL — `ImportError: cannot import name 'exit_enforcement_error' from '_common'`

- [ ] **Step 3: Implement `exit_enforcement_error` in `enforcement/hooks/_common.py`**

Add these imports near the top of the file (after the existing imports):

```python
from _protocol_cache import is_enforcement_fresh, read_cache
```

Add this function after the `write_active_run_marker` function (after line 128):

```python
def exit_enforcement_error(
    cwd: str,
    reason: str,
    hook_type: str = "PreToolUse",
) -> None:
    """Block if active audit + fresh enforcement, else allow.

    Replaces exit_ok() at daemon-failure fallback paths. During an active,
    fresh audit, daemon failures are blocks (PreToolUse) or warnings
    (PostToolUse). Outside audits or with stale enforcement, fail-open
    as before.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if os.path.isdir(data_dir):
        cache = read_cache(cwd)
        if is_enforcement_fresh(cache):
            if hook_type == "PreToolUse":
                exit_block(f"ENFORCEMENT DEGRADED: {reason}")
            else:
                exit_warn(f"ENFORCEMENT DEGRADED: {reason}")
    # No active audit or stale enforcement — fail-open
    if hook_type == "PreToolUse":
        exit_ok("PreToolUse")
    else:
        exit_ok()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestExitEnforcementError -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest && ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_common.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): add exit_enforcement_error() shared utility (#39)

Fail-closed during active audits when daemon is unreachable.
Blocks on PreToolUse, warns on PostToolUse. Fail-open when no
active audit or stale enforcement."
```

---

### Task 2: Fix bootstrap MANAGED_DATA path protection gap (P2)

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py:276-289`
- Test: `tests/test_bootstrap_read_guard.py`

- [ ] **Step 1: Write failing tests for MANAGED_DATA Write/Edit blocking**

Add a new test class at the end of `tests/test_bootstrap_read_guard.py`:

```python
class TestManagedDataWriteProtection:
    """Issue #39 P2: Write/Edit to .sahjhan/ data dir must be blocked."""

    def test_write_to_enforcement_cache_blocked(self):
        """Write tool targeting enforcement-cache.json must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Use a cwd where docs/holtz/.sahjhan/ would resolve
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/enforcement-cache.json"},
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "sahjhan data directory" in output["hookSpecificOutput"]["permissionDecisionReason"].lower() or \
               "cannot be modified" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_edit_to_active_run_marker_blocked(self):
        """Edit tool targeting active-run marker must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "docs/holtz/.sahjhan/active-run",
                "old_string": "run-1",
                "new_string": "run-999",
            },
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_write_to_daemon_pid_blocked(self):
        """Write tool targeting daemon.pid must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/daemon.pid"},
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_write_outside_sahjhan_dir_allowed(self):
        """Write tool targeting a non-protected path is allowed."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/some-notes.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bootstrap_read_guard.py::TestManagedDataWriteProtection -v`
Expected: FAIL — the block assertions fail because MANAGED_DATA isn't checked for Write/Edit

- [ ] **Step 3: Add MANAGED_DATA to Write/Edit path check in `_sahjhan_bootstrap.py`**

In `enforcement/hooks/_sahjhan_bootstrap.py`, after the `PROTECTED` loop (after line 287, before `_allow()`), add the `MANAGED_DATA` loop. The key difference is MANAGED_DATA paths are relative to `cwd`, not `_PLUGIN_ROOT`:

```python
    # MANAGED_DATA paths are relative to cwd (not _PLUGIN_ROOT)
    for p in MANAGED_DATA:
        full = os.path.realpath(os.path.join(cwd, p))
        if resolved == full or resolved.startswith(full + os.sep):
            _block(
                f"BLOCKED: {path} is in the Sahjhan data directory. "
                "This path cannot be modified during an audit session."
            )
            return
```

This goes between line 287 (`return` after PROTECTED block) and line 289 (`_allow()`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bootstrap_read_guard.py::TestManagedDataWriteProtection -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest && ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py tests/test_bootstrap_read_guard.py
git commit -m "fix(enforcement): block Write/Edit to MANAGED_DATA paths (#39)

_sahjhan_bootstrap.py only checked PROTECTED paths for Write/Edit tools.
MANAGED_DATA (.sahjhan/ dir) was only protected from Bash writes.
This allowed the agent to overwrite enforcement-cache.json directly
via Write tool and escape the stop hook."
```

---

### Task 3: Harden daemon lifecycle to block on failed restart (P3/P6)

**Files:**
- Modify: `enforcement/hooks/_daemon_lifecycle.py`
- Test: `tests/test_daemon_lifecycle.py`

- [ ] **Step 1: Write failing tests for daemon lifecycle blocking**

Add new test classes at the end of `tests/test_daemon_lifecycle.py`:

```python
class TestDaemonLifecycleBlocksDuringActiveAudit:
    """Issue #39: Dead daemon during active+fresh audit must block, not allow."""

    def test_blocks_when_restart_fails_and_fresh(self, tmp_path):
        """Daemon dead + restart fails + fresh enforcement → block."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")  # dead PID

        # Write a fresh cache so enforcement is active
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        # Should block, not allow
        assert output.get("continue") is False
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "ENFORCEMENT DEGRADED" in reason

    def test_allows_when_restart_fails_and_stale(self, tmp_path):
        """Daemon dead + restart fails + stale enforcement → allow (abandoned audit)."""
        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")  # dead PID

        # Write a stale cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_allows_when_no_cache_file(self, tmp_path):
        """Daemon dead + no cache file → allow (no enforcement state to protect)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")  # dead PID
        # No cache file

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True


class TestDaemonStartVerification:
    """Issue #39 P3: Verify daemon is actually alive after start."""

    def test_still_allows_when_daemon_alive(self, tmp_path):
        """Daemon PID is alive → allow as before."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # Use our own PID — guaranteed alive
        (sahjhan_dir / "daemon.pid").write_text(f"{os.getpid()}\n")

        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_daemon_lifecycle.py::TestDaemonLifecycleBlocksDuringActiveAudit -v`
Expected: FAIL — `test_blocks_when_restart_fails_and_fresh` fails because the hook currently always allows

- [ ] **Step 3: Update the existing `test_never_blocks_on_failure` test**

The existing test `TestDaemonHealthCheck::test_never_blocks_on_failure` asserts the old behavior (always allow). Update it to reflect the new behavior — it should still allow when enforcement is stale (no cache written = no freshness):

```python
    def test_allows_on_failure_when_no_fresh_enforcement(self, tmp_path):
        """Daemon start fails + no fresh enforcement → allow (fail-open)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 4: Implement daemon lifecycle hardening in `_daemon_lifecycle.py`**

Add import for `exit_enforcement_error` at the top (alongside existing `_common` imports):

```python
from _common import (
    _active_ledger,
    exit_enforcement_error,
    exit_ok,
    read_event,
    write_active_run_marker,
)
```

Update `_start_daemon()` to verify PID after start (replace the return statement inside the try block):

```python
def _start_daemon(cwd: str) -> bool:
    """Attempt to start the sahjhan daemon. Returns True on success."""
    binary = ensure_sahjhan()
    if binary is None:
        return False
    try:
        from _common import resolve_config_dir
        config_dir, _ = resolve_config_dir(cwd)
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "start"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            # Verify daemon is actually alive after claiming success
            pid = _daemon_pid(cwd)
            return pid is not None and _is_process_alive(pid)
        return False
    except (OSError, subprocess.TimeoutExpired):
        return False
```

Update `main()` — replace lines 110-112 with:

```python
    # Daemon is down or missing — attempt start
    started = _start_daemon(cwd)
    if not started:
        # Double-check: daemon still dead after restart attempt?
        pid = _daemon_pid(cwd)
        if pid is None or not _is_process_alive(pid):
            exit_enforcement_error(
                cwd, "Daemon restart failed — enforcement cannot evaluate"
            )
    exit_ok()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_daemon_lifecycle.py -v`
Expected: All tests PASS (old and new)

- [ ] **Step 6: Run full test suite for regressions**

Run: `python -m pytest && ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/_daemon_lifecycle.py tests/test_daemon_lifecycle.py
git commit -m "feat(enforcement): daemon lifecycle blocks on failed restart (#39)

When daemon is dead and restart fails during an active audit with
fresh enforcement, the hook now blocks instead of silently allowing.
Also verifies PID is alive after daemon start claims success."
```

---

### Task 4: Update `pre_tool_hook.py` fallback paths

**Files:**
- Modify: `enforcement/hooks/pre_tool_hook.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write failing tests for pre_tool_hook fail-closed behavior**

Add a new test class in `tests/test_protocol_enforcement.py`:

```python
def _force_no_binary(tmp_path):
    """Create bootstrap cooldown marker so ensure_sahjhan() returns None fast.

    Without this, ensure_sahjhan() would attempt an HTTP download, adding
    latency and flakiness. The cooldown marker makes it return None immediately.
    """
    import time
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / ".sahjhan-bootstrap-failed").write_text(str(time.time()))


class TestPreToolHookFailClosed:
    """Issue #39: pre_tool_hook blocks when daemon unreachable during active audit."""

    def test_blocks_when_binary_unavailable_and_fresh(self, tmp_path):
        """Sahjhan binary missing + fresh enforcement → block."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "app.py")},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is False
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "ENFORCEMENT DEGRADED" in reason

    def test_allows_when_binary_unavailable_and_stale(self, tmp_path):
        """Sahjhan binary missing + stale enforcement → allow."""
        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # stale
        write_cache(str(tmp_path), cache)
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "app.py")},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is True

    def test_allows_when_binary_unavailable_and_no_audit(self, tmp_path):
        """Sahjhan binary missing + no active audit → allow."""
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "app.py")},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPreToolHookFailClosed -v`
Expected: FAIL — `test_blocks_when_binary_unavailable_and_fresh` fails (currently allows)

- [ ] **Step 3: Update `pre_tool_hook.py` fallback paths**

Add `exit_enforcement_error` to the import from `_common`:

```python
from _common import exit_block, exit_enforcement_error, exit_ok, exit_warn, read_event, resolve_config_dir
```

Replace each fallback `exit_ok` with `exit_enforcement_error`. The stale check on line 52 stays unchanged.

Line 56-57 (binary unavailable):
```python
    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable")
```

Line 60-61 (config not found):
```python
    config_dir, config_found = resolve_config_dir(cwd)
    if not config_found:
        exit_enforcement_error(cwd, "Enforcement config not found")
```

Line 85-86 (subprocess failure):
```python
    except (OSError, subprocess.TimeoutExpired):
        exit_enforcement_error(cwd, "Hook eval subprocess failed")
```

Line 88-89 (non-zero exit):
```python
    if result.returncode != 0:
        exit_enforcement_error(cwd, "Hook eval returned error")
```

Line 93-94 (JSON parse error):
```python
    except (json.JSONDecodeError, ValueError):
        exit_enforcement_error(cwd, "Hook eval returned invalid JSON")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPreToolHookFailClosed -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest && ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/pre_tool_hook.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): pre_tool_hook fail-closed during active audits (#39)

Replace exit_ok fallbacks with exit_enforcement_error at all 5
daemon-failure paths. Stale enforcement fast-path unchanged."
```

---

### Task 5: Update `post_tool_hook.py` fallback paths

**Files:**
- Modify: `enforcement/hooks/post_tool_hook.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write failing test for post_tool_hook fail-closed behavior**

Add a new test class in `tests/test_protocol_enforcement.py` (uses `_force_no_binary` helper from Task 4):

```python
class TestPostToolHookFailClosed:
    """Issue #39: post_tool_hook warns when daemon unreachable during active audit."""

    def test_warns_when_binary_unavailable_and_fresh(self, tmp_path):
        """Sahjhan binary missing + fresh enforcement → warn (not silent allow)."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "app.py")},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "post_tool_hook.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is True
        assert "ENFORCEMENT DEGRADED" in output.get("additionalContext", "")

    def test_silent_allow_when_stale(self, tmp_path):
        """Stale enforcement → silent allow (no warning)."""
        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "app.py")},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "post_tool_hook.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True  # silent allow
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPostToolHookFailClosed -v`
Expected: FAIL — `test_warns_when_binary_unavailable_and_fresh` fails (currently silent allow)

- [ ] **Step 3: Update `post_tool_hook.py` fallback paths**

Add `exit_enforcement_error` to the import from `_common`:

```python
from _common import _active_ledger, exit_enforcement_error, exit_ok, exit_warn, read_event, resolve_config_dir
```

Line 113-115 (binary unavailable):
```python
    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")
```

Line 117-119 (config not found):
```python
    config_dir, config_found = resolve_config_dir(cwd)
    if not config_found:
        exit_enforcement_error(cwd, "Enforcement config not found", "PostToolUse")
```

Line 141 (subprocess/JSON failure — replace the bare `pass` in the except block):
```python
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        exit_enforcement_error(cwd, "Hook eval failed", "PostToolUse")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPostToolHookFailClosed -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest && ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/post_tool_hook.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): post_tool_hook warns on daemon failure (#39)

Replace silent exit_ok fallbacks with exit_enforcement_error at
3 failure paths. PostToolUse uses warn instead of block since
the tool has already executed."
```

---

### Task 6: Update `bash_guard.py` fallback paths

**Files:**
- Modify: `enforcement/hooks/bash_guard.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write failing test for bash_guard fail-closed behavior**

Add a new test class in `tests/test_protocol_enforcement.py` (uses `_force_no_binary` helper from Task 4):

```python
class TestBashGuardFailClosed:
    """Issue #39: bash_guard warns when daemon unreachable during active audit."""

    def test_warns_when_binary_unavailable_and_fresh(self, tmp_path):
        """Sahjhan binary missing + fresh enforcement → warn."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is True
        assert "ENFORCEMENT DEGRADED" in output.get("additionalContext", "")

    def test_silent_allow_when_no_audit(self, tmp_path):
        """No active audit → silent allow."""
        _force_no_binary(tmp_path)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=env,
        )
        assert code == 0
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestBashGuardFailClosed -v`
Expected: FAIL — `test_warns_when_binary_unavailable_and_fresh` fails

- [ ] **Step 3: Update `bash_guard.py` fallback paths**

Add `exit_enforcement_error` to the import from `_common`:

```python
from _common import _active_ledger, exit_enforcement_error, exit_ok, exit_warn, read_event, resolve_config_dir
```

Line 39-41 (binary unavailable) — need `cwd` available at this point. Move the `cwd` assignment above the binary check:

```python
    cwd = event.get("cwd", os.getcwd())

    binary = ensure_sahjhan()
    if binary is None:
        exit_enforcement_error(cwd, "Sahjhan binary unavailable", "PostToolUse")
```

Line 69-70 (subprocess failure):
```python
    except (OSError, subprocess.TimeoutExpired):
        exit_enforcement_error(cwd, "Manifest verify failed", "PostToolUse")
```

Note: The `cwd` variable is already assigned on line 43 in the current code. The binary check is on line 38-41, which is before the cwd assignment on line 43. You need to move `cwd = event.get("cwd", os.getcwd())` to before the binary check (after the `is_sahjhan_cmd` check on line 35-36).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestBashGuardFailClosed -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest && ruff check .`
Expected: All tests pass, no lint errors

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/bash_guard.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): bash_guard warns on daemon failure (#39)

Replace silent exit_ok fallbacks with exit_enforcement_error at
2 failure paths. Moved cwd assignment before binary check so
exit_enforcement_error has the path it needs."
```

---

### Task 7: Final integration verification

**Files:**
- No new files — verification only

- [ ] **Step 1: Run the full test suite with coverage**

Run: `python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60`
Expected: All tests PASS, coverage gate met

- [ ] **Step 2: Run linting and type checking**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: No errors

- [ ] **Step 3: Verify the fix addresses all 9 failures from issue #39**

Checklist against the issue:
- Failure 1 (daemon start not verified): Fixed in Task 3 — `_start_daemon()` verifies PID
- Failure 2 (stale cache): Out of scope (P5), but mitigated — dead daemon now blocks
- Failure 3 (TDD gate dead): Fixed in Task 4 — `pre_tool_hook.py` blocks on daemon failure
- Failure 4 (zero fix_commit): Fixed in Task 4 — daemon failure blocks edits
- Failure 5 (no TDD): Fixed — TDD gate in `pre_tool_hook.py` now blocks when daemon can't evaluate
- Failure 6 (batch fixes): Fixed — anti-batching in `post_tool_hook.py` now warns
- Failure 7 (bulk deferrals): Mitigated — daemon failure blocks prevent reaching deferral
- Failure 8 (stop hook): Already worked — stop hook reads cache directly
- Failure 9 (cache overwrite): Fixed in Task 2 — MANAGED_DATA blocked from Write/Edit

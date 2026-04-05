# Daemon Lifecycle Integration (Issue #37) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the sahjhan daemon lifecycle into audit orchestration so the daemon starts automatically, stays alive during audits, and stops at audit end or cleanup.

**Architecture:** Belt-and-suspenders — instruction-layer changes (phase-recon, phase-finalize) tell the agent what to do, hook-layer changes (_daemon_lifecycle.py, primer.py, protocol_tracker.py, stop_hook.py) catch failures automatically. The daemon lifecycle hook is a fast PreToolUse supervisor that checks PID liveness and restarts if needed. Teardown happens via protocol_tracker (finalized state), stop_hook (session end), and phase-finalize instructions.

**Tech Stack:** Python 3.11+, Unix domain sockets, os.kill() for PID probing, subprocess for daemon start/stop

**Spec:** `docs/superpowers/specs/2026-04-05-issue-37-daemon-lifecycle-design.md`

---

### Task 1: Daemon Lifecycle Hook — Core Logic

**Files:**
- Create: `enforcement/hooks/_daemon_lifecycle.py`
- Test: `tests/test_daemon_lifecycle.py`

This is the PreToolUse safety net hook. It ensures the daemon and active-run marker are present.

- [ ] **Step 1: Write tests for no-active-audit exit paths**

Create `tests/test_daemon_lifecycle.py`:

```python
"""Tests for _daemon_lifecycle.py — daemon lifecycle PreToolUse hook."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")

sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestDaemonLifecycleNoAudit:
    """Exit early when no active audit exists."""

    def test_allows_when_no_sahjhan_dir(self, tmp_path):
        """No docs/holtz/.sahjhan/ → allow, no action."""
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_allows_when_no_runs_and_no_marker(self, tmp_path):
        """Data dir exists but no runs/ and no active-run marker → allow, no action."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_daemon_lifecycle.py -v`
Expected: FAIL — `_daemon_lifecycle.py` does not exist yet.

- [ ] **Step 3: Write tests for active-run marker recovery**

Append to `tests/test_daemon_lifecycle.py`:

```python
class TestActiveRunMarker:
    """Tests for active-run marker creation when missing."""

    def test_creates_marker_from_highest_run(self, tmp_path):
        """Missing active-run marker + existing runs → writes marker for highest run."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        runs_dir = tmp_path / "docs" / "holtz" / "runs"
        (runs_dir / "run-1").mkdir(parents=True)
        (runs_dir / "run-3").mkdir(parents=True)
        (runs_dir / "run-2").mkdir(parents=True)
        # Write a daemon.pid so it doesn't try to start daemon
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        marker = sahjhan_dir / "active-run"
        assert marker.exists()
        assert marker.read_text().strip() == "run-3"

    def test_skips_marker_when_already_exists(self, tmp_path):
        """Existing active-run marker → left unchanged."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-5\n")
        # Write a daemon.pid so it doesn't try to start daemon
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        assert (sahjhan_dir / "active-run").read_text().strip() == "run-5"
```

- [ ] **Step 4: Write tests for daemon health check**

Append to `tests/test_daemon_lifecycle.py`:

```python
class TestDaemonHealthCheck:
    """Tests for daemon PID-based health checking."""

    def test_does_not_start_when_pid_alive(self, tmp_path, monkeypatch):
        """Daemon PID is alive → no restart attempt."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # Use our own PID — guaranteed alive
        (sahjhan_dir / "daemon.pid").write_text(f"{os.getpid()}\n")

        calls = []
        original_run = subprocess.run
        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return original_run(cmd, **kwargs)
        monkeypatch.setattr(subprocess, "run", mock_run)

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        # Should not have called sahjhan daemon start
        daemon_start_calls = [c for c in calls if "daemon" in str(c) and "start" in str(c)]
        assert daemon_start_calls == []

    def test_starts_daemon_when_pid_dead(self, tmp_path):
        """Daemon PID file exists but process is dead → attempt restart."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # PID 99999999 is almost certainly not running
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        # This will attempt daemon start (which will fail since no real binary),
        # but should still allow the tool call
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_starts_daemon_when_no_pid_file(self, tmp_path):
        """No daemon.pid → daemon not running → attempt start."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        # No daemon.pid file

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_never_blocks_on_failure(self, tmp_path):
        """Even if daemon start fails, the tool call is always allowed."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 5: Implement `_daemon_lifecycle.py`**

Create `enforcement/hooks/_daemon_lifecycle.py`:

```python
#!/usr/bin/env python3
"""Daemon lifecycle supervisor — ensures sahjhan daemon is running during active audits.

PreToolUse hook that:
- Detects active audit (docs/holtz/.sahjhan/ exists)
- Writes active-run marker if missing (scans docs/holtz/runs/ for highest run)
- Checks daemon health via PID probe (os.kill(pid, 0))
- Starts daemon if dead or missing

Never blocks. Best-effort supervisor — if daemon start fails, tool call proceeds.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import _active_ledger, exit_ok, read_event, write_active_run_marker  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402


def _find_highest_run(cwd: str) -> str | None:
    """Scan docs/holtz/runs/ for the highest-numbered run-N directory."""
    runs_dir = os.path.join(cwd, "docs", "holtz", "runs")
    if not os.path.isdir(runs_dir):
        return None
    highest = -1
    for entry in os.listdir(runs_dir):
        m = re.match(r"^run-(\d+)$", entry)
        if m and os.path.isdir(os.path.join(runs_dir, entry)):
            n = int(m.group(1))
            if n > highest:
                highest = n
    return f"run-{highest}" if highest >= 0 else None


def _daemon_pid(cwd: str) -> int | None:
    """Read the daemon PID from daemon.pid, or None if missing/invalid."""
    pid_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "daemon.pid")
    try:
        with open(pid_file, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _is_process_alive(pid: int) -> bool:
    """Check if a process is alive using signal 0."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


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
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # No active audit — nothing to do
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Ensure active-run marker exists
    ledger = _active_ledger(cwd)
    if ledger is None:
        ledger = _find_highest_run(cwd)
        if ledger is None:
            exit_ok()  # No runs exist — data dir is stale or pre-init
        write_active_run_marker(cwd, ledger)

    # Check daemon health
    pid = _daemon_pid(cwd)
    if pid is not None and _is_process_alive(pid):
        exit_ok()  # Daemon is healthy

    # Daemon is down or missing — attempt start
    _start_daemon(cwd)
    exit_ok()  # Always allow, regardless of start success


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_daemon_lifecycle.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Run full test suite + lint**

Run: `python -m pytest && ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: PASS. No regressions.

- [ ] **Step 8: Commit**

```bash
git add enforcement/hooks/_daemon_lifecycle.py tests/test_daemon_lifecycle.py
git commit -m "feat(enforcement): add daemon lifecycle PreToolUse hook (#37)"
```

---

### Task 2: Register Lifecycle Hook in hooks.json

**Files:**
- Modify: `hooks/hooks.json`
- Test: `tests/test_hooks.py` (if hook registration tests exist)

- [ ] **Step 1: Write test for hook registration**

Check if `tests/test_hooks.py` or `tests/test_verify_hooks.py` validates hook registration. If so, add a test that `_daemon_lifecycle.py` is registered. If not, skip this step.

Look for existing registration validation in `tests/test_verify_hooks.py`:

```python
# If there's a test that checks all hooks are registered, it will
# automatically cover _daemon_lifecycle.py once hooks.json is updated.
# Otherwise, add:

def test_daemon_lifecycle_registered():
    """Lifecycle hook must be registered in hooks.json."""
    import json
    hooks_path = os.path.join(REPO_ROOT, "hooks", "hooks.json")
    with open(hooks_path) as f:
        config = json.load(f)
    pre_tool_hooks = config["hooks"]["PreToolUse"]
    all_commands = []
    for entry in pre_tool_hooks:
        for hook in entry["hooks"]:
            all_commands.append(hook["command"])
    assert any("_daemon_lifecycle.py" in cmd for cmd in all_commands), (
        "_daemon_lifecycle.py not found in hooks.json PreToolUse hooks"
    )
```

- [ ] **Step 2: Add lifecycle hook to hooks.json**

Add a new `PreToolUse` entry with `"matcher": "*"` as the **first** entry in the `PreToolUse` list. The lifecycle hook must fire before all other PreToolUse hooks:

In `hooks/hooks.json`, add this as the first element of the `"PreToolUse"` array:

```json
{
  "matcher": "*",
  "hooks": [
    {
      "type": "command",
      "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_daemon_lifecycle.py\""
    }
  ]
}
```

The full `PreToolUse` array becomes:

```json
"PreToolUse": [
  {
    "matcher": "*",
    "hooks": [
      {
        "type": "command",
        "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_daemon_lifecycle.py\""
      }
    ]
  },
  {
    "matcher": "Write|Edit",
    ...existing...
  },
  ...rest unchanged...
]
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_verify_hooks.py tests/test_hooks.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add hooks/hooks.json tests/test_verify_hooks.py
git commit -m "feat(enforcement): register daemon lifecycle hook in hooks.json (#37)"
```

---

### Task 3: Primer Restart-and-Retry

**Files:**
- Modify: `enforcement/hooks/primer.py:77-93`
- Test: `tests/test_sahjhan_integration.py` (TestPrimer class)

- [ ] **Step 1: Write test for restart-and-retry**

Add to the `TestPrimer` class in `tests/test_sahjhan_integration.py`:

```python
def test_restart_retry_on_daemon_failure(self):
    """When context_reset fails, primer attempts daemon restart and retries.

    Uses a mock socket that rejects the first connection (simulating dead
    daemon), then accepts after restart. The restart is simulated by the
    mock binary's daemon-start command creating a flag file.
    """
    import shutil
    import tempfile

    short_tmp = tempfile.mkdtemp(prefix="hz")
    tmp_path = Path(short_tmp)
    try:
        self._run_restart_retry_test(tmp_path)
    finally:
        shutil.rmtree(short_tmp, ignore_errors=True)

def _run_restart_retry_test(self, tmp_path):
    import socket as socket_mod
    import threading
    from datetime import datetime, timezone

    sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
    sahjhan_dir.mkdir(parents=True)
    (tmp_path / "enforcement").mkdir(parents=True)

    from _protocol_cache import empty_cache, write_cache
    _cache = empty_cache()
    _cache["state"] = "awaiting_clear"
    _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
    write_cache(str(tmp_path), _cache)

    # Track calls to the mock binary
    log_file = tmp_path / "cmd.log"
    restart_flag = tmp_path / "daemon_restarted"

    _create_mock_binary(tmp_path, (
        'echo "$*" >> ' + str(log_file) + '\n'
        'case "$*" in\n'
        '  *status*)\n'
        '    echo "state: awaiting_clear (10 events, chain valid)"\n'
        '    exit 0\n'
        '    ;;\n'
        '  *daemon*start*)\n'
        '    touch ' + str(restart_flag) + '\n'
        '    exit 0\n'
        '    ;;\n'
        'esac\n'
        'exit 0'
    ))

    # Mock daemon socket — first connection serves the sign request
    # (The restart-retry logic means primer will attempt daemon start
    # then retry record_authed_event. We set up the socket to serve
    # the retry's sign request.)
    sock_path = str(sahjhan_dir / "daemon.sock")
    srv = socket_mod.socket(socket_mod.AF_UNIX, socket_mod.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(1)
    srv.settimeout(5)

    attempt = {"count": 0}

    def _serve():
        import json as _json
        try:
            conn, _ = srv.accept()
            attempt["count"] += 1
            if attempt["count"] == 1:
                # First attempt: reject (simulates dead daemon)
                conn.close()
                # Accept the retry after restart
                conn2, _ = srv.accept()
                data = conn2.makefile().readline()
                req = _json.loads(data)
                if req.get("op") == "sign":
                    conn2.sendall((_json.dumps({"ok": True, "proof": "deadbeef"}) + "\n").encode())
                conn2.close()
            else:
                data = conn.makefile().readline()
                req = _json.loads(data)
                if req.get("op") == "sign":
                    conn.sendall((_json.dumps({"ok": True, "proof": "deadbeef"}) + "\n").encode())
                conn.close()
        except Exception:
            pass

    t = threading.Thread(target=_serve, daemon=True)
    t.start()

    event = {"user_message": "continue", "cwd": str(tmp_path)}
    code, output, stderr = run_enforcement_hook(
        "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
    )
    srv.close()

    # Verify daemon start was attempted
    assert restart_flag.exists(), "primer should have attempted daemon restart"

    # Verify context_reset was recorded (retry succeeded)
    logged = log_file.read_text()
    assert "context_reset" in logged, "retry should have recorded context_reset"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestPrimer::test_restart_retry_on_daemon_failure -v`
Expected: FAIL — primer does not yet have restart-retry logic.

- [ ] **Step 3: Implement restart-retry in primer.py**

In `enforcement/hooks/primer.py`, add a helper function before `main()`:

```python
def _try_restart_daemon(cwd: str, binary: str) -> bool:
    """Attempt to restart the sahjhan daemon. Returns True on success."""
    try:
        config_dir, _ = resolve_config_dir(cwd)
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "start"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
```

Then replace the `context_reset` try/except block (lines 80-93) with:

```python
    context_reset_failed = False
    try:
        record_authed_event(
            "context_reset",
            {
                "project": "holtz",
                "run": run_number,
                "auditor": "holtz",
                "trigger": "user_prompt_submit",
            },
            cwd=cwd,
            ledger=ledger,
        )
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        # Daemon may be down — attempt restart and retry once
        if _try_restart_daemon(cwd, binary):
            try:
                record_authed_event(
                    "context_reset",
                    {
                        "project": "holtz",
                        "run": run_number,
                        "auditor": "holtz",
                        "trigger": "user_prompt_submit",
                    },
                    cwd=cwd,
                    ledger=ledger,
                )
            except (OSError, subprocess.TimeoutExpired, RuntimeError):
                context_reset_failed = True
        else:
            context_reset_failed = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestPrimer::test_restart_retry_on_daemon_failure -v`
Expected: PASS.

- [ ] **Step 5: Run full primer tests to verify no regressions**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestPrimer tests/test_sahjhan_integration.py::TestPrimerWithMockBinary tests/test_protocol_enforcement.py::TestPrimerFreshness tests/test_protocol_enforcement.py::TestPrimerNoFreshnessGate -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_sahjhan_integration.py
git commit -m "fix(enforcement): primer restarts daemon and retries context_reset (#37)"
```

---

### Task 4: Protocol Tracker Daemon Teardown on Finalize

**Files:**
- Modify: `enforcement/hooks/protocol_tracker.py:115-128`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write test for daemon stop on finalized state**

Add a new class in `tests/test_protocol_enforcement.py`:

```python
class TestProtocolTrackerDaemonTeardown:
    """Tests for daemon stop when protocol reaches finalized state."""

    def test_stops_daemon_on_finalized(self, tmp_path, monkeypatch):
        """When sahjhan status returns finalized, protocol_tracker stops the daemon."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "converged"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        # Create mock binary that returns finalized status and logs daemon stop
        stop_flag = tmp_path / "daemon_stopped"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_binary = bin_dir / "sahjhan-mock"
        mock_binary.write_text(
            '#!/bin/bash\n'
            'case "$*" in\n'
            '  *status*)\n'
            '    echo "state: finalized (100 events, chain valid)"\n'
            '    exit 0\n'
            '    ;;\n'
            '  *daemon*stop*)\n'
            f'    touch {stop_flag}\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0\n'
        )
        mock_binary.chmod(0o755)

        (tmp_path / "enforcement").mkdir(parents=True)
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        env["PATH"] = str(bin_dir) + ":" + env.get("PATH", "")

        # Monkeypatch ensure_sahjhan to return our mock
        monkeypatch.setattr(
            "enforcement.hooks._resolve.ensure_sahjhan",
            lambda: str(mock_binary),
        )

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"{mock_binary} transition finalize"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event, cwd=str(tmp_path), env=env)

        assert stop_flag.exists(), "protocol_tracker should stop daemon when state is finalized"

    def test_does_not_stop_daemon_in_non_terminal(self, tmp_path, monkeypatch):
        """Non-terminal state → daemon should not be stopped."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache

        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        stop_flag = tmp_path / "daemon_stopped"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_binary = bin_dir / "sahjhan-mock"
        mock_binary.write_text(
            '#!/bin/bash\n'
            'case "$*" in\n'
            '  *status*)\n'
            '    echo "state: fix_loop (50 events, chain valid)"\n'
            '    exit 0\n'
            '    ;;\n'
            '  *daemon*stop*)\n'
            f'    touch {stop_flag}\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0\n'
        )
        mock_binary.chmod(0o755)

        (tmp_path / "enforcement").mkdir(parents=True)
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)

        monkeypatch.setattr(
            "enforcement.hooks._resolve.ensure_sahjhan",
            lambda: str(mock_binary),
        )

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"{mock_binary} status"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event, cwd=str(tmp_path), env=env)

        assert not stop_flag.exists(), "daemon should not be stopped in non-terminal state"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolTrackerDaemonTeardown -v`
Expected: FAIL — protocol_tracker doesn't stop daemon yet.

- [ ] **Step 3: Implement daemon stop in protocol_tracker.py**

Add a helper before `main()` in `enforcement/hooks/protocol_tracker.py`:

```python
def _stop_daemon(cwd: str) -> None:
    """Best-effort daemon stop after audit finalization."""
    binary = ensure_sahjhan()
    if binary is None:
        return
    config_dir, _ = resolve_config_dir(cwd)
    try:
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
```

Then in the `is_sahjhan_cmd` block (after `cache = _refresh_from_sahjhan(cwd, cache)` at line 118), add:

```python
        cache = _refresh_from_sahjhan(cwd, cache)
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()

        # Stop daemon after finalization (teardown safety net)
        if cache.get("state") == "finalized":
            _stop_daemon(cwd)

        # BH-017: match subcommand tokens...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolTrackerDaemonTeardown -v`
Expected: PASS.

- [ ] **Step 5: Run full protocol tracker tests**

Run: `python -m pytest tests/test_protocol_enforcement.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/protocol_tracker.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): stop daemon on finalized state in protocol_tracker (#37)"
```

---

### Task 5: Stop Hook Daemon Cleanup and User Hint

**Files:**
- Modify: `enforcement/hooks/stop_hook.py`
- Test: `tests/test_protocol_enforcement.py` (TestStopHookFreshness class)

- [ ] **Step 1: Write test for daemon cleanup on terminal stop**

Add to `tests/test_protocol_enforcement.py`:

```python
class TestStopHookDaemonCleanup:
    """Tests for daemon cleanup in stop_hook.py."""

    def test_stops_daemon_on_terminal_state(self, tmp_path, monkeypatch):
        """Terminal state (finalized) → stop daemon during cleanup."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "finalized"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        stop_flag = tmp_path / "daemon_stopped"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_binary = bin_dir / "sahjhan-mock"
        mock_binary.write_text(
            '#!/bin/bash\n'
            f'touch {stop_flag}\n'
            'exit 0\n'
        )
        mock_binary.chmod(0o755)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        (tmp_path / "enforcement").mkdir(parents=True)

        monkeypatch.setattr(
            "enforcement.hooks._resolve.ensure_sahjhan",
            lambda: str(mock_binary),
        )

        event = {"cwd": str(tmp_path)}
        run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path), env=env)

        assert stop_flag.exists(), "stop_hook should stop daemon on terminal state"

    def test_stops_daemon_on_stale_audit(self, tmp_path, monkeypatch):
        """Stale audit → stop daemon during cleanup."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        stop_flag = tmp_path / "daemon_stopped"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_binary = bin_dir / "sahjhan-mock"
        mock_binary.write_text(
            '#!/bin/bash\n'
            f'touch {stop_flag}\n'
            'exit 0\n'
        )
        mock_binary.chmod(0o755)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
        (tmp_path / "enforcement").mkdir(parents=True)

        monkeypatch.setattr(
            "enforcement.hooks._resolve.ensure_sahjhan",
            lambda: str(mock_binary),
        )

        event = {"cwd": str(tmp_path)}
        run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path), env=env)

        assert stop_flag.exists(), "stop_hook should stop daemon on stale audit"

    def test_block_message_includes_manual_hint(self, tmp_path):
        """Blocked stop message should tell user how to manually kill daemon."""
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        reason = output.get("reason", "")
        assert "daemon stop" in reason.lower() or "! sahjhan" in reason, (
            "Block message should tell user how to manually stop daemon"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookDaemonCleanup -v`
Expected: FAIL.

- [ ] **Step 3: Implement daemon cleanup in stop_hook.py**

Add imports and helper to `enforcement/hooks/stop_hook.py`:

```python
import subprocess

# ... existing imports ...

from _resolve import ensure_sahjhan  # noqa: E402
from _common import resolve_config_dir  # noqa: E402
```

Add helper before `main()`:

```python
def _try_stop_daemon(cwd: str) -> None:
    """Best-effort daemon stop for session cleanup."""
    binary = ensure_sahjhan()
    if binary is None:
        return
    config_dir, _ = resolve_config_dir(cwd)
    try:
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
```

Then modify `main()`:

```python
    # Terminal or idle — allow stop, clean up daemon
    if current_state in _STOP_ALLOWED_STATES:
        _try_stop_daemon(cwd)
        exit_stop_allow()

    # Non-terminal state: check freshness
    if not is_enforcement_fresh(cache):
        _try_stop_daemon(cwd)
        exit_stop_warn(
            f"Stale Holtz audit detected (state: '{current_state}'). "
            "No recent sahjhan activity — this appears to be an abandoned audit. "
            "Consider cleaning up docs/holtz/.sahjhan/ if the audit is no longer needed."
        )

    # Active audit, non-terminal state — block, with manual hint
    exit_stop_block(
        f"Audit is in state '{current_state}' which is not terminal. "
        "You must complete the audit protocol before stopping. "
        "If this audit cannot be completed, the user can manually run: "
        "! sahjhan daemon stop"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookDaemonCleanup -v`
Expected: PASS.

- [ ] **Step 5: Run full stop hook tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): daemon cleanup in stop_hook, manual hint on block (#37)"
```

---

### Task 6: Instruction Layer Updates

**Files:**
- Modify: `skills/holtz/references/phase-recon.md:9-17`
- Modify: `skills/holtz/references/phase-finalize.md:38-52`

- [ ] **Step 1: Update phase-recon.md Step 0**

In `skills/holtz/references/phase-recon.md`, replace the initialization block (lines 10-17):

```markdown
#### Run Initialization (before anything else)

Determine the run number N (check `docs/holtz/runs/` for existing runs, or start at 1). Then start the daemon and initialize the run ledger and protocol state — **all three commands must succeed before any events are recorded:**

```
sahjhan daemon start
sahjhan ledger create --from run N
sahjhan transition run_start
```

The daemon must be running before any hooks that need signing or vault access. All subsequent `event` commands in this run **must** use `--ledger run-N` so findings land in the run ledger, not the default ledger. Omitting `--ledger run-N` causes render warnings and orphaned findings.
```

- [ ] **Step 2: Update phase-finalize.md Step 20**

In `skills/holtz/references/phase-finalize.md`, replace the Step 20 section (lines 38-52):

```markdown
### Step 20: Finalize

This is the LAST step — nothing comes after it.

Run `sahjhan transition finalize` — this transitions to the terminal `finalized` state and renders SUMMARY.md from the ledger. The finalize gate verifies: architecture baseline updated (Step 17), living punchlist updated (Step 19), pattern contribution completed (Step 18). SUMMARY.md includes a Prediction Accuracy table:

```markdown
## Prediction Accuracy
| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | N         | N         | N%       |
| MEDIUM     | N         | N         | N%       |
| LOW        | N         | N         | N%       |
| **Total**  | **N**     | **N**     | **N%**   |
```

After finalization, stop the daemon:

```
sahjhan daemon stop
```
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/phase-recon.md skills/holtz/references/phase-finalize.md
git commit -m "feat: add daemon start/stop to phase-recon and phase-finalize instructions (#37)"
```

---

### Task 7: Final Validation

- [ ] **Step 1: Run full test suite with lint and type checking**

Run: `python -m pytest && ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: All PASS. No regressions.

- [ ] **Step 2: Verify all three bugs are addressed**

Manually trace each bug path:

1. **Bug 1 (state stuck at awaiting_clear):** primer.py now restarts daemon and retries context_reset → gate opens → state advances.
2. **Bug 2 (daemon never started):** phase-recon.md instructs `sahjhan daemon start` + `_daemon_lifecycle.py` auto-starts on every tool use if missing.
3. **Bug 3 (missing active-run marker):** `_daemon_lifecycle.py` detects missing marker and writes it from highest run number.
4. **Teardown (new):** phase-finalize.md instructs `sahjhan daemon stop` + protocol_tracker stops on finalized + stop_hook cleans up on session end.
5. **Failed audit cleanup:** stop_hook cleans up daemon on stale audit. Block message tells user `! sahjhan daemon stop`.

- [ ] **Step 3: Final commit (if any fixups needed)**

Only if previous tasks required adjustments. Otherwise, skip.

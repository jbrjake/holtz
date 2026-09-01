# Daemon Death = Audit Terminal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make daemon death an unrecoverable, audit-terminal event — detect it, block everything, allow stop.

**Architecture:** Add `daemon-init-pid` tracking and `terminated` marker file to `.sahjhan/` data dir. Rewrite `_daemon_lifecycle.py` to detect death instead of restarting. Strip restart logic from `primer.py`. Update `stop_hook.py` to allow stop on terminated audits.

**Tech Stack:** Python 3.11+, pytest, sahjhan 0.10.0

---

### Task 1: Upgrade sahjhan to 0.10.0

**Files:**
- Modify: `enforcement/hooks/_resolve.py:14-23`

Already done in this session. Version pin, checksums, and binaries are updated.

- [x] **Step 1: Verify upgrade**

Run: `bin/sahjhan --version`
Expected: `sahjhan 0.10.0`

- [x] **Step 2: Verify idle-timeout flag exists**

Run: `bin/sahjhan daemon start --help`
Expected: Output includes `--idle-timeout`

---

### Task 2: Add shared helpers to `enforcement/hooks/_common.py`

**Files:**
- Modify: `enforcement/hooks/_common.py`
- Test: `tests/test_daemon_lifecycle.py`

The `_write_terminated_marker`, `_read_init_pid`, and `_is_process_alive` functions are needed by both `_daemon_lifecycle.py` and `primer.py`. Put them in `_common.py` so both can import them.

Note: `_is_process_alive` already exists in `_daemon_lifecycle.py:56-62`. We're moving it to `_common.py` so `primer.py` can use it too.

- [ ] **Step 1: Write failing tests for `_write_terminated_marker`**

Add to `tests/test_daemon_lifecycle.py`:

```python
class TestWriteTerminatedMarker:
    """Tests for _write_terminated_marker shared helper."""

    def test_creates_marker_file(self, tmp_path):
        """Writes terminated marker with correct fields."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345, detected_by="_daemon_lifecycle")

        marker = sahjhan_dir / "terminated"
        assert marker.exists()
        content = marker.read_text()
        assert "reason: daemon_pid_dead" in content
        assert "init_pid: 12345" in content
        assert "detected_by: _daemon_lifecycle" in content
        assert "detected_at:" in content

    def test_updates_enforcement_cache(self, tmp_path):
        """Sets cache state to terminated and active to False."""
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        # Write an existing cache
        cache_path = sahjhan_dir / "enforcement-cache.json"
        cache_path.write_text(json.dumps({"state": "fix_loop", "active": True}))

        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)

        cache = json.loads(cache_path.read_text())
        assert cache["state"] == "terminated"
        assert cache["active"] is False
        assert cache["terminated_reason"] == "daemon_pid_dead"

    def test_handles_missing_cache(self, tmp_path):
        """Creates cache from scratch when no cache file exists."""
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)

        cache_path = sahjhan_dir / "enforcement-cache.json"
        cache = json.loads(cache_path.read_text())
        assert cache["state"] == "terminated"
        assert cache["active"] is False

    def test_handles_corrupt_cache(self, tmp_path):
        """Overwrites corrupt cache gracefully."""
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "enforcement-cache.json").write_text("NOT JSON{{{")

        from _common import _write_terminated_marker
        _write_terminated_marker(str(tmp_path), 12345)

        cache = json.loads((sahjhan_dir / "enforcement-cache.json").read_text())
        assert cache["state"] == "terminated"


class TestReadInitPid:
    """Tests for _read_init_pid shared helper."""

    def test_reads_existing_pid(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon-init-pid").write_text("72578\n")

        from _common import _read_init_pid
        assert _read_init_pid(str(tmp_path)) == 72578

    def test_returns_none_when_missing(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        from _common import _read_init_pid
        assert _read_init_pid(str(tmp_path)) is None

    def test_returns_none_on_corrupt_file(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon-init-pid").write_text("not-a-number\n")

        from _common import _read_init_pid
        assert _read_init_pid(str(tmp_path)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_daemon_lifecycle.py::TestWriteTerminatedMarker tests/test_daemon_lifecycle.py::TestReadInitPid -v`
Expected: FAIL — `_write_terminated_marker` and `_read_init_pid` not found in `_common`

- [ ] **Step 3: Implement helpers in `_common.py`**

Add these imports at the top of `enforcement/hooks/_common.py` (after existing imports):

```python
from datetime import datetime, timezone
```

Add these functions at the end of the file (after `record_authed_event`):

```python
def _read_init_pid(cwd: str) -> int | None:
    """Read the daemon PID recorded at audit initialization.

    Returns None if the file is missing or corrupt. This PID identifies
    the specific daemon instance that holds the session key — if this
    PID is dead, the key is gone and the audit is unrecoverable.
    """
    pid_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "daemon-init-pid")
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


def _write_terminated_marker(
    cwd: str,
    init_pid: int,
    detected_by: str = "unknown",
) -> None:
    """Write the audit-terminated marker and update enforcement cache.

    Called when daemon death is detected. The marker file prevents
    repeated PID checks on subsequent hook invocations. The cache
    update ensures stop_hook allows stop.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    marker = os.path.join(data_dir, "terminated")
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"reason: daemon_pid_dead\n")
        f.write(f"init_pid: {init_pid}\n")
        f.write(f"detected_by: {detected_by}\n")
        f.write(f"detected_at: {datetime.now(timezone.utc).isoformat()}Z\n")

    cache_path = os.path.join(data_dir, "enforcement-cache.json")
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        cache = {}
    cache["state"] = "terminated"
    cache["terminated_reason"] = "daemon_pid_dead"
    cache["active"] = False
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_daemon_lifecycle.py::TestWriteTerminatedMarker tests/test_daemon_lifecycle.py::TestReadInitPid -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_common.py tests/test_daemon_lifecycle.py
git commit -m "feat(enforcement): add terminated marker and init-pid helpers

Shared helpers for daemon-death detection: _write_terminated_marker
writes the terminated marker file and updates enforcement cache,
_read_init_pid reads the PID recorded at audit init, _is_process_alive
checks process liveness. Used by both _daemon_lifecycle.py and
primer.py in subsequent commits."
```

---

### Task 3: Rewrite `_daemon_lifecycle.py` — detect death, never restart

**Files:**
- Modify: `enforcement/hooks/_daemon_lifecycle.py`
- Modify: `tests/test_daemon_lifecycle.py`

Remove `_start_daemon()`. Replace the restart-on-death flow with terminated-marker-and-block. Keep `_find_highest_run` and `_daemon_pid` (still needed). Move `_is_process_alive` import from local to `_common`.

- [ ] **Step 1: Update existing tests and add new ones**

The existing `TestDaemonHealthCheck` tests need to change behavior. `test_starts_daemon_when_pid_dead` currently asserts allow — it should now assert block (when init PID tracked) or allow (legacy, no init PID file).

Replace `TestDaemonHealthCheck` and `TestDaemonLifecycleBlocksDuringActiveAudit` in `tests/test_daemon_lifecycle.py` with:

```python
class TestDaemonDeathTerminatesAudit:
    """Daemon death with init PID tracking → audit terminated."""

    def test_blocks_when_init_pid_dead(self, tmp_path):
        """Init PID dead → writes terminated marker, blocks."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is False
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason
        assert (sahjhan_dir / "terminated").exists()

    def test_allows_when_init_pid_alive(self, tmp_path):
        """Init PID is alive → allow, no termination."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text(f"{os.getpid()}\n")
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True
        assert not (sahjhan_dir / "terminated").exists()

    def test_blocks_fast_when_terminated_marker_exists(self, tmp_path):
        """Terminated marker already present → block immediately, no PID check."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is False
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "AUDIT TERMINATED" in reason

    def test_allows_legacy_no_init_pid_file(self, tmp_path):
        """No daemon-init-pid file → legacy audit, allow."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        # No daemon-init-pid file

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("continue") is True

    def test_writes_terminated_cache_state(self, tmp_path):
        """Terminated marker also updates enforcement-cache.json."""
        import json
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon.pid").write_text("99999999\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}
        run_enforcement_hook("_daemon_lifecycle.py", event, cwd=str(tmp_path))

        cache_path = sahjhan_dir / "enforcement-cache.json"
        cache = json.loads(cache_path.read_text())
        assert cache["state"] == "terminated"
        assert cache["active"] is False
```

Keep `TestDaemonLifecycleNoAudit` and `TestActiveRunMarker` unchanged. Delete `TestDaemonHealthCheck`, `TestDaemonLifecycleBlocksDuringActiveAudit`, and `TestDaemonStartVerification`.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/test_daemon_lifecycle.py::TestDaemonDeathTerminatesAudit -v`
Expected: FAIL — old code still restarts instead of terminating

- [ ] **Step 3: Rewrite `_daemon_lifecycle.py`**

Replace the entire file content of `enforcement/hooks/_daemon_lifecycle.py`:

```python
#!/usr/bin/env python3
"""Daemon lifecycle — detects daemon death and terminates audit.

PreToolUse hook that:
- Detects active audit (docs/holtz/.sahjhan/ exists)
- Checks terminated marker (fast path for already-dead audits)
- Verifies the init-PID daemon is still alive
- If dead: writes terminated marker, blocks all tool use
- Never restarts the daemon — a new daemon has a new key

The daemon holds the HMAC session key exclusively in memory.
Daemon death = key loss = ledger unwritable = audit is over.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    _active_ledger,
    exit_block,
    exit_ok,
    read_event,
    write_active_run_marker,
)


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


def _ensure_active_run_marker(cwd: str) -> None:
    """Write active-run marker if missing."""
    ledger = _active_ledger(cwd)
    if ledger is not None:
        return
    ledger = _find_highest_run(cwd)
    if ledger is None:
        return
    try:
        write_active_run_marker(cwd, ledger)
    except OSError:
        pass


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Already terminated — block immediately
    terminated = os.path.join(data_dir, "terminated")
    if os.path.isfile(terminated):
        exit_block(
            "AUDIT TERMINATED: daemon died — session key lost. "
            "The audit cannot be completed. /stop to exit."
        )

    # Check init PID
    init_pid = _read_init_pid(cwd)
    if init_pid is None:
        # No init PID tracked — legacy audit or pre-init.
        # Can't distinguish original daemon from restart.
        # Allow rather than kill audits started before this feature.
        exit_ok()

    # Init PID exists — is it still alive?
    if _is_process_alive(init_pid):
        _ensure_active_run_marker(cwd)
        exit_ok()

    # Init PID is dead. Audit is over.
    _write_terminated_marker(cwd, init_pid, detected_by="_daemon_lifecycle")
    exit_block(
        "AUDIT TERMINATED: daemon (PID {}) died — session key lost, "
        "ledger unwritable. The audit cannot be completed. "
        "/stop to exit.".format(init_pid)
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_daemon_lifecycle.py -v`
Expected: All PASS (both old retained tests and new ones)

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_daemon_lifecycle.py tests/test_daemon_lifecycle.py
git commit -m "feat(enforcement): daemon death terminates audit, never restarts

Rewrite _daemon_lifecycle.py: instead of restarting a dead daemon
(which generates a new key, breaking the HMAC chain), detect death
via daemon-init-pid and write a terminated marker. All subsequent
hook calls block immediately via the marker fast path.

Removes _start_daemon() entirely. Daemon start belongs in audit
initialization (Step 0), not in hook recovery paths.

Ref: jbrjake/holtz#37, jbrjake/sahjhan#24"
```

---

### Task 4: Rewrite `primer.py` — remove restart, check terminated

**Files:**
- Modify: `enforcement/hooks/primer.py`
- Create: `tests/test_primer.py`

Strip `_try_restart_daemon`. On socket failure, check init PID and write terminated marker if dead. Change the warning message from "restart daemon" to "audit is dead."

- [ ] **Step 1: Write failing tests**

Create `tests/test_primer.py`:

```python
"""Tests for primer.py — UserPromptSubmit hook."""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestPrimerTerminatedAudit:
    """Primer detects terminated audit and injects termination message."""

    def test_injects_termination_when_marker_exists(self, tmp_path):
        """Terminated marker present → inject termination message."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")
        (sahjhan_dir / "active-run").write_text("run-1\n")

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        # Primer uses exit_warn, so continue=True, suppressOutput=False
        assert output.get("continue") is True
        context = output.get("additionalContext", "")
        assert "AUDIT TERMINATED" in context

    def test_no_restart_attempt_on_socket_failure(self, tmp_path):
        """Socket failure does not attempt daemon restart."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-1\n")
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")

        # No daemon running — record_authed_event will fail
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        # Should write terminated marker since init PID is dead
        assert (sahjhan_dir / "terminated").exists()


class TestPrimerNoAudit:
    """Primer exits clean when no audit is active."""

    def test_allows_when_no_sahjhan_dir(self, tmp_path):
        """No .sahjhan dir → no injection, silent allow."""
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_primer.py -v`
Expected: `test_injects_termination_when_marker_exists` FAIL (no terminated check in current primer), `test_no_restart_attempt_on_socket_failure` FAIL (current code restarts)

- [ ] **Step 3: Rewrite `primer.py`**

Replace the full content of `enforcement/hooks/primer.py`:

```python
#!/usr/bin/env python3
"""Sahjhan primer — injects resume context on UserPromptSubmit.

When there's an active non-terminal Sahjhan run, this hook:
1. Checks for terminated audit (daemon died)
2. Records a context_reset event (used by awaiting_clear gate)
3. Injects current protocol state as additional context

If the daemon is dead and the init PID confirms death, writes a
terminated marker and injects a termination message. No restart
attempts — a new daemon has a new key, the old ledger is sealed.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import format_state_line, parse_status_text  # noqa: E402
from _protocol_cache import read_cache as read_enforcement_cache
from _resolve import ensure_sahjhan  # noqa: E402

from _common import (  # noqa: E402
    _active_ledger,
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_ok,
    exit_warn,
    read_event,
    record_authed_event,
    resolve_config_dir,
)


def main() -> None:
    event = read_event()
    binary = ensure_sahjhan()

    if binary is None:
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    config_dir, _ = resolve_config_dir(cwd)

    # No active run — nothing to inject
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Terminated audit — inject termination message, skip everything else
    terminated = os.path.join(data_dir, "terminated")
    if os.path.isfile(terminated):
        exit_warn(
            "AUDIT TERMINATED: daemon died — session key lost. "
            "The ledger is unwritable. This audit cannot be completed. "
            "Use /stop to exit, then start a new audit."
        )

    # Get current status
    ledger = _active_ledger(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.append("status")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_ok()

    if result.returncode != 0:
        exit_ok()

    status = parse_status_text(result.stdout)

    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    if is_terminal or not current_state:
        exit_ok()

    # Record context_reset event (gates awaiting_clear -> fix_loop)
    run_number = (ledger or "").replace("run-", "") or "0"
    context_reset_failed = False
    audit_terminated = False
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
        # Don't restart. Check if daemon init PID is dead.
        init_pid = _read_init_pid(cwd)
        if init_pid is not None and not _is_process_alive(init_pid):
            _write_terminated_marker(cwd, init_pid, detected_by="primer")
            audit_terminated = True
        context_reset_failed = True

    if audit_terminated:
        exit_warn(
            "AUDIT TERMINATED: daemon died during awaiting_clear — session key lost. "
            "The ledger is unwritable. This audit cannot be completed. "
            "Use /stop to exit, then start a new audit."
        )

    # Build resume context
    perspective = status.get("current_perspective", "unknown")
    available = status.get("available_transitions", [])

    context = (
        f"SAHJHAN RESUME CONTEXT — Run {run_number}\n"
        f"Current state: {current_state}\n"
        f"Active perspective: {perspective}\n"
    )
    if available:
        context += f"Available transitions: {', '.join(available)}\n"

    # Add lens priming if in audit/fix_loop with active perspective
    if current_state in ("audit", "fix_loop") and perspective != "unknown":
        context += f"\nLens: {perspective}. Quiz on exit. Failures restart."

    context += (
        f"\nRun `{binary} status` for full state. "
        f"Run `{binary} gate check <transition>` to see what gates are blocking."
    )

    # Append enforcement state line if cache exists
    state_line = format_state_line(read_enforcement_cache(cwd))
    if state_line:
        context += "\n" + state_line

    if context_reset_failed:
        context += (
            "\nWARNING: context_reset recording failed — daemon may not be running. "
            "If the daemon is dead, the audit cannot be completed."
        )

    context += f"\nSahjhan binary: {binary}"
    if ledger:
        context += f"\nActive ledger: {ledger} (use: {binary} --ledger {ledger})"

    exit_warn(context)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_primer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_primer.py
git commit -m "feat(enforcement): primer detects daemon death, no restart

Remove _try_restart_daemon from primer.py. On socket failure,
check daemon-init-pid — if dead, write terminated marker and
inject termination message. No restart attempts.

Ref: jbrjake/holtz#37"
```

---

### Task 5: Update `stop_hook.py` — allow stop on terminated

**Files:**
- Modify: `enforcement/hooks/stop_hook.py`
- Modify: `tests/test_sahjhan_integration.py` (or wherever stop hook tests live)

Add terminated marker check before the cache read. If terminated, allow stop immediately.

- [ ] **Step 1: Find existing stop hook tests and add new test**

Run: `python -m pytest -k "stop" --collect-only` to find test locations.

Add a test (in whichever file has stop hook tests):

```python
class TestStopHookTerminatedAudit:
    """Stop hook allows stop when audit is terminated."""

    def test_allows_stop_on_terminated_marker(self, tmp_path):
        """Terminated marker present → allow stop."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("decision") == "allow"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestStopHookTerminatedAudit -v`
Expected: FAIL — current stop_hook doesn't check terminated marker

- [ ] **Step 3: Add terminated check to `stop_hook.py`**

In `enforcement/hooks/stop_hook.py`, add after the `if not _has_active_audit(cwd):` block (after line 64):

```python
    # Terminated audit — always allow stop
    terminated = os.path.join(cwd, "docs", "holtz", ".sahjhan", "terminated")
    if os.path.isfile(terminated):
        _try_stop_daemon(cwd)
        exit_stop_allow()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sahjhan_integration.py -k "stop" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_sahjhan_integration.py
git commit -m "feat(enforcement): stop hook allows stop on terminated audit

When the terminated marker exists (daemon died, audit is
unrecoverable), allow stop immediately. Attempts best-effort
daemon stop for cleanup.

Ref: jbrjake/holtz#37"
```

---

### Task 6: Rehash trusted-callers manifest and run full test suite

**Files:**
- Modify: `enforcement/trusted-callers.toml` (generated)

Since `_common.py`, `primer.py`, and `stop_hook.py` all changed, their SHA-256 hashes in the trusted-callers manifest are stale.

- [ ] **Step 1: Regenerate manifest**

Run: `scripts/hash-trusted-callers.sh`
Expected: "Updated enforcement/trusted-callers.toml"

- [ ] **Step 2: Run ruff check**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 3: Run mypy**

Run: `mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: No errors

- [ ] **Step 4: Run full test suite with coverage**

Run: `python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60`
Expected: All PASS, coverage >= 60%

- [ ] **Step 5: Commit**

```bash
git add enforcement/trusted-callers.toml
git commit -m "chore: rehash trusted-callers manifest after hook changes"
```

---

### Task 7: Final commit — sahjhan upgrade

The `_resolve.py` version bump and binary changes from Task 1 haven't been committed yet.

- [ ] **Step 1: Commit version upgrade**

```bash
git add enforcement/hooks/_resolve.py
git commit -m "feat(enforcement): upgrade sahjhan to 0.10.0

Adds --idle-timeout flag support (jbrjake/sahjhan#24).
Updates version pin, checksums, and binaries."
```

Note: Do NOT `git add` the `bin/` binaries — they are gitignored.

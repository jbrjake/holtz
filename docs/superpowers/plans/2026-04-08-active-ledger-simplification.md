# Active Ledger Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade sahjhan to v0.11.0 (active-ledger support), then remove all holtz-side `_active_ledger()` / `write_active_run_marker()` plumbing so agents and hooks rely on sahjhan's native active-ledger resolution.

**Architecture:** Sahjhan v0.11.0 reads `{data_dir}/active-ledger` as a fallback when `--ledger` is not specified. Holtz currently duplicates this with its own `active-run` marker file and per-hook injection logic. We upgrade sahjhan, update run initialization to use `--activate`, remove all holtz-side marker reading/writing, simplify every hook, and update the SKILL.md/reference docs.

**Tech Stack:** Python (hooks), TOML (enforcement config), Markdown (SKILL.md, references), Rust binary (sahjhan — consumed, not modified)

---

### Task 1: Upgrade sahjhan to v0.11.0

**Files:**
- Modify: `enforcement/hooks/_resolve.py:14-23`

- [ ] **Step 1: Update version and checksums**

```python
SAHJHAN_VERSION = "0.11.0"

SAHJHAN_CHECKSUMS: dict[str, str] = {
    "aarch64-apple-darwin": "502b14ce17e7f73570566605238c0aa6511e1249d03eaa9ff0dcf58cbc5a74aa",
    "x86_64-apple-darwin": "5bc56d58f101ed9a21a81a09cf4229505793b07bb0af3a60458aabd471cb7c10",
    "x86_64-unknown-linux-gnu": "5d4f16208fb2d0c0d6eafa19f2d11635d79b0991acea457cced446af06b90706",
    "aarch64-unknown-linux-gnu": "40cb1084a1a82f66219bac7bba0a904ad7b96805c9b16049749849ae4724664e",
}
```

- [ ] **Step 2: Delete cached binary to force re-download**

```bash
rm -f bin/sahjhan-* bin/.sahjhan-version
```

- [ ] **Step 3: Verify download works**

Run: `python -c "from enforcement.hooks._resolve import ensure_sahjhan; print(ensure_sahjhan())"`
Expected: prints path to the downloaded binary

Run: `sahjhan --version`
Expected: output contains `0.11.0`

- [ ] **Step 4: Verify new subcommands exist**

Run: `sahjhan ledger activate --help`
Expected: shows help for activate subcommand

Run: `sahjhan ledger deactivate --help`
Expected: shows help for deactivate subcommand

Run: `sahjhan ledger create --help`
Expected: output includes `--activate`

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_resolve.py
git commit -m "chore(enforcement): upgrade sahjhan to v0.11.0 (active-ledger support)"
```

---

### Task 2: Parse `Ledger:` line from sahjhan v0.11.0 status output

**Files:**
- Modify: `enforcement/hooks/_protocol_cache.py:128-168`
- Modify: `tests/test_protocol_enforcement.py` (add test for Ledger line parsing)

Sahjhan v0.11.0 status output now includes a line like `Ledger: run-31 (active-ledger marker)`. We should parse this so `parse_status_text` populates `run_number` and `ledger_name` from it, rather than always defaulting to `"0"`.

- [ ] **Step 1: Write failing test**

Add to `tests/test_protocol_enforcement.py`:

```python
def test_parse_status_text_ledger_line():
    """parse_status_text extracts run_number from Ledger line (sahjhan v0.11.0+)."""
    text = (
        "Ledger: run-31 (active-ledger marker)\n"
        "state: fix_loop (59 events, chain valid)\n"
    )
    result = parse_status_text(text)
    assert result["run_number"] == "31"
    assert result["ledger_name"] == "run-31"
    assert result["ledger_source"] == "active-ledger marker"


def test_parse_status_text_ledger_line_default():
    """parse_status_text handles default ledger (no run number)."""
    text = (
        "Ledger: default (no active-ledger marker)\n"
        "state: idle (0 events, chain valid)\n"
    )
    result = parse_status_text(text)
    assert result["run_number"] == "0"
    assert result["ledger_name"] == "default"


def test_parse_status_text_ledger_line_explicit():
    """parse_status_text handles explicit --ledger flag."""
    text = (
        "Ledger: project (explicit --ledger flag)\n"
        "state: idle (5 events, chain valid)\n"
    )
    result = parse_status_text(text)
    assert result["ledger_name"] == "project"
    assert result["run_number"] == "0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protocol_enforcement.py -k "ledger_line" -v`
Expected: FAIL (ledger_name key missing, run_number always "0")

- [ ] **Step 3: Add Ledger line parsing to `parse_status_text`**

Add to the defaults dict in `parse_status_text`:
```python
    result: dict[str, Any] = {
        "current_state": "",
        "terminal": False,
        "event_count": 0,
        "run_number": "0",
        "ledger_name": "",
        "ledger_source": "",
        "sets": {},
        "available_transitions": [],
        "current_perspective": "unknown",
    }
```

Add a new parsing block in the `for line in lines:` loop, before the state parsing:
```python
        # "Ledger: run-31 (active-ledger marker)"
        m = re.match(r"^Ledger:\s+(\S+)(?:\s+\((.+)\))?", stripped)
        if m:
            ledger_name = m.group(1)
            result["ledger_name"] = ledger_name
            result["ledger_source"] = m.group(2) or ""
            # Extract run number from "run-N" pattern
            rm = re.match(r"^run-(\d+)$", ledger_name)
            if rm:
                result["run_number"] = rm.group(1)
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_protocol_enforcement.py -k "ledger_line" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_protocol_cache.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): parse Ledger line from sahjhan v0.11.0 status output

Sahjhan v0.11.0 status now includes a Ledger line showing which ledger
was resolved and how. parse_status_text now extracts run_number,
ledger_name, and ledger_source from this line."
```

---

### Task 3: Remove `_active_ledger()` and `write_active_run_marker()` from `_common.py`

**Files:**
- Modify: `enforcement/hooks/_common.py:109-129` (remove two functions)
- Modify: `enforcement/hooks/_common.py:221-251` (remove `ledger` param from `record_authed_event`)

- [ ] **Step 1: Write failing tests — importing removed functions raises**

Add to `tests/test_enforcement_config.py` (or a new file `tests/test_active_ledger_removal.py`):

```python
"""Verify _active_ledger and write_active_run_marker are removed from _common.py."""
import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


def _load_enforcement_common():
    spec = importlib.util.spec_from_file_location(
        "_common_enforcement",
        os.path.join(REPO_ROOT, "enforcement", "hooks", "_common.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_active_ledger_removed():
    """_active_ledger must not exist — sahjhan handles ledger resolution."""
    mod = _load_enforcement_common()
    assert not hasattr(mod, "_active_ledger"), (
        "_active_ledger still exists in enforcement/hooks/_common.py. "
        "Remove it — sahjhan v0.11.0 handles active-ledger resolution."
    )


def test_write_active_run_marker_removed():
    """write_active_run_marker must not exist — sahjhan manages the marker."""
    mod = _load_enforcement_common()
    assert not hasattr(mod, "write_active_run_marker"), (
        "write_active_run_marker still exists in enforcement/hooks/_common.py. "
        "Remove it — sahjhan ledger create --activate manages the marker."
    )


def test_record_authed_event_no_ledger_param():
    """record_authed_event should not accept a ledger parameter."""
    import inspect
    mod = _load_enforcement_common()
    sig = inspect.signature(mod.record_authed_event)
    assert "ledger" not in sig.parameters, (
        "record_authed_event still has a 'ledger' parameter. "
        "Remove it — sahjhan resolves the active ledger automatically."
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_active_ledger_removal.py -v`
Expected: all 3 tests FAIL (functions still exist)

- [ ] **Step 3: Remove `_active_ledger()` and `write_active_run_marker()` from `_common.py`**

Delete lines 109-129 (the two functions). In `record_authed_event` (starts at line 221), remove the `ledger` parameter and the `if ledger:` block:

Before:
```python
def record_authed_event(
    event_type: str,
    fields: dict[str, str],
    cwd: str,
    ledger: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Record a restricted event with daemon-signed HMAC proof via sahjhan authed-event.

    Args:
        event_type: The restricted event type name.
        fields: Dict of field name -> value pairs.
        cwd: Working directory for the sahjhan command.
        ledger: Optional ledger name (e.g., "run-25").

    Returns:
        The CompletedProcess from the sahjhan call.
    """
    from _resolve import ensure_sahjhan

    proof = compute_event_proof(event_type, fields, cwd=cwd)
    binary = ensure_sahjhan()
    if binary is None:
        raise OSError("Sahjhan binary unavailable")
    config_dir, _ = resolve_config_dir(cwd)
    cmd = [binary, "--config-dir", config_dir]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["authed-event", event_type, "--proof", proof])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=10)
```

After:
```python
def record_authed_event(
    event_type: str,
    fields: dict[str, str],
    cwd: str,
) -> subprocess.CompletedProcess[str]:
    """Record a restricted event with daemon-signed HMAC proof via sahjhan authed-event.

    Args:
        event_type: The restricted event type name.
        fields: Dict of field name -> value pairs.
        cwd: Working directory for the sahjhan command.

    Returns:
        The CompletedProcess from the sahjhan call.
    """
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    proof = compute_event_proof(event_type, fields, cwd=cwd)
    binary = ensure_sahjhan()
    if binary is None:
        raise OSError("Sahjhan binary unavailable")
    config_dir, _ = resolve_config_dir(cwd)
    cmd = [binary, "--config-dir", config_dir]
    cmd.extend(["authed-event", event_type, "--proof", proof])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=10)
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `python -m pytest tests/test_active_ledger_removal.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_common.py tests/test_active_ledger_removal.py
git commit -m "fix(enforcement): remove _active_ledger and write_active_run_marker from _common.py

Sahjhan v0.11.0 handles active-ledger resolution natively via the
{data_dir}/active-ledger marker file. The holtz-side _active_ledger()
and write_active_run_marker() are no longer needed."
```

---

### Task 4: Remove ledger plumbing from `_daemon_lifecycle.py`

**Files:**
- Modify: `enforcement/hooks/_daemon_lifecycle.py`
- Modify: `tests/test_daemon_lifecycle.py`

- [ ] **Step 1: Update `_daemon_lifecycle.py`**

Remove `_find_highest_run()`, `_ensure_active_run_marker()`, and all imports of `_active_ledger` and `write_active_run_marker`. Remove the `_ensure_active_run_marker(cwd)` call from `main()`.

Full replacement of the file:

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
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_block,
    exit_ok,
    read_event,
)


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
        exit_ok()

    # Init PID exists — is it still alive?
    if _is_process_alive(init_pid):
        exit_ok()

    # Init PID is dead. Audit is over.
    _write_terminated_marker(cwd, init_pid, detected_by="_daemon_lifecycle")
    exit_block(
        f"AUDIT TERMINATED: daemon (PID {init_pid}) died — session key lost, "
        "ledger unwritable. The audit cannot be completed. "
        "/stop to exit."
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update `tests/test_daemon_lifecycle.py`**

Remove the `TestActiveRunMarker` class entirely (tests `test_creates_marker_from_highest_run` and `test_skips_marker_when_already_exists`). These tested holtz-side marker creation which no longer exists.

For tests in `TestDaemonDeathTerminatesAudit` and elsewhere that write `active-run` files as test fixtures — remove those lines. The tests only need the daemon-init-pid and terminated marker files, not the active-run marker.

Remove lines that write `active-run` markers in the remaining test classes. The `active-run` file is no longer read by `_daemon_lifecycle.py`. Specifically:
- `test_blocks_when_init_pid_dead`: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`
- `test_allows_when_init_pid_alive`: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`
- `test_allows_legacy_no_init_pid_file`: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`
- `test_writes_terminated_cache_state`: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`

Delete class `TestActiveRunMarker` (lines 35-68).

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_daemon_lifecycle.py -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/_daemon_lifecycle.py tests/test_daemon_lifecycle.py
git commit -m "fix(enforcement): remove active-run marker logic from _daemon_lifecycle.py

Sahjhan v0.11.0 manages the active-ledger marker natively. The holtz-side
_find_highest_run() and _ensure_active_run_marker() are no longer needed."
```

---

### Task 5: Remove ledger plumbing from `primer.py`

**Files:**
- Modify: `enforcement/hooks/primer.py`
- Modify: `tests/test_primer.py`

- [ ] **Step 1: Update `primer.py`**

Remove import of `_active_ledger`. Remove ledger resolution and `--ledger` injection. Remove the `(use: ...)` hint from the context output. Simplify `record_authed_event` call to drop `ledger=ledger`.

Full replacement:

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

    # Get current status — sahjhan resolves active ledger automatically
    try:
        cmd = [binary, "--config-dir", config_dir, "status"]
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

    # Derive run number from status output or active-ledger marker
    # sahjhan v0.11.0 status shows "Ledger: run-N (...)" — parse it
    run_number = status.get("run_number", "0")
    if run_number == "0":
        # Fallback: read active-ledger marker directly
        active_file = os.path.join(data_dir, "active-ledger")
        try:
            with open(active_file, encoding="utf-8") as f:
                run_number = f.read().strip().replace("run-", "") or "0"
        except OSError:
            pass

    # Record context_reset event (gates awaiting_clear -> fix_loop)
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

    exit_warn(context)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update `tests/test_primer.py`**

Remove `active-run` marker file creation lines from test fixtures. The primer no longer reads this file.

Line 50: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`
Line 64: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_primer.py -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_primer.py
git commit -m "fix(enforcement): remove ledger plumbing from primer.py

Sahjhan v0.11.0 resolves the active ledger automatically. The primer
no longer needs to read the active-run marker or inject --ledger flags."
```

---

### Task 6: Remove ledger plumbing from `pre_tool_hook.py`

**Files:**
- Modify: `enforcement/hooks/pre_tool_hook.py:64-75`

- [ ] **Step 1: Remove ledger detection and injection**

Replace lines 64-75:

Before:
```python
    # Detect active ledger
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-run")
    ledger = None
    try:
        with open(active_file, encoding="utf-8") as f:
            ledger = f.read().strip()
    except OSError:
        pass

    cmd = [binary, "--config-dir", config_dir, "--json"]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["hook", "eval", "--event", "PreToolUse"])
```

After:
```python
    cmd = [binary, "--config-dir", config_dir, "--json",
           "hook", "eval", "--event", "PreToolUse"]
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_sahjhan_integration.py -k "PreTool" -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/pre_tool_hook.py
git commit -m "fix(enforcement): remove ledger plumbing from pre_tool_hook.py"
```

---

### Task 7: Remove ledger plumbing from `post_tool_hook.py`

**Files:**
- Modify: `enforcement/hooks/post_tool_hook.py`

- [ ] **Step 1: Remove `_active_ledger` import and all ledger plumbing**

Remove `_active_ledger` from imports (line 30). Remove `ledger` parameter from `_record_event()`. Remove `ledger = _active_ledger(cwd)` (line 128). Remove all `if ledger:` blocks and `ledger` arguments.

Updated imports:
```python
from _common import (  # noqa: E402
    exit_enforcement_error,
    exit_ok,
    exit_warn,
    read_event,
    resolve_config_dir,
)
```

Updated `_record_event`:
```python
def _record_event(
    binary: str,
    config_dir: str,
    cwd: str,
    event_type: str,
    fields: dict[str, str],
) -> None:
    """Record an event via sahjhan CLI. Best-effort, failures are silent."""
    cmd = [binary, "--config-dir", config_dir, "event", event_type]
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=cwd)
```

Updated `main()` — remove `ledger = _active_ledger(cwd)` and simplify the hook eval and record calls:

```python
    # Call hook eval
    cmd = [binary, "--config-dir", config_dir, "--json",
           "hook", "eval", "--event", "PostToolUse"]
    if tool_name:
        cmd.extend(["--tool", tool_name])
    if file_path:
        cmd.extend(["--file", file_path])
```

And the `_record_event` calls lose the `ledger` argument:
```python
        _record_event(
            binary, config_dir, cwd,
            enriched["event_type"], enriched["fields"],
        )
```
```python
        _record_event(
            binary, config_dir, cwd,
            bash_event["event_type"], bash_event["fields"],
        )
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_sahjhan_integration.py -k "PostTool" -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/post_tool_hook.py
git commit -m "fix(enforcement): remove ledger plumbing from post_tool_hook.py"
```

---

### Task 8: Remove ledger plumbing from `bash_guard.py`

**Files:**
- Modify: `enforcement/hooks/bash_guard.py`

- [ ] **Step 1: Remove `_active_ledger` import and ledger plumbing**

Updated imports:
```python
from _common import (  # noqa: E402
    exit_enforcement_error,
    exit_ok,
    exit_warn,
    read_event,
    resolve_config_dir,
)
```

Replace the manifest verify block (lines 62-100) — remove `ledger = _active_ledger(cwd)` and all `if ledger:` blocks:

```python
    try:
        cmd = [binary, "--config-dir", config_dir, "manifest", "verify"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_enforcement_error(cwd, "Manifest verify failed", "PostToolUse")

    if result.returncode != 0:
        # Record protocol violation
        detail = result.stderr.strip() or result.stdout.strip() or "Manifest verification failed"
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            violation_cmd = [
                binary, "--config-dir", config_dir,
                "event", "protocol_violation",
                "--field", "project=holtz",
                "--field", "run=0",
                "--field", "auditor=holtz",
                "--field", "file_path=unknown",
                "--field", f"detail={detail}",
            ]
            subprocess.run(
                violation_cmd,
                capture_output=True,
                timeout=5,
                cwd=cwd,
            )

        exit_warn(
            f"PROTOCOL VIOLATION: Managed file integrity check failed. "
            f"Detail: {detail}. This violation is permanent and will "
            f"block convergence for this run."
        )
```

Note: `run_number` derivation from ledger name is removed. The `run=0` field is acceptable here because this is a protocol violation event, and the run number is secondary to the violation itself. Sahjhan resolves the correct ledger to write to regardless.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_sahjhan_integration.py -k "BashGuard" -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/bash_guard.py
git commit -m "fix(enforcement): remove ledger plumbing from bash_guard.py"
```

---

### Task 9: Remove ledger plumbing from `protocol_tracker.py`

**Files:**
- Modify: `enforcement/hooks/protocol_tracker.py:29,69-84`

- [ ] **Step 1: Remove `_active_ledger` import and ledger plumbing**

Remove `_active_ledger` from the import on line 29.

In `_refresh_from_sahjhan()`, replace lines 75-83:

Before:
```python
    config_dir, _ = resolve_config_dir(cwd)
    ledger = _active_ledger(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.append("status")
```

After:
```python
    config_dir, _ = resolve_config_dir(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir, "status"]
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_protocol_enforcement.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/protocol_tracker.py
git commit -m "fix(enforcement): remove ledger plumbing from protocol_tracker.py"
```

---

### Task 10: Remove ledger plumbing from `lens_quiz.py`

**Files:**
- Modify: `enforcement/hooks/lens_quiz.py`

- [ ] **Step 1: Remove `_active_ledger` import and all ledger threading**

Remove `_active_ledger` from the import on line 31.

Simplify `_run_sahjhan` — remove `ledger` parameter:
```python
def _run_sahjhan(
    binary: str,
    config_dir: str,
    cwd: str,
    args: list[str],
) -> subprocess.CompletedProcess[str] | None:
    """Run a sahjhan command, returning None on any failure."""
    cmd = [binary, "--config-dir", config_dir]
    cmd.extend(args)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    return None
```

Simplify `_get_run_number` — remove `ledger` parameter, read `active-ledger` marker:
```python
def _get_run_number(cwd: str) -> str:
    """Get current run number from sahjhan active-ledger marker."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-ledger")
    try:
        with open(active_file, encoding="utf-8") as f:
            return f.read().strip().replace("run-", "") or "0"
    except OSError:
        return "0"
```

Simplify `_query_events` — remove `ledger` parameter:
```python
def _query_events(
    binary: str,
    config_dir: str,
    cwd: str,
    event_type: str,
    perspective: str,
) -> list[dict]:
    """Query sahjhan for events of a given type and perspective."""
    result = _run_sahjhan(
        binary, config_dir, cwd,
        ["query", "--type", event_type, "--field", f"perspective={perspective}", "--json"],
    )
    if result and result.returncode == 0:
        with contextlib.suppress(json.JSONDecodeError):
            return json.loads(result.stdout)
    return []
```

In `main()`:
- Replace `ledger = _active_ledger(cwd)` and `run = _get_run_number(binary, config_dir, cwd, ledger)` with `run = _get_run_number(cwd)`.
- Remove `ledger` from all `_query_events()`, `_run_sahjhan()`, and `record_authed_event()` calls.

Specifically, update all call sites:
- `_query_events(binary, config_dir, cwd, ledger, ...)` → `_query_events(binary, config_dir, cwd, ...)`
- `record_authed_event("quiz_posed", {...}, cwd, ledger)` → `record_authed_event("quiz_posed", {...}, cwd)`
- `record_authed_event("quiz_answered", {...}, cwd, ledger)` → `record_authed_event("quiz_answered", {...}, cwd)`
- `record_authed_event("quiz_failed", {...}, cwd, ledger)` → `record_authed_event("quiz_failed", {...}, cwd)`
- `record_authed_event("quiz_exhausted", {...}, cwd, ledger)` → `record_authed_event("quiz_exhausted", {...}, cwd)`

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_lens_quiz_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/lens_quiz.py
git commit -m "fix(enforcement): remove ledger plumbing from lens_quiz.py"
```

---

### Task 11: Remove stale tests for deleted functions

**Files:**
- Modify: `tests/test_sahjhan_integration.py`
- Modify: `tests/test_hmac_helpers.py`
- Modify: `tests/test_bootstrap_read_guard.py`

- [ ] **Step 1: Remove `TestActiveLedger` class from `test_sahjhan_integration.py`**

Delete lines 1017-1069 (the entire `TestActiveLedger` class with `test_active_ledger_returns_name`, `test_active_ledger_returns_none_missing`, and `test_active_run_marker_matches_ledger_registry`).

Also remove `active-run` marker writes from test fixtures elsewhere in the file:
- Line 729: remove `(sahjhan_dir / "active-run").write_text("run-1\n")`
- Lines 943-944: remove the comment and `(tmp_path / "docs" / "holtz" / ".sahjhan" / "active-run").write_text("run-31\n")`
- Lines 999-1000: remove the comment and `(tmp_path / "docs" / "holtz" / ".sahjhan" / "active-run").write_text("run-35\n")`

- [ ] **Step 2: Remove `write_active_run_marker` tests from `test_hmac_helpers.py`**

Delete `test_write_active_run_marker` (lines 196-202) and `test_write_active_run_marker_requires_data_dir` (lines 205-210).

- [ ] **Step 3: Update `test_bootstrap_read_guard.py` — update `test_edit_to_active_run_marker_blocked`**

The `active-run` marker file is replaced by sahjhan's `active-ledger` marker. But the `.sahjhan/` directory is still protected as a whole by `MANAGED_DATA`. The specific test for `active-run` should be updated to test `active-ledger` instead — sahjhan now manages this file, so it should still be blocked from direct writes.

Update `test_edit_to_active_run_marker_blocked` (lines 236-251):

```python
    def test_edit_to_active_ledger_marker_blocked(self):
        """Edit tool targeting active-ledger marker must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "docs/holtz/.sahjhan/active-ledger",
                "old_string": "run-1",
                "new_string": "run-999",
            },
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
```

- [ ] **Step 4: Run all affected tests**

Run: `python -m pytest tests/test_sahjhan_integration.py tests/test_hmac_helpers.py tests/test_bootstrap_read_guard.py tests/test_active_ledger_removal.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_sahjhan_integration.py tests/test_hmac_helpers.py tests/test_bootstrap_read_guard.py
git commit -m "test(enforcement): remove stale active-run marker tests

Tests for _active_ledger(), write_active_run_marker(), and active-run
marker file fixtures are removed. These functions no longer exist —
sahjhan v0.11.0 manages the active-ledger marker natively."
```

---

### Task 12: Update SKILL.md command reference

**Files:**
- Modify: `skills/holtz/SKILL.md:77-142`

- [ ] **Step 1: Update the Sahjhan Enforcement Quick Reference block**

Replace the entire code block (lines 77-142) with:

````
```
# Run ledger management — sahjhan resolves active ledger automatically
sahjhan ledger create --from run N --activate

# Record findings and resolution
sahjhan event finding --field project=holtz --field run=N \
  --field auditor=holtz --field phase=audit --field step=7 \
  --field id=BH-001 --field severity=HIGH --field category=doc/drift \
  --field location="README.md:108" --field perspective=public-contract \
  --field description="Pattern count stale" --field predicted_by=1
sahjhan event finding_resolved --field project=holtz --field run=N \
  --field auditor=holtz --field phase=fix_loop --field step=10 \
  --field id=BH-001 --field commit_hash=abc1234

# Record recon and audit events
sahjhan event recon_finding --field project=holtz --field run=N \
  --field auditor=holtz --field phase=recon --field step=0 \
  --field topic=architecture --field content="Four layers..."
sahjhan event audit_claim --field project=holtz --field run=N \
  --field auditor=holtz --field phase=audit --field step=6 \
  --field source="README.md:15" --field claim="Supports 13 lenses" \
  --field verdict=VERIFIED --field evidence="..."

# Advance protocol steps (canonical commands only)
sahjhan transition run_start           # begin a new audit run
sahjhan transition recon_complete      # after Steps 0-4
sahjhan transition audit_complete      # after Steps 6-8
sahjhan transition merge_complete      # after Step 9
sahjhan transition fix_commit          # after each fix commit
sahjhan set complete perspective <name> # when a perspective passes clean
sahjhan transition lens_rotate         # switch to next perspective
sahjhan transition converge            # attempt convergence
sahjhan transition finalize            # after Steps 17-20

# Check status and gates
sahjhan status                         # current state, set progress
sahjhan gate check converge            # see what's blocking convergence
sahjhan set status perspective         # which perspectives are done

# Checkpoint before /clear
sahjhan ledger checkpoint --name pre-clear

# Record events (all use --field key=value syntax — required: project, run, auditor, phase, step)
sahjhan event recon_step --field project=holtz --field run=N \
  --field auditor=holtz --field phase=recon --field step=0 \
  --field artifact_path=docs/holtz/recon/step0-project-overview.md
sahjhan event fix_start --field project=holtz --field run=N \
  --field auditor=holtz --field finding_id=BH-001
sahjhan event blast_radius --field project=holtz --field run=N \
  --field auditor=holtz --field phase=fix_loop --field step=10 \
  --field target_node=module.py --field depth=2 \
  --field affected_count=5 --field finding_id=BH-001
sahjhan event hardening_complete --field project=holtz --field run=N \
  --field auditor=holtz --field phase=fix_loop --field step=10 \
  --field finding_id=BH-001 --field edge_cases_tested=3 --field tests_added=2
sahjhan event pattern_analysis_complete --field project=holtz --field run=N \
  --field auditor=holtz --field phase=fix_loop --field step=11 \
  --field patterns_found=2 --field siblings_found=4
sahjhan event iteration_complete --field project=holtz --field run=N \
  --field auditor=holtz --field phase=fix_loop --field step=10 \
  --field perspective=component --field items_resolved=3 --field items_remaining=2 \
  --field test_count=50 --field tests_passed=true
sahjhan event justine_dispatched --field project=holtz --field run=N \
  --field auditor=holtz --field phase=recon --field mode=full
```
````

- [ ] **Step 2: Update the Context Survival Protocol section (line 201)**

Replace:
```
- **After compaction or `/clear`: STOP.** Run `sahjhan status` (or `sahjhan --ledger run-N status` to check the active run ledger) and re-read the latest step output files before continuing. After `/clear`, the primer hook injects resume context automatically and records a `context_reset` event in the ledger.
```

With:
```
- **After compaction or `/clear`: STOP.** Run `sahjhan status` and re-read the latest step output files before continuing. After `/clear`, the primer hook injects resume context automatically and records a `context_reset` event in the ledger.
```

- [ ] **Step 3: Update the resume instructions (line 246)**

Replace:
```
2. **If no Sahjhan state but `docs/holtz/recon/` dir exists:** A prior run crashed during recon (Steps 0-4). Create the run ledger (`sahjhan ledger create --from run N`) then run `sahjhan transition run_start`, then check which `docs/holtz/recon/step*.md` files exist. Resume from the first missing step.
```

With:
```
2. **If no Sahjhan state but `docs/holtz/recon/` dir exists:** A prior run crashed during recon (Steps 0-4). Create the run ledger (`sahjhan ledger create --from run N --activate`) then run `sahjhan transition run_start`, then check which `docs/holtz/recon/step*.md` files exist. Resume from the first missing step.
```

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat: remove --ledger run-N from SKILL.md command reference

Sahjhan v0.11.0 resolves the active ledger automatically from the
{data_dir}/active-ledger marker. Agents no longer need to remember
or specify --ledger run-N on every command."
```

---

### Task 13: Update phase reference docs

**Files:**
- Modify: `skills/holtz/references/phase-recon.md:10-31`
- Modify: `skills/holtz/references/phase-convergence.md:11`

- [ ] **Step 1: Update phase-recon.md run initialization**

Replace lines 10-31:

```markdown
Determine the run number N (check `docs/holtz/runs/` for existing runs, or start at 1). Then start the daemon and initialize the run ledger and protocol state — **all four commands must succeed before any events are recorded:**

```bash
# sahjhan daemon start runs in the foreground — you MUST background it.
# Use nohup + & so it survives shell exit, and wait briefly for the
# socket and PID file to appear before proceeding.
nohup sahjhan daemon start > /dev/null 2>&1 &

# Wait for daemon to be ready (socket + PID file)
sleep 1

# Copy daemon.pid → daemon-init-pid so lifecycle hooks can detect daemon death
cp docs/holtz/.sahjhan/daemon.pid docs/holtz/.sahjhan/daemon-init-pid

sahjhan ledger create --from run N --activate
sahjhan transition run_start
```

**Why nohup?** `sahjhan daemon start` is foreground-only — it does not fork. Without `nohup ... &`, the Bash tool blocks until timeout and then kills the daemon. The `daemon-init-pid` copy is required by `_daemon_lifecycle.py` to distinguish "original daemon" from "restarted daemon with different key."

The `--activate` flag sets the active-ledger marker so all subsequent sahjhan commands automatically target this run's ledger. No `--ledger run-N` needed on individual commands.
```

- [ ] **Step 2: Update phase-recon.md step event reminder (line 83)**

Replace:
```
**After each step:** record a `sahjhan event recon_step` with the step number and artifact path. Additionally, record significant findings as `recon_finding` events (e.g., `sahjhan event recon_finding --field topic=architecture --field content="..."`) so they are captured in the run ledger alongside the markdown artifacts.
```

With:
```
**After each step:** record a `sahjhan event recon_step` with the step number and artifact path. Additionally, record significant findings as `recon_finding` events (e.g., `sahjhan event recon_finding --field topic=architecture --field content="..."`) so they are captured in the ledger alongside the markdown artifacts.
```

- [ ] **Step 3: Update phase-convergence.md checkpoint command (line 11)**

Replace:
```
3. If not converged: run `sahjhan --ledger run-N ledger checkpoint` then `sahjhan transition iteration_boundary`. Tell the user: *"Not converged. `/clear` then any message to continue."* Stop. The stop gate hook enforces this: blocks premature stops until the protocol reaches a terminal state.
```

With:
```
3. If not converged: run `sahjhan ledger checkpoint` then `sahjhan transition iteration_boundary`. Tell the user: *"Not converged. `/clear` then any message to continue."* Stop. The stop gate hook enforces this: blocks premature stops until the protocol reaches a terminal state.
```

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/references/phase-recon.md skills/holtz/references/phase-convergence.md
git commit -m "feat: update phase references for active-ledger simplification

Run initialization now uses --activate flag. Phase docs no longer
reference --ledger run-N for individual commands."
```

---

### Task 14: Update `_sahjhan_bootstrap.py` comment

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py:36`

- [ ] **Step 1: Update the comment**

Replace:
```python
# ledger, active-run marker). Writes and deletes must be blocked.
```

With:
```python
# ledger, active-ledger marker). Writes and deletes must be blocked.
```

- [ ] **Step 2: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py
git commit -m "fix(enforcement): update active-run comment to active-ledger in bootstrap"
```

---

### Task 15: Run full test suite and lints

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite with coverage**

Run: `python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60`
Expected: all tests PASS, coverage >= 60%

- [ ] **Step 2: Run ruff**

Run: `ruff check .`
Expected: no errors

- [ ] **Step 3: Run mypy**

Run: `mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: no errors

- [ ] **Step 4: Verify no stale references to `active-run` or `_active_ledger` in hook code**

Run: `grep -r "active-run\|_active_ledger\|write_active_run_marker" enforcement/hooks/`
Expected: only the comment in `_sahjhan_bootstrap.py` references `active-ledger` (not `active-run`)

Run: `grep -r "_active_ledger\|write_active_run_marker" enforcement/hooks/`
Expected: no matches

- [ ] **Step 5: Verify SKILL.md has no `--ledger run-` patterns (except project ledger)**

Run: `grep -n "\-\-ledger run" skills/holtz/SKILL.md skills/holtz/references/*.md`
Expected: no matches

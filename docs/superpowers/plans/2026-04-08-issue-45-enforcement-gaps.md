# Issue #45 Enforcement Gap Closure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close five enforcement gaps that allow ledger destruction and inescapable stop loops (issue #45).

**Architecture:** Four changes across three files plus SKILL.md. Bootstrap hook switches from blocklist to allowlist for sahjhan commands. Stop hook adds inline daemon liveness check. Primer injects hard stop on auth failure. SKILL.md gets a new hard gate and red flag.

**Tech Stack:** Python 3, pytest, subprocess-based hook testing

**Spec:** `docs/superpowers/specs/2026-04-08-issue-45-enforcement-gaps-design.md`

---

### Task 1: Sahjhan version upgrade to 0.12.0

**Files:**
- Modify: `enforcement/hooks/_resolve.py:14-23`
- Modify: `bin/.sahjhan-version`

This is already done — version and checksums updated, binary downloaded. Confirm it works.

- [ ] **Step 1: Verify binary version**

Run: `bin/sahjhan-aarch64-apple-darwin --version`
Expected: `sahjhan 0.12.0`

- [ ] **Step 2: Run existing tests to confirm nothing broke**

Run: `python -m pytest tests/test_bootstrap_read_guard.py tests/test_primer.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/_resolve.py
git commit -m "feat(enforcement): upgrade sahjhan to v0.12.0

Authenticated reset, macOS auth fix, diagnostic error reason codes.
Resolves daemon-side requirements from issue #45."
```

---

### Task 2: Allowlist model in `_sahjhan_bootstrap.py`

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py:44-69`
- Modify: `tests/test_bootstrap_read_guard.py`

- [ ] **Step 1: Write failing tests for new allowlist behavior**

Add to `tests/test_bootstrap_read_guard.py`, new class `TestSahjhanAllowlist`:

```python
class TestSahjhanAllowlist:
    """Sahjhan command allowlist: only permitted subcommands pass."""

    def test_sahjhan_reset_blocked(self):
        """reset is not in the allowlist — must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "not permitted" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_sahjhan_reset_with_proof_blocked(self):
        """reset with --proof is still blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm --proof abc123"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sahjhan_unknown_subcommand_blocked(self):
        """Unknown/future subcommands are blocked by default."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan frobnicate --all"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bare_sahjhan_blocked(self):
        """Bare sahjhan with no subcommand is blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sahjhan_with_config_dir_flag_allowed(self):
        """Flags before subcommand must be skipped correctly."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan --config-dir /some/path status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_stop_blocked(self):
        """daemon is allowed but daemon stop is specifically blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sahjhan_daemon_start_allowed(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_gate_check_allowed(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan gate check converge"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_defer_allowed(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan defer low PL-005"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_init_allowed(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan init"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_nohup_sahjhan_daemon_start_allowed(self):
        """nohup wrapper around allowed command must pass."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "nohup sahjhan daemon start > /dev/null 2>&1 &"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_chained_sahjhan_reset_blocked(self):
        """reset blocked even in chained commands."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo foo && sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_case_insensitive_reset_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "Sahjhan Reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bootstrap_read_guard.py::TestSahjhanAllowlist -v`
Expected: Several FAIL (reset tests pass by accident since existing blocklist catches `sahjhan sign` etc, but `reset` and `unknown` tests should fail)

- [ ] **Step 3: Implement allowlist in `_sahjhan_bootstrap.py`**

Replace `BLOCKED_DAEMON_CMDS` (lines 44-51) and `_bash_references_daemon_cmd()` (lines 60-69) with:

```python
# Sahjhan subcommands the agent is permitted to invoke via Bash.
# Everything not listed is blocked by default (defense-in-depth).
ALLOWED_SAHJHAN_SUBCMDS = {
    "status",        # Read protocol state
    "event",         # Record standard events
    "authed-event",  # Record restricted events
    "transition",    # Advance protocol state
    "hook",          # Hook evaluation
    "manifest",      # Manifest verify
    "ledger",        # Ledger operations
    "render",        # Render STATUS.md/PUNCHLIST.md
    "daemon",        # Daemon management (start, status — NOT stop)
    "gate",          # Gate check
    "defer",         # Defer findings
    "init",          # Initialize sahjhan
}

# Second-level blocks: subcommand is allowed but specific sub-subcommands are not.
BLOCKED_SAHJHAN_SUBSUB: dict[str, set[str]] = {
    "daemon": {"stop"},
}


def _extract_sahjhan_subcmd(command: str) -> tuple[str, str] | None:
    """Extract sahjhan subcommand from a shell command.

    Skips leading wrappers (nohup, env) and flags (--config-dir X).
    Returns (subcommand, sub_subcommand) or None if not a sahjhan command.
    """
    # Strip shell wrappers
    tokens = command.split()
    i = 0
    while i < len(tokens) and tokens[i].lower() in ("nohup", "env"):
        i += 1

    # Find sahjhan token
    while i < len(tokens):
        if tokens[i].lower().rstrip(";") in ("sahjhan", "./sahjhan"):
            break
        # Skip env VAR=val pairs
        if "=" in tokens[i]:
            i += 1
            continue
        return None  # non-sahjhan command
    else:
        return None

    i += 1  # skip past 'sahjhan'

    # Skip flags and their values before the subcommand
    subcmd = ""
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            # Flags like --config-dir take a value argument
            if tok in ("--config-dir", "--data-dir", "-c"):
                i += 2  # skip flag + value
            else:
                i += 1  # boolean flag
            continue
        subcmd = tok.lower().rstrip(";")
        break

    if not subcmd:
        return ("", "")  # bare 'sahjhan' with no subcommand

    # Extract sub-subcommand (e.g., 'daemon stop' → 'stop')
    subsub = ""
    if i + 1 < len(tokens):
        next_tok = tokens[i + 1]
        if not next_tok.startswith("-"):
            subsub = next_tok.lower().rstrip(";")

    return (subcmd, subsub)


def _bash_references_blocked_sahjhan(command: str) -> str | None:
    """Check if a Bash command invokes a blocked sahjhan subcommand.

    Uses allowlist: only ALLOWED_SAHJHAN_SUBCMDS pass. Everything else is blocked.
    Returns a block reason string if blocked, None if allowed.
    """
    import re
    segments = re.split(r'\s*(?:&&|\|\||[;|\n])\s*', command)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        result = _extract_sahjhan_subcmd(seg)
        if result is None:
            continue  # not a sahjhan command

        subcmd, subsub = result

        if not subcmd:
            return (
                "BLOCKED: bare 'sahjhan' with no subcommand is not permitted. "
                "Use a specific subcommand (status, event, transition, etc.)."
            )

        if subcmd not in ALLOWED_SAHJHAN_SUBCMDS:
            return (
                f"BLOCKED: sahjhan subcommand '{subcmd}' is not permitted. "
                f"Allowed: {', '.join(sorted(ALLOWED_SAHJHAN_SUBCMDS))}."
            )

        blocked_subs = BLOCKED_SAHJHAN_SUBSUB.get(subcmd)
        if blocked_subs and subsub in blocked_subs:
            return (
                f"BLOCKED: 'sahjhan {subcmd} {subsub}' is not permitted. "
                f"Only trusted hook scripts may invoke this command."
            )

    return None
```

Update `main()` to call `_bash_references_blocked_sahjhan` instead of `_bash_references_daemon_cmd`:

Replace lines 251-257 (the daemon_cmd block) with:

```python
        # Allowlist check for sahjhan subcommands (defense-in-depth)
        sahjhan_block = _bash_references_blocked_sahjhan(command)
        if sahjhan_block:
            _block(sahjhan_block)
            return
```

- [ ] **Step 4: Run the full test suite for the bootstrap hook**

Run: `python -m pytest tests/test_bootstrap_read_guard.py -v`
Expected: All tests pass (both old and new)

- [ ] **Step 5: Remove superseded tests from `TestDaemonCommandGuards`**

The old `TestDaemonCommandGuards` class tests the blocklist behavior. Several tests now duplicate `TestSahjhanAllowlist` tests. Keep only tests that verify behavior NOT covered by the new class:

- Delete: `test_bash_sahjhan_sign_blocked` (covered: not in allowlist)
- Delete: `test_bash_sahjhan_verify_blocked` (covered: not in allowlist)
- Delete: `test_bash_sahjhan_vault_store_blocked` (covered: not in allowlist)
- Delete: `test_bash_sahjhan_vault_read_blocked` (covered: not in allowlist)
- Delete: `test_bash_sahjhan_vault_list_blocked` (covered: not in allowlist)
- Delete: `test_bash_sahjhan_daemon_stop_blocked` (covered: new class)
- Delete: `test_bash_sahjhan_status_allowed` (covered: new class)
- Delete: `test_bash_sahjhan_event_allowed` (covered: new class)
- Delete: `test_bash_sahjhan_daemon_start_allowed` (covered: new class)
- Delete: `test_bash_sahjhan_daemon_status_allowed` (covered: new class)
- Delete: `test_bash_git_status_allowed` (keep — verifies non-sahjhan commands pass)
- Delete: `test_bash_case_insensitive_sign_blocked` (covered: new class has case test)

Keep `test_bash_git_status_allowed` — move it into `TestSahjhanAllowlist` or leave in the old class. Delete the rest of `TestDaemonCommandGuards` if empty.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/test_bootstrap_read_guard.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py tests/test_bootstrap_read_guard.py
git commit -m "feat(enforcement): switch sahjhan bootstrap to allowlist model

Replace BLOCKED_DAEMON_CMDS blocklist with ALLOWED_SAHJHAN_SUBCMDS
allowlist. Unknown subcommands (including reset) are blocked by default.
daemon is allowed but daemon stop is specifically blocked.

Closes half of #45 (issue 3)."
```

---

### Task 3: Stop hook daemon liveness check

**Files:**
- Modify: `enforcement/hooks/stop_hook.py:64-113`
- Create: `tests/test_stop_hook.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_stop_hook.py`:

```python
"""Tests for stop_hook.py — Stop event hook."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


class TestStopHookDaemonLiveness:
    """Stop hook should check daemon liveness and allow stop if daemon is dead."""

    def test_dead_daemon_allows_stop(self, tmp_path):
        """Dead daemon PID → write terminated marker → allow stop."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        # Write a PID that definitely doesn't exist
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")
        # Write a cache in non-terminal state
        cache = {"state": "fix_loop", "active": True,
                 "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00"}
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        assert code == 0
        # Should allow stop
        decision = output.get("hookSpecificOutput", {}).get("decision", "")
        assert decision == "allow", f"Expected allow, got {decision}"
        # Should have written terminated marker
        assert (sahjhan_dir / "terminated").exists()

    def test_no_pid_file_allows_stop(self, tmp_path):
        """No daemon-init-pid file → no daemon session → allow stop."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        cache = {"state": "fix_loop", "active": True,
                 "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00"}
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        assert code == 0
        decision = output.get("hookSpecificOutput", {}).get("decision", "")
        assert decision == "allow"

    def test_live_daemon_still_blocks(self, tmp_path):
        """Live daemon in non-terminal state → still blocked."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        # Use our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")
        cache = {"state": "fix_loop", "active": True,
                 "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00"}
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        assert code == 0
        decision = output.get("hookSpecificOutput", {}).get("decision", "")
        assert decision == "block"


class TestStopHookRemediationMessage:
    """Block message must explain that ! sahjhan daemon stop → next stop works."""

    def test_block_message_explains_two_step(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")
        cache = {"state": "fix_loop", "active": True,
                 "last_sahjhan_cmd": "2099-01-01T00:00:00+00:00"}
        (sahjhan_dir / "enforcement-cache.json").write_text(json.dumps(cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        reason = output.get("hookSpecificOutput", {}).get("reason", "")
        assert "next stop attempt" in reason.lower() or "next stop" in reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stop_hook.py -v`
Expected: `test_dead_daemon_allows_stop` FAIL (currently blocks), `test_no_pid_file_allows_stop` FAIL, remediation message test FAIL

- [ ] **Step 3: Implement daemon liveness check in `stop_hook.py`**

Add `_is_process_alive`, `_read_init_pid`, `_write_terminated_marker` to the existing `from _common import` block at line 26-32:

```python
from _common import (  # noqa: E402
    _is_process_alive,
    _read_init_pid,
    _write_terminated_marker,
    exit_stop_allow,
    exit_stop_block,
    exit_stop_warn,
    read_event,
    resolve_config_dir,
)
```

Add daemon liveness check after the terminated marker check (after line 76) and before the cache read:

```python
    # Daemon liveness check: if the daemon is dead, the audit is
    # unrecoverable (session key lost). Allow stop and write marker
    # so future checks fast-path. Fixes issue #45 (stop loop escape).
    init_pid = _read_init_pid(cwd)
    if init_pid is not None and not _is_process_alive(init_pid):
        _write_terminated_marker(cwd, init_pid, detected_by="stop_hook")
        exit_stop_allow()
    if init_pid is None:
        # No daemon PID file → daemon was never started or already cleaned.
        # No session key to protect → allow stop.
        exit_stop_allow()
```

Update the block message at the end of `main()`:

```python
    exit_stop_block(
        f"Audit is in state '{current_state}' which is not terminal. "
        "You must complete the audit protocol before stopping. "
        "If this audit cannot be completed, the user can manually run: "
        "! sahjhan daemon stop\n"
        "(The next stop attempt will detect the dead daemon and allow exit.)"
    )
```

- [ ] **Step 4: Run stop hook tests**

Run: `python -m pytest tests/test_stop_hook.py -v`
Expected: All pass

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_stop_hook.py
git commit -m "feat(enforcement): add daemon liveness check to stop hook

Stop hook now checks daemon-init-pid liveness directly. Dead daemon
→ write terminated marker → allow stop. No PID file → allow stop.
Fixes the inescapable stop loop from issue #45 (issue 5)."
```

---

### Task 4: Primer fail-closed on auth failure

**Files:**
- Modify: `enforcement/hooks/primer.py:149-153`
- Modify: `tests/test_primer.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_primer.py`, new class:

```python
class TestPrimerAuthFailureFailClosed:
    """Auth failure must inject hard stop instruction, not soft warning."""

    def test_auth_failure_injects_hard_stop(self, tmp_path):
        """When context_reset auth fails (daemon alive but auth broken),
        primer must inject enforcement failure stop instruction."""
        _init_sahjhan(tmp_path)
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        # Write a PID that IS alive (our own PID) so it's not a daemon death
        (sahjhan_dir / "daemon-init-pid").write_text(f"{os.getpid()}\n")
        # No daemon socket → record_authed_event will fail with OSError
        # But PID is alive → not a daemon death → auth failure path

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event, cwd=str(tmp_path))
        assert code == 0
        context = output.get("additionalContext", "")
        assert "ENFORCEMENT FAILURE" in context
        assert "STOP" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_primer.py::TestPrimerAuthFailureFailClosed -v`
Expected: FAIL — currently injects soft warning, not hard stop

- [ ] **Step 3: Change primer auth failure from soft warning to hard stop**

In `primer.py`, replace the soft warning at lines 149-153:

```python
    if context_reset_failed:
        context += (
            "\nWARNING: context_reset recording failed — daemon may not be running. "
            "If the daemon is dead, the audit cannot be completed."
        )
```

With a hard stop injection:

```python
    if context_reset_failed:
        context += (
            "\n\n⛔ ENFORCEMENT FAILURE — STOP IMMEDIATELY\n\n"
            "Daemon authentication failed. The context_reset event cannot be recorded, "
            "which means protocol gates are permanently blocked for this session.\n\n"
            "This is an unrecoverable state. Do NOT attempt to:\n"
            "- Reset the ledger (sahjhan reset)\n"
            "- Modify .sahjhan/ contents directly\n"
            "- Work around the blocked gate\n\n"
            "Report this failure to the user and wait for instructions."
        )
```

- [ ] **Step 4: Run primer tests**

Run: `python -m pytest tests/test_primer.py -v`
Expected: All pass (old and new)

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_primer.py
git commit -m "feat(enforcement): fail-closed on primer auth failure

When context_reset auth fails but daemon PID is alive (auth broken,
not daemon dead), inject hard stop instruction instead of soft warning.
Addresses issue #45 (issues 1 + 4)."
```

---

### Task 5: SKILL.md hard gate and rationalization red flag

**Files:**
- Modify: `skills/holtz/SKILL.md:22-26` (hard gate section)
- Modify: `skills/holtz/SKILL.md:186-187` (red flags table)

No tests — this is a skill instruction change.

- [ ] **Step 1: Add hard gate**

After the existing `</HARD-GATE>` closing tag at line 26, add:

```markdown

<HARD-GATE>
Cannot advance through legitimate transitions → STOP. A broken enforcement state is a finding, not an obstacle. Report to user. Never run `sahjhan reset` or modify `.sahjhan/` directly.
</HARD-GATE>
```

- [ ] **Step 2: Add rationalization red flag**

Add a new row after the last row of the table (line 187, after the "fixing all bugs" row):

```markdown
| "The enforcement is broken, I'll reset and start fresh" | Broken state is evidence. Report and stop. |
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat: add unrecoverable-state hard gate and red flag to SKILL.md

Instructs agent to stop and report when enforcement is broken rather
than attempting to reset or work around. Addresses issue #45 (issue 4)."
```

---

### Task 6: Final verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60`
Expected: All pass, coverage gate met

- [ ] **Step 2: Run linters**

Run: `ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: Clean

- [ ] **Step 3: Verify spec coverage**

Checklist against spec:
- [x] Change 1: Allowlist model (Task 2)
- [x] Change 2: Stop hook liveness (Task 3)
- [x] Change 3: Primer fail-closed (Task 4)
- [x] Change 4: SKILL.md hard gate (Task 5)
- [x] Change 5: Daemon reset auth (sahjhan v0.12.0, Task 1)
- [x] Change 6: macOS auth fix (sahjhan v0.12.0, Task 1)

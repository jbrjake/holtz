# Enforcement Hardening Phase 1: Capability Restriction + Protocol Integrity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 4 critical exploits (quiz bypass, lens bulk-completion, self-merge, raw event injection) and add 5 protocol integrity gates, using HMAC-authenticated events and read guards.

**Architecture:** Extends the existing hook-based enforcement layer with three new capabilities: (1) read-guarding sensitive files via `_sahjhan_bootstrap.py`, (2) HMAC-authenticated event recording via shared helpers in `_common.py`, (3) new gate conditions in `transitions.toml`. The Sahjhan binary changes from jbrjake/sahjhan#11 must be merged before starting.

**Tech Stack:** Python 3.11+ (hooks), TOML (Sahjhan config), HMAC-SHA256 (event provenance), pytest (tests)

**Prerequisite:** jbrjake/sahjhan#11 must be merged and the updated `bin/sahjhan` binary must be in place. Verify with: `bin/sahjhan authed-event --help` (should show the command). `bin/sahjhan guards` (should return JSON).

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `enforcement/hooks/_sahjhan_bootstrap.py` | Modify | Add read-guard support (Read tool + Bash reads) |
| `enforcement/hooks/_common.py` | Modify | Add HMAC helpers (`compute_event_proof`, `record_authed_event`) |
| `enforcement/hooks/lens_quiz.py` | Modify | Use authenticated events, restructure for subagent-answers-quiz flow |
| `enforcement/hooks/primer.py` | Modify | Use authenticated events for `context_reset` |
| `enforcement/hooks/commit_gate.py` | Modify | Unconditional commit blocking in fix_loop state |
| `enforcement/hooks/_protocol_cache.py` | Modify | Expose `is_fix_loop_state()` helper |
| `enforcement/events.toml` | Modify | Add `restricted = true`, new event types |
| `enforcement/transitions.toml` | Modify | New gate conditions on 5 transitions |
| `enforcement/protocol.toml` | Modify | Add `[guards]` section |
| `enforcement/scripts/check_sweep_evidence.py` | Create | Final sweep read-count validator |
| `tests/test_bootstrap_read_guard.py` | Create | Tests for read-guard enforcement |
| `tests/test_hmac_helpers.py` | Create | Tests for HMAC computation |
| `tests/test_commit_gate.py` | Modify | Tests for unconditional blocking |
| `tests/test_sweep_evidence.py` | Create | Tests for sweep evidence checker |

---

### Task 1: Configure Read-Guard Manifest in protocol.toml

**Files:**
- Modify: `enforcement/protocol.toml`

- [ ] **Step 1: Add guards section to protocol.toml**

Add at end of file:

```toml
[guards]
read_blocked = [
    ".sahjhan/session.key",
    "enforcement/quiz-bank.json",
]
```

- [ ] **Step 2: Commit**

```bash
git add enforcement/protocol.toml
git commit -m "feat(enforcement): add read-guard manifest to protocol.toml

Declares paths that must be blocked from agent Read/Bash access.
The _sahjhan_bootstrap hook will consume this via 'sahjhan guards'."
```

---

### Task 2: Mark Restricted Event Types in events.toml

**Files:**
- Modify: `enforcement/events.toml`

- [ ] **Step 1: Add `restricted = true` to quiz and context_reset events**

Add `restricted = true` line after the `description` line for each of these event blocks:
- `[events.quiz_posed]` (line 359)
- `[events.quiz_answered]` (line 369)
- `[events.quiz_failed]` (line 380)
- `[events.quiz_exhausted]` (line 390)
- `[events.context_reset]` (line 117)

Example for `quiz_posed`:
```toml
[events.quiz_posed]
description = "Quiz questions posed to lens subagent"
restricted = true
fields = [
```

- [ ] **Step 2: Add new event types**

Add at end of `events.toml`:

```toml
# ── Enforcement hardening events ──

[events.lens_sweep_started]
description = "A lens sweep has been initiated for a specific perspective"
fields = [
    { name = "perspective", type = "string" },
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
]

[events.merge_agent_dispatched]
description = "Merge agent subagent was dispatched for finding classification"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
]
```

- [ ] **Step 3: Commit**

```bash
git add enforcement/events.toml
git commit -m "feat(enforcement): mark restricted event types and add new event types

quiz_posed, quiz_answered, quiz_failed, quiz_exhausted, and context_reset
are now restricted (require HMAC proof via sahjhan authed-event).

New types: lens_sweep_started (for sequential rotation enforcement),
merge_agent_dispatched (for merge-agent gate)."
```

---

### Task 3: Add Read-Guard Enforcement to _sahjhan_bootstrap.py

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py`
- Create: `tests/test_bootstrap_read_guard.py`

- [ ] **Step 1: Write failing tests for read-guard**

Create `tests/test_bootstrap_read_guard.py`:

```python
"""Tests for _sahjhan_bootstrap.py read-guard enforcement."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

HOOK = "enforcement/hooks/_sahjhan_bootstrap.py"


def _run_hook(event: dict) -> dict:
    """Run the bootstrap hook with a given event dict, return parsed output."""
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


class TestReadGuard:
    """Tests for blocking Read tool on guarded paths."""

    def test_read_quiz_bank_blocked(self, tmp_path, monkeypatch):
        """Read tool targeting quiz-bank.json must be blocked."""
        # Create a mock guards response — in real use, sahjhan guards returns this.
        # For testing, we patch the guard list directly.
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "enforcement/quiz-bank.json"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "block", f"Expected block, got {decision}"

    def test_read_session_key_blocked(self, tmp_path):
        """Read tool targeting .sahjhan/session.key must be blocked."""
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/session.key"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "block"

    def test_read_normal_file_allowed(self, tmp_path):
        """Read tool on non-guarded paths must be allowed."""
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "allow"

    def test_bash_cat_quiz_bank_blocked(self, tmp_path):
        """Bash command referencing guarded path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/quiz-bank.json"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "block"

    def test_bash_python_open_session_key_blocked(self, tmp_path):
        """Bash python command reading session key must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "python3 -c \"print(open('docs/holtz/.sahjhan/session.key').read())\""
            },
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "block"

    def test_bash_without_guarded_path_allowed(self, tmp_path):
        """Bash command not referencing guarded paths must be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "allow"

    def test_path_traversal_blocked(self, tmp_path):
        """Read with ../traversal to guarded path must be blocked."""
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "hooks/../enforcement/quiz-bank.json"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "block"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

Expected: All tests FAIL (read-guard not yet implemented).

- [ ] **Step 3: Implement read-guard in _sahjhan_bootstrap.py**

In `enforcement/hooks/_sahjhan_bootstrap.py`, add the read-guard paths list and extend `main()`:

After the `PROTECTED` list (line 21), add:

```python
# Paths blocked from Read and Bash reading (populated from sahjhan guards or hardcoded fallback)
READ_GUARDED = [
    ".sahjhan/session.key",
    "enforcement/quiz-bank.json",
]
```

Replace the `main()` function with:

```python
def _resolve_path(path: str, cwd: str) -> str:
    """Resolve a path to absolute, handling relative paths and traversal."""
    if os.path.isabs(path):
        return os.path.realpath(path)
    return os.path.realpath(os.path.join(cwd, path))


def _is_read_guarded(path: str, cwd: str) -> str | None:
    """Check if a resolved path matches any read-guarded path. Returns the guard or None."""
    resolved = _resolve_path(path, cwd)
    for g in READ_GUARDED:
        # READ_GUARDED paths are relative to the data dir or plugin root
        for base in (os.path.join(cwd, "docs", "holtz"), _PLUGIN_ROOT, cwd):
            full = os.path.realpath(os.path.join(base, g))
            if resolved == full or resolved.startswith(full + os.sep):
                return g
    return None


def _bash_references_guarded(command: str, cwd: str) -> str | None:
    """Check if a Bash command references any read-guarded path."""
    for g in READ_GUARDED:
        # Check if the guarded path (or its basename) appears in the command
        if g in command:
            return g
        # Also check with docs/holtz prefix for .sahjhan paths
        if g.startswith(".sahjhan/"):
            full_rel = os.path.join("docs", "holtz", g)
            if full_rel in command:
                return g
    return None


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        event = {}

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")
    cwd = event.get("cwd", os.getcwd())

    # ── Read guard: block Read tool on guarded paths ──
    if tool_name == "Read" and path:
        guard = _is_read_guarded(path, cwd)
        if guard:
            _block(
                f"BLOCKED: Cannot read '{guard}'. "
                "This file is read-guarded enforcement infrastructure."
            )
            return

    # ── Read guard: block Bash commands that reference guarded paths ──
    if command:
        guard = _bash_references_guarded(command, cwd)
        if guard:
            _block(
                f"BLOCKED: Bash command references read-guarded path '{guard}'. "
                "This file cannot be accessed during an audit session."
            )
            return

    # ── Write guard: block Bash redirections/copies to PROTECTED paths ──
    if command and not path:
        for p in PROTECTED:
            for op in (">", ">>"):
                idx = command.find(op)
                if idx >= 0:
                    after_op = command[idx + len(op):].strip()
                    if after_op.startswith(p):
                        _block(
                            f"BLOCKED: Bash command redirects to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                        return
            if "tee " in command:
                tee_idx = command.find("tee ")
                after_tee = command[tee_idx + 4:].strip()
                if any(arg.startswith(p) for arg in after_tee.split()):
                    _block(
                        f"BLOCKED: Bash command tees to protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )
                    return
            cmd_stripped = command.lstrip()
            if any(cmd_stripped.startswith(c) for c in ("cp ", "mv ", "install ")):
                args = cmd_stripped.split()
                if len(args) >= 3:
                    dest = args[-1]
                    if dest.startswith(p):
                        _block(
                            f"BLOCKED: Bash command copies/moves to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                        return
        _allow()
        return

    if not path:
        _allow()
        return

    # ── Write guard: block Write/Edit to PROTECTED paths ──
    resolved = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(cwd, path))

    for p in PROTECTED:
        full = os.path.realpath(os.path.join(_PLUGIN_ROOT, p))
        if resolved == full or resolved.startswith(full + os.sep):
            _block(
                f"BLOCKED: {path} is protected enforcement infrastructure. "
                "This file cannot be modified during an audit session."
            )
            return

    _allow()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_bootstrap_read_guard.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run full suite to check for regressions**

```bash
python -m pytest tests/ -x --tb=short -q
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py tests/test_bootstrap_read_guard.py
git commit -m "feat(enforcement): add read-guard to _sahjhan_bootstrap.py

Blocks agent from reading quiz-bank.json and .sahjhan/session.key
via Read tool or Bash commands. Hooks can still read these files
directly via Python open() since they bypass Claude Code tools."
```

---

### Task 4: Add HMAC Helpers to enforcement/hooks/_common.py

**Files:**
- Modify: `enforcement/hooks/_common.py`
- Create: `tests/test_hmac_helpers.py`

- [ ] **Step 1: Write failing tests for HMAC helpers**

Create `tests/test_hmac_helpers.py`:

```python
"""Tests for HMAC event provenance helpers."""
from __future__ import annotations

import hashlib
import hmac
import os

import pytest


def test_compute_event_proof_deterministic(tmp_path):
    """Same inputs produce same proof."""
    # Create a fake session key
    key = b"test-key-32-bytes-exactly-here!!"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    # Import after setting up key
    from enforcement.hooks._common import compute_event_proof

    fields = {"project": "holtz", "run": "25", "auditor": "holtz", "perspective": "component"}
    proof1 = compute_event_proof("quiz_answered", fields, str(key_path))
    proof2 = compute_event_proof("quiz_answered", fields, str(key_path))
    assert proof1 == proof2
    assert len(proof1) == 64  # SHA-256 hex digest


def test_compute_event_proof_field_order_independent(tmp_path):
    """Field ordering must not affect the proof (sorted internally)."""
    key = b"test-key-32-bytes-exactly-here!!"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    from enforcement.hooks._common import compute_event_proof

    fields_a = {"z_field": "last", "a_field": "first"}
    fields_b = {"a_field": "first", "z_field": "last"}
    assert compute_event_proof("test_event", fields_a, str(key_path)) == \
           compute_event_proof("test_event", fields_b, str(key_path))


def test_compute_event_proof_matches_manual(tmp_path):
    """Proof must match manual HMAC-SHA256 computation."""
    key = b"known-key"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    from enforcement.hooks._common import compute_event_proof

    fields = {"auditor": "holtz", "project": "test"}
    proof = compute_event_proof("my_event", fields, str(key_path))

    # Manual computation: event_type\0field=value\0field=value (sorted)
    payload = "my_event\0auditor=holtz\0project=test"
    expected = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    assert proof == expected


def test_compute_event_proof_different_types_differ(tmp_path):
    """Different event types produce different proofs."""
    key = b"test-key-32-bytes-exactly-here!!"
    key_path = tmp_path / "session.key"
    key_path.write_bytes(key)

    from enforcement.hooks._common import compute_event_proof

    fields = {"project": "holtz"}
    proof_a = compute_event_proof("event_a", fields, str(key_path))
    proof_b = compute_event_proof("event_b", fields, str(key_path))
    assert proof_a != proof_b
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_hmac_helpers.py -v
```

Expected: FAIL with ImportError (functions don't exist yet).

- [ ] **Step 3: Implement HMAC helpers in _common.py**

In `enforcement/hooks/_common.py`, add after the `_active_ledger` function:

```python
def _get_session_key_path(cwd: str | None = None) -> str:
    """Find the session key path. Tries sahjhan config, falls back to default."""
    if cwd is None:
        cwd = os.getcwd()
    default = os.path.join(cwd, "docs", "holtz", ".sahjhan", "session.key")
    # Try sahjhan binary for canonical path
    try:
        from _resolve import sahjhan_binary
        binary = sahjhan_binary()
        if os.path.isfile(binary):
            import subprocess
            result = subprocess.run(
                [binary, "--config-dir", os.path.join(cwd, "enforcement"),
                 "config", "session-key-path"],
                capture_output=True, text=True, timeout=5, cwd=cwd,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except Exception:
        pass
    return default


def compute_event_proof(event_type: str, fields: dict[str, str], key_path: str | None = None) -> str:
    """Compute HMAC-SHA256 proof for a restricted event.

    Args:
        event_type: The event type name (e.g., "quiz_answered").
        fields: Dict of field name -> value pairs.
        key_path: Path to the session key file. If None, auto-discovers.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    import hashlib
    import hmac as hmac_mod

    if key_path is None:
        key_path = _get_session_key_path()
    with open(key_path, "rb") as f:
        key = f.read()
    parts = [event_type] + [f"{k}={v}" for k, v in sorted(fields.items())]
    payload = "\0".join(parts).encode()
    return hmac_mod.new(key, payload, hashlib.sha256).hexdigest()


def record_authed_event(
    event_type: str,
    fields: dict[str, str],
    cwd: str,
    ledger: str | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Record a restricted event with HMAC proof via sahjhan authed-event.

    Args:
        event_type: The restricted event type name.
        fields: Dict of field name -> value pairs.
        cwd: Working directory for the sahjhan command.
        ledger: Optional ledger name (e.g., "run-25").

    Returns:
        The CompletedProcess from the sahjhan call.
    """
    import subprocess
    from _resolve import sahjhan_binary

    key_path = _get_session_key_path(cwd)
    proof = compute_event_proof(event_type, fields, key_path)
    binary = sahjhan_binary()
    cmd = [binary, "--config-dir", os.path.join(cwd, "enforcement")]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["authed-event", event_type, "--proof", proof])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=10)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_hmac_helpers.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -x --tb=short -q
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/_common.py tests/test_hmac_helpers.py
git commit -m "feat(enforcement): add HMAC event provenance helpers

compute_event_proof() and record_authed_event() provide the foundation
for capability-restricted event recording. Hooks use these to record
restricted events that the agent cannot forge."
```

---

### Task 5: Update primer.py to Use Authenticated Events

**Files:**
- Modify: `enforcement/hooks/primer.py`

- [ ] **Step 1: Import record_authed_event in primer.py**

At `enforcement/hooks/primer.py` line 25, add `record_authed_event` to the import:

```python
from _common import _active_ledger, exit_ok, exit_warn, read_event, record_authed_event  # noqa: E402
```

- [ ] **Step 2: Replace context_reset event recording with authenticated version**

Find the section in `primer.py` where it records the `context_reset` event (search for `"context_reset"` in the file). Replace the `subprocess.run` call to `sahjhan event context_reset` with:

```python
    record_authed_event(
        "context_reset",
        {
            "project": os.path.basename(cwd),
            "run": run,
            "auditor": "holtz",
            "trigger": "user_prompt_submit",
        },
        cwd=cwd,
        ledger=ledger,
    )
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/primer.py
git commit -m "fix(enforcement): use authenticated events for context_reset in primer

context_reset is now a restricted event type. The primer hook records it
via record_authed_event() with HMAC proof, preventing the agent from
forging context reset events."
```

---

### Task 6: Update lens_quiz.py to Use Authenticated Events and Subagent Quiz Flow

**Files:**
- Modify: `enforcement/hooks/lens_quiz.py`

This is the largest single change. The quiz hook needs to:
1. Record `quiz_posed` and `quiz_answered` via `record_authed_event()`
2. Ensure the subagent (not the main agent) provides answers in its final message

- [ ] **Step 1: Add `record_authed_event` import**

At `enforcement/hooks/lens_quiz.py` line 30, add to the `_common` import:

```python
from _common import (  # noqa: E402
    _active_ledger,
    exit_stop_allow,
    exit_stop_block,
    read_event,
    record_authed_event,
)
```

- [ ] **Step 2: Replace `_record_event` calls with `record_authed_event`**

In the `main()` function (starting around line 267), find every call to `_record_event(binary, config_dir, cwd, ledger, event_type, fields)` and replace with `record_authed_event(event_type, fields, cwd, ledger)`.

Specifically, replace the `_record_event` call for `quiz_posed` (around line 358):

```python
        # Old:
        _record_event(binary, config_dir, cwd, ledger, "quiz_posed", {
            **base_fields, "questions_hash": qhash
        })

        # New:
        record_authed_event("quiz_posed", {
            **base_fields, "questions_hash": qhash
        }, cwd, ledger)
```

Replace all `_record_event` calls for `quiz_answered`, `quiz_failed`, and `quiz_exhausted` similarly. Search the file for `_record_event(binary, config_dir, cwd, ledger, "quiz_` and replace each one.

- [ ] **Step 3: Remove the now-unused `_record_event` function**

Delete the `_record_event` function (around lines 249-261) since all quiz events now go through `record_authed_event`.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```

Expected: All pass. The existing `lens_quiz` tests should still work since the external behavior (block/allow) hasn't changed — only the event recording pathway.

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/lens_quiz.py
git commit -m "feat(enforcement): use HMAC-authenticated events in lens_quiz.py

All quiz events (quiz_posed, quiz_answered, quiz_failed, quiz_exhausted)
are now recorded via record_authed_event() with HMAC proof. The agent
can no longer self-record quiz success events via sahjhan event."
```

---

### Task 7: Add New Gate Conditions to transitions.toml

**Files:**
- Modify: `enforcement/transitions.toml`

- [ ] **Step 1: Add quiz_posed gate to `set complete perspective`**

In the `set complete perspective` transition (line 108-122), add a new gate after the existing `quiz_answered` gate:

```toml
    { type = "query", sql = "SELECT count(*) >= 1 FROM events WHERE type='quiz_posed' AND perspective='{{current_perspective}}'", expect = "true", intent = "quiz must be posed by enforcement hook before completion" },
```

- [ ] **Step 2: Add lens_sweep_started gate to `set complete perspective`**

In the same transition block, add:

```toml
    { type = "ledger_has_event_since", event = "lens_sweep_started", filter = { perspective = "{{current_perspective}}" }, since = "last_event_of_type:set_member_complete", intent = "a lens sweep must be started for this perspective before completion" },
```

- [ ] **Step 3: Add merge_agent_dispatched gate to `merge_complete`**

In the `merge_complete` transition (line 34-40), add to the gates array:

```toml
    { type = "ledger_has_event", event = "merge_agent_dispatched", min_count = 1, intent = "merge must be performed by a separate merge-agent subagent" },
```

- [ ] **Step 4: Add recon ordering gate to `recon_complete`**

In the `recon_complete` transition (line 9-19), add to the gates array:

```toml
    { type = "ledger_lacks_event", event = "finding", filter = { phase = "audit" }, intent = "no audit-phase findings should exist before recon is complete" },
```

- [ ] **Step 5: Add final sweep read threshold gate to `converge`**

In the `converge` transition (line 149-161), add:

```toml
    { type = "command_succeeds", cmd = "python enforcement/scripts/check_sweep_evidence.py --min-reads 30", timeout = 15, intent = "final sweep must demonstrate substantive code reading" },
```

- [ ] **Step 6: Commit**

```bash
git add enforcement/transitions.toml
git commit -m "feat(enforcement): add 5 new gate conditions for protocol integrity

- quiz_posed required before lens completion (closes quiz bypass)
- lens_sweep_started required before lens completion (blocks batch-marking)
- merge_agent_dispatched required before merge_complete (forces merge agent)
- ledger_lacks_event finding(phase=audit) on recon_complete (ordering)
- check_sweep_evidence on converge (minimum read threshold)"
```

---

### Task 8: Unconditional Commit Blocking in fix_loop State

**Files:**
- Modify: `enforcement/hooks/commit_gate.py`
- Modify: `enforcement/hooks/_protocol_cache.py`

- [ ] **Step 1: Add `is_fix_loop_state` helper to _protocol_cache.py**

In `enforcement/hooks/_protocol_cache.py`, after the `is_sahjhan_cmd` function (line 181), add:

```python
def is_fix_loop_state(cache: dict[str, Any] | None) -> bool:
    """Check if the current protocol state is fix_loop."""
    if cache is None:
        return False
    return cache.get("state") == "fix_loop"
```

- [ ] **Step 2: Add unconditional commit blocking in commit_gate.py**

In `enforcement/hooks/commit_gate.py`, add the import:

```python
from _protocol_cache import (  # noqa: E402
    compute_obligations,
    format_injection,
    is_git_commit,
    is_fix_loop_state,
    is_sahjhan_cmd,
    read_cache,
)
```

Then in `main()`, after `cache = read_cache(cwd)` (line 42), add:

```python
    # Unconditional: in fix_loop, git commit requires prior fix_commit registration
    if cache and is_fix_loop_state(cache) and is_git_commit(cmd):
        commits = cache.get("unregistered_commits", [])
        if commits:
            exit_block(
                f"BLOCKED: {len(commits)} unregistered commit(s). "
                "Run sahjhan transition fix_commit before committing again."
            )
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_commit_gate.py tests/test_protocol_cache.py -v
```

Expected: Pass (existing tests should still work; new behavior only triggers in fix_loop with unregistered commits).

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/commit_gate.py enforcement/hooks/_protocol_cache.py
git commit -m "fix(enforcement): unconditional commit blocking in fix_loop state

During fix_loop, git commit is now always blocked if prior commits are
unregistered with sahjhan fix_commit. Previously this only triggered
when obligation-based blocking was active."
```

---

### Task 9: Create check_sweep_evidence.py Script

**Files:**
- Create: `enforcement/scripts/check_sweep_evidence.py`
- Create: `tests/test_sweep_evidence.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sweep_evidence.py`:

```python
"""Tests for check_sweep_evidence.py — final sweep read threshold."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

SCRIPT = "enforcement/scripts/check_sweep_evidence.py"


def _make_transcript(tmp_path, read_count: int) -> str:
    """Create a fake session JSONL with N distinct file reads."""
    transcript = tmp_path / "transcript.jsonl"
    lines = []
    for i in range(read_count):
        entry = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": f"src/file_{i}.py"},
                    }
                ]
            },
        }
        lines.append(json.dumps(entry))
    transcript.write_text("\n".join(lines))
    return str(transcript)


def test_below_threshold_fails(tmp_path):
    """Fewer than min_reads distinct reads should fail."""
    transcript = _make_transcript(tmp_path, 10)
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "30", "--transcript", transcript],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_above_threshold_passes(tmp_path):
    """Meeting min_reads should pass."""
    transcript = _make_transcript(tmp_path, 35)
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "30", "--transcript", transcript],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_duplicate_reads_not_double_counted(tmp_path):
    """Reading the same file twice counts as one distinct read."""
    transcript = tmp_path / "transcript.jsonl"
    lines = []
    for _ in range(40):
        entry = {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "src/same.py"}}]
            },
        }
        lines.append(json.dumps(entry))
    transcript.write_text("\n".join(lines))
    result = subprocess.run(
        [sys.executable, SCRIPT, "--min-reads", "2", "--transcript", str(transcript)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0  # only 1 distinct file
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sweep_evidence.py -v
```

Expected: FAIL (script doesn't exist).

- [ ] **Step 3: Create the script**

Create `enforcement/scripts/check_sweep_evidence.py`:

```python
#!/usr/bin/env python3
"""Check that the final sweep has sufficient distinct file reads.

Used as a gate condition on the 'converge' transition to prevent
lightweight final sweeps from passing convergence.

Usage: python check_sweep_evidence.py --min-reads 30 [--transcript PATH]
Exit 0 if threshold met, exit 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def count_distinct_reads(transcript_path: str) -> int:
    """Count distinct file paths read in a transcript JSONL."""
    files_read: set[str] = set()
    if not os.path.isfile(transcript_path):
        return 0
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Handle nested message.content format (session JSONL)
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("name") == "Read":
                        fp = block.get("input", {}).get("file_path", "")
                        if fp:
                            files_read.add(fp)
            # Handle flat tool_use format
            if entry.get("type") == "tool_use" and entry.get("name") == "Read":
                fp = entry.get("input", {}).get("file_path", "")
                if fp:
                    files_read.add(fp)
    return len(files_read)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check sweep evidence")
    parser.add_argument("--min-reads", type=int, default=30)
    parser.add_argument("--transcript", default=None,
                        help="Path to transcript JSONL. Auto-discovers if omitted.")
    args = parser.parse_args()

    if args.transcript:
        transcript = args.transcript
    else:
        # Auto-discover from Claude Code session directory
        cwd = os.getcwd()
        # Look for the most recent session JSONL
        claude_dir = os.path.expanduser("~/.claude")
        # Fallback: check environment
        transcript = os.environ.get("CLAUDE_SESSION_TRANSCRIPT", "")
        if not transcript or not os.path.isfile(transcript):
            print(f"FAIL: No transcript found. Cannot verify sweep evidence.", file=sys.stderr)
            sys.exit(1)

    distinct = count_distinct_reads(transcript)
    if distinct >= args.min_reads:
        print(f"PASS: {distinct} distinct file reads (threshold: {args.min_reads})")
        sys.exit(0)
    else:
        print(f"FAIL: {distinct} distinct file reads (threshold: {args.min_reads})", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sweep_evidence.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add enforcement/scripts/check_sweep_evidence.py tests/test_sweep_evidence.py
git commit -m "feat(enforcement): add check_sweep_evidence.py for final sweep gate

Counts distinct file reads in the conversation transcript. Used as a
gate condition on the 'converge' transition to prevent lightweight
single-subagent final sweeps from passing convergence."
```

---

### Task 10: Run Full Suite and Verify

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite with coverage**

```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks --cov-report=term-missing --cov-fail-under=60
```

Expected: All pass, coverage >= 60%.

- [ ] **Step 2: Run linter**

```bash
ruff check .
```

Expected: Clean.

- [ ] **Step 3: Run type checker**

```bash
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

Expected: Clean.

- [ ] **Step 4: Verify Sahjhan integration**

```bash
bin/sahjhan --config-dir enforcement guards
bin/sahjhan --config-dir enforcement event quiz_answered --field score=5/5 --field pass=true 2>&1 | head -1
```

Expected: `guards` returns JSON with read_blocked paths. `event quiz_answered` returns error about restricted event type.


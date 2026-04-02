# Freshness-Gated Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix issue #24 (stop hook timeout) and prevent stale enforcement state from poisoning non-Holtz sessions by gating all enforcement hooks on sahjhan activity freshness.

**Architecture:** Add a `last_sahjhan_cmd` timestamp to the enforcement cache, updated only on sahjhan commands. A shared `is_enforcement_fresh()` function checks this timestamp against a 30-minute threshold. All enforcement hooks call this function first — if stale, they stand down. The stop hook additionally replaces its `sahjhan status` subprocess call with a direct cache read, eliminating the timeout root cause.

**Tech Stack:** Python 3.11+, pytest, subprocess hooks (Claude Code hook protocol)

---

### Task 1: Add `last_sahjhan_cmd` and `is_enforcement_fresh()` to `_protocol_cache.py`

**Files:**
- Modify: `enforcement/hooks/_protocol_cache.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write tests for `is_enforcement_fresh()`**

Add to the `TestProtocolCache` class in `tests/test_protocol_enforcement.py`:

```python
class TestEnforcementFreshness:
    """Tests for is_enforcement_fresh() — sahjhan activity freshness check."""

    def test_none_cache_is_not_fresh(self):
        from _protocol_cache import is_enforcement_fresh
        assert is_enforcement_fresh(None) is False

    def test_missing_field_is_not_fresh(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        cache = empty_cache()
        # empty_cache has no last_sahjhan_cmd yet — should be not fresh
        assert is_enforcement_fresh(cache) is False

    def test_recent_timestamp_is_fresh(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        from datetime import datetime, timezone
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        assert is_enforcement_fresh(cache) is True

    def test_stale_timestamp_is_not_fresh(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        from datetime import datetime, timedelta, timezone
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = (
            datetime.now(timezone.utc) - timedelta(minutes=45)
        ).isoformat()
        assert is_enforcement_fresh(cache) is False

    def test_exactly_at_threshold_is_fresh(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        from datetime import datetime, timedelta, timezone
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = (
            datetime.now(timezone.utc) - timedelta(minutes=29)
        ).isoformat()
        assert is_enforcement_fresh(cache) is True

    def test_custom_threshold(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        from datetime import datetime, timedelta, timezone
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        ).isoformat()
        assert is_enforcement_fresh(cache, threshold_minutes=5) is False
        assert is_enforcement_fresh(cache, threshold_minutes=15) is True

    def test_garbage_timestamp_is_not_fresh(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = "not-a-timestamp"
        assert is_enforcement_fresh(cache) is False

    def test_empty_string_is_not_fresh(self):
        from _protocol_cache import is_enforcement_fresh, empty_cache
        cache = empty_cache()
        cache["last_sahjhan_cmd"] = ""
        assert is_enforcement_fresh(cache) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestEnforcementFreshness -v`
Expected: FAIL — `is_enforcement_fresh` does not exist yet.

- [ ] **Step 3: Implement `is_enforcement_fresh()` and update `empty_cache()`**

In `enforcement/hooks/_protocol_cache.py`, add at the top of the file (after imports):

```python
_ENFORCEMENT_FRESHNESS_MINUTES = 30
```

Update `empty_cache()` to include the new field:

```python
def empty_cache() -> dict[str, Any]:
    return {
        "active": True,
        "state": "",
        "unregistered_commits": [],
        "fixes_since_pattern": 0,
        "perspective": "",
        "perspectives_done": 0,
        "perspectives_total": _read_perspectives_total(),
        "stall": 0,
        "last_refresh": "",
        "last_sahjhan_cmd": "",
    }
```

Add the function after `write_cache()`:

```python
def is_enforcement_fresh(
    cache: dict[str, Any] | None,
    threshold_minutes: int = _ENFORCEMENT_FRESHNESS_MINUTES,
) -> bool:
    """Check if enforcement should be active based on sahjhan command recency.

    Returns True if a sahjhan command was run within the threshold window,
    indicating an active audit session. Returns False if the cache is
    missing, the timestamp is absent/unparseable, or the timestamp is stale.
    """
    if cache is None:
        return False
    ts = cache.get("last_sahjhan_cmd", "")
    if not ts:
        return False
    try:
        from datetime import datetime, timedelta, timezone
        last = datetime.fromisoformat(ts)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
        return last >= cutoff
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestEnforcementFreshness -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_protocol_cache.py tests/test_protocol_enforcement.py
git commit -m "feat(hooks): add is_enforcement_fresh() and last_sahjhan_cmd field"
```

---

### Task 2: Update `protocol_tracker.py` to write `last_sahjhan_cmd`

**Files:**
- Modify: `enforcement/hooks/protocol_tracker.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write test for `last_sahjhan_cmd` update on sahjhan commands**

Add to `TestProtocolTracker` in `tests/test_protocol_enforcement.py`:

```python
    def test_sahjhan_cmd_updates_last_sahjhan_cmd(self, tmp_path):
        """Sahjhan commands update last_sahjhan_cmd timestamp."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop (10 events, chain valid)"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated is not None
        assert updated.get("last_sahjhan_cmd"), "last_sahjhan_cmd should be set"
        # Verify it's a valid ISO timestamp
        from datetime import datetime
        datetime.fromisoformat(updated["last_sahjhan_cmd"])

    def test_non_sahjhan_cmd_does_not_update_last_sahjhan_cmd(self, tmp_path):
        """Regular bash commands do NOT update last_sahjhan_cmd."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2026-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"exit_code": 0, "output": "total 0"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["last_sahjhan_cmd"] == "2026-01-01T00:00:00+00:00"

    def test_git_commit_does_not_update_last_sahjhan_cmd(self, tmp_path):
        """Git commits do NOT update last_sahjhan_cmd."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2026-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: stuff'"},
            "tool_response": {"exit_code": 0, "output": "[dev abc1234] fix: stuff"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["last_sahjhan_cmd"] == "2026-01-01T00:00:00+00:00"
```

- [ ] **Step 2: Run tests to verify the first test fails**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolTracker::test_sahjhan_cmd_updates_last_sahjhan_cmd -v`
Expected: FAIL — `last_sahjhan_cmd` is empty string (the default from `empty_cache()`).

- [ ] **Step 3: Update `protocol_tracker.py` to set `last_sahjhan_cmd`**

In `enforcement/hooks/protocol_tracker.py`, add an import at the top (after existing imports from `_protocol_cache`):

```python
from datetime import datetime, timezone
```

In the `is_sahjhan_cmd(cmd)` branch of `main()`, add one line before `write_cache`:

```python
    if is_sahjhan_cmd(cmd):
        if cache is None:
            cache = empty_cache()
        cache = _refresh_from_sahjhan(cwd, cache)
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        # BH-017: match subcommand tokens, not substrings of full command
        tokens = cmd.split()
```

The rest of the function remains unchanged.

- [ ] **Step 4: Also add stale-enforcement early exit**

In `protocol_tracker.py`, add an import:

```python
from _protocol_cache import (  # noqa: E402
    empty_cache,
    is_enforcement_fresh,
    is_git_commit,
    is_sahjhan_cmd,
    parse_status_text,
    read_cache,
    write_cache,
)
```

Then after the `cache = read_cache(cwd)` line and the `is_sahjhan_cmd` branch, update the `if cache is None` block:

```python
    if cache is None:
        exit_ok()

    # Stale enforcement: don't track stall for abandoned audits
    if not is_enforcement_fresh(cache):
        exit_ok()
```

- [ ] **Step 5: Write test for stale-enforcement early exit**

Add to `TestProtocolTracker`:

```python
    def test_stale_enforcement_skips_stall(self, tmp_path):
        """When enforcement is stale, protocol_tracker does not increment stall."""
        from _protocol_cache import empty_cache, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat some_file.py"},
            "tool_response": {"exit_code": 0, "output": "contents"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["stall"] == 5, "Stall should not increment when enforcement is stale"

    def test_stale_enforcement_still_allows_sahjhan(self, tmp_path):
        """Even with stale enforcement, sahjhan commands reactivate tracking."""
        from _protocol_cache import empty_cache, is_enforcement_fresh, read_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop (10 events, chain valid)"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert is_enforcement_fresh(updated), "Sahjhan command should reactivate freshness"
```

- [ ] **Step 6: Run all tracker tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolTracker -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/protocol_tracker.py tests/test_protocol_enforcement.py
git commit -m "feat(hooks): track last_sahjhan_cmd timestamp, skip stall on stale enforcement"
```

---

### Task 3: Rewrite `stop_hook.py` to use cache + freshness

**Files:**
- Modify: `enforcement/hooks/stop_hook.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write tests for the new stop hook behavior**

Add a new test class to `tests/test_protocol_enforcement.py`:

```python
class TestStopHookFreshness:
    """Tests for stop_hook.py freshness-gated enforcement (issue #24)."""

    def test_allows_stop_when_no_sahjhan_dir(self):
        """No .sahjhan directory → allow stop immediately."""
        event = {"cwd": "/tmp/no-audit-here"}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}  # no output = allow

    def test_blocks_stop_in_active_audit(self, tmp_path):
        """Active audit (fresh enforcement, non-terminal state) → block."""
        from _protocol_cache import empty_cache, write_cache
        from datetime import datetime, timezone
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        # Create .sahjhan dir (write_cache creates it, but ensure it exists)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output.get("decision") == "block"
        assert "fix_loop" in output.get("reason", "")

    def test_warns_stop_in_stale_audit(self, tmp_path):
        """Stale audit (old last_sahjhan_cmd, non-terminal state) → warn, allow."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output.get("decision") == "approve"
        assert "stale" in output.get("reason", "").lower() or "abandoned" in output.get("reason", "").lower()

    def test_allows_stop_in_terminal_state(self, tmp_path):
        """Terminal state (finalized) → allow stop regardless of freshness."""
        from _protocol_cache import empty_cache, write_cache
        from datetime import datetime, timezone
        cache = empty_cache()
        cache["state"] = "finalized"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}  # no output = allow

    def test_allows_stop_in_idle_state(self, tmp_path):
        """Idle state → allow stop regardless of freshness."""
        from _protocol_cache import empty_cache, write_cache
        from datetime import datetime, timezone
        cache = empty_cache()
        cache["state"] = "idle"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        assert output == {}

    def test_warns_when_no_cache_but_sahjhan_dir_exists(self, tmp_path):
        """Has .sahjhan dir but no enforcement cache → warn (not block)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert code == 0
        # Should warn (approve) not block — we can't determine state
        assert output.get("decision") in ("approve", None)

    def test_block_message_includes_available_transitions(self, tmp_path):
        """Block message should indicate what transitions are available."""
        from _protocol_cache import empty_cache, write_cache
        from datetime import datetime, timezone
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event)
        assert output.get("decision") == "block"
        reason = output.get("reason", "")
        assert "not terminal" in reason.lower() or "fix_loop" in reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness -v`
Expected: Most will FAIL because stop_hook.py still uses the subprocess approach.

- [ ] **Step 3: Rewrite `stop_hook.py`**

Replace the contents of `enforcement/hooks/stop_hook.py`:

```python
#!/usr/bin/env python3
"""Sahjhan stop hook — blocks stop in non-terminal audit states.

Stop hook. Two enforcement layers:
1. Cache-based state check: reads enforcement-cache.json directly
   (no subprocess, no timeout — fixes issue #24)
2. Freshness gate: only blocks when enforcement is fresh (sahjhan
   was used recently). Stale enforcement = abandoned audit, allow
   stop with a warning.

Falls back to WARN if sahjhan config is unavailable during an
active audit. See: holtz issue #19.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402

from _common import (  # noqa: E402
    exit_stop_allow,
    exit_stop_block,
    exit_stop_warn,
    read_event,
)

_STOP_ALLOWED_STATES = {"idle", "finalized", ""}


def _has_active_audit(cwd: str) -> bool:
    """Check if there's an active Sahjhan audit (data dir exists)."""
    return os.path.isdir(os.path.join(cwd, "docs", "holtz", ".sahjhan"))


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    # No active run — allow stop
    if not _has_active_audit(cwd):
        exit_stop_allow()

    # Read enforcement cache directly (no subprocess, no timeout)
    cache = read_cache(cwd)

    if cache is None:
        # .sahjhan dir exists but no enforcement cache — can't determine state
        exit_stop_warn(
            "WARNING: Sahjhan data directory exists but enforcement cache is missing. "
            "Enforcement state unknown. Run `sahjhan status` manually to check."
        )

    current_state = cache.get("state", "")

    # Terminal or idle — allow stop
    if current_state in _STOP_ALLOWED_STATES:
        exit_stop_allow()

    # Non-terminal state: check freshness
    if not is_enforcement_fresh(cache):
        exit_stop_warn(
            f"Stale Holtz audit detected (state: '{current_state}'). "
            "No recent sahjhan activity — this appears to be an abandoned audit. "
            "Consider cleaning up docs/holtz/.sahjhan/ if the audit is no longer needed."
        )

    # Active audit, non-terminal state — block
    exit_stop_block(
        f"Audit is in state '{current_state}' which is not terminal. "
        "You must complete the audit protocol before stopping."
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run stop hook tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness -v`
Expected: All tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/test_protocol_enforcement.py -v`
Expected: All tests PASS. Some existing stop hook tests in `test_sahjhan_integration.py` may need updating if they test the old subprocess-based flow — check and fix.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_protocol_enforcement.py
git commit -m "fix(hooks): rewrite stop_hook to use cache + freshness gate (fixes #24)"
```

---

### Task 4: Gate `commit_gate.py` on enforcement freshness

**Files:**
- Modify: `enforcement/hooks/commit_gate.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write test for stale enforcement passthrough**

Add to `TestCommitGate` in `tests/test_protocol_enforcement.py`:

```python
    def test_allows_commit_when_enforcement_stale(self, tmp_path):
        """Stale enforcement → commit gate passes through, no blocking."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "git commit -m 'fix: next'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_allows_all_bash_when_enforcement_stale(self, tmp_path):
        """Stale enforcement → even stall > 15 doesn't block."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 20
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestCommitGate::test_allows_commit_when_enforcement_stale tests/test_protocol_enforcement.py::TestCommitGate::test_allows_all_bash_when_enforcement_stale -v`
Expected: FAIL — commit_gate still blocks regardless of freshness.

- [ ] **Step 3: Add freshness gate to `commit_gate.py`**

In `enforcement/hooks/commit_gate.py`, update the import from `_protocol_cache`:

```python
from _protocol_cache import (  # noqa: E402
    compute_obligations,
    format_injection,
    is_enforcement_fresh,
    is_fix_loop_state,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache,
)
```

Add the freshness check early in `main()`, after reading the cache and before any enforcement logic:

```python
def main() -> None:
    event = read_event()
    cmd = event.get("tool_input", {}).get("command", "")
    cwd = event.get("cwd", os.getcwd())

    cache = read_cache(cwd)

    # Sahjhan commands are always allowed
    if is_sahjhan_cmd(cmd):
        exit_ok("PreToolUse")

    # Stale enforcement: pass through without blocking
    if not is_enforcement_fresh(cache):
        exit_ok("PreToolUse")

    # Unconditional: in fix_loop, git commit requires prior fix_commit registration
    # ... rest of existing logic unchanged ...
```

- [ ] **Step 4: Run all commit gate tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestCommitGate -v`
Expected: All tests PASS.

Note: The existing tests that expect blocking behavior (e.g., `test_blocks_commit_with_unregistered`) use `write_cache` which sets `last_refresh` but NOT `last_sahjhan_cmd`. They'll need updating — add a fresh `last_sahjhan_cmd` to the cache setup in each existing blocking test:

```python
from datetime import datetime, timezone
cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/commit_gate.py tests/test_protocol_enforcement.py
git commit -m "feat(hooks): gate commit_gate on enforcement freshness"
```

---

### Task 5: Gate `primer.py` on enforcement freshness

**Files:**
- Modify: `enforcement/hooks/primer.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write test for stale enforcement passthrough**

Add a new test class to `tests/test_protocol_enforcement.py`:

```python
class TestPrimerFreshness:
    """Tests for primer.py freshness gate."""

    def test_primer_exits_early_when_stale(self, tmp_path):
        """Stale enforcement → primer does not inject context."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"  # very stale
        write_cache(str(tmp_path), cache)

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("primer.py", event)
        assert code == 0
        # Should pass through silently — no context injection
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPrimerFreshness -v`
Expected: FAIL — primer still injects context regardless of freshness (or may fail due to missing sahjhan binary; either way the test captures the intent).

- [ ] **Step 3: Add freshness gate to `primer.py`**

In `enforcement/hooks/primer.py`, add import:

```python
from _protocol_cache import format_state_line, parse_status_text  # noqa: E402
from _protocol_cache import is_enforcement_fresh  # noqa: E402
from _protocol_cache import read_cache as read_enforcement_cache
```

Add freshness check after the `.sahjhan` directory check:

```python
    # No active run — nothing to inject
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Stale enforcement: don't inject context for abandoned audits
    cache = read_enforcement_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok()

    # Get current status
    # ... rest unchanged ...
```

- [ ] **Step 4: Run primer tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPrimerFreshness tests/test_protocol_enforcement.py::TestPrimerStateLine -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_protocol_enforcement.py
git commit -m "feat(hooks): gate primer on enforcement freshness"
```

---

### Task 6: Gate remaining hooks (`pre_tool_hook.py`, `post_tool_hook.py`, `bash_guard.py`)

**Files:**
- Modify: `enforcement/hooks/pre_tool_hook.py`
- Modify: `enforcement/hooks/post_tool_hook.py`
- Modify: `enforcement/hooks/bash_guard.py`
- Test: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Write tests for all three hooks**

Add to `tests/test_protocol_enforcement.py`:

```python
class TestRemainingHooksFreshness:
    """Tests for freshness gate on pre_tool_hook, post_tool_hook, bash_guard."""

    def test_pre_tool_hook_skips_eval_when_stale(self, tmp_path):
        """Stale enforcement → pre_tool_hook skips hook eval but keeps managed-path guard."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "main.py")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_pre_tool_hook_still_guards_managed_paths_when_stale(self, tmp_path):
        """Managed-path guard is always active, even when stale."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        # Try to write to a managed file (STATUS.md)
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "STATUS.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"

    def test_post_tool_hook_exits_early_when_stale(self, tmp_path):
        """Stale enforcement → post_tool_hook does nothing."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.py"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("post_tool_hook.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_bash_guard_exits_early_when_stale(self, tmp_path):
        """Stale enforcement → bash_guard does not verify manifest."""
        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["last_sahjhan_cmd"] = "2025-01-01T00:00:00+00:00"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("bash_guard.py", event)
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestRemainingHooksFreshness -v`
Expected: Some will FAIL (hooks still run without freshness check). The managed-path guard test should already PASS since that guard doesn't depend on freshness.

- [ ] **Step 3: Add freshness gate to `pre_tool_hook.py`**

In `enforcement/hooks/pre_tool_hook.py`, add import:

```python
from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402
```

Add freshness check after the managed-path guard block and before the binary/hook-eval logic:

```python
    # ── Managed-path guard (no binary required) ──
    # ... existing managed-path guard code ...

    # Stale enforcement: skip hook eval for abandoned audits
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok("PreToolUse")

    binary = ensure_sahjhan()
    # ... rest unchanged ...
```

- [ ] **Step 4: Add freshness gate to `post_tool_hook.py`**

In `enforcement/hooks/post_tool_hook.py`, add import:

```python
from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: E402
```

Add freshness check early in `main()`, after reading `cwd`:

```python
def main() -> None:
    event = read_event()
    tool_name = event.get("tool_name", event.get("tool", ""))
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    # Stale enforcement: skip event recording for abandoned audits
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok()

    binary = ensure_sahjhan()
    # ... rest unchanged ...
```

- [ ] **Step 5: Add freshness gate to `bash_guard.py`**

In `enforcement/hooks/bash_guard.py`, add import:

```python
from _protocol_cache import is_enforcement_fresh, is_sahjhan_cmd, read_cache  # noqa: E402
```

Add freshness check after the `.sahjhan` directory check:

```python
    # Check if there's an active Sahjhan run (data dir exists)
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_ok()

    # Stale enforcement: skip manifest verification for abandoned audits
    cache = read_cache(cwd)
    if not is_enforcement_fresh(cache):
        exit_ok()

    ledger = _active_ledger(cwd)
    # ... rest unchanged ...
```

- [ ] **Step 6: Run all freshness tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestRemainingHooksFreshness -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/pre_tool_hook.py enforcement/hooks/post_tool_hook.py enforcement/hooks/bash_guard.py tests/test_protocol_enforcement.py
git commit -m "feat(hooks): gate pre_tool_hook, post_tool_hook, bash_guard on enforcement freshness"
```

---

### Task 7: Update existing tests that set up enforcement cache

**Files:**
- Modify: `tests/test_protocol_enforcement.py`
- Modify: `tests/test_sahjhan_integration.py` (if needed)

- [ ] **Step 1: Find and fix tests that create caches without `last_sahjhan_cmd`**

Existing tests that set up enforcement cache with `write_cache` and expect blocking behavior will now pass through (because `is_enforcement_fresh` returns False when `last_sahjhan_cmd` is missing). These tests need a fresh timestamp added.

Search for all tests in `test_protocol_enforcement.py` and `test_sahjhan_integration.py` that call `write_cache` and expect blocking. Add this to each cache setup:

```python
from datetime import datetime, timezone
cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
```

Affected tests (in `TestCommitGate`):
- `test_blocks_commit_with_unregistered`
- `test_blocks_on_stall`
- `test_blocks_commit_when_pattern_overdue`
- `test_injects_soft_obligation_non_commit_cmd`

Affected tests (in `TestEnforcementIntegration`):
- `test_commit_blocked_after_unregistered`
- `test_stall_blocks_all`
- `test_tracker_then_gate_full_cycle`
- `test_fix_commit_substring_not_triggered_by_option`

Affected tests (in `TestProtocolTracker`):
- `test_increments_stall_counter`
- `test_tdd_commands_skip_stall`

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/test_protocol_enforcement.py -v`
Expected: All PASS.

- [ ] **Step 3: Run tests in `test_sahjhan_integration.py` too**

Run: `python -m pytest tests/test_sahjhan_integration.py -v`
Expected: All PASS. If any enforcement-cache-related tests fail, apply the same `last_sahjhan_cmd` fix.

- [ ] **Step 4: Commit**

```bash
git add tests/test_protocol_enforcement.py tests/test_sahjhan_integration.py
git commit -m "test(hooks): update existing tests to include last_sahjhan_cmd for freshness gate"
```

---

### Task 8: Full regression test and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run the full test suite with coverage**

Run: `python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60`
Expected: All PASS, coverage above 60%.

- [ ] **Step 2: Run linting**

Run: `ruff check .`
Expected: No errors.

- [ ] **Step 3: Run type checking**

Run: `mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: No errors.

- [ ] **Step 4: Commit any fixups**

If any lint/type/test issues were found, fix and commit:

```bash
git commit -m "fix(hooks): address lint/type issues from freshness gate changes"
```

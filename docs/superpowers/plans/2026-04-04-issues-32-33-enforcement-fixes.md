# Issues #32 & #33: Enforcement Deadlock & Bypass Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `awaiting_clear` deadlock (#32) and close the enforcement bypass via Bash-mediated writes/deletes (#33).

**Architecture:** Two independent fixes sharing no code paths. #32 is a one-line allowlist change in `stop_hook.py` plus test updates. #33 adds `rm`/`rmdir` detection and `.sahjhan/` path protection to `_sahjhan_bootstrap.py`. Both are defense-in-depth hardening of the existing PreToolUse hook chain.

**Tech Stack:** Python 3.10+, pytest, existing hook infrastructure (`_sahjhan_bootstrap.py`, `stop_hook.py`)

---

## File Map

| File | Change | Purpose |
|------|--------|---------|
| `enforcement/hooks/stop_hook.py` | Modify line 30 | Add `awaiting_clear` to `_STOP_ALLOWED_STATES` |
| `enforcement/hooks/_sahjhan_bootstrap.py` | Modify `ALL_PROTECTED`, `_check_bash_write()` | Add `.sahjhan/` dir protection + `rm`/`rmdir` blocking |
| `tests/test_sahjhan_integration.py` | Modify `TestStopHook`, `TestBootstrapHook` | Update parametrized stop tests, add rm/rmdir tests |
| `tests/test_protocol_enforcement.py` | Modify `TestStopHookFreshness` | Add `awaiting_clear` allowed test |

---

### Task 1: Fix #32 — Add `awaiting_clear` to stop-allowed states

**Files:**
- Modify: `enforcement/hooks/stop_hook.py:30`
- Modify: `tests/test_sahjhan_integration.py:1016-1033` (TestStopHook parametrize)
- Modify: `tests/test_protocol_enforcement.py:865+` (TestStopHookFreshness)

- [ ] **Step 1: Write the failing test — stop hook should ALLOW in awaiting_clear**

In `tests/test_protocol_enforcement.py`, add a test to `TestStopHookFreshness`:

```python
def test_allows_stop_in_awaiting_clear_state(self, tmp_path):
    """Issue #32: awaiting_clear is a stop-allowed state — agent must be able to stop."""
    from datetime import datetime, timezone

    from _protocol_cache import empty_cache, write_cache
    cache = empty_cache()
    cache["state"] = "awaiting_clear"
    cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()
    write_cache(str(tmp_path), cache)

    event = {"cwd": str(tmp_path)}
    code, output, _ = run_enforcement_hook("stop_hook.py", event)
    assert code == 0
    assert output == {}  # no output = allow
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness::test_allows_stop_in_awaiting_clear_state -v`
Expected: FAIL — output contains `{"decision": "block", ...}` instead of `{}`

- [ ] **Step 3: Fix stop_hook.py — add awaiting_clear to allowed states**

In `enforcement/hooks/stop_hook.py` line 30, change:

```python
_STOP_ALLOWED_STATES = {"idle", "finalized", ""}
```

to:

```python
_STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestStopHookFreshness::test_allows_stop_in_awaiting_clear_state -v`
Expected: PASS

- [ ] **Step 5: Update existing parametrized test that expects awaiting_clear to block**

In `tests/test_sahjhan_integration.py`, the `TestStopHook.test_blocks_in_non_terminal_non_active_states` parametrize list at line 1016-1019 includes `"awaiting_clear"`. Remove it from that list:

```python
@pytest.mark.parametrize("state", [
    "recon", "merge_ready", "merge_done",
    "perspective_clean", "all_perspectives_clean",
    "final_sweep_clean", "converged",
])
```

Then add a new test method to `TestStopHook` that verifies `awaiting_clear` is allowed:

```python
def test_allows_in_awaiting_clear_state(self, tmp_path):
    """Issue #32: awaiting_clear is designed for agent stop — must be allowed."""
    self._setup_active_audit(tmp_path, "awaiting_clear")
    event = {"cwd": str(tmp_path)}
    code, output, _ = run_enforcement_hook(
        "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
    )
    assert code == 0
    assert output.get("decision") != "block", (
        f"awaiting_clear should allow stop but got: {output}"
    )
```

- [ ] **Step 6: Run full stop hook test suite**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestStopHook tests/test_protocol_enforcement.py::TestStopHookFreshness -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_sahjhan_integration.py tests/test_protocol_enforcement.py
git commit -m "fix(enforcement): add awaiting_clear to stop-allowed states

The awaiting_clear state is designed for the agent to stop and yield
control to the user. Blocking stop in this state created an
unrecoverable deadlock (issue #32).

Closes #32"
```

---

### Task 2: Fix #33 — Protect .sahjhan directory from Bash-mediated writes/deletes

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py` (lines 18-36 + `_check_bash_write()`)
- Modify: `tests/test_sahjhan_integration.py` (TestBootstrapHook)

- [ ] **Step 1: Write failing tests — rm/rm -rf/rmdir targeting protected paths must be blocked**

Add these tests to `TestBootstrapHook` in `tests/test_sahjhan_integration.py`:

```python
def test_blocks_rm_enforcement_directory(self):
    """Issue #33: rm -rf targeting enforcement/ must be blocked."""
    event = {
        "tool_input": {"command": "rm -rf enforcement/hooks"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_blocked(code, output, "protected")

def test_blocks_rm_sahjhan_data_dir(self):
    """Issue #33: rm -rf targeting .sahjhan/ data dir must be blocked."""
    event = {
        "tool_input": {"command": "rm -rf docs/holtz/.sahjhan"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_blocked(code, output, "protected")

def test_blocks_rm_single_file_in_sahjhan(self):
    """Issue #33: rm targeting a single file inside .sahjhan/ must be blocked."""
    event = {
        "tool_input": {"command": "rm docs/holtz/.sahjhan/enforcement-cache.json"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_blocked(code, output, "protected")

def test_blocks_rmdir_enforcement(self):
    """Issue #33: rmdir targeting enforcement/ must be blocked."""
    event = {
        "tool_input": {"command": "rmdir enforcement/hooks"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_blocked(code, output, "protected")

def test_blocks_rm_chained_after_ls(self):
    """Issue #33: rm after shell operator must still be caught."""
    event = {
        "tool_input": {"command": "ls && rm -rf docs/holtz/.sahjhan"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_blocked(code, output, "protected")

def test_allows_rm_non_protected(self):
    """rm targeting non-protected paths must be allowed."""
    event = {
        "tool_input": {"command": "rm /tmp/scratch.txt"},
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_allowed(code, output)

def test_blocks_python_write_to_sahjhan_cache(self):
    """Issue #33: python3 -c writing to enforcement-cache.json must be blocked."""
    event = {
        "tool_input": {
            "command": 'python3 -c "import json; open(\'docs/holtz/.sahjhan/enforcement-cache.json\',\'w\').write(\'{}\')"'
        },
        "cwd": REPO_ROOT,
    }
    code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
    assert_blocked(code, output, "protected")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_enforcement_directory tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_sahjhan_data_dir tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_single_file_in_sahjhan tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rmdir_enforcement tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_chained_after_ls tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_python_write_to_sahjhan_cache -v`
Expected: FAIL — these commands are currently allowed

- [ ] **Step 3: Add .sahjhan/ data directory to protected paths**

In `enforcement/hooks/_sahjhan_bootstrap.py`, add the data directory to `ALL_PROTECTED`. After the `MANAGED_DOCS` list (line 33), add:

```python
# Issue #33: The .sahjhan data directory contains enforcement state (cache,
# ledger, active-run marker). Writes and deletes must be blocked.
MANAGED_DATA = [
    "docs/holtz/.sahjhan/",
]

# Combined set of all paths that must be protected from Bash writes.
ALL_PROTECTED = PROTECTED + MANAGED_DOCS + MANAGED_DATA
```

Replace the existing `ALL_PROTECTED = PROTECTED + MANAGED_DOCS` line.

- [ ] **Step 4: Add rm/rmdir detection to _check_bash_write()**

In `enforcement/hooks/_sahjhan_bootstrap.py`, inside `_check_bash_write()`, add a new check block after the `cp/mv/install` check (after line 135). Insert before the `# In-place modification tools` comment:

```python
            # Issue #33: rm/rmdir check — destructive operations on protected paths
            if any(seg_stripped.startswith(c) for c in ("rm ", "rm\t", "rmdir ")):
                ref = _segment_references_protected(seg, [p])
                if ref:
                    return (
                        f"BLOCKED: Bash command removes protected path '{p}'. "
                        "This path cannot be deleted during an audit session."
                    )
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_enforcement_directory tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_sahjhan_data_dir tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_single_file_in_sahjhan tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rmdir_enforcement tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_rm_chained_after_ls tests/test_sahjhan_integration.py::TestBootstrapHook::test_allows_rm_non_protected tests/test_sahjhan_integration.py::TestBootstrapHook::test_blocks_python_write_to_sahjhan_cache -v`
Expected: ALL PASS

- [ ] **Step 6: Run full bootstrap test suite to check for regressions**

Run: `python -m pytest tests/test_sahjhan_integration.py::TestBootstrapHook -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/_sahjhan_bootstrap.py tests/test_sahjhan_integration.py
git commit -m "fix(enforcement): block rm/rmdir and .sahjhan writes via Bash

Adds rm/rmdir detection to _check_bash_write() and adds docs/holtz/.sahjhan/
to the protected path list. Previously, an agent could bypass enforcement by
running rm -rf on the .sahjhan directory or writing to enforcement-cache.json
via python3 -c through the Bash tool.

Closes #33"
```

---

### Task 3: Full regression + lint check

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 2: Run ruff lint**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 3: Run mypy**

Run: `mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: No errors

# Protocol Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent agents from bypassing the Holtz audit protocol by enforcing state-driven pacing via hooks that block and inject directives.

**Architecture:** Two new hooks (commit_gate PreToolUse, protocol_tracker PostToolUse) share a cache file that tracks protocol obligations. The commit_gate blocks git commits when prior commits are unregistered and injects terse directives. The protocol_tracker updates the cache after every Bash command. The existing primer hook gets a one-line state summary.

**Tech Stack:** Python 3.10+, Claude Code hooks API (command-based), sahjhan CLI

**Spec:** `docs/superpowers/specs/2026-03-26-protocol-enforcement-design.md`

---

### Task 1: Create shared protocol cache module

**Files:**
- Create: `enforcement/hooks/_protocol_cache.py`
- Test: `tests/test_protocol_enforcement.py`

The cache module handles read/write of the enforcement state file and command detection heuristics. Both new hooks import from here.

- [ ] **Step 1: Write failing tests for cache module**

```python
"""Tests for protocol enforcement hooks."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


class TestProtocolCache:
    """Tests for _protocol_cache.py shared module."""

    def test_read_cache_missing_file(self, tmp_path):
        """Returns None when cache file doesn't exist."""
        from _protocol_cache import read_cache
        assert read_cache(str(tmp_path)) is None

    def test_write_and_read_cache(self, tmp_path):
        """Round-trip write then read."""
        from _protocol_cache import read_cache, write_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)
        loaded = read_cache(str(tmp_path))
        assert loaded is not None
        assert loaded["state"] == "fix_loop"
        assert loaded["unregistered_commits"] == ["abc1234"]

    def test_detect_git_commit(self):
        """Detects git commit commands."""
        from _protocol_cache import is_git_commit
        assert is_git_commit("git commit -m 'fix: stuff'")
        assert is_git_commit("git add . && git commit -m 'feat: x'")
        assert not is_git_commit("git commit --amend")
        assert not is_git_commit("git status")
        assert not is_git_commit("git log --oneline")

    def test_detect_sahjhan_command(self):
        """Detects sahjhan commands."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd("./bin/sahjhan status")
        assert is_sahjhan_cmd("./bin/sahjhan transition fix_commit")
        assert is_sahjhan_cmd("sahjhan status")
        assert not is_sahjhan_cmd("git commit -m 'sahjhan'")
        assert not is_sahjhan_cmd("echo sahjhan")

    def test_compute_obligations_no_cache(self):
        """No obligations when no cache."""
        from _protocol_cache import compute_obligations
        assert compute_obligations(None) == []

    def test_compute_obligations_unregistered_commits(self):
        """Unregistered commits produce obligation."""
        from _protocol_cache import compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc", "def"]
        obligations = compute_obligations(cache)
        assert any("fix_commit" in o["msg"] for o in obligations)
        assert any(o["blocks_commit"] for o in obligations)

    def test_compute_obligations_pattern_check_due(self):
        """Pattern check due after 3+ fixes."""
        from _protocol_cache import compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
        obligations = compute_obligations(cache)
        assert any("pattern_check" in o["msg"] for o in obligations)

    def test_compute_obligations_stall(self):
        """Stall detected after threshold."""
        from _protocol_cache import compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
        obligations = compute_obligations(cache)
        assert any(o["blocks_all"] for o in obligations)

    def test_format_injection_under_30_tokens(self):
        """Injected text must be under 30 tokens."""
        from _protocol_cache import format_injection, compute_obligations, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["a", "b", "c"]
        cache["perspective"] = "component"
        cache["perspectives_done"] = 2
        cache["perspectives_total"] = 13
        cache["fixes_since_pattern"] = 5
        obligations = compute_obligations(cache)
        text = format_injection(obligations, cache)
        # Rough token estimate: words + punctuation
        token_estimate = len(text.split())
        assert token_estimate <= 35, f"Injection too verbose ({token_estimate} tokens): {text}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache -v --no-cov`
Expected: ImportError — `_protocol_cache` doesn't exist yet

- [ ] **Step 3: Implement `_protocol_cache.py`**

```python
"""Shared protocol enforcement cache — read/write state, detect commands, compute obligations.

Used by commit_gate.py (PreToolUse) and protocol_tracker.py (PostToolUse).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

CACHE_FILENAME = "enforcement-cache.json"


def _cache_path(cwd: str) -> str:
    return os.path.join(cwd, "docs", "holtz", ".sahjhan", CACHE_FILENAME)


def empty_cache() -> dict[str, Any]:
    return {
        "active": True,
        "state": "",
        "unregistered_commits": [],
        "fixes_since_pattern": 0,
        "perspective": "",
        "perspectives_done": 0,
        "perspectives_total": 13,
        "stall": 0,
        "last_refresh": "",
    }


def read_cache(cwd: str) -> dict[str, Any] | None:
    path = _cache_path(cwd)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(cwd: str, cache: dict[str, Any]) -> None:
    path = _cache_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cache["last_refresh"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def is_git_commit(cmd: str) -> bool:
    """Detect git commit commands (not amend)."""
    return bool(re.search(r"\bgit\s+commit\b", cmd)) and "--amend" not in cmd


def is_sahjhan_cmd(cmd: str) -> bool:
    """Detect sahjhan CLI invocations."""
    stripped = cmd.strip()
    # Handle chained commands: check each segment
    for segment in re.split(r"[;&|]+", stripped):
        seg = segment.strip()
        if seg.startswith("./bin/sahjhan") or seg.startswith("sahjhan"):
            return True
    return False


def compute_obligations(cache: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Compute current protocol obligations from cache state.

    Returns list of dicts: {"msg": str, "blocks_commit": bool, "blocks_all": bool}
    """
    if cache is None or not cache.get("active"):
        return []

    state = cache.get("state", "")
    if state not in ("fix_loop", "pattern_analysis"):
        return []

    obligations: list[dict[str, Any]] = []
    commits = cache.get("unregistered_commits", [])
    stall = cache.get("stall", 0)
    fixes = cache.get("fixes_since_pattern", 0)
    perspective = cache.get("perspective", "?")
    p_done = cache.get("perspectives_done", 0)
    p_total = cache.get("perspectives_total", 13)

    if commits:
        obligations.append({
            "msg": f"{len(commits)} unregistered commits. sahjhan fix_commit required. "
                   f"{perspective} ({p_done}/{p_total})",
            "blocks_commit": True,
            "blocks_all": False,
        })

    if stall > 15:
        obligations.append({
            "msg": f"{stall} commands without protocol event. Run sahjhan status.",
            "blocks_commit": True,
            "blocks_all": True,
        })

    if fixes >= 3 and not commits:
        obligations.append({
            "msg": f"pattern_check due ({fixes} fixes). sahjhan transition pattern_check",
            "blocks_commit": False,
            "blocks_all": False,
        })

    return obligations


def format_injection(obligations: list[dict[str, Any]], cache: dict[str, Any] | None) -> str:
    """Format obligations into terse injection text. Max ~30 tokens."""
    if not obligations:
        return ""
    # Use the highest priority obligation only
    ob = obligations[0]
    blocks = "BLOCKED" if ob.get("blocks_commit") or ob.get("blocks_all") else "PROTOCOL"
    return f"{blocks}: {ob['msg']}"


def format_state_line(cache: dict[str, Any] | None) -> str:
    """One-line state summary for primer injection. Max ~20 tokens."""
    if cache is None or not cache.get("active"):
        return ""
    state = cache.get("state", "?")
    perspective = cache.get("perspective", "?")
    p_done = cache.get("perspectives_done", 0)
    p_total = cache.get("perspectives_total", 13)
    commits = len(cache.get("unregistered_commits", []))
    parts = [f"Protocol: {state}", f"{perspective} {p_done}/{p_total}"]
    if commits:
        parts.append(f"{commits} pending commits")
    fixes = cache.get("fixes_since_pattern", 0)
    if fixes >= 3:
        parts.append("pattern_check due")
    return " | ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolCache -v --no-cov`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_protocol_cache.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): add protocol cache module for state-driven enforcement"
```

---

### Task 2: Create protocol_tracker (PostToolUse)

**Files:**
- Create: `enforcement/hooks/protocol_tracker.py`
- Test: `tests/test_protocol_enforcement.py` (add TestProtocolTracker class)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_protocol_enforcement.py`:

```python
from test_sahjhan_integration import run_enforcement_hook


class TestProtocolTracker:
    """Tests for protocol_tracker.py PostToolUse hook."""

    def test_allows_all_commands(self):
        """Tracker never blocks — it's observation only."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"exit_code": 0, "output": ""},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_detects_git_commit(self, tmp_path):
        """Git commit updates cache with unregistered commit."""
        from _protocol_cache import write_cache, read_cache, empty_cache
        # Pre-seed cache so tracker has something to update
        cache = empty_cache()
        cache["state"] = "fix_loop"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix: stuff'"},
            "tool_response": {"exit_code": 0, "output": "[dev abc1234] fix: stuff"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0

        updated = read_cache(str(tmp_path))
        assert updated is not None
        assert "abc1234" in updated["unregistered_commits"]

    def test_increments_stall_counter(self, tmp_path):
        """Non-git, non-sahjhan commands increment stall."""
        from _protocol_cache import write_cache, read_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 5
        write_cache(str(tmp_path), cache)

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "python -m pytest --tb=short -q"},
            "tool_response": {"exit_code": 0, "output": "10 passed"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", event)

        updated = read_cache(str(tmp_path))
        assert updated["stall"] == 6

    def test_ignores_non_bash(self):
        """Non-Bash tool calls are ignored."""
        event = {"tool_name": "Read", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("protocol_tracker.py", event)
        assert code == 0
        assert output.get("continue") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolTracker -v --no-cov`
Expected: FAIL — `protocol_tracker.py` doesn't exist

- [ ] **Step 3: Implement `protocol_tracker.py`**

```python
#!/usr/bin/env python3
"""Protocol tracker — updates enforcement cache after Bash commands.

PostToolUse hook for Bash. Detects git commits and sahjhan commands,
updates the enforcement cache file. Never blocks. Pure bookkeeping.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import exit_ok, read_event  # noqa: E402
from _protocol_cache import (  # noqa: E402
    empty_cache,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache,
    write_cache,
)
from _resolve import sahjhan_binary  # noqa: E402


def _parse_commit_hash(output: str) -> str:
    """Extract short commit hash from git commit output."""
    # git commit output: "[branch hash] message"
    m = re.search(r"\[[\w/.-]+\s+([0-9a-f]{7,})\]", output)
    return m.group(1) if m else "unknown"


def _refresh_from_sahjhan(cwd: str, cache: dict) -> dict:
    """Query sahjhan status and update cache fields."""
    binary = sahjhan_binary()
    if not os.path.isfile(binary):
        return cache
    config_dir = os.path.join(cwd, "enforcement")
    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "status"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cache

    if result.returncode != 0:
        return cache

    # Parse status output for key fields
    output = result.stdout
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("State:"):
            # "State:     Fix Loop (Step 10) (fix_loop)"
            m = re.search(r"\((\w+)\)\s*$", line)
            if m:
                cache["state"] = m.group(1)
        if "perspective" in line and "/" in line and "complete" in line:
            # "Set: perspective (2/13 complete)"
            m = re.search(r"\((\d+)/(\d+)\s+complete\)", line)
            if m:
                cache["perspectives_done"] = int(m.group(1))
                cache["perspectives_total"] = int(m.group(2))

    cache["stall"] = 0
    cache["active"] = cache.get("state", "") not in ("", "idle", "finalized")
    return cache


def main() -> None:
    event = read_event()

    if event.get("tool_name") != "Bash":
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    cmd = event.get("tool_input", {}).get("command", "")
    exit_code = event.get("tool_response", {}).get("exit_code", -1)
    output = event.get("tool_response", {}).get("output", "")

    cache = read_cache(cwd)

    if is_sahjhan_cmd(cmd):
        # Sahjhan command — refresh full state
        if cache is None:
            cache = empty_cache()
        cache = _refresh_from_sahjhan(cwd, cache)
        # Check if fix_commit was run — clears unregistered commits
        if "fix_commit" in cmd:
            cache["unregistered_commits"] = []
            cache["fixes_since_pattern"] = cache.get("fixes_since_pattern", 0) + 1
        if "pattern_check" in cmd or "pattern_done" in cmd:
            cache["fixes_since_pattern"] = 0
        write_cache(cwd, cache)
        exit_ok()

    if cache is None:
        # No active enforcement
        exit_ok()

    if is_git_commit(cmd) and exit_code == 0:
        commit_hash = _parse_commit_hash(output)
        cache.setdefault("unregistered_commits", []).append(commit_hash)
        cache["stall"] = 0
        write_cache(cwd, cache)
        exit_ok()

    # Any other command — increment stall
    cache["stall"] = cache.get("stall", 0) + 1
    write_cache(cwd, cache)
    exit_ok()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestProtocolTracker -v --no-cov`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/protocol_tracker.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): add protocol_tracker PostToolUse hook"
```

---

### Task 3: Create commit_gate (PreToolUse)

**Files:**
- Create: `enforcement/hooks/commit_gate.py`
- Test: `tests/test_protocol_enforcement.py` (add TestCommitGate class)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_protocol_enforcement.py`:

```python
class TestCommitGate:
    """Tests for commit_gate.py PreToolUse hook."""

    def test_allows_when_no_cache(self):
        """No enforcement when no cache file exists."""
        event = {
            "tool_input": {"command": "git commit -m 'feat: new'"},
            "cwd": "/nonexistent/path",
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_blocks_commit_with_unregistered(self, tmp_path):
        """Blocks git commit when prior commits unregistered."""
        from _protocol_cache import write_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        cache["perspective"] = "component"
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "git commit -m 'fix: next'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"
        reason = output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "unregistered" in reason.lower() or "fix_commit" in reason.lower()

    def test_allows_sahjhan_with_unregistered(self, tmp_path):
        """Sahjhan commands always allowed, even with obligations."""
        from _protocol_cache import write_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "./bin/sahjhan fix_commit --item-id BH-001"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_allows_pytest_with_unregistered(self, tmp_path):
        """Test commands allowed even with unregistered commits."""
        from _protocol_cache import write_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["unregistered_commits"] = ["abc1234"]
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "python -m pytest --tb=short -q"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"

    def test_blocks_on_stall(self, tmp_path):
        """Blocks all non-sahjhan Bash after stall threshold."""
        from _protocol_cache import write_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "python -m pytest --tb=short -q"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"

    def test_injects_soft_obligation(self, tmp_path):
        """Pattern check due injects warning but doesn't block."""
        from _protocol_cache import write_cache, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["fixes_since_pattern"] = 4
        write_cache(str(tmp_path), cache)

        event = {
            "tool_input": {"command": "git commit -m 'fix: next'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        assert code == 0
        # Should allow but with additionalContext
        context = output.get("additionalContext", "")
        assert "pattern_check" in context.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestCommitGate -v --no-cov`
Expected: FAIL — `commit_gate.py` doesn't exist

- [ ] **Step 3: Implement `commit_gate.py`**

```python
#!/usr/bin/env python3
"""Commit gate — blocks git commits when protocol obligations are pending.

PreToolUse hook for Bash. Reads the enforcement cache and decides:
- BLOCK git commit when prior commits are unregistered
- BLOCK all non-sahjhan Bash when stall threshold exceeded
- INJECT terse directive when soft obligations exist (pattern check due)
- ALLOW everything else silently
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import exit_block, exit_ok, exit_warn, read_event  # noqa: E402
from _protocol_cache import (  # noqa: E402
    compute_obligations,
    format_injection,
    is_git_commit,
    is_sahjhan_cmd,
    read_cache,
)


def main() -> None:
    event = read_event()
    cmd = event.get("tool_input", {}).get("command", "")
    cwd = event.get("cwd", os.getcwd())

    cache = read_cache(cwd)
    obligations = compute_obligations(cache)

    if not obligations:
        exit_ok("PreToolUse")

    # Sahjhan commands and pytest are always allowed
    if is_sahjhan_cmd(cmd):
        exit_ok("PreToolUse")

    blocks_commit = any(o.get("blocks_commit") for o in obligations)
    blocks_all = any(o.get("blocks_all") for o in obligations)
    injection = format_injection(obligations, cache)

    # Hard block: stall threshold exceeded
    if blocks_all:
        exit_block(injection)

    # Hard block: git commit with unregistered prior commits
    if is_git_commit(cmd) and blocks_commit:
        exit_block(injection)

    # Soft injection: obligations exist but don't block this command
    if injection:
        exit_warn(injection)

    exit_ok("PreToolUse")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestCommitGate -v --no-cov`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/commit_gate.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): add commit_gate PreToolUse hook"
```

---

### Task 4: Enhance primer.py with state line

**Files:**
- Modify: `enforcement/hooks/primer.py:88-107` (add cache read before building context)
- Test: `tests/test_protocol_enforcement.py` (add TestPrimerStateLine class)

- [ ] **Step 1: Write failing test**

Add to `tests/test_protocol_enforcement.py`:

```python
class TestPrimerStateLine:
    """Tests for primer.py enforcement cache integration."""

    def test_primer_source_reads_cache(self):
        """primer.py imports and calls format_state_line from cache module."""
        source_path = os.path.join(REPO_ROOT, "enforcement", "hooks", "primer.py")
        with open(source_path) as f:
            source = f.read()
        assert "format_state_line" in source, (
            "primer.py should import format_state_line from _protocol_cache"
        )

    def test_format_state_line_output(self):
        """State line is terse and under 20 tokens."""
        from _protocol_cache import format_state_line, empty_cache
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
        cache["perspectives_done"] = 2
        cache["perspectives_total"] = 13
        cache["unregistered_commits"] = ["abc"]
        cache["fixes_since_pattern"] = 4
        line = format_state_line(cache)
        assert line  # non-empty
        assert len(line.split()) <= 25, f"State line too long: {line}"
        assert "fix_loop" in line
        assert "component" in line

    def test_format_state_line_inactive(self):
        """No output when no active cache."""
        from _protocol_cache import format_state_line
        assert format_state_line(None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPrimerStateLine -v --no-cov`
Expected: first test fails (primer.py doesn't import format_state_line yet)

- [ ] **Step 3: Add cache integration to primer.py**

In `enforcement/hooks/primer.py`, add import at the top (after existing imports):

```python
from _protocol_cache import format_state_line, read_cache  # noqa: E402
```

Then, in the `main()` function, after the line that builds `context` (around line 102), before `exit_warn(context)`, add:

```python
    # Append enforcement state line if cache exists
    state_line = format_state_line(read_cache(cwd))
    if state_line:
        context += "\n" + state_line
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestPrimerStateLine -v --no-cov`
Expected: all pass

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: all pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/primer.py tests/test_protocol_enforcement.py
git commit -m "feat(enforcement): add protocol state line to primer hook"
```

---

### Task 5: Register hooks in .claude/settings.local.json

**Files:**
- Modify: `.claude/settings.local.json`

- [ ] **Step 1: Write failing test**

Add to `tests/test_enforcement_config.py`:

```python
def test_settings_local_registers_enforcement_hooks():
    """Dev-mode settings must register commit_gate and protocol_tracker."""
    settings_path = Path(__file__).parent.parent / ".claude" / "settings.local.json"
    assert settings_path.exists(), ".claude/settings.local.json missing"
    cfg = json.loads(settings_path.read_text())
    hooks = cfg.get("hooks", {})

    pre_tool = hooks.get("PreToolUse", [])
    post_tool = hooks.get("PostToolUse", [])

    pre_commands = []
    for entry in pre_tool:
        for h in entry.get("hooks", []):
            pre_commands.append(h.get("command", ""))

    post_commands = []
    for entry in post_tool:
        for h in entry.get("hooks", []):
            post_commands.append(h.get("command", ""))

    assert any("commit_gate" in c for c in pre_commands), (
        "commit_gate.py not registered in settings.local.json PreToolUse"
    )
    assert any("protocol_tracker" in c for c in post_commands), (
        "protocol_tracker.py not registered in settings.local.json PostToolUse"
    )
```

Add this import at the top of the test file if not present: `import json`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enforcement_config.py::test_settings_local_registers_enforcement_hooks -v --no-cov`
Expected: FAIL — hooks not registered yet

- [ ] **Step 3: Update `.claude/settings.local.json`**

Add hooks section to the existing settings. Merge with existing `permissions` key:

```json
{
  "permissions": {
    "allow": [
      ... existing entries ...
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python enforcement/hooks/commit_gate.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python enforcement/hooks/protocol_tracker.py"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_enforcement_config.py::test_settings_local_registers_enforcement_hooks -v --no-cov`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/settings.local.json tests/test_enforcement_config.py
git commit -m "feat(enforcement): register pacing hooks in dev-mode settings"
```

---

### Task 6: Register hooks in hooks.json (plugin mode)

**Files:**
- Modify: `hooks/hooks.json`

- [ ] **Step 1: Write failing test**

Add to `tests/test_enforcement_config.py`:

```python
def test_hooks_json_registers_enforcement_hooks():
    """Plugin-mode hooks.json must register commit_gate and protocol_tracker."""
    hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
    cfg = json.loads(hooks_path.read_text())
    hooks = cfg.get("hooks", {})

    pre_tool = hooks.get("PreToolUse", [])
    post_tool = hooks.get("PostToolUse", [])

    all_pre_commands = []
    for entry in pre_tool:
        for h in entry.get("hooks", []):
            all_pre_commands.append(h.get("command", ""))

    all_post_commands = []
    for entry in post_tool:
        for h in entry.get("hooks", []):
            all_post_commands.append(h.get("command", ""))

    assert any("commit_gate" in c for c in all_pre_commands), (
        "commit_gate.py not registered in hooks.json PreToolUse"
    )
    assert any("protocol_tracker" in c for c in all_post_commands), (
        "protocol_tracker.py not registered in hooks.json PostToolUse"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enforcement_config.py::test_hooks_json_registers_enforcement_hooks -v --no-cov`
Expected: FAIL

- [ ] **Step 3: Update hooks.json**

Add commit_gate to the PreToolUse array (new entry with Bash matcher) and protocol_tracker to the PostToolUse array:

In `PreToolUse`, add a new entry:
```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/commit_gate.py\""
    }
  ]
}
```

In `PostToolUse`, add to the existing Bash matcher's hooks array:
```json
{
  "type": "command",
  "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/protocol_tracker.py\""
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_enforcement_config.py::test_hooks_json_registers_enforcement_hooks -v --no-cov`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add hooks/hooks.json tests/test_enforcement_config.py
git commit -m "feat(enforcement): register pacing hooks in plugin-mode hooks.json"
```

---

### Task 7: Integration test — simulate enforcement

**Files:**
- Modify: `tests/test_protocol_enforcement.py` (add integration test)

- [ ] **Step 1: Write integration test**

```python
class TestEnforcementIntegration:
    """End-to-end: simulate a fix loop and verify enforcement."""

    def test_commit_blocked_after_unregistered(self, tmp_path):
        """Full flow: tracker detects commit, gate blocks next commit."""
        from _protocol_cache import write_cache, empty_cache

        # Seed cache as if we're in an active fix loop
        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["perspective"] = "component"
        write_cache(str(tmp_path), cache)

        # Simulate: git commit succeeds (tracker fires)
        tracker_event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m 'fix(x): first'"},
            "tool_response": {"exit_code": 0, "output": "[dev aaa1111] fix(x): first"},
            "cwd": str(tmp_path),
        }
        run_enforcement_hook("protocol_tracker.py", tracker_event)

        # Now: git commit attempted (gate fires)
        gate_event = {
            "tool_input": {"command": "git commit -m 'fix(y): second'"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", gate_event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block", "Gate should block second commit"

        # But: sahjhan command is allowed
        sahjhan_event = {
            "tool_input": {"command": "./bin/sahjhan transition fix_commit --item-id BH-001"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", sahjhan_event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow", "Gate should allow sahjhan commands"

    def test_stall_blocks_all(self, tmp_path):
        """Stall counter blocks everything except sahjhan."""
        from _protocol_cache import write_cache, empty_cache

        cache = empty_cache()
        cache["state"] = "fix_loop"
        cache["stall"] = 16
        write_cache(str(tmp_path), cache)

        # Regular command blocked
        event = {
            "tool_input": {"command": "ls -la"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "block"

        # Sahjhan allowed
        event["tool_input"]["command"] = "./bin/sahjhan status"
        code, output, _ = run_enforcement_hook("commit_gate.py", event)
        perm = output.get("hookSpecificOutput", {}).get("permissionDecision")
        assert perm == "allow"
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_protocol_enforcement.py::TestEnforcementIntegration -v --no-cov`
Expected: all pass

- [ ] **Step 3: Run full suite + linters**

```bash
python -m pytest --tb=short -q
ruff check enforcement/hooks/commit_gate.py enforcement/hooks/protocol_tracker.py enforcement/hooks/_protocol_cache.py
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_protocol_enforcement.py
git commit -m "test(enforcement): add integration tests for protocol pacing"
```

---

### Task 8: Verify README metrics and final checks

**Files:**
- Modify: `README.md` (update test count and hook count if needed)

- [ ] **Step 1: Check if README metrics test passes**

Run: `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v --no-cov`

If it fails (test count or hook count changed), update the README badges and "What's inside" line to match.

- [ ] **Step 2: Update README if needed**

Update badge and counts to match actual values.

- [ ] **Step 3: Final full suite**

Run: `python -m pytest --tb=short -q`
Expected: 0 failures

- [ ] **Step 4: Commit if changes were needed**

```bash
git add README.md
git commit -m "fix(docs): update README metrics after enforcement hooks"
```

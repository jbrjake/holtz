# Sahjhan 0.7.0 Runtime Hooks Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade holtz from sahjhan 0.6.1 to 0.7.0, replacing bespoke Python enforcement hooks with declarative `hooks.toml` rules and adding comprehensive auto-recording of all tool use.

**Architecture:** New `enforcement/hooks.toml` declares 6 hooks + 2 monitors evaluated by `sahjhan hook eval`. Three thin Python wrappers delegate to the binary. `write_guard.py` and `stop_gate.py` are replaced; bootstrap, commit_gate, bash_guard, protocol_tracker, primer, and lens_quiz stay as-is.

**Tech Stack:** Python 3.12+, TOML config, sahjhan 0.7.0 binary (Rust), pytest

**Spec:** `docs/superpowers/specs/2026-03-31-sahjhan-070-runtime-hooks-design.md`

---

### Task 1: Upgrade sahjhan binary version

**Files:**
- Modify: `enforcement/hooks/_resolve.py:14-23`

- [ ] **Step 1: Update version and checksums**

In `enforcement/hooks/_resolve.py`, change the version and all four checksums:

```python
SAHJHAN_VERSION = "0.7.0"
_RELEASE_BASE = "https://github.com/jbrjake/sahjhan/releases/download"
_BOOTSTRAP_COOLDOWN = 3600  # seconds before retrying after failure

SAHJHAN_CHECKSUMS: dict[str, str] = {
    "aarch64-apple-darwin": "c07d71bb377711d2b15aca9799f985d0f4f2fbb370c5bfd96d1327bf71e4b5eb",
    "x86_64-apple-darwin": "667d83918d485ed41685f24e99fef6d671e7741b692525fbafdf64b3d80fdd73",
    "x86_64-unknown-linux-gnu": "59b5a387c2fceaadb9afeb3d45a4e89eb2393a941fa4d484ee84a572c95e8338",
    "aarch64-unknown-linux-gnu": "849844b0727ef261e29d24bba53e40ea3809e207acc160c905db17b7ab646ba5",
}
```

- [ ] **Step 2: Delete stale binary so bootstrap re-downloads**

```bash
rm -f bin/sahjhan-* bin/.sahjhan-version bin/.sahjhan-bootstrap-failed
```

- [ ] **Step 3: Verify bootstrap downloads 0.7.0**

```bash
python -c "
import sys; sys.path.insert(0, 'enforcement/hooks')
from _resolve import ensure_sahjhan, SAHJHAN_VERSION
binary = ensure_sahjhan()
print(f'Version: {SAHJHAN_VERSION}')
print(f'Binary: {binary}')
assert binary is not None, 'Bootstrap failed'
print('OK')
"
```

Expected: `Version: 0.7.0`, `Binary: /path/to/bin/sahjhan-<triple>`, `OK`

- [ ] **Step 4: Verify binary runs**

```bash
bin/sahjhan --version
```

Expected: output containing `0.7.0`

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/_resolve.py
git commit -m "feat(holtz): upgrade sahjhan binary from 0.6.1 to 0.7.0"
```

---

### Task 2: Add new event types to events.toml

**Files:**
- Modify: `enforcement/events.toml` (append at end)

- [ ] **Step 1: Add four new event types**

Append to the end of `enforcement/events.toml`:

```toml
# ── Auto-recorded tool use events (sahjhan 0.7.0 hooks) ──

[events.file_read]
description = "File read by agent (auto-recorded by hook eval)"
fields = [
    { name = "file_path", type = "string" },
    { name = "line_start", type = "string", pattern = "^\\d+$", optional = true },
    { name = "line_end", type = "string", pattern = "^\\d+$", optional = true },
    { name = "tool", type = "string" },
]

[events.source_edit]
description = "Source file modified by agent (auto-recorded by hook eval)"
fields = [
    { name = "file_path", type = "string" },
    { name = "lines_changed", type = "string", pattern = "^\\d+$", optional = true },
    { name = "edit_type", type = "string", pattern = "^(partial|full_file)$", optional = true },
    { name = "tool", type = "string" },
]

[events.file_search]
description = "File search by agent (auto-recorded by hook eval)"
fields = [
    { name = "pattern", type = "string", optional = true },
    { name = "search_path", type = "string", optional = true },
    { name = "tool", type = "string" },
]

[events.bash_command]
description = "Shell command executed by agent (recorded by post-tool hook)"
fields = [
    { name = "command", type = "string" },
]
```

- [ ] **Step 2: Validate config**

```bash
bin/sahjhan --config-dir enforcement validate
```

Expected: exit 0, no errors. (Validation should pass with the new event types even without hooks.toml yet — events.toml is independently valid.)

- [ ] **Step 3: Commit**

```bash
git add enforcement/events.toml
git commit -m "feat(holtz): add auto-recorded event types for tool use tracking"
```

---

### Task 3: Create enforcement/hooks.toml

**Files:**
- Create: `enforcement/hooks.toml`

- [ ] **Step 1: Create the hooks config file**

Create `enforcement/hooks.toml`:

```toml
# Runtime enforcement hooks for the holtz audit protocol.
# Evaluated by `sahjhan hook eval` on every tool use.
# Sealed at init time alongside the other 5 config files.

# ── TDD Gate ──
# Block source file edits in fix_loop without a prior failing test.
# Makes TDD mechanically unavoidable. Filter excludes test files.
# Every fix_commit self-loop is a state transition, so the gate resets.

[[hooks]]
event = "PreToolUse"
tools = ["Edit", "Write"]
states = ["fix_loop"]
action = "block"
message = "TDD violation: write and run a failing test before editing source files. Record with: sahjhan event test_failed_before_fix --field finding_id=BH-NNN --field test_name=..."

[hooks.gate]
type = "ledger_has_event_since"
event = "test_failed_before_fix"
since = "last_transition"

[hooks.filter]
path_not_matches = "tests/**"

# ── Premature Completion Blocker ──
# Block stop when agent output claims completion in non-terminal states.

[[hooks]]
event = "Stop"
states_not = ["converged", "finalized"]
action = "block"
message = "You are claiming completion but sahjhan state is {current_state}, not converged/finalized. Run `sahjhan status` to check your position. Continue the protocol."

[hooks.check]
type = "output_contains_any"
patterns = [
    "audit complete",
    "audit is complete",
    "all fixes applied",
    "CONVERGED",
    "holtz complete",
    "holtz audit complete",
    "all issues resolved",
    "punchlist complete",
    "work is done",
    "summary of everything",
    "convergence achieved",
    "no remaining items",
    "all findings resolved",
]

# ── Edit Accumulation Warning ──
# Warn after many events in fix_loop without a state transition.
# Catches "batch all fixes then summarize" anti-pattern.

[[hooks]]
event = "PostToolUse"
tools = ["Edit"]
states = ["fix_loop"]
action = "warn"
message = "High activity: {count} events since your last fix_commit. Each fix must be committed atomically. Run: sahjhan transition fix_commit --item-id BH-NNN"

[hooks.check]
type = "event_count_since_last_transition"
threshold = 8

# ── Auto-Record: File Reads ──

[[hooks]]
event = "PostToolUse"
tools = ["Read"]

[hooks.auto_record]
event_type = "file_read"
fields = { file_path = "{tool.file_path}" }

# ── Auto-Record: Source Edits ──

[[hooks]]
event = "PostToolUse"
tools = ["Edit", "Write", "NotebookEdit"]

[hooks.auto_record]
event_type = "source_edit"
fields = { file_path = "{tool.file_path}" }

# ── Auto-Record: File Searches ──

[[hooks]]
event = "PostToolUse"
tools = ["Grep"]

[hooks.auto_record]
event_type = "file_search"
fields = { file_path = "{tool.file_path}" }

# ── Monitors ──

[[monitors]]
name = "fix_loop_stall"
states = ["fix_loop"]
action = "warn"
message = "{count} events since last state transition. Run `sahjhan status`. If you have been fixing bugs without committing, stop and commit each fix atomically."

[monitors.trigger]
type = "event_count_since_last_transition"
threshold = 20

[[monitors]]
name = "audit_stall"
states = ["audit"]
action = "warn"
message = "{count} events in audit state without advancing. Run `sahjhan status` to check progress."

[monitors.trigger]
type = "event_count_since_last_transition"
threshold = 30
```

- [ ] **Step 2: Validate full config including hooks.toml**

```bash
bin/sahjhan --config-dir enforcement validate
```

Expected: exit 0. Sahjhan 0.7.0 auto-discovers hooks.toml in the config directory and validates hook states, gate configs, auto_record event types, and monitor names.

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks.toml
git commit -m "feat(holtz): add hooks.toml with TDD gate, completion blocker, stall monitors, and auto-recording"
```

---

### Task 4: Create pre_tool_hook.py (replaces write_guard.py)

**Files:**
- Create: `enforcement/hooks/pre_tool_hook.py`
- Test: `tests/test_sahjhan_integration.py`

- [ ] **Step 1: Write failing tests for pre_tool_hook**

Add a new test class to `tests/test_sahjhan_integration.py`. Insert it after the existing `TestWriteGuard` class (which will be removed in Task 8). For now, both coexist.

```python
class TestPreToolHook:
    """Tests for the pre_tool_hook.py thin wrapper."""

    def test_blocks_managed_path(self):
        """pre_tool_hook blocks writes to sahjhan-managed files."""
        event = {
            "tool_input": {"file_path": "docs/holtz/STATUS.md"},
            "tool_name": "Edit",
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert_blocked(code, output, "managed")

    def test_allows_non_managed_path(self):
        """pre_tool_hook allows writes outside managed paths."""
        event = {
            "tool_input": {"file_path": "src/main.py"},
            "tool_name": "Edit",
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert_allowed(code, output)

    def test_allows_empty_path(self):
        """pre_tool_hook allows when no file path is provided."""
        event = {"tool_input": {}, "tool_name": "Edit", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert_allowed(code, output)

    def test_degrades_gracefully_without_binary(self, tmp_path):
        """pre_tool_hook allows when sahjhan binary is unavailable."""
        event = {
            "tool_input": {"file_path": "src/main.py"},
            "tool_name": "Edit",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert_allowed(code, output)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sahjhan_integration.py::TestPreToolHook -v --tb=short --no-header
```

Expected: FAIL (pre_tool_hook.py does not exist yet)

- [ ] **Step 3: Write pre_tool_hook.py**

Create `enforcement/hooks/pre_tool_hook.py`:

```python
#!/usr/bin/env python3
"""Sahjhan pre-tool hook — delegates to hook eval for managed paths and TDD gate.

PreToolUse hook. Replaces write_guard.py. Calls `sahjhan hook eval` which:
- Checks paths.managed (blocks writes to docs/holtz/, enforcement/)
- Evaluates hooks.toml rules (TDD gate in fix_loop, etc.)

Falls back to allow if sahjhan binary is unavailable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import exit_block, exit_ok, exit_warn, read_event  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402


def main() -> None:
    event = read_event()
    tool_name = event.get("tool_name", event.get("tool", ""))
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    binary = ensure_sahjhan()
    if binary is None:
        exit_ok("PreToolUse")

    config_dir = os.path.join(cwd, "enforcement")
    if not os.path.isdir(config_dir):
        exit_ok("PreToolUse")

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
    if tool_name:
        cmd.extend(["--tool", tool_name])
    if file_path:
        cmd.extend(["--file", file_path])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_ok("PreToolUse")

    if result.returncode != 0:
        exit_ok("PreToolUse")

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        exit_ok("PreToolUse")

    eval_data = data.get("data", data)
    decision = eval_data.get("decision", "allow")
    messages = eval_data.get("messages", [])

    if decision == "block":
        reason = next(
            (m["message"] for m in messages if m.get("action") == "block"),
            "Blocked by sahjhan hook eval",
        )
        exit_block(reason)

    if decision == "warn":
        warnings = [m["message"] for m in messages if m.get("action") == "warn"]
        monitor_warnings = eval_data.get("monitor_warnings", [])
        warnings.extend(w["message"] for w in monitor_warnings)
        if warnings:
            exit_warn(" | ".join(warnings))

    exit_ok("PreToolUse")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sahjhan_integration.py::TestPreToolHook -v --tb=short --no-header
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/pre_tool_hook.py tests/test_sahjhan_integration.py
git commit -m "feat(holtz): add pre_tool_hook.py thin wrapper replacing write_guard.py"
```

---

### Task 5: Create post_tool_hook.py (auto-recording + enrichment)

**Files:**
- Create: `enforcement/hooks/post_tool_hook.py`
- Test: `tests/test_sahjhan_integration.py`

- [ ] **Step 1: Write failing tests for post_tool_hook**

Add to `tests/test_sahjhan_integration.py`:

```python
class TestPostToolHook:
    """Tests for the post_tool_hook.py thin wrapper."""

    def test_allows_without_binary(self, tmp_path):
        """post_tool_hook degrades gracefully when no binary available."""
        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.py"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook(
            "post_tool_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("continue") is True

    @pytest.fixture
    def ptmod(self):
        """Load post_tool_hook module for unit testing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "post_tool_hook",
            os.path.join(ENFORCEMENT_HOOKS_DIR, "post_tool_hook.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_enriches_read_line_span(self, ptmod):
        """post_tool_hook enriches file_read with offset/limit as line span."""
        record = {"event_type": "file_read", "fields": {"file_path": "src/main.py"}}
        tool_input = {"file_path": "src/main.py", "offset": "10", "limit": "50"}
        result = ptmod._enrich_auto_record(record, "Read", tool_input)
        assert result["fields"]["line_start"] == "10"
        assert result["fields"]["line_end"] == "59"
        assert result["fields"]["tool"] == "Read"

    def test_enriches_edit_lines_changed(self, ptmod):
        """post_tool_hook enriches source_edit with lines_changed from old_string."""
        record = {"event_type": "source_edit", "fields": {"file_path": "src/main.py"}}
        tool_input = {
            "file_path": "src/main.py",
            "old_string": "line1\nline2\nline3",
            "new_string": "new1\nnew2",
        }
        result = ptmod._enrich_auto_record(record, "Edit", tool_input)
        assert result["fields"]["lines_changed"] == "3"
        assert result["fields"]["edit_type"] == "partial"
        assert result["fields"]["tool"] == "Edit"

    def test_enriches_write_full_file(self, ptmod):
        """post_tool_hook marks Write as full_file edit."""
        record = {"event_type": "source_edit", "fields": {"file_path": "src/main.py"}}
        tool_input = {"file_path": "src/main.py", "content": "full file content"}
        result = ptmod._enrich_auto_record(record, "Write", tool_input)
        assert result["fields"]["edit_type"] == "full_file"
        assert result["fields"]["tool"] == "Write"

    def test_enriches_grep_search(self, ptmod):
        """post_tool_hook enriches file_search with pattern and path."""
        record = {"event_type": "file_search", "fields": {"file_path": ""}}
        tool_input = {"pattern": "TODO", "path": "src/"}
        result = ptmod._enrich_auto_record(record, "Grep", tool_input)
        assert result["fields"]["pattern"] == "TODO"
        assert result["fields"]["search_path"] == "src/"
        assert result["fields"]["tool"] == "Grep"

    def test_builds_bash_command_event(self, ptmod):
        """post_tool_hook builds bash_command event from tool_input."""
        result = ptmod._build_bash_event({"command": "git status"})
        assert result["event_type"] == "bash_command"
        assert result["fields"]["command"] == "git status"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sahjhan_integration.py::TestPostToolHook -v --tb=short --no-header
```

Expected: FAIL (post_tool_hook.py does not exist yet)

- [ ] **Step 3: Write post_tool_hook.py**

Create `enforcement/hooks/post_tool_hook.py`:

```python
#!/usr/bin/env python3
"""Sahjhan post-tool hook — auto-records tool use and evaluates monitors.

PostToolUse hook. Calls `sahjhan hook eval` which:
- Returns auto_record events to write to the ledger
- Evaluates edit accumulation warning in fix_loop
- Evaluates stall monitors

The wrapper enriches auto_record fields with data from tool_input
(line spans for Read, lines_changed for Edit, etc.) and additionally
records bash_command events for Bash tools.

Falls back to allow if sahjhan binary is unavailable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

from _common import _active_ledger, exit_ok, exit_warn, read_event  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402


def _enrich_auto_record(
    record: dict[str, Any], tool_name: str, tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Enrich an auto_record result with data from the tool event.

    Returns a new dict with enriched fields. Does not mutate the input.
    """
    fields = dict(record.get("fields", {}))
    event_type = record.get("event_type", "")
    fields["tool"] = tool_name

    if event_type == "file_read" and tool_name == "Read":
        offset = tool_input.get("offset", "1")
        limit = tool_input.get("limit", "")
        try:
            start = int(offset) if offset else 1
            fields["line_start"] = str(start)
            if limit:
                fields["line_end"] = str(start + int(limit) - 1)
        except (ValueError, TypeError):
            pass

    elif event_type == "source_edit":
        if tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            if old_string:
                fields["lines_changed"] = str(old_string.count("\n") + 1)
            fields["edit_type"] = "partial"
        elif tool_name == "Write":
            fields["edit_type"] = "full_file"
        elif tool_name == "NotebookEdit":
            fields["edit_type"] = "partial"

    elif event_type == "file_search" and tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", "")
        if pattern:
            fields["pattern"] = pattern
        if search_path:
            fields["search_path"] = search_path

    return {"event_type": event_type, "fields": fields}


def _build_bash_event(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Build a bash_command event from Bash tool_input."""
    command = tool_input.get("command", "")
    return {"event_type": "bash_command", "fields": {"command": command}}


def _record_event(
    binary: str,
    config_dir: str,
    ledger: str | None,
    cwd: str,
    event_type: str,
    fields: dict[str, str],
) -> None:
    """Record an event via sahjhan CLI. Best-effort, failures are silent."""
    cmd = [binary, "--config-dir", config_dir]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["event", event_type])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main() -> None:
    event = read_event()
    tool_name = event.get("tool_name", event.get("tool", ""))
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = event.get("cwd", os.getcwd())

    binary = ensure_sahjhan()
    if binary is None:
        exit_ok()

    config_dir = os.path.join(cwd, "enforcement")
    if not os.path.isdir(config_dir):
        exit_ok()

    ledger = _active_ledger(cwd)

    # Call hook eval
    cmd = [binary, "--config-dir", config_dir, "--json"]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["hook", "eval", "--event", "PostToolUse"])
    if tool_name:
        cmd.extend(["--tool", tool_name])
    if file_path:
        cmd.extend(["--file", file_path])

    eval_data = {}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            eval_data = data.get("data", data)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass

    # Process auto_records
    for record in eval_data.get("auto_records", []):
        enriched = _enrich_auto_record(record, tool_name, tool_input)
        _record_event(
            binary, config_dir, ledger, cwd,
            enriched["event_type"], enriched["fields"],
        )

    # Record bash_command for Bash tools (not in hooks.toml auto_record)
    if tool_name == "Bash":
        bash_event = _build_bash_event(tool_input)
        _record_event(
            binary, config_dir, ledger, cwd,
            bash_event["event_type"], bash_event["fields"],
        )

    # Surface warnings
    decision = eval_data.get("decision", "allow")
    if decision == "warn":
        messages = eval_data.get("messages", [])
        monitor_warnings = eval_data.get("monitor_warnings", [])
        warnings = [m["message"] for m in messages if m.get("action") == "warn"]
        warnings.extend(w["message"] for w in monitor_warnings)
        if warnings:
            exit_warn(" | ".join(warnings))

    exit_ok()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sahjhan_integration.py::TestPostToolHook -v --tb=short --no-header
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/post_tool_hook.py tests/test_sahjhan_integration.py
git commit -m "feat(holtz): add post_tool_hook.py with auto-record enrichment for all tool types"
```

---

### Task 6: Create stop_hook.py (replaces stop_gate.py)

**Files:**
- Create: `enforcement/hooks/stop_hook.py`
- Test: `tests/test_sahjhan_integration.py`

- [ ] **Step 1: Write failing tests for stop_hook**

Add to `tests/test_sahjhan_integration.py`:

```python
class TestStopHook:
    """Tests for the stop_hook.py thin wrapper."""

    def test_allows_without_binary(self, tmp_path):
        """stop_hook degrades gracefully when no binary available."""
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output == {}

    def test_allows_without_active_run(self, tmp_path):
        """stop_hook allows when no .sahjhan directory exists."""
        _create_mock_binary(tmp_path, 'echo "state: finalized (1 events, chain valid)"')
        (tmp_path / "enforcement").mkdir(parents=True)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output == {}

    def test_degrades_gracefully_on_oserror(self, tmp_path):
        """stop_hook allows when binary is unexecutable."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        _create_mock_binary(tmp_path, "exit 0")
        binary_path = list((tmp_path / "bin").iterdir())[0]
        binary_path.chmod(0o000)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        binary_path.chmod(0o755)
        assert code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sahjhan_integration.py::TestStopHook -v --tb=short --no-header
```

Expected: FAIL (stop_hook.py does not exist yet)

- [ ] **Step 3: Write stop_hook.py**

Create `enforcement/hooks/stop_hook.py`:

```python
#!/usr/bin/env python3
"""Sahjhan stop hook — blocks stop in active audit states.

Stop hook. Replaces stop_gate.py. Two enforcement layers:
1. State-based blocking: blocks stop in active work states
   (audit, fix_loop, pattern_analysis, final_sweep)
2. Output pattern matching: delegates to `sahjhan hook eval`
   to catch premature completion claims via hooks.toml rules

Falls back to allow if sahjhan binary is unavailable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import _active_ledger, exit_stop_allow, exit_stop_block, read_event  # noqa: E402
from _protocol_cache import parse_status_text  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

_ACTIVE_WORK_STATES = {"audit", "fix_loop", "pattern_analysis", "final_sweep"}


def main() -> None:
    event = read_event()
    cwd = event.get("cwd", os.getcwd())

    binary = ensure_sahjhan()
    if binary is None:
        exit_stop_allow()

    config_dir = os.path.join(cwd, "enforcement")

    # No active run — allow stop
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        exit_stop_allow()

    ledger = _active_ledger(cwd)

    # Query current state
    try:
        cmd = [binary, "--config-dir", config_dir]
        if ledger:
            cmd.extend(["--ledger", ledger])
        cmd.append("status")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        exit_stop_allow()

    if result.returncode != 0:
        exit_stop_allow()

    status = parse_status_text(result.stdout)
    current_state = status.get("current_state", "")
    is_terminal = status.get("terminal", False)

    # Allow stop in terminal or non-active states
    if is_terminal or current_state not in _ACTIVE_WORK_STATES:
        exit_stop_allow()

    # In active work state — try hook eval for more specific blocking
    output_text = event.get("result", "")
    if output_text:
        try:
            hook_cmd = [binary, "--config-dir", config_dir, "--json"]
            if ledger:
                hook_cmd.extend(["--ledger", ledger])
            hook_cmd.extend(["hook", "eval", "--event", "Stop"])
            hook_cmd.extend(["--output-text", output_text])
            hook_result = subprocess.run(
                hook_cmd, capture_output=True, text=True, timeout=5, cwd=cwd,
            )
            if hook_result.returncode == 0:
                data = json.loads(hook_result.stdout)
                eval_data = data.get("data", data)
                if eval_data.get("decision") == "block":
                    messages = eval_data.get("messages", [])
                    reason = next(
                        (m["message"] for m in messages if m.get("action") == "block"),
                        None,
                    )
                    if reason:
                        exit_stop_block(reason)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
            pass

    # State-based blocking (fallback if hook eval didn't produce a more specific message)
    msg_parts = [
        f"Audit is in state '{current_state}' which is not terminal.",
        "You must complete the audit protocol before stopping.",
    ]
    next_transitions = status.get("available_transitions", [])
    if next_transitions:
        msg_parts.append(f"Available transitions: {', '.join(next_transitions)}")

    exit_stop_block(" ".join(msg_parts))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_sahjhan_integration.py::TestStopHook -v --tb=short --no-header
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_sahjhan_integration.py
git commit -m "feat(holtz): add stop_hook.py with state blocking and premature completion detection"
```

---

### Task 7: Update hook registrations

**Files:**
- Modify: `hooks/hooks.json`
- Modify: `.claude/settings.local.json:65-151`
- Modify: `enforcement/hooks-manifest.json`

- [ ] **Step 1: Update hooks/hooks.json**

Replace the contents of `hooks/hooks.json` with:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_sahjhan_bootstrap.py\""
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/pre_tool_hook.py\""
          }
        ]
      },
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_sahjhan_bootstrap.py\""
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/_sahjhan_bootstrap.py\""
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/commit_gate.py\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/post_tool_hook.py\""
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/bash_guard.py\""
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/protocol_tracker.py\""
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/subagent_findings_check.py\""
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/lens_quiz.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/stop_hook.py\""
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/primer.py\""
          }
        ]
      }
    ]
  }
}
```

Key changes:
- `write_guard.py` → `pre_tool_hook.py` in PreToolUse Write|Edit
- `stop_gate.py` → `stop_hook.py` in Stop
- New PostToolUse catch-all matcher `""` for `post_tool_hook.py` (fires on ALL tools)
- Existing Bash-specific PostToolUse matcher stays for bash_guard + protocol_tracker

- [ ] **Step 2: Update .claude/settings.local.json hooks section**

Update the hooks section of `.claude/settings.local.json` (lines 65-151) with the same changes but using local paths (no `${CLAUDE_PLUGIN_ROOT}`):

- Line 76: `"python \"enforcement/hooks/write_guard.py\""` → `"python \"enforcement/hooks/pre_tool_hook.py\""`
- Line 135: `"python \"enforcement/hooks/stop_gate.py\""` → `"python \"enforcement/hooks/stop_hook.py\""`
- Add a new PostToolUse catch-all entry before the Bash-specific one:

```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "python \"enforcement/hooks/post_tool_hook.py\""
    }
  ]
},
```

- [ ] **Step 3: Update hooks-manifest.json**

Replace `enforcement/hooks-manifest.json`:

```json
{
  "required_hooks": {
    "PreToolUse": ["_sahjhan_bootstrap.py", "pre_tool_hook.py", "commit_gate.py"],
    "PostToolUse": ["post_tool_hook.py", "bash_guard.py", "protocol_tracker.py"],
    "UserPromptSubmit": ["primer.py"],
    "Stop": ["stop_hook.py"],
    "SubagentStop": ["lens_quiz.py"]
  }
}
```

- [ ] **Step 4: Run hook verification**

```bash
python enforcement/hooks/verify_hooks.py --settings .claude/settings.local.json
```

Expected: exit 0, `Hook verification: all N required hooks present.`

- [ ] **Step 5: Commit**

```bash
git add hooks/hooks.json .claude/settings.local.json enforcement/hooks-manifest.json
git commit -m "feat(holtz): update hook registrations for sahjhan 0.7.0 thin wrappers"
```

---

### Task 8: Delete replaced hooks and update tests

**Files:**
- Delete: `enforcement/hooks/write_guard.py`
- Delete: `enforcement/hooks/stop_gate.py`
- Modify: `tests/test_sahjhan_integration.py`
- Modify: `tests/test_verify_hooks.py`
- Modify: `tests/test_protocol_enforcement.py`

- [ ] **Step 1: Delete replaced hook files**

```bash
git rm enforcement/hooks/write_guard.py enforcement/hooks/stop_gate.py
```

- [ ] **Step 2: Remove TestWriteGuard and TestStopGate from test_sahjhan_integration.py**

Delete the entire `TestWriteGuard` class (the section starting with `# --- write_guard.py (PreToolUse) ---` through the last test method before `# --- bash_guard.py`).

Delete the entire `TestStopGate` class (the section starting with `# --- stop_gate.py (Stop) ---` through the last test method before `# --- primer.py`).

Also delete the `TestStopGateWithMockBinary` class (around line 847) and any other test classes that reference `stop_gate.py` or `write_guard.py` directly.

- [ ] **Step 3: Update test_verify_hooks.py**

In `tests/test_verify_hooks.py`, update the `test_passes_with_all_hooks` function. Replace `write_guard.py` with `pre_tool_hook.py` and `stop_gate.py` with `stop_hook.py` in the hook definitions:

```python
def test_passes_with_all_hooks(tmp_path):
    """verify_hooks exits 0 when all required hooks are present."""
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    hooks = {
        "PreToolUse": [
            {"matcher": "Write|Edit", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/_sahjhan_bootstrap.py"},
                {"type": "command", "command": "python enforcement/hooks/pre_tool_hook.py"},
            ]},
            {"matcher": "Read", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/_sahjhan_bootstrap.py"},
            ]},
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/commit_gate.py"},
            ]},
        ],
        "PostToolUse": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/post_tool_hook.py"},
            ]},
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/bash_guard.py"},
                {"type": "command", "command": "python enforcement/hooks/protocol_tracker.py"},
            ]},
        ],
        "UserPromptSubmit": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/primer.py"},
            ]},
        ],
        "Stop": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/stop_hook.py"},
            ]},
        ],
        "SubagentStop": [
            {"matcher": "", "hooks": [
                {"type": "command", "command": "python enforcement/hooks/lens_quiz.py"},
            ]},
        ],
    }
    settings.write_text(json.dumps({"hooks": hooks}))
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--settings", str(settings)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0
```

Do the same for `test_detects_partial_hooks` — update the hook references.

- [ ] **Step 4: Update test_protocol_enforcement.py**

Find the test that imports from `write_guard` (around line 654-656). Replace it to test that `pre_tool_hook.py` exists and is importable:

```python
def test_pre_tool_hook_exists(self):
    """pre_tool_hook.py must exist as write_guard replacement."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pre_tool_hook",
        os.path.join(REPO_ROOT, "enforcement", "hooks", "pre_tool_hook.py"),
    )
    assert spec is not None, "pre_tool_hook.py must exist"
```

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: all tests pass (no references to deleted files remain)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(holtz): remove write_guard.py and stop_gate.py, update all test references"
```

---

### Task 9: Run linting and type checks

**Files:** None (verification only)

- [ ] **Step 1: Run ruff**

```bash
ruff check .
```

Expected: no errors

- [ ] **Step 2: Run mypy**

```bash
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

Expected: no errors

- [ ] **Step 3: Fix any issues found**

If ruff or mypy report issues in the new files, fix them.

- [ ] **Step 4: Run full test suite with coverage**

```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov-report=term-missing --cov-fail-under=60
```

Expected: all tests pass, coverage >= 60%

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix(holtz): resolve lint and type issues in new hook scripts"
```

(Skip commit if no changes needed.)

---

### Task 10: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

Read `README.md` in full to re-familiarize with the voice and structure before editing.

- [ ] **Step 2: Update "The hooks" section**

The hooks section (starting around line 206) currently describes 9 hooks. It needs to be rewritten to reflect the new architecture while maintaining the authorial voice. The section should cover:

- The shift from bespoke Python to declarative `hooks.toml` — framed as a natural evolution, not a rewrite
- **TDD gate** — a new paragraph after the current write guard paragraph. The gate that makes "write a failing test first" mechanically unavoidable. Not advisory. Not a suggestion. The edit doesn't go through.
- **Completion blocker** — integrated into the stop gate paragraph. The stop gate now checks two things: state and output. If the agent says "audit complete" while in fix_loop, the stop is blocked with a message telling it to check `sahjhan status`.
- **Stall monitors** — a new paragraph. After 20 events in fix_loop without a state transition, a warning surfaces on every tool use. Not a block. A warning. The kind that gets louder.
- **Auto-recording** — a new paragraph. Every file read, every edit, every search, every bash command. Ground truth about what the agent actually did, independent of what it claims. The ledger knows.
- **Edit accumulation warning** — folded into the commit gate or stall monitor paragraph naturally

Update the hook count from "Nine hooks" to reflect the new total (the hooks.toml adds enforcement rules, not separate hook scripts — the count refers to registered Claude Code hooks which is now 10 with post_tool_hook added).

- [ ] **Step 3: Update "What's inside" line**

Line 233: Update the counts. The hook count changes (now 10 enforcement hooks with post_tool_hook), and hooks.toml is a new config file worth mentioning.

- [ ] **Step 4: Update run history**

Add a brief entry after the "Run 25" paragraph (around line 201) about the 0.7.0 upgrade. Something in the style of:

> **Run 31** was the hooks.toml migration — replacing Python enforcement with declarative rules evaluated by the Sahjhan binary. [Brief details matching the voice]

Keep it to one paragraph. Match the style of the other run entries.

- [ ] **Step 5: Update "Steps 15-16: Convergence" paragraph**

Line 152: update the enforcement description to mention hooks.toml-based monitors alongside the existing circuit breakers.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "feat(holtz): update README for sahjhan 0.7.0 runtime hooks"
```

---

### Task 11: Add bootstrap protection for hooks.toml

**Files:**
- Modify: `enforcement/hooks/_sahjhan_bootstrap.py:16-21`

- [ ] **Step 1: Verify hooks.toml is already protected**

Check that the bootstrap PROTECTED list includes `"enforcement/"` which already covers `enforcement/hooks.toml`. Read `enforcement/hooks/_sahjhan_bootstrap.py` lines 16-21.

The current list is:
```python
PROTECTED = [
    "enforcement/",
    "bin/sahjhan",
    "hooks/hooks.json",
    "_sahjhan_bootstrap.py",
]
```

Since `enforcement/` covers `enforcement/hooks.toml`, no change is needed. Verify by running:

```bash
python -c "
import json, sys
event = {'tool_input': {'file_path': 'enforcement/hooks.toml'}, 'cwd': '$(pwd)'}
print(json.dumps(event))
" | python enforcement/hooks/_sahjhan_bootstrap.py
```

Expected: output containing `"permissionDecision": "block"` (hooks.toml is under enforcement/)

- [ ] **Step 2: Skip this task if already protected**

No commit needed — hooks.toml is already covered by the `enforcement/` protection.

---

### Task 12: Final validation

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 2: Run ruff**

```bash
ruff check .
```

Expected: no errors

- [ ] **Step 3: Run mypy**

```bash
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

Expected: no errors

- [ ] **Step 4: Validate sahjhan config**

```bash
bin/sahjhan --config-dir enforcement validate
```

Expected: exit 0, all config files valid including hooks.toml

- [ ] **Step 5: Verify hook registration**

```bash
python enforcement/hooks/verify_hooks.py --settings .claude/settings.local.json
```

Expected: exit 0, all required hooks present

- [ ] **Step 6: Smoke test hook eval**

```bash
bin/sahjhan --config-dir enforcement --json hook eval --event PreToolUse --tool Edit --file src/main.py
```

Expected: JSON output with `"decision": "allow"` (no active ledger, so no hooks fire)

- [ ] **Step 7: Verify new files are committed**

```bash
git status
```

Expected: clean working tree, all new files committed

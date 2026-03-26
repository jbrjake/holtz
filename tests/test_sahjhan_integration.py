"""Integration tests for Sahjhan enforcement hooks.

Tests the hook scripts in enforcement/hooks/ using the correct
Claude Code output protocol (hookSpecificOutput with permissionDecision
for PreToolUse hooks, decision/reason for Stop hooks).
"""

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")


def run_enforcement_hook(hook_name, event, cwd=None):
    """Run an enforcement hook script with the given event JSON on stdin."""
    script = os.path.join(ENFORCEMENT_HOOKS_DIR, hook_name)
    result = subprocess.run(
        [sys.executable, script],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd or REPO_ROOT,
    )
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output, result.stderr


def assert_allowed(code, output):
    """Assert that a PreToolUse hook allowed the operation."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is True
    assert output.get("suppressOutput") is True


def assert_blocked(code, output, reason_substring=""):
    """Assert that a PreToolUse hook blocked the operation."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is False
    hook_output = output.get("hookSpecificOutput", {})
    assert hook_output.get("permissionDecision") == "block", (
        f"Expected block, got: {hook_output}"
    )
    if reason_substring:
        reason = hook_output.get("permissionDecisionReason", "")
        assert reason_substring.lower() in reason.lower(), (
            f"Expected '{reason_substring}' in reason, got: {reason}"
        )


# --- _sahjhan_bootstrap.py (PreToolUse) ---


class TestBootstrapHook:
    """Tests for the self-protecting bootstrap hook."""

    def test_blocks_enforcement_directory(self):
        """Bootstrap hook blocks edits to enforcement/ directory."""
        event = {
            "tool_input": {"file_path": "enforcement/protocol.toml"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_binary_modification(self):
        """Bootstrap hook blocks edits to bin/sahjhan*."""
        event = {
            "tool_input": {"file_path": "bin/sahjhan-aarch64-apple-darwin"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_self_modification(self):
        """Bootstrap hook blocks edits to itself."""
        event = {
            "tool_input": {"file_path": "enforcement/hooks/_sahjhan_bootstrap.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_hooks_json_modification(self):
        """Bootstrap hook blocks edits to hooks.json."""
        event = {
            "tool_input": {"file_path": "hooks/hooks.json"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_allows_source_files(self):
        """Bootstrap hook allows normal source file edits."""
        event = {
            "tool_input": {"file_path": "skills/holtz/scripts/convergence_check.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_allows_empty_path(self):
        """Bootstrap hook allows when no file path is provided."""
        event = {"tool_input": {}, "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_path_traversal(self):
        """Bootstrap hook blocks path traversal attempts to enforcement/."""
        event = {
            "tool_input": {"file_path": "../../enforcement/protocol.toml"},
            "cwd": os.path.join(REPO_ROOT, "docs", "holtz"),
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_absolute_enforcement_path(self):
        """Bootstrap hook blocks absolute paths to enforcement/."""
        event = {
            "tool_input": {"file_path": os.path.join(REPO_ROOT, "enforcement", "states.toml")},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")


# --- write_guard.py (PreToolUse) ---


class TestWriteGuard:
    """Tests for the managed-path write guard."""

    def test_blocks_managed_path(self):
        """Write guard blocks Write/Edit to docs/holtz/."""
        event = {
            "tool_input": {"file_path": "docs/holtz/PUNCHLIST.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_blocked(code, output, "managed by sahjhan")

    def test_blocks_managed_subdirectory(self):
        """Write guard blocks writes to subdirectories of managed paths."""
        event = {
            "tool_input": {"file_path": "docs/holtz/recon/step0.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_blocked(code, output, "managed by sahjhan")

    def test_allows_non_managed_path(self):
        """Write guard allows writes outside managed paths."""
        event = {
            "tool_input": {"file_path": "src/main.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)

    def test_allows_empty_path(self):
        """Write guard allows when no file path is provided."""
        event = {"tool_input": {}, "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)

    def test_allows_docs_outside_holtz(self):
        """Write guard allows writes to docs/ but not docs/holtz/."""
        event = {
            "tool_input": {"file_path": "docs/README.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)


# --- bash_guard.py (PostToolUse) ---


class TestBashGuard:
    """Tests for the Bash manifest verification guard."""

    def test_allows_without_sahjhan_binary(self):
        """Bash guard allows when no Sahjhan binary is installed."""
        event = {"tool_name": "Bash", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("bash_guard.py", event)
        # Should allow since no binary exists yet
        assert code == 0
        assert output.get("continue") is True

    def test_allows_non_bash_tools(self):
        """Bash guard allows non-Bash tool calls."""
        event = {"tool_name": "Read", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("bash_guard.py", event)
        assert code == 0
        assert output.get("continue") is True


# --- stop_gate.py (Stop) ---


class TestStopGate:
    """Tests for the stop gate."""

    def test_allows_without_sahjhan_binary(self):
        """Stop gate allows when no Sahjhan binary is installed."""
        code, output, _ = run_enforcement_hook("stop_gate.py", {})
        assert code == 0
        # No binary = no output = allow
        assert output == {}

    def test_allows_without_active_run(self):
        """Stop gate allows when no active Sahjhan run exists."""
        code, output, _ = run_enforcement_hook("stop_gate.py", {})
        assert code == 0
        assert output == {}


# --- primer.py (UserPromptSubmit) ---


class TestPrimer:
    """Tests for the UserPromptSubmit primer hook."""

    def test_allows_without_sahjhan_binary(self):
        """Primer allows when no Sahjhan binary is installed."""
        event = {"user_message": "continue", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("primer.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_allows_without_active_run(self):
        """Primer allows when no active Sahjhan run exists."""
        event = {"user_message": "continue", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("primer.py", event)
        assert code == 0
        assert output.get("continue") is True

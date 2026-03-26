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

    def test_allows_enforcement_prefix_collision(self):
        """BH-014: Bootstrap allows enforcement_evil/ (prefix collision)."""
        event = {
            "tool_input": {"file_path": "enforcement_evil/bad.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)


# --- write_guard.py (PreToolUse) ---


class TestWriteGuard:
    """Tests for the managed-path write guard."""

    def test_blocks_merge_report(self):
        """Write guard blocks MERGE-REPORT.md (sahjhan-rendered)."""
        event = {
            "tool_input": {"file_path": "docs/holtz/MERGE-REPORT.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_blocked(code, output, "managed by Sahjhan")

    def test_blocks_punchlist_md(self):
        """Write guard blocks PUNCHLIST.md (sahjhan-rendered)."""
        event = {
            "tool_input": {"file_path": "docs/holtz/PUNCHLIST.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_blocked(code, output, "managed by Sahjhan")

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

    def test_allows_recon_subdirectory(self):
        """BH-009: Write guard allows writes to docs/holtz/recon/ (not managed)."""
        event = {
            "tool_input": {"file_path": "docs/holtz/recon/step0.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)

    def test_allows_audit_subdirectory(self):
        """BH-009: Write guard allows writes to docs/holtz/audit/ (not managed)."""
        event = {
            "tool_input": {"file_path": "docs/holtz/audit/1-doc-claims.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)

    def test_allows_impact_graph(self):
        """BH-009: Write guard allows writes to docs/holtz/impact-graph.json."""
        event = {
            "tool_input": {"file_path": "docs/holtz/impact-graph.json"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)

    def test_allows_justine_directory(self):
        """BH-009: Write guard allows writes to docs/holtz/justine/."""
        event = {
            "tool_input": {"file_path": "docs/holtz/justine/PUNCHLIST.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_allowed(code, output)

    def test_blocks_status_md(self):
        """BH-009: Write guard blocks STATUS.md (sahjhan-rendered)."""
        event = {
            "tool_input": {"file_path": "docs/holtz/STATUS.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_blocked(code, output, "managed by Sahjhan")

    def test_blocks_summary_md(self):
        """BH-009: Write guard blocks SUMMARY.md (sahjhan-rendered)."""
        event = {
            "tool_input": {"file_path": "docs/holtz/SUMMARY.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("write_guard.py", event)
        assert_blocked(code, output, "managed by Sahjhan")

    def test_allows_prefix_collision_path(self):
        """BH-014: Write guard does not block docs/holtz2/ (prefix collision)."""
        event = {
            "tool_input": {"file_path": "docs/holtz2/test.md"},
            "cwd": REPO_ROOT,
        }
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

    def test_violation_cmd_uses_field_syntax(self):
        """BH-007/BH-013: Violation command uses --field key=value, not bare args."""
        source_path = os.path.join(ENFORCEMENT_HOOKS_DIR, "bash_guard.py")
        with open(source_path) as f:
            source = f.read()
        # Must not use bare --file_path or --detail args
        assert "--file_path" not in source.split("--field"), \
            "bash_guard still uses bare --file_path arg"
        assert '"--file_path"' not in source, \
            "bash_guard still uses bare --file_path arg"
        assert '"--detail"' not in source, \
            "bash_guard still uses bare --detail arg"
        # Must use --field syntax for all event fields
        assert '"--field"' in source, "bash_guard should use --field syntax"
        # Must include required fields
        assert "project=holtz" in source, "bash_guard missing project field"
        assert "auditor=holtz" in source, "bash_guard missing auditor field"

    def test_exception_catches_oserror(self):
        """BH-015: bash_guard catches OSError (includes PermissionError)."""
        source_path = os.path.join(ENFORCEMENT_HOOKS_DIR, "bash_guard.py")
        with open(source_path) as f:
            source = f.read()
        assert "OSError" in source, "bash_guard should catch OSError"
        # Should not have bare FileNotFoundError without OSError
        lines = source.split("\n")
        for line in lines:
            if "except" in line and "FileNotFoundError" in line and "OSError" not in line:
                raise AssertionError(
                    f"bash_guard catches FileNotFoundError without OSError: {line.strip()}"
                )


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


# --- _active_ledger (enforcement/hooks/_common.py) ---


class TestActiveLedger:
    """Tests for active ledger detection in hooks."""

    def test_active_ledger_returns_name(self, tmp_path):
        """_active_ledger returns the ledger name from marker file."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-22\n")
        # Import the function
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_common_enforcement",
            os.path.join(REPO_ROOT, "enforcement", "hooks", "_common.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod._active_ledger(str(tmp_path))
        assert result == "run-22"

    def test_active_ledger_returns_none_missing(self, tmp_path):
        """_active_ledger returns None when no marker file exists."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_common_enforcement",
            os.path.join(REPO_ROOT, "enforcement", "hooks", "_common.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod._active_ledger(str(tmp_path))
        assert result is None

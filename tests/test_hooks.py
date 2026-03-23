"""Tests for hooks/ modules.

All hooks output modern-format JSON to stdout and exit 0.
Decision semantics are encoded in the JSON payload:

  - allow:  {"continue": true,  "suppressOutput": true, ...}
  - warn:   {"continue": true,  "suppressOutput": false, "additionalContext": ...}
  - block:  {"continue": false, "hookSpecificOutput": {"permissionDecision": "block", ...}}

See: https://github.com/anthropics/claude-code/issues/17088
"""

import json
import os
import subprocess
import sys

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")


def run_hook(hook_name, event, cwd=None):
    """Run a hook script with the given event JSON on stdin.

    Returns (exit_code, output_dict, stderr) where output_dict is
    the parsed JSON from stdout (or {} if stdout is empty/invalid).
    """
    script = os.path.join(HOOKS_DIR, hook_name)
    result = subprocess.run(
        [sys.executable, script],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
    )
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output, result.stderr


def assert_allowed(code, output):
    """Assert that the hook allowed the operation."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is True
    assert output.get("suppressOutput") is True


def assert_blocked(code, output, reason_substring=""):
    """Assert that the hook blocked the operation (PreToolUse)."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is False
    hook_output = output.get("hookSpecificOutput", {})
    assert hook_output.get("permissionDecision") == "block"
    if reason_substring:
        assert reason_substring in hook_output.get("permissionDecisionReason", "")


def assert_warned(code, output, reason_substring=""):
    """Assert that the hook warned but allowed the operation."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is True
    assert output.get("suppressOutput") is False
    context = output.get("additionalContext", "")
    if reason_substring:
        assert reason_substring in context


# --- _common.py output format ---


class TestModernOutputFormat:
    """Tests for modern hook output format from _common.py functions."""

    def _run_common_func(self, func_name, *args):
        """Run a _common.py function in a subprocess.

        Returns (exit_code, parsed_stdout_json, stderr).
        """
        args_str = ", ".join(repr(a) for a in args)
        code_str = (
            f"import sys; sys.path.insert(0, {HOOKS_DIR!r}); "
            f"from _common import {func_name}; {func_name}({args_str})"
        )
        result = subprocess.run(
            [sys.executable, "-c", code_str],
            capture_output=True,
            text=True,
            timeout=10,
        )
        try:
            output = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            output = {}
        return result.returncode, output, result.stderr

    # -- exit_ok --

    def test_exit_ok_exits_zero(self):
        code, _, _ = self._run_common_func("exit_ok")
        assert code == 0

    def test_exit_ok_outputs_valid_json(self):
        _, output, _ = self._run_common_func("exit_ok")
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True

    def test_exit_ok_no_stderr(self):
        _, _, stderr = self._run_common_func("exit_ok")
        assert stderr == ""

    def test_exit_ok_pretooluse_includes_hook_specific_output(self):
        """PreToolUse exit_ok includes hookSpecificOutput to avoid phantom error."""
        _, output, _ = self._run_common_func("exit_ok", "PreToolUse")
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "allow"
        assert hook_output["permissionDecisionReason"] == ""

    def test_exit_ok_non_pretooluse_omits_hook_specific_output(self):
        """Non-PreToolUse exit_ok does not include hookSpecificOutput."""
        _, output, _ = self._run_common_func("exit_ok")
        assert "hookSpecificOutput" not in output

    # -- exit_warn --

    def test_exit_warn_exits_zero(self):
        code, _, _ = self._run_common_func("exit_warn", "test warning")
        assert code == 0

    def test_exit_warn_outputs_valid_json(self):
        _, output, _ = self._run_common_func("exit_warn", "test warning")
        assert output.get("continue") is True
        assert output.get("suppressOutput") is False
        assert output.get("additionalContext") == "test warning"

    def test_exit_warn_no_stderr(self):
        _, _, stderr = self._run_common_func("exit_warn", "test warning")
        assert stderr == ""

    # -- exit_block --

    def test_exit_block_exits_zero(self):
        code, _, _ = self._run_common_func("exit_block", "test block")
        assert code == 0

    def test_exit_block_outputs_valid_json(self):
        _, output, _ = self._run_common_func("exit_block", "test block")
        assert output.get("continue") is False
        assert output.get("suppressOutput") is False

    def test_exit_block_includes_hook_specific_output(self):
        _, output, _ = self._run_common_func("exit_block", "reason here")
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output["hookEventName"] == "PreToolUse"
        assert hook_output["permissionDecision"] == "block"
        assert hook_output["permissionDecisionReason"] == "reason here"

    def test_exit_block_no_stderr(self):
        _, _, stderr = self._run_common_func("exit_block", "test block")
        assert stderr == ""


# --- _common.py read_event ---


class TestReadEvent:
    """Tests for _common.read_event via hooks that use it."""

    def test_empty_stdin_does_not_crash(self):
        """Hooks should handle empty stdin gracefully."""
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "impact_graph_gate.py")],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_malformed_json_does_not_crash(self):
        """Hooks should handle malformed JSON gracefully."""
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "impact_graph_gate.py")],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


# --- impact_graph_gate.py (PreToolUse) ---


class TestImpactGraphGate:
    """Tests for the impact graph gate hook."""

    def test_allows_non_audit_writes(self):
        """Writes outside docs/holtz/audit/ should be allowed."""
        event = {"tool_input": {"file_path": "docs/holtz/recon/0a.md"}}
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_allowed(code, output)

    def test_allows_audit_write_when_graph_exists(self, tmp_path):
        """Writes to audit/ should be allowed when impact-graph.json exists."""
        docs = tmp_path / "docs" / "holtz"
        docs.mkdir(parents=True)
        (docs / "impact-graph.json").write_text("{}")
        event = {
            "tool_input": {"file_path": str(docs / "audit" / "1-doc-claims.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_allowed(code, output)

    def test_blocks_audit_write_when_graph_missing(self, tmp_path):
        """Writes to audit/ should be blocked when impact-graph.json is missing."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "audit" / "1.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_blocked(code, output, "BLOCKED")

    def test_allows_empty_file_path(self):
        """Empty file_path should be allowed."""
        event = {"tool_input": {"file_path": ""}}
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_allowed(code, output)

    def test_justine_audit_checks_justine_graph(self, tmp_path):
        """Justine audit writes should check Justine's graph, not Holtz's."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "justine" / "audit" / "1.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_blocked(code, output, "justine")

    def test_pretooluse_allow_has_hook_specific_output(self):
        """PreToolUse allow should include hookSpecificOutput."""
        event = {"tool_input": {"file_path": "src/foo.py"}}
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert code == 0
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output.get("permissionDecision") == "allow"

    def test_pretooluse_block_has_hook_specific_output(self, tmp_path):
        """PreToolUse block should include hookSpecificOutput."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "audit" / "1.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert code == 0
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output.get("permissionDecision") == "block"
        assert hook_output.get("hookEventName") == "PreToolUse"


# --- status_staleness_gate.py (PreToolUse) ---


class TestStatusStalenessGate:
    """Tests for the status staleness gate hook."""

    def test_allows_non_holtz_writes(self):
        """Writes outside docs/holtz/ should be allowed."""
        event = {"tool_input": {"file_path": "src/foo.py"}}
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_allowed(code, output)

    def test_allows_status_md_write(self, tmp_path):
        """Writing to STATUS.md itself should always be allowed."""
        status = tmp_path / "docs" / "holtz" / "STATUS.md"
        status.parent.mkdir(parents=True)
        status.write_text("old")
        # Make it stale
        os.utime(str(status), (0, 0))
        event = {
            "tool_input": {"file_path": str(status)},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_allowed(code, output)

    def test_allows_fresh_status(self, tmp_path):
        """Writes should be allowed when STATUS.md is fresh."""
        status = tmp_path / "docs" / "holtz" / "STATUS.md"
        status.parent.mkdir(parents=True)
        status.write_text("current")
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "PUNCHLIST.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_allowed(code, output)

    def test_blocks_stale_status(self, tmp_path):
        """Writes should be blocked when STATUS.md is stale."""
        status = tmp_path / "docs" / "holtz" / "STATUS.md"
        status.parent.mkdir(parents=True)
        status.write_text("stale")
        os.utime(str(status), (0, 0))
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "PUNCHLIST.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_blocked(code, output, "BLOCKED")

    def test_allows_when_no_status_exists(self, tmp_path):
        """First write of a run (no STATUS.md yet) should be allowed."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "recon" / "0a.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_allowed(code, output)

    def test_status_exemption_scoped_to_protocol_paths(self, tmp_path):
        """Only the protocol STATUS.md paths should be exempt, not arbitrary files."""
        status = tmp_path / "docs" / "holtz" / "STATUS.md"
        status.parent.mkdir(parents=True)
        status.write_text("stale")
        os.utime(str(status), (0, 0))
        # A file named STATUS.md in a subdirectory should NOT be exempt
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "recon" / "STATUS.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_blocked(code, output)

    def test_pretooluse_allow_has_hook_specific_output(self):
        """PreToolUse allow should include hookSpecificOutput."""
        event = {"tool_input": {"file_path": "src/foo.py"}}
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert code == 0
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output.get("permissionDecision") == "allow"


# --- artifact_verification.py (PostToolUse) ---


class TestArtifactVerification:
    """Tests for the artifact verification hook."""

    def test_ignores_non_impact_graph_commands(self):
        """Commands that don't run impact_graph.py should be allowed."""
        event = {"tool_input": {"command": "python -m pytest test_foo.py"}}
        code, output, _ = run_hook("artifact_verification.py", event)
        assert_allowed(code, output)

    def test_ignores_test_impact_graph_filename(self):
        """Commands referencing test_impact_graph.py should not trigger the check."""
        event = {"tool_input": {"command": "python -m pytest test_impact_graph.py"}}
        code, output, _ = run_hook("artifact_verification.py", event)
        assert_allowed(code, output)

    def test_allows_when_graph_exists(self, tmp_path):
        """Running impact_graph.py should be allowed when graph file exists."""
        graph = tmp_path / "docs" / "holtz" / "impact-graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text("{}")
        event = {
            "tool_input": {"command": f"python impact_graph.py --graph {graph} add_node x y z"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("artifact_verification.py", event)
        assert_allowed(code, output)

    def test_warns_when_graph_missing(self, tmp_path):
        """Running impact_graph.py should warn when graph file doesn't exist."""
        event = {
            "tool_input": {"command": "python impact_graph.py --graph docs/holtz/impact-graph.json add_node x y z"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("artifact_verification.py", event)
        assert_warned(code, output, "BLOCKED")

    def test_skips_shell_variable_paths(self):
        """Commands with shell variable in --graph path should be skipped."""
        event = {"tool_input": {"command": 'python impact_graph.py --graph "$GRAPH" add_node x y z'}}
        code, output, _ = run_hook("artifact_verification.py", event)
        assert_allowed(code, output)

    def test_default_graph_path_when_no_graph_flag(self, tmp_path):
        """When --graph is not specified, default path should be used."""
        event = {
            "tool_input": {"command": "python impact_graph.py add_node x y z"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("artifact_verification.py", event)
        assert_warned(code, output, "impact-graph.json")

    def test_posttooluse_does_not_include_hook_specific_output(self):
        """PostToolUse hooks should not include hookSpecificOutput."""
        event = {"tool_input": {"command": "python -m pytest test_foo.py"}}
        code, output, _ = run_hook("artifact_verification.py", event)
        assert code == 0
        assert "hookSpecificOutput" not in output


# --- subagent_findings_check.py (SubagentStop) ---


class TestSubagentFindingsCheck:
    """Tests for the subagent findings check hook."""

    def test_allows_empty_message(self):
        """Empty last_assistant_message should be allowed."""
        event = {"last_assistant_message": ""}
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_allowed(code, output)

    def test_allows_no_holtz_paths(self):
        """Messages without docs/holtz/ paths should be allowed."""
        event = {"last_assistant_message": "I fixed the bug in src/foo.py"}
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_allowed(code, output)

    def test_allows_existing_files(self, tmp_path):
        """Referenced files that exist should not trigger a warning."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True)
        (holtz / "PUNCHLIST.md").write_text("items")
        event = {
            "last_assistant_message": "I wrote findings to docs/holtz/PUNCHLIST.md",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_allowed(code, output)

    def test_warns_missing_files(self, tmp_path):
        """Referenced files that don't exist should trigger a warning."""
        event = {
            "last_assistant_message": "I wrote findings to docs/holtz/PUNCHLIST.md",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_warned(code, output, "WARNING")
        assert "PUNCHLIST.md" in output.get("additionalContext", "")

    def test_deduplicates_paths(self, tmp_path):
        """Multiple references to the same path should be deduplicated."""
        event = {
            "last_assistant_message": "Wrote docs/holtz/FOO.md and referenced docs/holtz/FOO.md again",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_warned(code, output)
        # Should only mention FOO.md once
        assert output.get("additionalContext", "").count("FOO.md") == 1

    def test_subagentstop_does_not_include_hook_specific_output(self):
        """SubagentStop hooks should not include hookSpecificOutput."""
        event = {"last_assistant_message": ""}
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert code == 0
        assert "hookSpecificOutput" not in output

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


def assert_stop_blocked(code, output, reason_substring=""):
    """Assert that the Stop hook blocked the stop."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("decision") == "block"
    if reason_substring:
        assert reason_substring in output.get("reason", "")


def assert_stop_allowed(code, output):
    """Assert that the Stop hook allowed the stop (no output)."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output == {}


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

    # -- exit_stop_allow --

    def test_exit_stop_allow_exits_zero(self):
        code, _, _ = self._run_common_func("exit_stop_allow")
        assert code == 0

    def test_exit_stop_allow_no_output(self):
        """Stop allow should produce no stdout (empty = allow)."""
        _, output, _ = self._run_common_func("exit_stop_allow")
        assert output == {}

    def test_exit_stop_allow_no_stderr(self):
        _, _, stderr = self._run_common_func("exit_stop_allow")
        assert stderr == ""

    # -- exit_stop_block --

    def test_exit_stop_block_exits_zero(self):
        code, _, _ = self._run_common_func("exit_stop_block", "test reason")
        assert code == 0

    def test_exit_stop_block_outputs_stop_format(self):
        """Stop block should use decision/reason format, not PreToolUse format."""
        _, output, _ = self._run_common_func("exit_stop_block", "test reason")
        assert output.get("decision") == "block"
        assert output.get("reason") == "test reason"

    def test_exit_stop_block_no_pretooluse_fields(self):
        """Stop hooks should NOT use PreToolUse format."""
        _, output, _ = self._run_common_func("exit_stop_block", "test reason")
        assert "hookSpecificOutput" not in output
        assert "continue" not in output

    def test_exit_stop_block_no_stderr(self):
        _, _, stderr = self._run_common_func("exit_stop_block", "test reason")
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

    def test_blocks_punchlist_merged_when_graph_missing(self, tmp_path):
        """Writes to PUNCHLIST-MERGED.md should be blocked when graph is missing (BH-004)."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "PUNCHLIST-MERGED.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_blocked(code, output, "BLOCKED")

    def test_allows_punchlist_merged_when_graph_exists(self, tmp_path):
        """Writes to PUNCHLIST-MERGED.md should be allowed when graph exists (BH-004)."""
        docs = tmp_path / "docs" / "holtz"
        docs.mkdir(parents=True)
        (docs / "impact-graph.json").write_text("{}")
        event = {
            "tool_input": {"file_path": str(docs / "PUNCHLIST-MERGED.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_allowed(code, output)

    def test_blocks_justine_punchlist_when_graph_missing(self, tmp_path):
        """Writes to Justine's PUNCHLIST.md should check Justine's graph (BH-006)."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "justine" / "PUNCHLIST.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_blocked(code, output, "justine")

    def test_allows_justine_punchlist_when_graph_exists(self, tmp_path):
        """Writes to Justine's PUNCHLIST.md should be allowed when Justine's graph exists (BH-006)."""
        justine_dir = tmp_path / "docs" / "holtz" / "justine"
        justine_dir.mkdir(parents=True)
        (justine_dir / "impact-graph.json").write_text("{}")
        event = {
            "tool_input": {"file_path": str(justine_dir / "PUNCHLIST.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("impact_graph_gate.py", event)
        assert_allowed(code, output)


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

    def test_blocks_when_status_missing_but_recon_exists(self, tmp_path):
        """STATUS.md missing but recon/ exists = deleted mid-run, should block (BH-005)."""
        holtz = tmp_path / "docs" / "holtz"
        recon = holtz / "recon"
        recon.mkdir(parents=True)
        (recon / "0a.md").write_text("recon data")
        event = {
            "tool_input": {"file_path": str(holtz / "PUNCHLIST.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_blocked(code, output, "missing")

    def test_blocks_when_status_missing_but_punchlist_exists(self, tmp_path):
        """STATUS.md missing but PUNCHLIST.md exists = deleted mid-run, should block (BH-005)."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True)
        (holtz / "PUNCHLIST.md").write_text("items")
        event = {
            "tool_input": {"file_path": str(holtz / "recon" / "0b.md")},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("status_staleness_gate.py", event)
        assert_blocked(code, output, "missing")

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


# --- convergence_gate.py (Stop) ---


class TestConvergenceGate:
    """Tests for the convergence gate Stop hook."""

    def _make_status(self, tmp_path, content="**Phase:** 4\n**Status:** IN PROGRESS", stale=False):
        """Create a STATUS.md with the given content."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True, exist_ok=True)
        status = holtz / "STATUS.md"
        status.write_text(
            f"# Holtz Status\n\n{content}\n\n## Next Action\nContinue fixing items."
        )
        if stale:
            os.utime(str(status), (0, 0))
        return status

    def _make_summary(self, tmp_path):
        """Create a SUMMARY.md (indicates convergence)."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True, exist_ok=True)
        (holtz / "SUMMARY.md").write_text("# Summary\nConverged.")

    def _make_punchlist(self, tmp_path, open_count=3):
        """Create a PUNCHLIST.md with open items."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True, exist_ok=True)
        items = "\n".join(
            f"### BH-{i:03d}: Item {i}\n**Status:** OPEN\n"
            for i in range(1, open_count + 1)
        )
        (holtz / "PUNCHLIST.md").write_text(f"# Punchlist\n\n{items}")

    def test_allows_when_no_holtz_dir(self, tmp_path):
        """No docs/holtz/ means no active run — allow stop."""
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_allowed(code, output)

    def test_allows_when_summary_exists(self, tmp_path):
        """SUMMARY.md exists means converged — allow stop."""
        self._make_status(tmp_path)
        self._make_summary(tmp_path)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_allowed(code, output)

    def test_allows_when_stop_hook_active(self, tmp_path):
        """Second stop attempt (stop_hook_active=true) — allow regardless."""
        self._make_status(tmp_path)
        event = {"cwd": str(tmp_path), "stop_hook_active": True}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_allowed(code, output)

    def test_allows_when_status_complete(self, tmp_path):
        """STATUS.md says COMPLETE — allow stop."""
        self._make_status(tmp_path, content="**Phase:** 6\n**Status:** COMPLETE")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_allowed(code, output)

    def test_allows_when_status_converged(self, tmp_path):
        """STATUS.md says CONVERGED — allow stop."""
        self._make_status(tmp_path, content="**Phase:** 6\n**Status:** CONVERGED")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_allowed(code, output)

    def test_allows_when_status_stale(self, tmp_path):
        """Stale STATUS.md (>30 min) likely from previous session — allow stop."""
        self._make_status(tmp_path, stale=True)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_allowed(code, output)

    def test_blocks_when_active_run(self, tmp_path):
        """Active run, not converged — block stop."""
        self._make_status(tmp_path)
        self._make_punchlist(tmp_path, open_count=5)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_blocked(code, output, "CONVERGENCE GATE")

    def test_block_includes_phase(self, tmp_path):
        """Block message should include current phase."""
        self._make_status(tmp_path, content="**Phase:** 4\n**Status:** IN PROGRESS")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_blocked(code, output, "Phase: 4")

    def test_block_includes_open_count(self, tmp_path):
        """Block message should include approximate open item count."""
        self._make_status(tmp_path)
        self._make_punchlist(tmp_path, open_count=3)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_blocked(code, output, "~3")

    def test_blocks_converging_status(self, tmp_path):
        """STATUS.md says CONVERGING (not CONVERGED) — block stop."""
        self._make_status(tmp_path, content="**Phase:** 6\n**Status:** CONVERGING")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_blocked(code, output, "CONVERGENCE GATE")

    def test_stop_output_format_has_no_pretooluse_fields(self, tmp_path):
        """Stop hook output should use Stop format, not PreToolUse format."""
        self._make_status(tmp_path)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert code == 0
        assert output.get("decision") == "block"
        assert "reason" in output
        assert "hookSpecificOutput" not in output
        assert "continue" not in output

    def test_handles_empty_stdin(self):
        """Empty stdin should not crash."""
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "convergence_gate.py")],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_blocks_with_no_punchlist(self, tmp_path):
        """Active run with no punchlist yet (mid-recon) — still block."""
        self._make_status(tmp_path, content="**Phase:** 0\n**Status:** IN PROGRESS")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_blocked(code, output, "CONVERGENCE GATE")

    def test_block_message_includes_clear_instruction(self, tmp_path):
        """Block reason should tell Holtz to instruct user to /clear."""
        self._make_status(tmp_path)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_hook("convergence_gate.py", event)
        assert_stop_blocked(code, output, "/clear")


# --- convergence_primer.py (UserPromptSubmit) ---


class TestConvergencePrimer:
    """Tests for the convergence primer UserPromptSubmit hook."""

    def _make_status(self, tmp_path, content="**Phase:** 4\n**Status:** IN PROGRESS"):
        """Create a STATUS.md with the given content."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True, exist_ok=True)
        status = holtz / "STATUS.md"
        status.write_text(
            f"# Holtz Status\n\n{content}\n\n## Next Action\nFix BH-005 via fast path."
        )
        return status

    def _make_summary(self, tmp_path):
        """Create a SUMMARY.md (indicates convergence)."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True, exist_ok=True)
        (holtz / "SUMMARY.md").write_text("# Summary\nConverged.")

    def test_silent_when_no_holtz_dir(self, tmp_path):
        """No docs/holtz/ means no active run — silent."""
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_allowed(code, output)

    def test_silent_when_summary_exists(self, tmp_path):
        """SUMMARY.md exists means converged — silent."""
        self._make_status(tmp_path)
        self._make_summary(tmp_path)
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_allowed(code, output)

    def test_silent_when_status_complete(self, tmp_path):
        """STATUS.md says COMPLETE — silent."""
        self._make_status(tmp_path, content="**Phase:** 6\n**Status:** COMPLETE")
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_allowed(code, output)

    def test_silent_when_status_converged(self, tmp_path):
        """STATUS.md says CONVERGED — silent."""
        self._make_status(tmp_path, content="**Phase:** 6\n**Status:** CONVERGED")
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_allowed(code, output)

    def test_injects_context_when_active(self, tmp_path):
        """Active run should inject resume context."""
        self._make_status(tmp_path)
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_warned(code, output, "HOLTZ CONVERGENCE LOOP")

    def test_context_includes_phase(self, tmp_path):
        """Injected context should include phase info."""
        self._make_status(tmp_path, content="**Phase:** 3\n**Status:** IN PROGRESS")
        event = {"cwd": str(tmp_path), "user_message": "continue"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_warned(code, output, "Phase 3")

    def test_context_includes_next_action(self, tmp_path):
        """Injected context should include next action from STATUS.md."""
        self._make_status(tmp_path)
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert_warned(code, output, "Fix BH-005")

    def test_handles_empty_stdin(self):
        """Empty stdin should not crash."""
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "convergence_primer.py")],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_handles_malformed_status(self, tmp_path):
        """Malformed STATUS.md should not crash, uses 'unknown' for missing fields."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True, exist_ok=True)
        (holtz / "STATUS.md").write_text("This is not a valid status file")
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        # Should still inject context with 'unknown' fields
        assert code == 0
        assert_warned(code, output, "HOLTZ CONVERGENCE LOOP")

    def test_userpromptsubmit_does_not_include_hook_specific_output(self, tmp_path):
        """UserPromptSubmit hooks should not include hookSpecificOutput."""
        self._make_status(tmp_path)
        event = {"cwd": str(tmp_path), "user_message": "go"}
        code, output, _ = run_hook("convergence_primer.py", event)
        assert code == 0
        assert "hookSpecificOutput" not in output

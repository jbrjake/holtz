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

    def test_exit_ok_outputs_valid_json(self):
        _, output, _ = self._run_common_func("exit_ok")
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True

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

    def test_exit_warn_outputs_valid_json(self):
        _, output, _ = self._run_common_func("exit_warn", "test warning")
        assert output.get("continue") is True
        assert output.get("suppressOutput") is False
        assert output.get("additionalContext") == "test warning"

    # -- exit_block --

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

    # -- exit_stop_allow --

    def test_exit_stop_allow_no_output(self):
        """Stop allow should produce no stdout (empty = allow)."""
        _, output, _ = self._run_common_func("exit_stop_allow")
        assert output == {}

    # -- exit_stop_block --

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



# --- _common.py mask_fenced_blocks ---


class TestMaskFencedBlocks:
    """Tests for _common.mask_fenced_blocks fence length enforcement.

    BH-004 run 16: mask_fenced_blocks must track fence character count so
    a 4-backtick fence is NOT closed by a 3-backtick line (CommonMark spec).
    """

    def _mask(self, text):
        code_str = (
            f"import sys; sys.path.insert(0, {HOOKS_DIR!r}); "
            f"from _common import mask_fenced_blocks; "
            f"print(mask_fenced_blocks({text!r}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code_str],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.rstrip("\n")

    def test_4_backtick_fence_not_closed_by_3(self):
        """A 4-backtick opening fence must NOT be closed by 3 backticks."""
        text = "Before\n````python\ncode inside\n```\nstill inside\n````\nAfter"
        masked = self._mask(text)
        lines = masked.split("\n")
        # "still inside" (line index 4) must be masked (empty)
        assert lines[4] == "", (
            f"Line 'still inside' should be masked but got: {lines[4]!r}"
        )
        # "After" (line index 6) must NOT be masked
        assert lines[6] == "After", (
            f"Line 'After' should not be masked but got: {lines[6]!r}"
        )

    def test_longer_closer_valid(self):
        """A 5-backtick line CAN close a 3-backtick fence (CommonMark)."""
        text = "Before\n```\ncode\n`````\nAfter"
        masked = self._mask(text)
        lines = masked.split("\n")
        # "code" (line index 2) should be masked
        assert lines[2] == "", f"'code' should be masked but got: {lines[2]!r}"
        # "After" (line index 4) should NOT be masked
        assert lines[4] == "After", f"'After' should not be masked but got: {lines[4]!r}"

    def test_tilde_fence_not_closed_by_backtick(self):
        """A tilde fence cannot be closed by backticks."""
        text = "Before\n~~~\ncode\n```\nstill fenced\n~~~\nAfter"
        masked = self._mask(text)
        lines = masked.split("\n")
        assert lines[4] == "", (
            f"'still fenced' should be masked but got: {lines[4]!r}"
        )
        assert lines[6] == "After"


# --- _common.py read_event ---


class TestReadEvent:
    """Tests for _common.read_event via hooks that use it."""

    def test_empty_stdin_does_not_crash(self):
        """Hooks should handle empty stdin gracefully."""
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "subagent_findings_check.py")],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_malformed_json_does_not_crash(self):
        """Hooks should handle malformed JSON gracefully."""
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "subagent_findings_check.py")],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


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

    def test_warns_missing_json_artifacts(self, tmp_path):
        """BH-007: .json artifacts under docs/holtz/ should be checked, not just .md."""
        event = {
            "last_assistant_message": "Updated docs/holtz/impact-graph.json",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_warned(code, output, "WARNING")
        assert "impact-graph.json" in output.get("additionalContext", "")

    def test_allows_existing_json_artifact(self, tmp_path):
        """BH-007: existing .json artifact should be allowed."""
        holtz_dir = tmp_path / "docs" / "holtz"
        holtz_dir.mkdir(parents=True)
        (holtz_dir / "impact-graph.json").write_text("{}")
        event = {
            "last_assistant_message": "Updated docs/holtz/impact-graph.json",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert_allowed(code, output)

    def test_subagentstop_does_not_include_hook_specific_output(self):
        """SubagentStop hooks should not include hookSpecificOutput."""
        event = {"last_assistant_message": ""}
        code, output, _ = run_hook("subagent_findings_check.py", event)
        assert code == 0
        assert "hookSpecificOutput" not in output


class TestSubagentFindingsCheckInProcess:
    """BH-010: In-process tests for subagent_findings_check.py coverage."""

    @staticmethod
    def _run_main(event, capsys):
        """Import and run main() in-process, returning parsed JSON output."""
        import contextlib
        import importlib
        import io
        from unittest.mock import patch

        sys.path.insert(0, HOOKS_DIR)
        import subagent_findings_check
        importlib.reload(subagent_findings_check)
        stdin_data = io.StringIO(json.dumps(event))
        with patch("sys.stdin", stdin_data), contextlib.suppress(SystemExit):
            subagent_findings_check.main()
        captured = capsys.readouterr()
        try:
            return json.loads(captured.out)
        except json.JSONDecodeError:
            return {}

    def test_empty_message_ok(self, capsys):
        output = self._run_main({"last_assistant_message": ""}, capsys)
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True

    def test_no_holtz_paths_ok(self, capsys):
        output = self._run_main({"last_assistant_message": "Fixed src/foo.py"}, capsys)
        assert output.get("continue") is True

    def test_missing_md_warns(self, tmp_path, capsys):
        event = {
            "last_assistant_message": "Wrote docs/holtz/NONEXISTENT.md",
            "cwd": str(tmp_path),
        }
        output = self._run_main(event, capsys)
        assert output.get("suppressOutput") is False
        assert "NONEXISTENT.md" in output.get("additionalContext", "")

    def test_existing_file_ok(self, tmp_path, capsys):
        holtz_dir = tmp_path / "docs" / "holtz"
        holtz_dir.mkdir(parents=True)
        (holtz_dir / "PUNCHLIST.md").write_text("# Punchlist")
        event = {
            "last_assistant_message": "Updated docs/holtz/PUNCHLIST.md",
            "cwd": str(tmp_path),
        }
        output = self._run_main(event, capsys)
        assert output.get("continue") is True
        assert output.get("suppressOutput") is True

    def test_json_artifact_warns(self, tmp_path, capsys):
        event = {
            "last_assistant_message": "Updated docs/holtz/impact-graph.json",
            "cwd": str(tmp_path),
        }
        output = self._run_main(event, capsys)
        assert "impact-graph.json" in output.get("additionalContext", "")


# --- _common.py in-process coverage for exit_stop_warn, exit_stop_block, read_event ---


class TestCommonInProcess:
    """In-process tests for _common.py functions that subprocess tests can't cover."""

    @staticmethod
    def _import_common():
        sys.path.insert(0, HOOKS_DIR)
        import importlib
        import _common
        importlib.reload(_common)
        return _common

    def test_read_event_empty_stdin(self, monkeypatch):
        """read_event returns {} when stdin is empty (line 35)."""
        import io
        common = self._import_common()
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        result = common.read_event()
        assert result == {}

    def test_read_event_whitespace_only_stdin(self, monkeypatch):
        """read_event returns {} when stdin is only whitespace."""
        import io
        common = self._import_common()
        monkeypatch.setattr("sys.stdin", io.StringIO("   \n  \n"))
        result = common.read_event()
        assert result == {}

    def test_read_event_malformed_json(self, monkeypatch):
        """read_event returns {} on malformed JSON (lines 37-38)."""
        import io
        common = self._import_common()
        monkeypatch.setattr("sys.stdin", io.StringIO("not valid json {{{"))
        result = common.read_event()
        assert result == {}

    def test_read_event_valid_json(self, monkeypatch):
        """read_event returns parsed dict for valid JSON."""
        import io
        common = self._import_common()
        monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_name": "Bash", "args": {}}'))
        result = common.read_event()
        assert result == {"tool_name": "Bash", "args": {}}

    def test_exit_stop_warn_outputs_approve_decision(self, capsys):
        """exit_stop_warn outputs decision=approve with reason (lines 163-167)."""
        import contextlib
        common = self._import_common()
        with contextlib.suppress(SystemExit):
            common.exit_stop_warn("config not found")
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["decision"] == "approve"
        assert output["reason"] == "config not found"

    def test_exit_stop_block_outputs_block_decision(self, capsys):
        """exit_stop_block outputs decision=block with reason (lines 177-181)."""
        import contextlib
        common = self._import_common()
        with contextlib.suppress(SystemExit):
            common.exit_stop_block("punchlist not written")
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["decision"] == "block"
        assert output["reason"] == "punchlist not written"


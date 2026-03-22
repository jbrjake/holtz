"""Tests for hooks/ modules.

Each hook reads JSON from stdin, writes reason to stderr, and exits 0/1/2.
Exit 0 = allow, exit 1 = warn (non-blocking), exit 2 = block.
"""

import json
import os
import subprocess
import sys

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")


def run_hook(hook_name, event, cwd=None):
    """Run a hook script with the given event JSON on stdin.

    Returns (exit_code, stdout, stderr).
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
    return result.returncode, result.stdout, result.stderr


# --- _common.py ---


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
        # Empty event → no file_path → exit_ok
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


# --- impact_graph_gate.py ---


class TestImpactGraphGate:
    """Tests for the impact graph gate hook."""

    def test_allows_non_audit_writes(self):
        """Writes outside docs/holtz/audit/ should be allowed."""
        event = {"tool_input": {"file_path": "docs/holtz/recon/0a.md"}}
        code, _, _ = run_hook("impact_graph_gate.py", event)
        assert code == 0

    def test_allows_audit_write_when_graph_exists(self, tmp_path):
        """Writes to audit/ should be allowed when impact-graph.json exists."""
        docs = tmp_path / "docs" / "holtz"
        docs.mkdir(parents=True)
        (docs / "impact-graph.json").write_text("{}")
        event = {
            "tool_input": {"file_path": str(docs / "audit" / "1-doc-claims.md")},
            "cwd": str(tmp_path),
        }
        code, _, _ = run_hook("impact_graph_gate.py", event)
        assert code == 0

    def test_blocks_audit_write_when_graph_missing(self, tmp_path):
        """Writes to audit/ should be blocked when impact-graph.json is missing."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "audit" / "1.md")},
            "cwd": str(tmp_path),
        }
        code, _, stderr = run_hook("impact_graph_gate.py", event)
        assert code == 2
        assert "BLOCKED" in stderr

    def test_allows_empty_file_path(self):
        """Empty file_path should be allowed."""
        event = {"tool_input": {"file_path": ""}}
        code, _, _ = run_hook("impact_graph_gate.py", event)
        assert code == 0

    def test_justine_audit_checks_justine_graph(self, tmp_path):
        """Justine audit writes should check Justine's graph, not Holtz's."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "justine" / "audit" / "1.md")},
            "cwd": str(tmp_path),
        }
        code, _, stderr = run_hook("impact_graph_gate.py", event)
        assert code == 2
        assert "justine" in stderr


# --- status_staleness_gate.py ---


class TestStatusStalenessGate:
    """Tests for the status staleness gate hook."""

    def test_allows_non_holtz_writes(self):
        """Writes outside docs/holtz/ should be allowed."""
        event = {"tool_input": {"file_path": "src/foo.py"}}
        code, _, _ = run_hook("status_staleness_gate.py", event)
        assert code == 0

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
        code, _, _ = run_hook("status_staleness_gate.py", event)
        assert code == 0

    def test_allows_fresh_status(self, tmp_path):
        """Writes should be allowed when STATUS.md is fresh."""
        status = tmp_path / "docs" / "holtz" / "STATUS.md"
        status.parent.mkdir(parents=True)
        status.write_text("current")
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "PUNCHLIST.md")},
            "cwd": str(tmp_path),
        }
        code, _, _ = run_hook("status_staleness_gate.py", event)
        assert code == 0

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
        code, _, stderr = run_hook("status_staleness_gate.py", event)
        assert code == 2
        assert "BLOCKED" in stderr

    def test_allows_when_no_status_exists(self, tmp_path):
        """First write of a run (no STATUS.md yet) should be allowed."""
        event = {
            "tool_input": {"file_path": str(tmp_path / "docs" / "holtz" / "recon" / "0a.md")},
            "cwd": str(tmp_path),
        }
        code, _, _ = run_hook("status_staleness_gate.py", event)
        assert code == 0

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
        code, _, stderr = run_hook("status_staleness_gate.py", event)
        # The file is in docs/holtz/ and doesn't match the protocol STATUS.md paths,
        # so it should be gated. Since STATUS.md is stale, it should be blocked.
        assert code == 2


# --- artifact_verification.py ---


class TestArtifactVerification:
    """Tests for the artifact verification hook."""

    def test_ignores_non_impact_graph_commands(self):
        """Commands that don't run impact_graph.py should be allowed."""
        event = {"tool_input": {"command": "python -m pytest test_foo.py"}}
        code, _, _ = run_hook("artifact_verification.py", event)
        assert code == 0

    def test_ignores_test_impact_graph_filename(self):
        """Commands referencing test_impact_graph.py should not trigger the check."""
        event = {"tool_input": {"command": "python -m pytest test_impact_graph.py"}}
        code, _, _ = run_hook("artifact_verification.py", event)
        assert code == 0

    def test_allows_when_graph_exists(self, tmp_path):
        """Running impact_graph.py should be allowed when graph file exists."""
        graph = tmp_path / "docs" / "holtz" / "impact-graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text("{}")
        event = {
            "tool_input": {"command": f"python impact_graph.py --graph {graph} add_node x y z"},
            "cwd": str(tmp_path),
        }
        code, _, _ = run_hook("artifact_verification.py", event)
        assert code == 0

    def test_blocks_when_graph_missing(self, tmp_path):
        """Running impact_graph.py should be blocked when graph file doesn't exist."""
        event = {
            "tool_input": {"command": "python impact_graph.py --graph docs/holtz/impact-graph.json add_node x y z"},
            "cwd": str(tmp_path),
        }
        code, _, stderr = run_hook("artifact_verification.py", event)
        assert code == 2
        assert "BLOCKED" in stderr

    def test_skips_shell_variable_paths(self):
        """Commands with shell variable in --graph path should be skipped."""
        event = {"tool_input": {"command": 'python impact_graph.py --graph "$GRAPH" add_node x y z'}}
        code, _, _ = run_hook("artifact_verification.py", event)
        assert code == 0

    def test_default_graph_path_when_no_graph_flag(self, tmp_path):
        """When --graph is not specified, default path should be used."""
        event = {
            "tool_input": {"command": "python impact_graph.py add_node x y z"},
            "cwd": str(tmp_path),
        }
        code, _, stderr = run_hook("artifact_verification.py", event)
        # Default path won't exist in tmp_path
        assert code == 2
        assert "impact-graph.json" in stderr


# --- subagent_findings_check.py ---


class TestSubagentFindingsCheck:
    """Tests for the subagent findings check hook."""

    def test_allows_empty_message(self):
        """Empty last_assistant_message should be allowed."""
        event = {"last_assistant_message": ""}
        code, _, _ = run_hook("subagent_findings_check.py", event)
        assert code == 0

    def test_allows_no_holtz_paths(self):
        """Messages without docs/holtz/ paths should be allowed."""
        event = {"last_assistant_message": "I fixed the bug in src/foo.py"}
        code, _, _ = run_hook("subagent_findings_check.py", event)
        assert code == 0

    def test_allows_existing_files(self, tmp_path):
        """Referenced files that exist should not trigger a warning."""
        holtz = tmp_path / "docs" / "holtz"
        holtz.mkdir(parents=True)
        (holtz / "PUNCHLIST.md").write_text("items")
        event = {
            "last_assistant_message": "I wrote findings to docs/holtz/PUNCHLIST.md",
            "cwd": str(tmp_path),
        }
        code, _, _ = run_hook("subagent_findings_check.py", event)
        assert code == 0

    def test_warns_missing_files(self, tmp_path):
        """Referenced files that don't exist should trigger a warning."""
        event = {
            "last_assistant_message": "I wrote findings to docs/holtz/PUNCHLIST.md",
            "cwd": str(tmp_path),
        }
        code, _, stderr = run_hook("subagent_findings_check.py", event)
        assert code == 1
        assert "WARNING" in stderr
        assert "PUNCHLIST.md" in stderr

    def test_deduplicates_paths(self, tmp_path):
        """Multiple references to the same path should be deduplicated."""
        event = {
            "last_assistant_message": "Wrote docs/holtz/FOO.md and referenced docs/holtz/FOO.md again",
            "cwd": str(tmp_path),
        }
        code, _, stderr = run_hook("subagent_findings_check.py", event)
        assert code == 1
        # Should only mention FOO.md once
        assert stderr.count("FOO.md") == 1

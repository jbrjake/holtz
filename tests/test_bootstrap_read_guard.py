"""Tests for _sahjhan_bootstrap.py daemon command guards and write protection.

With sahjhan 0.9.0, read guards are removed (secrets live in daemon memory).
These tests verify the new daemon command blocking and retained write guards.
"""
from __future__ import annotations

import json
import subprocess
import sys

HOOK = "enforcement/hooks/_sahjhan_bootstrap.py"


def _run_hook(event: dict) -> dict:
    """Run the bootstrap hook with a given event dict, return parsed output."""
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


class TestSahjhanAllowlist:
    """Sahjhan subcommand allowlist: only permitted subcmds pass, all else blocked."""

    def test_sahjhan_reset_blocked(self):
        """sahjhan reset is not on the allowlist and must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "not permitted" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_sahjhan_reset_with_proof_blocked(self):
        """sahjhan reset with extra flags is still blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm --proof abc123"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sahjhan_unknown_subcommand_blocked(self):
        """Unknown subcommands are blocked by the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan frobnicate --all"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bare_sahjhan_blocked(self):
        """Bare 'sahjhan' with no subcommand is blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sahjhan_with_config_dir_flag_allowed(self):
        """Flags before the subcommand should be skipped; status is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan --config-dir /some/path status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_stop_blocked(self):
        """daemon is allowed but daemon stop is blocked via sub-subcommand check."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sahjhan_daemon_start_allowed(self):
        """daemon start is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_gate_check_allowed(self):
        """gate subcommand is on the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan gate check converge"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_defer_allowed(self):
        """defer subcommand is on the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan defer low PL-005"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_init_allowed(self):
        """init subcommand is on the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan init"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_nohup_sahjhan_daemon_start_allowed(self):
        """nohup wrapper before sahjhan should be handled; daemon start is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "nohup sahjhan daemon start > /dev/null 2>&1 &"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_chained_sahjhan_reset_blocked(self):
        """sahjhan reset in a chained command is blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo foo && sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_case_insensitive_reset_blocked(self):
        """Case-insensitive matching must catch mixed-case sahjhan commands."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "Sahjhan Reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_non_sahjhan_command_allowed(self):
        """Normal bash commands should be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestReadNoLongerGuarded:
    """With daemon vault, file reads are no longer blocked."""

    def test_read_quiz_bank_allowed(self):
        """quiz-bank.json is no longer read-guarded (data lives in vault)."""
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_read_normal_file_allowed(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_cat_quiz_bank_allowed(self):
        """Bash cat of quiz-bank.json is no longer blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestWriteGuardsRetained:
    """Write protection must still work after read guard removal."""

    def test_write_to_protected_still_blocked(self):
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "enforcement/hooks/lens_quiz.py"},
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sed_inplace_to_protected_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sed -i 's/old/new/g' enforcement/events.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_redirect_to_managed_status_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo "hacked" > docs/holtz/STATUS.md'},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"


class TestManagedDataWriteProtection:
    """Issue #39 P2: Write/Edit to .sahjhan/ data dir must be blocked."""

    def test_write_to_enforcement_cache_blocked(self):
        """Write tool targeting enforcement-cache.json must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/enforcement-cache.json"},
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "cannot be modified" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_edit_to_active_ledger_marker_blocked(self):
        """Edit tool targeting active-ledger marker must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "docs/holtz/.sahjhan/active-ledger",
                "old_string": "run-1",
                "new_string": "run-999",
            },
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_write_to_daemon_pid_blocked(self):
        """Write tool targeting daemon.pid must be blocked."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/daemon.pid"},
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_write_outside_sahjhan_dir_allowed(self):
        """Write tool targeting a non-protected path is allowed."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/some-notes.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

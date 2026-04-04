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


class TestDaemonCommandGuards:
    """Bash commands invoking privileged sahjhan daemon commands must be blocked."""

    def test_bash_sahjhan_sign_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "sahjhan sign --event-type quiz_answered --field perspective=security"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "sahjhan sign" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_sahjhan_verify_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "sahjhan verify --event-type quiz_answered --proof abc123"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_sahjhan_vault_store_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "sahjhan vault store --name quiz-bank --file data.json"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "sahjhan vault" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_sahjhan_vault_read_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan vault read --name quiz-bank"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_sahjhan_vault_list_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan vault list"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_sahjhan_daemon_stop_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "sahjhan daemon stop" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_sahjhan_status_allowed(self):
        """Non-privileged sahjhan commands should be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_sahjhan_event_allowed(self):
        """Non-privileged sahjhan commands should be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan event finding --field msg=test"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_sahjhan_daemon_start_allowed(self):
        """daemon start is allowed (only stop is blocked)."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_sahjhan_daemon_status_allowed(self):
        """daemon status is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_git_status_allowed(self):
        """Normal bash commands should be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_case_insensitive_sign_blocked(self):
        """Case variations of privileged commands must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "Sahjhan Sign --event-type test"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"


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

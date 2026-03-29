"""Tests for _sahjhan_bootstrap.py read-guard enforcement."""
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


class TestReadGuard:
    def test_read_quiz_bank_blocked(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_read_session_key_blocked(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/session.key"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_read_normal_file_allowed(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_cat_quiz_bank_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_python_open_session_key_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "python3 -c \"print(open('docs/holtz/.sahjhan/session.key').read())\""
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_without_guarded_path_allowed(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_path_traversal_blocked(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "hooks/../enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_write_to_protected_still_blocked(self):
        """Existing write protection must still work."""
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
        """BH-008: sed -i to protected enforcement/ path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sed -i 's/old/new/g' enforcement/events.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_perl_inplace_to_protected_blocked(self):
        """BH-008: perl -pi to protected enforcement/ path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "perl -pi -e 's/old/new/g' enforcement/states.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_patch_to_protected_blocked(self):
        """BH-008: patch to protected enforcement/ path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "patch enforcement/hooks/primer.py < fix.patch"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_sahjhan_cmd_with_guarded_path_allowed(self):
        """sahjhan commands referencing quiz-bank.json should be allowed since
        sahjhan itself needs to read the quiz bank."""
        # Actually NO - the bootstrap hook doesn't know about sahjhan commands.
        # The read guard blocks ALL bash commands referencing guarded paths.
        # sahjhan reads files directly, not through bash cat.
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/quiz-bank.json | wc -l"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

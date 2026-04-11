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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "not permitted" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_sahjhan_reset_with_proof_blocked(self):
        """sahjhan reset with extra flags is still blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm --proof abc123"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sahjhan_unknown_subcommand_blocked(self):
        """Unknown subcommands are blocked by the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan frobnicate --all"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bare_sahjhan_blocked(self):
        """Bare 'sahjhan' with no subcommand is blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_case_insensitive_reset_blocked(self):
        """Case-insensitive matching must catch mixed-case sahjhan commands."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "Sahjhan Reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sed_inplace_to_protected_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sed -i 's/old/new/g' enforcement/events.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_redirect_to_managed_status_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo "hacked" > docs/holtz/STATUS.md'},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestExtractSahjhanSubcmd:
    """Direct unit tests for _extract_sahjhan_subcmd parsing logic."""

    @staticmethod
    def _get_extract():
        import os as _os
        import sys as _sys
        hook_dir = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "enforcement", "hooks",
        )
        if hook_dir not in _sys.path:
            _sys.path.insert(0, hook_dir)
        from _sahjhan_bootstrap import _extract_sahjhan_subcmd
        return _extract_sahjhan_subcmd

    def test_simple_subcommand(self):
        extract = self._get_extract()
        assert extract("sahjhan status") == ("status", "")

    def test_boolean_flag_before_subcommand(self):
        extract = self._get_extract()
        assert extract("sahjhan --verbose status") == ("status", "")

    def test_value_flag_before_subcommand(self):
        extract = self._get_extract()
        assert extract("sahjhan --config-dir /path status") == ("status", "")

    def test_subcommand_with_sub_subcommand(self):
        extract = self._get_extract()
        assert extract("sahjhan daemon stop") == ("daemon", "stop")

    def test_boolean_flag_between_subcmd_and_sub_subcmd(self):
        extract = self._get_extract()
        assert extract("sahjhan daemon --verbose start") == ("daemon", "start")

    def test_bare_sahjhan(self):
        extract = self._get_extract()
        assert extract("sahjhan") == ("", "")

    def test_nohup_wrapper(self):
        extract = self._get_extract()
        assert extract("nohup sahjhan daemon start") == ("daemon", "start")

    def test_non_sahjhan_command(self):
        extract = self._get_extract()
        assert extract("git status") is None

    def test_env_var_prefix_single(self):
        """Env var prefix before sahjhan must be skipped — FOO=bar sahjhan reset
        must be recognized as ('reset', '') so the allowlist can block it."""
        extract = self._get_extract()
        assert extract("FOO=bar sahjhan reset") == ("reset", "")

    def test_env_var_prefix_multiple(self):
        """Multiple env var prefixes must all be skipped."""
        extract = self._get_extract()
        # --confirm is a flag, not a sub-subcommand — parser correctly skips it
        assert extract("A=1 B=2 sahjhan reset --confirm") == ("reset", "")

    def test_env_var_prefix_with_path(self):
        """Env var with path value must be handled (= inside value)."""
        extract = self._get_extract()
        assert extract("PATH=/usr/bin sahjhan status") == ("status", "")


class TestEnvVarPrefixBypassesAllowlist:
    """Env var prefix before blocked sahjhan subcommand must still be blocked.

    Root cause: _extract_sahjhan_subcmd only skips 'nohup' and 'env' wrappers.
    Shell env var assignments (FOO=bar) before the command are valid syntax
    but aren't recognized, causing the entire subcommand allowlist to be bypassed.
    """

    def test_env_prefix_sahjhan_reset_blocked(self):
        """FOO=bar sahjhan reset must be blocked — not allowed to bypass allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "FOO=bar sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Env var prefix bypassed sahjhan subcommand allowlist — "
            "'FOO=bar sahjhan reset' was allowed through"
        )

    def test_multi_env_prefix_sahjhan_reset_blocked(self):
        """A=1 B=2 sahjhan reset must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "A=1 B=2 sahjhan reset --confirm"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Multiple env var prefixes bypassed sahjhan allowlist"
        )


class TestEnvVarPrefixBypassesWriteProtection:
    """Env var prefix before destructive commands bypasses write protection.

    Root cause: _check_bash_write checks seg_stripped.startswith("rm ") etc.,
    but doesn't strip env var assignments first. FOO=bar rm ... starts with
    "FOO=bar", not "rm", so the check is skipped entirely.
    """

    def test_env_prefix_rm_sahjhan_dir_blocked(self):
        """X=1 rm -rf docs/holtz/.sahjhan/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "X=1 rm -rf docs/holtz/.sahjhan/"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Env var prefix bypassed rm write protection on .sahjhan dir"
        )

    def test_env_prefix_cp_to_enforcement_blocked(self):
        """X=1 cp /tmp/evil enforcement/hooks/foo.py must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "X=1 cp /tmp/evil enforcement/hooks/foo.py"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Env var prefix bypassed cp write protection on enforcement/"
        )

    def test_env_prefix_sed_inplace_blocked(self):
        """X=1 sed -i 's/old/new/' enforcement/events.toml must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "X=1 sed -i 's/old/new/' enforcement/events.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Env var prefix bypassed sed write protection on enforcement/"
        )

    def test_env_prefix_redirect_to_managed_blocked(self):
        """X=1 echo hacked > docs/holtz/STATUS.md must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'X=1 echo "hacked" > docs/holtz/STATUS.md'},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Env var prefix bypassed redirect write protection on managed doc"
        )


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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

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
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_write_outside_sahjhan_dir_allowed(self):
        """Write tool targeting a non-protected path is allowed."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/some-notes.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

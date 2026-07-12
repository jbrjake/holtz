"""Tests for _sahjhan_bootstrap.py daemon command guards and write protection.

With sahjhan 0.9.0, read guards are removed (secrets live in daemon memory).
These tests verify the new daemon command blocking and retained write guards.
"""
from __future__ import annotations

import os

import pytest

from hook_runner import run_hook

HOOK = "enforcement/hooks/_sahjhan_bootstrap.py"

# Use the plugin root as the default test cwd so bootstrap's PROTECTED-path
# checks (enforcement/, hooks/hooks.json, bin/sahjhan…) stay active during
# these bypass-detection tests. PROTECTED is plugin-relative, so the guard
# only engages when cwd is inside the plugin — the realistic "agent working
# on the plugin itself" scenario the tests are written to exercise.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_hook(event: dict) -> dict:
    """Run the bootstrap hook with a given event dict, return parsed output."""
    return run_hook(HOOK, event)


@pytest.mark.hook_e2e
class TestSahjhanAllowlist:
    """Sahjhan subcommand allowlist: only permitted subcmds pass, all else blocked."""

    def test_sahjhan_reset_blocked(self):
        """sahjhan reset is not on the allowlist and must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "not permitted" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_sahjhan_reset_with_proof_blocked(self):
        """sahjhan reset with extra flags is still blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm --proof abc123"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sahjhan_unknown_subcommand_blocked(self):
        """Unknown subcommands are blocked by the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan frobnicate --all"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bare_sahjhan_blocked(self):
        """Bare 'sahjhan' with no subcommand is blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sahjhan_with_config_dir_flag_allowed(self):
        """Flags before the subcommand should be skipped; status is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan --config-dir /some/path status"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_stop_blocked_mid_audit(self, tmp_path, mock_daemon):
        """daemon stop is blocked while a live daemon reports an active audit (#57)."""
        mock_daemon.state = {"active": True, "state": "fix_loop"}
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "session key" in reason, (
            "block message should explain WHY daemon stop is dangerous mid-audit"
        )

    def test_sahjhan_daemon_stop_blocked_when_state_unknown(self, tmp_path, mock_daemon):
        """Live daemon but unreadable state — fail closed."""
        mock_daemon.state = None
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sahjhan_daemon_stop_allowed_when_daemon_dead(self, tmp_path):
        """Dead daemon: stop only cleans stale pid/socket files — allowed (#57).

        This is the recovery path the stop hook's escape hatch needs.
        """
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_stop_allowed_after_termination(self, tmp_path, mock_daemon):
        """Terminated audits permit daemon stop even with a live daemon (#57)."""
        mock_daemon.state = {"active": True, "state": "fix_loop"}
        marker = tmp_path / "docs" / "holtz" / ".sahjhan" / "terminated"
        marker.write_text("reason: daemon_pid_dead\n")
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_stop_allowed_in_cleanup_state(self, tmp_path, mock_daemon):
        """finalized/idle audits have no session key worth protecting (#57)."""
        mock_daemon.state = {"active": False, "state": "finalized"}
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_stop_blocked_in_awaiting_clear(self, tmp_path, mock_daemon):
        """awaiting_clear allows the TURN to stop, but the daemon must survive
        (it holds the HMAC session key for the resuming session)."""
        mock_daemon.state = {"active": True, "state": "awaiting_clear"}
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sahjhan_daemon_stop_allowed_without_audit_dir(self, tmp_path):
        """No docs/holtz/.sahjhan — nothing to protect."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_daemon_start_allowed(self):
        """daemon start is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan daemon start"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_gate_check_allowed(self):
        """gate subcommand is on the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan gate check converge"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_defer_allowed(self):
        """defer subcommand is on the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan defer low PL-005"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_init_allowed(self):
        """init subcommand is on the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan init"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_nohup_sahjhan_daemon_start_allowed(self):
        """nohup wrapper before sahjhan should be handled; daemon start is allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "nohup sahjhan daemon start > /dev/null 2>&1 &"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_chained_sahjhan_reset_blocked(self):
        """sahjhan reset in a chained command is blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo foo && sahjhan reset --confirm"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_case_insensitive_reset_blocked(self):
        """Case-insensitive matching must catch mixed-case sahjhan commands."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "Sahjhan Reset --confirm"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_non_sahjhan_command_allowed(self):
        """Normal bash commands should be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.hook_e2e
class TestReadNoLongerGuarded:
    """With daemon vault, file reads are no longer blocked.

    These cases use /tmp/fake-cwd so the cwd-relative path resolves outside
    the plugin root. PROTECTED enforcement is plugin-scoped; a Read from an
    unrelated cwd naming ``enforcement/…`` refers to the target project's
    own enforcement directory, not the plugin's.
    """

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


@pytest.mark.hook_e2e
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
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_redirect_to_managed_status_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo "hacked" > docs/holtz/STATUS.md'},
            "cwd": REPO_ROOT,
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

    # --- Issue #53: --help flag must not be treated as a subcommand ---

    def test_help_flag_returns_none(self):
        """sahjhan --help must return None (bypass enforcement)."""
        extract = self._get_extract()
        assert extract("sahjhan --help") is None

    def test_short_help_flag_returns_none(self):
        """sahjhan -h must return None (bypass enforcement)."""
        extract = self._get_extract()
        assert extract("sahjhan -h") is None

    def test_version_flag_returns_none(self):
        """sahjhan --version must return None (bypass enforcement)."""
        extract = self._get_extract()
        assert extract("sahjhan --version") is None

    def test_help_after_subcommand_still_parses(self):
        """sahjhan init --help — subcmd is init, --help is just a trailing flag."""
        extract = self._get_extract()
        result = extract("sahjhan init --help")
        assert result == ("init", "")

    def test_help_after_config_dir_flag(self):
        """sahjhan --config-dir /path --help must return None."""
        extract = self._get_extract()
        assert extract("sahjhan --config-dir /path --help") is None

    # --- Issue #53: redirect fragments must not become subcommand tokens ---

    def test_status_with_stderr_redirect(self):
        """sahjhan status 2>&1 — '2' must not become sub-subcommand."""
        extract = self._get_extract()
        assert extract("sahjhan status 2>&1") == ("status", "")

    def test_status_with_fd_redirect_to_devnull(self):
        """sahjhan status 2>/dev/null — '2' must not leak."""
        extract = self._get_extract()
        assert extract("sahjhan status 2>/dev/null") == ("status", "")

    def test_init_with_stderr_redirect(self):
        """sahjhan init 2>&1 — redirect must be fully stripped."""
        extract = self._get_extract()
        assert extract("sahjhan init 2>&1") == ("init", "")

    def test_bare_sahjhan_with_redirect(self):
        """sahjhan 2>&1 — after stripping redirect, bare sahjhan remains."""
        extract = self._get_extract()
        assert extract("sahjhan 2>&1") == ("", "")

    def test_nohup_daemon_start_full_redirect(self):
        """Full nohup pattern: > /dev/null 2>&1 & — must parse to daemon start."""
        extract = self._get_extract()
        assert extract("nohup sahjhan daemon start > /dev/null 2>&1 &") == ("daemon", "start")

    def test_combined_redirect(self):
        """sahjhan status &>/dev/null — combined redirect must be stripped."""
        extract = self._get_extract()
        assert extract("sahjhan status &>/dev/null") == ("status", "")

    def test_stdout_redirect_to_file(self):
        """sahjhan status > /tmp/out.log — stdout redirect stripped."""
        extract = self._get_extract()
        assert extract("sahjhan status > /tmp/out.log") == ("status", "")

    def test_stderr_redirect_to_file(self):
        """sahjhan init 2>/tmp/err.log — fd redirect stripped."""
        extract = self._get_extract()
        assert extract("sahjhan init 2>/tmp/err.log") == ("init", "")

    def test_reverse_fd_dup(self):
        """sahjhan status 1>&2 — reverse fd duplication stripped."""
        extract = self._get_extract()
        assert extract("sahjhan status 1>&2") == ("status", "")


@pytest.mark.hook_e2e
class TestHelpFlagAllowed:
    """Issue #53: sahjhan --help and -h must be allowed through the hook."""

    def test_sahjhan_help_allowed(self):
        """sahjhan --help must not be blocked by the allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan --help"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "sahjhan --help was blocked — help requests must bypass enforcement"
        )

    def test_sahjhan_short_help_allowed(self):
        """sahjhan -h must not be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan -h"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_init_help_allowed(self):
        """sahjhan init --help must be allowed (init is on allowlist, --help is a flag)."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan init --help"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_help_with_config_dir_allowed(self):
        """sahjhan --config-dir /path --help must be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan --config-dir /some/path --help"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.hook_e2e
class TestRedirectFragmentHandling:
    """Issue #53: shell redirect fragments must not become subcommand tokens."""

    def test_sahjhan_status_stderr_redirect_allowed(self):
        """sahjhan status 2>&1 — '2' from redirect must not be parsed as subcommand."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status 2>&1"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "sahjhan status 2>&1 was blocked — redirect fragment '2' was "
            "parsed as a subcommand"
        )

    def test_sahjhan_init_stderr_redirect_allowed(self):
        """sahjhan init 2>&1 must be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan init 2>&1"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_status_fd_redirect_devnull_allowed(self):
        """sahjhan status 2>/dev/null must be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status 2>/dev/null"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_sahjhan_transition_with_redirect_allowed(self):
        """sahjhan transition run_start 2>&1 must be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan transition run_start 2>&1"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_blocked_subcmd_with_redirect_still_blocked(self):
        """sahjhan reset 2>&1 — redirect doesn't bypass the allowlist block."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm 2>&1"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "sahjhan reset with redirect was allowed — redirect stripping must "
            "not bypass the allowlist"
        )


@pytest.mark.hook_e2e
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
            "cwd": REPO_ROOT,
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
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Multiple env var prefixes bypassed sahjhan allowlist"
        )


@pytest.mark.hook_e2e
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
            "cwd": REPO_ROOT,
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
            "cwd": REPO_ROOT,
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
            "cwd": REPO_ROOT,
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
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Env var prefix bypassed redirect write protection on managed doc"
        )


@pytest.mark.hook_e2e
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
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.hook_e2e
class TestCopyMoveTargetDirectoryBypass:
    """cp/mv -t and --target-directory bypass: target is NOT the last arg."""

    def test_cp_t_flag_to_enforcement_blocked(self):
        """cp -t enforcement/hooks/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cp -t enforcement/hooks/ /tmp/evil.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_mv_t_flag_to_enforcement_blocked(self):
        """mv -t enforcement/hooks/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "mv -t enforcement/hooks/ /tmp/evil.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_cp_target_directory_long_flag_blocked(self):
        """cp --target-directory=enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cp --target-directory=enforcement/ /tmp/evil.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_mv_target_directory_space_flag_blocked(self):
        """mv --target-directory enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "mv --target-directory enforcement/ /tmp/evil.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.hook_e2e
class TestFullPathCommandBypass:
    """Full-path commands (/bin/cp, /usr/bin/rm) must be caught."""

    def test_bin_cp_to_enforcement_blocked(self):
        """/bin/cp to enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "/bin/cp /tmp/evil.py enforcement/hooks/foo.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_usr_bin_mv_to_enforcement_blocked(self):
        """/usr/bin/mv to enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "/usr/bin/mv /tmp/evil.py enforcement/hooks/foo.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bin_rm_sahjhan_dir_blocked(self):
        """/bin/rm -rf docs/holtz/.sahjhan/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "/bin/rm -rf docs/holtz/.sahjhan/"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_usr_bin_rmdir_sahjhan_blocked(self):
        """/usr/bin/rmdir docs/holtz/.sahjhan/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "/usr/bin/rmdir docs/holtz/.sahjhan/"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_full_path_cp_safe_target_allowed(self):
        """/bin/cp to a non-protected path must be allowed."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "/bin/cp file.txt /tmp/safe.txt"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.hook_e2e
class TestQuotedPathBypass:
    """Shell-quoted paths must not bypass write protection.

    Prior bug: cp /tmp/evil "enforcement/hooks/foo.py" was allowed because
    the target after split() was '"enforcement/hooks/foo.py"' with leading
    quote, so startswith("enforcement/") failed. Fixed by _unquote().
    """

    def test_cp_double_quoted_target_blocked(self):
        """cp to double-quoted enforcement path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'cp /tmp/evil "enforcement/hooks/foo.py"'},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_cp_single_quoted_target_blocked(self):
        """cp to single-quoted enforcement path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cp /tmp/evil 'enforcement/hooks/foo.py'"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_redirect_to_quoted_managed_path_blocked(self):
        """Redirect to quoted managed path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo pwned > "docs/holtz/STATUS.md"'},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_rm_quoted_sahjhan_dir_blocked(self):
        """rm of quoted .sahjhan path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'rm -rf "docs/holtz/.sahjhan/"'},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_tee_quoted_managed_path_blocked(self):
        """tee to quoted managed path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo pwned | tee "docs/holtz/STATUS.md"'},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_env_var_quoted_value_interpreter_blocked(self):
        """FOO="bar baz" python3 -c "..." with protected path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": 'FOO="bar baz" python3 -c "open(\'enforcement/hooks/x\',\'w\')"',
            },
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.hook_e2e
class TestBackslashEscapedCommandBypass:
    """Backslash-escaped or quoted command names (\\cp, "cp", 'rm') must not bypass guards.

    Shell interprets ``\\cp`` and ``"cp"`` as the literal command ``cp`` (escaping
    skips alias/function lookup). The bash_guard detected the destructive
    operation by matching on the unescaped, unquoted name, so writes via these
    forms slipped past every protection that didn't use substring search.
    """

    def test_backslash_cp_to_enforcement_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "\\cp /tmp/evil enforcement/hooks/foo.py"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Backslash-escaped cp bypassed write protection on enforcement/"
        )

    def test_backslash_rm_sahjhan_dir_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "\\rm -rf docs/holtz/.sahjhan"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Backslash-escaped rm bypassed protection on .sahjhan dir"
        )

    def test_double_quoted_cp_to_enforcement_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": '"cp" /tmp/evil enforcement/hooks/foo.py'},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Double-quoted cp bypassed write protection"
        )

    def test_single_quoted_rm_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "'rm' -rf docs/holtz/.sahjhan"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Single-quoted rm bypassed protection on .sahjhan dir"
        )

    def test_backslash_python_interpreter_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "\\python3 -c \"open('enforcement/hooks/x','w')\"",
            },
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Backslash-escaped python interpreter bypassed protected-path check"
        )

    def test_backslash_curl_to_enforcement_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "\\curl -o enforcement/hooks/foo.py https://example.com/x",
            },
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Backslash-escaped curl bypassed -o protected-path check"
        )

    def test_backslash_cp_safe_target_allowed(self):
        """\\cp to a non-protected path remains allowed (no false positive)."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "\\cp file.txt /tmp/safe.txt"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_backslash_sahjhan_reset_blocked(self):
        """\\sahjhan reset must still be blocked by the subcommand allowlist."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "\\sahjhan reset --confirm"},
            "cwd": REPO_ROOT,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Backslash-escaped sahjhan bypassed subcommand allowlist"
        )

    def test_quoted_sahjhan_daemon_stop_blocked(self, tmp_path, mock_daemon):
        """'sahjhan' daemon stop must still be blocked mid-audit — quoting the
        command name must not bypass the sub-subcommand check."""
        mock_daemon.state = {"active": True, "state": "fix_loop"}
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "'sahjhan' daemon stop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Quoted sahjhan bypassed daemon stop allowlist"
        )


@pytest.mark.hook_e2e
class TestParentDirectoryRemovalBypass:
    """Destructive commands targeting the parent of a MANAGED path bypass
    the guard.

    Root cause: the rm check matches the literal MANAGED_DATA path
    (``docs/holtz/.sahjhan/``) against command arguments with
    ``startswith``. A parent path like ``docs/holtz`` does not start
    with the longer managed path, so the check skips it — even though
    ``rm -rf docs/holtz`` destroys the audit state just as thoroughly.

    Run 25 postmortem: Holtz ran ``rm -rf docs/holtz/.sahjhan``
    mid-audit, obliterating 1,110 ledger events. The guard was added
    to stop that exact move. A parent-dir rm is the same move with
    one extra slash — the guard must catch it.
    """

    def test_rm_docs_holtz_parent_blocked_on_active_audit(self, tmp_path):
        """rm -rf docs/holtz must be blocked when .sahjhan/ lives inside it."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs/holtz"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "rm -rf docs/holtz bypassed the guard — it destroys "
            "docs/holtz/.sahjhan/ even though the literal path doesn't match"
        )

    def test_rm_docs_holtz_trailing_slash_blocked(self, tmp_path):
        """rm -rf docs/holtz/ must be blocked — same bypass with trailing slash."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs/holtz/"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_rm_docs_grandparent_blocked(self, tmp_path):
        """rm -rf docs must be blocked when it contains the audit state."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_rm_relative_parent_blocked(self, tmp_path):
        """rm -rf ./docs/holtz must be blocked (relative path form)."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf ./docs/holtz/"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_rm_parent_allowed_when_terminated(self, tmp_path):
        """Recovery: parent-dir rm is fine once the audit is terminated."""
        sahjhan = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan.mkdir(parents=True)
        (sahjhan / "terminated").write_text("reason: test\n")
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs/holtz"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_rm_unrelated_dir_still_allowed(self, tmp_path):
        """Non-audit dirs must remain deletable — no false positives."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf build"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


@pytest.mark.hook_e2e
class TestTerminatedMarkerRecoveryPath:
    """When the `terminated` marker exists, the audit is dead (session key
    lost, ledger unwritable). The primer and stop_hook both direct the user
    to ``remove docs/holtz/.sahjhan/`` as the recovery step — but the
    bash_guard blocks that exact command.

    The guard exists to prevent Holtz from nuking the ledger during an
    ACTIVE audit (see run 25 postmortem). When the audit is already
    terminated, the guard is guarding nothing — it only traps the user in
    an instruction they're told to follow but can't execute. Lift the
    ``docs/holtz/.sahjhan/`` + managed-doc guards when the marker is
    present so the recovery path the plugin documents actually works.
    """

    def _with_terminated_marker(self, tmp_path):
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text(
            "reason: daemon_pid_dead\ninit_pid: 99999\n"
        )
        return str(tmp_path)

    def test_rm_sahjhan_dir_allowed_when_terminated(self, tmp_path):
        """rm -rf docs/holtz/.sahjhan/ must be allowed after termination."""
        cwd = self._with_terminated_marker(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs/holtz/.sahjhan/"},
            "cwd": cwd,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "Terminated audit recovery blocked — primer tells the user to "
            "remove docs/holtz/.sahjhan/ but the guard refuses the command"
        )

    def test_rm_sahjhan_dir_blocked_without_marker(self, tmp_path):
        """Without the terminated marker, rm must still be blocked (active audit)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)  # audit present, no termination
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf docs/holtz/.sahjhan/"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Active audit lost its guard on .sahjhan — the ledger is still live "
            "and Holtz could destroy it mid-run (the run 25 failure mode)"
        )

    def test_rm_sahjhan_file_allowed_when_terminated(self, tmp_path):
        """Deleting individual files inside .sahjhan/ is part of recovery too."""
        cwd = self._with_terminated_marker(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm docs/holtz/.sahjhan/daemon.pid"},
            "cwd": cwd,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "Recovery on a terminated audit must allow cleanup of .sahjhan contents"
        )

    def test_rm_status_md_allowed_when_terminated(self, tmp_path):
        """Managed docs (STATUS.md/PUNCHLIST.md) are re-rendered — deletable on recovery."""
        cwd = self._with_terminated_marker(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm docs/holtz/STATUS.md"},
            "cwd": cwd,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "After termination, managed docs exist as stale artifacts and "
            "blocking their deletion leaves the project in a half-state"
        )

    def test_write_to_managed_doc_allowed_when_terminated(self, tmp_path):
        """Write/Edit on STATUS.md/PUNCHLIST.md works once audit is terminated."""
        cwd = self._with_terminated_marker(tmp_path)
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/STATUS.md"},
            "cwd": cwd,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "Write to managed doc must be permitted during recovery so users "
            "can replace stale STATUS.md content"
        )

    def test_write_to_managed_doc_blocked_without_marker(self, tmp_path):
        """Without marker, Write to managed doc still blocked (live render)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)  # no terminated marker
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/STATUS.md"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Active audit must keep STATUS.md read-only (rendered from ledger)"
        )

    def test_write_to_sahjhan_data_allowed_when_terminated(self, tmp_path):
        """Write to .sahjhan/ contents works on a terminated audit."""
        cwd = self._with_terminated_marker(tmp_path)
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/notes.txt"},
            "cwd": cwd,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "Writing inside .sahjhan/ is blocked on live audits, but once the "
            "ledger is dead, the directory is user-owned state"
        )

    def test_write_to_enforcement_still_blocked_when_terminated(self, tmp_path):
        """PROTECTED plugin-internal paths are always off-limits, even after termination.

        The terminated marker lifts audit-state protections, not plugin integrity
        protections. An agent that tries to modify enforcement/ in any state is
        attempting to rewrite its own guards.
        """
        # Termination doesn't matter here — PROTECTED check fires on plugin cwd
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm enforcement/hooks/bash_guard.py"},
            "cwd": REPO_ROOT,
        }
        # Set up terminated marker in the plugin's own tree just to verify it
        # doesn't accidentally grant access to enforcement/.
        sahjhan_dir = os.path.join(REPO_ROOT, "docs", "holtz", ".sahjhan")
        marker = os.path.join(sahjhan_dir, "terminated")
        created_dir = False
        created_marker = False
        try:
            if not os.path.isdir(sahjhan_dir):
                os.makedirs(sahjhan_dir)
                created_dir = True
            if not os.path.isfile(marker):
                with open(marker, "w") as f:
                    f.write("reason: test\n")
                created_marker = True
            output = _run_hook(event)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
                "Terminated marker must not lift PROTECTED guards on enforcement/"
            )
        finally:
            if created_marker:
                os.unlink(marker)
            if created_dir:
                os.rmdir(sahjhan_dir)

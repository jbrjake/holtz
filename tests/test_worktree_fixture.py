"""F1-V — the worktree fixture is correct when it reproduces item 29.

W01 ships fixtures and no product change, so these tests describe the tree as
it stands: a hook driven at a linked worktree's cwd skips the very check it
exists to perform, because the audit directory it probes for is gitignored and
therefore absent from the worktree.

When W02 lands, `test_the_probe_is_cwd_relative_today` is the test that must
flip. It is written as an assertion about the *observed* asymmetry rather than
as an xfail so that the flip is a visible, deliberate edit.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worktree_project import fresh_enforcement_state  # noqa: E402

pytestmark = pytest.mark.hook_e2e


def _echo_event() -> dict:
    """A Bash PostToolUse event that is not itself a sahjhan invocation.

    `bash_guard` short-circuits on sahjhan commands before it ever reaches the
    audit-dir probe, so a sahjhan command here would pass for the wrong reason.
    """
    return {
        "tool_name": "Bash",
        "tool_input": {"command": "echo hello"},
        "tool_response": {"exit_code": 0, "stdout": "hello", "stderr": ""},
    }


class TestTheFixtureBuildsTheSituation:
    def test_the_audit_dir_exists_only_in_the_main_checkout(self, worktree_cwd):
        assert os.path.isdir(worktree_cwd.sahjhan_dir)
        assert not os.path.isdir(
            os.path.join(worktree_cwd.worktree, "docs", "holtz", ".sahjhan")
        )

    def test_the_worktree_is_linked_to_the_main_checkout(self, worktree_cwd):
        """A copied directory would reproduce nothing — the link is the point."""
        dotgit = os.path.join(worktree_cwd.worktree, ".git")
        assert os.path.isfile(dotgit), "a linked worktree carries a .git *file*"
        with open(dotgit, encoding="utf-8") as fh:
            assert "gitdir:" in fh.read()

    def test_the_stub_binary_is_the_one_the_hooks_resolve(self, worktree_cwd):
        """Positive claim: the stub really is reached, so a silent log is signal.

        Without this, "no manifest verify recorded" could mean the hook skipped
        the check *or* that the fixture never wired a binary up at all.
        """
        worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=worktree_cwd.main)
        # No daemon here, so bash_guard stops at the freshness check — but the
        # binary path itself must resolve, or the next test proves nothing.
        from worktree_project import _platform_triple

        stub = os.path.join(
            worktree_cwd.plugin_root, "bin", f"sahjhan-{_platform_triple()}"
        )
        assert os.access(stub, os.X_OK)


class TestTheAsymmetryItReproduces:
    """F1-V: `bash_guard` verifies in one checkout and not in the other."""

    def test_the_probe_is_cwd_relative_today(self, worktree_cwd, mock_daemon):
        mock_daemon.state = fresh_enforcement_state()

        worktree_cwd.reset_binary_calls()
        worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=worktree_cwd.main)
        main_calls = worktree_cwd.binary_calls()

        worktree_cwd.reset_binary_calls()
        worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=worktree_cwd.worktree)
        worktree_calls = worktree_cwd.binary_calls()

        # Positive on both sides: the main checkout reaches a *named* command,
        # the worktree reaches the binary not at all. Asserting only that the
        # worktree log is empty would pass just as well against a fixture whose
        # binary was never resolvable.
        assert any("manifest verify" in line for line in main_calls), main_calls
        assert worktree_calls == [], (
            "item 29: the worktree leg is expected to skip verification "
            f"entirely at this commit, but the binary was called: {worktree_calls}"
        )

    def test_both_legs_still_exit_cleanly(self, worktree_cwd, mock_daemon):
        """The asymmetry is in what got checked, not in what got reported.

        Both legs allow. That is exactly why the defect is invisible to a test
        that reads only the permission decision.
        """
        mock_daemon.state = fresh_enforcement_state()
        for cwd in (worktree_cwd.main, worktree_cwd.worktree):
            out = worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=cwd)
            assert out.get("_returncode", 0) == 0, out
            decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
            assert decision in (None, "allow"), out

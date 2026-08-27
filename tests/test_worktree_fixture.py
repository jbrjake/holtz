"""F1-V — the worktree fixture is correct when it reproduces item 29.

These tests are about the *fixture*: that it builds a main checkout whose audit
directory a linked worktree does not carry, and that its observable — the stub
binary's argv log — can tell "this hook verified" from "this hook exited early".

At `17e648e` the fixture recorded item 29 as observed: the worktree leg called
the binary not at all. W02 anchored the probe and that assertion was rewritten
in place. The substantive claims about what each leg decides live in
`test_worktree_audit_anchor.py`.
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


class TestTheFixtureCanSeeWhichCheckRan:
    """F1-V: the fixture's observable discriminates the two legs.

    This test asserted item 29 as the tree stood at `17e648e` — the worktree
    leg called the binary not at all — and was rewritten when W02 anchored the
    probe. It is kept rather than deleted because the claim it needs to make is
    unchanged: *the observable can tell the legs apart*. If it could not, W02's
    own V1 would be measuring nothing.

    The substantive assertion about what each leg now decides lives in
    `test_worktree_audit_anchor.py`.
    """

    def test_both_legs_reach_manifest_verify(self, worktree_cwd, mock_daemon):
        mock_daemon.state = fresh_enforcement_state()
        seen = {}
        for name, cwd in (("main", worktree_cwd.main), ("worktree", worktree_cwd.worktree)):
            worktree_cwd.reset_binary_calls()
            worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=cwd)
            seen[name] = worktree_cwd.binary_calls()
        for name, calls in seen.items():
            assert any("manifest verify" in line for line in calls), (name, calls)

    def test_the_observable_still_discriminates(self, worktree_cwd, mock_daemon):
        """Remove the audit dir and the same leg records nothing.

        Without this, "both legs verify" would hold just as well against a
        fixture whose log recorded every subprocess, or none.
        """
        import shutil

        mock_daemon.state = fresh_enforcement_state()
        shutil.rmtree(worktree_cwd.sahjhan_dir)
        worktree_cwd.reset_binary_calls()
        worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=worktree_cwd.worktree)
        assert worktree_cwd.binary_calls() == []

    def test_both_legs_still_exit_cleanly(self, worktree_cwd, mock_daemon):
        """`bash_guard` reports `allow` either way when the tree is clean.

        The permission decision carries no information about whether
        verification happened — which is exactly why item 29 shipped, and why
        this fixture measures the binary call instead.
        """
        mock_daemon.state = fresh_enforcement_state()
        for cwd in (worktree_cwd.main, worktree_cwd.worktree):
            out = worktree_cwd.run_hook("bash_guard.py", _echo_event(), cwd=cwd)
            assert out.get("_returncode", 0) == 0, out
            decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
            assert decision in (None, "allow"), out

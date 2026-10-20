"""The consumer side of the sandbox fuse: a refusing daemon must block, not allow.

The failure this guards is subtle and total. `read_cache` returned `None` for
every daemon error, and every gate reads `is_enforcement_fresh(None)` as False
and allows — which is right for "no audit here" and catastrophically wrong for
"the daemon just refused because the agent is no longer confined". Under the
old shape, tripping the fuse did not tighten enforcement; it deleted it.

Every test here drives a hook as a subprocess, because the thing under test is
a decision Claude Code reads off the hook's stdout.
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_primer import _init_sahjhan  # noqa: E402
from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

BOUNDARY_REASON = "sandbox_not_enabled"


def _fresh_state():
    """An enforcement cache that looks like a live audit mid-fix-loop."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    return {
        "active": True,
        "state": "fix_loop",
        "unregistered_commits": [],
        "pattern_analysis_overdue": False,
        "perspective": "component",
        "perspectives_done": 1,
        "perspectives_total": 13,
        "stall": 0,
        "last_refresh": now,
        "last_sahjhan_cmd": now,
    }


def _deny_reason(output: dict) -> str:
    hso = output.get("hookSpecificOutput", {})
    assert hso.get("permissionDecision") == "deny", f"expected a block, got {output}"
    return hso.get("permissionDecisionReason", "")


@pytest.mark.hook_e2e
class TestPreToolUseFailsClosed:

    def test_commit_gate_blocks_bash(self, tmp_path, mock_daemon):
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
             "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert "AUDIT BOUNDARY MISSING" in _deny_reason(output)

    def test_commit_gate_blocks_sahjhan_commands_too(self, tmp_path, mock_daemon):
        """The sahjhan allowance is not a hole to leave open.

        `transition`, `event` and `set` write the ledger straight to disk with
        no daemon involved, so letting them through would let the run keep
        advancing while the enforcement meant to gate it does nothing.
        """
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "sahjhan transition fix_commit BH-001"},
             "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert "AUDIT BOUNDARY MISSING" in _deny_reason(output)

    def test_pre_tool_hook_blocks_edits(self, tmp_path, mock_daemon):
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        source = tmp_path / "src" / "app.py"
        source.parent.mkdir(parents=True)
        source.write_text("x = 1\n")
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py",
            {"tool_name": "Edit", "tool_input": {"file_path": str(source)},
             "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert "AUDIT BOUNDARY MISSING" in _deny_reason(output)

    def test_the_block_names_the_one_thing_that_fixes_it(self, tmp_path, mock_daemon):
        """The agent cannot fix this and must not try; only a human can.

        A block that does not say `holtz-start` sends the agent hunting for a
        bug in enforcement, which is exactly the wrong direction.
        """
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        reason = _deny_reason(output)
        assert "holtz-start" in reason
        assert BOUNDARY_REASON in reason, "the daemon's own reason code should reach the user"


@pytest.mark.hook_e2e
class TestScopeOfTheBlock:
    """It must fire for a refusing daemon and for nothing else."""

    def test_a_live_daemon_that_serves_does_not_block(self, tmp_path, mock_daemon):
        mock_daemon.state = _fresh_state()
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    def test_no_daemon_at_all_does_not_block(self, tmp_path, monkeypatch):
        """A project that is not being audited must be untouched.

        Only a *live* daemon can produce the refusal, so the fail-closed path
        is self-limiting: there is no daemon here, so there is no audit, so
        holtz has no business blocking anything.
        """
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", str(tmp_path / "nothing.sock"))
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
             "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    def test_stale_enforcement_still_blocks(self, tmp_path, mock_daemon):
        """Freshness cannot gate this, because a refusing daemon serves no cache.

        The refusal arrives *instead of* the state the freshness check reads,
        so ordering the boundary check after it would mean the check never
        runs — the exact inversion this whole change exists to fix.
        """
        mock_daemon.state = None  # nothing stored: is_enforcement_fresh() is False
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
             "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert "AUDIT BOUNDARY MISSING" in _deny_reason(output)


def _audit_dir(root) -> str:
    """The audit state directory `holtz-start` and death detection both use."""
    return os.path.join(str(root), "docs", "holtz", ".sahjhan")


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _decision(output: dict) -> str:
    return output.get("hookSpecificOutput", {}).get("permissionDecision", "")


@pytest.mark.hook_e2e
class TestAnAbandonedAuditIsNotHeldByTheBoundary:
    """Item 41. The refusal was read as "an audit needs protecting" when all it
    says is "a daemon is answering".

    Those are different facts, and when they come apart the block is aimed at
    the wrong people: every Bash, Write and Edit in the project — and in every
    linked worktree, since the socket is anchored — denied with *type
    holtz-start*, including sessions doing no audit at all.

    The discriminator is not freshness. A refusing daemon serves no cache, so
    `is_enforcement_fresh` is False for a live audit and an abandoned one
    alike; ordering the boundary check after it is the fuse inversion this
    module's other tests exist to prevent. It is the two facts that death
    detection already writes: the `terminated` marker, and an init PID whose
    process is gone.
    """

    def _cmd_event(self, tmp_path, command="ls"):
        return {"tool_name": "Bash", "tool_input": {"command": command},
                "cwd": str(tmp_path)}

    def test_a_terminated_audit_releases_bash(self, tmp_path, mock_daemon):
        _write(os.path.join(_audit_dir(tmp_path), "terminated"),
               "reason: daemon_pid_dead\ninit_pid: 99999999\n")
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py", self._cmd_event(tmp_path), cwd=str(tmp_path),
        )
        assert code == 0
        assert _decision(output) != "deny", \
            "the audit is over; the boundary is protecting nothing"

    def test_a_terminated_audit_releases_edits(self, tmp_path, mock_daemon):
        _write(os.path.join(_audit_dir(tmp_path), "terminated"),
               "reason: daemon_pid_dead\ninit_pid: 99999999\n")
        source = tmp_path / "src" / "app.py"
        _write(str(source), "x = 1\n")
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py",
            {"tool_name": "Edit", "tool_input": {"file_path": str(source)},
             "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        assert _decision(output) != "deny"

    def test_the_recovery_command_lifecycle_exempts_is_not_revoked_here(
        self, tmp_path, mock_daemon,
    ):
        """`_daemon_lifecycle` blocks a terminated audit and lets recovery through.

        `commit_gate` then denied that same command on the boundary, because
        `is_sahjhan_cmd` sits *below* the boundary check — deliberately, so a
        live audit cannot keep advancing its ledger with enforcement down. The
        two rules only conflict once the audit is over, and there the exemption
        has to win: `sahjhan daemon stop` is how the human gets the project back.
        """
        _write(os.path.join(_audit_dir(tmp_path), "terminated"),
               "reason: daemon_pid_dead\ninit_pid: 99999999\n")
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py",
            self._cmd_event(tmp_path, "sahjhan daemon stop"),
            cwd=str(tmp_path),
        )
        assert code == 0
        assert _decision(output) != "deny"

    def test_a_dead_init_pid_releases_before_the_marker_is_written(
        self, tmp_path, mock_daemon,
    ):
        """The marker is written by whichever hook notices first, so a gate that
        only read the marker would still deny the call that was about to
        produce it."""
        _write(os.path.join(_audit_dir(tmp_path), "daemon-init-pid"), "99999999\n")
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py", self._cmd_event(tmp_path), cwd=str(tmp_path),
        )
        assert code == 0
        assert _decision(output) != "deny"

    def test_a_live_init_pid_still_blocks(self, tmp_path, mock_daemon):
        """V2 — the fuse. A running audit whose boundary just came down is the
        whole reason this block exists, and nothing here may soften it."""
        _write(os.path.join(_audit_dir(tmp_path), "daemon-init-pid"), f"{os.getpid()}\n")
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py", self._cmd_event(tmp_path), cwd=str(tmp_path),
        )
        assert code == 0
        reason = _deny_reason(output)
        assert "AUDIT BOUNDARY MISSING" in reason
        assert "holtz-start" in reason, \
            "a block that stands must still name the word that clears it"

    def test_an_audit_with_no_init_pid_recorded_still_blocks(self, tmp_path, mock_daemon):
        """"I cannot tell" is answered "live".

        A pre-init or legacy audit records no PID, and reading that absence as
        death would hand the release to exactly the audits death detection
        cannot see.
        """
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "commit_gate.py", self._cmd_event(tmp_path), cwd=str(tmp_path),
        )
        assert code == 0
        assert "AUDIT BOUNDARY MISSING" in _deny_reason(output)

    def test_a_linked_worktree_gets_the_same_answer(self, worktree_cwd, mock_daemon):
        """V3. The socket is anchored at the project, so a worktree reaches the
        same refusing daemon — and must reach the same audit state to judge it
        by, rather than a cwd-relative probe that finds no audit dir."""
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}}

        blocked = [
            _decision(worktree_cwd.run_hook("commit_gate.py", event, cwd=where))
            for where in (worktree_cwd.main, worktree_cwd.worktree)
        ]
        assert blocked == ["deny", "deny"], \
            f"a live audit blocks in both checkouts, got {blocked}"

        _write(os.path.join(worktree_cwd.sahjhan_dir, "terminated"),
               "reason: daemon_pid_dead\ninit_pid: 99999999\n")
        released = [
            _decision(worktree_cwd.run_hook("commit_gate.py", event, cwd=where))
            for where in (worktree_cwd.main, worktree_cwd.worktree)
        ]
        assert "deny" not in released, \
            f"the same terminated audit must release both checkouts, got {released}"


@pytest.mark.slow
@pytest.mark.hook_e2e
class TestTheEscapeTheBlockNamesIsRunnable:
    """V1's other arm. A session killed mid-`fix_loop` leaves its daemon alive,
    so the audit is *not* abandoned and the block correctly stands — which
    makes "the message names a working escape" the load-bearing claim, and
    a claim no mock can settle: the mock's refusal is a flag a test sets,
    while the real fuse's is a verdict on the settings file the escape writes.
    """

    def test_holtz_start_lifts_the_block_it_tells_the_human_to_lift(
        self, real_daemon, monkeypatch, tmp_path,
    ):
        project = real_daemon["project_root"]
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"},
                 "cwd": project}

        # `_apply_settings` backs the previous block up under `boundary_dir`,
        # which is keyed off HOME — pointed at the tmp dir so a test cannot
        # leave a file in the user's.
        monkeypatch.setenv("HOME", str(tmp_path))

        # Take the boundary down under the running daemon. This is the state a
        # killed session leaves behind: `daemon-init-pid` still names a live
        # process, so `audit_abandoned` is False and nothing releases it.
        os.remove(os.path.join(project, ".claude", "settings.local.json"))
        code, output, _ = run_enforcement_hook("commit_gate.py", event, cwd=project)
        assert code == 0
        reason = _deny_reason(output)
        assert "holtz-start" in reason, \
            f"the block must name the escape it expects a human to run: {reason}"

        # Run it — the settings step of `arm()`, the same call the verb makes.
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from sandbox_control import _apply_settings
        _apply_settings(project)

        code, output, _ = run_enforcement_hook("commit_gate.py", event, cwd=project)
        assert code == 0
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny", \
            f"the named escape did not lift the block: {output}"


@pytest.mark.hook_e2e
class TestPostToolUseWarns:
    """After the fact, a block undoes nothing — but the reason still has to land."""

    def test_post_tool_hook_warns(self, tmp_path, mock_daemon):
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON
        code, output, _ = run_enforcement_hook(
            "post_tool_hook.py",
            {"tool_name": "Bash", "tool_input": {"command": "ls"},
             "tool_response": {"exit_code": 0}, "cwd": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "AUDIT BOUNDARY MISSING" in context
        assert output.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"


@pytest.mark.hook_e2e
class TestPrimerDistinguishesTheCause:

    def test_missing_boundary_is_not_reported_as_broken_enforcement(self, tmp_path, mock_daemon):
        """"Report this and wait" is the wrong instruction for a one-word fix.

        The unrecoverable-enforcement message tells the agent to stop and
        escalate a bug. A missing boundary is not a bug — someone has not typed
        `holtz-start` yet — and conflating them wastes the user's time on a
        hunt for a defect that does not exist.
        """
        # A real ledger, so primer gets past its "no resolvable state" exit and
        # actually reaches the health probe. Without this the test passes by
        # never running the code it is named after.
        _init_sahjhan(tmp_path)
        mock_daemon.state = _fresh_state()
        mock_daemon.refuse_boundary = BOUNDARY_REASON

        code, output, _ = run_enforcement_hook(
            "primer.py", {"cwd": str(tmp_path)}, cwd=str(tmp_path),
        )
        assert code == 0
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SAHJHAN RESUME CONTEXT" in context, \
            f"primer never reached the health probe: {context!r}"
        assert "AUDIT BOUNDARY MISSING" in context
        assert "ENFORCEMENT FAILURE" not in context

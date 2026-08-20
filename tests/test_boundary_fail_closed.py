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

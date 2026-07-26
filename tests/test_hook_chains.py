"""Hook chain integration tests — simulate realistic multi-hook sequences.

In production, hooks chain via hooks.json. These tests verify that:
- All hooks in a chain produce valid output
- Chains short-circuit correctly on block
- PostToolUse chains record state correctly
- Full PreToolUse → PostToolUse round trips work

Uses mock_daemon for most tests (format verification only).
Uses real_daemon where enforcement state must be real.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hook_runner import run_hook as _run_hook

REPO_ROOT = Path(__file__).parent.parent

# Hook paths in chain order (as defined in hooks.json)
PRE_TOOL_LIFECYCLE = str(REPO_ROOT / "enforcement" / "hooks" / "_daemon_lifecycle.py")
PRE_TOOL_BOOTSTRAP = str(REPO_ROOT / "enforcement" / "hooks" / "_sahjhan_bootstrap.py")
PRE_TOOL_COMMIT_GATE = str(REPO_ROOT / "enforcement" / "hooks" / "commit_gate.py")
POST_TOOL_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "post_tool_hook.py")
POST_TOOL_BASH_GUARD = str(REPO_ROOT / "enforcement" / "hooks" / "bash_guard.py")
POST_TOOL_TRACKER = str(REPO_ROOT / "enforcement" / "hooks" / "protocol_tracker.py")
STOP_HOOK = str(REPO_ROOT / "enforcement" / "hooks" / "stop_hook.py")

pytestmark = pytest.mark.integration


def _is_pre_tool_allowed(output: dict) -> bool:
    """Check if PreToolUse hook allowed."""
    return output.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"


def _is_pre_tool_blocked(output: dict) -> bool:
    """Check if PreToolUse hook blocked."""
    return output.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def _is_post_tool_ok(output: dict) -> bool:
    """Check if PostToolUse hook exited ok."""
    return output.get("continue") is True


def _is_stop_allowed(output: dict) -> bool:
    """Check if stop was allowed (empty output or systemMessage without block)."""
    return output.get("_empty", False) or (
        "systemMessage" in output and output.get("decision") != "block"
    )


def _is_stop_blocked(output: dict) -> bool:
    """Check if stop was blocked."""
    return output.get("decision") == "block"


# ---------------------------------------------------------------------------
# 2a: PreToolUse chain for Bash (sahjhan command)
# ---------------------------------------------------------------------------


class TestPreToolUseBashChain:
    """PreToolUse chain for Bash: lifecycle → bootstrap → commit_gate."""

    def test_allowed_sahjhan_command_passes_all_hooks(self, tmp_path):
        """An allowed sahjhan command passes through the entire chain."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status 2>&1"},
            "cwd": str(tmp_path),
        }
        # Chain order: lifecycle → bootstrap → commit_gate
        for hook_path in [PRE_TOOL_LIFECYCLE, PRE_TOOL_BOOTSTRAP, PRE_TOOL_COMMIT_GATE]:
            output = _run_hook(hook_path, event)
            assert _is_pre_tool_allowed(output), \
                f"Hook {Path(hook_path).name} should allow sahjhan status: {output}"

    def test_blocked_command_short_circuits(self, tmp_path):
        """Bootstrap blocks sahjhan reset — commit_gate never needs to run.

        In Claude Code's actual behavior, a blocking hook stops the chain.
        We verify each hook independently and confirm the block happens
        at the expected point.
        """
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm"},
            "cwd": str(tmp_path),
        }
        # lifecycle: allows (no active audit)
        output = _run_hook(PRE_TOOL_LIFECYCLE, event)
        assert _is_pre_tool_allowed(output)

        # bootstrap: blocks (reset is not in allowlist)
        output = _run_hook(PRE_TOOL_BOOTSTRAP, event)
        assert _is_pre_tool_blocked(output)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "reset" in reason.lower()

        # commit_gate: would allow (no enforcement state)
        # In reality this never runs because bootstrap already blocked.
        output = _run_hook(PRE_TOOL_COMMIT_GATE, event)
        assert _is_pre_tool_allowed(output)

    def test_lifecycle_blocks_when_daemon_dead(self, tmp_path):
        """Lifecycle hook blocks everything when daemon is dead."""
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        with open(os.path.join(sahjhan_dir, "terminated"), "w") as f:
            f.write("reason: daemon_pid_dead\n")

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "cwd": str(tmp_path),
        }
        # lifecycle: blocks (terminated marker exists)
        output = _run_hook(PRE_TOOL_LIFECYCLE, event)
        assert _is_pre_tool_blocked(output)
        # In real chain, bootstrap and commit_gate never run.


# ---------------------------------------------------------------------------
# 2b: PostToolUse chain for Bash
# ---------------------------------------------------------------------------


class TestPostToolUseBashChain:
    """PostToolUse chain for Bash: post_tool_hook → bash_guard → protocol_tracker."""

    def test_normal_command_passes_all_hooks(self, tmp_path, monkeypatch):
        """A normal echo command passes through all PostToolUse hooks."""
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"exit_code": 0, "output": "hello"},
            "cwd": str(tmp_path),
        }
        for hook_path in [POST_TOOL_HOOK, POST_TOOL_BASH_GUARD, POST_TOOL_TRACKER]:
            output = _run_hook(hook_path, event)
            assert _is_post_tool_ok(output), \
                f"Hook {Path(hook_path).name} should allow: {output}"

    def test_git_commit_tracked_by_protocol_tracker(self, mock_daemon, tmp_path):
        """A git commit is recorded by protocol_tracker."""
        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 0,
            "unregistered_commits": [],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "pattern_analysis_overdue": False,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix: something"'},
            "tool_response": {
                "exit_code": 0,
                "output": "[dev abc1234] fix: something\n 1 file changed",
            },
            "cwd": str(tmp_path),
        }
        output = _run_hook(POST_TOOL_TRACKER, event)
        assert _is_post_tool_ok(output)

        # Verify commit was recorded in state
        assert "abc1234" in mock_daemon.state.get("unregistered_commits", [])

    def test_sahjhan_command_refreshes_state(self, mock_daemon, tmp_path, monkeypatch):
        """A sahjhan command triggers state refresh in protocol_tracker."""
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(REPO_ROOT))
        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 5,
            "unregistered_commits": [],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "pattern_analysis_overdue": False,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status 2>&1"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop (10 events)"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(POST_TOOL_TRACKER, event)
        assert _is_post_tool_ok(output)


# ---------------------------------------------------------------------------
# 2c: Full round trip (PreToolUse → PostToolUse)
# ---------------------------------------------------------------------------


class TestFullRoundTrip:
    """Complete PreToolUse → tool execution → PostToolUse round trip."""

    def test_allowed_bash_round_trip(self, tmp_path, monkeypatch):
        """Full round trip for an allowed bash command."""
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        pre_event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        post_event = {
            **pre_event,
            "tool_response": {"exit_code": 0, "output": "hello"},
        }

        # PreToolUse chain
        for hook in [PRE_TOOL_LIFECYCLE, PRE_TOOL_BOOTSTRAP, PRE_TOOL_COMMIT_GATE]:
            output = _run_hook(hook, pre_event)
            assert _is_pre_tool_allowed(output), \
                f"Pre {Path(hook).name}: {output}"

        # PostToolUse chain
        for hook in [POST_TOOL_HOOK, POST_TOOL_BASH_GUARD, POST_TOOL_TRACKER]:
            output = _run_hook(hook, post_event)
            assert _is_post_tool_ok(output), \
                f"Post {Path(hook).name}: {output}"

    def test_commit_round_trip_with_enforcement(self, mock_daemon, tmp_path, monkeypatch):
        """git commit round trip: PreToolUse allows, PostToolUse records."""
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))

        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 0,
            "unregistered_commits": [],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "pattern_analysis_overdue": False,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        pre_event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix: test"'},
            "cwd": str(tmp_path),
        }

        # PreToolUse: all hooks allow (no unregistered commits yet)
        for hook in [PRE_TOOL_LIFECYCLE, PRE_TOOL_BOOTSTRAP, PRE_TOOL_COMMIT_GATE]:
            output = _run_hook(hook, pre_event)
            assert _is_pre_tool_allowed(output), \
                f"Pre {Path(hook).name}: {output}"

        # Simulate tool execution succeeding (hash must be hex for regex)
        post_event = {
            **pre_event,
            "tool_response": {
                "exit_code": 0,
                "output": "[dev a1b2c3d] fix: test\n 1 file changed",
            },
        }

        # PostToolUse: tracker records the commit
        output = _run_hook(POST_TOOL_TRACKER, post_event)
        assert _is_post_tool_ok(output)
        assert "a1b2c3d" in mock_daemon.state.get("unregistered_commits", [])

        # Now a second commit should be blocked by commit_gate
        pre_event2 = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix: another"'},
            "cwd": str(tmp_path),
        }
        output = _run_hook(PRE_TOOL_COMMIT_GATE, pre_event2)
        assert _is_pre_tool_blocked(output), \
            f"Second commit should be blocked: {output}"


# ---------------------------------------------------------------------------
# 2d: Chain with one hook blocking
# ---------------------------------------------------------------------------


class TestChainBlockingBehavior:
    """Verify chain semantics when one hook blocks."""

    def test_bootstrap_blocks_before_commit_gate(self):
        """sahjhan reset is blocked by bootstrap — commit_gate is irrelevant."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan reset --confirm"},
            "cwd": "/tmp/fake",
        }
        # bootstrap: blocks
        bootstrap_output = _run_hook(PRE_TOOL_BOOTSTRAP, event)
        assert _is_pre_tool_blocked(bootstrap_output)

        # commit_gate: allows (sahjhan commands are always allowed in commit_gate)
        gate_output = _run_hook(PRE_TOOL_COMMIT_GATE, event)
        assert _is_pre_tool_allowed(gate_output)

    def test_commit_gate_blocks_when_bootstrap_allows(self, mock_daemon, tmp_path):
        """commit_gate can block even when bootstrap allows (protocol obligation)."""
        mock_daemon.state = {
            "active": True,
            "state": "fix_loop",
            "stall": 0,
            "unregistered_commits": ["abc1234"],
            "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "pattern_analysis_overdue": False,
            "perspective": "integration",
            "perspectives_done": 3,
            "perspectives_total": 13,
            "last_refresh": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }

        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix: x"'},
            "cwd": str(tmp_path),
        }
        # bootstrap: allows (git commit is not a sahjhan command)
        output = _run_hook(PRE_TOOL_BOOTSTRAP, event)
        assert _is_pre_tool_allowed(output)

        # commit_gate: blocks (unregistered commit exists)
        output = _run_hook(PRE_TOOL_COMMIT_GATE, event)
        assert _is_pre_tool_blocked(output)

    def test_write_guard_blocks_edit_to_enforcement(self):
        """Write/Edit to enforcement/ blocked by bootstrap."""
        protected = str(REPO_ROOT / "enforcement" / "hooks" / "evil.py")
        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": protected,
                "old_string": "x",
                "new_string": "y",
            },
            "cwd": str(REPO_ROOT),
        }
        output = _run_hook(PRE_TOOL_BOOTSTRAP, event)
        assert _is_pre_tool_blocked(output)


# ---------------------------------------------------------------------------
# 2d-bis: Chicken-and-egg stall block (#70 item 1)
# ---------------------------------------------------------------------------


def _stalled_fix_loop_state(stall: int, commits: list[str] | None = None) -> dict:
    """A fresh fix_loop cache with the stall counter tripped."""
    now = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    return {
        "active": True,
        "state": "fix_loop",
        "stall": stall,
        "unregistered_commits": commits or [],
        "last_sahjhan_cmd": now,
        "pattern_analysis_overdue": False,
        "perspective": "integration",
        "perspectives_done": 3,
        "perspectives_total": 13,
        "last_refresh": now,
    }


class TestChickenAndEggStallBlock:
    """#70 item 1: a stalled run must still be able to run sahjhan to re-sync.

    Before the fix, the stall block ("N commands without protocol event")
    blocked *all* Bash including the ``sahjhan status`` needed to clear it,
    and only a bare, unwrapped invocation slipped through.
    """

    def test_wrapped_sahjhan_resync_allowed_through_stall_block(self, mock_daemon, tmp_path):
        """``cd repo && sahjhan status | head`` passes commit_gate when stalled."""
        mock_daemon.state = _stalled_fix_loop_state(stall=20)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"cd {tmp_path} && sahjhan status | head"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(PRE_TOOL_COMMIT_GATE, event)
        assert _is_pre_tool_allowed(output), \
            f"Wrapped sahjhan re-sync must clear the stall block: {output}"

    def test_plain_command_still_blocked_by_stall(self, mock_daemon, tmp_path):
        """A non-sahjhan command is still blocked while stalled."""
        mock_daemon.state = _stalled_fix_loop_state(stall=20)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(PRE_TOOL_COMMIT_GATE, event)
        assert _is_pre_tool_blocked(output), \
            "Plain command must remain blocked by the stall gate"

    def test_git_commit_with_sahjhan_still_blocked_by_stall(self, mock_daemon, tmp_path):
        """The re-sync exemption must not become a git-commit bypass."""
        mock_daemon.state = _stalled_fix_loop_state(stall=20)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'sahjhan status && git commit -m "x"'},
            "cwd": str(tmp_path),
        }
        output = _run_hook(PRE_TOOL_COMMIT_GATE, event)
        assert _is_pre_tool_blocked(output), \
            "A git commit chained with sahjhan must not slip past the stall block"

    def test_wrapped_sahjhan_resync_resets_stall(self, mock_daemon, tmp_path, monkeypatch):
        """protocol_tracker clears the stall counter on a wrapped re-sync."""
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(REPO_ROOT))
        mock_daemon.state = _stalled_fix_loop_state(stall=20)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": f"cd {tmp_path} && sahjhan status | head"},
            "tool_response": {"exit_code": 0, "output": "state: fix_loop"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(POST_TOOL_TRACKER, event)
        assert _is_post_tool_ok(output)
        assert mock_daemon.state.get("stall") == 0, \
            "Wrapped sahjhan re-sync must reset the stall counter"

    def test_plain_command_increments_stall(self, mock_daemon, tmp_path):
        """A plain command still increments the stall counter (contrast)."""
        mock_daemon.state = _stalled_fix_loop_state(stall=5)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"exit_code": 0, "output": "hello"},
            "cwd": str(tmp_path),
        }
        output = _run_hook(POST_TOOL_TRACKER, event)
        assert _is_post_tool_ok(output)
        assert mock_daemon.state.get("stall") == 6, \
            "Plain command should increment stall, not reset it"


# ---------------------------------------------------------------------------
# 2e: Stop chain
# ---------------------------------------------------------------------------


class TestStopChain:
    """Stop hook chain behavior."""

    def test_stop_allowed_when_no_audit(self, tmp_path):
        """Stop is allowed when no active audit exists."""
        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        assert _is_stop_allowed(output)

    def test_stop_allowed_after_termination(self, tmp_path):
        """Stop is allowed when audit has been terminated."""
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        with open(os.path.join(sahjhan_dir, "terminated"), "w") as f:
            f.write("reason: daemon_pid_dead\n")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        assert _is_stop_allowed(output)

    def test_stop_blocked_in_active_state(self, tmp_path, monkeypatch):
        """Stop is blocked during active audit with non-terminal state."""
        sahjhan_dir = os.path.join(str(tmp_path), "docs", "holtz", ".sahjhan")
        os.makedirs(sahjhan_dir, exist_ok=True)
        with open(os.path.join(sahjhan_dir, "daemon-init-pid"), "w") as f:
            f.write(str(os.getpid()))
        with open(os.path.join(sahjhan_dir, "status-cache.json"), "w") as f:
            json.dump({"state": "fix_loop"}, f)
        monkeypatch.setenv("SAHJHAN_DAEMON_SOCKET", "/tmp/nonexistent.sock")

        event = {"tool_name": "Stop", "cwd": str(tmp_path)}
        output = _run_hook(STOP_HOOK, event)
        assert _is_stop_blocked(output)

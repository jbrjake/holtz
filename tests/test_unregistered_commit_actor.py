"""The pending-commit block is a charge against one actor's own commits.

P0.3 runs the fix loop several subagents wide, each in its own worktree. The
commit gate refuses `git commit` in `fix_loop` while a commit is unregistered,
and that list was run-global: the first subagent to commit blocked every other
one, and the block named `transition fix_commit` as the way out — a transition
the orchestrator owns, gated on `git log -1` and a tree hash taken at the
project root. A subagent could not reach its own escape, which is #77's shape.

Keyed on the actor (D41), each subagent is charged for its own commits and
nobody else's. This is the same fix D10 applied to the stall counter, and the
actor comes from the same place: `agent_id` on the hook payload, with the
orchestrator as the empty-string bucket — a real actor, never a wildcard.

The clear stays run-global. `fix_commit` registers the commit at `HEAD`, and
after a fast-forward that commit belongs to whichever subagent authored it;
the transition cannot know which, so it clears the slate exactly as it did
before keying.

Driven by subprocess throughout — the interface Claude Code actually uses, and
the only one that cannot be poisoned by another test's import of a same-named
module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hook_runner import run_hook as _run_hook

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMIT_GATE = str(REPO_ROOT / "enforcement" / "hooks" / "commit_gate.py")
TRACKER = str(REPO_ROOT / "enforcement" / "hooks" / "protocol_tracker.py")

pytestmark = pytest.mark.hook_e2e


def _fix_loop_state(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    state = {
        "active": True,
        "state": "fix_loop",
        "stall": {},
        "unregistered_commits": {},
        "last_sahjhan_cmd": now,
        "pattern_analysis_overdue": False,
        "perspective": "integration",
        "perspectives_done": 3,
        "perspectives_total": 13,
        "last_refresh": now,
    }
    state.update(overrides)
    return state


def _commit_event(cwd: str, agent_id: str | None = None) -> dict:
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": 'git commit -m "fix(x): BH-101"'},
        "cwd": cwd,
    }
    if agent_id is not None:
        event["agent_id"] = agent_id
    return event


def _blocked(output: dict) -> str | None:
    hso = output.get("hookSpecificOutput", {})
    if hso.get("permissionDecision") == "deny":
        return hso.get("permissionDecisionReason", "")
    return None


class TestTheBlockIsChargedToTheActorWhoCommitted:
    """A sibling's commit is not evidence about this actor."""

    def test_a_subagent_is_not_blocked_by_a_siblings_commit(
        self, mock_daemon, tmp_path
    ):
        """The whole point of P0.3: two fix subagents commit independently."""
        mock_daemon.state = _fix_loop_state(
            unregistered_commits={"agent-a": ["abc1234"]}
        )

        output = _run_hook(COMMIT_GATE, _commit_event(str(tmp_path), "agent-b"))

        assert _blocked(output) is None, output

    def test_an_actor_is_blocked_by_its_own_unregistered_commit(
        self, mock_daemon, tmp_path
    ):
        """Per-actor is not no-actor — the charge still lands on its author."""
        mock_daemon.state = _fix_loop_state(
            unregistered_commits={"agent-a": ["abc1234"]}
        )

        reason = _blocked(_run_hook(COMMIT_GATE, _commit_event(str(tmp_path), "agent-a")))

        assert reason is not None, "agent-a's own commit must still block it"
        assert "fix_commit" in reason, reason

    def test_the_orchestrator_is_a_bucket_and_not_a_wildcard(
        self, mock_daemon, tmp_path
    ):
        """An orchestrator commit must not block every subagent in the run."""
        mock_daemon.state = _fix_loop_state(unregistered_commits={"": ["abc1234"]})

        subagent = _run_hook(COMMIT_GATE, _commit_event(str(tmp_path), "agent-a"))
        orchestrator = _run_hook(COMMIT_GATE, _commit_event(str(tmp_path)))

        assert _blocked(subagent) is None, subagent
        assert _blocked(orchestrator) is not None, orchestrator

    def test_a_flat_list_from_a_run_that_predates_keying_is_the_orchestrators(
        self, mock_daemon, tmp_path
    ):
        """A run upgrading mid-flight keeps its charge instead of getting a reset.

        The same tolerance `stall_counts` gives an int: the old value was the
        whole run's, which is the orchestrator's as far as anything can now
        tell. Dropping it would hand a pending commit a free pass at exactly
        the wrong moment.
        """
        mock_daemon.state = _fix_loop_state(unregistered_commits=["abc1234"])

        orchestrator = _run_hook(COMMIT_GATE, _commit_event(str(tmp_path)))
        subagent = _run_hook(COMMIT_GATE, _commit_event(str(tmp_path), "agent-a"))

        assert _blocked(orchestrator) is not None, orchestrator
        assert _blocked(subagent) is None, subagent


class TestTheTrackerChargesTheCommitToItsAuthor:
    """PostToolUse writes the bucket the gate then reads."""

    def _post_commit_event(self, cwd: str, agent_id: str | None = None) -> dict:
        event = _commit_event(cwd, agent_id)
        event["tool_response"] = {
            "exit_code": 0,
            "stdout": "[dev abc1234] fix(x): BH-101\n 1 file changed",
            "stderr": "",
        }
        return event

    def test_a_subagents_commit_lands_in_its_own_bucket(self, mock_daemon, tmp_path):
        """Asserted on the bucket's contents, not on "something was written"."""
        mock_daemon.state = _fix_loop_state()

        _run_hook(TRACKER, self._post_commit_event(str(tmp_path), "agent-a"))

        assert mock_daemon.state["unregistered_commits"] == {"agent-a": ["abc1234"]}

    def test_the_orchestrators_commit_lands_in_the_empty_bucket(
        self, mock_daemon, tmp_path
    ):
        mock_daemon.state = _fix_loop_state()

        _run_hook(TRACKER, self._post_commit_event(str(tmp_path)))

        assert mock_daemon.state["unregistered_commits"] == {"": ["abc1234"]}

    def test_fix_commit_clears_every_bucket(self, mock_daemon, tmp_path):
        """The clear stays run-global, because the transition names no actor.

        After a fast-forward the commit at `HEAD` is the subagent's, and
        `transition fix_commit` is the orchestrator's — so a per-actor clear
        would leave the real author charged forever.
        """
        mock_daemon.state = _fix_loop_state(
            unregistered_commits={"agent-a": ["abc1234"], "": ["def5678"]}
        )
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" '
                    "transition fix_commit BH-101"
                )
            },
            "tool_response": {"exit_code": 0, "stdout": "ok", "stderr": ""},
            "cwd": str(tmp_path),
        }

        _run_hook(TRACKER, event)

        assert mock_daemon.state["unregistered_commits"] == {}


def test_the_status_line_counts_the_whole_run(mock_daemon, tmp_path):
    """The primer reports the run, so its count spans every actor's bucket."""
    import importlib.util

    path = str(REPO_ROOT / "enforcement" / "hooks" / "_protocol_cache.py")
    spec = importlib.util.spec_from_file_location("_protocol_cache_uca", path)
    assert spec and spec.loader
    cache_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cache_mod)

    # Three commits across two buckets. Equal numbers would let a count of
    # buckets pass, which is exactly what `len()` over the keyed dict does.
    cache = _fix_loop_state(
        unregistered_commits={"agent-a": ["a1", "a2"], "": ["b1"]}
    )

    assert "3 pending commits" in cache_mod.format_state_line(cache)


def test_the_deny_message_still_counts_this_actors_commits(mock_daemon, tmp_path):
    """The number in the block is the actor's own, not the run's."""
    # Three commits for agent-b against two buckets, so a message that counted
    # buckets — which is what `len()` over the keyed dict would do — reads 2
    # and fails here. Equal numbers would have let the old code pass.
    mock_daemon.state = _fix_loop_state(
        unregistered_commits={"agent-a": ["a1"], "agent-b": ["b1", "b2", "b3"]}
    )

    reason = _blocked(_run_hook(COMMIT_GATE, _commit_event(str(tmp_path), "agent-b")))

    assert reason is not None
    assert "3 unregistered" in reason, reason

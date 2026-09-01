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

The clear is keyed too, and by the ledger rather than the cache (item 32). It
used to stay run-global on the argument that `fix_commit` registers the commit
at `HEAD`, and that after a fast-forward that commit belongs to whichever
subagent authored it — which the transition cannot know. The *cache* cannot;
`fix_commit` auto-emits `finding_resolved` stamped with that hash, so the
ledger names it. While it went unasked, one subagent's registration discharged
every sibling's charge.

Both halves are needed and neither substitutes for the other. A mock daemon has
no ledger, so every mock-driven `fix_commit` takes the unanswerable-ledger
fallback — worth pinning, but it pins nothing about the rule. The rule itself is
only observable against a real ledger, which is what the F2 class below drives.

Driven by subprocess throughout — the interface Claude Code actually uses, and
the only one that cannot be poisoned by another test's import of a same-named
module. Against a real daemon that is not merely good practice: it refuses
`enforcement_write` from a test process (`auth_failed`, reason
`pid_resolution_failed`), so the buckets can only be seeded through the tracker
and read back through the gate.
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


def _transition_event(cwd: str, exit_code: int = 0, cmd: str | None = None) -> dict:
    """A PostToolUse event for the orchestrator's `fix_commit` transition."""
    return {
        "tool_name": "Bash",
        "tool_input": {
            "command": cmd or (
                'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" '
                "transition fix_commit BH-101"
            )
        },
        "tool_response": {"exit_code": exit_code, "stdout": "ok", "stderr": ""},
        "cwd": cwd,
    }


#: Three actors, three commits, one commit each: no two of "buckets",
#: "commits" and "actors" can coincide, so no assertion below passes by
#: counting the wrong one. The hashes are real 7-hex abbreviations because
#: that is what `git commit` prints and what the ledger stamps.
THREE_BUCKETS: dict[str, list[str]] = {
    "agent-a": ["a111111"],
    "agent-b": ["b222222"],
    "": ["c333333"],
}


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

    def test_fix_commit_discharges_the_orchestrator_when_the_ledger_is_silent(
        self, mock_daemon, tmp_path
    ):
        """The clear's scope now comes from the ledger — or, failing that, here.

        Rewritten rather than deleted: it was the guard for the run-global
        clear, and it is the guard for the rule that replaced it. Against a
        mock daemon there is no ledger to ask, which is exactly the branch
        this pins — the transition registered *something*, nothing can say
        which bucket held it, so only the actor who ran the transition is
        discharged. Losing a clear costs a nudge; losing a charge loses the
        gate, so the unanswerable case fails towards keeping the charge.
        """
        mock_daemon.state = _fix_loop_state(
            unregistered_commits={"agent-a": ["abc1234"], "": ["def5678"]}
        )

        _run_hook(TRACKER, _transition_event(str(tmp_path)))

        assert mock_daemon.state["unregistered_commits"] == {"agent-a": ["abc1234"]}


class TestARefusedTransitionDischargesNothing:
    """The clear reads the engine's answer, not the command's text.

    `_runs_transition` is pure token adjacency, and the branch it guarded
    ignored `exit_code` — which is computed two lines away and honoured by the
    git-commit branch immediately above it. A `fix_commit` the engine refuses
    registers no commit, so it must discharge none.
    """

    def test_a_refused_fix_commit_clears_nothing(self, mock_daemon, tmp_path):
        mock_daemon.state = _fix_loop_state(unregistered_commits=dict(THREE_BUCKETS))

        _run_hook(TRACKER, _transition_event(str(tmp_path), exit_code=1))

        assert mock_daemon.state["unregistered_commits"] == THREE_BUCKETS

    def test_a_line_that_merely_names_the_transition_clears_nothing(
        self, mock_daemon, tmp_path
    ):
        """A real sahjhan line whose *text* also spells the verb.

        `echo remember to run transition fix_commit` on its own never reaches
        this branch — it invokes no sahjhan subcommand. Wrapped onto one that
        does, it did: the scan splits the whole line on whitespace, so the
        echoed words are indistinguishable from the ones that ran. Nothing was
        registered, so nothing may be discharged.
        """
        mock_daemon.state = _fix_loop_state(unregistered_commits=dict(THREE_BUCKETS))

        _run_hook(TRACKER, _transition_event(
            str(tmp_path),
            cmd='sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" status '
                "&& echo remember to run transition fix_commit",
        ))

        assert mock_daemon.state["unregistered_commits"] == THREE_BUCKETS

    def test_a_bare_reminder_clears_nothing(self, mock_daemon, tmp_path):
        """The same words with no sahjhan command under them.

        Pinned even though it is safe for a reason of its own: a line that
        invokes no sahjhan subcommand never reaches this branch at all, so it
        is the wrapped form above that carries the risk. Keeping both means a
        future change that widens the entry condition cannot quietly re-admit
        the class through the door this one watches.
        """
        mock_daemon.state = _fix_loop_state(unregistered_commits=dict(THREE_BUCKETS))

        _run_hook(TRACKER, _transition_event(
            str(tmp_path), cmd="echo remember to run transition fix_commit",
        ))

        assert mock_daemon.state["unregistered_commits"] == THREE_BUCKETS

    def test_a_diagnostic_that_names_the_verb_in_its_sql_clears_nothing(
        self, mock_daemon, tmp_path
    ):
        """A read-only query is not the transition, however its text reads.

        This is the case `_runs_transition`'s docstring has always claimed to
        distinguish, and the only one where the words sit inside a genuine
        sahjhan invocation rather than beside one.

        The verb and the command are bare words *inside* the quotes, with a
        word after them: a closing quote riding on `fix_commit` would make the
        old adjacency scan miss this for a reason that has nothing to do with
        quoting, and the test would pin nothing.
        """
        mock_daemon.state = _fix_loop_state(unregistered_commits=dict(THREE_BUCKETS))

        _run_hook(TRACKER, _transition_event(
            str(tmp_path),
            cmd='sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" query '
                '"SELECT count(*) FROM events WHERE type=\'state_transition\' '
                '-- counts every transition fix_commit so far"',
        ))

        assert mock_daemon.state["unregistered_commits"] == THREE_BUCKETS


@pytest.mark.slow
class TestTheLedgerDecidesWhichBucketIsDischarged:
    """Against a real ledger, the discharge names the commit it discharges.

    D41 keyed the *charge* per actor and left the *clear* run-global, arguing
    that a transition registering `HEAD` cannot name the author of a commit
    that reached `HEAD` by fast-forward. The cache indeed cannot say — but the
    ledger can, and it always could: `fix_commit` auto-emits `finding_resolved`
    with `commit_hash` stamped from `git rev-parse --short=7 HEAD`. So the
    question was never unanswerable, only unasked, and one subagent's
    registration was granting the other two a free unregistered commit each.

    Driven end to end against a real daemon because that is the only place the
    question has an answer: a mock has no ledger, and a test that stubbed one
    would be asserting against its own fixture.
    """

    def _seed_three_buckets(self, actors) -> None:
        """One commit per actor, charged the way `git commit` charges them."""
        for actor, commit_hash in (
            ("agent-a", "a111111"), ("agent-b", "b222222"), ("", "c333333"),
        ):
            actors.git_commit(actor, commit_hash)

    def test_the_charge_lands_per_actor_before_anything_is_discharged(
        self, two_actors
    ):
        """The precondition, asserted rather than assumed.

        Without this, a discharge test passes whenever the seeding silently
        failed — every actor unblocked, for the wrong reason.
        """
        self._seed_three_buckets(two_actors)

        assert two_actors.charges("agent-a", "agent-b", "") == {
            "agent-a": 1, "agent-b": 1, "": 1,
        }

    def test_a_successful_fix_commit_discharges_only_the_commit_it_registered(
        self, two_actors
    ):
        """V4, by name: agent-a's registration is not agent-b's discharge."""
        self._seed_three_buckets(two_actors)
        two_actors.sibling_fix_commit("BH-101", commit_hash="a111111")

        two_actors.fix_commit_transition("BH-101")

        assert two_actors.charges("agent-a", "agent-b", "") == {
            "agent-a": None, "agent-b": 1, "": 1,
        }

    def test_a_commit_the_ledger_never_registered_stays_charged(self, two_actors):
        """The other direction: a resolution names one commit, not any commit.

        The registered hash belongs to no bucket here — the shape a rebase
        produces, since rebasing rewrites the hash the tracker charged. The
        answer must be "discharge nothing", not "discharge the nearest thing".
        """
        self._seed_three_buckets(two_actors)
        two_actors.sibling_fix_commit("BH-101", commit_hash="9999999")

        two_actors.fix_commit_transition("BH-101")

        assert two_actors.charges("agent-a", "agent-b", "") == {
            "agent-a": 1, "agent-b": 1, "": 1,
        }

    def test_a_refused_transition_discharges_nothing_against_a_real_ledger(
        self, two_actors
    ):
        """V2 again, where the ledger *could* have answered and must not be asked."""
        self._seed_three_buckets(two_actors)
        two_actors.sibling_fix_commit("BH-101", commit_hash="a111111")

        two_actors.fix_commit_transition("BH-101", exit_code=1)

        assert two_actors.charges("agent-a", "agent-b", "") == {
            "agent-a": 1, "agent-b": 1, "": 1,
        }


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

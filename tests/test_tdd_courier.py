"""Tests for tdd_courier.py — the channel that names the actor behind a
`test_failed_before_fix`.

P0.3's defect is that the fix-loop TDD gate is run-global: with two agents
working, each one's source edit is authorised by the other's failing test, so
the loop can only run 1-wide. Scoping the gate needs an actor on the ledger,
and the actor cannot be an agent-stated field — Claude Code puts `agent_id` on
the hook event, not into the model's context.

So the question these tests are organised around is the one that matters for a
courier: *which fields can the agent influence?*

  agent_id                — the hook payload only. This is the whole point.
  finding_id / test_name  — re-read from the ledger row, never parsed out of
  run / auditor             the command text the agent typed.

Plus the two refusals that keep it honest: a chained Bash line must not ride
the one command whose success becomes a ledger entry, and a replayed line must
not mint evidence for work already paired.
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import tdd_courier  # noqa: E402
from test_sahjhan_integration import run_enforcement_hook  # noqa: E402

RECORD = (
    'sahjhan --config-dir "$CLAUDE_PLUGIN_ROOT/enforcement" '
    "event test_failed_before_fix --field finding_id=BH-101 "
    "--field test_name=test_thing"
)


def _event(command: str, *, exit_code: int = 0, agent_id: str | None = None) -> dict:
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"exit_code": exit_code, "stdout": "", "stderr": ""},
        "cwd": REPO_ROOT,
    }
    if agent_id is not None:
        event["agent_id"] = agent_id
    return event


class TestWhichCommandsItClaims:
    """The trigger has to be exactly the recording command, and only it."""

    def test_it_claims_the_canonical_recording_command(self):
        assert tdd_courier._records_a_failing_test(RECORD)

    def test_a_bare_invocation_is_claimed_too(self):
        assert tdd_courier._records_a_failing_test(
            "sahjhan event test_failed_before_fix --field finding_id=BH-101"
        )

    @pytest.mark.parametrize(
        "command",
        [
            f"{RECORD} && rm -rf /",
            f"{RECORD}; echo done",
            f"echo before && {RECORD}",
            f"{RECORD} | tee log",
        ],
    )
    def test_a_chained_line_is_refused(self, command):
        """Arbitrary work must not ride the one Bash line whose success this
        hook converts into a ledger entry."""
        assert not tdd_courier._records_a_failing_test(command)

    @pytest.mark.parametrize(
        "command",
        [
            "sahjhan event finding --field id=BH-101",
            "sahjhan event fix_start --field finding_id=BH-101",
            "sahjhan transition fix_commit -- BH-101",
            "sahjhan status",
            "pytest tests/",
            "echo test_failed_before_fix",
        ],
    )
    def test_another_command_is_not_claimed(self, command):
        assert not tdd_courier._records_a_failing_test(command)


class TestWhatItRefusesToRecord:
    """Every refusal warns rather than passing silently: nothing was recorded,
    so the next source edit will block with no obvious link to this moment."""

    @pytest.mark.hook_e2e
    def test_a_non_bash_tool_is_ignored(self):
        event = {"tool_name": "Edit", "tool_input": {"file_path": "a.py"}, "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("tdd_courier.py", event)
        assert code == 0, output

    @pytest.mark.hook_e2e
    def test_an_unrelated_command_is_ignored(self):
        code, output, _ = run_enforcement_hook(
            "tdd_courier.py", _event("pytest tests/")
        )
        assert code == 0, output

    @pytest.mark.hook_e2e
    def test_a_failed_command_records_nothing(self):
        """The host says it failed, so there is no new evidence to attribute."""
        code, output, _ = run_enforcement_hook(
            "tdd_courier.py", _event(RECORD, exit_code=1)
        )
        assert code == 0, output
        assert "tdd_evidence" not in str(output)


class TestTheActorComesFromTheHost:
    """The load-bearing property. `event_actor` reads the hook payload, which
    the agent's shell does not write."""

    def test_a_subagent_is_its_own_actor(self):
        from _protocol_cache import event_actor

        assert event_actor(_event(RECORD, agent_id="agent-A")) == "agent-A"

    def test_the_orchestrator_is_the_empty_actor_not_a_wildcard(self):
        """`None` must become a real bucket. A wildcard here would let the
        orchestrator inherit any subagent's evidence, which is the run-global
        behaviour P0.3 exists to remove."""
        from _protocol_cache import event_actor

        assert event_actor(_event(RECORD)) == ""

    def test_the_command_text_cannot_name_the_actor(self):
        """An agent typing `--field agent_id=someone-else` must not reach the
        evidence row: the courier reads the ledger and the payload, never the
        command."""
        from _protocol_cache import event_actor

        forged = _event(
            f"{RECORD} --field agent_id=agent-B", agent_id="agent-A"
        )
        assert event_actor(forged) == "agent-A"
        # …and the forged line is not even claimed, because the courier's own
        # trigger check is on the parsed subcommand, not on the fields.
        assert tdd_courier._records_a_failing_test(
            forged["tool_input"]["command"]
        )


class TestTheQueryPairsEvidenceToWork:
    """The query is what stops a replayed Bash line minting a second evidence
    row for work already attributed — and, since item 19, what stops one
    actor's courier attributing another actor's row.

    `test_it_takes_the_newest_unpaired_row` used to live here, asserting
    `ORDER BY seq DESC LIMIT 1` against the SQL string. It was asserting the
    defect as intended behaviour: taking the newest row *on the whole ledger*
    is exactly how agent-A's courier came to stamp agent-B's finding. It is
    replaced by the behavioural tests in `test_tdd_courier_pairing.py`, not by
    a string match on the new SQL — a string match would reproduce the same
    mistake one revision later, since it tests what the query says rather than
    what it selects.
    """

    def test_it_floors_on_this_findings_last_evidence_row(self):
        """The watermark is per-finding, not run-global.

        A run-global `MAX(seq)` means any actor's evidence row retires every
        other actor's unpaired record.
        """
        sql = tdd_courier.unpaired_sql("BH-101")
        assert (
            "MAX(seq) FROM events WHERE type='tdd_evidence' "
            "AND finding_id='BH-101'"
        ) in sql

    def test_it_reads_only_the_agent_written_event(self):
        assert "type='test_failed_before_fix'" in tdd_courier.unpaired_sql("BH-101")

    def test_both_halves_are_keyed_on_the_same_finding(self):
        """One id, two places. Keyed on one and not the other, the courier
        would select the right row and then floor it on everyone's."""
        assert tdd_courier.unpaired_sql("BH-101").count("finding_id='BH-101'") == 2

    def test_it_selects_no_field_the_agent_could_redirect(self):
        """Every field the courier writes except `agent_id` comes from this
        query or from the tree — none from the command text.

        `finding_id` is now *also* read off the command, to choose which row to
        select. It is still written from the selected row, so a mismatch
        selects nothing rather than mis-attributing.
        """
        sql = tdd_courier.unpaired_sql("BH-101")
        for field in ("finding_id", "test_name", "run", "auditor", "project"):
            assert field in sql, field
        assert "agent_id" not in sql

    def test_the_id_comes_from_a_closed_character_set(self):
        """`query_ledger` takes a statement, not bound parameters.

        So the only thing making interpolation safe is that the id was
        pattern-matched first. Assert the refusal, not just the acceptance.
        """
        assert tdd_courier._finding_id_of(
            "sahjhan event test_failed_before_fix --field finding_id=BH-101"
        ) == "BH-101"
        for hostile in (
            "--field finding_id=BH-101'; DROP TABLE events;--",
            "--field finding_id=../../etc",
            "--field finding_id=BH-1",
            "--field finding_id=XX-101",
        ):
            assert tdd_courier._finding_id_of(hostile) is None, hostile
        with pytest.raises(ValueError):
            tdd_courier.unpaired_sql("BH-101' OR '1'='1")

    def test_the_courier_needs_nothing_from_the_working_tree(self):
        """`project` comes from the ledger row, not from a git call.

        An earlier draft named the project from `repo_root(cwd)`, which made
        the courier refuse outside a git tree — the failure surfaced as a gate
        that never opened, with the evidence silently never written.
        """
        with open(tdd_courier.__file__, encoding="utf-8") as fh:
            source = fh.read()
        assert "repo_root" not in source

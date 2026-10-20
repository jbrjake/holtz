"""W04 / items 19 + 1 — the fix loop's two independent breaks, driven.

Both are about the same thing from opposite ends: **which actor is authorised
to edit source right now**. 19 is the courier writing the wrong actor's row; 1
is the gate discarding the right actor's row. 19 fires first — before any
`fix_commit` exists to revoke anything — so one fixture drives both.

Everything here is behavioural. The tests these replace asserted the SQL
*string* (`"ORDER BY seq DESC LIMIT 1" in _UNPAIRED`), which is how the defect
shipped as intended behaviour: the string was correct about what the query
said and silent about what it selected.

Every claim is positive and per-actor. `len(rows) == 2` and
`a_finding != b_finding` are what let items 19 and 32 through — an inequality
passes when the code lands on a third wrong answer, and a count passes when two
quantities coincide.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from two_actors import DEFAULT_SEEDING, ORCHESTRATOR, record_command  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.hook_e2e]


def _decision(out: dict) -> str | None:
    return out.get("hookSpecificOutput", {}).get("permissionDecision")


class TestItem19EvidencePairsByRow:
    """V1/V3 — each actor's evidence names that actor's own finding."""

    def test_each_actors_evidence_names_its_own_finding(self, two_actors):
        """V1 — the concurrent ordering, which is where this breaks.

        Every record lands before any courier runs, as a three-wide dispatch
        produces. Before this fix, `agent-a`'s courier stamped `BH-104` — the
        newest unpaired row on the whole ledger.
        """
        two_actors.seed_concurrently()
        two_actors.run_couriers()

        by_actor: dict[str, set[str]] = {}
        for actor, finding_id, _test in DEFAULT_SEEDING:
            by_actor.setdefault(actor, set()).add(finding_id)

        for actor, expected in by_actor.items():
            got = {r["finding_id"] for r in two_actors.evidence_for(actor)}
            assert got == expected, (
                f"{actor or '<orchestrator>'} expected {sorted(expected)}, "
                f"got {sorted(got)}"
            )

    def test_the_test_name_travels_with_the_finding(self, two_actors):
        """The courier still invents nothing — every field is off the row.

        A pairing fix that got `finding_id` right by reading the command text
        and left `test_name` coming from the wrong row would pass the test
        above.
        """
        two_actors.seed_concurrently()
        two_actors.run_couriers()
        expected = {f: t for _a, f, t in DEFAULT_SEEDING}
        for row in two_actors.evidence_rows():
            assert row["test_name"] == expected[row["finding_id"]], row

    def test_no_row_is_lost(self, two_actors):
        """V3 — two unpaired rows for one actor, two couriers, two rows out.

        `LIMIT 1` over a run-global watermark dropped the older row for good.
        `agent-a` holds two rows in the default seeding precisely so this is
        expressible.
        """
        two_actors.seed_concurrently()
        two_actors.run_couriers()
        assert len(two_actors.evidence_rows()) == len(DEFAULT_SEEDING)
        assert {r["finding_id"] for r in two_actors.evidence_rows()} == {
            f for _a, f, _t in DEFAULT_SEEDING
        }

    def test_a_replayed_line_mints_nothing(self, two_actors):
        """The property the old watermark existed for, kept.

        A fix that scoped the watermark per-finding but dropped it would let
        every replay mint another row.
        """
        two_actors.seed_concurrently()
        two_actors.run_couriers()
        before = len(two_actors.evidence_rows())
        actor, finding_id, test_name = DEFAULT_SEEDING[0]
        two_actors.courier(actor, finding_id, test_name)
        assert len(two_actors.evidence_rows()) == before

    def test_an_actor_cannot_ride_a_siblings_unpaired_row(self, two_actors):
        """The gate-bypass half of item 19, stated as its own claim.

        `agent-b` replaying `agent-a`'s command text must not produce evidence
        naming `agent-b`. Before the fix, any actor's courier took whatever
        unpaired row was newest, so this is exactly how A could edit source
        having recorded nothing.
        """
        two_actors.seed_concurrently()
        a_actor, a_finding, a_test = DEFAULT_SEEDING[0]
        two_actors.courier("agent-b", a_finding, a_test)

        b_rows = two_actors.evidence_for("agent-b")
        assert [r["finding_id"] for r in b_rows] == [a_finding], (
            "the row is attributed to whoever ran the Bash line, which is "
            "correct — the actor is host-attested. What must not happen is "
            f"agent-b acquiring evidence for a finding it never recorded: {b_rows}"
        )
        # …and agent-a's own row is now consumed, so A gets nothing later.
        two_actors.courier(a_actor, a_finding, a_test)
        assert two_actors.evidence_for(a_actor) == []


class TestItem1TheWindowIsScopedToTheActor:
    """V4/V5 — a sibling's commit must not revoke this actor's authorisation."""

    def _authorise(self, two_actors, actor: str, finding_id: str, test_name: str):
        two_actors.record(finding_id, test_name)
        two_actors.courier(actor, finding_id, test_name)

    def test_an_actor_survives_a_siblings_fix_commit(self, two_actors):
        """V4 — record -> edit(allow) -> sibling fix_commit -> edit(allow).

        Observed before this fix: the second edit returned deny.
        """
        self._authorise(two_actors, "agent-a", "BH-101", "test_alpha")
        assert _decision(two_actors.edit("agent-a")) in (None, "allow")

        two_actors.sibling_fix_commit("BH-102")

        assert _decision(two_actors.edit("agent-a")) in (None, "allow"), (
            "a sibling's commit revoked this actor's own authorisation"
        )

    def test_the_gate_still_bites(self, two_actors):
        """V5 — an actor with no evidence is denied, before and after.

        A window fix that allows everyone is worse than the bug.
        """
        assert _decision(two_actors.edit("agent-b")) == "deny"
        self._authorise(two_actors, "agent-a", "BH-101", "test_alpha")
        two_actors.sibling_fix_commit("BH-102")
        assert _decision(two_actors.edit("agent-b")) == "deny"

    def test_an_actors_own_commit_consumes_its_authorisation(self, two_actors):
        """The window has to close, or the gate stops being per-fix.

        `fix_commit BH-NNN` auto-emits `finding_resolved` for that id, so the
        actor's own evidence is consumed by its own commit and by nothing else.
        """
        self._authorise(two_actors, "agent-a", "BH-101", "test_alpha")
        assert _decision(two_actors.edit("agent-a")) in (None, "allow")

        two_actors.sibling_fix_commit("BH-101")

        assert _decision(two_actors.edit("agent-a")) == "deny", (
            "this actor's own commit must close its window; otherwise one "
            "failing test authorises every later edit by that actor"
        )

    def test_the_orchestrator_is_an_actor_not_a_wildcard(self, two_actors):
        """The empty-string actor gets the same treatment as a named one."""
        assert _decision(two_actors.edit(ORCHESTRATOR)) == "deny"
        self._authorise(two_actors, ORCHESTRATOR, "BH-103", "test_gamma")
        assert _decision(two_actors.edit(ORCHESTRATOR)) in (None, "allow")
        assert _decision(two_actors.edit("agent-a")) == "deny"

    def test_a_test_file_edit_is_still_exempt(self, two_actors):
        """Step 2 of the taught sequence writes the failing test *before*
        recording it, so `tests/**` must stay outside the gate."""
        assert _decision(
            two_actors.edit("agent-b", path=os.path.join("tests", "test_x.py"))
        ) in (None, "allow")


class TestTheCommandMustNameItsFinding:
    def test_a_command_without_a_finding_id_warns(self, two_actors):
        """Silence is the failure mode this hook exists to avoid.

        The engine already refuses such a command, but the host can still
        report success for a line that only looks like the recording command —
        and the block that follows will not explain itself.
        """
        out = two_actors.hook("tdd_courier.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan event test_failed_before_fix "
                                      "--field test_name=t --field project=holtz "
                                      "--field run=1 --field auditor=holtz"},
            "tool_response": {"exit_code": 0, "stdout": "", "stderr": ""},
            "agent_id": "agent-a",
        })
        assert "finding_id" in str(out), out
        assert two_actors.evidence_rows() == []

    def test_the_canonical_command_still_carries_one(self):
        """The form W03 teaches must satisfy the parser this fix added."""
        import tdd_courier

        assert tdd_courier._finding_id_of(
            record_command("BH-101", "test_alpha")
        ) == "BH-101"

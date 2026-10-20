"""F2-V — the two-actor fixture can name an actor's own row, positively.

What is being validated here is the *fixture*: that it drives the concurrent
ordering a three-wide dispatch produces, and that a test written on it can state
"A's evidence row names A's finding" as a claim about a value rather than as a
count or an inequality.

At `17e648e` this file also recorded item 19 as observed; that assertion was
rewritten in place when W04 landed, and its history is in its docstring.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from two_actors import DEFAULT_SEEDING, ORCHESTRATOR  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.hook_e2e]


class TestTheFixtureDrivesTheLoopsOrdering:
    def test_every_record_lands_before_any_courier(self, two_actors):
        """The concurrent ordering, asserted on the ledger rather than assumed."""
        two_actors.seed_concurrently()
        recorded = two_actors.findings_recorded()
        assert [r["finding_id"] for r in recorded] == [
            f for _a, f, _t in DEFAULT_SEEDING
        ], recorded
        assert two_actors.evidence_rows() == [], (
            "no courier has run yet, so no evidence may exist"
        )

    def test_the_counts_a_careless_assertion_would_confuse_are_unequal(self):
        """Actors and rows must not give the same number.

        A `len()` over the wrong dimension is how item 32's guard test passed
        while the code was wrong; this fixture is built so that cannot happen
        by coincidence.
        """
        actors = {a for a, _f, _t in DEFAULT_SEEDING}
        assert len(actors) == 3
        assert len(DEFAULT_SEEDING) == 4
        assert ORCHESTRATOR in actors, "the orchestrator is an actor, not a wildcard"


class TestItCanNameAnActorsOwnRow:
    def test_evidence_for_returns_rows_keyed_by_actor(self, two_actors):
        """The accessor exists and discriminates — the pass criterion."""
        two_actors.seed_concurrently()
        two_actors.run_couriers()

        rows = two_actors.evidence_rows()
        assert rows, "the courier wrote nothing; every assertion below would be vacuous"

        actors = {actor for actor, _f, _t in DEFAULT_SEEDING}
        assert actors >= {"agent-a", "agent-b", ORCHESTRATOR}
        for actor in actors:
            for row in two_actors.evidence_for(actor):
                assert (row.get("agent_id") or "") == actor

    def test_the_courier_pairs_by_row(self, two_actors):
        """The fixture's whole reason for existing, as one claim.

        At `17e648e` this test asserted the defect: `_UNPAIRED` selected the
        newest unpaired `test_failed_before_fix` on the *whole ledger*, so with
        every record landing before any courier — which is what a three-wide
        dispatch produces — the first courier to fire took the last row
        written, `BH-104`. W04 keyed both halves of the query on the finding
        the command names, and this now asserts the correct value.

        The seeding is what makes the claim discriminating: `BH-101` is the
        first row and `BH-104` the newest, so "its own" and "the newest" are
        different answers. The exhaustive per-actor version lives in
        `test_tdd_courier_pairing.py`.
        """
        two_actors.seed_concurrently()
        first_actor, first_finding, first_test = DEFAULT_SEEDING[0]
        newest_recorded = DEFAULT_SEEDING[-1][1]
        assert first_finding != newest_recorded, "the seeding must make these differ"

        two_actors.courier(first_actor, first_finding, first_test)

        rows = two_actors.evidence_for(first_actor)
        assert len(rows) == 1, rows
        assert rows[0]["finding_id"] == first_finding, rows[0]
        assert rows[0]["test_name"] == first_test, rows[0]

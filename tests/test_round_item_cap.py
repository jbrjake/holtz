"""P0.2's round cap and its close-as-many-as-you-open obligation (D7).

A pattern round's job is to find siblings, and the audited run's rounds did it
so well that the board rose 124 -> 273 and the run could not terminate. The
clause caps a round at **3 new items** and obliges it to **close or merge at
least as many as it opens**.

Both halves needed an escape that could not exist before this: a filing cannot
be withdrawn from an append-only ledger, so a cap counting *filings* is
unclearable the moment a fourth sibling lands — a block naming an impossible
act, which is #77 from a new direction. The cap therefore counts the round's
findings that are still **open**, and `merge_finding` is the act that brings
the count back down: this sibling is a duplicate of that finding, so the work
is tracked there and this id closes.

`merge_finding` is declared from `fix_loop` **and** `pattern_analysis` because
the two gates sit in different states, and a block must name a command
reachable from its own side. That is the property the tests below spend most
of their time on: asserting the SQL proves the block, and only driving the
named command proves the way out.

Driven end to end against a real daemon, because a restricted
`pattern_analysis_complete` reaches a ledger no other way. Every predicate is
read out of `protocol.toml` rather than restated, so editing the config
re-tests the config.
"""
from __future__ import annotations

import json
import os
import sys
import tomllib

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_amplification_breaker import _named_query, _Run  # noqa: E402,F401

pytestmark = [pytest.mark.slow, pytest.mark.integration]


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


def _blocked_on(out, query_name):
    """Whether `gate check`'s line for one named query carries the ✗.

    Keyed on the query *name* and not on the intent prose: the name is the
    object both the gate and the block message reference, so an assertion on
    it survives a reworded intent and fails on a re-pointed gate. Asserting
    only that some ✗ appears would pass on any unrelated failing conjunct —
    `pattern_done` normally has one.
    """
    lines = [ln.strip() for ln in out.splitlines() if f"'{query_name}'" in ln]
    assert len(lines) == 1, f"expected one line naming {query_name}, got {lines}\n{out}"
    return lines[0].startswith("✗")


def _seed(run):
    """`pattern_round.py` refuses on a ledger where no event names a run, so a
    round can never be the first thing written. This finding carries no
    `pattern_id`, so it is in no round's population."""
    run.file("BH-001")


def _round_with_siblings(run, ids, pattern_id="PAT-001"):
    """The shape of a real round: siblings filed at Step 11.2, recorded at 11.6.

    A first round has to exist before them so the window under test is the
    *second* round's — which is also the only arrangement in which the floor
    (the second-most-recent round) is not simply the run start.
    """
    _seed(run)
    run.round()
    for finding_id in ids:
        run.file(finding_id, pattern_id=pattern_id)
    run.round()


class TestTheCapCountsTheRoundsOwnOpenItems:
    """Which findings a round is charged for, and which it is not."""

    def test_four_open_siblings_is_over_the_cap(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103", "BH-104"])
        assert run.answer("round_item_cap_exceeded") == "true"

    def test_three_is_not(self, run):
        """Non-vacuity: the cap is not simply always exceeded."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        assert run.answer("round_item_cap_exceeded") == "false"

    def test_closing_one_brings_a_fourth_back_under(self, run):
        """The property the escape rests on — the count is of *open* items."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103", "BH-104"])
        assert run.answer("round_item_cap_exceeded") == "true"

        run.resolve("BH-104")
        assert run.answer("round_item_cap_exceeded") == "false"

    def test_findings_with_no_pattern_id_are_not_the_rounds(self, run):
        """Step 13's blast-radius items land in the same window.

        Charging the round for them would block it for work it did not do.
        """
        _seed(run)
        run.round()
        for finding_id in ("BH-201", "BH-202", "BH-203", "BH-204"):
            run.file(finding_id)
        run.round()
        assert run.answer("round_item_cap_exceeded") == "false"

    def test_a_pattern_id_no_round_ever_wrote_does_not_count(self, run):
        """The population joins to the courier-derived `pattern_ids` (D6).

        A PAT the brief never got is not a round's output, whatever the
        finding claims.
        """
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for finding_id in ("BH-101", "BH-102", "BH-103", "BH-104"):
            run.file(finding_id, pattern_id="PAT-777")
        run.round(pat_ids=["PAT-001"])
        assert run.answer("round_item_cap_exceeded") == "false"

    def test_an_earlier_rounds_siblings_are_not_charged_to_this_one(self, run):
        """The window floor is the *previous* round, not the run start.

        Four filed in round one and four in round two is over the cap twice
        over if the window never moves, and correct only if it does.
        """
        _seed(run)
        run.round()
        for finding_id in ("BH-101", "BH-102", "BH-103", "BH-104"):
            run.file(finding_id, pattern_id="PAT-001")
        run.round()
        assert run.answer("round_item_cap_exceeded") == "true"

        run.round()
        assert run.answer("round_item_cap_exceeded") == "false", (
            "round three is charged for round two's findings — the window "
            "floor is not moving with the rounds"
        )


class TestTheCapBlocksTheRoundsExit:
    def test_pattern_done_is_blocked_over_the_cap(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103", "BH-104"])
        run.enter_pattern_analysis()
        out = run.gate_check()
        assert _blocked_on(out, "round_item_cap_exceeded"), out

    def test_the_block_names_the_command_that_clears_it(self, run):
        """An escape the agent cannot read is a deadlock with extra steps."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103", "BH-104"])
        run.enter_pattern_analysis()
        assert "merge_finding" in run.gate_check()

    def test_a_round_at_the_cap_is_not_blocked(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        run.enter_pattern_analysis()
        out = run.gate_check()
        assert not _blocked_on(out, "round_item_cap_exceeded"), out


class TestTheEscapeIsReachableFromTheBlockedState:
    """`pattern_analysis` cannot reach `fix_commit`, so closing needs a merge."""

    def test_merge_finding_is_declared_from_both_states(self):
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        states = {t["from"] for t in transitions if t["command"] == "merge_finding"}
        assert {"fix_loop", "pattern_analysis"} <= states, (
            f"merge_finding is only declared from {sorted(states)} — one of "
            f"D7's two blocks names an escape the run cannot reach from where "
            f"it is standing"
        )

    def test_the_merge_clears_the_block_from_inside_a_round(self, run):
        """The whole design turns on this: the named command, from the blocked
        state, against the real transitions."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103", "BH-104"])
        run.enter_pattern_analysis()
        assert _blocked_on(run.gate_check(), "round_item_cap_exceeded")

        result = run.merge("BH-104", "BH-101", check=False)
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

        out = run.gate_check()
        assert not _blocked_on(out, "round_item_cap_exceeded"), (
            f"the named escape ran and the cap did not clear:\n{out}"
        )


class TestMergeFinding:
    """The primitive itself: what it records, and what it refuses."""

    def test_it_records_the_resolution_and_names_the_target(self, run):
        run.file("BH-101")
        run.file("BH-102")
        run.merge("BH-102", "BH-101")

        rows = json.loads(run.sah(
            "query",
            "SELECT id, merged_into FROM events WHERE type='finding_resolved'",
            "--format", "json").stdout)
        assert rows == [{"id": "BH-102", "merged_into": "BH-101"}], rows

    def test_a_merged_finding_is_closed(self, run):
        run.file("BH-101")
        run.file("BH-102")
        run.merge("BH-102", "BH-101")
        assert run.answer("all_findings_closed") == "1", (
            "a merge must close the item everywhere a close is counted — "
            "otherwise 'close or merge' is two facts and they will disagree"
        )

    def test_merging_into_a_finding_that_does_not_exist_is_refused(self, run):
        run.file("BH-101")
        result = run.merge("BH-101", "BH-999", check=False)
        assert result.returncode != 0, result.stdout

    def test_a_finding_cannot_be_merged_into_itself(self, run):
        """Otherwise one command closes any finding for free, and the cap and
        the obligation are both defeated by typing the same id twice."""
        run.file("BH-101")
        result = run.merge("BH-101", "BH-101", check=False)
        assert result.returncode != 0, result.stdout
        assert run.answer("all_findings_closed") == "1", (
            "the self-merge was refused but something still closed the finding"
        )

    def test_an_already_closed_finding_cannot_be_merged(self, run):
        run.file("BH-101")
        run.file("BH-102")
        run.resolve("BH-102")
        result = run.merge("BH-102", "BH-101", check=False)
        assert result.returncode != 0, result.stdout

    def test_the_target_may_already_be_closed(self, run):
        """The common case: the duplicate is not reproducible *because* the
        finding it repeats was already fixed."""
        run.file("BH-101")
        run.file("BH-102")
        run.resolve("BH-101")
        result = run.merge("BH-102", "BH-101", check=False)
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


class TestTheObligation:
    """Close or merge at least as many as the round opens."""

    def test_a_round_that_closes_nothing_owes(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        assert run.answer("round_opens_exceed_closes") == "true"

    def test_closing_as_many_discharges_it(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        for finding_id in ("BH-101", "BH-102", "BH-103"):
            run.resolve(finding_id)
        assert run.answer("round_opens_exceed_closes") == "false", (
            "three opened and three closed is the obligation met, not broken"
        )

    def test_closing_one_short_still_owes(self, run):
        """Non-vacuity in the other direction — `>` and not `>=`."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        run.resolve("BH-101")
        run.resolve("BH-102")
        assert run.answer("round_opens_exceed_closes") == "true"

    def test_merges_count_as_closes(self, run):
        """"Close **or** merge" is one count, which is only true because
        `merge_finding` emits `finding_resolved`."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        run.merge("BH-102", "BH-101")
        run.merge("BH-103", "BH-101")
        run.resolve("BH-101")
        assert run.answer("round_opens_exceed_closes") == "false"

    def test_a_run_with_no_rounds_owes_nothing(self, run):
        """A run before its first round must not be blocked by a round's debt."""
        run.file("BH-101")
        run.file("BH-102")
        assert run.answer("round_opens_exceed_closes") == "false"
        assert run.answer("round_item_cap_exceeded") == "false"

    def test_the_boundary_is_blocked_while_it_owes(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        out = run.gate_check("iteration_boundary")
        assert _blocked_on(out, "round_opens_exceed_closes"), out

    def test_the_merge_clears_the_boundary_block(self, run):
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103"])
        assert _blocked_on(run.gate_check("iteration_boundary"),
                           "round_opens_exceed_closes")

        run.merge("BH-102", "BH-101")
        run.merge("BH-103", "BH-101")
        run.resolve("BH-101")

        out = run.gate_check("iteration_boundary")
        assert not _blocked_on(out, "round_opens_exceed_closes"), (
            f"the named escape ran and the obligation did not clear:\n{out}"
        )

    def test_the_cap_is_checked_at_the_boundary_too(self, run):
        """Step 11's *usual* path never enters `pattern_analysis`, so a cap
        that only gated `pattern_done` would leave the common path uncapped."""
        _round_with_siblings(run, ["BH-101", "BH-102", "BH-103", "BH-104"])
        out = run.gate_check("iteration_boundary")
        assert _blocked_on(out, "round_item_cap_exceeded"), out


class TestDeferralDoesNotPayTheObligation:
    """A deferred sibling leaves the *cap*, but does not discharge the debt.

    The two halves count different things on purpose. The cap asks what the
    round left open, so a deferral relieves it — the board really did shrink.
    The obligation asks what the round *closed or merged*, and D3/D5 keep
    deferral a budgeted act rather than a way of paying for work: if a deferred
    sibling paid the debt, D2's own escape (`defer batch --severity low,medium`)
    would settle every round it fired on.
    """

    def _round_of_lows(self, run):
        _seed(run)
        run.round()
        for finding_id in ("BH-101", "BH-102", "BH-103"):
            run.file(finding_id, severity="LOW", pattern_id="PAT-001")
        run.round()
        for finding_id in ("BH-101", "BH-102", "BH-103"):
            run.sah("transition", "defer_low", finding_id)

    def test_the_cap_is_relieved_by_a_deferral(self, run):
        _seed(run)
        run.round()
        for finding_id in ("BH-101", "BH-102", "BH-103", "BH-104"):
            run.file(finding_id, severity="LOW", pattern_id="PAT-001")
        run.round()
        assert run.answer("round_item_cap_exceeded") == "true"

        run.sah("transition", "defer_low", "BH-104")
        assert run.answer("round_item_cap_exceeded") == "false"

    def test_the_obligation_is_not(self, run):
        self._round_of_lows(run)
        assert run.answer("round_opens_exceed_closes") == "true", (
            "three deferrals paid a debt the clause says is discharged by "
            "closing or merging"
        )

    def test_the_run_still_has_a_door(self, run):
        """Escape by construction, checked where it is thinnest.

        Every one of the round's items is deferred, so none of them is a
        `merge_finding` argument any more, and merging the last open finding
        empties the board. That is the one state in which the obligation has
        no escape left at `iteration_boundary` — and the run is not wedged,
        because `set complete perspective` is a different door and no *ledger*
        gate on it is shut by any of this: deferred findings count as closed
        for `all_findings_closed`, and the round just run is not owed again.

        What is still ✗ there — the suite, the linter, a lens sweep — is the
        run's ordinary work, not a consequence of the deferral, so this asserts
        on the two named queries rather than on the absence of any ✗.
        """
        self._round_of_lows(run)
        run.merge("BH-001", "BH-101")           # the last open finding
        assert run.answer("all_findings_closed") == "0"
        assert _blocked_on(run.gate_check("iteration_boundary"),
                           "round_opens_exceed_closes")

        out = run.gate_check("set complete perspective")
        for query in ("all_findings_closed", "pattern_analysis_overdue"):
            assert not _blocked_on(out, query), (
                f"the obligation shut `iteration_boundary` and {query} shuts "
                f"the other door — a round whose items were deferred is "
                f"wedged:\n{out}"
            )

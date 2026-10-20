"""P0.2's backpressure conjunct: no round while >25 pattern-filed findings are open.

A pattern round exists to find siblings. Running one while the siblings from
earlier rounds are still open buys more board rather than less — the audited
run's 24 rounds cost 474 subagent-minutes and its open count never came down.
So past 25 open pattern-filed findings the obligation lapses, the same way it
lapses after two dry rounds, and the run is expected to fix what it has.

The population needed provenance that did not exist. Checked across every
archived ledger in this repo: `pattern_ids` names the PAT entries a round
appended and links to no finding; `predicted_by` holds a prediction index
(0-7) and never a PAT id; no finding has ever been filed at `step=11`; and
`siblings_found` is a per-round count with no ids. So `finding` gained an
optional `pattern_id`, taught in Step 11.2, and the conjunct joins it to the
rounds: an id counts only when that PAT appears in some round's `pattern_ids`,
which the courier derives from the brief's own headings.

Driven against a real daemon for the same reason `TestTheYieldStop` is —
`pattern_analysis_complete` is restricted, and its `pattern_ids` is exactly
the derived half this conjunct leans on. The predicate is read out of
`protocol.toml`, so editing the config re-tests the config.
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_amplification_breaker import _Run  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration]

CAP = 25


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


def _owed(run) -> bool:
    return run.answer("pattern_analysis_overdue") == "true"


def _seed(run):
    """One finding before the first round.

    `pattern_round.py` derives the run from the ledger and refuses when no
    event names one, so a round cannot be the first thing a ledger sees.
    """
    run.file("BH-700")


def _resolve_three(run, prefix="BH-9"):
    """Satisfy the first conjunct so the third is what decides the answer.

    Must run *after* the last round: the conjunct counts resolutions since the
    most recent `pattern_analysis_complete`, so resolving first leaves zero.
    """
    for n in range(1, 4):
        run.file(f"{prefix}{n:02d}")
        run.resolve(f"{prefix}{n:02d}")


class TestTheBackpressureStop:

    def test_a_round_is_owed_at_the_cap(self, run):
        """25 open is not more than 25 — the boundary belongs to the obligation."""
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for n in range(1, CAP + 1):
            run.file(f"BH-{n:03d}", pattern_id="PAT-001")
        _resolve_three(run)

        assert _owed(run), "exactly 25 open pattern-filed findings still owes a round"

    def test_one_past_the_cap_withdraws_the_obligation(self, run):
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for n in range(1, CAP + 2):
            run.file(f"BH-{n:03d}", pattern_id="PAT-001")
        _resolve_three(run)

        assert not _owed(run), (
            f"{CAP + 1} open pattern-filed findings should stop the round"
        )

    def test_closing_them_brings_the_obligation_back(self, run):
        """The conjunct reads the ledger at check time, not a latched flag."""
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for n in range(1, CAP + 3):
            run.file(f"BH-{n:03d}", pattern_id="PAT-001")
        _resolve_three(run)
        assert not _owed(run)

        run.resolve("BH-001")
        run.resolve("BH-002")
        assert _owed(run), "closing back down to the cap should re-owe the round"

    def test_a_deferred_finding_leaves_the_population(self, run):
        """Deferral closes a finding as surely as a fix does."""
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for n in range(1, CAP + 2):
            run.file(f"BH-{n:03d}", "LOW", pattern_id="PAT-001")
        _resolve_three(run)
        assert not _owed(run)

        run.sah("transition", "defer_low", "BH-001")
        assert _owed(run)


class TestWhatCountsAsPatternFiled:

    def test_an_unattributed_finding_does_not_count(self, run):
        """Audit and lens findings carry no `pattern_id` and are not the target.

        The conjunct is about a round's own output. Counting every open finding
        would make it a general board cap, which is a different rule and one
        the plan does not ask for.
        """
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for n in range(1, CAP + 10):
            run.file(f"BH-{n:03d}")
        _resolve_three(run)

        assert _owed(run), "findings with no pattern_id were counted"

    def test_a_pattern_the_brief_never_got_does_not_count(self, run):
        """The join to `pattern_ids` is what makes the field non-forgeable upward.

        `pattern_ids` comes from the courier's read of the brief's headings, so
        attributing findings to a PAT that no round produced cannot inflate the
        population and buy the run out of its obligation.
        """
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        for n in range(1, CAP + 10):
            run.file(f"BH-{n:03d}", pattern_id="PAT-777")
        _resolve_three(run)

        assert _owed(run), (
            "PAT-777 is in no round's pattern_ids, so those findings must not "
            "count toward the cap"
        )

    def test_pat_1_is_not_a_prefix_match_for_pat_10(self, run):
        """`pattern_ids` is a joined string, so the membership test is fenced.

        A bare substring test reads PAT-001 as present in "PAT-0010,PAT-0011"
        and vice versa. Both sides are comma-fenced for exactly this.
        """
        _seed(run)
        run.round(pat_ids=["PAT-0010", "PAT-0011"])
        for n in range(1, CAP + 10):
            run.file(f"BH-{n:03d}", pattern_id="PAT-001")
        _resolve_three(run)

        assert _owed(run), (
            "PAT-001 matched the round's PAT-0010/PAT-0011 by prefix — the "
            "comma fencing is not doing its job"
        )

    def test_a_pattern_from_any_round_counts(self, run):
        """The population spans the run, not just the latest round."""
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        run.round(pat_ids=["PAT-001", "PAT-002"])
        for n in range(1, CAP + 2):
            run.file(f"BH-{n:03d}", pattern_id="PAT-001")
        _resolve_three(run)

        assert not _owed(run), (
            "findings attributed to the first round's pattern stopped counting "
            "once a later round ran"
        )


class TestTheOtherConjunctsStillDecide:
    """Adding a third conjunct must not make the first two unreachable."""

    def test_fewer_than_three_resolutions_still_owes_nothing(self, run):
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        run.file("BH-001", pattern_id="PAT-001")
        run.resolve("BH-001")

        assert not _owed(run), "the 3-resolutions conjunct stopped deciding"

    def test_two_dry_rounds_still_stop_the_obligation(self, run):
        """The yield stop is independent of how many findings are open."""
        _seed(run)
        run.round(pat_ids=["PAT-001"])
        run.round(pat_ids=["PAT-001"])          # dry: no new heading
        run.round(pat_ids=["PAT-001"])          # dry again
        _resolve_three(run, prefix="BH-8")

        assert not _owed(run), "two consecutive dry rounds no longer stop it"

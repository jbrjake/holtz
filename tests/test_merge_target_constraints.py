"""W21 / item 9 — `merge_finding` needs an open target of at least equal severity.

`merge_target_exists` asked only that the target was a finding this run filed
and was not the item itself. So `merge_finding BH-010 BH-011` closed a CRITICAL
into an unrelated LOW — the merge emits `finding_resolved`, which clears
`all_critical_resolved` — and a pattern round could discharge
`round_opens_exceed_closes` by merging its last open sibling into one it had
already merged away.

RULED (Jon, 2026-08-27, D-c): **both** terms. The target's severity must be
`>=` the merged item's, graded by latest filing (D25), **and** the target must
still be open.

Driven against a real daemon rather than asserted off the SQL: the thing under
test is the engine's answer to a transition the run actually types, and a gate
that refuses for the wrong reason reads identically to one that refuses for the
right one until you run it.
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_amplification_breaker import _Run  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration]


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


def _refused(result) -> bool:
    return result.returncode != 0


class TestTheSeverityFloor:
    """A merge closes the item, so the target must carry at least its weight."""

    def test_a_critical_cannot_be_merged_into_a_low(self, run):
        """V1. The row that made the no-fix-CRITICAL-closure table four long."""
        run.file("BH-010", severity="CRITICAL")
        run.file("BH-011", severity="LOW")
        assert _refused(run.merge("BH-010", "BH-011", check=False))

    def test_a_merge_into_an_open_target_of_equal_severity_still_works(self, run):
        """V3. The transition has a real use — this is the sibling merge the
        round cap's whole escape rests on, and it must survive."""
        run.file("BH-010", severity="HIGH")
        run.file("BH-011", severity="HIGH")
        assert not _refused(run.merge("BH-010", "BH-011", check=False))

    def test_a_merge_into_a_higher_target_still_works(self, run):
        """V4. The floor is `>=`, not `==` — a duplicate of something worse is
        still a duplicate."""
        run.file("BH-010", severity="MEDIUM")
        run.file("BH-011", severity="CRITICAL")
        assert not _refused(run.merge("BH-010", "BH-011", check=False))

    def test_severity_is_the_latest_filing_on_both_sides(self, run):
        """V6. D25 — the ledger holds every filing and a correction supersedes.

        Graded by first filing, this refuses: BH-011 was filed LOW. Graded by
        any row ever filed, `item_is_low`'s old defect, the re-file would not
        have been needed to pass. Only max-seq gives the right answer here.
        """
        run.file("BH-010", severity="CRITICAL")
        run.file("BH-011", severity="LOW")
        run.file("BH-011", severity="CRITICAL")  # the correction
        assert not _refused(run.merge("BH-010", "BH-011", check=False))

    def test_a_downgrade_of_the_target_takes_it_off_the_list(self, run):
        """The same clause read the other way, which is what stops the max-seq
        term being satisfiable by filing one high row and forgetting it."""
        run.file("BH-010", severity="CRITICAL")
        run.file("BH-011", severity="CRITICAL")
        run.file("BH-011", severity="LOW")  # re-graded down
        assert _refused(run.merge("BH-010", "BH-011", check=False))


class TestTheTargetMustStillBeOpen:
    """A closed target tracks no work, so merging into it closes for free."""

    def test_a_merge_into_a_resolved_target_is_refused(self, run):
        """V2."""
        run.file("BH-010", severity="HIGH")
        run.file("BH-012", severity="HIGH")
        run.resolve("BH-012")
        assert _refused(run.merge("BH-010", "BH-012", check=False))

    def test_a_merge_into_a_deferred_target_is_refused_too(self, run):
        """Deferred is the other half of closed — `item_open` reads both, and a
        term covering only `finding_resolved` would leave the cheaper route open.
        """
        run.file("BH-010", severity="HIGH")
        run.file("BH-012", severity="HIGH")
        run.defer("BH-012")
        assert _refused(run.merge("BH-010", "BH-012", check=False))

    def test_a_merge_into_an_open_target_is_not_refused(self, run):
        """Non-vacuity for the pair above: the openness term is not a constant."""
        run.file("BH-010", severity="HIGH")
        run.file("BH-012", severity="HIGH")
        assert not _refused(run.merge("BH-010", "BH-012", check=False))


class TestARoundCannotMergeAwayItsOwnSiblings:
    """V5 — driven, not asserted off the predicate.

    `round_opens_exceed_closes` counts merges as closes deliberately: *"close
    **or** merge"* is one count. What stops a round undoing its own search is
    that the chain has to end somewhere. Merging four siblings pairwise closes
    three and leaves one open, and the last one has nowhere to go — every
    sibling it might name is now closed, and a finding cannot merge into itself.
    Before the openness term it could name one it had already merged away, and
    the round discharged its obligation having fixed nothing.
    """

    def test_the_last_sibling_has_nowhere_to_go(self, run):
        run.file("BH-001")
        run.round()
        for sibling in ("BH-101", "BH-102", "BH-103", "BH-104"):
            run.file(sibling, pattern_id="PAT-001")
        run.round()

        for sibling in ("BH-102", "BH-103", "BH-104"):
            assert not _refused(run.merge(sibling, "BH-101", check=False)), \
                f"{sibling} into the open BH-101 is the legitimate sibling merge"

        assert run.answer("round_opens_exceed_closes") == "true", \
            "four opened, three closed — the obligation is not met yet"

        for closed in ("BH-102", "BH-103", "BH-104"):
            assert _refused(run.merge("BH-101", closed, check=False)), \
                f"BH-101 must not be merged into the already-merged {closed}"

        assert run.answer("round_opens_exceed_closes") == "true", \
            "the round must still owe a real close"

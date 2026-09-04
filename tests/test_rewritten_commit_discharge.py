"""Item 50 — a commit the loop rewrote is still the commit that was registered.

W08 keys the pending-commit discharge to a hash, and the two ends stamp that
hash at different moments: the tracker charges what `git commit` **printed**,
the ledger stamps what was at `HEAD` when `transition fix_commit` **ran**.
Anything rewriting the commit in between makes them different strings, so no
bucket holds what the ledger registered and the charge is never discharged.

`phase-fix-loop.md:59-63` prescribes exactly such a rewrite — `git commit` then
`git rebase <branch>` — and in a three-wide loop the first subagent's merge
moves the branch, so **subagents 2 and 3 rebase on every round**. It fails in
the safe direction (a charge is kept, never lost), which is why it is Tier C
and not Tier A, and it costs three things: the primer's run-total drifts upward
and never returns to zero, the actor is falsely blocked if it commits again, and
`compute_obligations` suppresses that actor's pattern nudge for as long as the
bucket is non-empty.

**The key is the finding id, matched the way `fix_commit`'s own gate matches
it** — `git log -1 --format=%B` of the charged commit, searched for an id the
ledger records as resolved. The rewrite preserves the message; the old commit
object survives the rewrite unreachable-but-present; and a linked worktree
shares the object store, so the orchestrator's `cwd` can read a subagent's
pre-rebase commit. The worklist unit records why this beats the two rejected
alternatives (a PostToolUse on `git rebase`/`--amend`, and patch-id).

**Real commits, deliberately.** Every other test of this machinery charges a
fabricated hash, which is the honest stimulus for anything turning on the hash
alone. This one turns on the commit that hash *names* still being readable after
the hash has moved, so `git init` and a genuine `git rebase` are the fixture.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.hook_e2e


def _cache_module():
    """`_protocol_cache` by path — never by name.

    Two modules in this tree are called `_common`, and the wrong one imports
    cleanly while every query returns empty. Loading by path is the habit that
    keeps that from happening to a third name.
    """
    path = str(REPO_ROOT / "enforcement" / "hooks" / "_protocol_cache.py")
    spec = importlib.util.spec_from_file_location("_protocol_cache_rcd", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheDischargeSubtractsRewrittenChargesToo:
    """The value-level rule, before anything drives git.

    `pending_commits_discharged` is pure and stays pure: which charges a rewrite
    moved is decided by the caller, which is the half that can ask git. Pinning
    the pure half separately is what makes the tracker tests below about the
    *lookup* rather than about the subtraction.
    """

    def test_a_rewritten_charge_is_removed_from_whichever_bucket_holds_it(self):
        cache = {"unregistered_commits": {"agent-a": ["a111111"], "": ["c333333"]}}

        buckets = _cache_module().pending_commits_discharged(
            cache, [], rewritten=["a111111"]
        )

        assert buckets == {"": ["c333333"]}

    def test_a_rewritten_charge_leaves_that_actors_other_commits_alone(self):
        """Per charge, not per actor — the deny direction turns on this.

        An actor holding two commits, one of which a registration accounts for,
        is still charged for the other. A rule that emptied the bucket would
        pass every other test in this file and hand that actor a free commit.
        """
        cache = {"unregistered_commits": {"agent-a": ["a111111", "a222222"]}}

        buckets = _cache_module().pending_commits_discharged(
            cache, [], rewritten=["a111111"]
        )

        assert buckets == {"agent-a": ["a222222"]}

    def test_naming_no_rewritten_charge_discharges_exactly_what_it_did_before(self):
        """The default is the old behaviour, asserted rather than assumed."""
        cache = {"unregistered_commits": {"agent-a": ["a111111"], "": ["c333333"]}}

        assert _cache_module().pending_commits_discharged(
            cache, ["a111111"]
        ) == {"": ["c333333"]}


@pytest.mark.slow
class TestARebasedCommitIsDischarged:
    """V1 and V3 — driven through git and a real ledger, end to end.

    A real daemon is the only place the question has an answer: the ledger's
    `finding_resolved` rows are one end of the match and a mock has none. The
    charges are seeded through the tracker and read back through the commit
    gate, because a real daemon refuses `enforcement_write` from a test process
    (`auth_failed` / `pid_resolution_failed`) — the two production paths are the
    only two available, which is also what keeps a fixture from writing a shape
    the hooks never produce.
    """

    def test_a_rebased_commit_discharges_when_its_finding_is_registered(
        self, two_actors
    ):
        """V1 — the defect, end to end: commit, rebase, register, discharge."""
        two_actors.git_init()
        two_actors.git("checkout", "-b", "work-a")
        two_actors.real_commit(
            "agent-a", "fix_a.py", "fix(cache): the thing\n\nBH-101"
        )
        assert two_actors.charges("agent-a") == {"agent-a": 1}, (
            "the commit was never charged, so nothing below would be testing "
            "the discharge"
        )

        rewritten = two_actors.rebase_onto_moved_tip("work-a")
        two_actors.sibling_fix_commit("BH-101", commit_hash=rewritten)
        two_actors.fix_commit_transition("BH-101")

        assert two_actors.charges("agent-a") == {"agent-a": None}

    def test_a_second_commit_for_an_unresolved_finding_stays_charged(
        self, two_actors
    ):
        """V3 — one registration accounts for one commit, rewritten or not.

        Both commits are rewritten by the one rebase, so both charges are
        stranded under the old rule and a fix that discharged the *actor* rather
        than the *commit* would pass V1 and leak here.
        """
        two_actors.git_init()
        two_actors.git("checkout", "-b", "work-a")
        two_actors.real_commit(
            "agent-a", "fix_a.py", "fix(cache): the thing\n\nBH-101"
        )
        two_actors.real_commit(
            "agent-a", "fix_b.py", "fix(cache): the other thing\n\nBH-104"
        )
        assert two_actors.charges("agent-a") == {"agent-a": 2}

        two_actors.rebase_onto_moved_tip("work-a")
        # Only BH-101 is registered. BH-104's commit was rewritten by the same
        # rebase and is just as unfindable by hash — so if the rule were "this
        # actor rebased, clear it", this would read None.
        two_actors.sibling_fix_commit(
            "BH-101", commit_hash=two_actors.git(
                "rev-parse", "--short=7", "HEAD~1"
            ).stdout.strip()
        )
        two_actors.fix_commit_transition("BH-101")

        assert two_actors.charges("agent-a") == {"agent-a": 1}

    def test_a_commit_naming_no_registered_finding_stays_charged(self, two_actors):
        """V3 again, from the other side: a resolution is about its own finding.

        `test_a_commit_the_ledger_never_registered_stays_charged` makes this
        claim about a tree with no commits in it at all, where git can answer
        nothing and the charge is kept for want of an answer. Here git answers
        fully — the commit is real, its message is readable, the rebase really
        moved it — and the charge is kept because the answer is *no*.
        """
        two_actors.git_init()
        two_actors.git("checkout", "-b", "work-a")
        two_actors.real_commit(
            "agent-a", "fix_a.py", "fix(cache): the thing\n\nBH-999"
        )

        rewritten = two_actors.rebase_onto_moved_tip("work-a")
        two_actors.sibling_fix_commit("BH-101", commit_hash=rewritten)
        two_actors.fix_commit_transition("BH-101")

        assert two_actors.charges("agent-a") == {"agent-a": 1}, (
            "a resolution for BH-101 discharged a commit that names BH-999"
        )

    def test_a_sibling_actors_commit_is_not_discharged_by_this_ones(self, two_actors):
        """D41's per-actor keying, under the new match and in one run.

        The two cases above each hold one actor. This one holds two, and both
        routes fire in it: agent-a's charge is discharged through the rewrite,
        agent-b's is kept — so a lookup that searched the ledger's ids without
        caring *which* commit it was reading would show up here and nowhere
        else in this file.
        """
        two_actors.git_init()
        two_actors.git("checkout", "-b", "work-a")
        two_actors.real_commit(
            "agent-a", "fix_a.py", "fix(cache): the thing\n\nBH-101"
        )
        rewritten = two_actors.rebase_onto_moved_tip("work-a")
        two_actors.git("checkout", "main")
        two_actors.real_commit(
            "agent-b", "fix_b.py", "fix(cache): a different thing\n\nBH-102"
        )

        two_actors.sibling_fix_commit("BH-101", commit_hash=rewritten)
        two_actors.fix_commit_transition("BH-101")

        assert two_actors.charges("agent-a", "agent-b") == {
            "agent-a": None, "agent-b": 1,
        }


@pytest.mark.slow
class TestTheStatusLineReturnsToZero:
    """V2 — the observable symptom, read where a session reads it.

    The unit calls the run-total the observable cost: `format_state_line` sums
    every bucket, so a stranded charge makes "N pending commits" drift upward
    and never come back. Asserted out of the primer's own injected context
    rather than by formatting a cache the test fetched — the symptom is what a
    session is shown.
    """

    def _three_actors_two_rebased(self, two_actors) -> dict[str, str]:
        """Three commits on three branches; two of them rewritten by a rebase.

        Three actors and two rebases: the counts a careless assertion would
        confuse — actors, rebases, charges — are deliberately unequal.
        """
        two_actors.git_init()
        registered: dict[str, str] = {}

        two_actors.git("checkout", "-b", "work-a")
        two_actors.real_commit("agent-a", "fix_a.py", "fix(a): thing\n\nBH-101")
        registered["BH-101"] = two_actors.rebase_onto_moved_tip("work-a")

        two_actors.git("checkout", "main")
        two_actors.git("checkout", "-b", "work-b")
        two_actors.real_commit("agent-b", "fix_b.py", "fix(b): thing\n\nBH-102")
        registered["BH-102"] = two_actors.rebase_onto_moved_tip("work-b")

        # The orchestrator's commit is never rewritten, so its charge discharges
        # by hash exactly as it does today. A run where every charge took the
        # new route would not show that the old one still works.
        two_actors.git("checkout", "main")
        registered["BH-103"] = two_actors.real_commit(
            "", "fix_c.py", "fix(c): thing\n\nBH-103"
        )
        return registered

    def test_the_run_total_counts_every_charge_before_any_is_registered(
        self, two_actors
    ):
        """The precondition. Without it, "no pending commits" passes vacuously."""
        self._three_actors_two_rebased(two_actors)

        assert "3 pending commits" in two_actors.state_line()

    def test_the_run_total_returns_to_zero_once_all_three_are_registered(
        self, two_actors
    ):
        registered = self._three_actors_two_rebased(two_actors)
        for finding_id, commit_hash in registered.items():
            two_actors.sibling_fix_commit(finding_id, commit_hash=commit_hash)

        two_actors.fix_commit_transition("BH-101")

        line = two_actors.state_line()
        assert "pending commits" not in line, line
        assert line.startswith("Protocol:"), (
            f"the primer said nothing at all, so this asserts nothing: {line!r}"
        )

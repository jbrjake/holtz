"""W05 / item 2 — `medium_deferral_budget` does not gate `converge`.

⚠️ **This file used to say "three seats, not four".** It is four again, and the
fourth is not the one W05 removed: W14 (item 5) gave the amplification breaker
a second seat at `iteration_boundary`, because `pattern_done` is reachable only
from `pattern_analysis` and the fix loop teaches staying in `fix_loop`. W05's
ruling is untouched — `converge` still has no budget seat, which is what
`TestTheSeatIsGoneFromConverge` asserts. The count was never the claim; the
*set* is, and it is pinned by name below.

`converge` required the MEDIUM deferral budget **spent** (`expect = "false"`).
The denominator counts every MEDIUM ever filed, open or closed, and
`defer_medium`'s cap is `deferred < N/2` against the same integer division — so
converging required *exactly* `floor(N/2)` deferrals, and a run that fixed all
its MEDIUMs could never converge. Worse, the budget had to be spent *before* the
MEDIUMs were fixed, so the run had to decide which half to abandon at the moment
it was least able to judge.

RULED (Jon, 2026-08-27), D-a: drop the conjunct from `converge` only. The
predicate keeps its other consumers and every one of them is correct:

    defer_medium        fix_loop           expect true   the cap
    pattern_done        breaker any_of     expect false  the escape's post-state
    defer_medium        pattern_analysis   expect true   the cap, other state
    iteration_boundary  breaker any_of     expect false  the same escape, on the
                                                         taught path (W14/item 5)

(Line numbers dropped: they were wrong within two commits of being written, and
`_budget_seats()` finds the seats by query name regardless.)

The breaker seat reads `expect = "false"` for a reason that does *not* transfer
to `converge`: its block must have an escape achievable by construction, and
"no open MEDIUM" is unachievable because the cap forbids deferring them all — so
it is phrased as budget-spent, which cannot be refused. `converge` is a standing
precondition, not a block needing a reachable escape. The form was copied to a
seat where its reasoning does not hold.

So these tests come in two halves, and the second is the one that makes the
deletion a ruling rather than a weakening: **V5 and V6 must stay green while V1
and V2 flip.** A change that turned them all green would have removed the cap.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from test_amplification_breaker import _Run  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.integration]


@pytest.fixture
def run(real_daemon):
    return _Run(real_daemon)


def _transitions() -> list[dict]:
    with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
        return tomllib.load(fh)["transitions"]


def _converge_gates() -> list[dict]:
    return next(t for t in _transitions() if t["command"] == "converge")["gates"]


def _walk(gates):
    """Gates, flattened. A seat can be nested inside `any_of`/`all_of`."""
    for gate in gates:
        yield gate
        yield from _walk(gate.get("gates", []))


def _budget_seats() -> set[tuple[str, str, str]]:
    """Every `medium_deferral_budget` gate as (command, from_state, expect)."""
    return {
        (t["command"], t["from"], g.get("expect"))
        for t in _transitions()
        for g in _walk(t.get("gates", []))
        if g.get("query") == "medium_deferral_budget"
    }


def _at_final_sweep(run) -> None:
    run.sah("event", "state_transition", "--field", "from=all_perspectives_clean",
            "--field", "to=final_sweep", "--field", "command=final_sweep_start")


def _converge_check(run) -> str:
    return run.sah("gate", "check", "converge", check=False).stdout


def _assert_budget_does_not_gate_converge(out: str) -> None:
    """No budget verdict on converge — and proof the gate was evaluated.

    Without the second assertion an empty or errored output would satisfy the
    first, and "the conjunct is gone" would be indistinguishable from "the gate
    never ran". Same discipline as W04's control ledger.
    """
    assert "medium_deferral_budget" not in out, out
    assert "all_critical_resolved" in out, f"converge gate did not evaluate:\n{out}"


class TestTheSeatIsGoneFromConverge:
    """V1-V4. The strand, and the three shapes of run it stranded."""

    def test_the_conjunct_is_absent_from_the_transition(self):
        assert "medium_deferral_budget" not in {g.get("query") for g in _converge_gates()}

    def test_v1_the_strand_five_fixed_one_deferred(self, run):
        """The acceptance criterion. Observed blocked before the ruling.

        N=6 with 5 resolved and 1 deferred leaves no open MEDIUM at all, and the
        old gate still refused: 1 < 6/2 = 3, so the budget read unspent.
        """
        for n in range(1, 7):
            run.file(f"BH-1{n:02d}", "MEDIUM")
        for n in range(1, 6):
            run.resolve(f"BH-1{n:02d}")
        run.defer("BH-106", reason="medium_budget")
        _at_final_sweep(run)
        _assert_budget_does_not_gate_converge(_converge_check(run))

    def test_v2_the_virtuous_run_fixes_all_six(self, run):
        """The case the old gate made unreachable, and the reason for D-a."""
        for n in range(1, 7):
            run.file(f"BH-1{n:02d}", "MEDIUM")
            run.resolve(f"BH-1{n:02d}")
        _at_final_sweep(run)
        _assert_budget_does_not_gate_converge(_converge_check(run))

    @pytest.mark.parametrize("n_mediums", [0, 1, 2, 6])
    def test_v3_no_n_dependence_survives(self, run, n_mediums):
        """The old gate was vacuous at N=1 (1/2 == 0) and binding from N=2.

        Parametrised across that boundary: after the deletion there is no
        N-dependence left to get wrong.
        """
        for n in range(1, n_mediums + 1):
            run.file(f"BH-1{n:02d}", "MEDIUM")
            run.resolve(f"BH-1{n:02d}")
        _at_final_sweep(run)
        _assert_budget_does_not_gate_converge(_converge_check(run))

    def test_v4_a_late_medium_no_longer_reblocks(self, run):
        """N=6 spent, then two more filed. The old denominator grew and the
        budget went unspent again, re-blocking an already-open converge."""
        for n in range(1, 7):
            run.file(f"BH-1{n:02d}", "MEDIUM")
        for n in (1, 2, 3):
            run.defer(f"BH-1{n:02d}", reason="medium_budget")
        _at_final_sweep(run)
        run.file("BH-107", "MEDIUM")
        run.file("BH-108", "MEDIUM")
        _assert_budget_does_not_gate_converge(_converge_check(run))


class TestTheOtherSeatsAreUntouched:
    """V5, V6. What distinguishes a ruling from a blanket removal.

    If these go green-by-absence the deletion took the cap with it, and the
    protocol would let a run defer every MEDIUM it has.
    """

    def test_v5_v6_exactly_these_seats_remain_and_which(self):
        """The whole risk of this unit is deleting one seat too many.

        Pinning the exact set, not a count: a count survives a change that
        removes one seat and adds another somewhere wrong.

        **Was three seats; W14 (item 5) added the fourth deliberately.** The
        amplification breaker used to block only at `pattern_done`, reachable
        only from `pattern_analysis` — the *rare* path, since the fix loop
        teaches staying in `fix_loop`. It now blocks at `iteration_boundary`
        too, referencing the same three named queries so the seats cannot
        drift. This test failing on that addition is it working: a seat set
        that changes silently is the thing it exists to prevent.
        """
        assert _budget_seats() == {
            ("defer_medium", "fix_loop", "true"),          # the cap
            ("defer_medium", "pattern_analysis", "true"),  # the cap, other state
            ("pattern_done", "pattern_analysis", "false"),  # the breaker's escape
            ("iteration_boundary", "fix_loop", "false"),   # the same escape, taught path
        }

    def test_v5_the_cap_refuses_the_deferral_past_half(self, run):
        """Driven, not read.

        The gate is `deferred < N/2` and it is evaluated *before* the deferral
        records, so at N=6 it admits the third (2 < 3) and refuses the fourth
        (3 < 3 is false). Three permitted, not two — which is also why
        `converge`'s old `expect = "false"` seat demanded exactly `floor(N/2)`.
        """
        for n in range(1, 7):
            run.file(f"BH-1{n:02d}", "MEDIUM")
        for n in (1, 2, 3):
            allowed = run.sah("transition", "defer_medium", "--", f"BH-1{n:02d}",
                              check=False)
            assert allowed.returncode == 0, (
                f"the cap refused deferral {n} of 3, which is within budget:\n"
                f"{allowed.stdout}{allowed.stderr}"
            )
        refused = run.sah("transition", "defer_medium", "--", "BH-104", check=False)
        assert refused.returncode != 0, (
            f"the cap let a fourth deferral through:\n{refused.stdout}{refused.stderr}"
        )
        assert "medium_deferral_budget" in (refused.stdout + refused.stderr)

    def test_the_refusal_names_its_escape(self, run):
        """W25 / item 11 (D-l) — the spent budget says what to do instead.

        The escape is the fix: `fix_commit` is declared from `fix_loop`, where
        this refusal fires. It cannot be driven to success from a test — a real
        daemon refuses a test process the `suite_green` its gate reads — so the
        assertion is on what the refusal prints.
        """
        for n in range(1, 3):
            run.file(f"BH-2{n:02d}", "MEDIUM")
        run.sah("transition", "defer_medium", "--", "BH-201")
        refused = run.sah("transition", "defer_medium", "--", "BH-202", check=False)
        assert refused.returncode != 0, refused.stdout + refused.stderr
        assert "`fix_commit`" in (refused.stdout + refused.stderr), (
            refused.stdout + refused.stderr
        )

    def test_v6_the_breaker_escape_is_still_reachable(self, run):
        """`pattern_done`'s `any_of` keeps the branch whose post-state a single
        `defer batch --severity low,medium` produces. Without it the breaker's
        escape is unreachable and the block is #77's deadlock again.

        Driven through the escape rather than read off the config: spending the
        budget must actually flip the predicate.
        """
        for n in range(1, 7):
            run.file(f"BH-1{n:02d}", "MEDIUM")
        assert run.answer("medium_deferral_budget") == "true", "budget starts unspent"
        for n in (1, 2, 3):
            run.sah("transition", "defer_medium", "--", f"BH-1{n:02d}")
        assert run.answer("medium_deferral_budget") == "false", (
            "spending the budget must flip the predicate the breaker branch reads"
        )


class TestThePredicateItselfIsUnchanged:
    """V8, plus the half of step 2 that is a claim rather than an instruction."""

    def test_v8_the_linter_reports_no_orphan(self):
        """H1 reports an orphaned query. Deleting the last consumer of a
        predicate is a different change from deleting one seat of four, and the
        linter is what tells those apart."""
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "scripts", "enforcement_lint.py")],
            capture_output=True, text=True, timeout=300, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        offending = [
            ln for ln in result.stdout.splitlines()
            if "medium_deferral_budget" in ln and "error" in ln.lower()
        ]
        assert not offending, offending

    def test_the_query_text_and_intent_are_untouched(self):
        """Step 2: protocol.toml keeps its own wording, which describes the cap
        and is accurate for the three seats that remain."""
        with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
            query = tomllib.load(fh)["queries"]["medium_deferral_budget"]
        assert query["intent"] == (
            "MEDIUM deferrals must not exceed 50% of total MEDIUM findings"
        )
        assert "reason='medium_budget'" in query["sql"]


# Step 3's "confirm by diff that this commit touches exactly one line of gate
# config" is not expressed as a test on purpose: a test reading `git show HEAD`
# cannot pass during the commit that introduces it, and one reading the working
# tree stops meaning anything the moment the change lands. The standing claim it
# would make is `test_v5_v6_exactly_these_seats_remain_and_which` above, which
# pins the surviving seats by name and holds for every future commit rather than
# for one. The diff itself is checked at commit time and recorded in the message.

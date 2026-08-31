"""P0.1's convergence redefinition — D4's four conjuncts, under D5 (P0.5).

`converge` required `all_findings_closed == 0`. The audited run's open count
rose 124 -> 273 and fell exactly once, so that gate was unreachable from
pattern round 1: the run was non-terminating by construction and the protocol
said nothing about it. What it also could not say was *which* findings had to
be closed. These four conjuncts say it:

    all CRITICAL resolved
    AND all user_reachable HIGH resolved-or-deferred
    AND A < 1.0 over the last 3 rounds
    AND DEFERRED.md written

D5 added a fifth conjunct — the MEDIUM budget **spent** — as the counterweight
to the carve-out, so that "MEDIUM may stay open" could not become "defer the
MEDIUMs instead of fixing half of them." **D-a (Jon, 2026-08-27) removed it from
this transition**, and W05 is where that landed: the denominator counts every
MEDIUM ever filed and `defer_medium`'s cap is the same integer division, so
converging required *exactly* `floor(N/2)` deferrals and a run that fixed all
its MEDIUMs could never converge at all. The counterweight is not lost — it
lives in the cap itself (`defer_medium`, both states), which still refuses the
deferral past half. See `tests/test_medium_budget_seats.py` for the three seats
that remain and why this one was the wrong one.

The third conjunct is the one the 2026-08-21 session rejected, on the grounds
that it "blocks a run that has legitimately closed everything." That is true
only under the gate being *replaced*, where nothing is open at converge by
definition. Under the replacement, open MEDIUM and LOW findings persist and
that conjunct is exactly what stops a run converging while it still generates
faster than it retires. Scoring one clause of a package against the baseline
the package removes is the error; the tests below are written against the
package.
"""
from __future__ import annotations

import json
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


class TestAllCriticalResolved:
    """Resolved, not resolved-or-deferred. A CRITICAL is not deferrable."""

    def test_an_open_critical_blocks(self, run):
        run.file("BH-001", "CRITICAL")
        assert run.answer("all_critical_resolved") == "false"

    def test_resolving_it_clears(self, run):
        run.file("BH-001", "CRITICAL")
        run.resolve("BH-001")
        assert run.answer("all_critical_resolved") == "true"

    def test_deferring_it_does_not(self, run):
        """The conjunct says *resolved*. Every other severity in this package
        admits deferral; this one is why the package still terminates on the
        findings that matter."""
        run.file("BH-001", "CRITICAL")
        run.defer("BH-001")
        assert run.answer("all_critical_resolved") == "false", (
            "a deferred CRITICAL satisfied the conjunct that says resolved"
        )

    def test_a_downgraded_critical_is_not_a_critical(self, run):
        """Severity is the latest filing (D25)."""
        run.file("BH-001", "CRITICAL")
        run.file("BH-001", "LOW")
        assert run.answer("all_critical_resolved") == "true"

    def test_an_upgraded_finding_is(self, run):
        run.file("BH-001", "LOW")
        assert run.answer("all_critical_resolved") == "true"
        run.file("BH-001", "CRITICAL")
        assert run.answer("all_critical_resolved") == "false"

    def test_a_run_with_no_criticals_is_clear(self, run):
        """Non-vacuity: the conjunct is not simply always shut."""
        run.file("BH-001", "HIGH")
        assert run.answer("all_critical_resolved") == "true"


class TestAllUserReachableHighClosed:
    """The carve-out, and its edge: reachability is graded, and re-gradable."""

    def test_an_open_user_reachable_high_blocks(self, run):
        run.file("BH-001", "HIGH", reachability="user_reachable")
        assert run.answer("all_user_reachable_high_closed") == "false"

    def test_resolving_clears(self, run):
        run.file("BH-001", "HIGH")
        run.resolve("BH-001")
        assert run.answer("all_user_reachable_high_closed") == "true"

    def test_deferring_also_clears(self, run):
        """"resolved-**or-deferred**" — unlike the CRITICAL conjunct."""
        run.file("BH-001", "HIGH")
        run.defer("BH-001")
        assert run.answer("all_user_reachable_high_closed") == "true"

    def test_a_fault_injected_high_is_outside_the_population(self, run):
        """The whole point of P0.5: ~22 of 62 commits went to defects
        reachable only by making another call raise."""
        run.file("BH-001", "HIGH", reachability="fault_injected")
        run.file("BH-002", "HIGH", reachability="theoretical")
        assert run.answer("all_user_reachable_high_closed") == "true"

    def test_a_regrade_moves_it_into_the_population(self, run):
        """A probe that establishes reachability must put the finding back on
        the list convergence has to clear."""
        run.file("BH-001", "HIGH", reachability="theoretical")
        assert run.answer("all_user_reachable_high_closed") == "true"

        run.file("BH-001", "HIGH", reachability="user_reachable")
        assert run.answer("all_user_reachable_high_closed") == "false", (
            "reachability is not being read from the latest filing"
        )

    def test_a_user_reachable_medium_does_not_block(self, run):
        """MEDIUM and LOW may legitimately persist — that is the carve-out,
        and D5's budget conjunct is what keeps it honest."""
        run.file("BH-001", "MEDIUM")
        run.file("BH-002", "LOW")
        assert run.answer("all_user_reachable_high_closed") == "true"


class TestTheGateIsThePackage:
    """All four conjuncts on `converge`. D5's fifth was removed by D-a (W05)."""

    def _at_final_sweep(self, run):
        run.sah("event", "state_transition", "--field", "from=all_perspectives_clean",
                "--field", "to=final_sweep", "--field", "command=final_sweep_start")

    def _lines(self, run):
        return run.sah("gate", "check", "converge", check=False).stdout

    def test_every_conjunct_is_on_the_transition(self):
        import tomllib
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        converge = next(t for t in transitions if t["command"] == "converge")
        queries = {g.get("query") for g in converge["gates"]}
        assert {"all_critical_resolved", "all_user_reachable_high_closed",
                "amplification_diverging"} <= queries
        assert any(g.get("path") == "docs/holtz/DEFERRED.md"
                   for g in converge["gates"]), "the DEFERRED.md conjunct is missing"
        # D-a / W05. Stated as a negative here as well as positively in
        # test_medium_budget_seats.py: `<=` is a subset test, so dropping the
        # name from the set above would pass whether or not the seat came back.
        assert "medium_deferral_budget" not in queries

    def test_all_findings_closed_no_longer_gates_converge(self):
        """The clause *replaces* it. Leaving it would keep the unreachable
        requirement and make the four conjuncts decoration."""
        import tomllib
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        converge = next(t for t in transitions if t["command"] == "converge")
        assert "all_findings_closed" not in {g.get("query") for g in converge["gates"]}

    def test_an_open_critical_blocks_converge(self, run):
        run.file("BH-001", "CRITICAL")
        self._at_final_sweep(run)
        out = self._lines(run)
        line = [ln for ln in out.splitlines() if "'all_critical_resolved'" in ln]
        assert len(line) == 1 and line[0].strip().startswith("✗"), out

    def test_an_unspent_medium_budget_no_longer_blocks_converge(self, run):
        """D-a / W05, the reverse of what D5 asserted here.

        Four MEDIUMs filed and none deferred is an unspent budget. It used to
        block, which meant a run had to abandon two of the four *before* it
        could converge, whether or not it had fixed them.
        """
        for n in range(1, 5):
            run.file(f"BH-1{n:02d}", "MEDIUM")
        self._at_final_sweep(run)
        out = self._lines(run)
        assert "medium_deferral_budget" not in out, out
        # ...and the gate did run, so the absence is a decision and not a
        # skipped evaluation.
        assert "all_critical_resolved" in out, out


class TestTheBlockIsEscapable:
    """`sweep_dirty` is `final_sweep -> fix_loop` with no gates, so every
    conjunct here is escapable by going back and doing the work."""

    def test_sweep_dirty_is_ungated(self):
        import tomllib
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        dirty = next(t for t in transitions if t["command"] == "sweep_dirty")
        assert dirty["from"] == "final_sweep" and dirty["to"] == "fix_loop"
        assert not dirty.get("gates"), (
            "sweep_dirty gained gates — every converge conjunct's escape runs "
            "through it"
        )

    def test_the_run_can_go_back_and_clear_a_critical(self, run):
        run.file("BH-001", "CRITICAL")
        run.sah("event", "state_transition", "--field", "from=all_perspectives_clean",
                "--field", "to=final_sweep", "--field", "command=final_sweep_start")
        assert run.answer("all_critical_resolved") == "false"

        result = run.sah("transition", "sweep_dirty", check=False)
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        run.resolve("BH-001")
        assert run.answer("all_critical_resolved") == "true"


class TestTheDeferredFileConjunct:

    def test_the_render_target_exists(self):
        """The conjunct names a file the ledger renders; a converge gate on a
        file nothing writes is the shape that wedged #60."""
        import tomllib
        with open(os.path.join(CONFIG_DIR, "renders.toml"), "rb") as fh:
            renders = tomllib.load(fh)["renders"]
        assert any(r["target"] == "DEFERRED.md" for r in renders)

    def test_it_is_written_once_the_run_has_findings(self, run):
        run.file("BH-001", "LOW")
        path = os.path.join(run.root, "docs", "holtz", "DEFERRED.md")
        assert os.path.exists(path), (
            f"DEFERRED.md is a converge conjunct and nothing wrote it: "
            f"{json.dumps(sorted(os.listdir(os.path.dirname(path))))}"
        )

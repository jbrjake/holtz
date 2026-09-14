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
from pathlib import Path

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
        # D-b: the deferral conjunct is a ledger predicate, not a `file_exists`.
        # `DEFERRED.md` is no longer written by a run that defers nothing, so a
        # gate on the file would refuse exactly the run that fixed everything.
        assert "deferral_record_complete" in queries, "the deferral conjunct is missing"
        assert not any(g.get("path") == "docs/holtz/DEFERRED.md"
                       for g in converge["gates"]), (
            "a `file_exists` on DEFERRED.md is unsatisfiable for a run with no "
            "deferrals now that `finding` is off its render trigger"
        )
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

    def _deferred_path(self, run):
        return os.path.join(run.root, "docs", "holtz", "DEFERRED.md")

    def test_filing_a_finding_no_longer_writes_it(self, run):
        """Step 1 — `finding` is off the trigger.

        While it was on, the file existed from the run's first finding, which
        is what reduced `converge`'s conjunct to a `file_exists` on a file the
        engine wrote unconditionally.
        """
        run.file("BH-001", "LOW")
        assert not os.path.exists(self._deferred_path(run)), (
            "filing a finding rendered DEFERRED.md, so `finding` is still on "
            "the trigger"
        )

    def test_a_run_that_defers_nothing_still_converges(self, run):
        """⭐ THE TRAP (D-b). Acceptance criterion number one.

        A run that files findings and fixes all of them defers nothing, and the
        conjunct must not stop it. Asserted on the **predicate**, which is what
        the trap is about, rather than on the file's existence.

        ⚠️ **V1 also says "`DEFERRED.md` does not exist" here, and it does.**
        Step 4 puts `finding_resolved` on the trigger so a deferred-then-fixed
        finding leaves the list, and that render fires whether or not anything
        was ever deferred — so a virtuous run writes an empty file. The two
        clauses cannot both hold: no conditional-render mechanism exists
        (`RenderConfig.trigger` is one string and the engine writes whatever
        the template produces). Harmless as built, because nothing gates on the
        file any more; recorded rather than resolved by dropping step 4.
        """
        run.file("BH-001", "LOW")
        run.resolve("BH-001")
        assert run.answer("deferral_record_complete") == "true", (
            "the replacement conjunct must be vacuously true at zero deferrals"
        )
        # `gate check` prints nothing for a transition unavailable from the
        # current state, and an empty read would assert nothing at all.
        run.sah("event", "state_transition", "--field", "from=all_perspectives_clean",
                "--field", "to=final_sweep", "--field", "command=final_sweep_start")
        out = run.gate_check("converge")
        assert out.strip(), "gate check converge produced nothing — wrong state?"
        lines = [ln.strip() for ln in out.splitlines()
                 if "deferral_record_complete" in ln]
        assert len(lines) == 1, f"expected one line naming the conjunct:\n{out}"
        assert not lines[0].startswith("\u2717"), (
            f"the deferral conjunct blocks a run that deferred nothing:\n{out}"
        )

    def test_a_deferral_writes_it(self, run):
        """V2 — the render still fires on the event that means something."""
        run.file("BH-001", "LOW")
        run.defer("BH-001")
        assert os.path.exists(self._deferred_path(run)), (
            f"DEFERRED.md is a converge conjunct and nothing wrote it: "
            f"{json.dumps(sorted(os.listdir(os.path.dirname(self._deferred_path(run)))))}"
        )
        assert run.answer("deferral_record_complete") == "true"

    def test_a_deferral_naming_no_filed_finding_reads_false(self, run):
        """V3 — the predicate is refusable, and this is the state it refuses.

        A `finding_deferred` whose id was never filed is a deferral tracked
        nowhere: it satisfies every write-time check (`id`'s pattern only fixes
        the shape) and closes a finding that does not exist. A predicate true in
        every reachable state is decoration, which is what P0.1 removed from
        `converge` to begin with.
        """
        run.file("BH-001", "LOW")
        run.defer("BH-999")
        assert run.answer("deferral_record_complete") == "false"

    def test_filing_the_finding_the_deferral_names_flips_it(self, run):
        """V4 — the escape, driven. Every state it refuses has a way out."""
        run.file("BH-001", "LOW")
        run.defer("BH-999")
        assert run.answer("deferral_record_complete") == "false"
        run.file("BH-999", "LOW")
        assert run.answer("deferral_record_complete") == "true"

    def test_a_deferred_then_fixed_finding_leaves_the_file(self, run):
        """V6 (item 44). `fix_commit` carries no `item_open` gate, so deferring
        a finding and fixing it anyway is a legal path — and the template
        listed it as deferred forever, because it computed `deferred_ids` and
        never `resolved_ids`."""
        run.file("BH-001", "LOW")
        run.defer("BH-001")
        run.resolve("BH-001")
        text = Path(self._deferred_path(run)).read_text(encoding="utf-8")
        assert "BH-001" not in text, (
            f"a resolved finding is still listed as deferred:\n{text}"
        )

    def test_a_deferred_finding_that_was_not_fixed_is_still_listed(self, run):
        """V7 — the non-vacuity of V6. Precedence, not deletion."""
        run.file("BH-001", "LOW")
        run.file("BH-002", "LOW")
        run.defer("BH-001")
        run.defer("BH-002")
        run.resolve("BH-002")
        text = Path(self._deferred_path(run)).read_text(encoding="utf-8")
        assert "BH-001" in text, f"the unfixed deferral vanished:\n{text}"
        assert "BH-002" not in text


class TestTheFindingTemplateFamilyAgrees:
    """V8/V9/V10 — the render side of D-b and D-g.

    `deferred.md.tera` was the one member of the family that computed
    `deferred_ids` and never `resolved_ids`, so a finding deferred and fixed
    anyway — legal, since `fix_commit` carries no `item_open` gate — stayed on
    the deferred list forever. Asserted across the family rather than on the
    one file, because "three had it and one did not" is exactly the state a
    single-file test cannot see.
    """

    _FAMILY = ("punchlist.md.tera", "punchlist-archive.md.tera",
               "deferred.md.tera", "status.md.tera", "summary.md.tera")

    @pytest.mark.parametrize("template", _FAMILY)
    def test_every_finding_template_computes_resolved_ids(self, template):
        path = os.path.join(CONFIG_DIR, "templates", template)
        text = Path(path).read_text(encoding="utf-8")
        assert "resolved_ids" in text, (
            f"{template} renders findings without asking which are resolved — "
            f"copy punchlist.md.tera's expression rather than writing a second"
        )

    def test_status_counts_move_on_a_finding_event_with_no_transition(self, run):
        """V9 (D-g). `STATUS.md` rendered `on_transition` only, so its
        Open/Resolved counts froze between transitions — and the fix loop runs
        many findings between them."""
        status = os.path.join(run.root, "docs", "holtz", "STATUS.md")
        run.file("BH-001", "LOW")
        assert os.path.exists(status), "no STATUS.md after a finding event"
        before = Path(status).read_text(encoding="utf-8")

        run.file("BH-002", "LOW")
        after = Path(status).read_text(encoding="utf-8")
        assert before != after, (
            "STATUS.md did not change on a finding event — the on_event entry "
            "is missing or its event_types do not name `finding`"
        )

    def test_the_extra_renders_record_no_protocol_violation(self, run):
        """V10 — the failure mode this could have introduced.

        `STATUS.md` is a managed file, so every finding event now re-renders
        and re-tracks it. If the manifest did not absorb those writes, each one
        would land a `protocol_violation` and the run would end unable to
        converge for reasons nobody wrote.
        """
        for finding_id in ("BH-001", "BH-002", "BH-003"):
            run.file(finding_id, "LOW")
        run.defer("BH-001")
        run.resolve("BH-002")

        out = run.sah("query", "SELECT count(*) FROM events WHERE "
                               "type='protocol_violation'", "--format", "json").stdout
        count = list(json.loads(out)[0].values())[0]
        assert int(count) == 0, (
            f"{count} protocol_violation event(s) after six finding-family "
            f"renders — the manifest is not absorbing the re-renders"
        )

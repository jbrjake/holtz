"""`sahjhan defer batch --severity low,medium` — the circuit-breaker's escape.

P0.1's block is cleared by *one* command that defers every open LOW and spends
the MEDIUM budget. That command is a declared `[batches.defer]` driven by two
named populations, and it has to hold three properties the gate will lean on:

* It applies `defer_low` / `defer_medium` **with their own gates**. The 50% cap
  on MEDIUM stays load-bearing (D5) — the batch must not become a way around it.
* A gate refusal is **not fatal**. A budget-capped step is supposed to stop
  partway; reaching that line is the point, and a batch that aborted on the
  first refusal would leave the escape half-applied.
* Its post-state is exactly what the breaker's predicate asserts: no open LOW,
  and the MEDIUM budget spent. Phrasing the predicate as *budget spent* rather
  than *set empty* is what makes the escape achievable by construction, since
  one batch can never defer every MEDIUM.

The populations are read out of `protocol.toml` and run through the real
binary, so editing the config re-tests the config.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib

import pytest

pytestmark = [pytest.mark.slow]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))

_COMMON = [
    "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
    "--field", "phase=fix_loop", "--field", "step=10",
]
DEFERRED_MD = os.path.join("docs", "holtz", "DEFERRED.md")


def _protocol() -> dict:
    with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
        return tomllib.load(fh)


def _named_query(name: str) -> str:
    try:
        return _protocol()["queries"][name]["sql"]
    except KeyError:
        raise AssertionError(f"protocol.toml has no [queries.{name}]") from None


def _rows(root) -> dict[str, str]:
    """The rendered DEFERRED.md data rows, keyed by finding id."""
    path = root / DEFERRED_MD
    if not path.exists():
        return {}
    return {
        line.split("|")[1].strip(): line
        for line in path.read_text().splitlines()
        if line.startswith("| BH-")
    }


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.fixture
def loop(tmp_path):
    """A ledger parked in `fix_loop`, plus helpers to fill and drive it.

    Straight to the state under test with a `state_transition` event rather
    than walking nine gated transitions, none of which is what this asserts.
    """
    binary = _binary()
    root = str(tmp_path)

    def sah(*args, check=True):
        result = subprocess.run(
            [binary, "--config-dir", CONFIG_DIR, *args],
            capture_output=True, text=True, cwd=root, timeout=60,
        )
        if check:
            assert result.returncode == 0, (
                f"{' '.join(args)}\n{result.stdout}\n{result.stderr}"
            )
        return result

    sah("init")
    sah("event", "state_transition", "--field", "from=merge_done",
        "--field", "to=fix_loop", "--field", "command=fix_loop_start")

    def file_finding(finding_id, severity, description="a finding"):
        sah("event", "finding",
            "--field", f"id={finding_id}", "--field", f"severity={severity}",
            "--field", "category=correctness", "--field", "location=src/x.py:1",
            "--field", "perspective=integration", "--field", "predicted_by=none",
             "--field", "reachability=user_reachable",
            "--field", f"description={description}", *_COMMON)

    def ids_from(query_name):
        out = sah("query", _named_query(query_name), "--format", "csv").stdout
        rows = [line.strip().strip('"') for line in out.strip().splitlines()[1:]]
        return sorted(r for r in rows if r)

    def answer(query_name):
        out = sah("query", _named_query(query_name), "--format", "csv").stdout
        return out.strip().splitlines()[-1].strip().strip('"').lower() in ("true", "1")

    def batch(*severities):
        return sah("defer", "batch", "--severity", ",".join(severities), check=False)

    return tmp_path, file_finding, ids_from, answer, batch


class TestThePopulations:
    """`open_low_findings` / `open_medium_findings` select what the batch sweeps."""

    def test_only_open_findings_of_that_severity_are_selected(self, loop):
        _, file_finding, ids_from, _, _ = loop
        file_finding("BH-001", "LOW")
        file_finding("BH-002", "MEDIUM")
        file_finding("BH-003", "HIGH")

        assert ids_from("open_low_findings") == ["BH-001"]
        assert ids_from("open_medium_findings") == ["BH-002"]

    def test_severity_is_the_latest_filing(self, loop):
        """D25: a finding corrected LOW -> HIGH is not a LOW any more.

        The run-wide form needs the max-seq subquery correlated on `f.id`;
        pinning it to a constant, or dropping it, sweeps a HIGH into the LOW
        batch and closes it as a priority deferral. That is the defect
        `fe2ef56` fixed for `defer_low`, one field further in.
        """
        _, file_finding, ids_from, _, _ = loop
        file_finding("BH-001", "LOW", "first filing")
        file_finding("BH-001", "HIGH", "corrected — this is worse than it looked")
        file_finding("BH-002", "HIGH", "always was high")
        file_finding("BH-002", "LOW", "downgraded on review")

        assert ids_from("open_low_findings") == ["BH-002"], (
            "the corrected HIGH is still being swept as a LOW"
        )

    def test_a_closed_finding_leaves_the_population(self, loop):
        """Resolved and deferred ids are out — the batch must not re-defer."""
        _, file_finding, ids_from, _, batch = loop
        file_finding("BH-001", "LOW")
        file_finding("BH-002", "LOW")
        batch("low")

        assert ids_from("open_low_findings") == []


class TestTheBatchRespectsTheGates:

    def test_every_open_low_is_deferred(self, loop):
        _, file_finding, ids_from, _, batch = loop
        for n in range(1, 6):
            file_finding(f"BH-00{n}", "LOW")

        result = batch("low", "medium")
        assert "defer_low: 5 applied, 0 refused" in result.stdout, result.stdout
        assert ids_from("open_low_findings") == []

    def test_the_medium_budget_still_caps_the_batch(self, loop):
        """D5: the 50% fix-half rule keeps force inside the batch.

        Four MEDIUMs buy two deferrals. If the batch bypassed the gates it
        would defer all four, and the only rule forcing a run to *fix* half its
        MEDIUMs would be void.
        """
        _, file_finding, ids_from, _, batch = loop
        for n in range(1, 5):
            file_finding(f"BH-00{n}", "MEDIUM")

        result = batch("medium")
        assert "defer_medium: 2 applied, 2 refused" in result.stdout, result.stdout
        assert len(ids_from("open_medium_findings")) == 2

    def test_a_refusal_is_reported_and_not_fatal(self, loop):
        """The command exits 0 and names the query that refused each item.

        A batch that aborted on the first budget refusal would leave the LOWs
        deferred and the MEDIUM step half-run, and the breaker's escape would
        depend on how many MEDIUMs happened to be open.
        """
        _, file_finding, _, _, batch = loop
        for n in range(1, 5):
            file_finding(f"BH-00{n}", "MEDIUM")

        result = batch("medium")
        assert result.returncode == 0, (
            f"a budget refusal aborted the batch:\n{result.stdout}\n{result.stderr}"
        )
        assert "medium_deferral_budget" in result.stdout, (
            f"the refusal does not name the predicate that caused it:\n{result.stdout}"
        )

    def test_the_low_step_runs_before_the_medium_population_is_read(self, loop):
        """Steps read their population in order, after earlier steps append.

        Both steps run in one command, so the MEDIUM budget is computed against
        a ledger that already carries the LOW deferrals. LOW deferrals carry
        `reason='low_priority'` and the budget counts `reason='medium_budget'`,
        so they must not fund or spend MEDIUM budget.
        """
        _, file_finding, ids_from, _, batch = loop
        for n in range(1, 5):
            file_finding(f"BH-10{n}", "LOW")
        for n in range(1, 5):
            file_finding(f"BH-20{n}", "MEDIUM")

        result = batch("low", "medium")
        assert "defer_low: 4 applied" in result.stdout, result.stdout
        assert "defer_medium: 2 applied, 2 refused" in result.stdout, (
            f"the four LOW deferrals moved the MEDIUM budget:\n{result.stdout}"
        )


class TestTheEscapeIsAchievableByConstruction:
    """One batch reaches the post-state the breaker's predicate will assert.

    The predicate cannot be "no open MEDIUM": the 50% cap makes that
    unreachable, and a block whose escape cannot clear it is a deadlock. It has
    to be "no open LOW **and** the MEDIUM budget is spent" — which one run of
    the named command always achieves.
    """

    def test_one_batch_clears_the_lows_and_spends_the_medium_budget(self, loop):
        _, file_finding, ids_from, answer, batch = loop
        for n in range(1, 4):
            file_finding(f"BH-10{n}", "LOW")
        for n in range(1, 6):
            file_finding(f"BH-20{n}", "MEDIUM")

        assert answer("medium_deferral_budget"), "budget starts unspent"

        batch("low", "medium")

        assert ids_from("open_low_findings") == [], "an open LOW survived the batch"
        assert not answer("medium_deferral_budget"), (
            "the MEDIUM budget is not spent after one batch — a predicate "
            "phrased in budget-spent terms would never clear"
        )
        assert ids_from("open_medium_findings"), (
            "every MEDIUM was deferred, so the 50% cap did not hold"
        )

    def test_the_odd_medium_count_still_spends_the_budget(self, loop):
        """Non-vacuity for the boundary: one MEDIUM buys zero deferrals.

        `count < total / 2` with integer division is already false at zero
        deferrals for a single MEDIUM, so the budget reads spent without the
        batch applying anything. The escape still clears — which is the
        property, not the count.
        """
        _, file_finding, _, answer, batch = loop
        file_finding("BH-001", "LOW")
        file_finding("BH-002", "MEDIUM")

        batch("low", "medium")
        assert not answer("medium_deferral_budget")


class TestTheRenderIsWrittenByTheCommandThatDefers:

    def test_the_batch_writes_deferred_md(self, loop):
        """`docs/holtz/DEFERRED.md`, per P0.1 — from the same command.

        The render also fires on `finding` so a correction to a deferred item
        reaches the view, which means the file exists (with no rows) before any
        deferral. The claim under test is that the *batch* is what fills it.
        """
        root, file_finding, _, _, batch = loop
        file_finding("BH-001", "LOW", "a low finding")
        file_finding("BH-002", "MEDIUM", "a medium finding")
        file_finding("BH-003", "MEDIUM", "another medium finding")

        assert _rows(root) == {}, "rows before anything was deferred"
        batch("low", "medium")

        rows = _rows(root)
        assert "BH-001" in rows, rows
        mediums = {"BH-002", "BH-003"} & set(rows)
        assert len(mediums) == 1, (
            f"two MEDIUMs buy exactly one deferral; got {sorted(mediums)}"
        )

    def test_the_reason_column_comes_from_the_transition(self, loop):
        """Each row carries the reason its own transition emitted.

        `reason` is the field the MEDIUM budget gate counts, so a row here is
        auditable against the cap it spent. A single hardcoded reason would
        render identically for a LOW and pass a test that only checked ids.

        Which MEDIUM the cap admits is not asserted: the population query has
        no ORDER BY, and the clause is about the budget being spent, not about
        a particular id.
        """
        root, file_finding, _, _, batch = loop
        file_finding("BH-001", "LOW", "a low finding")
        file_finding("BH-002", "MEDIUM", "a medium finding")
        file_finding("BH-003", "MEDIUM", "another medium finding")
        batch("low", "medium")

        rows = _rows(root)
        assert "low_priority" in rows["BH-001"], rows["BH-001"]
        deferred_medium = next(r for i, r in rows.items() if i != "BH-001")
        assert "medium_budget" in deferred_medium, deferred_medium

    def test_an_open_finding_is_not_in_the_deferred_view(self, loop):
        """The file is the deferred slice, not the whole board."""
        root, file_finding, _, _, batch = loop
        file_finding("BH-001", "LOW", "gets deferred")
        file_finding("BH-002", "HIGH", "stays open")
        batch("low")

        assert set(_rows(root)) == {"BH-001"}, _rows(root)

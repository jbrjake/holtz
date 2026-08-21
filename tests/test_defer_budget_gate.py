"""The MEDIUM deferral budget must count findings, not ledger rows.

`defer_medium`'s budget gate is *"MEDIUM deferrals must not exceed 50% of total
MEDIUM findings"*. It expressed that as ``count(*) < count(*) / 2`` over raw
events, so both sides counted rows:

* A MEDIUM finding re-filed under its own id — a correction recorded without
  retracting the original — inflates the denominator, and the cap it enforces
  is no longer 50% of anything real. Two genuine MEDIUMs with one correction
  between them read as three, so a second deferral passes a gate that exists to
  stop it.
* A ``finding_deferred`` recorded twice for one id inflates the numerator, and
  the run loses budget it never spent. `sahjhan event finding_deferred` is on
  the bootstrap allowlist, so this is a path the agent has.

The gate is a policy on findings, so it counts distinct finding ids. These
tests run the gate's *own* SQL — read out of transitions.toml, not restated
here — against a real ledger, so editing the config re-tests the config.
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


def _budget_sql() -> str:
    """The live SQL of `defer_medium`'s budget gate."""
    with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
        cfg = tomllib.load(fh)
    for transition in cfg["transitions"]:
        if transition.get("command") != "defer_medium":
            continue
        for gate in transition.get("gates", []):
            if "50%" in gate.get("intent", ""):
                return gate["sql"]
    raise AssertionError("defer_medium has no MEDIUM-budget gate")


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


def _run(binary, root, *args):
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, *args],
        capture_output=True, text=True, cwd=root, timeout=30,
    )
    assert result.returncode == 0, f"{' '.join(args)}\n{result.stdout}\n{result.stderr}"
    return result


@pytest.fixture
def ledger(tmp_path):
    binary = _binary()
    root = str(tmp_path)
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        capture_output=True, text=True, cwd=root, timeout=30, check=True,
    )

    def file_medium(finding_id, description="a medium finding"):
        _run(
            binary, root, "event", "finding",
            "--field", f"id={finding_id}", "--field", "severity=MEDIUM",
            "--field", "category=correctness", "--field", "location=src/x.py:10",
            "--field", "perspective=integration", "--field", "predicted_by=none",
            "--field", f"description={description}", *_COMMON,
        )

    def defer(finding_id):
        _run(
            binary, root, "event", "finding_deferred",
            "--field", f"id={finding_id}", "--field", "reason=medium_budget",
            *_COMMON,
        )

    def budget_allows():
        out = _run(binary, root, "query", _budget_sql(), "--format", "csv").stdout
        answer = out.strip().splitlines()[-1].strip().strip('"').lower()
        assert answer in ("true", "false", "1", "0"), f"unparseable gate answer: {out!r}"
        return answer in ("true", "1")

    return file_medium, defer, budget_allows


class TestMediumDeferralBudget:

    def test_half_of_the_mediums_is_the_cap(self, ledger):
        """Baseline: two MEDIUMs allow one deferral, not two."""
        file_medium, defer, budget_allows = ledger
        file_medium("BH-001")
        file_medium("BH-002")
        assert budget_allows(), "the first deferral of two MEDIUMs is within budget"
        defer("BH-001")
        assert not budget_allows(), "the second would be 100% of the MEDIUMs"

    def test_a_refiled_medium_does_not_buy_extra_budget(self, ledger):
        """A correction is not a second finding, and must not fund a deferral.

        Two real MEDIUMs, each re-filed once — a correction pass over the
        punchlist. Four rows, two findings. The cap is one deferral either way;
        counting rows reads the budget as two.
        """
        file_medium, defer, budget_allows = ledger
        file_medium("BH-001", "first filing")
        file_medium("BH-002", "a different finding")
        file_medium("BH-001", "corrected filing")
        file_medium("BH-002", "corrected filing")
        defer("BH-001")

        assert not budget_allows(), (
            "One of two real MEDIUMs is already the whole budget — the re-filed "
            "ids inflated the denominator to four and let a second deferral through"
        )

    def test_a_double_recorded_deferral_does_not_burn_extra_budget(self, ledger):
        """One deferred finding spends one unit of budget, however many times
        the deferral was recorded."""
        file_medium, defer, budget_allows = ledger
        for n in range(1, 5):
            file_medium(f"BH-00{n}")
        defer("BH-001")
        defer("BH-001")

        assert budget_allows(), (
            "One deferred finding of four MEDIUMs is under the 50% cap; the "
            "repeated record inflated the numerator to two"
        )

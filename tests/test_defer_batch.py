"""Batch deferral must close every finding the per-item transitions would.

`defer_low` and `defer_medium` gate on severity and open-ness only, so the run
they were measured on could have closed 133 of its 273 open findings with them
and used them zero times. `defer_batch.py` is that loop; these tests drive it
against the real binary and read the result out of the ledger, because the
properties worth having are about what the transitions did, not about what the
script printed.

Two of them pin ordering. MEDIUM is budget-capped, and a refused MEDIUM must
neither look like a failure nor cost the LOW deferrals that share the batch.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.slow]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
SCRIPT = os.path.join(REPO_ROOT, "skills", "holtz", "scripts", "defer_batch.py")
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))

_COMMON = [
    "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
    "--field", "phase=fix_loop", "--field", "step=10",
]


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.fixture
def project(tmp_path):
    """A ledger parked in `fix_loop`, with helpers to fill and inspect it."""
    binary = _binary()
    root = str(tmp_path)

    def sah(*args, check=True):
        result = subprocess.run(
            [binary, "--config-dir", CONFIG_DIR, *args],
            capture_output=True, text=True, cwd=root, timeout=30,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    subprocess.run(["git", "init", "-q", "."], cwd=root, timeout=30, check=True)
    sah("init")
    # The deferral transitions run from `fix_loop`; walking the whole protocol
    # to get there would test the protocol, not the batch.
    sah("transition", "run_start")
    sah("event", "state_transition", "--field", "from=recon",
        "--field", "to=fix_loop", "--field", "run=1",
        "--field", "auditor=holtz", "--field", "project=t")

    def file_finding(finding_id, severity):
        sah("event", "finding", "--field", f"id={finding_id}",
            "--field", f"severity={severity}", "--field", "category=correctness",
            "--field", "location=src/x.py:10", "--field", "perspective=integration",
            "--field", "predicted_by=none", "--field", "description=a finding",
            *_COMMON)

    def resolve(finding_id):
        sah("event", "finding_resolved", "--field", f"id={finding_id}",
            "--field", "commit_hash=abc1234", *_COMMON)

    def deferred_ids():
        out = sah("query", "--type", "finding_deferred", "--format", "jsonl").stdout
        ids = set()
        for line in out.splitlines():
            if line.strip():
                record = json.loads(line)
                ids.add(record.get("id") or record.get("fields", {}).get("id"))
        return ids

    def batch(*args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            capture_output=True, text=True, cwd=root, timeout=180,
        )

    return file_finding, resolve, deferred_ids, batch


class TestBatchDeferral:

    def test_every_open_low_is_deferred_and_nothing_else_is(self, project):
        file_finding, _resolve, deferred_ids, batch = project
        for n in (1, 2, 3):
            file_finding(f"BH-00{n}", "LOW")
        file_finding("BH-004", "HIGH")
        file_finding("BH-005", "MEDIUM")

        result = batch("--severity", "low")

        assert result.returncode == 0, result.stderr
        assert deferred_ids() == {"BH-001", "BH-002", "BH-003"}, (
            "the LOW pass must close every open LOW and touch no other severity"
        )

    def test_an_already_closed_low_is_left_alone(self, project):
        """`item_open` would refuse it, and one refusal stops the pass."""
        file_finding, resolve, deferred_ids, batch = project
        file_finding("BH-001", "LOW")
        file_finding("BH-002", "LOW")
        resolve("BH-001")

        result = batch("--severity", "low")

        assert result.returncode == 0, result.stderr
        assert deferred_ids() == {"BH-002"}, (
            "a resolved LOW must not be offered to the transition — it would be "
            "refused, and the refusal would strand every LOW after it"
        )

    def test_the_medium_budget_caps_the_pass_without_failing_it(self, project):
        """Half the MEDIUMs is the cap; reaching it is policy, not an error."""
        file_finding, _resolve, deferred_ids, batch = project
        for n in range(1, 5):
            file_finding(f"BH-00{n}", "MEDIUM")

        result = batch("--severity", "medium")

        assert result.returncode == 0, (
            f"the budget cap is the gate working, not a failure: {result.stderr}"
        )
        assert len(deferred_ids()) == 2, (
            f"4 MEDIUMs allow 2 deferrals, got {sorted(deferred_ids())}"
        )
        assert "budget" in result.stdout.lower(), (
            f"the caller must be told the rest stay open: {result.stdout!r}"
        )

    def test_a_spent_medium_budget_does_not_strand_the_uncapped_lows(self, project):
        """The cap ends the MEDIUM pass, not the batch.

        LOW is the half that can always be spent, and it is 133 of the 273
        findings this whole mechanism exists for.
        """
        file_finding, _resolve, deferred_ids, batch = project
        for n in range(1, 5):
            file_finding(f"BH-00{n}", "MEDIUM")
        for n in range(5, 8):
            file_finding(f"BH-00{n}", "LOW")

        result = batch("--severity", "low,medium")

        assert result.returncode == 0, result.stderr
        assert {"BH-005", "BH-006", "BH-007"} <= deferred_ids(), (
            f"every LOW must be deferred whatever the MEDIUM budget does; "
            f"deferred {sorted(deferred_ids())}"
        )
        assert len(deferred_ids()) == 5, (
            f"3 LOWs and half of 4 MEDIUMs; deferred {sorted(deferred_ids())}"
        )

    def test_high_cannot_be_batch_deferred(self, project):
        """Priority deferral stops at MEDIUM; HIGH needs an investigation file."""
        file_finding, _resolve, deferred_ids, batch = project
        file_finding("BH-001", "HIGH")

        result = batch("--severity", "high")

        assert result.returncode != 0, "batching HIGH must be refused outright"
        assert deferred_ids() == set(), "a refused batch must defer nothing"

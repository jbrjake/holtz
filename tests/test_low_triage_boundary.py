"""`iteration_boundary` refuses to carry open LOW findings past a diverging run.

The run this comes from filed 2.43 findings per fix, never once used the
deferral transitions, and halted with 273 open of which 133 were legally
batch-closable. `converge` needs every finding resolved or deferred, so that
run could not terminate — and nothing before the very end of the protocol ever
mentioned it.

The property that matters most here is not when the gate fires but that its
block is always escapable: every finding the predicate counts satisfies
`defer_low`'s own gates, so the command the block names can always close them.
A gate whose escape can be shut is #77, and this repo has paid for that twice.

The predicate is read out of protocol.toml by name and run through the real
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
BATCH = os.path.join(REPO_ROOT, "skills", "holtz", "scripts", "defer_batch.py")
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))

QUERY = "low_findings_carried"

_COMMON = [
    "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
    "--field", "phase=fix_loop", "--field", "step=10",
]


def _config(filename: str) -> dict:
    with open(os.path.join(CONFIG_DIR, filename), "rb") as fh:
        return tomllib.load(fh)


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.fixture
def ledger(tmp_path):
    binary = _binary()
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q", "."], cwd=root, timeout=30, check=True)
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        capture_output=True, text=True, cwd=root, timeout=30, check=True,
    )

    def sah(*args, check=True):
        result = subprocess.run(
            [binary, "--config-dir", CONFIG_DIR, *args],
            capture_output=True, text=True, cwd=root, timeout=30,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

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

    def carried():
        sql = _config("protocol.toml")["queries"][QUERY]["sql"]
        out = sah("query", sql, "--format", "csv").stdout
        answer = out.strip().splitlines()[-1].strip().strip('"').lower()
        assert answer in ("true", "false", "1", "0"), f"unparseable: {out!r}"
        return answer in ("true", "1")

    def batch():
        return subprocess.run(
            [sys.executable, BATCH, "--severity", "low"],
            capture_output=True, text=True, cwd=root, timeout=180,
        )

    return file_finding, resolve, carried, batch


class TestWhenTheGateFires:

    def test_a_fresh_fix_loop_with_open_lows_is_carrying_them(self, ledger):
        """Nothing is closed at fix-loop entry, so triage is owed immediately —
        which is where the batch belongs, ahead of the first fix subagent."""
        file_finding, _resolve, carried, _batch = ledger
        file_finding("BH-001", "LOW")
        file_finding("BH-002", "HIGH")

        assert carried()

    def test_a_run_with_no_open_low_is_not_carrying_any(self, ledger):
        file_finding, _resolve, carried, _batch = ledger
        for n, severity in ((1, "HIGH"), (2, "MEDIUM"), (3, "CRITICAL")):
            file_finding(f"BH-00{n}", severity)

        assert not carried(), "the gate is about LOW findings, not open findings"

    def test_a_run_that_has_closed_the_majority_may_carry_a_low(self, ledger):
        """Both conjuncts, and the one that lets the gate stop firing.

        A late lens sweep filing one LOW into a run that has retired most of
        its board is not divergence, and forcing a batch there would defer work
        the run has time for.
        """
        file_finding, resolve, carried, _batch = ledger
        for n in range(1, 6):
            file_finding(f"BH-00{n}", "HIGH")
        for n in range(1, 5):
            resolve(f"BH-00{n}")
        file_finding("BH-006", "LOW")

        assert not carried(), (
            "2 open against 4 closed is a converging run; the open LOW alone "
            "must not force a batch"
        )

    def test_the_backlog_conjunct_alone_is_not_enough(self, ledger):
        """Mirror of the above: a large backlog with no open LOW does not fire."""
        file_finding, _resolve, carried, _batch = ledger
        for n in range(1, 6):
            file_finding(f"BH-00{n}", "MEDIUM")

        assert not carried()

    def test_a_low_corrected_to_high_stops_being_carried(self, ledger):
        """The predicate and `defer_low` must agree about which findings the
        escape covers, or the block names a command that cannot clear it."""
        file_finding, _resolve, carried, _batch = ledger
        file_finding("BH-001", "LOW")
        assert carried()

        file_finding("BH-001", "HIGH")

        assert not carried(), (
            "a finding whose latest filing is HIGH cannot be closed by "
            "`defer_low`, so counting it would make the block unescapable"
        )


class TestTheBlockIsAlwaysEscapable:

    def test_the_batch_the_block_names_clears_the_block(self, ledger):
        """End to end: the predicate is true, the named command runs, the
        predicate is false — against the real transitions, not a stand-in."""
        file_finding, _resolve, carried, batch = ledger
        for n in range(1, 6):
            file_finding(f"BH-00{n}", "LOW")
        for n in range(6, 9):
            file_finding(f"BH-00{n}", "HIGH")
        assert carried()

        result = batch()

        assert result.returncode == 0, result.stderr
        assert not carried(), (
            f"`defer_batch.py --severity low` must clear the gate it is named "
            f"in; it printed {result.stdout!r}"
        )

    def test_the_gate_names_the_command_that_clears_it(self):
        """#77 was a block whose printed escape was itself blocked. The intent
        string is the only place a reader learns what to run."""
        intent = _config("protocol.toml")["queries"][QUERY]["intent"]

        assert "defer_batch.py" in intent, (
            f"the block must name its escape; intent is {intent!r}"
        )
        assert os.path.exists(BATCH), (
            "the intent names a script that is not in the tree"
        )


class TestTheGateIsWired:

    def test_iteration_boundary_gates_on_the_predicate(self):
        gates = [
            t for t in _config("transitions.toml")["transitions"]
            if t.get("command") == "iteration_boundary"
        ][0]["gates"]
        named = [(g.get("query"), g.get("expect")) for g in gates]

        assert (QUERY, "false") in named, (
            f"iteration_boundary must refuse to pass while findings are "
            f"carried; its gates are {named}"
        )

"""A finding's severity is its latest filing, at every gate that reads one.

The ledger keeps every filing of an id. `punchlist.md.tera` and `findings.py`
both render the last one, so a finding corrected LOW -> HIGH shows as HIGH on
the board — while `defer_low`'s gate matched any row ever filed under the id
and let the run close it as a LOW. Severity re-grading is a thing this protocol
expects (one defect class in the measured run decayed CRITICAL -> LOW across
four findings), so a correction that the deferral gates ignore is a hole in the
one place severity decides anything.

`defer_medium`'s budget denominator has the same shape from the other side: a
finding corrected MEDIUM -> HIGH is not a MEDIUM, and must fund no budget.

These tests run the gates' *own* SQL, read out of the config through the query
name the transition references, so editing the config re-tests the config.
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


def _named_query(name: str) -> str:
    with open(os.path.join(CONFIG_DIR, "protocol.toml"), "rb") as fh:
        queries = tomllib.load(fh)["queries"]
    assert name in queries, f"protocol.toml has no [queries.{name}]"
    return queries[name]["sql"]


def _gate_names(command: str) -> list[str]:
    """The named queries `command` gates on, in order."""
    with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
        cfg = tomllib.load(fh)
    for transition in cfg["transitions"]:
        if transition.get("command") == command:
            return [g["query"] for g in transition.get("gates", []) if "query" in g]
    raise AssertionError(f"no transition named {command}")


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

    def file_finding(finding_id, severity):
        sah("event", "finding", "--field", f"id={finding_id}",
            "--field", f"severity={severity}", "--field", "category=correctness",
            "--field", "location=src/x.py:10", "--field", "perspective=integration",
            "--field", "predicted_by=none", "--field", "description=a finding",
            *_COMMON)

    def defer(finding_id, reason="medium_budget"):
        sah("event", "finding_deferred", "--field", f"id={finding_id}",
            "--field", f"reason={reason}", *_COMMON)

    def asks(name, finding_id=""):
        sql = _named_query(name).replace("{{item_id}}", finding_id)
        out = sah("query", sql, "--format", "csv").stdout
        answer = out.strip().splitlines()[-1].strip().strip('"').lower()
        assert answer in ("true", "false", "1", "0"), f"unparseable: {out!r}"
        return answer in ("true", "1")

    return file_finding, defer, asks


class TestTheDeferralGatesReadTheLatestFiling:

    def test_a_low_corrected_to_high_is_no_longer_low(self, ledger):
        file_finding, _defer, asks = ledger
        file_finding("BH-001", "LOW")
        assert asks("item_is_low", "BH-001"), "the first filing is LOW"

        file_finding("BH-001", "HIGH")

        assert not asks("item_is_low", "BH-001"), (
            "the correction supersedes the filing it corrects — matching any row "
            "ever filed under the id lets a HIGH be closed by `defer low`"
        )

    def test_a_high_corrected_to_low_becomes_low(self, ledger):
        """The correction is honoured in both directions, not just the strict one."""
        file_finding, _defer, asks = ledger
        file_finding("BH-001", "HIGH")
        assert not asks("item_is_low", "BH-001")

        file_finding("BH-001", "LOW")

        assert asks("item_is_low", "BH-001"), (
            "a downgrade is a correction too, and `defer_low` must accept it"
        )

    def test_a_medium_corrected_to_high_is_no_longer_medium(self, ledger):
        file_finding, _defer, asks = ledger
        file_finding("BH-001", "MEDIUM")
        file_finding("BH-001", "HIGH")

        assert not asks("item_is_medium", "BH-001")

    def test_one_finding_is_never_two_severities(self, ledger):
        file_finding, _defer, asks = ledger
        file_finding("BH-001", "LOW")
        file_finding("BH-001", "MEDIUM")

        assert [asks("item_is_low", "BH-001"), asks("item_is_medium", "BH-001")] \
            == [False, True], "exactly one severity gate may admit a finding"


class TestTheMediumBudgetCountsCurrentMediums:

    def test_a_medium_corrected_to_high_funds_no_budget(self, ledger):
        """Two real MEDIUMs allow one deferral. A third id filed MEDIUM and then
        corrected to HIGH must not raise the cap to two."""
        file_finding, defer, asks = ledger
        file_finding("BH-001", "MEDIUM")
        file_finding("BH-002", "MEDIUM")
        file_finding("BH-003", "MEDIUM")
        file_finding("BH-003", "HIGH")
        defer("BH-001")

        assert not asks("medium_deferral_budget"), (
            "one of two current MEDIUMs is the whole budget; counting the "
            "corrected id read the denominator as three"
        )


class TestTheGatesReferenceTheNames:
    """`sahjhan lint` L6 reports copies; these pin that the deferral gates hold
    no SQL of their own to drift."""

    @pytest.mark.parametrize("command,expected", [
        ("defer_low", ["item_is_low", "item_open"]),
        ("defer_medium", ["item_is_medium", "item_open", "medium_deferral_budget"]),
    ])
    def test_the_deferral_gates_are_all_named_queries(self, command, expected):
        assert _gate_names(command) == expected

    @pytest.mark.parametrize("command", ["defer_low", "defer_medium"])
    def test_no_gate_carries_inline_sql(self, command):
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            cfg = tomllib.load(fh)
        for transition in cfg["transitions"]:
            if transition.get("command") != command:
                continue
            inline = [g for g in transition.get("gates", []) if "sql" in g]
            assert not inline, (
                f"{command} gates on inline SQL: {inline}. A predicate two sites "
                f"decide should be one [queries.<name>] object."
            )

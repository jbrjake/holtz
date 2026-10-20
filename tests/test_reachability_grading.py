"""P0.5's reachability grading — the field, and that it is not optional.

~22 of the audited run's 62 commits were fault-injection-only: reachable only
by making some other call raise. BH-258's own text conceded that "reachability
on CPython 3.12 is uncertain… needs a reachability probe before any fix" and it
got a full fix cycle anyway. Meanwhile 51 of the 75 open HIGHs predated the
first commit and were never worked, including an unescaped-`desc` HTML
injection. The board had no way to say which findings a user can actually
reach, so it could not sort by it.

Required rather than optional, because D4's convergence conjunct is defined
over it — "all `user_reachable` HIGH resolved-or-deferred". An optional field
makes that conjunct silently weaker on every finding that omits it, which is
the direction laziness points.

Driven against the real binary: a schema assertion read out of `events.toml`
would only prove the file says what the file says.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))

VALUES = ("user_reachable", "fault_injected", "theoretical")


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.fixture
def project(tmp_path):
    binary = _binary()
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        cwd=root, capture_output=True, text=True, timeout=60, check=True,
    )
    return binary, root


def _file_finding(binary, root, finding_id="BH-001", reachability="user_reachable"):
    extra = ["--field", f"reachability={reachability}"] if reachability else []
    return subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "event", "finding",
         "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
         "--field", "phase=audit", "--field", "step=7", "--field", f"id={finding_id}",
         "--field", "severity=HIGH", "--field", "category=bug",
         "--field", "location=a.py:1", "--field", "perspective=component",
         "--field", "predicted_by=none", "--field", "description=x", *extra],
        cwd=root, capture_output=True, text=True, timeout=60,
    )


class TestTheFieldIsRequired:

    def test_a_finding_without_it_is_refused(self, project):
        binary, root = project
        result = _file_finding(binary, root, reachability=None)
        assert result.returncode != 0, (
            "a finding filed with no reachability was accepted — D4's "
            "user_reachable conjunct is only as strong as this field's "
            "presence"
        )

    @pytest.mark.parametrize("value", VALUES)
    def test_each_grade_is_accepted(self, project, value):
        binary, root = project
        result = _file_finding(binary, root, f"BH-{VALUES.index(value) + 1:03d}", value)
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    def test_a_grade_outside_the_three_is_refused(self, project):
        """Otherwise the vocabulary drifts and the gate reading it cannot
        enumerate what it is reading."""
        binary, root = project
        result = _file_finding(binary, root, reachability="probably")
        assert result.returncode != 0, result.stdout


class TestTheSchemaAndTheDocAgree:
    """The auditor grades from `punchlist-format.md`; the engine validates from
    `events.toml`. A value in one and not the other is a step the run cannot
    complete, or a grade nothing will ever check."""

    def test_the_taught_values_are_exactly_the_accepted_ones(self):
        with open(os.path.join(CONFIG_DIR, "events.toml"), "rb") as fh:
            fields = tomllib.load(fh)["events"]["finding"]["fields"]
        declared = next(f for f in fields if f["name"] == "reachability")
        assert declared.get("optional") is not True

        doc = os.path.join(
            REPO_ROOT, "skills", "holtz", "references", "punchlist-format.md")
        with open(doc, encoding="utf-8") as fh:
            text = fh.read()
        for value in VALUES:
            assert value in declared["pattern"], value
            assert value in text, f"{value} is accepted but never taught"

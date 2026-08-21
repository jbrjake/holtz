"""PUNCHLIST.md must be a table anyone can parse, with one row per finding.

The punchlist is rendered from the ledger and is the file every status count
is taken off. Two defects made those counts wrong:

* A description containing a pipe — ``breaks on `prog | head` input`` — was
  interpolated raw into a Markdown table cell, so the row split into seven
  columns instead of six. 22 of 354 rows in one run.
* A finding filed twice under one id rendered as two rows, so the headline
  count was off by the number of duplicates.

Both are render defects, so both are pinned at the render, against the real
binary rather than a reimplementation of it.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.slow]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))

EXPECTED_COLUMNS = 6


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


def _record_finding(binary, project_root, finding_id, description, location="src/x.py:10"):
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "event", "finding",
         "--field", f"id={finding_id}", "--field", "project=t",
         "--field", "run=1", "--field", "auditor=holtz",
         "--field", "phase=audit", "--field", "step=6",
         "--field", "severity=HIGH", "--field", "category=correctness",
         "--field", f"location={location}", "--field", "perspective=integration",
         "--field", "predicted_by=none", "--field", f"description={description}"],
        capture_output=True, text=True, cwd=project_root, timeout=30,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def _data_rows(project_root):
    """The finding rows of the rendered punchlist, header and rule excluded."""
    path = os.path.join(project_root, "docs", "holtz", "PUNCHLIST.md")
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    return [
        line for line in lines
        if line.startswith("| ") and not line.startswith("| ID ")
        and not line.startswith("|----")
    ]


def _cells(row):
    """Split a Markdown table row on unescaped pipes."""
    import re
    body = row.strip().strip("|")
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


@pytest.fixture
def rendered_punchlist(tmp_path):
    binary = _binary()
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=30, check=True,
    )
    return binary, str(tmp_path)


class TestPunchlistRenderIsParseable:

    def test_pipe_in_description_does_not_add_a_column(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-001", "breaks on `prog | head` input")

        rows = _data_rows(root)
        assert len(rows) == 1
        assert len(_cells(rows[0])) == EXPECTED_COLUMNS, (
            f"Row did not parse into {EXPECTED_COLUMNS} columns: {rows[0]}"
        )
        assert "prog \\| head" in rows[0], "The pipe must be escaped, not dropped"

    def test_pipe_in_location_does_not_add_a_column(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(
            binary, root, "BH-002", "ordinary description",
            location="src/x.py:10 | src/y.py:2",
        )
        rows = _data_rows(root)
        assert len(_cells(rows[0])) == EXPECTED_COLUMNS

    def test_newline_in_description_does_not_split_the_row(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-003", "line one\nline two")

        rows = _data_rows(root)
        assert len(rows) == 1, f"A newline broke one finding into {len(rows)} rows"
        assert len(_cells(rows[0])) == EXPECTED_COLUMNS

    def test_one_row_per_finding_id(self, rendered_punchlist):
        """A finding re-filed under an existing id renders once, not twice."""
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-004", "first filing")
        _record_finding(binary, root, "BH-005", "a different finding")
        _record_finding(binary, root, "BH-004", "corrected filing")

        rows = _data_rows(root)
        ids = [_cells(row)[0] for row in rows]
        assert len(ids) == len(set(ids)), f"Duplicate ids rendered: {ids}"
        assert sorted(ids) == ["BH-004", "BH-005"]

        # The survivor is the latest filing, so a correction supersedes what it
        # corrects. Keeping the first would make re-filing a no-op, which is
        # the opposite of what an agent re-recording a finding means by it.
        surviving = next(row for row in rows if _cells(row)[0] == "BH-004")
        assert "corrected filing" in surviving, (
            "Dedupe must keep the latest filing, not the earliest"
        )

    def test_every_row_parses_when_all_hazards_are_present(self, rendered_punchlist):
        """The whole table stays rectangular with all three hazards mixed in."""
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-006", "pipe `a | b` here")
        _record_finding(binary, root, "BH-007", "newline\nhere")
        _record_finding(binary, root, "BH-006", "duplicate id")
        _record_finding(binary, root, "BH-008", "plain")

        rows = _data_rows(root)
        assert len(rows) == 3
        for row in rows:
            assert len(_cells(row)) == EXPECTED_COLUMNS, f"Ragged row: {row}"

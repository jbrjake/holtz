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

# P0.4 trimmed the open worklist to id, severity, `file:line` and a 12-word
# summary. The archive keeps the six-column form: it is read once, by recon's
# cold-file scan, not reloaded on every fix.
OPEN_COLUMNS = 4
ARCHIVE_COLUMNS = 6


def _binary():
    from _resolve import ensure_sahjhan
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


_COMMON = [
    "--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
    "--field", "phase=audit", "--field", "step=6",
]


def _record_finding(binary, project_root, finding_id, description, location="src/x.py:10"):
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "event", "finding",
         "--field", f"id={finding_id}",
         "--field", "severity=HIGH", "--field", "category=correctness",
         "--field", f"location={location}", "--field", "perspective=integration",
         "--field", "predicted_by=none", "--field", f"description={description}",
         *_COMMON],
        capture_output=True, text=True, cwd=project_root, timeout=30,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def _resolve_finding(binary, project_root, finding_id):
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "event", "finding_resolved",
         "--field", f"id={finding_id}", "--field", "commit_hash=abc1234", *_COMMON],
        capture_output=True, text=True, cwd=project_root, timeout=30,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def _defer_finding(binary, project_root, finding_id):
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "event", "finding_deferred",
         "--field", f"id={finding_id}", "--field", "reason=low_priority", *_COMMON],
        capture_output=True, text=True, cwd=project_root, timeout=30,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def _rows_of(project_root, basename):
    """The finding rows of a rendered table, header and rule excluded."""
    path = os.path.join(project_root, "docs", "holtz", basename)
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    return [
        line for line in lines
        if line.startswith("| ") and not line.startswith("| ID ")
        and not line.startswith("|----")
    ]


def _data_rows(project_root):
    return _rows_of(project_root, "PUNCHLIST.md")


def _archive_rows(project_root):
    return _rows_of(project_root, "PUNCHLIST-ARCHIVE.md")


def _statuses(rows):
    """id -> Status cell, for a list of rendered archive rows."""
    return {_cells(row)[0]: _cells(row)[-1] for row in rows}


def _open_statuses(rows):
    """id -> OPEN, for rows of PUNCHLIST.md.

    The open worklist carries no Status column since P0.4 — appearing in it
    *is* the status, and a column whose every cell reads OPEN is four bytes
    per finding spent saying so twice.
    """
    return {_cells(row)[0]: "OPEN" for row in rows}


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
        assert len(_cells(rows[0])) == OPEN_COLUMNS, (
            f"Row did not parse into {OPEN_COLUMNS} columns: {rows[0]}"
        )
        assert "prog \\| head" in rows[0], "The pipe must be escaped, not dropped"

    def test_pipe_in_location_does_not_add_a_column(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(
            binary, root, "BH-002", "ordinary description",
            location="src/x.py:10 | src/y.py:2",
        )
        rows = _data_rows(root)
        assert len(_cells(rows[0])) == OPEN_COLUMNS

    def test_newline_in_description_does_not_split_the_row(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-003", "line one\nline two")

        rows = _data_rows(root)
        assert len(rows) == 1, f"A newline broke one finding into {len(rows)} rows"
        assert len(_cells(rows[0])) == OPEN_COLUMNS

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
            assert len(_cells(row)) == OPEN_COLUMNS, f"Ragged row: {row}"


class TestPunchlistIsOpenWorkOnly:
    """PUNCHLIST.md is the worklist; closed findings render to the archive."""

    def test_the_punchlist_lists_only_open_findings(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-001", "fixed")
        _record_finding(binary, root, "BH-002", "deferred")
        _record_finding(binary, root, "BH-003", "still open")
        _resolve_finding(binary, root, "BH-001")
        _defer_finding(binary, root, "BH-002")

        statuses = _open_statuses(_data_rows(root))
        assert statuses == {"BH-003": "OPEN"}, (
            f"PUNCHLIST.md carries closed work: {statuses}"
        )

    def test_closed_findings_render_to_the_archive(self, rendered_punchlist):
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-001", "fixed")
        _record_finding(binary, root, "BH-002", "deferred")
        _record_finding(binary, root, "BH-003", "still open")
        _resolve_finding(binary, root, "BH-001")
        _defer_finding(binary, root, "BH-002")

        assert _statuses(_archive_rows(root)) == {
            "BH-001": "RESOLVED", "BH-002": "DEFERRED",
        }

    def test_every_finding_is_in_exactly_one_of_the_two_files(self, rendered_punchlist):
        """Splitting one view in two must not lose or duplicate a finding."""
        binary, root = rendered_punchlist
        for n in range(1, 6):
            _record_finding(binary, root, f"BH-00{n}", f"finding {n}")
        _record_finding(binary, root, "BH-001", "re-filed, then resolved")
        _resolve_finding(binary, root, "BH-001")
        _defer_finding(binary, root, "BH-002")

        open_ids = set(_open_statuses(_data_rows(root)))
        archived_ids = set(_statuses(_archive_rows(root)))
        assert not open_ids & archived_ids, (
            f"Findings render in both files: {sorted(open_ids & archived_ids)}"
        )
        assert open_ids | archived_ids == {
            "BH-001", "BH-002", "BH-003", "BH-004", "BH-005",
        }, f"A finding fell between the two views: {open_ids}, {archived_ids}"

    def test_a_finding_deferred_then_fixed_anyway_archives_once_as_resolved(
        self, rendered_punchlist
    ):
        """``fix_commit`` has no ``item_open`` gate, so the two sets overlap.
        Resolved wins, the same precedence STATUS.md counts by."""
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-001", "deferred, then fixed anyway")
        _defer_finding(binary, root, "BH-001")
        _resolve_finding(binary, root, "BH-001")

        assert _data_rows(root) == []
        assert _statuses(_archive_rows(root)) == {"BH-001": "RESOLVED"}

    def test_a_converged_run_still_archives_every_finding_with_its_location(
        self, rendered_punchlist
    ):
        """Recon's cold-file coverage scan reads archived punchlists to decide
        which files were ever audited. A converged run resolves everything, so
        an open-only PUNCHLIST.md archives empty — every one already on disk in
        this repo has zero OPEN rows. The locations have to survive somewhere."""
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-001", "one", location="src/parser.py:88")
        _record_finding(binary, root, "BH-002", "two", location="src/writer.py:12")
        _resolve_finding(binary, root, "BH-001")
        _resolve_finding(binary, root, "BH-002")

        assert _data_rows(root) == [], "converged run leaves open rows"
        archived = "\n".join(_archive_rows(root))
        assert "src/parser.py:88" in archived and "src/writer.py:12" in archived, (
            f"Archived punchlist lost the finding locations:\n{archived}"
        )

    def test_archive_rows_parse_into_six_columns(self, rendered_punchlist):
        """The archive is a table things count off too — same hazards, same rule."""
        binary, root = rendered_punchlist
        _record_finding(binary, root, "BH-001", "breaks on `prog | head` input",
                        location="src/x.py:1 | src/y.py:2")
        _record_finding(binary, root, "BH-002", "line one\nline two")
        _resolve_finding(binary, root, "BH-001")
        _defer_finding(binary, root, "BH-002")

        rows = _archive_rows(root)
        assert len(rows) == 2, f"A hazard split an archived row: {rows}"
        for row in rows:
            assert len(_cells(row)) == ARCHIVE_COLUMNS, f"Ragged row: {row}"


class TestSkillFilesMatchWhatThePunchlistCarries:
    """A trimmed render silently breaks any step that reads what it trimmed."""

    def test_the_cold_file_scan_reads_the_archive(self):
        """`phase-recon.md`'s coverage scan classifies a file as audited if a
        prior punchlist names it. Prior punchlists are converged, so their
        findings are all in the archive."""
        text = os.path.join(
            REPO_ROOT, "skills", "holtz", "references", "phase-recon.md")
        with open(text, encoding="utf-8") as fh:
            scan_lines = [ln for ln in fh.read().splitlines()
                          if "Cold file coverage scan" in ln]
        assert scan_lines, "phase-recon.md no longer has a cold file coverage scan"
        for line in scan_lines:
            assert "PUNCHLIST-ARCHIVE.md" in line, (
                "The cold file coverage scan reads archived PUNCHLIST.md only. "
                "Those render open findings, and a converged run has none — so "
                "every file reads as cold on every later run:\n  " + line
            )

    def test_no_skill_file_reads_the_punchlist_for_resolved_findings(self):
        """Grouping resolved items by root cause is the pattern round's job and
        it used to read this file. It has to query the ledger instead."""
        from pathlib import Path

        offenders = []
        for path in sorted((Path(REPO_ROOT) / "skills").rglob("*.md")):
            if path.name in {"justine-skill.md", "justine.md"}:
                continue  # her punchlist is hand-written and unrendered
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if "docs/holtz/PUNCHLIST.md" not in line:
                    continue
                if "resolved" in line.lower() or "full punchlist" in line.lower():
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno} {line.strip()}")

        assert not offenders, (
            "Skill files expect resolved findings in docs/holtz/PUNCHLIST.md, "
            "which now renders open work only:\n  " + "\n  ".join(offenders) +
            "\n\nUse `findings.py list --all`, which reads the ledger both "
            "views render from."
        )

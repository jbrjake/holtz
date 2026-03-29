"""Tests for validate_merge_report.py."""
from __future__ import annotations

import subprocess
import sys

import pytest

SCRIPT = "enforcement/scripts/validate_merge_report.py"


def _run(path: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, path],
        capture_output=True, text=True,
    )


def test_valid_report(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text(
        "# Merged Punchlist\n\n"
        "## Agreement\n\n"
        "| ID | Description |\n|---|---|\n| BH-001 | test |\n\n"
        "**Agreements:** 3\n\n"
        "## Holtz-Only\n\n"
        "| ID | Description |\n|---|---|\n\n"
        "## Justine-Only\n\n"
        "| ID | Description |\n|---|---|\n\n"
        "## Blind Spot Analysis\n\n"
        "No blind spots identified.\n"
    )
    result = _run(str(report))
    assert result.returncode == 0


def test_missing_agreement_section(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text(
        "# Merged Punchlist\n\n"
        "## Holtz-Only\n\nstuff\n"
        "## Justine-Only\n\nstuff\n"
        "## Blind Spot Analysis\n\nstuff\n"
    )
    result = _run(str(report))
    assert result.returncode != 0
    assert "Agreement" in result.stderr


def test_missing_blind_spot_section(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text(
        "# Merged Punchlist\n\n"
        "## Agreement\n\nstuff\n"
        "## Holtz-Only\n\nstuff\n"
        "## Justine-Only\n\nstuff\n"
    )
    result = _run(str(report))
    assert result.returncode != 0
    assert "Blind Spot" in result.stderr


def test_nonexistent_file():
    result = _run("/nonexistent/path.md")
    assert result.returncode != 0


def test_empty_file(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text("")
    result = _run(str(report))
    assert result.returncode != 0

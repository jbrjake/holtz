"""STATUS.md and PUNCHLIST.md must not disagree about how many findings there are.

Both files are rendered from one ledger, and STATUS.md is where the headline
"N open" is read from. Two defects made its counts wrong:

* ``finding_count`` was ``count(all finding events)`` with no dedupe, while the
  Resolved and Deferred counts one and two lines below it *were* deduped. A
  finding re-filed under an existing id — a correction recorded without
  retracting the original — inflated Total and Open by one each, and PUNCHLIST.md
  rendered one row for it. Two views of the same ledger, different answers.
  This is the defect ``punchlist.md.tera`` was fixed for; it lived in a second
  template that no one checked.
* Open was ``total - resolved - deferred``, which assumes those two sets are
  disjoint. They are not: every deferral transition gates on ``item_open``, but
  ``fix_commit`` does not, so deferring a LOW and later fixing it anyway puts
  one finding in both sets and drives Open below zero.

Both counts are now decided the way PUNCHLIST.md decides each row's Status —
by membership, with resolved taking precedence over deferred — so the two
views agree by construction rather than by two expressions happening to match.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.slow]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
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


def _run(binary, root, *args):
    result = subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, *args],
        capture_output=True, text=True, cwd=root, timeout=30,
    )
    assert result.returncode == 0, f"{' '.join(args)}\n{result.stdout}\n{result.stderr}"
    return result


def _file_finding(binary, root, finding_id, description="a finding", severity="HIGH"):
    _run(
        binary, root, "event", "finding",
        "--field", f"id={finding_id}", "--field", f"severity={severity}",
        "--field", "category=correctness", "--field", "location=src/x.py:10",
        "--field", "perspective=integration", "--field", "predicted_by=none",
        "--field", f"description={description}", *_COMMON,
    )


def _resolve(binary, root, finding_id):
    _run(
        binary, root, "event", "finding_resolved",
        "--field", f"id={finding_id}", "--field", "commit_hash=abc1234", *_COMMON,
    )


def _defer(binary, root, finding_id, reason="low_priority"):
    _run(
        binary, root, "event", "finding_deferred",
        "--field", f"id={finding_id}", "--field", f"reason={reason}", *_COMMON,
    )


def _status_counts(root):
    """The Open/Resolved/Deferred/Total line of the rendered STATUS.md."""
    path = os.path.join(root, "docs", "holtz", "STATUS.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(
        r"\*\*Open:\*\*\s*(-?\d+)\s*\|\s*\*\*Resolved:\*\*\s*(-?\d+)\s*\|"
        r"\s*\*\*Deferred:\*\*\s*(-?\d+)\s*\|\s*\*\*Total:\*\*\s*(-?\d+)",
        text,
    )
    assert match, f"STATUS.md has no findings count line:\n{text}"
    return {
        "open": int(match.group(1)), "resolved": int(match.group(2)),
        "deferred": int(match.group(3)), "total": int(match.group(4)),
    }


def _punchlist_statuses(root):
    """Status cell of every PUNCHLIST.md finding row, keyed by finding id."""
    path = os.path.join(root, "docs", "holtz", "PUNCHLIST.md")
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    statuses = {}
    for line in lines:
        if not line.startswith("| B") or line.startswith("| ID "):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        statuses[cells[0]] = cells[-1]
    return statuses


@pytest.fixture
def ledger(tmp_path):
    binary = _binary()
    root = str(tmp_path)
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        capture_output=True, text=True, cwd=root, timeout=30, check=True,
    )

    def render():
        _run(binary, root, "render")

    return binary, root, render


class TestStatusFindingCounts:

    def test_a_refiled_finding_is_counted_once(self, ledger):
        binary, root, render = ledger
        _file_finding(binary, root, "BH-001", "first filing")
        _file_finding(binary, root, "BH-002", "a different finding")
        _file_finding(binary, root, "BH-001", "corrected filing")
        render()

        counts = _status_counts(root)
        assert counts["total"] == 2, (
            f"A finding filed twice under one id inflated Total: {counts}"
        )
        assert counts["open"] == 2, f"...and Open with it: {counts}"

    def test_status_totals_match_the_punchlist_rows(self, ledger):
        """The two rendered views of one ledger must give the same answer."""
        binary, root, render = ledger
        _file_finding(binary, root, "BH-001", "resolved one")
        _file_finding(binary, root, "BH-002", "deferred one", severity="LOW")
        _file_finding(binary, root, "BH-003", "still open")
        _file_finding(binary, root, "BH-001", "re-filed after a correction")
        _resolve(binary, root, "BH-001")
        _defer(binary, root, "BH-002")
        render()

        counts = _status_counts(root)
        rows = _punchlist_statuses(root)
        assert counts["total"] == len(rows), (
            f"STATUS.md Total {counts['total']} vs {len(rows)} PUNCHLIST.md rows"
        )
        for key, label in (("open", "OPEN"), ("resolved", "RESOLVED"),
                           ("deferred", "DEFERRED")):
            expected = sum(1 for status in rows.values() if status == label)
            assert counts[key] == expected, (
                f"STATUS.md {key}={counts[key]} but PUNCHLIST.md has "
                f"{expected} {label} rows: {rows}"
            )

    def test_a_finding_both_deferred_and_resolved_does_not_go_negative(self, ledger):
        """Deferring a LOW and fixing it anyway is legal — fix_commit has no
        item_open gate — so the two sets overlap and subtraction underflows."""
        binary, root, render = ledger
        _file_finding(binary, root, "BH-001", "deferred, then fixed anyway",
                      severity="LOW")
        _defer(binary, root, "BH-001")
        _resolve(binary, root, "BH-001")
        render()

        counts = _status_counts(root)
        assert counts["open"] >= 0, f"Open count underflowed: {counts}"
        assert counts["total"] == 1, counts
        assert counts["open"] == 0, counts
        assert counts["resolved"] + counts["deferred"] == 1, (
            f"One finding must be counted in exactly one bucket: {counts}"
        )

    def test_counts_agree_when_a_finding_is_in_both_sets(self, ledger):
        """The overlap case must also leave the two views agreeing."""
        binary, root, render = ledger
        _file_finding(binary, root, "BH-001", "both", severity="LOW")
        _file_finding(binary, root, "BH-002", "open")
        _defer(binary, root, "BH-001")
        _resolve(binary, root, "BH-001")
        render()

        counts = _status_counts(root)
        rows = _punchlist_statuses(root)
        assert counts["total"] == len(rows) == 2
        for key, label in (("open", "OPEN"), ("resolved", "RESOLVED"),
                           ("deferred", "DEFERRED")):
            expected = sum(1 for status in rows.values() if status == label)
            assert counts[key] == expected, (
                f"{key}={counts[key]} but PUNCHLIST.md shows {expected} {label}: {rows}"
            )

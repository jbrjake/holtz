"""`findings.py` is the fix loop's worklist lookup, so it must agree with the render.

Before this script the fix loop was told to run
``validate_punchlist.py <path> --filter-status OPEN …`` against
``docs/holtz/PUNCHLIST.md``. That parser expects ``### BH-NNN:`` prose blocks;
the render emits a six-column table. The mandated command exits
``ERROR: No punchlist items found`` on the auditor's own punchlist, which is why
one run wrote a replacement from scratch in three separate sessions.

`findings.py` reads the ledger the punchlist is a view of, applying the same two
rules ``punchlist.md.tera`` renders by — last filing wins per id, resolved
before deferred. These tests pin that agreement against the real binary, since
"the script and the template both got it right" is the only property worth
having.
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
SCRIPT = os.path.join(REPO_ROOT, "skills", "holtz", "scripts", "findings.py")
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
def ledger(tmp_path):
    binary = _binary()
    root = str(tmp_path)
    subprocess.run(
        [binary, "--config-dir", CONFIG_DIR, "init"],
        capture_output=True, text=True, cwd=root, timeout=30, check=True,
    )

    def sah(*args):
        result = subprocess.run(
            [binary, "--config-dir", CONFIG_DIR, *args],
            capture_output=True, text=True, cwd=root, timeout=30,
        )
        assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"

    def file_finding(finding_id, description="a finding", severity="HIGH",
                     location="src/x.py:10"):
        sah("event", "finding", "--field", f"id={finding_id}",
            "--field", f"severity={severity}", "--field", "category=correctness",
            "--field", f"location={location}", "--field", "perspective=integration",
            "--field", "predicted_by=none", "--field", f"description={description}",
            *_COMMON)

    def resolve(finding_id):
        sah("event", "finding_resolved", "--field", f"id={finding_id}",
            "--field", "commit_hash=abc1234", *_COMMON)

    def defer(finding_id):
        sah("event", "finding_deferred", "--field", f"id={finding_id}",
            "--field", "reason=low_priority", *_COMMON)

    def run(*args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            capture_output=True, text=True, cwd=root, timeout=60,
        )

    def punchlist_statuses():
        """Both rendered tables: PUNCHLIST.md is the open half, the archive the
        closed half, and together they are every finding on the ledger."""
        sah("render")
        out = {}
        for basename in ("PUNCHLIST.md", "PUNCHLIST-ARCHIVE.md"):
            path = os.path.join(root, "docs", "holtz", basename)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            for line in lines:
                if not line.startswith("| B"):
                    continue
                cells = [c.strip()
                         for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                out[cells[0]] = cells[-1]
        return out

    return file_finding, resolve, defer, run, punchlist_statuses


def _ids(stdout: str) -> list[str]:
    return re.findall(r"^(B[HJ]-\d{3})\b", stdout, re.MULTILINE)


class TestFindingsList:

    def test_list_shows_only_open_findings(self, ledger):
        file_finding, resolve, defer, run, _ = ledger
        file_finding("BH-001", "fixed one")
        file_finding("BH-002", "deferred one")
        file_finding("BH-003", "still open")
        resolve("BH-001")
        defer("BH-002")

        result = run("list")
        assert result.returncode == 0, result.stderr
        assert _ids(result.stdout) == ["BH-003"]

    def test_all_includes_resolved_and_deferred(self, ledger):
        file_finding, resolve, defer, run, _ = ledger
        file_finding("BH-001")
        file_finding("BH-002")
        resolve("BH-001")

        result = run("list", "--all")
        assert sorted(_ids(result.stdout)) == ["BH-001", "BH-002"]
        assert "RESOLVED" in result.stdout

    def test_a_refiled_finding_appears_once_with_its_latest_text(self, ledger):
        """Same dedupe rule the punchlist renders by."""
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "first filing")
        file_finding("BH-001", "corrected filing")

        result = run("list")
        assert _ids(result.stdout) == ["BH-001"]
        assert "corrected filing" in result.stdout
        assert "first filing" not in result.stdout

    def test_status_matches_the_rendered_punchlist_exactly(self, ledger):
        """The script and the template must not disagree about any finding."""
        file_finding, resolve, defer, run, punchlist_statuses = ledger
        file_finding("BH-001", "resolved")
        file_finding("BH-002", "deferred", severity="LOW")
        file_finding("BH-003", "open")
        file_finding("BJ-004", "justine's, merged in", severity="MEDIUM")
        file_finding("BH-001", "re-filed then resolved")
        resolve("BH-001")
        defer("BH-002")

        rendered = punchlist_statuses()
        result = run("list", "--all")
        assert result.returncode == 0, result.stderr

        reported = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^(B[HJ]-\d{3})\s+\S+\s+(\S+)", line)
            if match:
                reported[match.group(1)] = match.group(2)
        assert reported == rendered, (
            f"findings.py says {reported}, PUNCHLIST.md says {rendered}"
        )

    def test_justine_ids_survive_the_merge(self, ledger):
        """Merge records her findings under BJ- ids; nothing renumbers them."""
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "holtz found this")
        file_finding("BJ-007", "justine found this")

        result = run("list")
        assert sorted(_ids(result.stdout)) == ["BH-001", "BJ-007"]

    def test_severity_filter(self, ledger):
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "critical one", severity="CRITICAL")
        file_finding("BH-002", "low one", severity="LOW")

        result = run("list", "--severity", "CRITICAL")
        assert _ids(result.stdout) == ["BH-001"]

    def test_severity_orders_the_listing(self, ledger):
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "low", severity="LOW")
        file_finding("BH-002", "critical", severity="CRITICAL")
        file_finding("BH-003", "medium", severity="MEDIUM")

        result = run("list")
        assert _ids(result.stdout) == ["BH-002", "BH-003", "BH-001"]

    def test_count(self, ledger):
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001")
        file_finding("BH-002")
        assert run("list", "--count").stdout.strip() == "2"

    def test_a_pipe_in_a_description_does_not_break_the_line(self, ledger):
        """The render escapes pipes; this reads the ledger, so it needs none."""
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "breaks on `prog | head` input")
        result = run("list")
        assert len(_ids(result.stdout)) == 1
        assert "prog | head" in result.stdout

    def test_a_newline_in_a_description_stays_on_one_line(self, ledger):
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "line one\nline two")
        result = run("list")
        body = [ln for ln in result.stdout.splitlines() if ln.startswith("BH-")]
        assert len(body) == 1, f"description newline split the row: {body}"
        assert "line one line two" in body[0]


class TestFindingsShow:

    def test_show_prints_the_full_record(self, ledger):
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "a long and detailed description of the defect")

        result = run("show", "BH-001")
        assert result.returncode == 0, result.stderr
        assert "a long and detailed description of the defect" in result.stdout
        assert "status: OPEN" in result.stdout

    def test_show_reports_an_unknown_id(self, ledger):
        _, _, _, run, _ = ledger
        result = run("show", "BH-999")
        assert result.returncode != 0
        assert "BH-999" in result.stderr

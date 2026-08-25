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
            "--field", "predicted_by=none", "--field", "reachability=user_reachable",
            "--field", f"description={description}",
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
        closed half, and together they are every finding on the ledger.

        PUNCHLIST.md carries no Status column since P0.4 — appearing in it *is*
        the status, so a row read out of it is OPEN by construction. The
        archive still names the status it closed with, in its last cell.
        """
        sah("render")
        out = {}
        for basename, status in (("PUNCHLIST.md", "OPEN"), ("PUNCHLIST-ARCHIVE.md", None)):
            path = os.path.join(root, "docs", "holtz", basename)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            for line in lines:
                if not line.startswith("| B"):
                    continue
                cells = [c.strip()
                         for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                out[cells[0]] = status if status else cells[-1]
        return out

    return file_finding, resolve, defer, run, punchlist_statuses


def _ids(stdout: str) -> list[str]:
    return re.findall(r"^(B[HJ]-\d{3})\b", stdout, re.MULTILINE)


class TestThePunchlistRendersOneLinePerFinding:
    """P0.4: 81k tokens of punchlist, reloaded on every fix.

    The render carried `category` and `perspective` on every row — neither is
    branched on in the fix loop — and the whole description. The clause is one
    line each: id, severity, `file:line`, and a summary capped at 12 words.
    Truncation happens here, in the template, against the description the
    agent already wrote; a second agent-written summary field would be two
    texts for one fact.
    """

    def _rows(self, root):
        path = os.path.join(root, "docs", "holtz", "PUNCHLIST.md")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        return [
            [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            for line in lines if line.startswith("| B")
        ]

    def test_the_summary_is_capped_at_twelve_words(self, ledger, tmp_path):
        file_finding, _, _, _, punchlist_statuses = ledger
        long_description = " ".join(f"word{n}" for n in range(1, 41))
        file_finding("BH-001", long_description)
        punchlist_statuses()  # renders

        rows = self._rows(str(tmp_path))
        assert len(rows) == 1, f"expected one row, got {rows}"
        summary = rows[0][-1]
        assert len(summary.split()) <= 12, f"summary is {len(summary.split())} words: {summary}"
        assert summary.startswith("word1 "), "the summary is not the description's own opening"
        assert "word13" not in summary, "truncation did not happen"

    def test_a_short_description_is_not_padded_or_mangled(self, ledger, tmp_path):
        file_finding, _, _, _, punchlist_statuses = ledger
        file_finding("BH-002", "off-by-one in the retry backoff")
        punchlist_statuses()

        rows = self._rows(str(tmp_path))
        assert rows[0][-1] == "off-by-one in the retry backoff"

    def test_the_row_carries_the_four_fields_and_no_others(self, ledger, tmp_path):
        file_finding, _, _, _, punchlist_statuses = ledger
        file_finding("BH-003", "a finding", severity="CRITICAL", location="src/y.py:42")
        punchlist_statuses()

        rows = self._rows(str(tmp_path))
        assert rows[0] == ["BH-003", "CRITICAL", "src/y.py:42", "a finding"], (
            "the row is not (id, severity, file:line, summary) — category and "
            "perspective are the columns the fix loop never reads"
        )


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


class TestAuditedFiles:
    """Recon decides which files are cold from the ledger, not from a render.

    The coverage scan classified a file as audited if a prior punchlist named
    it. Since P0.4 the punchlist renders open findings only, and a converged
    run has none — so the scan was reading a file that is empty exactly when
    the run it describes went well, and the archive it fell back to is a
    second rendered view of data the ledger already holds. Every run's ledger
    is still on disk; this reads all of them.
    """

    def _paths(self, stdout: str) -> set[str]:
        return {line.strip() for line in stdout.splitlines() if line.strip()}

    def test_a_closed_finding_still_marks_its_file_audited(self, ledger):
        """The case the archive read existed for: a converged run's files."""
        file_finding, resolve, defer, run, _ = ledger
        file_finding("BH-001", "open", location="src/parser.py:88")
        file_finding("BH-002", "resolved", location="src/writer.py:12")
        resolve("BH-002")
        file_finding("BH-003", "deferred", location="src/reader.py:3")
        defer("BH-003")

        result = run("audited-files")
        assert result.returncode == 0, result.stderr
        assert self._paths(result.stdout) == {
            "src/parser.py", "src/writer.py", "src/reader.py",
        }

    def test_every_file_in_a_multi_file_location_counts(self, ledger):
        """`location` is free text and runs write several paths into it."""
        file_finding, _, _, run, _ = ledger
        file_finding("BH-001", "two files", location="src/a.py:1,src/b.py:2")
        file_finding("BH-002", "two more", location="src/c.py:1 | src/d.py")

        result = run("audited-files")
        assert result.returncode == 0, result.stderr
        assert self._paths(result.stdout) == {
            "src/a.py", "src/b.py", "src/c.py", "src/d.py",
        }

    def test_prior_runs_count_even_though_they_are_other_ledgers(self, ledger, tmp_path):
        """Each run gets its own ledger, so coverage that stopped at the active
        one would call every file cold on the first round of every run."""
        file_finding, _, _, run, _ = ledger
        binary = _binary()
        file_finding("BH-001", "last run's finding", location="src/old.py:1")
        subprocess.run(
            [binary, "--config-dir", CONFIG_DIR, "ledger", "create",
             "--from", "run", "2", "--activate"],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=30, check=True,
        )
        file_finding("BH-002", "this run's finding", location="src/new.py:1")

        listed = run("list")
        assert _ids(listed.stdout) == ["BH-002"], (
            "the active ledger should carry only this run's finding"
        )
        result = run("audited-files")
        assert result.returncode == 0, result.stderr
        assert self._paths(result.stdout) == {"src/old.py", "src/new.py"}

    def test_a_project_with_no_ledger_reports_nothing(self, tmp_path):
        """First run: no ledger anywhere, so every file is cold. An empty
        listing says that; an error would stop recon on the run that needs
        the inventory most."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "audited-files"],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == ""

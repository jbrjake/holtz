"""Tests for legacy migration script."""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

# Add scripts/ to path so we can import migrate_legacy
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from migrate_legacy import (  # noqa: E402
    ARCHIVE_MAP,
    JUSTINE_MAP,
    build_project_ledger,
    migrate_directory,
    parse_audit_file,
    parse_history_json,
    parse_merge_report,
    parse_postmortem,
    parse_punchlist,
    parse_recon_dir,
    parse_status,
    parse_summary,
)

# ---------------------------------------------------------------------------
# Task 3.1: Archive mapping tests
# ---------------------------------------------------------------------------


def test_archive_mapping_complete():
    assert len(ARCHIVE_MAP) == 30


def test_archive_mapping_unique_run_numbers():
    run_numbers = [entry["run"] for entry in ARCHIVE_MAP.values()]
    assert len(run_numbers) == len(set(run_numbers))


def test_justine_matching():
    assert JUSTINE_MAP["justine-2026-03-22"] == 19
    assert JUSTINE_MAP["justine-2026-03-25-run19"] == 30


# ---------------------------------------------------------------------------
# Task 3.2: Punchlist parser tests
# ---------------------------------------------------------------------------

SAMPLE_TABLE_PUNCHLIST = """\
# Punchlist

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:108 | public-contract | Pattern count stale | OPEN |
| BH-002 | test/gap | tests/test_foo.py | component | Missing edge case | RESOLVED |
"""

SAMPLE_BLOCK_PUNCHLIST = """\
# Punchlist

### BH-001: Pattern count stale
**Severity:** HIGH
**Category:** doc/drift
**Location:** README.md:108
**Perspective:** public-contract
**Status:** OPEN
**Problem:** Pattern count is outdated

### BH-002: Missing edge case
**Severity:** HIGH
**Category:** test/gap
**Location:** tests/test_foo.py
**Perspective:** component
**Status:** RESOLVED
**Fix Commit:** abc1234
"""


def test_parse_table_punchlist():
    events = parse_punchlist(SAMPLE_TABLE_PUNCHLIST, run="9", auditor="holtz", source="PUNCHLIST.md")
    findings = [e for e in events if e["type"] == "finding"]
    resolved = [e for e in events if e["type"] == "finding_resolved"]
    assert len(findings) == 2
    assert findings[0]["fields"]["id"] == "BH-001"
    assert findings[0]["fields"]["severity"] == "HIGH"
    assert findings[0]["fields"]["_migrated"] == "true"
    assert len(resolved) == 1
    assert resolved[0]["fields"]["id"] == "BH-002"


def test_parse_block_punchlist():
    events = parse_punchlist(SAMPLE_BLOCK_PUNCHLIST, run="1", auditor="holtz", source="BUG-HUNTER-PUNCHLIST.md")
    findings = [e for e in events if e["type"] == "finding"]
    resolved = [e for e in events if e["type"] == "finding_resolved"]
    assert len(findings) == 2
    assert findings[0]["fields"]["id"] == "BH-001"
    assert len(resolved) == 1
    assert resolved[0]["fields"]["commit_hash"] == "abc1234"


def test_punchlist_breadcrumbs():
    events = parse_punchlist(SAMPLE_TABLE_PUNCHLIST, run="9", auditor="holtz", source="PUNCHLIST.md")
    for e in events:
        assert e["fields"]["project"] == "holtz"
        assert e["fields"]["run"] == "9"
        assert e["fields"]["auditor"] == "holtz"


# ---------------------------------------------------------------------------
# Task 3.3: Recon parser tests
# ---------------------------------------------------------------------------

SAMPLE_RECON_LETTERED = {
    "0a-project-overview.md": "# Project Overview\n\nFour layers of architecture.",
    "0g-recon-summary.md": "# Recon Summary\n\n## Architecture\nFour layers...\n## Drift\n2 drifted nodes",
    "0h-predictions.md": "# Predictions\n\n| # | Target | Confidence | Basis |\n|---|--------|------------|-------|\n| 1 | README | HIGH | stale count |",
}


def test_parse_recon_lettered():
    events = parse_recon_dir(SAMPLE_RECON_LETTERED, run="19", auditor="holtz")
    findings = [e for e in events if e["type"] == "recon_finding"]
    predictions = [e for e in events if e["type"] == "prediction"]
    assert len(findings) >= 2
    assert findings[0]["fields"]["step"] in ("0", "3", "4")
    assert len(predictions) >= 1
    assert predictions[0]["fields"]["confidence"] == "HIGH"


def test_parse_recon_numbered():
    files = {
        "step0-project-overview.md": "# Overview\n\nContent here",
        "step4-predictions.md": "# Predictions\n\n| # | Target | Confidence | Basis |\n|---|--------|------------|-------|\n| 1 | auth | MEDIUM | new code |",
    }
    events = parse_recon_dir(files, run="20", auditor="holtz")
    findings = [e for e in events if e["type"] == "recon_finding"]
    assert any(e["fields"]["step"] == "0" for e in findings)


# ---------------------------------------------------------------------------
# Task 3.4: Audit parser tests
# ---------------------------------------------------------------------------

SAMPLE_AUDIT_CLAIMS = """\
# Documentation Claims Audit

| Source | Claim | Verdict | Evidence |
|--------|-------|---------|----------|
| README.md:15 | Supports 13 lenses | VERIFIED | lens-registry.md lists 13 |
| README.md:22 | 647 tests | OVERSTATED | Actual count 585 |
"""


def test_parse_audit_claims():
    events = parse_audit_file("1-doc-claims.md", SAMPLE_AUDIT_CLAIMS, run="19", auditor="holtz")
    claims = [e for e in events if e["type"] == "audit_claim"]
    assert len(claims) == 2
    assert claims[0]["fields"]["verdict"] == "VERIFIED"
    assert claims[1]["fields"]["verdict"] == "OVERSTATED"


# ---------------------------------------------------------------------------
# Task 3.5: Remaining parser tests
# ---------------------------------------------------------------------------

SAMPLE_SUMMARY = """\
# Audit Summary

## Results
Total findings: 12
Resolved: 10

## Prediction Accuracy

| # | Target | Outcome |
|---|--------|---------|
| 1 | auth | CONFIRMED |
| 2 | cache | UNCONFIRMED |

## Recommendations
Fix the auth module first.
"""

SAMPLE_MERGE_REPORT = """\
# Merge Report
Agreements: 5
Holtz-only: 3
Justine-only: 2
Contradictions: 1
"""

SAMPLE_STATUS = """\
# Status
- [x] Step 0: Project overview
- [x] Step 1: Toolchain survey
- [ ] Step 2: Code signals
"""

SAMPLE_HISTORY = json.dumps([
    {"open": 5, "resolved": 2, "test_count": 100, "tests_passed": True},
    {"open": 3, "resolved": 4, "test_count": 102, "tests_passed": True},
])


def test_parse_summary():
    events = parse_summary(SAMPLE_SUMMARY, run="19", auditor="holtz", source="SUMMARY.md")
    summaries = [e for e in events if e["type"] == "run_summary"]
    outcomes = [e for e in events if e["type"] == "prediction_outcome"]
    assert len(summaries) == 1
    assert summaries[0]["fields"]["total_findings"] == "12"
    assert len(outcomes) == 2


def test_parse_merge_report():
    events = parse_merge_report(SAMPLE_MERGE_REPORT, run="19", auditor="holtz", source="MERGE-REPORT.md")
    assert len(events) == 1
    assert events[0]["fields"]["agreements"] == "5"


def test_parse_status():
    events = parse_status(SAMPLE_STATUS, run="19", auditor="holtz", source="STATUS.md")
    assert len(events) == 2  # only [x] items


def test_parse_history_json():
    events = parse_history_json(SAMPLE_HISTORY, run="19", auditor="holtz", source="HISTORY.json")
    assert len(events) == 2
    assert events[0]["fields"]["iteration"] == "1"
    assert events[1]["fields"]["open"] == "3"


def test_parse_postmortem():
    events = parse_postmortem("# Postmortem\n\nLessons learned.", run="19", auditor="holtz", source="postmortem.md")
    assert len(events) == 1
    assert events[0]["type"] == "run_postmortem"


# ---------------------------------------------------------------------------
# Task 3.6: Orchestrator tests
# ---------------------------------------------------------------------------


def test_migrate_directory(tmp_path):
    run_dir = tmp_path / "2026-03-22-run9"
    run_dir.mkdir()
    (run_dir / "PUNCHLIST.md").write_text(SAMPLE_TABLE_PUNCHLIST)
    (run_dir / "STATUS.md").write_text(SAMPLE_STATUS)
    recon = run_dir / "recon"
    recon.mkdir()
    (recon / "step0-project-overview.md").write_text("# Overview\n\nContent here")

    events = migrate_directory(run_dir, run=20, auditor="holtz", project="holtz")
    assert len(events) > 0
    for e in events:
        assert e["fields"]["project"] == "holtz"
        assert e["fields"]["run"] == "20"
        assert e["fields"]["auditor"] == "holtz"
        assert e["fields"]["_migrated"] == "true"


def test_migrate_nested_justine(tmp_path):
    run_dir = tmp_path / "2026-03-22-run8"
    run_dir.mkdir()
    justine = run_dir / "justine"
    justine.mkdir()
    (justine / "PUNCHLIST.md").write_text(SAMPLE_TABLE_PUNCHLIST.replace("BH-", "BJ-"))
    events = migrate_directory(run_dir, run=19, auditor="holtz", project="holtz")
    justine_events = [e for e in events if e["fields"]["auditor"] == "justine"]
    assert len(justine_events) > 0


def test_parse_summary_greedy_regex():
    """BH-017: parse_summary must extract total findings, not total resolved."""
    content = """# Summary

Total Resolved: 7
Total Findings: 10
"""
    events = parse_summary(content, run="20", auditor="holtz", source="SUMMARY.md")
    summaries = [e for e in events if e["type"] == "run_summary"]
    assert len(summaries) == 1
    assert summaries[0]["fields"]["total_findings"] == "10", (
        f"Greedy regex extracted {summaries[0]['fields']['total_findings']} "
        "instead of 10 — matched 'Total Resolved' before 'Total Findings'"
    )


def test_extract_field_ignores_code_fences():
    """BH-016: _extract_field must not match inside code fences."""
    from migrate_legacy import _extract_field
    block = """**Severity:** HIGH

```
**Severity:** LOW
```

**Status:** OPEN
"""
    assert _extract_field(block, "Severity") == "HIGH"
    assert _extract_field(block, "Status") == "OPEN"


def test_parse_predictions_ignores_code_fences():
    """BH-016: _parse_predictions must not extract from fenced blocks."""
    from migrate_legacy import _parse_predictions
    content = """# Predictions

| # | Target | Confidence | Basis |
|---|--------|-----------|-------|
| 1 | auth.py | HIGH | churn data |

```
| 2 | fake.py | MEDIUM | not real |
```
"""
    events = _parse_predictions(content, run="20", auditor="holtz", source="step4.md", project="holtz")
    assert len(events) == 1
    assert events[0]["fields"]["target"] == "auth.py"


def test_build_project_ledger():
    events = build_project_ledger(
        runs=[(1, "holtz"), (2, "holtz"), (3, "holtz")],
        project="holtz",
    )
    registered = [e for e in events if e["type"] == "run_registered"]
    assert len(registered) == 3
    checkpoints = [e for e in events if e["type"] == "_checkpoint"]
    assert len(checkpoints) >= 1


# ---------------------------------------------------------------------------
# W27 / item 45: `--all` keeps each run in its own ledger
# ---------------------------------------------------------------------------
#
# `--all` printed every run's events as one stream, and the usage line invited
# piping it into a single `sahjhan ledger import` — which creates ONE ledger,
# so every run's BH-001 landed in it and D25's by-id latest-wins collapsed them.

_SCRIPT = Path(__file__).parent.parent / "scripts" / "migrate_legacy.py"
_TWO_RUNS = ("2026-03-19-run2", "2026-03-20-run2")  # ARCHIVE_MAP runs 12 and 13


def _archive(root: Path) -> Path:
    archive = root / "archive"
    for dirname in _TWO_RUNS:
        run_dir = archive / dirname
        run_dir.mkdir(parents=True)
        (run_dir / "PUNCHLIST.md").write_text(
            SAMPLE_TABLE_PUNCHLIST.replace("Pattern count stale", f"stale in {dirname}")
        )
    return archive


def _migrate_all(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--all", *extra],
        capture_output=True, text=True, timeout=60,
    )


def test_all_refuses_to_write_one_combined_stream(tmp_path):
    result = _migrate_all("--archive-root", str(_archive(tmp_path)))
    assert result.returncode != 0
    assert result.stdout == "", "no events may reach a stream a single import would merge"
    assert "--out-dir" in result.stderr


def test_all_writes_one_file_per_run(tmp_path):
    out = tmp_path / "out"
    result = _migrate_all("--archive-root", str(_archive(tmp_path)), "--out-dir", str(out))
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in out.iterdir()) == ["run-12.jsonl", "run-13.jsonl"]
    for name, dirname in (("run-12.jsonl", _TWO_RUNS[0]), ("run-13.jsonl", _TWO_RUNS[1])):
        events = [json.loads(line) for line in (out / name).read_text().splitlines()]
        assert {e["fields"]["run"] for e in events} == {name[4:6]}
        ids = [e["fields"]["description"] for e in events
               if e["type"] == "finding" and e["fields"]["id"] == "BH-001"]
        assert ids == [f"stale in {dirname}"]


def test_the_same_id_in_two_runs_stays_two_findings(tmp_path):
    """V5, end to end: each file into its own ledger with the real engine."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "enforcement" / "hooks"))
    from _resolve import ensure_sahjhan

    binary = ensure_sahjhan()
    if not binary:
        import pytest
        pytest.skip("sahjhan binary not available")
    config = str(Path(__file__).parent.parent / "enforcement")
    out = tmp_path / "out"
    assert _migrate_all("--archive-root", str(_archive(tmp_path)),
                        "--out-dir", str(out)).returncode == 0
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run([binary, "--config-dir", config, "init"], cwd=project,
                   check=True, capture_output=True)
    seen = {}
    for run in ("12", "13"):
        with open(out / f"run-{run}.jsonl") as stream:
            subprocess.run(
                [binary, "--config-dir", config, "ledger", "import",
                 "--name", f"run-{run}", "--path", str(project / f"run-{run}.jsonl")],
                cwd=project, stdin=stream, check=True, capture_output=True,
            )
        rows = subprocess.run(
            [binary, "--config-dir", config, "--ledger", f"run-{run}", "query",
             "SELECT description FROM events WHERE type='finding' AND id='BH-001'",
             "--format", "json"],
            cwd=project, check=True, capture_output=True, text=True,
        ).stdout
        seen[run] = [r["description"] for r in json.loads(rows)]
    assert seen == {"12": [f"stale in {_TWO_RUNS[0]}"], "13": [f"stale in {_TWO_RUNS[1]}"]}


def test_the_usage_line_teaches_the_per_run_import():
    import migrate_legacy

    usage = [
        ln for ln in (migrate_legacy.__doc__ or "").splitlines()
        if "migrate_legacy.py" in ln and "--all" in ln
    ]
    assert usage and all("--out-dir" in ln for ln in usage), usage


# ---------------------------------------------------------------------------
# W27 / item 45 step 3: emit values the schema accepts (D-q, RULED 2026-09-23)
# ---------------------------------------------------------------------------
#
# `step` and `commit_hash` are required and pattern-bound, so the migration
# emitted `""` for both on every finding and resolution — accepted only because
# `ledger import` validates nothing.


def _by_type(events, event_type):
    return [e["fields"] for e in events if e["type"] == event_type]


def test_a_finding_records_the_audit_step_and_a_resolution_the_fix_loop_step():
    for sample in (SAMPLE_TABLE_PUNCHLIST, SAMPLE_BLOCK_PUNCHLIST):
        events = parse_punchlist(sample, run="9", auditor="holtz", source="PUNCHLIST.md")
        assert {f["step"] for f in _by_type(events, "finding")} == {"7"}
        assert {f["step"] for f in _by_type(events, "finding_resolved")} == {"10"}


def test_a_resolution_with_no_recorded_commit_carries_the_unknown_sentinel():
    events = parse_punchlist(SAMPLE_TABLE_PUNCHLIST, run="9", auditor="holtz", source="PUNCHLIST.md")
    assert [f["commit_hash"] for f in _by_type(events, "finding_resolved")] == ["0000000"]
    no_commit = SAMPLE_BLOCK_PUNCHLIST.replace("**Fix Commit:** abc1234\n", "")
    events = parse_punchlist(no_commit, run="1", auditor="holtz", source="PUNCHLIST.md")
    assert [f["commit_hash"] for f in _by_type(events, "finding_resolved")] == ["0000000"]


def test_a_recorded_commit_is_kept_out_of_the_prose_around_it():
    wrapped = SAMPLE_BLOCK_PUNCHLIST.replace("abc1234", "`abc1234` (rebased onto dev)")
    events = parse_punchlist(wrapped, run="1", auditor="holtz", source="PUNCHLIST.md")
    assert [f["commit_hash"] for f in _by_type(events, "finding_resolved")] == ["abc1234"]


def test_a_prose_severity_keeps_its_leading_word():
    prose = SAMPLE_BLOCK_PUNCHLIST.replace(
        "### BH-001: Pattern count stale\n**Severity:** HIGH",
        "### BH-001: Pattern count stale\n**Severity:** LOW (upgraded from MEDIUM per Justine merge)",
    )
    events = parse_punchlist(prose, run="1", auditor="holtz", source="PUNCHLIST.md")
    assert [f["severity"] for f in _by_type(events, "finding")] == ["LOW", "HIGH"]


# `_parse_claims_table` read column 3 of any row as the verdict whatever the
# header said, so most of what it emitted were locations, labels and counts.
# D-q′ and D-u (RULED 2026-09-23): read the header, map the verdict words the
# archive uses, and skip — counted — what is not a claim or carries no verdict.


def _claims(table: str) -> list[dict]:
    events = parse_audit_file("1-doc-claims.md", table, run="9", auditor="holtz")
    return _by_type(events, "audit_claim")


@pytest.mark.parametrize(("cell", "verdict"), [
    ("VERIFIED (rounded)", "VERIFIED"),
    ("TRUE", "VERIFIED"),
    ("YES", "VERIFIED"),
    ("PASS", "VERIFIED"),
    ("OK (matches #13)", "VERIFIED"),
    ("Verified", "VERIFIED"),
    ("confirmed in code", "VERIFIED"),
    ("NO", "FALSE"),
    ("**FALSE** — off by 24", "FALSE"),
    ("FAIL — recommendation-escalation.md not counted", "FALSE"),
    ("DRIFT (minor)", "FALSE"),
    ("UNDERSTATED (missing 2) → BH-001", "FALSE"),
    ("STALE — run 12 completed, now run 13", "FALSE"),
    ("PARTIAL", "OVERSTATED"),
    ("**PARTIAL** — convention violated in some places", "OVERSTATED"),
    ("OVERSTATED → BH-004", "OVERSTATED"),
    ("MISSING", "MISSING"),
])
def test_every_ruled_verdict_word_maps(cell, verdict):
    table = f"| # | Claim | Location | Verdict | Notes |\n|---|---|---|---|---|\n| 1 | c | L1 | {cell} | n |\n"
    assert [c["verdict"] for c in _claims(table)] == [verdict]


def test_a_claims_table_is_read_by_its_header():
    table = (
        "| # | Claim | Location | Status | Notes |\n"
        "|---|-------|----------|--------|-------|\n"
        '| 7 | "13 lenses" | README:15 | VERIFIED | lens-registry.md lists 13 |\n'
    )
    [claim] = _claims(table)
    assert claim["claim"] == '"13 lenses"'
    assert claim["source"] == "README:15"
    assert claim["verdict"] == "VERIFIED"
    assert "lens-registry.md lists 13" in claim["evidence"]


def test_status_is_the_verdict_when_a_table_also_has_verified():
    table = (
        "| # | Claim | Verified | Status |\n"
        "|---|-------|----------|--------|\n"
        "| 17 | version: 0.3.1 | Matches | PASS |\n"
    )
    [claim] = _claims(table)
    assert claim["verdict"] == "VERIFIED"
    assert "Matches" in claim["evidence"]


def test_an_escaped_pipe_stays_inside_its_cell():
    table = (
        "| # | Claim | Actual | Verdict |\n"
        "|---|-------|--------|---------|\n"
        '| 3 | "13 reference docs" | ls references/*.md \\| grep -v backstory = 13 | TRUE |\n'
    )
    [claim] = _claims(table)
    assert claim["verdict"] == "VERIFIED"
    assert "ls references/*.md | grep -v backstory = 13" in claim["evidence"]


def test_a_table_with_no_verdict_column_is_skipped_and_counted(capsys):
    table = (
        "| Result | Count |\n|---|---|\n| PASS | 30 |\n| FAIL | 2 |\n\n"
        "| # | Claim | Test exists? | Notes |\n|---|---|---|---|\n| 1 | c | yes | n |\n"
    )
    assert _claims(table) == []
    assert "3 rows in tables with no verdict column" in capsys.readouterr().err


def test_a_row_with_no_verdict_word_is_skipped_and_counted(capsys):
    table = (
        "| # | Claim | Location | Status |\n|---|---|---|---|\n"
        "| 1 | a | L1 | NEEDS CHECK |\n| 2 | b | L2 | N/A |\n"
        "| 3 | c | L3 | See #8/#9 above |\n| 4 | d | L4 | VERIFIED |\n"
    )
    assert [c["claim"] for c in _claims(table)] == ["d"]
    assert "3 rows with no verdict word" in capsys.readouterr().err


_REPO = Path(__file__).parent.parent
# Written by the engine itself, so events.toml declares no schema for them.
_ENGINE_EVENTS = {"state_transition"}


def _schema_failures(events: list[dict], declared: dict) -> Counter[str]:
    """Every (type, field) an event fails against its events.toml declaration."""
    import re

    failures: Counter[str] = Counter()
    for event in events:
        spec = declared.get(event["type"])
        if spec is None:
            if event["type"] not in _ENGINE_EVENTS:
                failures[f"{event['type']}: undeclared"] += 1
            continue
        for field in spec["fields"]:
            value = event["fields"].get(field["name"])
            if value is None:
                if not field.get("optional"):
                    failures[f"{event['type']}.{field['name']}: missing"] += 1
            elif field.get("pattern") and not re.search(field["pattern"], value):
                failures[f"{event['type']}.{field['name']}: {value[:40]!r}"] += 1
    return failures


def test_every_migrated_event_validates_against_events_toml(tmp_path):
    """V4: field by field over every archive, not through a lax import.

    "The archive migrated" is judged per mapped directory this checkout has.
    `recon/` is gitignored, so a clean clone holds fewer mapped runs than a
    working copy, and no single event count is right for both.
    """
    import tomllib

    archive = _REPO / "docs" / "holtz" / "archive"
    declared = tomllib.loads((_REPO / "enforcement" / "events.toml").read_text())["events"]
    out = tmp_path / "out"
    result = _migrate("--all", "--archive-root", str(archive), "--out-dir", str(out))
    assert result.returncode == 0, result.stderr
    present = {meta["run"] for name, meta in ARCHIVE_MAP.items() if (archive / name).is_dir()}
    present |= {run for name, run in JUSTINE_MAP.items() if (archive / name).is_dir()}
    assert present, "no mapped archive directory is in this checkout"
    by_run = {int(path.stem.removeprefix("run-")): path.read_text().splitlines()
              for path in out.iterdir()}
    assert sorted(run for run in present if not by_run.get(run)) == [], (
        "the archive did not migrate: these runs produced no events"
    )
    events = [json.loads(line) for lines in by_run.values() for line in lines]
    assert _schema_failures(events, declared) == Counter()


def test_the_validator_sees_a_bad_value():
    """The V4 check is only as good as its ability to fail."""
    import tomllib

    declared = tomllib.loads((_REPO / "enforcement" / "events.toml").read_text())["events"]
    events = parse_punchlist(SAMPLE_TABLE_PUNCHLIST, run="9", auditor="holtz", source="P.md")
    assert _schema_failures(events, declared) == Counter()
    events[0]["fields"]["step"] = ""
    events.append({"type": "run_summary", "fields": {}})
    assert _schema_failures(events, declared) == Counter(
        {"finding.step: ''": 1, "run_summary: undeclared": 1}
    )


def _migrate(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True, text=True, timeout=120, cwd=cwd,
    )


_UNDECLARED = ("run_summary", "merge_result", "convergence_iteration", "run_postmortem")


def _run_with_every_undeclared_source(root: Path) -> Path:
    run_dir = root / "2026-03-22-run9"
    run_dir.mkdir(parents=True)
    (run_dir / "PUNCHLIST.md").write_text(SAMPLE_TABLE_PUNCHLIST)
    (run_dir / "SUMMARY.md").write_text(SAMPLE_SUMMARY)
    (run_dir / "MERGE-REPORT.md").write_text(SAMPLE_MERGE_REPORT)
    (run_dir / "HISTORY.json").write_text(SAMPLE_HISTORY)
    (run_dir / "run-20-postmortem.md").write_text("# Postmortem\n\nLessons.")
    return run_dir


def test_the_four_undeclared_legacy_types_are_counted_not_emitted(tmp_path):
    result = _migrate("--input", str(_run_with_every_undeclared_source(tmp_path)))
    assert result.returncode == 0, result.stderr
    emitted = [json.loads(line)["type"] for line in result.stdout.splitlines()]
    assert not set(emitted) & set(_UNDECLARED), emitted
    # The same SUMMARY.md also carries prediction outcomes, which are declared.
    assert emitted.count("prediction_outcome") == 2
    for count, event_type in ((1, "run_summary"), (1, "merge_result"),
                              (2, "convergence_iteration"), (1, "run_postmortem")):
        assert f"{count} {event_type}" in result.stderr, result.stderr


def test_all_counts_what_it_does_not_emit(tmp_path):
    archive = tmp_path / "archive"
    _run_with_every_undeclared_source(archive)
    out = tmp_path / "out"
    result = _migrate("--all", "--archive-root", str(archive), "--out-dir", str(out))
    assert result.returncode == 0, result.stderr
    emitted = [json.loads(line)["type"] for line in (out / "run-20.jsonl").read_text().splitlines()]
    assert not set(emitted) & set(_UNDECLARED), emitted
    assert "2 convergence_iteration" in result.stderr, result.stderr


# ---------------------------------------------------------------------------
# W27 / item 45 step 5: --build-project is idempotent (D-r, RULED 2026-09-23)
# ---------------------------------------------------------------------------
#
# `ledger import` refuses an existing path, so a re-run cannot go through it.
# `--ledger NAME` reads the registered runs from that ledger and prints only
# the ones it lacks; each goes in with `sahjhan --ledger NAME event`.


def test_build_project_skips_runs_already_registered():
    events = build_project_ledger(
        runs=[(1, "holtz"), (2, "holtz"), (3, "holtz")],
        project="holtz",
        registered={"1", "3"},
    )
    assert [e["fields"]["run"] for e in events if e["type"] == "run_registered"] == ["2"]
    assert [e["fields"]["run"] for e in events if e["type"] == "run_completed"] == ["2"]


def test_build_project_with_nothing_new_emits_nothing():
    """A second checkpoint is a row the first run did not write."""
    assert build_project_ledger(runs=[(1, "holtz")], project="holtz", registered={"1"}) == []


def test_the_registry_events_carry_only_their_declared_fields():
    import tomllib

    declared = tomllib.loads(
        (Path(__file__).parent.parent / "enforcement" / "events.toml").read_text()
    )["events"]
    for event in build_project_ledger(runs=[(1, "holtz")], project="holtz"):
        if event["type"] not in ("run_registered", "run_completed"):
            continue
        names = {f["name"] for f in declared[event["type"]]["fields"]}
        own = {k for k in event["fields"] if not k.startswith("_")}
        assert own == names, (event["type"], own ^ names)


class _Engine:
    """The real engine in a scratch project, for the ledger-reading paths."""

    def __init__(self, root: Path):
        sys.path.insert(0, str(Path(__file__).parent.parent / "enforcement" / "hooks"))
        from _resolve import ensure_sahjhan

        binary = ensure_sahjhan()
        if not binary:
            import pytest
            pytest.skip("sahjhan binary not available")
        self.binary = binary
        self.config = str(Path(__file__).parent.parent / "enforcement")
        self.root = root
        root.mkdir(exist_ok=True)
        self.sahjhan("init")

    def sahjhan(self, *args: str, stdin: str | None = None) -> str:
        return subprocess.run(
            [self.binary, "--config-dir", self.config, *args],
            cwd=self.root, input=stdin, check=True, capture_output=True, text=True,
        ).stdout

    def import_stream(self, name: str, stream: str) -> None:
        self.sahjhan("ledger", "import", "--name", name,
                     "--path", str(self.root / f"{name}.jsonl"), stdin=stream)

    def append(self, name: str, stream: str) -> None:
        for line in stream.splitlines():
            event = json.loads(line)
            fields = [a for k, v in event["fields"].items() for a in ("--field", f"{k}={v}")]
            self.sahjhan("--ledger", name, "event", event["type"], *fields)

    def rows(self, name: str) -> list[tuple[str, str]]:
        out = self.sahjhan("--ledger", name, "query",
                           "SELECT type, run FROM events WHERE type != 'genesis' ORDER BY seq",
                           "--format", "json")
        return [(r["type"], r["run"]) for r in json.loads(out)]


def test_build_project_run_twice_is_the_ledger_run_once(tmp_path):
    """V6: the second pass reads the ledger the first one made and adds nothing."""
    engine = _Engine(tmp_path / "project")
    first = _migrate("--build-project")
    assert first.returncode == 0, first.stderr
    engine.import_stream("project", first.stdout)
    once = engine.rows("project")
    assert once.count(("run_registered", "1")) == 1

    second = _migrate("--build-project", "--ledger", "project", cwd=engine.root)
    assert second.returncode == 0, second.stderr
    assert second.stdout == ""
    engine.append("project", second.stdout)
    assert engine.rows("project") == once


def test_build_project_fills_in_only_the_missing_runs(tmp_path):
    engine = _Engine(tmp_path / "project")
    full = _migrate("--build-project").stdout.splitlines()
    head = [ln for ln in full if json.loads(ln)["fields"]["run"] in ("1", "2")
            and json.loads(ln)["type"] != "_checkpoint"]
    engine.import_stream("project", "\n".join(head) + "\n")

    delta = _migrate("--build-project", "--ledger", "project", cwd=engine.root)
    assert delta.returncode == 0, delta.stderr
    emitted = [json.loads(ln) for ln in delta.stdout.splitlines()]
    assert not {e["fields"]["run"] for e in emitted if e["type"] != "_checkpoint"} & {"1", "2"}
    engine.append("project", delta.stdout)

    registered = [run for kind, run in engine.rows("project") if kind == "run_registered"]
    assert sorted(registered, key=int) == [str(n) for n in range(1, len(ARCHIVE_MAP) + 1)]
    assert _migrate("--build-project", "--ledger", "project", cwd=engine.root).stdout == ""


def test_build_project_refuses_a_ledger_it_cannot_read(tmp_path):
    """An unreadable registry must not read as "nothing is registered"."""
    engine = _Engine(tmp_path / "project")
    result = _migrate("--build-project", "--ledger", "no-such-ledger", cwd=engine.root)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "no-such-ledger" in result.stderr

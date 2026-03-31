"""Tests for legacy migration script."""
from __future__ import annotations

import json
import sys
from pathlib import Path

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

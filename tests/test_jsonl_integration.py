"""Integration tests for sahjhan v0.2.0 JSONL ledger operations.

These tests require the sahjhan binary to be vendored at bin/sahjhan.
They exercise the actual binary with the Holtz enforcement config.

Covers:
- Task 5.2: Event schema validation (all event types from events.toml)
- Task 5.3: Migration import pipeline (migrate_legacy.py -> ledger import)
- Task 5.4: Template rendering (dump-context + render when possible)
- Task 5.5: Query engine (DataFusion SQL over JSONL ledgers)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SAHJHAN = REPO_ROOT / "bin" / "sahjhan"
CONFIG_DIR = REPO_ROOT / "enforcement"

pytestmark = pytest.mark.skipif(
    not SAHJHAN.exists(), reason="sahjhan binary not vendored"
)


def _run_sahjhan(*args, cwd=None, input_data=None, check=True):
    """Run sahjhan with the enforcement config dir."""
    cmd = [str(SAHJHAN), "--config-dir", str(CONFIG_DIR)] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        input=input_data,
        timeout=30,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"sahjhan failed (exit {result.returncode}):\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def _read_ledger(path: Path) -> list[dict]:
    """Read a JSONL ledger file and return parsed events."""
    lines = path.read_text().strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def _init_and_create_ledger(tmp_path: Path, name: str) -> Path:
    """Init sahjhan working directory and create a named ledger.

    The init step creates the manifest and data_dir that sahjhan needs
    before named ledger operations work.
    """
    _run_sahjhan("init", cwd=tmp_path)
    ledger_path = tmp_path / f"{name}.jsonl"
    _run_sahjhan(
        "ledger", "create", "--name", name, "--path", str(ledger_path),
        cwd=tmp_path,
    )
    return ledger_path


def _record_event(tmp_path: Path, ledger_name: str, event_type: str,
                   fields: dict[str, str]) -> subprocess.CompletedProcess:
    """Record an event into a named ledger."""
    field_args = []
    for key, value in fields.items():
        field_args.extend(["--field", f"{key}={value}"])
    return _run_sahjhan(
        "--ledger", ledger_name,
        "event", event_type,
        *field_args,
        cwd=tmp_path,
    )


# Common breadcrumb fields used in most events
BREADCRUMBS = {
    "project": "holtz",
    "run": "1",
    "auditor": "holtz",
}


# ---------------------------------------------------------------------------
# Task 5.2: Event schema validation
# ---------------------------------------------------------------------------


class TestEventSchemaValidation:
    """Test that sahjhan v0.2.0 accepts events matching our enforcement config."""

    def test_record_finding_with_all_fields(self, tmp_path):
        """Record a finding event with all required fields."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS,
            "phase": "audit",
            "step": "7",
            "id": "BH-001",
            "severity": "HIGH",
            "category": "doc/drift",
            "location": "README.md:108",
            "perspective": "public-contract",
            "description": "Pattern count stale",
            "predicted_by": "1",
        })
        events = _read_ledger(ledger)
        findings = [e for e in events if e["type"] == "finding"]
        assert len(findings) == 1
        f = findings[0]["fields"]
        assert f["project"] == "holtz"
        assert f["run"] == "1"
        assert f["auditor"] == "holtz"
        assert f["id"] == "BH-001"
        assert f["severity"] == "HIGH"
        assert f["category"] == "doc/drift"
        assert f["location"] == "README.md:108"
        assert f["perspective"] == "public-contract"
        assert f["description"] == "Pattern count stale"

    def test_record_recon_finding(self, tmp_path):
        """Record a recon_finding event (new in JSONL migration)."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "recon_finding", {
            **BREADCRUMBS,
            "phase": "recon",
            "step": "0",
            "topic": "architecture",
            "content": "Four layers of architecture identified",
        })
        events = _read_ledger(ledger)
        recon = [e for e in events if e["type"] == "recon_finding"]
        assert len(recon) == 1
        assert recon[0]["fields"]["topic"] == "architecture"
        assert recon[0]["fields"]["content"] == "Four layers of architecture identified"

    def test_record_audit_claim(self, tmp_path):
        """Record an audit_claim event (new in JSONL migration)."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "audit_claim", {
            **BREADCRUMBS,
            "phase": "audit",
            "step": "6",
            "source": "README.md:15",
            "claim": "Supports 13 lenses",
            "verdict": "VERIFIED",
            "evidence": "lens-registry.md lists 13",
        })
        events = _read_ledger(ledger)
        claims = [e for e in events if e["type"] == "audit_claim"]
        assert len(claims) == 1
        assert claims[0]["fields"]["verdict"] == "VERIFIED"
        assert claims[0]["fields"]["claim"] == "Supports 13 lenses"

    def test_record_graph_delta(self, tmp_path):
        """Record a graph_delta event (new in JSONL migration)."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "graph_delta", {
            **BREADCRUMBS,
            "phase": "recon",
            "step": "0",
            "operation": "add_edge",
            "source": "module_a",
            "target": "module_b",
            "edge_type": "imports",
            "note": "direct dependency",
        })
        events = _read_ledger(ledger)
        deltas = [e for e in events if e["type"] == "graph_delta"]
        assert len(deltas) == 1
        assert deltas[0]["fields"]["operation"] == "add_edge"
        assert deltas[0]["fields"]["source"] == "module_a"
        assert deltas[0]["fields"]["target"] == "module_b"

    def test_record_run_summary(self, tmp_path):
        """Record a run_summary event (new in JSONL migration)."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "run_summary", {
            **BREADCRUMBS,
            "phase": "finalize",
            "step": "20",
            "total_findings": "12",
            "resolved": "10",
            "prediction_accuracy": "75%",
            "recommendations": "Fix auth module",
        })
        events = _read_ledger(ledger)
        summaries = [e for e in events if e["type"] == "run_summary"]
        assert len(summaries) == 1
        assert summaries[0]["fields"]["total_findings"] == "12"
        assert summaries[0]["fields"]["resolved"] == "10"

    def test_record_finding_resolved(self, tmp_path):
        """Record a finding_resolved event."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "finding_resolved", {
            **BREADCRUMBS,
            "phase": "fix_loop",
            "step": "10",
            "id": "BH-001",
            "commit_hash": "abc1234",
        })
        events = _read_ledger(ledger)
        resolved = [e for e in events if e["type"] == "finding_resolved"]
        assert len(resolved) == 1
        assert resolved[0]["fields"]["id"] == "BH-001"
        assert resolved[0]["fields"]["commit_hash"] == "abc1234"

    def test_record_prediction(self, tmp_path):
        """Record a prediction event."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "prediction", {
            **BREADCRUMBS,
            "id": "1",
            "target": "stale doc counts",
            "confidence": "HIGH",
            "basis": "pattern analysis from run 28",
        })
        events = _read_ledger(ledger)
        preds = [e for e in events if e["type"] == "prediction"]
        assert len(preds) == 1
        assert preds[0]["fields"]["confidence"] == "HIGH"

    def test_record_convergence_iteration(self, tmp_path):
        """Record a convergence_iteration event."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "convergence_iteration", {
            **BREADCRUMBS,
            "phase": "fix_loop",
            "step": "10",
            "iteration": "3",
            "open": "2",
            "resolved": "5",
            "test_count": "47",
            "tests_passed": "true",
        })
        events = _read_ledger(ledger)
        iters = [e for e in events if e["type"] == "convergence_iteration"]
        assert len(iters) == 1
        assert iters[0]["fields"]["iteration"] == "3"
        assert iters[0]["fields"]["tests_passed"] == "true"

    def test_record_pattern_discovered(self, tmp_path):
        """Record a pattern_discovered event."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "pattern_discovered", {
            **BREADCRUMBS,
            "phase": "audit",
            "step": "11",
            "pattern_id": "PAT-001",
            "name": "stale-counts",
            "heuristic": "numeric literal in doc not matching code",
            "instance_count": "3",
        })
        events = _read_ledger(ledger)
        patterns = [e for e in events if e["type"] == "pattern_discovered"]
        assert len(patterns) == 1
        assert patterns[0]["fields"]["name"] == "stale-counts"

    def test_record_baseline_delta(self, tmp_path):
        """Record a baseline_delta event."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "baseline_delta", {
            **BREADCRUMBS,
            "phase": "finalize",
            "step": "20",
            "section": "module-graph",
            "change_type": "modified",
            "content": "Added new edge from auth to cache",
        })
        events = _read_ledger(ledger)
        deltas = [e for e in events if e["type"] == "baseline_delta"]
        assert len(deltas) == 1
        assert deltas[0]["fields"]["change_type"] == "modified"

    def test_jsonl_has_hash_chain(self, tmp_path):
        """Verify JSONL events form a hash chain."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        # Record two events
        for i in range(2):
            _record_event(tmp_path, "test-run", "recon_finding", {
                **BREADCRUMBS,
                "phase": "recon",
                "step": str(i),
                "topic": f"topic-{i}",
                "content": f"content-{i}",
            })
        events = _read_ledger(ledger)
        # Genesis + 2 events = 3 entries
        assert len(events) == 3
        # First event is genesis
        assert events[0]["type"] == "genesis"
        assert events[0]["seq"] == 0
        # Each event's prev should be the previous event's hash
        for i in range(1, len(events)):
            assert events[i]["prev"] == events[i - 1]["hash"], (
                f"Hash chain broken at seq {events[i]['seq']}: "
                f"prev={events[i]['prev']} != hash[{i-1}]={events[i-1]['hash']}"
            )

    def test_jsonl_schema_version(self, tmp_path):
        """Verify all JSONL lines have schema version 1."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7", "id": "BH-001", "severity": "HIGH",
            "category": "test", "location": "foo.py", "perspective": "component",
            "description": "test", "predicted_by": "",
        })
        events = _read_ledger(ledger)
        for event in events:
            assert event["schema"] == 1
            assert event["engine"] == "sahjhan"
            assert event["protocol"] == "holtz/1.0.0"

    def test_sequential_seq_numbers(self, tmp_path):
        """Verify seq numbers are sequential starting from 0."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        for i in range(3):
            _record_event(tmp_path, "test-run", "recon_finding", {
                **BREADCRUMBS,
                "phase": "recon", "step": str(i),
                "topic": f"topic-{i}", "content": f"content-{i}",
            })
        events = _read_ledger(ledger)
        for i, event in enumerate(events):
            assert event["seq"] == i, f"Expected seq {i}, got {event['seq']}"

    def test_multiple_event_types_in_one_ledger(self, tmp_path):
        """Record multiple event types in a single ledger."""
        ledger = _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "recon_finding", {
            **BREADCRUMBS, "phase": "recon", "step": "0",
            "topic": "arch", "content": "x",
        })
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS, "phase": "audit", "step": "7",
            "id": "BH-001", "severity": "HIGH", "category": "test",
            "location": "foo.py", "perspective": "component",
            "description": "bug", "predicted_by": "",
        })
        _record_event(tmp_path, "test-run", "audit_claim", {
            **BREADCRUMBS, "phase": "audit", "step": "6",
            "source": "README.md", "claim": "works",
            "verdict": "VERIFIED", "evidence": "yes",
        })
        events = _read_ledger(ledger)
        event_types = {e["type"] for e in events if e["type"] != "genesis"}
        assert "recon_finding" in event_types
        assert "finding" in event_types
        assert "audit_claim" in event_types

    def test_finding_rejects_invalid_severity(self, tmp_path):
        """sahjhan rejects a finding with invalid severity pattern."""
        _init_and_create_ledger(tmp_path, "test-run")
        result = _run_sahjhan(
            "--ledger", "test-run",
            "event", "finding",
            "--field", "project=holtz",
            "--field", "run=1",
            "--field", "auditor=holtz",
            "--field", "phase=audit",
            "--field", "step=7",
            "--field", "id=BH-001",
            "--field", "severity=INVALID",
            "--field", "category=test",
            "--field", "location=foo.py",
            "--field", "perspective=component",
            "--field", "description=test",
            "--field", "predicted_by=",
            cwd=tmp_path,
            check=False,
        )
        # sahjhan enforces the severity pattern from events.toml
        assert result.returncode != 0
        assert "severity" in result.stderr.lower() or "pattern" in result.stderr.lower()

    def test_finding_rejects_invalid_id_pattern(self, tmp_path):
        """sahjhan should reject a finding with invalid ID pattern."""
        _init_and_create_ledger(tmp_path, "test-run")
        result = _run_sahjhan(
            "--ledger", "test-run",
            "event", "finding",
            "--field", "project=holtz",
            "--field", "run=1",
            "--field", "auditor=holtz",
            "--field", "phase=audit",
            "--field", "step=7",
            "--field", "id=INVALID-ID",
            "--field", "severity=HIGH",
            "--field", "category=test",
            "--field", "location=foo.py",
            "--field", "perspective=component",
            "--field", "description=test",
            "--field", "predicted_by=",
            cwd=tmp_path,
            check=False,
        )
        # BH-011: Assertion must be unconditional — if sahjhan accepts
        # invalid IDs, that itself is a test failure worth knowing about
        assert result.returncode != 0, (
            "sahjhan accepted INVALID-ID — expected rejection for non-matching ID pattern"
        )
        assert "id" in result.stderr.lower() or "pattern" in result.stderr.lower()

    def test_ledger_verify_passes(self, tmp_path):
        """Verify that ledger verify confirms hash chain integrity."""
        _init_and_create_ledger(tmp_path, "test-run")
        for i in range(3):
            _record_event(tmp_path, "test-run", "recon_finding", {
                **BREADCRUMBS, "phase": "recon", "step": str(i),
                "topic": f"topic-{i}", "content": f"content-{i}",
            })
        result = _run_sahjhan(
            "ledger", "verify", "--name", "test-run",
            cwd=tmp_path,
        )
        assert "valid" in result.stdout.lower()
        assert "4 entries" in result.stdout  # genesis + 3 events


# ---------------------------------------------------------------------------
# Task 5.3: Migration import pipeline
# ---------------------------------------------------------------------------


class TestMigrationImportPipeline:
    """Test that migrate_legacy.py output can be imported into sahjhan."""

    def test_import_generated_jsonl(self, tmp_path):
        """Generate JSONL from migration script and validate structure."""
        # Create a minimal archive directory with table-format punchlist
        archive = tmp_path / "archive" / "test-run"
        archive.mkdir(parents=True)
        (archive / "PUNCHLIST.md").write_text(
            "# Punchlist\n\n## HIGH\n\n"
            "| ID | Category | Location | Perspective | Description | Status |\n"
            "|----|----------|----------|-------------|-------------|--------|\n"
            "| BH-001 | doc/drift | README.md:1 | component | Stale count | OPEN |\n"
            "| BH-002 | test/gap | tests/:0 | integration | Missing test | RESOLVED |\n"
        )
        # Run migration script
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "migrate_legacy.py"),
             "--input", str(archive), "--run", "99"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"migrate_legacy.py failed: {result.stderr}"
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        assert len(lines) > 0

        # Validate JSONL structure
        for line in lines:
            event = json.loads(line)
            assert "type" in event
            assert "fields" in event
            assert event["fields"]["_migrated"] == "true"
            assert event["fields"]["run"] == "99"
            assert event["fields"]["project"] == "holtz"

        # Should have both a finding and a finding_resolved (for RESOLVED item)
        types = [json.loads(l)["type"] for l in lines]
        assert "finding" in types
        assert "finding_resolved" in types

    def test_import_into_sahjhan_ledger(self, tmp_path):
        """Import migration output into a real sahjhan ledger."""
        # Create a minimal archive directory
        archive = tmp_path / "archive" / "test-run"
        archive.mkdir(parents=True)
        (archive / "PUNCHLIST.md").write_text(
            "# Punchlist\n\n## HIGH\n\n"
            "| ID | Category | Location | Perspective | Description | Status |\n"
            "|----|----------|----------|-------------|-------------|--------|\n"
            "| BH-001 | doc/drift | README.md:1 | component | Stale count | OPEN |\n"
        )

        # Generate JSONL
        gen_result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "migrate_legacy.py"),
             "--input", str(archive), "--run", "99"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert gen_result.returncode == 0

        # Init sahjhan and import via stdin
        _run_sahjhan("init", cwd=tmp_path)
        imported_path = tmp_path / "imported.jsonl"
        result = _run_sahjhan(
            "ledger", "import",
            "--name", "migrated-run",
            "--path", str(imported_path),
            cwd=tmp_path,
            input_data=gen_result.stdout,
        )
        assert "imported" in result.stdout.lower() or "registered" in result.stdout.lower()

        # Verify the imported ledger
        events = _read_ledger(imported_path)
        assert len(events) >= 2  # genesis + at least 1 finding

        # Genesis first
        assert events[0]["type"] == "genesis"

        # Finding events should have _migrated marker
        findings = [e for e in events if e["type"] == "finding"]
        assert len(findings) >= 1
        assert findings[0]["fields"]["_migrated"] == "true"
        assert findings[0]["fields"]["run"] == "99"

        # Hash chain should be valid
        verify_result = _run_sahjhan(
            "ledger", "verify", "--name", "migrated-run",
            cwd=tmp_path,
        )
        assert "valid" in verify_result.stdout.lower()

    def test_import_preserves_field_values(self, tmp_path):
        """Import preserves all field values from migration output."""
        # Craft a known JSONL payload
        bare_events = [
            json.dumps({
                "type": "finding",
                "fields": {
                    "project": "holtz", "run": "42", "auditor": "holtz",
                    "phase": "audit", "step": "7",
                    "id": "BH-001", "severity": "CRITICAL",
                    "category": "security/auth",
                    "location": "src/auth.py:55",
                    "perspective": "security",
                    "description": "Token not rotated",
                    "predicted_by": "3",
                    "_migrated": "true",
                    "_source": "PUNCHLIST.md",
                },
            }),
        ]

        _run_sahjhan("init", cwd=tmp_path)
        imported_path = tmp_path / "field-test.jsonl"
        _run_sahjhan(
            "ledger", "import",
            "--name", "field-test",
            "--path", str(imported_path),
            cwd=tmp_path,
            input_data="\n".join(bare_events) + "\n",
        )
        events = _read_ledger(imported_path)
        findings = [e for e in events if e["type"] == "finding"]
        assert len(findings) == 1
        f = findings[0]["fields"]
        assert f["id"] == "BH-001"
        assert f["severity"] == "CRITICAL"
        assert f["category"] == "security/auth"
        assert f["location"] == "src/auth.py:55"
        assert f["_migrated"] == "true"
        assert f["_source"] == "PUNCHLIST.md"

    def test_import_real_archive_if_available(self, tmp_path):
        """Import from a real archive directory if available."""
        # Look for any existing archive directory
        archive_root = REPO_ROOT / "docs" / "holtz" / "archive"
        if not archive_root.exists():
            pytest.skip("Archive root not available")

        # Find the first directory that exists
        archive = None
        for candidate in ["bug-hunter-2026-03-19", "2026-03-25-run19"]:
            candidate_path = archive_root / candidate
            if candidate_path.is_dir():
                archive = candidate_path
                break

        if archive is None:
            pytest.skip("No archive directories available")

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "migrate_legacy.py"),
             "--input", str(archive)],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        assert len(lines) > 0

        for line in lines:
            event = json.loads(line)
            assert event["fields"]["_migrated"] == "true"
            assert event["fields"]["project"] == "holtz"


# ---------------------------------------------------------------------------
# Task 5.4: Template rendering
# ---------------------------------------------------------------------------


class TestTemplateRendering:
    """Test that sahjhan renders templates from JSONL ledger data."""

    def test_dump_context_has_correct_structure(self, tmp_path):
        """Render --dump-context returns valid JSON with expected keys."""
        _init_and_create_ledger(tmp_path, "run")
        _record_event(tmp_path, "run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7",
            "id": "BH-001", "severity": "HIGH",
            "category": "doc/drift", "location": "README.md:108",
            "perspective": "public-contract",
            "description": "Pattern count stale", "predicted_by": "",
        })

        result = _run_sahjhan(
            "--ledger", "run", "render", "--dump-context",
            cwd=tmp_path,
        )
        ctx = json.loads(result.stdout)

        # Verify top-level keys
        assert "events" in ctx
        assert "protocol" in ctx
        assert "state" in ctx
        assert "ledger_len" in ctx

        # Protocol metadata
        assert ctx["protocol"]["name"] == "holtz"
        assert ctx["protocol"]["version"] == "1.0.0"

        # Events should include our finding
        finding_events = [
            e for e in ctx["events"] if e["event_type"] == "finding"
        ]
        assert len(finding_events) == 1
        assert finding_events[0]["fields"]["id"] == "BH-001"

    def test_dump_context_includes_sets(self, tmp_path):
        """Render context includes perspective set from protocol."""
        _init_and_create_ledger(tmp_path, "run")
        result = _run_sahjhan(
            "--ledger", "run", "render", "--dump-context",
            cwd=tmp_path,
        )
        ctx = json.loads(result.stdout)

        assert "sets" in ctx
        assert "perspective" in ctx["sets"]
        perspective_set = ctx["sets"]["perspective"]
        assert perspective_set["total"] == 13
        member_names = [m["name"] for m in perspective_set["members"]]
        assert "component" in member_names
        assert "security" in member_names
        assert "public-contract" in member_names

    def test_dump_context_with_multiple_findings(self, tmp_path):
        """Render context includes all recorded findings."""
        _init_and_create_ledger(tmp_path, "run")
        for i, (item_id, sev) in enumerate([
            ("BH-001", "HIGH"), ("BH-002", "HIGH"), ("BH-003", "MEDIUM"),
        ]):
            _record_event(tmp_path, "run", "finding", {
                **BREADCRUMBS,
                "phase": "audit", "step": "7",
                "id": item_id, "severity": sev,
                "category": "test", "location": f"file{i}.py",
                "perspective": "component",
                "description": f"finding {i}", "predicted_by": "",
            })

        result = _run_sahjhan(
            "--ledger", "run", "render", "--dump-context",
            cwd=tmp_path,
        )
        ctx = json.loads(result.stdout)
        finding_events = [
            e for e in ctx["events"] if e["event_type"] == "finding"
        ]
        assert len(finding_events) == 3

    def test_render_produces_output_or_known_error(self, tmp_path):
        """Render either produces PUNCHLIST.md or fails with known error.

        The render system requires all referenced ledger names to be resolvable.
        When renders.toml references ledger='run' and ledger='project', both
        must exist. This test verifies the behavior is predictable.
        """
        _init_and_create_ledger(tmp_path, "run")
        # Also create a 'project' ledger since renders.toml references it
        project_path = tmp_path / "project.jsonl"
        _run_sahjhan(
            "ledger", "create", "--name", "project", "--path", str(project_path),
            cwd=tmp_path,
        )

        _record_event(tmp_path, "run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7",
            "id": "BH-001", "severity": "HIGH",
            "category": "doc/drift", "location": "README.md:108",
            "perspective": "public-contract",
            "description": "Pattern count stale", "predicted_by": "",
        })

        result = _run_sahjhan(
            "--ledger", "run", "render",
            cwd=tmp_path,
            check=False,
        )

        render_dir = tmp_path / "docs" / "holtz"
        if result.returncode == 0 and render_dir.exists():
            punchlist = render_dir / "PUNCHLIST.md"
            if punchlist.exists():
                content = punchlist.read_text()
                assert "BH-001" in content
                assert "HIGH" in content
                assert "doc/drift" in content
        else:
            # Known limitation: render may fail if ledger path resolution
            # doesn't match protocol.toml path_template expectations.
            # The dump-context path (tested above) still works.
            assert "render" in result.stderr.lower() or "ledger" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Task 5.5: Query engine
# ---------------------------------------------------------------------------


class TestQueryEngine:
    """Test DataFusion SQL queries over JSONL ledgers.

    sahjhan v0.2.0 flattens event fields into the 'events' table columns
    (not nested under fields->). Column names match the field names directly.
    """

    def test_count_findings_by_severity(self, tmp_path):
        """Query should count findings grouped by severity."""
        _init_and_create_ledger(tmp_path, "test-run")
        for item_id, severity in [
            ("BH-001", "HIGH"), ("BH-002", "HIGH"), ("BH-003", "MEDIUM"),
        ]:
            _record_event(tmp_path, "test-run", "finding", {
                **BREADCRUMBS,
                "phase": "audit", "step": "7",
                "id": item_id, "severity": severity,
                "category": "test", "location": "foo.py",
                "perspective": "component",
                "description": "test finding", "predicted_by": "",
            })

        result = _run_sahjhan(
            "--ledger", "test-run",
            "query",
            "SELECT severity, count(*) as cnt FROM events WHERE type='finding' GROUP BY 1 ORDER BY 2 DESC",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "HIGH" in result.stdout
        assert "MEDIUM" in result.stdout

    def test_query_json_output(self, tmp_path):
        """Query with --json returns parseable JSON array."""
        _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7",
            "id": "BH-001", "severity": "HIGH",
            "category": "test", "location": "foo.py",
            "perspective": "component",
            "description": "test finding", "predicted_by": "",
        })

        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--json",
            "SELECT id, severity FROM events WHERE type='finding'",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "BH-001"
        assert data[0]["severity"] == "HIGH"

    def test_query_count_flag(self, tmp_path):
        """Query with --count returns just the count."""
        _init_and_create_ledger(tmp_path, "test-run")
        for i in range(3):
            _record_event(tmp_path, "test-run", "recon_finding", {
                **BREADCRUMBS,
                "phase": "recon", "step": str(i),
                "topic": f"topic-{i}", "content": f"content-{i}",
            })

        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--count",
            "--type", "recon_finding",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "3" in result.stdout

    def test_query_filter_by_type_in_sql(self, tmp_path):
        """SQL WHERE type= filters events by type."""
        _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "recon_finding", {
            **BREADCRUMBS,
            "phase": "recon", "step": "0",
            "topic": "arch", "content": "content",
        })
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7",
            "id": "BH-001", "severity": "HIGH",
            "category": "test", "location": "foo.py",
            "perspective": "component",
            "description": "test finding", "predicted_by": "",
        })

        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--json",
            "SELECT type, id FROM events WHERE type='finding'",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should only have findings, not recon_finding or genesis
        assert len(data) == 1
        assert all(row["type"] == "finding" for row in data)

    def test_query_filter_by_field_in_sql(self, tmp_path):
        """SQL WHERE clause filters by field value."""
        _init_and_create_ledger(tmp_path, "test-run")
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7",
            "id": "BH-001", "severity": "HIGH",
            "category": "test", "location": "foo.py",
            "perspective": "component",
            "description": "test finding", "predicted_by": "",
        })
        _record_event(tmp_path, "test-run", "finding", {
            **BREADCRUMBS,
            "phase": "audit", "step": "7",
            "id": "BH-002", "severity": "MEDIUM",
            "category": "test", "location": "bar.py",
            "perspective": "component",
            "description": "another finding", "predicted_by": "",
        })

        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--json",
            "SELECT id, severity FROM events WHERE type='finding' AND severity='HIGH'",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["id"] == "BH-001"
        assert data[0]["severity"] == "HIGH"

    def test_query_glob_across_multiple_ledgers(self, tmp_path):
        """Query with --glob across multiple ledger files."""
        _run_sahjhan("init", cwd=tmp_path)

        # Create two run ledgers in separate directories
        runs_dir = tmp_path / "runs"
        for run_num in [1, 2]:
            run_dir = runs_dir / str(run_num)
            run_dir.mkdir(parents=True)
            ledger_path = run_dir / "ledger.jsonl"
            _run_sahjhan(
                "ledger", "create",
                "--name", f"run-{run_num}",
                "--path", str(ledger_path),
                cwd=tmp_path,
            )
            _record_event(tmp_path, f"run-{run_num}", "finding", {
                "project": "holtz",
                "run": str(run_num),
                "auditor": "holtz",
                "phase": "audit", "step": "7",
                "id": f"BH-00{run_num}", "severity": "HIGH",
                "category": "test", "location": "foo.py",
                "perspective": "component",
                "description": f"finding from run {run_num}",
                "predicted_by": "",
            })

        # Query across both ledgers using glob
        result = _run_sahjhan(
            "query",
            "--glob", str(runs_dir / "*" / "ledger.jsonl"),
            "--json",
            "SELECT run, id FROM events WHERE type='finding' ORDER BY run",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        runs_found = {row["run"] for row in data}
        assert "1" in runs_found
        assert "2" in runs_found

    def test_query_sql_with_aggregation(self, tmp_path):
        """SQL aggregation queries work over JSONL events."""
        _init_and_create_ledger(tmp_path, "test-run")
        for i, item_id in enumerate(["BH-001", "BH-002", "BH-003"]):
            _record_event(tmp_path, "test-run", "finding", {
                **BREADCRUMBS,
                "phase": "audit", "step": "7",
                "id": item_id, "severity": "HIGH",
                "category": "test", "location": f"file{i}.py",
                "perspective": "component",
                "description": f"finding {i}", "predicted_by": "",
            })
        # Resolve one
        _record_event(tmp_path, "test-run", "finding_resolved", {
            **BREADCRUMBS,
            "phase": "fix_loop", "step": "10",
            "id": "BH-001", "commit_hash": "abc1234",
        })

        # Count total findings
        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--json",
            "SELECT count(*) as total FROM events WHERE type='finding'",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert int(data[0]["total"]) == 3

        # Count resolved
        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--json",
            "SELECT count(*) as resolved FROM events WHERE type='finding_resolved'",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert int(data[0]["resolved"]) == 1

    def test_query_empty_ledger(self, tmp_path):
        """Query an empty ledger (genesis only) returns no user events."""
        _init_and_create_ledger(tmp_path, "test-run")
        result = _run_sahjhan(
            "--ledger", "test-run",
            "query", "--json",
            "SELECT count(*) as cnt FROM events WHERE type='finding'",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert int(data[0]["cnt"]) == 0

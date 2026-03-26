"""Tests for enforcement TOML configuration files."""

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ENFORCEMENT_DIR = Path(__file__).parent.parent / "enforcement"
EVENTS_TOML = ENFORCEMENT_DIR / "events.toml"
TRANSITIONS_TOML = ENFORCEMENT_DIR / "transitions.toml"
RENDERS_TOML = ENFORCEMENT_DIR / "renders.toml"
PROTOCOL_TOML = ENFORCEMENT_DIR / "protocol.toml"

BREADCRUMBS = ["project", "run", "auditor"]

NEW_EVENT_TYPES = [
    "recon_finding", "audit_claim", "test_audit_finding",
    "code_audit_finding", "merge_result", "convergence_iteration",
    "run_summary", "graph_delta", "pattern_discovered",
    "baseline_delta", "run_postmortem",
]


# ── Task 1.1: events.toml ──


def test_all_events_have_breadcrumbs():
    """Every event type must have project, run, auditor fields."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for name, defn in events.items():
        field_names = [f["name"] for f in defn["fields"]]
        for bc in BREADCRUMBS:
            assert bc in field_names, (
                f"Event '{name}' missing breadcrumb field '{bc}'"
            )


def test_finding_has_phase_and_step():
    """The 'finding' event must have phase and step fields."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    finding = cfg["events"]["finding"]
    field_names = [f["name"] for f in finding["fields"]]
    assert "phase" in field_names, "finding missing 'phase' field"
    assert "step" in field_names, "finding missing 'step' field"


def test_new_event_types_exist():
    """All new event types must be defined."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for evt in NEW_EVENT_TYPES:
        assert evt in events, f"Missing new event type: {evt}"


def test_field_patterns_are_valid_regexes():
    """Every field with a 'pattern' key must compile as a valid regex."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for name, defn in events.items():
        for field in defn["fields"]:
            if "pattern" in field:
                try:
                    re.compile(field["pattern"])
                except re.error as exc:
                    raise AssertionError(
                        f"Event '{name}', field '{field['name']}': "
                        f"invalid regex pattern '{field['pattern']}': {exc}"
                    )


# ── Task 1.2: transitions.toml ──


def test_recon_complete_uses_event_gates():
    """recon_complete must not use files_exist; should use query or ledger_has_event."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    recon_complete = None
    for t in cfg["transitions"]:
        if t.get("command") == "recon_complete":
            recon_complete = t
            break
    assert recon_complete is not None, "No recon_complete transition found"
    gate_types = [g["type"] for g in recon_complete["gates"]]
    assert "files_exist" not in gate_types, (
        "recon_complete should not use files_exist gate"
    )
    assert "query" in gate_types or "ledger_has_event" in gate_types, (
        "recon_complete should have a query or ledger_has_event gate"
    )


def test_audit_complete_uses_event_gates():
    """audit_complete must not use file_exists for audit markdown."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    audit_complete = None
    for t in cfg["transitions"]:
        if t.get("command") == "audit_complete":
            audit_complete = t
            break
    assert audit_complete is not None, "No audit_complete transition found"
    for gate in audit_complete["gates"]:
        if gate["type"] == "file_exists":
            # file_exists for impact-graph.json is OK
            assert "impact-graph" in gate.get("path", ""), (
                f"audit_complete has file_exists gate for non-graph file: {gate}"
            )


def test_fix_commit_has_circuit_breaker():
    """fix_commit must have a query gate (circuit breaker)."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    fix_commit = None
    for t in cfg["transitions"]:
        if t.get("command") == "fix_commit":
            fix_commit = t
            break
    assert fix_commit is not None, "No fix_commit transition found"
    gate_types = [g["type"] for g in fix_commit["gates"]]
    assert "query" in gate_types, (
        "fix_commit should have a query gate (circuit breaker)"
    )


# ── Task 1.3: renders.toml ──


def test_renders_have_ledger_field():
    """Every render entry must have a 'ledger' field."""
    cfg = tomllib.loads(RENDERS_TOML.read_text())
    for i, render in enumerate(cfg["renders"]):
        assert "ledger" in render, (
            f"Render entry {i} (target={render.get('target', '?')}) missing 'ledger' field"
        )


# ── Task 1.4: protocol.toml ──


def test_protocol_has_ledger_config():
    """protocol.toml must have ledgers.run and ledgers.project."""
    cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    assert "ledgers" in cfg, "protocol.toml missing 'ledgers' key"
    assert "run" in cfg["ledgers"], "protocol.toml missing ledgers.run"
    assert "project" in cfg["ledgers"], "protocol.toml missing ledgers.project"


def test_protocol_has_content_event_aliases():
    """protocol.toml aliases must include content event shortcuts."""
    cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    aliases = cfg["aliases"]
    expected = [
        "recon finding",
        "audit claim",
        "test finding",
        "code finding",
        "graph delta",
    ]
    for alias in expected:
        assert alias in aliases, f"Missing alias: '{alias}'"


def test_transitions_no_plugin_root_references():
    """BH-002: Gate commands must not reference ${CLAUDE_PLUGIN_ROOT}."""
    content = TRANSITIONS_TOML.read_text()
    assert "${CLAUDE_PLUGIN_ROOT}" not in content, (
        "transitions.toml still references ${CLAUDE_PLUGIN_ROOT} — "
        "use relative paths (e.g. skills/holtz/scripts/) instead"
    )


def test_mypy_uses_explicit_package_bases():
    """BH-002: mypy commands must use --explicit-package-bases to avoid _common collision."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        for gate in t.get("gates", []):
            cmd = gate.get("cmd", "")
            if "mypy" in cmd:
                assert "--explicit-package-bases" in cmd, (
                    f"mypy gate in '{t['command']}' missing --explicit-package-bases: {cmd}"
                )

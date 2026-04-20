"""Tests for enforcement TOML configuration files."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):  # noqa: UP036
    import tomllib
else:
    import tomli as tomllib

ENFORCEMENT_DIR = Path(__file__).parent.parent / "enforcement"
EVENTS_TOML = ENFORCEMENT_DIR / "events.toml"
TRANSITIONS_TOML = ENFORCEMENT_DIR / "transitions.toml"
RENDERS_TOML = ENFORCEMENT_DIR / "renders.toml"
PROTOCOL_TOML = ENFORCEMENT_DIR / "protocol.toml"

BREADCRUMBS = ["project", "run", "auditor"]

# Auto-recorded events don't need breadcrumb fields — they're telemetry, not audit events
_AUTO_RECORDED_EVENTS = {"file_read", "source_edit", "file_search", "bash_command"}

NEW_EVENT_TYPES = [
    "recon_finding", "audit_claim", "test_audit_finding",
    "code_audit_finding", "merge_result", "convergence_iteration",
    "run_summary", "graph_delta", "pattern_discovered",
    "baseline_delta", "run_postmortem",
]


# ── Task 1.1: events.toml ──


def test_all_events_have_breadcrumbs():
    """Every event type must have project, run, auditor fields.

    Auto-recorded events (file_read, source_edit, file_search, bash_command)
    are excluded — they are ground-truth telemetry emitted by hooks, not audit
    events authored by the auditor, so they don't carry breadcrumb fields.
    """
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for name, defn in events.items():
        if name in _AUTO_RECORDED_EVENTS:
            continue
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


def test_quiz_event_types_exist():
    """All quiz-related event types are defined in events.toml."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    required = ["quiz_bank_generated", "quiz_posed", "quiz_answered", "quiz_failed", "quiz_exhausted", "quiz_exhausted_resolved"]
    for name in required:
        assert name in events, f"Missing event type: {name}"


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
                    ) from exc


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


def test_iteration_boundary_enforces_pattern_check():
    """BH-020: iteration_boundary must block when 3+ fixes lack pattern analysis."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    boundary = None
    for t in cfg["transitions"]:
        if t.get("command") == "iteration_boundary":
            boundary = t
            break
    assert boundary is not None, "No iteration_boundary transition found"
    gate_strs = [json.dumps(g) for g in boundary.get("gates", [])]
    assert any("pattern_analysis" in g for g in gate_strs), (
        "iteration_boundary must have a gate enforcing pattern analysis "
        "after 3+ fix_commits — otherwise the auditor can skip Step 11 "
        "and miss recurring patterns (BH-020)"
    )


# ── Task 1.3: renders.toml ──


def test_renders_have_ledger_field():
    """Every render entry must have a 'ledger' or 'ledger_template' field."""
    cfg = tomllib.loads(RENDERS_TOML.read_text())
    for i, render in enumerate(cfg["renders"]):
        assert "ledger" in render or "ledger_template" in render, (
            f"Render entry {i} (target={render.get('target', '?')}) missing 'ledger' or 'ledger_template' field"
        )


def test_render_ledger_templates_match_protocol():
    """Every ledger_template in renders.toml must have a matching template in protocol.toml."""
    renders_cfg = tomllib.loads(RENDERS_TOML.read_text())
    protocol_cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    declared_templates = set(protocol_cfg.get("ledgers", {}).keys())
    for render in renders_cfg["renders"]:
        tmpl = render.get("ledger_template")
        if tmpl is not None:
            assert tmpl in declared_templates, (
                f"Render target '{render['target']}' uses ledger_template '{tmpl}' "
                f"but protocol.toml only declares: {sorted(declared_templates)}. "
                f"Ledger must be created with 'sahjhan ledger create --from {tmpl} <N>' "
                f"so the template link is preserved."
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


def test_perspective_clean_has_quiz_gate():
    """set complete perspective transition requires quiz_answered."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        if t.get("command") == "set complete perspective":
            gate_strs = [json.dumps(g) for g in t.get("gates", [])]
            assert any("quiz_answered" in g for g in gate_strs), \
                "set complete perspective missing quiz_answered gate"
            return
    raise AssertionError("set complete perspective transition not found")


def test_converge_has_quiz_exhaustion_gate():
    """converge transition checks for unresolved quiz_exhausted."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        if t.get("command") == "converge":
            gate_strs = [json.dumps(g) for g in t.get("gates", [])]
            assert any("quiz_exhausted" in g for g in gate_strs), \
                "converge missing quiz_exhausted gate"
            return
    raise AssertionError("converge transition not found")


def test_gate_sql_uses_seq_not_rowid():
    """BH-021: Gate SQL must use 'seq' not 'rowid' — Sahjhan uses DataFusion, not SQLite."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        for gate in t.get("gates", []):
            sql = gate.get("sql", "")
            assert "rowid" not in sql.lower(), (
                f"Gate SQL in '{t['command']}' references 'rowid' which is a SQLite concept. "
                f"Sahjhan's DataFusion backend uses 'seq' for event ordering. "
                f"SQL: {sql}"
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


# ── Tasks 5 & 6: Hook registration ──


def test_settings_local_has_no_enforcement_hooks():
    """settings.local.json must NOT register enforcement hooks.

    Enforcement hooks run via the plugin (hooks/hooks.json), not via
    project settings. Having them in settings.local.json causes them
    to fire during plugin development, blocking edits to the hooks
    themselves. See: two broken releases from this exact mistake.
    """
    settings_path = Path(__file__).parent.parent / ".claude" / "settings.local.json"
    if not settings_path.exists():
        pytest.skip(".claude/settings.local.json not present (not tracked in git)")
    cfg = json.loads(settings_path.read_text())
    hooks = cfg.get("hooks", {})

    all_commands = []
    for event_hooks in hooks.values():
        for entry in event_hooks if isinstance(event_hooks, list) else []:
            for h in entry.get("hooks", []):
                all_commands.append(h.get("command", ""))

    enforcement_hooks = [c for c in all_commands if "enforcement/" in c]
    assert not enforcement_hooks, (
        f"Enforcement hooks must not be in settings.local.json (found: {enforcement_hooks}). "
        "They belong in hooks/hooks.json (plugin mode only)."
    )


def test_pre_release_hook_validation_gate():
    """Pre-release gate: smoke test script exists and is executable."""
    smoke_test = Path(__file__).parent.parent / "scripts" / "smoke-test-hooks.sh"
    assert smoke_test.exists(), "scripts/smoke-test-hooks.sh missing"
    assert os.access(smoke_test, os.X_OK), "scripts/smoke-test-hooks.sh not executable"


def test_hook_schema_exists():
    """Pre-release gate: hook_schema.py must exist as source of truth."""
    schema = Path(__file__).parent / "hook_schema.py"
    assert schema.exists(), "tests/hook_schema.py missing — hooks have no schema to validate against"


def test_hooks_json_registers_enforcement_hooks():
    """Plugin-mode hooks.json must register commit_gate and protocol_tracker."""
    hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
    cfg = json.loads(hooks_path.read_text())
    hooks = cfg.get("hooks", {})

    pre_tool = hooks.get("PreToolUse", [])
    post_tool = hooks.get("PostToolUse", [])

    all_pre_commands = []
    for entry in pre_tool:
        for h in entry.get("hooks", []):
            all_pre_commands.append(h.get("command", ""))

    all_post_commands = []
    for entry in post_tool:
        for h in entry.get("hooks", []):
            all_post_commands.append(h.get("command", ""))

    assert any("commit_gate" in c for c in all_pre_commands), (
        "commit_gate.py not registered in hooks.json PreToolUse"
    )
    assert any("protocol_tracker" in c for c in all_post_commands), (
        "protocol_tracker.py not registered in hooks.json PostToolUse"
    )


def test_trusted_callers_keys_match_daemon_path_strip():
    """Manifest keys must match how the daemon identifies caller scripts.

    The sahjhan daemon identifies a caller by taking the caller's absolute
    script path and stripping its ``--config-dir`` prefix (which is
    ``<plugin_root>/enforcement``). So a script at
    ``<plugin_root>/enforcement/hooks/primer.py`` is identified as
    ``hooks/primer.py`` — NOT ``enforcement/hooks/primer.py``.

    A previous version of the manifest used plugin-root-relative keys with
    an ``enforcement/`` prefix. Every daemon auth request silently failed
    with "caller not in manifest", and the whole enforcement layer
    collapsed to fail-open in the installed-plugin case — read_cache
    returned None everywhere, is_enforcement_fresh returned False, every
    protocol gate fell through to exit_ok. No tests caught this because
    no tests hit the real authed-event path.

    Pin the format so the regression can't repeat silently.
    """
    repo_root = Path(__file__).parent.parent
    manifest_path = repo_root / "enforcement" / "trusted-callers.toml"
    manifest = tomllib.loads(manifest_path.read_text())

    bad_keys = [
        k for k in manifest.get("callers", {})
        if k.startswith("enforcement/")
    ]
    assert not bad_keys, (
        "trusted-callers.toml keys must be relative to --config-dir "
        "(which is enforcement/), not relative to plugin root. "
        f"These keys will be rejected by the daemon: {bad_keys}. "
        "Regenerate with scripts/hash-trusted-callers.sh."
    )


def test_trusted_callers_hashes_match_files():
    """Every hash in trusted-callers.toml must match the current file content.

    The daemon authenticates hook scripts by SHA-256 against this manifest.
    If a hook is edited but the hash isn't regenerated via
    scripts/hash-trusted-callers.sh, daemon auth silently fails and the
    hook can't record authed events.

    The file's own comment claims "the pre-commit hook verifies this
    manifest is up to date" — no such hook exists. This test is that
    check, running in pytest instead.
    """
    import hashlib

    repo_root = Path(__file__).parent.parent
    manifest_path = repo_root / "enforcement" / "trusted-callers.toml"
    manifest = tomllib.loads(manifest_path.read_text())

    mismatches: list[str] = []
    for rel_path, expected in manifest.get("callers", {}).items():
        if not expected.startswith("sha256:"):
            mismatches.append(f"{rel_path}: manifest entry missing sha256: prefix")
            continue
        expected_hash = expected.removeprefix("sha256:")
        # Manifest keys match the daemon's caller-identification path, which
        # strips the --config-dir prefix: `hooks/primer.py` really lives at
        # `enforcement/hooks/primer.py`, while `hooks/subagent_findings_check.py`
        # lives at the plugin-root path of the same name. Try both.
        candidates = [
            repo_root / "enforcement" / rel_path,
            repo_root / rel_path,
        ]
        full_path = next((p for p in candidates if p.is_file()), None)
        if full_path is None:
            mismatches.append(
                f"{rel_path}: file not found at any of "
                + ", ".join(str(p) for p in candidates)
            )
            continue
        actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            mismatches.append(
                f"{rel_path}: manifest has {expected_hash[:12]}..., "
                f"file is {actual_hash[:12]}.... "
                f"Regenerate with scripts/hash-trusted-callers.sh."
            )

    assert not mismatches, (
        "trusted-callers.toml is stale. The daemon will reject these callers:\n  "
        + "\n  ".join(mismatches)
    )

# Holtz JSONL Migration — Implementation Plan

**Goal:** Migrate all Holtz audit artifacts from scattered markdown + binary ledger to JSONL ledgers managed by sahjhan v0.2.0. Per-run ledgers hold every event; a project ledger accumulates cross-run state. Markdown files become rendered views.

**Architecture:** Multi-ledger (per-run `runs/N/ledger.jsonl` + project-level `project.jsonl`). Enforcement config updated for breadcrumb fields, query gates, and ledger-aware renders. Legacy archive migrated via `scripts/migrate_legacy.py`.

**Tech Stack:** Python 3.10+, sahjhan v0.2.0 (Rust CLI with JSONL + DataFusion + multi-ledger), Tera templates, TOML config.

**Dependency:** Requires sahjhan v0.2.0. Phases 1-4 are sahjhan-independent (config, templates, migration script, SKILL.md). Phases 5-6 require sahjhan v0.2.0 for integration testing and live cutover.

**Branch:** `feat/jsonl-migration` off `dev`.

---

## Phase 1 — Enforcement Config (sahjhan-independent)

Config files are declarative TOML consumed by sahjhan at runtime. We can update them now; they only activate when sahjhan v0.2.0 loads them.

### Task 1.1: Update events.toml with breadcrumbs and new event types

**Files:** modify `enforcement/events.toml`, modify `tests/test_enforcement_config.py` (create)

**Steps:**

- [ ] Write test `tests/test_enforcement_config.py` that loads `events.toml` via `tomllib` and asserts:
  - Every event type has `project`, `run`, `auditor` breadcrumb fields
  - `finding` has `phase` and `step` fields
  - New event types exist: `recon_finding`, `audit_claim`, `test_audit_finding`, `code_audit_finding`, `merge_result`, `convergence_iteration`, `run_summary`, `graph_delta`, `pattern_discovered`, `baseline_delta`, `run_postmortem`
  - Field patterns are valid regexes

```python
# tests/test_enforcement_config.py
import tomllib
from pathlib import Path

EVENTS_TOML = Path(__file__).parent.parent / "enforcement" / "events.toml"

BREADCRUMBS = ["project", "run", "auditor"]

NEW_EVENT_TYPES = [
    "recon_finding", "audit_claim", "test_audit_finding",
    "code_audit_finding", "merge_result", "convergence_iteration",
    "run_summary", "graph_delta", "pattern_discovered",
    "baseline_delta", "run_postmortem",
]

def test_all_events_have_breadcrumbs():
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    for name, event in cfg["events"].items():
        field_names = [f["name"] for f in event["fields"]]
        for bc in BREADCRUMBS:
            assert bc in field_names, f"{name} missing breadcrumb '{bc}'"

def test_new_event_types_exist():
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    for et in NEW_EVENT_TYPES:
        assert et in cfg["events"], f"Missing event type '{et}'"
```

- [ ] Run test — confirm it fails (breadcrumbs missing, new types missing)
- [ ] Add breadcrumb fields (`project`, `run`, `auditor`) to every existing event type
- [ ] Add `phase` and `step` fields to event types where semantically applicable: `finding`, `finding_resolved`, `recon_step`, `blast_radius`, `iteration_complete`, `hardening_complete`, `set_member_complete`, `pattern_analysis_complete`
- [ ] Add new event types with their fields per the design spec:

```toml
[events.recon_finding]
description = "A recon finding from reconnaissance phase"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string", pattern = "^\\d+$" },
    { name = "topic", type = "string" },
    { name = "content", type = "string" },
]

[events.audit_claim]
description = "A documentation claim verified during audit"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "source", type = "string" },
    { name = "claim", type = "string" },
    { name = "verdict", type = "string", pattern = "^(VERIFIED|OVERSTATED|FALSE|MISSING)$" },
    { name = "evidence", type = "string" },
]

[events.test_audit_finding]
description = "A test quality finding from test audit"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "test_file", type = "string" },
    { name = "anti_pattern", type = "string" },
    { name = "evidence", type = "string" },
]

[events.code_audit_finding]
description = "A code audit finding from adversarial analysis"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "module", type = "string" },
    { name = "concern", type = "string" },
    { name = "evidence", type = "string" },
]

[events.merge_result]
description = "Merge report from Holtz/Justine merge"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "agreements", type = "string", pattern = "^\\d+$" },
    { name = "holtz_only", type = "string", pattern = "^\\d+$" },
    { name = "justine_only", type = "string", pattern = "^\\d+$" },
    { name = "contradictions", type = "string", pattern = "^\\d+$" },
]

[events.convergence_iteration]
description = "A convergence fix-loop iteration"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "iteration", type = "string", pattern = "^\\d+$" },
    { name = "open", type = "string", pattern = "^\\d+$" },
    { name = "resolved", type = "string", pattern = "^\\d+$" },
    { name = "test_count", type = "string", pattern = "^\\d+$" },
    { name = "tests_passed", type = "string", pattern = "^(true|false)$" },
]

[events.run_summary]
description = "End-of-run summary"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "total_findings", type = "string", pattern = "^\\d+$" },
    { name = "resolved", type = "string", pattern = "^\\d+$" },
    { name = "prediction_accuracy", type = "string" },
    { name = "recommendations", type = "string" },
]

[events.graph_delta]
description = "Impact graph mutation"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "operation", type = "string", pattern = "^(add_edge|remove_edge|snapshot)$" },
    { name = "source", type = "string" },
    { name = "target", type = "string" },
    { name = "edge_type", type = "string" },
    { name = "note", type = "string" },
]

[events.pattern_discovered]
description = "A recurring pattern identified across findings"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "pattern_id", type = "string" },
    { name = "name", type = "string" },
    { name = "heuristic", type = "string" },
    { name = "instance_count", type = "string", pattern = "^\\d+$" },
]

[events.baseline_delta]
description = "Architecture baseline change"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "section", type = "string" },
    { name = "change_type", type = "string", pattern = "^(added|modified|removed)$" },
    { name = "content", type = "string" },
]

[events.run_postmortem]
description = "Post-run reflection or postmortem"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string" },
    { name = "step", type = "string" },
    { name = "content", type = "string" },
]
```

- [ ] Add `_migrated`, `_source`, `_migrated_at` as optional fields (no pattern) to all event types — OR define a migration-only config overlay. Prefer: add them only to the migration script's event construction, since sahjhan v0.2.0 should allow extra fields not in the schema when `_migrated=true`. Confirm with sahjhan spec. If sahjhan is strict, add them to each event type.
- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_enforcement_config.py -v
```

**Commit:** `feat(enforcement): add breadcrumb fields and new event types to events.toml`

### Task 1.2: Update transitions.toml for ledger-event gates

**Files:** modify `enforcement/transitions.toml`, add tests to `tests/test_enforcement_config.py`

**Steps:**

- [ ] Add test that loads `transitions.toml` and asserts:
  - `recon_complete` transition has NO `files_exist` gate (replaced by event checks)
  - `audit_complete` transition has NO `file_exists` gate for audit markdown
  - `recon_complete` uses `ledger_has_event` for `recon_finding` with step filters OR a `query` gate
  - `fix_commit` transition has a `query` circuit breaker gate
  - All `command_succeeds` gates referencing sahjhan use `--ledger` flag

```python
def test_recon_complete_uses_event_gates():
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    recon_transitions = [
        t for t in cfg["transitions"]
        if t["command"] == "recon_complete"
    ]
    assert len(recon_transitions) == 1
    gates = recon_transitions[0]["gates"]
    gate_types = [g["type"] for g in gates]
    assert "files_exist" not in gate_types
    assert any(g["type"] in ("ledger_has_event", "query") for g in gates)
```

- [ ] Run test — confirm it fails
- [ ] Replace `recon_complete` file-existence gates with event-count gates:

```toml
[[transitions]]
from = "recon"
to = "audit"
command = "recon_complete"
gates = [
    { type = "query", sql = "SELECT count(DISTINCT fields->>'step') >= 5 FROM events WHERE type='recon_finding'", expect = "true" },
    { type = "file_exists", path = "docs/holtz/impact-graph.json" },
    { type = "ledger_has_event", event = "recon_step", min_count = 5 },
    { type = "ledger_has_event", event = "justine_dispatched", min_count = 1 },
    { type = "command_succeeds", cmd = "sahjhan --ledger {{run_ledger}} event snapshot --field key=pre_audit_edge_count --field value=$(python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats | python -c \"import sys,json; print(json.load(sys.stdin)['edges'])\")" },
]
```

- [ ] Replace `audit_complete` file-existence gate with event-count gate:

```toml
[[transitions]]
from = "audit"
to = "merge_ready"
command = "audit_complete"
gates = [
    { type = "ledger_has_event", event = "audit_claim", min_count = 1 },
    { type = "snapshot_compare", cmd = "python ${CLAUDE_PLUGIN_ROOT}/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats", extract = "edges", compare = "gt", reference = "snapshot:pre_audit_edge_count" },
]
```

- [ ] Add circuit breaker query gate to `fix_commit`:

```toml
{ type = "query", sql = "SELECT count(*) < 15 FROM events WHERE type='state_transition' AND fields->>'command'='fix_commit'", expect = "true" },
```

- [ ] Update all `command_succeeds` gates that invoke `sahjhan` to use `--ledger {{run_ledger}}` where appropriate
- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_enforcement_config.py -v
```

**Commit:** `feat(enforcement): replace file-existence gates with event-count and query gates`

### Task 1.3: Update renders.toml with ledger field

**Files:** modify `enforcement/renders.toml`, add tests to `tests/test_enforcement_config.py`

**Steps:**

- [ ] Add test asserting every render entry has a `ledger` field

```python
def test_renders_have_ledger_field():
    cfg = tomllib.loads(RENDERS_TOML.read_text())
    for render in cfg["renders"]:
        assert "ledger" in render, f"Render for {render['target']} missing ledger field"
```

- [ ] Run test — confirm it fails
- [ ] Add `ledger` field to existing renders and add new renders for project-level templates:

```toml
[[renders]]
target = "STATUS.md"
template = "templates/status.md.tera"
trigger = "on_transition"
ledger = "run"

[[renders]]
target = "PUNCHLIST.md"
template = "templates/punchlist.md.tera"
trigger = "on_event"
event_types = ["finding", "finding_resolved"]
ledger = "run"

[[renders]]
target = "SUMMARY.md"
template = "templates/summary.md.tera"
trigger = "on_state"
state = "converged"
ledger = "run"

[[renders]]
target = "LIVING-PUNCHLIST.md"
template = "templates/living-punchlist.md.tera"
trigger = "on_event"
event_types = ["_checkpoint"]
ledger = "project"

[[renders]]
target = "architecture-baseline.md"
template = "templates/architecture-baseline.md.tera"
trigger = "on_event"
event_types = ["_checkpoint"]
ledger = "project"

[[renders]]
target = "patterns-brief.md"
template = "templates/patterns-brief.md.tera"
trigger = "on_event"
event_types = ["_checkpoint"]
ledger = "project"
```

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_enforcement_config.py -v
```

**Commit:** `feat(enforcement): add ledger field to renders and project-level render targets`

### Task 1.4: Update protocol.toml with checkpoint config

**Files:** modify `enforcement/protocol.toml`, add tests to `tests/test_enforcement_config.py`

**Steps:**

- [ ] Add test asserting `protocol.toml` has `paths.data_dir` pointing to `.sahjhan`, `ledgers` table with `run` and `project` entries, and new aliases for JSONL event types

```python
def test_protocol_has_ledger_config():
    cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    assert "ledgers" in cfg or "paths" in cfg
    # New aliases for content events
    aliases = cfg.get("aliases", {})
    assert "recon finding" in aliases
```

- [ ] Run test — confirm it fails
- [ ] Add ledger registry to protocol.toml:

```toml
[ledgers.run]
description = "Per-run audit ledger"
path_template = "docs/holtz/runs/{run}/ledger.jsonl"

[ledgers.project]
description = "Cross-run project ledger"
path = "docs/holtz/project.jsonl"
```

- [ ] Add new aliases for JSONL event recording:

```toml
"recon finding" = "event recon_finding"
"audit claim" = "event audit_claim"
"test finding" = "event test_audit_finding"
"code finding" = "event code_audit_finding"
"graph delta" = "event graph_delta"
```

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_enforcement_config.py -v
```

**Commit:** `feat(enforcement): add multi-ledger config and content event aliases to protocol.toml`

---

## Phase 2 — Templates (sahjhan-independent)

Templates are Tera files consumed by sahjhan at render time. We can write and test them syntactically now.

### Task 2.1: Update existing templates for breadcrumb-aware context

**Files:** modify `enforcement/templates/status.md.tera`, `enforcement/templates/punchlist.md.tera`, `enforcement/templates/summary.md.tera`

**Steps:**

- [ ] Update the comment header in each template from `v0.1.1` to `v0.2.0`
- [ ] The render context shape (`protocol`, `state`, `events`, `sets`, `ledger_len`, `violations`) is unchanged per the design spec. The events now carry breadcrumb fields in `e.fields`, but existing templates only access fields they already know (`e.fields.id`, `e.fields.severity`, etc.) — so they remain correct without changes to field access patterns.
- [ ] Add `run` and `auditor` display to status.md.tera header:

```
**Run:** {{ events | filter(attribute="event_type", value="state_transition") | first | get(key="fields") | get(key="run", default="?") }}
**Auditor:** holtz
```

- [ ] Verify templates still parse correctly (no syntax errors) — this is a manual check until sahjhan v0.2.0 `render --dry-run` is available. For now, validate with a simple Python regex test that all `{{ }}` and `{% %}` blocks are balanced.

**Commit:** `feat(templates): update existing templates for v0.2.0 breadcrumb context`

### Task 2.2: Create project-level templates

**Files:** create `enforcement/templates/living-punchlist.md.tera`, create `enforcement/templates/architecture-baseline.md.tera`, create `enforcement/templates/patterns-brief.md.tera`

**Steps:**

- [ ] Create `living-punchlist.md.tera` — reads `_checkpoint` events from project ledger, renders accumulated punchlist patterns, hotspots, and recurring findings:

```
{# enforcement/templates/living-punchlist.md.tera — reads from project ledger #}
# Living Punchlist

**Updated:** {{ now() | date(format="%Y-%m-%d") }}
**Source:** project.jsonl checkpoints

{% set checkpoints = events | filter(attribute="event_type", value="_checkpoint") -%}
{% set latest = checkpoints | last -%}

{% if latest -%}
## Recurring Patterns

{{ latest.fields.living_punchlist_patterns | default(value="No patterns recorded yet.") }}

## Hotspot Files

{{ latest.fields.living_punchlist_hotspots | default(value="No hotspots recorded yet.") }}

## Cross-Run Findings

{{ latest.fields.living_punchlist_findings | default(value="No cross-run findings yet.") }}
{% else -%}
No checkpoint data available yet. Complete a run and write checkpoints to project.jsonl.
{% endif %}
```

- [ ] Create `architecture-baseline.md.tera` — reads `_checkpoint` events, renders architecture snapshot:

```
{# enforcement/templates/architecture-baseline.md.tera — reads from project ledger #}
# Architecture Baseline

{% set checkpoints = events | filter(attribute="event_type", value="_checkpoint") -%}
{% set latest = checkpoints | last -%}

{% if latest -%}
{{ latest.fields.baseline_content | default(value="No baseline recorded yet.") }}
{% else -%}
No checkpoint data available yet.
{% endif %}
```

- [ ] Create `patterns-brief.md.tera` — reads `_checkpoint` events, renders patterns brief:

```
{# enforcement/templates/patterns-brief.md.tera — reads from project ledger #}
# Patterns Brief

{% set checkpoints = events | filter(attribute="event_type", value="_checkpoint") -%}
{% set latest = checkpoints | last -%}

{% if latest -%}
{{ latest.fields.patterns_brief_content | default(value="No patterns recorded yet.") }}
{% else -%}
No checkpoint data available yet.
{% endif %}
```

- [ ] Add a test in `tests/test_enforcement_config.py` that checks all `.tera` files referenced in `renders.toml` exist on disk:

```python
def test_render_templates_exist():
    renders_cfg = tomllib.loads(RENDERS_TOML.read_text())
    config_dir = RENDERS_TOML.parent
    for render in renders_cfg["renders"]:
        tmpl = config_dir / render["template"]
        assert tmpl.exists(), f"Template {render['template']} not found"
```

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_enforcement_config.py::test_render_templates_exist -v
```

**Commit:** `feat(templates): add project-level living-punchlist, baseline, and patterns-brief templates`

---

## Phase 3 — Legacy Migration Script (sahjhan-independent)

The migration script is pure Python. It reads markdown files and emits JSONL to stdout. No sahjhan dependency at parse time — the output is piped to `sahjhan ledger import` separately.

### Task 3.1: Create migration script scaffold with archive mapping

**Files:** create `scripts/migrate_legacy.py`, create `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write `tests/test_migrate_legacy.py` with initial tests:
  - `test_archive_mapping_complete` — mapping table covers all 37 archive dirs
  - `test_archive_mapping_unique_run_numbers` — no duplicate run numbers
  - `test_justine_matching` — standalone justine dirs match correct parent runs

```python
# tests/test_migrate_legacy.py
from scripts.migrate_legacy import ARCHIVE_MAP, JUSTINE_MAP

def test_archive_mapping_complete():
    assert len(ARCHIVE_MAP) == 30  # 30 holtz dirs (excl current+shakedown)

def test_archive_mapping_unique_run_numbers():
    run_numbers = [entry["run"] for entry in ARCHIVE_MAP.values()]
    assert len(run_numbers) == len(set(run_numbers))

def test_justine_matching():
    assert JUSTINE_MAP["justine-2026-03-22"] == 19
    assert JUSTINE_MAP["justine-2026-03-25-run19"] == 30
```

- [ ] Run test — confirm it fails (module doesn't exist)
- [ ] Create `scripts/migrate_legacy.py` with:
  - `ARCHIVE_MAP` dict: `{ "bug-hunter-2026-03-19": {"run": 1, "auditor": "holtz", "era": "proto"}, ... }` for all 30 holtz directories from the design spec table
  - `JUSTINE_MAP` dict: `{ "justine-2026-03-22": 19, ... }` for all 7 standalone justine dirs
  - CLI entry point: `--run N --input DIR [--project PROJECT]`

```python
#!/usr/bin/env python3
"""Migrate legacy Holtz archive directories to JSONL events.

Reads markdown files from an archived run directory and emits
JSONL events to stdout. Output is piped to sahjhan ledger import.

Usage:
    python scripts/migrate_legacy.py --input docs/holtz/archive/2026-03-22-run9/
    python scripts/migrate_legacy.py --run 9 --input docs/holtz/archive/2026-03-22-run9/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE_MAP: dict[str, dict] = {
    "bug-hunter-2026-03-19": {"run": 1, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21": {"run": 2, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run2": {"run": 3, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run3": {"run": 4, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run4": {"run": 5, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run5": {"run": 6, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run6": {"run": 7, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-21-run7": {"run": 8, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-22": {"run": 9, "auditor": "holtz", "era": "proto"},
    "bug-hunter-2026-03-22-run2": {"run": 10, "auditor": "holtz", "era": "proto"},
    "stray-root-2026-03-22": {"run": 11, "auditor": "holtz", "era": "proto"},
    "2026-03-19-run2": {"run": 12, "auditor": "holtz", "era": "numbered"},
    "2026-03-20-run2": {"run": 13, "auditor": "holtz", "era": "numbered"},
    "2026-03-20-run3": {"run": 14, "auditor": "holtz", "era": "numbered"},
    "2026-03-20-run4": {"run": 15, "auditor": "holtz", "era": "numbered"},
    "2026-03-21-run5": {"run": 16, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run6": {"run": 17, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run7": {"run": 18, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run8": {"run": 19, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run9": {"run": 20, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run10": {"run": 21, "auditor": "holtz", "era": "numbered"},
    "2026-03-22-run11": {"run": 22, "auditor": "holtz", "era": "numbered"},
    "2026-03-23-run12": {"run": 23, "auditor": "holtz", "era": "numbered"},
    "2026-03-24-run13": {"run": 24, "auditor": "holtz", "era": "numbered"},
    "2026-03-24-run14": {"run": 25, "auditor": "holtz", "era": "numbered"},
    "2026-03-24-run15": {"run": 26, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run16": {"run": 27, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run17": {"run": 28, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run18": {"run": 29, "auditor": "holtz", "era": "numbered"},
    "2026-03-25-run19": {"run": 30, "auditor": "holtz", "era": "numbered"},
}

JUSTINE_MAP: dict[str, int] = {
    "justine-2026-03-22": 19,
    "justine-2026-03-22-run11": 22,
    "justine-2026-03-23-run12": 23,
    "justine-2026-03-24-run14": 25,
    "justine-2026-03-25": 28,
    "justine-2026-03-25-run19": 30,
    "justine-2026-03-25-run20": 31,
}
```

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_migrate_legacy.py -v
```

**Commit:** `feat(migration): scaffold migrate_legacy.py with archive and justine mapping tables`

### Task 3.2: Implement punchlist parser

**Files:** modify `scripts/migrate_legacy.py`, modify `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write test with fixture markdown for each punchlist variant:
  - `PUNCHLIST.md` (standard `### BH-NNN:` blocks)
  - `BUG-HUNTER-PUNCHLIST.md` (proto era)
  - `PUNCHLIST-MERGED.md` (merged with status column)

```python
SAMPLE_PUNCHLIST = """\
# Punchlist

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:108 | public-contract | Pattern count stale | OPEN |
| BH-002 | test/gap | tests/test_foo.py | component | Missing edge case | RESOLVED |
"""

def test_parse_punchlist_findings():
    events = parse_punchlist(SAMPLE_PUNCHLIST, run="9", auditor="holtz", source="PUNCHLIST.md")
    findings = [e for e in events if e["type"] == "finding"]
    resolved = [e for e in events if e["type"] == "finding_resolved"]
    assert len(findings) == 2
    assert findings[0]["fields"]["id"] == "BH-001"
    assert findings[0]["fields"]["severity"] == "HIGH"
    assert len(resolved) == 1
    assert resolved[0]["fields"]["id"] == "BH-002"
```

- [ ] Run test — confirm it fails
- [ ] Implement `parse_punchlist(content, run, auditor, source) -> list[dict]`:
  - Detect format: table-based (newer) vs `### BH-NNN:` block-based (proto era)
  - Extract severity from `## SEVERITY` headers or table rows
  - Extract finding fields: id, category, location, perspective, description
  - Emit `finding_resolved` events for items with RESOLVED status
  - All events carry migration markers (`_migrated`, `_source`, `_migrated_at`)
- [ ] Handle `BUG-HUNTER-PUNCHLIST.md` filename — same parser, different filename detection
- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_migrate_legacy.py::test_parse_punchlist_findings -v
```

**Commit:** `feat(migration): implement punchlist parser for all naming eras`

### Task 3.3: Implement recon parser

**Files:** modify `scripts/migrate_legacy.py`, modify `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write test with fixture recon files:

```python
SAMPLE_RECON_LETTERED = {
    "0a-project-overview.md": "# Project Overview\n\nFour layers...",
    "0g-recon-summary.md": "# Recon Summary\n\n## Architecture\nFour layers...\n## Drift\n2 drifted nodes",
    "0h-predictions.md": "# Predictions\n\n| # | Target | Confidence |\n|---|--------|------------|\n| 1 | README | HIGH |",
}

def test_parse_recon_lettered():
    events = parse_recon_dir(SAMPLE_RECON_LETTERED, run="19", auditor="holtz")
    findings = [e for e in events if e["type"] == "recon_finding"]
    predictions = [e for e in events if e["type"] == "prediction"]
    assert len(findings) >= 2  # at least overview + summary sections
    assert findings[0]["fields"]["step"] == "0"
    assert len(predictions) >= 1
```

- [ ] Run test — confirm it fails
- [ ] Implement `parse_recon_dir(files, run, auditor) -> list[dict]`:
  - Map filenames to steps using the three-era table from the design spec:
    - Lettered: `0a` → step 0, `0b`/`0c`/`0c1`/`0d` → step 1, `0e`/`0f` → step 2, `0g`/`0-pattern`/`0-recommendation` → step 3, `0h` → step 4
    - Numbered: `step0` → 0, `step1` → 1, `step2`/`step2-cold` → 2, `step3` → 3, `step4` → 4
    - Justine variant: `predictions.md` → step 4, `recon-summary.md` → step 3
  - Split content on `## ` headers into separate `recon_finding` events with `topic` field
  - Parse prediction tables from step 4 files into `prediction` events
- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_migrate_legacy.py::test_parse_recon_lettered -v
```

**Commit:** `feat(migration): implement recon parser for lettered, numbered, and justine variants`

### Task 3.4: Implement audit parser

**Files:** modify `scripts/migrate_legacy.py`, modify `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write test with fixture audit files:

```python
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
```

- [ ] Run test — confirm it fails
- [ ] Implement `parse_audit_file(filename, content, run, auditor) -> list[dict]`:
  - `1-doc-claims.md` → `audit_claim` events (table rows)
  - `2-test-*.md` → `test_audit_finding` events (test file, anti-pattern, evidence)
  - `3-*.md` / `3a-*.md` / `3b-*.md` → `code_audit_finding` events
  - `4-resweep.md` / `convergence-sweep-*.md` / `final-sweep.md` → `code_audit_finding` events at step 16
  - Handle batch files (`2-test-batch1.md`, `2-test-batch2.md`) as sequential batch events
- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_migrate_legacy.py::test_parse_audit_claims -v
```

**Commit:** `feat(migration): implement audit file parser for claims, test, and code findings`

### Task 3.5: Implement summary, merge, status, and postmortem parsers

**Files:** modify `scripts/migrate_legacy.py`, modify `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write tests for each parser:
  - `test_parse_summary` — extracts `run_summary` event with totals
  - `test_parse_merge_report` — extracts `merge_result` event with counts
  - `test_parse_status` — reconstructs `state_transition` events from checkbox list
  - `test_parse_history_json` — extracts `convergence_iteration` events
  - `test_parse_postmortem` — extracts `run_postmortem` event
- [ ] Run tests — confirm they fail
- [ ] Implement parsers:
  - `parse_summary(content, run, auditor, source)` → `run_summary` + `prediction` + `prediction_outcome` events
  - `parse_merge_report(content, run, auditor, source)` → `merge_result` event
  - `parse_status(content, run, auditor, source)` → sequence of `state_transition` events
  - `parse_history_json(content, run, auditor, source)` → `convergence_iteration` events
  - `parse_postmortem(content, run, auditor, source)` → `run_postmortem` event
- [ ] Run tests — confirm they pass

```bash
python -m pytest tests/test_migrate_legacy.py -v
```

**Commit:** `feat(migration): implement summary, merge, status, history, and postmortem parsers`

### Task 3.6: Implement directory orchestrator and justine handling

**Files:** modify `scripts/migrate_legacy.py`, modify `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write test for the orchestrator:

```python
def test_migrate_directory(tmp_path):
    """Create a minimal archive dir and verify full migration."""
    run_dir = tmp_path / "2026-03-22-run9"
    run_dir.mkdir()
    (run_dir / "PUNCHLIST.md").write_text(SAMPLE_PUNCHLIST)
    (run_dir / "STATUS.md").write_text(SAMPLE_STATUS)
    recon = run_dir / "recon"
    recon.mkdir()
    (recon / "step0-project-overview.md").write_text("# Overview\n\nContent here")

    events = migrate_directory(run_dir, run=20, auditor="holtz", project="holtz")
    assert len(events) > 0
    # All events have breadcrumbs
    for e in events:
        assert e["fields"]["project"] == "holtz"
        assert e["fields"]["run"] == "20"
        assert e["fields"]["auditor"] == "holtz"
        assert e["fields"]["_migrated"] == "true"
```

- [ ] Write test for justine nested directory handling:

```python
def test_migrate_nested_justine(tmp_path):
    run_dir = tmp_path / "2026-03-22-run8"
    run_dir.mkdir()
    justine = run_dir / "justine"
    justine.mkdir()
    (justine / "PUNCHLIST.md").write_text(SAMPLE_PUNCHLIST.replace("BH-", "BJ-"))
    events = migrate_directory(run_dir, run=19, auditor="holtz", project="holtz")
    justine_events = [e for e in events if e["fields"]["auditor"] == "justine"]
    assert len(justine_events) > 0
```

- [ ] Run tests — confirm they fail
- [ ] Implement `migrate_directory(path, run, auditor, project) -> list[dict]`:
  - Detect which files exist and call appropriate parsers
  - Handle nested `justine/` subdirectory with `auditor="justine"`
  - Handle `justine/impact-graph.json` as `graph_delta` snapshot event
  - Apply migration markers to all events
  - Order events by: state_transitions first, then recon, then audit, then findings, then resolution
- [ ] Implement CLI `main()`:
  - `--input DIR` — archive directory to migrate
  - `--run N` — override run number (default: look up from `ARCHIVE_MAP`)
  - `--project PROJECT` — project name (default: `holtz`)
  - `--all` — migrate all directories from `ARCHIVE_MAP` + `JUSTINE_MAP`
  - Output: JSONL to stdout, one event per line
- [ ] Run tests — confirm they pass

```bash
python -m pytest tests/test_migrate_legacy.py -v
```

**Commit:** `feat(migration): implement directory orchestrator with justine handling and CLI`

### Task 3.7: Implement project ledger builder

**Files:** modify `scripts/migrate_legacy.py`, modify `tests/test_migrate_legacy.py`

**Steps:**

- [ ] Write test:

```python
def test_build_project_ledger():
    events = build_project_ledger(
        runs=[(1, "holtz"), (2, "holtz"), (3, "holtz")],
        impact_graph_path=Path("docs/holtz/impact-graph.json"),
        project="holtz",
    )
    registered = [e for e in events if e["type"] == "run_registered"]
    assert len(registered) == 3
    checkpoints = [e for e in events if e["type"] == "_checkpoint"]
    assert len(checkpoints) >= 1
```

- [ ] Run test — confirm it fails
- [ ] Implement `build_project_ledger(runs, impact_graph_path, project) -> list[dict]`:
  - Emit `run_registered` and `run_completed` events for each run
  - Read current `impact-graph.json`, `patterns-brief.md`, `architecture-baseline.md`, `LIVING-PUNCHLIST.md` (or `PUNCHLIST-MERGED.md`) and emit `_checkpoint` events with their content
- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_migrate_legacy.py -v
```

**Commit:** `feat(migration): implement project ledger builder with checkpoint events`

---

## Phase 4 — Hook Scripts and SKILL.md (sahjhan-independent)

### Task 4.1: Update enforcement hooks for --ledger flag

**Files:** modify `enforcement/hooks/primer.py`, `enforcement/hooks/stop_gate.py`, `enforcement/hooks/bash_guard.py`

**Steps:**

- [ ] Write tests in `tests/test_hooks.py`:
  - `test_primer_uses_ledger_flag` — mock subprocess and verify `--ledger` in sahjhan command args
  - `test_stop_gate_uses_ledger_flag` — same
  - `test_bash_guard_uses_ledger_flag` — same

- [ ] Run tests — confirm they fail
- [ ] Update `primer.py`:
  - Detect active run ledger: look for `docs/holtz/runs/*/ledger.jsonl` or read from a `.sahjhan/active-run` marker file
  - Pass `--ledger run-N` to all `sahjhan` subprocess calls
  - Fallback: if no run-specific ledger found, use existing behavior (backwards compatible with v0.1.x)

```python
# In primer.py, update sahjhan invocations:
def _active_ledger(cwd: str) -> str | None:
    """Detect the active run ledger name."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-run")
    if os.path.isfile(active_file):
        with open(active_file) as f:
            return f.read().strip()
    return None

# Then in subprocess calls:
ledger = _active_ledger(cwd)
cmd = [binary, "--config-dir", config_dir]
if ledger:
    cmd.extend(["--ledger", ledger])
cmd.extend(["status", "--json"])
```

- [ ] Update `stop_gate.py` — same pattern: detect active ledger, pass `--ledger`
- [ ] Update `bash_guard.py` — same pattern for `manifest verify` and `event protocol_violation` calls
- [ ] Extract `_active_ledger` to `enforcement/hooks/_common.py` bridge to avoid duplication
- [ ] Run tests — confirm they pass

```bash
python -m pytest tests/test_hooks.py -v
```

**Commit:** `feat(hooks): update enforcement hooks for multi-ledger --ledger flag`

### Task 4.2: Update SKILL.md for multi-ledger CLI and new event workflow

**Files:** modify `skills/holtz/SKILL.md`

**Steps:**

- [ ] Update Sahjhan Enforcement Quick Reference section:
  - Add run ledger creation at start:
    ```
    sahjhan ledger create --name run-N --path docs/holtz/runs/N/ledger.jsonl
    ```
  - Update all `sahjhan event` examples to include `--ledger run-N`
  - Add new event recording examples:
    ```
    sahjhan --ledger run-N event recon_finding --field step=0 --field topic=architecture --field content="Four layers..."
    sahjhan --ledger run-N event audit_claim --field source="README.md:15" --field claim="Supports 13 lenses" --field verdict=VERIFIED --field evidence="..."
    ```
  - Add checkpoint workflow:
    ```
    sahjhan --ledger run-N ledger checkpoint   # before /clear
    ```
  - Add project ledger checkpoint for post-convergence:
    ```
    sahjhan --ledger project event _checkpoint --field ...
    ```

- [ ] Update recon steps (Steps 0-4):
  - Change from "write to `docs/holtz/recon/stepN-*.md`" to "record `recon_finding` events"
  - Keep impact graph commands unchanged (standalone file)
  - Update step 4 to record `prediction` events instead of writing prediction file

- [ ] Update audit steps (Steps 6-8):
  - Change from "write to `docs/holtz/audit/*.md`" to "record `audit_claim`, `test_audit_finding`, `code_audit_finding` events"

- [ ] Update merge step (Step 9):
  - Add `merge_result` event recording

- [ ] Update convergence boundary:
  - Add `sahjhan --ledger run-N ledger checkpoint` before `/clear`

- [ ] Update post-convergence steps (Steps 17-20):
  - Add project ledger checkpoint writing for accumulated state

- [ ] Update Output Directory section:
  - Document new `runs/N/` structure
  - Document `project.jsonl`
  - Remove references to `recon/` and `audit/` subdirectories as write targets

**Commit:** `feat(skill): update SKILL.md for multi-ledger CLI syntax and event recording workflow`

---

## Phase 5 — Integration Testing (requires sahjhan v0.2.0)

**BLOCKED until sahjhan v0.2.0 ships.** Tasks 5.1-5.3 cannot run without the sahjhan binary supporting `--ledger`, `ledger create`, `ledger import`, `query`, and JSONL storage.

### Task 5.1: Vendor sahjhan v0.2.0

**Files:** modify `scripts/vendor-sahjhan.sh`, update `bin/sahjhan*`

**Steps:**

- [ ] Update `scripts/vendor-sahjhan.sh` to fetch v0.2.0 release
- [ ] Vendor the binary: `./scripts/vendor-sahjhan.sh`
- [ ] Verify: `bin/sahjhan --version` outputs `0.2.0`
- [ ] Run existing test suite to confirm no regressions:

```bash
python -m pytest --tb=short -q
```

**Commit:** `chore: vendor sahjhan v0.2.0`

### Task 5.2: Integration test — event schema validation

**Files:** create `tests/test_jsonl_integration.py`

**Steps:**

- [ ] Write integration test that:
  - Creates a temporary run ledger via `sahjhan ledger create`
  - Records one event of each new type with all required fields
  - Reads back via `sahjhan ledger dump` and validates JSON structure
  - Verifies breadcrumb fields are present on all events
  - Verifies migration markers are preserved through import

```python
# tests/test_jsonl_integration.py
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

SAHJHAN = Path(__file__).parent.parent / "bin" / "sahjhan"

@pytest.mark.skipif(not SAHJHAN.exists(), reason="sahjhan not vendored")
class TestJSONLIntegration:
    def test_record_and_read_finding(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        config = Path(__file__).parent.parent / "enforcement"
        subprocess.run([
            str(SAHJHAN), "--config-dir", str(config),
            "ledger", "create", "--name", "test-run",
            "--path", str(ledger),
        ], check=True, cwd=str(tmp_path))

        subprocess.run([
            str(SAHJHAN), "--config-dir", str(config),
            "--ledger", "test-run",
            "event", "finding",
            "--field", "project=holtz",
            "--field", "run=1",
            "--field", "auditor=holtz",
            "--field", "phase=audit",
            "--field", "step=7",
            "--field", "id=BH-001",
            "--field", "severity=HIGH",
            "--field", "category=doc/drift",
            "--field", "location=README.md:108",
            "--field", "perspective=public-contract",
            "--field", "description=Pattern count stale",
            "--field", "predicted_by=1",
        ], check=True, cwd=str(tmp_path))

        lines = ledger.read_text().strip().split("\n")
        events = [json.loads(line) for line in lines]
        findings = [e for e in events if e["type"] == "finding"]
        assert len(findings) == 1
        assert findings[0]["fields"]["project"] == "holtz"
        assert findings[0]["fields"]["run"] == "1"
```

- [ ] Run test — confirm it passes with sahjhan v0.2.0

```bash
python -m pytest tests/test_jsonl_integration.py -v
```

**Commit:** `test: add JSONL integration tests for event schema validation`

### Task 5.3: Integration test — migration import pipeline

**Files:** modify `tests/test_jsonl_integration.py`

**Steps:**

- [ ] Write integration test that:
  - Runs `migrate_legacy.py --input` on a real archive directory
  - Pipes output to `sahjhan ledger import`
  - Reads back the ledger and validates event count and structure
  - Verifies `_migrated=true` markers
  - Runs a DataFusion query across the imported ledger

```python
@pytest.mark.skipif(not SAHJHAN.exists(), reason="sahjhan not vendored")
def test_migration_import_pipeline(self, tmp_path):
    archive = Path("docs/holtz/archive/bug-hunter-2026-03-19")
    if not archive.exists():
        pytest.skip("Archive not available")

    # Generate JSONL
    result = subprocess.run(
        [sys.executable, "scripts/migrate_legacy.py",
         "--input", str(archive), "--run", "1"],
        capture_output=True, text=True, check=True,
    )
    jsonl_lines = result.stdout.strip().split("\n")
    assert len(jsonl_lines) > 0

    # Import into ledger
    ledger_path = tmp_path / "ledger.jsonl"
    (tmp_path / "ledger.jsonl").write_text(result.stdout)

    # Validate structure
    for line in jsonl_lines:
        event = json.loads(line)
        assert "type" in event
        assert "fields" in event
        assert event["fields"]["_migrated"] == "true"
        assert event["fields"]["run"] == "1"
```

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_jsonl_integration.py -v
```

**Commit:** `test: add migration import pipeline integration test`

### Task 5.4: Integration test — template rendering

**Files:** modify `tests/test_jsonl_integration.py`

**Steps:**

- [ ] Write integration test that:
  - Creates a run ledger with representative events
  - Calls `sahjhan --ledger test-run render` to generate STATUS.md, PUNCHLIST.md
  - Verifies rendered files contain expected content (finding IDs, severity counts)
  - Tests project-level template rendering from project ledger

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_jsonl_integration.py -v
```

**Commit:** `test: add template rendering integration tests`

### Task 5.5: Integration test — query gates

**Files:** modify `tests/test_jsonl_integration.py`

**Steps:**

- [ ] Write integration test that:
  - Creates a ledger with recon_finding events for steps 0-4
  - Runs `sahjhan gate check recon_complete` and verifies it passes
  - Creates a ledger with only steps 0-2
  - Runs `sahjhan gate check recon_complete` and verifies it fails
  - Tests the circuit breaker query gate (15 fix iterations)

- [ ] Run test — confirm it passes

```bash
python -m pytest tests/test_jsonl_integration.py -v
```

**Commit:** `test: add query gate integration tests`

---

## Phase 6 — Project Structure Migration (requires sahjhan v0.2.0)

### Task 6.1: Execute full legacy migration

**Files:** create `docs/holtz/runs/` directory tree, create `docs/holtz/project.jsonl`

**Steps:**

- [ ] Run migration for all archive directories:

```bash
# Migrate each holtz archive directory
for dir in docs/holtz/archive/*/; do
    dirname=$(basename "$dir")
    # Skip justine-* dirs (handled separately)
    [[ "$dirname" == justine-* ]] && continue
    python scripts/migrate_legacy.py --input "$dir" > "/tmp/holtz-migration-$dirname.jsonl"
done

# Import into sahjhan ledgers
for dir in docs/holtz/archive/*/; do
    dirname=$(basename "$dir")
    [[ "$dirname" == justine-* ]] && continue
    run_num=$(python -c "from scripts.migrate_legacy import ARCHIVE_MAP; print(ARCHIVE_MAP['$dirname']['run'])")
    mkdir -p "docs/holtz/runs/$run_num"
    sahjhan ledger create --name "run-$run_num" --path "docs/holtz/runs/$run_num/ledger.jsonl"
    cat "/tmp/holtz-migration-$dirname.jsonl" | sahjhan ledger import --name "run-$run_num"
done

# Migrate standalone justine directories into their matched runs
for dir in docs/holtz/archive/justine-*/; do
    dirname=$(basename "$dir")
    run_num=$(python -c "from scripts.migrate_legacy import JUSTINE_MAP; print(JUSTINE_MAP['$dirname'])")
    python scripts/migrate_legacy.py --input "$dir" --run "$run_num" | \
        sahjhan ledger import --name "run-$run_num"
done
```

- [ ] Build project ledger:

```bash
python scripts/migrate_legacy.py --build-project > docs/holtz/project.jsonl
```

- [ ] Verify event counts per run match expected artifact counts:

```bash
for run_dir in docs/holtz/runs/*/; do
    run_num=$(basename "$run_dir")
    count=$(wc -l < "$run_dir/ledger.jsonl")
    echo "Run $run_num: $count events"
done
```

- [ ] Run integration tests against real migrated data:

```bash
python -m pytest tests/test_jsonl_integration.py -v
```

**Commit:** `feat(migration): execute full legacy migration to JSONL ledgers`

### Task 6.2: Post-migration cleanup

**Files:** modify `.gitignore`, remove `docs/holtz/archive/` (or move to `.gitignore`), remove `docs/holtz/HISTORY.json`, remove `docs/holtz/.sahjhan/ledger.bin`

**Steps:**

- [ ] Verify all archive data is in `runs/`:

```bash
# Spot-check: compare finding counts
python scripts/migrate_legacy.py --verify --input docs/holtz/archive/2026-03-25-run19/ --run 30
```

- [ ] Update `.gitignore`:

```
# Legacy archive (migrated to runs/)
docs/holtz/archive/
```

- [ ] Remove binary ledger: `rm docs/holtz/.sahjhan/ledger.bin`
- [ ] Remove HISTORY.json: `rm docs/holtz/HISTORY.json`
- [ ] Update `enforcement/hooks/write_guard.py` MANAGED_PATHS to include `docs/holtz/runs/`
- [ ] Run full test suite:

```bash
python -m pytest --tb=short -q
ruff check .
mypy skills/holtz/scripts/ hooks/ enforcement/hooks/
```

**Commit:** `chore(migration): post-migration cleanup — remove binary ledger and legacy references`

### Task 6.3: Render initial views from migrated ledgers

**Steps:**

- [ ] Render views for the latest run:

```bash
sahjhan --ledger run-30 render
```

- [ ] Render project-level views:

```bash
sahjhan --ledger project render
```

- [ ] Verify rendered files match expected content:
  - `docs/holtz/STATUS.md` — state transitions from run 30
  - `docs/holtz/PUNCHLIST.md` — findings from run 30
  - `docs/holtz/LIVING-PUNCHLIST.md` — accumulated patterns
  - `docs/holtz/architecture-baseline.md` — current baseline
  - `docs/holtz/patterns-brief.md` — pattern library

- [ ] Git diff the rendered files against their current versions to validate no data loss

**Commit:** `feat(migration): render initial views from migrated JSONL ledgers`

---

## Summary

| Phase | Tasks | Depends on sahjhan v0.2.0 | Estimated commits |
|-------|-------|---------------------------|-------------------|
| 1 — Enforcement Config | 1.1-1.4 | No | 4 |
| 2 — Templates | 2.1-2.2 | No | 2 |
| 3 — Migration Script | 3.1-3.7 | No | 7 |
| 4 — Hooks + SKILL.md | 4.1-4.2 | No | 2 |
| 5 — Integration Tests | 5.1-5.5 | **Yes** | 5 |
| 6 — Structure Migration | 6.1-6.3 | **Yes** | 3 |
| **Total** | **18 tasks** | | **23 commits** |

**Parallelism:** Phases 1-4 can proceed immediately and in parallel. Phase 5 is blocked on sahjhan v0.2.0 binary. Phase 6 is blocked on Phase 5 passing.

**Risk mitigation:** The migration script (Phase 3) is the largest body of work and the most likely to surface edge cases in archive parsing. Starting it early gives time to discover filename variations not captured in the design spec. Integration tests (Phase 5) will catch any schema mismatches between the config files and sahjhan v0.2.0's actual behavior.

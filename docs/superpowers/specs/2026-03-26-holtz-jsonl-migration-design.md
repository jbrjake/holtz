# Holtz — JSONL Migration and Multi-Ledger Integration

**Date:** 2026-03-26
**Status:** Design
**Repo:** jbrjake/holtz
**Dependency:** sahjhan v0.2.0 (JSONL + DataFusion + multi-ledger)

## Problem

Holtz currently stores audit artifacts as scattered markdown files (recon reports, punchlists, summaries) with a binary sahjhan ledger for enforcement. This has three problems:

1. **Not queryable across runs.** Finding trends (which categories recur, prediction accuracy over time, which perspectives find the most bugs) requires manually reading SUMMARY.md files from 30+ archived runs.
2. **Binary ledger isn't git-diffable.** The enforcement state is opaque in PRs and git history.
3. **Artifact format varies across runs.** Early runs used `BUG-HUNTER-PUNCHLIST.md` and different recon file naming. No unified schema.

## Solution

Move all Holtz artifacts into JSONL ledgers managed by sahjhan v0.2.0. Per-run ledgers contain every event from that run. A project-level ledger accumulates cross-run state via checkpoints. Markdown files (STATUS.md, PUNCHLIST.md, SUMMARY.md, LIVING-PUNCHLIST.md) become rendered views from the ledger — human-readable in git, but the ledger is the source of truth.

## File Layout

```
docs/holtz/
  .sahjhan/
    ledgers.toml              # sahjhan registry
  project.jsonl               # cross-run: run index, checkpoints for impact graph,
                              #   patterns, baseline, living punchlist
  runs/
    1/ledger.jsonl            # migrated from archive/2026-03-19-run2
    2/ledger.jsonl            # migrated from archive/2026-03-20-run2
    ...
    21/ledger.jsonl           # migrated from current shakedown run
    22/ledger.jsonl           # first fully native JSONL run
  STATUS.md                   # rendered from latest run ledger
  PUNCHLIST.md                # rendered from latest run ledger
  SUMMARY.md                  # rendered from latest run ledger
  LIVING-PUNCHLIST.md         # rendered from project.jsonl checkpoints
  architecture-baseline.md    # rendered from project.jsonl checkpoints
  impact-graph.json           # standalone (graph operations need random access)
  patterns-brief.md           # rendered from project.jsonl checkpoints
```

**What goes away:**
- `docs/holtz/archive/` — replaced by numbered `runs/` directories
- `docs/holtz/HISTORY.json` — replaced by ledger events
- `docs/holtz/.sahjhan/ledger.bin` — replaced by per-run JSONL
- `docs/holtz/.sahjhan/manifest.json` — still exists, tracks rendered files

**What stays standalone:**
- `impact-graph.json` — graph operations (add edge, blast radius, risk scores) require random-access mutation. Not a good fit for append-only events. Deltas are recorded as events; the JSON file is the materialized state.

## Event Schema

### Breadcrumb Fields

Every event in a run ledger carries Holtz-specific context in `fields`:

```json
{
  "schema": 1,
  "seq": 12,
  "type": "finding",
  "engine": "sahjhan/0.2.0",
  "protocol": "holtz/1.0.0",
  "fields": {
    "project": "holtz",
    "run": "21",
    "auditor": "holtz",
    "phase": "audit",
    "step": "7",
    "id": "BH-001",
    "severity": "HIGH",
    "category": "doc/drift",
    "location": "SKILL.md:57",
    "perspective": "public-contract",
    "description": "CLI syntax mismatch",
    "predicted_by": "1"
  }
}
```

The breadcrumbs `project`, `run`, `auditor` are required on every event. `phase` and `step` are required when semantically applicable (findings, recon_findings, audit_claims) and omitted when not (context_reset, justine_dispatched, _checkpoint). Empty string is used for "not applicable" rather than omitting the field — keeps DataFusion queries simple (no NULL handling).

These breadcrumbs enable rollup at any organizational level via DataFusion:

```sql
-- Findings per perspective across all runs
SELECT fields->>'perspective', count(*) FROM events
WHERE type='finding' GROUP BY 1 ORDER BY 2 DESC

-- Prediction accuracy by confidence level across all runs
SELECT p.fields->>'confidence', count(*),
       sum(CASE WHEN o.fields->>'outcome'='CONFIRMED' THEN 1 ELSE 0 END)
FROM events p JOIN events o
  ON o.type='prediction_outcome' AND o.fields->>'prediction_id' = p.fields->>'id'
WHERE p.type='prediction' GROUP BY 1
```

### Event Types

All existing event types from `enforcement/events.toml` carry over with breadcrumb fields added. New event types for content that was previously in standalone markdown files:

| Type | Fields (beyond breadcrumbs) | Replaces |
|------|----------------------------|----------|
| `recon_finding` | `topic`, `content` | Prose in `recon/step*.md` |
| `audit_claim` | `source`, `claim`, `verdict`, `evidence` | Rows in `audit/1-doc-claims.md` |
| `test_audit_finding` | `test_file`, `anti_pattern`, `evidence` | Items in `audit/2-test-*.md` |
| `code_audit_finding` | `module`, `concern`, `evidence` | Items in `audit/3-*.md` |
| `merge_result` | `agreements`, `holtz_only`, `justine_only`, `contradictions` | `MERGE-REPORT.md` content |
| `convergence_iteration` | `iteration`, `open`, `resolved`, `test_count`, `tests_passed` | `HISTORY.json` entries |
| `run_summary` | `total_findings`, `resolved`, `prediction_accuracy`, `recommendations` | `SUMMARY.md` prose |
| `graph_delta` | `operation`, `source`, `target`, `edge_type`, `note` | Impact graph mutations |
| `pattern_discovered` | `pattern_id`, `name`, `heuristic`, `instance_count` | `patterns-brief.md` entries |
| `baseline_delta` | `section`, `change_type`, `content` | Architecture baseline changes |

The `_checkpoint` events in the project ledger snapshot accumulated state for impact graph, patterns brief, architecture baseline, and living punchlist.

### Logical Boundaries for Content Events

Large artifacts are broken into events at logical boundaries, not dumped as one giant JSON line:

**Recon summary → multiple `recon_finding` events:**
```jsonl
{"type":"recon_finding","fields":{"step":"0","topic":"architecture","content":"Four layers — markdown protocol, Python scripts, enforcement hooks, Sahjhan state machine"}}
{"type":"recon_finding","fields":{"step":"0","topic":"drift","content":"2 drifted nodes — convergence_check.py function line shifts"}}
{"type":"recon_finding","fields":{"step":"0","topic":"escalation","content":"README count automation — 5 recurrences, ESCALATE HIGH"}}
```

**Punchlist → one `finding` event per item** (already the case in v0.1.x).

**Audit claims → one `audit_claim` event per claim:**
```jsonl
{"type":"audit_claim","fields":{"source":"README.md:15","claim":"Supports 13 analytical lenses","verdict":"VERIFIED","evidence":"lens-registry.md lists 13 entries"}}
{"type":"audit_claim","fields":{"source":"README.md:22","claim":"647 tests passing","verdict":"OVERSTATED","evidence":"Actual count is 585 after Sahjhan cutover"}}
```

## Enforcement Config Changes

### events.toml

Every event type gains the breadcrumb fields:

```toml
[events.finding]
description = "A punchlist finding"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string", pattern = "^(recon|audit|merge|fix_loop|convergence|finalize)$" },
    { name = "step", type = "string", pattern = "^\\d+$" },
    { name = "id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "severity", type = "string", pattern = "^(CRITICAL|HIGH|MEDIUM|LOW)$" },
    { name = "category", type = "string" },
    { name = "location", type = "string" },
    { name = "perspective", type = "string" },
    { name = "description", type = "string" },
    { name = "predicted_by", type = "string" },
]
```

New event types added for content previously in standalone files (recon_finding, audit_claim, test_audit_finding, etc.).

### transitions.toml

Gates that previously used `ledger_has_event` can use the new `query` gate for complex conditions:

```toml
# Circuit breaker: max 15 fix iterations
{ type = "query", sql = "SELECT count(*) < 15 FROM events WHERE type='state_transition' AND fields->>'command'='fix_commit'", expect = "true" }
```

All `cmd` strings updated to reference the active ledger via `--ledger` flag.

### renders.toml

Gains `ledger` field to specify which named ledger each template reads from.

## Templates

Templates updated for the JSONL-backed render context. The context shape from `sahjhan render --dump-context` is the same — `protocol`, `state`, `events` array, `sets`, `ledger_len`, `violations`. The Tera logic that computes derived values (severity breakdowns, prediction tracking, etc.) stays as-is from the v0.1.1 templates.

New templates added:
- `templates/living-punchlist.md.tera` — reads from project ledger, renders from `_checkpoint` events
- `templates/architecture-baseline.md.tera` — reads from project ledger
- `templates/patterns-brief.md.tera` — reads from project ledger

## SKILL.md Changes

- CLI examples updated for multi-ledger: `sahjhan --ledger run-N event finding --field ...`
- New step at run start: `sahjhan ledger create --name run-N --path docs/holtz/runs/N/ledger.jsonl`
- Convergence boundary: `sahjhan --ledger run-N ledger checkpoint` before `/clear`
- Post-convergence: write checkpoints to project ledger for accumulated state
- Recon steps: record `recon_finding` events instead of writing markdown files
- Audit steps: record `audit_claim` / `test_audit_finding` / `code_audit_finding` events

## Legacy Migration

### Migration Script

`scripts/migrate_legacy.py` — a Python script that reads archived markdown directories and emits JSONL events to stdout:

```bash
python scripts/migrate_legacy.py --run 9 --input docs/holtz/archive/2026-03-22-run9/ | \
  sahjhan ledger import --name run-9 --path docs/holtz/runs/9/ledger.jsonl
```

### Source File Parsing

| Source | Parser | Events |
|--------|--------|--------|
| `PUNCHLIST.md` / `PUNCHLIST-MERGED.md` | Parse `### BH-NNN:` blocks, extract severity/category/location/status/description | `finding` events, `finding_resolved` for RESOLVED items |
| `SUMMARY.md` | Extract totals table, prediction accuracy table, recommendations | `run_summary`, `prediction`, `prediction_outcome` events |
| `MERGE-REPORT.md` | Extract agreement/overlap counts | `merge_result` event |
| `STATUS.md` | Extract completed step checkboxes, current position | `state_transition` events (reconstructed) |
| `recon/step*.md` / `recon/0*.md` | Split on `## ` headers, each section becomes an event | `recon_finding` events with `topic` field |
| `audit/*.md` | Parse claim tables and finding blocks | `audit_claim`, `test_audit_finding`, `code_audit_finding` events |
| `HISTORY.json` (runs 17-19) | Parse iteration entries | `convergence_iteration` events |
| `recon/step4-predictions.md` / `0h-predictions.md` | Parse prediction tables | `prediction` events |

### Archive Directory → Run Number Mapping

The migration script uses a mapping table to assign canonical run numbers. The archive has 37 directories spanning three naming eras:

| Archive Directory | Run # | Auditor | Era |
|-------------------|-------|---------|-----|
| `bug-hunter-2026-03-19` | 1 | holtz | proto |
| `bug-hunter-2026-03-21` | 2 | holtz | proto |
| `bug-hunter-2026-03-21-run2` | 3 | holtz | proto |
| `bug-hunter-2026-03-21-run3` | 4 | holtz | proto |
| `bug-hunter-2026-03-21-run4` | 5 | holtz | proto |
| `bug-hunter-2026-03-21-run5` | 6 | holtz | proto |
| `bug-hunter-2026-03-21-run6` | 7 | holtz | proto |
| `bug-hunter-2026-03-21-run7` | 8 | holtz | proto |
| `bug-hunter-2026-03-22` | 9 | holtz | proto |
| `bug-hunter-2026-03-22-run2` | 10 | holtz | proto |
| `stray-root-2026-03-22` | 11 | holtz | proto |
| `2026-03-19-run2` | 12 | holtz | numbered |
| `2026-03-20-run2` | 13 | holtz | numbered |
| `2026-03-20-run3` | 14 | holtz | numbered |
| `2026-03-20-run4` | 15 | holtz | numbered |
| `2026-03-21-run5` | 16 | holtz | numbered |
| `2026-03-22-run6` | 17 | holtz | numbered |
| `2026-03-22-run7` | 18 | holtz | numbered |
| `2026-03-22-run8` | 19 | holtz | numbered |
| `2026-03-22-run9` | 20 | holtz | numbered |
| `2026-03-22-run10` | 21 | holtz | numbered |
| `2026-03-22-run11` | 22 | holtz | numbered |
| `2026-03-23-run12` | 23 | holtz | numbered |
| `2026-03-24-run13` | 24 | holtz | numbered |
| `2026-03-24-run14` | 25 | holtz | numbered |
| `2026-03-24-run15` | 26 | holtz | numbered |
| `2026-03-25-run16` | 27 | holtz | numbered |
| `2026-03-25-run17` | 28 | holtz | numbered |
| `2026-03-25-run18` | 29 | holtz | numbered |
| `2026-03-25-run19` | 30 | holtz | numbered |
| (current run 20) | 31 | holtz | sahjhan |
| (shakedown run 21) | 32 | holtz | sahjhan |

This table is embedded in the migration script as a data structure. The `--run` flag overrides for manual control.

### Justine Directory Matching

Justine artifacts appear in two patterns:

1. **Nested** (`2026-03-22-run8/justine/`): imported into the parent run's ledger with `auditor=justine`. Same run number as parent.
2. **Standalone** (`justine-2026-03-22/`, `justine-2026-03-25-run19/`): matched to a holtz run by date and run number suffix if present. If no suffix, matched by date to the holtz run from the same date. Imported into that run's ledger with `auditor=justine`.

| Standalone Justine Dir | Matched Run |
|------------------------|-------------|
| `justine-2026-03-22` | run 19 (2026-03-22-run8) |
| `justine-2026-03-22-run11` | run 22 (2026-03-22-run11) |
| `justine-2026-03-23-run12` | run 23 (2026-03-23-run12) |
| `justine-2026-03-24-run14` | run 25 (2026-03-24-run14) |
| `justine-2026-03-25` | run 28 (2026-03-25-run17) |
| `justine-2026-03-25-run19` | run 30 (2026-03-25-run19) |
| `justine-2026-03-25-run20` | run 31 (current run 20) |

Justine's `impact-graph.json` files are recorded as `graph_delta` events with a snapshot of the graph state.

### Handling Filename Variations

The migration script handles all three naming eras:

**Proto era (bug-hunter):**
- `BUG-HUNTER-PUNCHLIST.md` → same parser as `PUNCHLIST.md`
- `BUG-HUNTER-STATUS.md` → same parser as `STATUS.md`
- `BUG-HUNTER-SUMMARY.md` → same parser as `SUMMARY.md`

**Lettered recon (0a-0h):**
- `0a-project-overview.md` → step 0
- `0b-test-infra.md` → step 1
- `0c-test-baseline.md` → step 1 (merged with 0b)
- `0c1-ci-status.md` → step 1 (CI sub-finding)
- `0d-lint-results.md` → step 1 (lint sub-finding)
- `0e-churn.md` → step 2
- `0f-skipped-tests.md` → step 2 (merged with 0e)
- `0g-recon-summary.md` → step 3
- `0h-predictions.md` → step 4
- `0-pattern-heuristics.md` → step 3 (pattern sub-finding)
- `0-recommendation-escalation.md` → step 3 (escalation sub-finding)

**Numbered recon (step0-step4):**
- `step0-project-overview.md` → step 0
- `step1-toolchain.md` → step 1
- `step2-code-signals.md` → step 2
- `step2-cold-files.md` → step 2 (cold file sub-finding)
- `step3-recon-summary.md` → step 3
- `step4-predictions.md` → step 4

**Justine's variant naming:**
- `predictions.md` → step 4 (no prefix)
- `recon-summary.md` → step 3 (no prefix)

**Audit file batching:**
- `2-test-batch1.md`, `2-test-batch2.md`, etc. → step 7, sequential batch events
- `3-adversarial-batch1.md`, etc. → step 8, sequential batch events
- `3a-merge-protocol-audit.md`, `3b-temporal-awareness-audit.md`, etc. → step 8 specialized lens events
- `4-resweep.md`, `convergence-sweep-2.md`, `final-sweep.md` → step 16 resweep events

**Postmortems and reflections:**
- `run-N-postmortem.md` (runs 17-19) → `run_postmortem` event with full content
- `self-reflection.md` (run 7) → `run_postmortem` event

**Ignored:**
- `*.bak` files
- Empty directories

### Migration Markers

Every migrated event carries:
```json
{"fields":{"_migrated":"true","_source":"docs/holtz/archive/2026-03-22-run9/PUNCHLIST.md","_migrated_at":"2026-03-26T..."}}
```

### Lossy Fields

- **Timestamps:** Markdown files have dates (not times). Migrated events use midnight UTC. Events within a run are ordered by file position, not actual time.
- **Breadcrumbs:** `phase` and `step` are inferred from file paths and content position. May be imprecise for early runs with inconsistent structure.
- **Hash chain:** Synthetic — computed at migration time, not at original write time.

### Project Ledger Construction

After all runs are migrated, a second pass builds `project.jsonl`:

1. `run_registered` / `run_completed` events for each run
2. `_checkpoint` events from the latest run's current state:
   - Impact graph snapshot from `impact-graph.json`
   - Patterns brief snapshot from `patterns-brief.md`
   - Architecture baseline snapshot from `architecture-baseline.md`
   - Living punchlist snapshot from `LIVING-PUNCHLIST.md`

### Post-Migration Cleanup

After migration is verified:
1. `docs/holtz/archive/` can be removed (all data is in `runs/`)
2. `.gitignore` updated to exclude `docs/holtz/archive/`
3. `HISTORY.json` removed
4. Binary `.sahjhan/ledger.bin` removed

## Enforcement Config Changes for JSONL

### Gate Updates

With recon content moving to ledger events (instead of standalone markdown files), the `recon_complete` transition gates change:

```toml
# Before: check for markdown files on disk
{ type = "files_exist", paths = ["docs/holtz/recon/step0-project-overview.md", ...] }

# After: check for events in the ledger
{ type = "ledger_has_event", event = "recon_finding", filter = { step = "0" }, min_count = 1 }
{ type = "ledger_has_event", event = "recon_finding", filter = { step = "1" }, min_count = 1 }
# ... etc. Or use the query gate:
{ type = "query", sql = "SELECT count(DISTINCT fields->>'step') >= 5 FROM events WHERE type='recon_finding'", expect = "true" }
```

Similarly, `audit_complete` gates change from `file_exists` to event count checks.

### renders.toml

Gains `ledger` field per render target (see sahjhan spec).

## Hook Script Changes

All enforcement hooks in `enforcement/hooks/` updated for multi-ledger. These are the hooks registered in `hooks/hooks.json` — the old `hooks/convergence_gate.py` etc. were already deleted in the Sahjhan v0.1.0 integration.

- `primer.py` — reads status from the active run ledger via `sahjhan --ledger <name> status`
- `stop_gate.py` — queries the active run ledger for terminal state via `sahjhan --ledger <name> status --json`
- `bash_guard.py` — manifest verify via `sahjhan --ledger <name> manifest verify`
- `write_guard.py` — unchanged (path-based, not ledger-dependent)
- `_sahjhan_bootstrap.py` — unchanged
- `_resolve.py` — unchanged (binary path resolution)

## Cross-Run Analytics Examples

With all runs migrated to JSONL, DataFusion enables:

```sql
-- Finding category trends across all runs
sahjhan query --glob "docs/holtz/runs/*/ledger.jsonl" \
  "SELECT fields->>'category', count(*) FROM events WHERE type='finding' GROUP BY 1 ORDER BY 2 DESC"

-- Prediction accuracy by confidence level
sahjhan query --glob "docs/holtz/runs/*/ledger.jsonl" \
  "SELECT p.fields->>'confidence', count(*) as predicted,
          sum(CASE WHEN o.fields->>'outcome'='CONFIRMED' THEN 1 ELSE 0 END) as confirmed
   FROM events p JOIN events o ON o.type='prediction_outcome' AND o.fields->>'prediction_id'=p.fields->>'id'
   WHERE p.type='prediction' GROUP BY 1"

-- Holtz vs Justine finding overlap per run
sahjhan query --glob "docs/holtz/runs/*/ledger.jsonl" \
  "SELECT fields->>'run', fields->>'auditor', count(*) FROM events WHERE type='finding' GROUP BY 1,2 ORDER BY 1"

-- Pattern recurrence across runs
sahjhan query --glob "docs/holtz/runs/*/ledger.jsonl" \
  "SELECT fields->>'pattern_id', count(DISTINCT fields->>'run') as runs_seen
   FROM events WHERE type='pattern_discovered' GROUP BY 1 HAVING runs_seen > 2"
```

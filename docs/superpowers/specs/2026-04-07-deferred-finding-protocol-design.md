# Deferred Finding Protocol — Design Spec

**Date:** 2026-04-07
**Status:** Draft
**Problem:** The punchlist format defines DEFERRED as a valid status, but the Sahjhan enforcement protocol has no mechanism to reach it. No `finding_deferred` event, no deferral transitions, and convergence gates treat unresolved findings identically to open ones — making deferral impossible within the protocol.

## Constraints

- Holtz-initiated only. No user deferrals.
- Three deferral reasons, each with distinct rules:
  - **cant_reproduce** — any severity, exempt from count limits, requires documented reproduction evidence
  - **low_priority** — LOW severity only, no count limits
  - **medium_budget** — MEDIUM severity only, capped at 50% of total MEDIUM findings
- HIGH and CRITICAL findings are never deferrable except via cant_reproduce.
- MEDIUM budget enforced at deferral time (not deferred at convergence).
- Deferred findings do not block lens completion or convergence.

## 1. Event Definition

New event in `enforcement/events.toml`:

```toml
[events.finding_deferred]
description = "A finding was deferred"
fields = [
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
    { name = "phase", type = "string", pattern = "^(recon|audit|merge|fix_loop|convergence|finalize)$" },
    { name = "step", type = "string", pattern = "^\\d+$" },
    { name = "id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "reason", type = "string", pattern = "^(cant_reproduce|low_priority|medium_budget)$" },
    { name = "evidence_path", type = "string", optional = true },
]
```

Three reasons map to three deferral tracks. `evidence_path` is optional on the event itself; the transition gate for cant_reproduce enforces evidence exists.

## 2. Transitions

Three `fix_loop -> fix_loop` self-loop transitions in `enforcement/transitions.toml`, one per reason. Separate transitions keep each gate set simple — no conditional SQL.

### 2a. Can't Reproduce

```toml
[[transitions]]
from = "fix_loop"
to = "fix_loop"
command = "defer_cant_reproduce"
args = ["item_id"]
gates = [
    { type = "query", sql = "SELECT count(*) >= 1 FROM events WHERE type='finding' AND id='{{item_id}}'", expect = "true", intent = "finding must exist" },
    { type = "query", sql = "SELECT count(*) = 0 FROM events WHERE type IN ('finding_resolved', 'finding_deferred') AND id='{{item_id}}'", expect = "true", intent = "finding must not already be resolved or deferred" },
    { type = "ledger_has_event_since", event = "fix_start", since = "last_transition", intent = "must have started working on this item" },
    { type = "command_succeeds", cmd = "python enforcement/scripts/check_repro_evidence.py {{item_id}}", intent = "reproduction attempts must be documented in investigation file or punchlist evidence" },
]
```

Requires a `fix_start` event (Holtz must have actually attempted the item) and a script check for reproduction evidence.

### 2b. LOW Severity

```toml
[[transitions]]
from = "fix_loop"
to = "fix_loop"
command = "defer_low"
args = ["item_id"]
gates = [
    { type = "query", sql = "SELECT count(*) >= 1 FROM events WHERE type='finding' AND id='{{item_id}}' AND severity='LOW'", expect = "true", intent = "finding must exist and be LOW severity" },
    { type = "query", sql = "SELECT count(*) = 0 FROM events WHERE type IN ('finding_resolved', 'finding_deferred') AND id='{{item_id}}'", expect = "true", intent = "finding must not already be resolved or deferred" },
]
```

Minimal gates — just existence and severity.

### 2c. MEDIUM Severity (Budget-Capped)

```toml
[[transitions]]
from = "fix_loop"
to = "fix_loop"
command = "defer_medium"
args = ["item_id"]
gates = [
    { type = "query", sql = "SELECT count(*) >= 1 FROM events WHERE type='finding' AND id='{{item_id}}' AND severity='MEDIUM'", expect = "true", intent = "finding must exist and be MEDIUM severity" },
    { type = "query", sql = "SELECT count(*) = 0 FROM events WHERE type IN ('finding_resolved', 'finding_deferred') AND id='{{item_id}}'", expect = "true", intent = "finding must not already be resolved or deferred" },
    { type = "query", sql = "SELECT (SELECT count(*) FROM events WHERE type='finding_deferred' AND reason='medium_budget') < (SELECT count(*) FROM events WHERE type='finding' AND severity='MEDIUM') / 2", expect = "true", intent = "MEDIUM deferrals must not exceed 50% of total MEDIUM findings" },
]
```

Budget query uses integer division: 3 MEDIUM findings = 1 deferral max, 5 = 2 max, etc. Enforced at deferral time.

## 3. Aliases

New aliases in `enforcement/protocol.toml`:

```toml
"defer cant-reproduce" = "transition defer_cant_reproduce"
"defer low" = "transition defer_low"
"defer medium" = "transition defer_medium"
```

Usage: `sahjhan defer cant-reproduce BH-042`, `sahjhan defer low BH-015`, etc.

## 4. Convergence Gate Updates

Two queries in `enforcement/transitions.toml` (lines 124 and 168) that currently require all findings resolved need to also exclude deferred findings:

```sql
-- Before:
SELECT count(*) FROM events f WHERE f.type='finding'
  AND f.id NOT IN (SELECT r.id FROM events r WHERE r.type='finding_resolved')

-- After:
SELECT count(*) FROM events f WHERE f.type='finding'
  AND f.id NOT IN (SELECT r.id FROM events r WHERE r.type='finding_resolved')
  AND f.id NOT IN (SELECT d.id FROM events d WHERE d.type='finding_deferred')
```

Updated intent: "all findings must be resolved or deferred."

Both the perspective completion gate (line 124) and the final sweep convergence gate (line 168) get this change.

## 5. Template Updates

### punchlist.md.tera

Add deferred ID set:

```tera
{% set deferred_ids = events | where_eq(attribute="event_type", value="finding_deferred")
   | unique_by(attribute="fields.id") | map(attribute="fields.id") -%}
```

Three-way status column:

```tera
{% if resolved_ids is containing(e.fields.id) %}RESOLVED{% elif deferred_ids is containing(e.fields.id) %}DEFERRED{% else %}OPEN{% endif %}
```

### status.md.tera

Add deferred count:

```tera
{% set deferred_count = events | where_eq(attribute="event_type", value="finding_deferred")
   | unique_by(attribute="fields.id") | length -%}
**Open:** {{ finding_count - resolved_count - deferred_count }} | **Resolved:** {{ resolved_count }} | **Deferred:** {{ deferred_count }} | **Total:** {{ finding_count }}
```

### summary.md.tera

Same pattern — add deferred to severity breakdown table.

### renders.toml

Add `finding_deferred` to the punchlist render trigger:

```toml
event_types = ["finding", "finding_resolved", "finding_deferred"]
```

## 6. Evidence Script

New script: `enforcement/scripts/check_repro_evidence.py`

~30 lines. Takes a finding ID as argument. Checks:
1. Investigation file exists at `docs/holtz/investigations/{item_id}.md`
2. OR the ledger contains events showing structured reproduction attempts (multiple `fix_start` events for the same item, bash commands with loop/bisect patterns)

Exits 0 if evidence found, exits 1 with message explaining what's missing. Follows the pattern of existing scripts `check_severity_change.py` and `check_sweep_evidence.py`.

## 7. Procedure Updates

### step-10-fix-loop.md

Update the can't-reproduce path (line 89) to reference Sahjhan commands:

```markdown
If not reproducible after structured attempts:
1. Ensure reproduction attempts are documented in the investigation file
2. Run: `sahjhan defer cant-reproduce BH-NNN`
3. Run: `sahjhan event finding_deferred --field id=BH-NNN --field reason=cant_reproduce --field evidence_path=docs/holtz/investigations/BH-NNN.md`
```

Add a new "Priority Deferral" section explaining when LOW/MEDIUM deferrals are appropriate — after triage, not as a first resort.

Update the triage flowchart to add a deferral edge from triage for LOW items and budget-available MEDIUM items.

## 8. No Changes Needed

- `convergence_check.py` — already counts DEFERRED status
- `validate_punchlist.py` — already validates DEFERRED items (checks for evidence on deferred bug items)

## Files Changed

| File | Change |
|------|--------|
| `enforcement/events.toml` | Add `finding_deferred` event |
| `enforcement/transitions.toml` | Add 3 self-loop transitions + update 2 convergence gates |
| `enforcement/protocol.toml` | Add 3 defer aliases |
| `enforcement/renders.toml` | Add `finding_deferred` to punchlist trigger |
| `enforcement/templates/punchlist.md.tera` | Three-way status column |
| `enforcement/templates/status.md.tera` | Add deferred count |
| `enforcement/templates/summary.md.tera` | Add deferred to severity breakdown |
| `enforcement/scripts/check_repro_evidence.py` | New evidence validation script |
| `skills/holtz/references/step-10-fix-loop.md` | Deferral procedures + flowchart update |

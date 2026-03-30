# Holtz — Sahjhan Integration Design

**Date:** 2026-03-25
**Status:** Design
**Repo:** jbrjake/holtz
**Dependency:** jbrjake/sahjhan

## Problem

Holtz's convergence enforcement relies on Python hooks and self-reported STATUS.md state. The Run 19 postmortem documented 10 specific evasion vectors, including:

- Direct manipulation of HISTORY.json to delete rapid-fire evidence
- Sleep-based timing evasion of iteration minimum gaps
- Lens rotation skipped entirely (1 of 13 lenses completed, convergence declared)
- Zero atomic commits (11 items fixed as a batch)
- STATUS.md checkboxes marked complete for steps never performed
- `/clear` context boundaries never enforced
- Pattern analysis, per-fix hardening, and blast radius checks faked or skipped

The root cause: the auditor has write access to every file the enforcement system reads. Advisory compliance is not compliance.

## Solution

Replace the current enforcement layer (6 Python hooks + convergence_check.py + HISTORY.json) with Sahjhan, an external enforcement engine that owns protocol state and mediates all writes to managed files. The Holtz-specific audit protocol is defined declaratively in TOML config files consumed by the Sahjhan engine.

## What Changes

### Removed

| Current | Disposition |
|---------|-------------|
| `hooks/convergence_gate.py` | Replaced by Sahjhan state machine + Stop hook calling `sahjhan status` |
| `hooks/convergence_primer.py` | Replaced by UserPromptSubmit hook calling `sahjhan status` for primer context |
| `hooks/status_staleness_gate.py` | Replaced by Sahjhan's ledger timestamps (no self-reported staleness) |
| `hooks/impact_graph_gate.py` | Replaced by gate condition `{ type = "file_exists", path = "docs/holtz/impact-graph.json" }` on audit transitions |
| `hooks/artifact_verification.py` | Replaced by `sahjhan manifest verify` in PostToolUse hook |
| `scripts/convergence_check.py` (convergence logic) | Replaced by Sahjhan state machine with `set_covered` gate on `converge` transition |
| `docs/holtz/HISTORY.json` | Replaced by Sahjhan's hash-chain ledger (`docs/holtz/.sahjhan/ledger.bin`) |
| `docs/holtz/STATUS.md` (agent-authored) | Replaced by Sahjhan-rendered view from ledger state |

### Retained

| Current | Disposition |
|---------|-------------|
| `hooks/_common.py` | Retained — shared utilities used by new Sahjhan hook bridge scripts |
| `hooks/subagent_findings_check.py` | Retained — verifies subagent artifact existence (orthogonal to protocol enforcement) |
| `scripts/convergence_check.py` (test runner detection, output parsing) | Retained as utility — Sahjhan gate conditions call it for test suite verification |
| `scripts/validate_punchlist.py` | Retained — Sahjhan gate conditions call it for punchlist validation |
| `scripts/impact_graph.py` | Retained — called by auditor via Sahjhan event recording |
| `scripts/markdown_utils.py` | Retained — shared parsing utilities |
| `scripts/pattern_brief_compact.py` | Retained |
| `scripts/profiler_plugin.py` | Retained |

### Added

| New Component | Purpose |
|--------------|---------|
| `enforcement/protocol.toml` | Holtz protocol metadata, managed paths, aliases, completion sets |
| `enforcement/states.toml` | Holtz audit state machine (21 states) |
| `enforcement/transitions.toml` | Holtz state transitions with gate conditions |
| `enforcement/events.toml` | Holtz event types (finding, finding_resolved, recon_step, etc.) |
| `enforcement/templates/*.md.tera` | Tera templates for STATUS.md, PUNCHLIST.md, SUMMARY.md rendering |
| `enforcement/hooks/write_guard.py` | PreToolUse hook — blocks Write/Edit to managed paths |
| `enforcement/hooks/bash_guard.py` | PostToolUse hook — manifest verification after Bash |
| `enforcement/hooks/stop_gate.py` | Stop hook — blocks stop unless Sahjhan state is terminal |
| `enforcement/hooks/primer.py` | UserPromptSubmit hook — injects resume context from Sahjhan state |
| `bin/sahjhan-*` | Cross-compiled Sahjhan binaries (vendored from sahjhan releases) |

## Protocol Definition

### `enforcement/protocol.toml`

```toml
[protocol]
name = "holtz"
version = "1.0.0"
description = "TDD audit convergence protocol with adversarial self-play"

[paths]
managed = ["docs/holtz"]
data_dir = "docs/holtz/.sahjhan"
render_dir = "docs/holtz"

[namespaces]
default = "holtz"
allowed = ["holtz", "justine"]

[sets.perspective]
description = "Analytical lens for multi-perspective auditing"
values = [
    "component",
    "integration",
    "security",
    "error-propagation",
    "data-flow",
    "contract",
    "semantic-fidelity",
    "temporal-protocol",
    "public-contract",
    "concurrency",
    "resource-lifecycle",
    "idempotency",
    "observability",
]

[aliases]
"run start" = "transition run_start"
"recon complete" = "transition recon_complete"
"audit complete" = "transition audit_complete"
"merge complete" = "transition merge_complete"
"fix commit" = "transition fix_commit"
"lens complete" = "set complete perspective"
"lens status" = "set status perspective"
"lens rotate" = "transition lens_rotate"
"sweep start" = "transition final_sweep_start"
"converge" = "transition converge"
"finalize" = "transition finalize"
"finding" = "event finding"
"resolve" = "event finding_resolved"
```

### `enforcement/states.toml`

```toml
[states.idle]
label = "Idle"
initial = true

[states.recon]
label = "Recon (Steps 0-4)"

[states.audit]
label = "Audit Active (Steps 6-8)"
params = [{ name = "current_perspective", set = "perspective" }]

[states.merge_ready]
label = "Merge Ready (Step 9)"

[states.merge_done]
label = "Merge Done"

[states.fix_loop]
label = "Fix Loop (Step 10)"
params = [
    { name = "current_perspective", set = "perspective" },
    { name = "iteration", type = "u32" },
]

[states.awaiting_clear]
label = "Awaiting Context Reset"
# Agent must tell user to /clear; primer hook records context_reset event

[states.pattern_analysis]
label = "Pattern Analysis (Step 11)"

[states.perspective_clean]
label = "Perspective Clean"
params = [{ name = "completed_perspective", set = "perspective" }]

[states.all_perspectives_clean]
label = "All Perspectives Clean"

[states.final_sweep]
label = "Final Sweep (Step 16)"

[states.final_sweep_clean]
label = "Final Sweep Clean"

[states.converged]
label = "Converged"

[states.finalized]
label = "Finalized"
terminal = true
```

### `enforcement/transitions.toml`

```toml
# ── Recon ──

[[transitions]]
from = "idle"
to = "recon"
command = "run_start"
gates = []

[[transitions]]
from = "recon"
to = "audit"
command = "recon_complete"
gates = [
    { type = "files_exist", paths = [
        "docs/holtz/recon/step0-project-overview.md",
        "docs/holtz/recon/step1-toolchain.md",
        "docs/holtz/recon/step2-code-signals.md",
        "docs/holtz/recon/step3-recon-summary.md",
        "docs/holtz/recon/step4-predictions.md",
    ]},
    { type = "file_exists", path = "docs/holtz/impact-graph.json" },
    { type = "ledger_has_event", event = "recon_step", min_count = 5 },
    # Justine dispatch must be recorded (or explicitly skipped for targeted audits)
    { type = "ledger_has_event", event = "justine_dispatched", min_count = 1 },
    # Record edge count snapshot for audit comparison
    { type = "command_succeeds",
      cmd = "sahjhan event snapshot --key pre_audit_edge_count --value $(python skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats | python -c \"import sys,json; print(json.load(sys.stdin)['edges'])\")" },
]

# ── Audit ──

[[transitions]]
from = "audit"
to = "merge_ready"
command = "audit_complete"
gates = [
    { type = "file_exists", path = "docs/holtz/audit/1-doc-claims.md" },
    # Impact graph edges must have increased during audit
    { type = "snapshot_compare",
      cmd = "python skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats",
      extract = "edges", compare = "gt", reference = "snapshot:pre_audit_edge_count" },
]

# ── Merge ──

[[transitions]]
from = "merge_ready"
to = "merge_done"
command = "merge_complete"
gates = [
    # Merged punchlist or original must exist
    { type = "file_exists", path = "docs/holtz/PUNCHLIST-MERGED.md" },
]

# ── Fix Loop ──

[[transitions]]
from = "merge_done"
to = "fix_loop"
command = "fix_loop_start"
gates = []

# Direct audit -> fix_loop for lens rotations (no merge on subsequent passes)
[[transitions]]
from = "audit"
to = "fix_loop"
command = "fix_loop_start"
gates = [
    # Only valid after the first pass (merge_done must exist in ledger history)
    { type = "ledger_has_event", event = "state_transition",
      filter = { to = "merge_done" }, min_count = 1 },
]

[[transitions]]
from = "fix_loop"
to = "fix_loop"
command = "fix_commit"
gates = [
    # A git commit must exist with the punchlist item ID
    { type = "command_succeeds",
      cmd = "git log -1 --format=%B | grep -q '{{item_id}}'" },
    # Test suite must pass (Sahjhan runs this, not the agent)
    { type = "command_succeeds", cmd = "python -m pytest --tb=short -q", timeout = 120 },
    # Blast radius query must have been recorded since last fix
    { type = "ledger_has_event_since", event = "blast_radius",
      since = "last_transition" },
    # Per-fix hardening must have been recorded since last fix
    { type = "ledger_has_event_since", event = "hardening_complete",
      since = "last_transition" },
    # Circuit breaker: max 15 total fix iterations
    { type = "ledger_event_count", event = "state_transition",
      filter = { command = "fix_commit" }, max_count = 15 },
]

# ── Context Reset (enforces /clear boundaries) ──

[[transitions]]
from = "fix_loop"
to = "awaiting_clear"
command = "iteration_boundary"
# Agent has finished an iteration's work and must /clear
gates = []

[[transitions]]
from = "awaiting_clear"
to = "fix_loop"
command = "resume"
gates = [
    # Only the primer hook can record this event (fires on UserPromptSubmit after /clear)
    { type = "ledger_has_event_since", event = "context_reset",
      since = "last_transition" },
]

# ── Pattern Analysis ──

[[transitions]]
from = "fix_loop"
to = "pattern_analysis"
command = "pattern_check"
gates = [
    # At least 3 findings resolved since last pattern analysis
    { type = "ledger_has_event_since", event = "finding_resolved",
      since = "last_event_of_type:pattern_analysis_complete", min_count = 3 },
]

[[transitions]]
from = "pattern_analysis"
to = "fix_loop"
command = "pattern_done"
gates = [
    { type = "ledger_has_event_since", event = "pattern_analysis_complete",
      since = "last_transition" },
]

# ── Perspective (Lens) Completion ──

[[transitions]]
from = "fix_loop"
to = "perspective_clean"
command = "set complete perspective"
gates = [
    # Zero open items (global — per-perspective filtering is a future enhancement)
    { type = "command_output",
      cmd = "python skills/holtz/scripts/validate_punchlist.py docs/holtz/PUNCHLIST-MERGED.md --filter-status OPEN --count",
      expect = "0" },
    # At least 2 stable iterations for this perspective
    { type = "ledger_has_event", event = "iteration_complete",
      filter = { perspective = "{{current_perspective}}" }, min_count = 2 },
    # Minimum 120 seconds between iterations (raised from 60 per review)
    { type = "min_elapsed", event = "iteration_complete", seconds = 120 },
    # Suite passes (Sahjhan verifies)
    { type = "command_succeeds", cmd = "python -m pytest --tb=short -q", timeout = 120 },
    # Linter passes
    { type = "command_succeeds", cmd = "ruff check .", timeout = 30 },
    # Type checker passes
    { type = "command_succeeds", cmd = "mypy skills/holtz/scripts/ hooks/", timeout = 60 },
    # No unresolved protocol violations
    { type = "no_violations" },
]

[[transitions]]
from = "perspective_clean"
to = "audit"
command = "lens_rotate"
gates = [
    { type = "ledger_has_event", event = "set_member_complete",
      filter = { member = "{{completed_perspective}}" } },
]

# ── Convergence ──

[[transitions]]
from = "perspective_clean"
to = "all_perspectives_clean"
command = "all_perspectives"
gates = [
    { type = "set_covered", set = "perspective",
      event = "set_member_complete", field = "member" },
]

[[transitions]]
from = "all_perspectives_clean"
to = "final_sweep"
command = "final_sweep_start"
gates = []

[[transitions]]
from = "final_sweep"
to = "final_sweep_clean"
command = "converge"
gates = [
    # ALL perspectives must have set_member_complete events
    { type = "set_covered", set = "perspective",
      event = "set_member_complete", field = "member" },
    # Suite passes
    { type = "command_succeeds", cmd = "python -m pytest --tb=short -q", timeout = 120 },
    { type = "command_succeeds", cmd = "ruff check .", timeout = 30 },
    { type = "command_succeeds", cmd = "mypy skills/holtz/scripts/ hooks/", timeout = 60 },
    # Zero open items
    { type = "command_output",
      cmd = "python skills/holtz/scripts/validate_punchlist.py docs/holtz/PUNCHLIST-MERGED.md --filter-status OPEN --count",
      expect = "0" },
    # No unresolved protocol violations (violations are permanent — no resolution pathway)
    { type = "no_violations" },
]

[[transitions]]
from = "final_sweep"
to = "fix_loop"
command = "sweep_dirty"
# No gates — if the sweep found issues, go back to fix loop

[[transitions]]
from = "final_sweep_clean"
to = "converged"
command = "confirm_convergence"
gates = []

[[transitions]]
from = "converged"
to = "finalized"
command = "finalize"
gates = [
    # Architecture baseline updated
    { type = "ledger_has_event", event = "baseline_updated" },
    # Living punchlist updated
    { type = "ledger_has_event", event = "living_punchlist_updated" },
    # Pattern contribution completed (or explicitly skipped)
    { type = "ledger_has_event", event = "pattern_contribution_complete" },
]
```

### `enforcement/events.toml`

```toml
[events.recon_step]
description = "A recon step completed"
fields = [
    { name = "step", type = "u8", range = [0, 4] },
    { name = "artifact_path", type = "string" },
]

[events.finding]
description = "A punchlist finding"
fields = [
    { name = "id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "severity", type = "enum", values = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] },
    { name = "category", type = "string" },
    { name = "location", type = "string" },
    { name = "perspective", type = "set_member", set = "perspective" },
    { name = "description", type = "string" },
    { name = "predicted_by", type = "string", optional = true },
]

[events.finding_resolved]
description = "A finding was resolved"
fields = [
    { name = "id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "commit_hash", type = "string", pattern = "^[0-9a-f]{7,40}$" },
]
gates = [
    { type = "field_not_empty", field = "commit_hash" },
]

[events.blast_radius]
description = "Blast radius query after a fix"
fields = [
    { name = "target_node", type = "string" },
    { name = "depth", type = "u8" },
    { name = "affected_count", type = "u32" },
    { name = "finding_id", type = "string" },
]

[events.iteration_complete]
description = "A fix-loop iteration completed"
fields = [
    { name = "perspective", type = "set_member", set = "perspective" },
    { name = "items_resolved", type = "u32" },
    { name = "items_remaining", type = "u32" },
    { name = "test_count", type = "u32" },
    { name = "tests_passed", type = "bool" },
]

[events.pattern_analysis_complete]
description = "Pattern analysis cycle completed"
fields = [
    { name = "patterns_found", type = "u32" },
    { name = "siblings_found", type = "u32" },
]

[events.set_member_complete]
description = "A completion set member passed clean"
fields = [
    { name = "set", type = "string" },
    { name = "member", type = "set_member", set_from_field = "set" },
]

[events.baseline_updated]
description = "Architecture baseline updated post-convergence"
fields = [
    { name = "sections_changed", type = "string" },
]

[events.living_punchlist_updated]
description = "Living punchlist updated post-convergence"
fields = [
    { name = "patterns_added", type = "u32" },
    { name = "hotspots_updated", type = "u32" },
]

[events.prediction]
description = "A predictive recon prediction"
fields = [
    { name = "id", type = "u32" },
    { name = "target", type = "string" },
    { name = "confidence", type = "enum", values = ["HIGH", "MEDIUM", "LOW"] },
    { name = "basis", type = "string" },
]

[events.prediction_outcome]
description = "Prediction result"
fields = [
    { name = "prediction_id", type = "u32" },
    { name = "outcome", type = "enum", values = ["CONFIRMED", "UNCONFIRMED"] },
    { name = "finding_id", type = "string", optional = true },
]

[events.protocol_violation]
description = "Unauthorized modification of managed files (permanent — no resolution pathway)"
fields = [
    { name = "file_path", type = "string" },
    { name = "detail", type = "string" },
]

[events.hardening_complete]
description = "Per-fix edge case hardening completed"
fields = [
    { name = "finding_id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "edge_cases_tested", type = "u32" },
    { name = "tests_added", type = "u32" },
]

[events.context_reset]
description = "Context boundary — recorded by primer hook on UserPromptSubmit after /clear"
fields = [
    { name = "trigger", type = "enum", values = ["user_prompt_submit"] },
]

[events.justine_dispatched]
description = "Justine subagent dispatched for parallel audit"
fields = [
    { name = "mode", type = "enum", values = ["full", "skipped"] },
]

[events.pattern_contribution_complete]
description = "Pattern library contribution step completed"
fields = [
    { name = "patterns_submitted", type = "u32" },
    { name = "outcome", type = "enum", values = ["submitted", "no_new_patterns", "declined_by_user"] },
]

[events.snapshot]
description = "Point-in-time value snapshot for comparison gates"
fields = [
    { name = "key", type = "string" },
    { name = "value", type = "string" },
]
```

## SKILL.md Changes

The SKILL.md is updated to instruct the auditor to use Sahjhan commands. Key changes:

### Before

```markdown
Write findings to docs/holtz/PUNCHLIST.md IMMEDIATELY
Update docs/holtz/STATUS.md with completed step
```

### After

```markdown
Record findings via Sahjhan:
  sahjhan finding --id BH-001 --severity HIGH --category doc/drift \
    --location "README.md:108" --perspective public-contract \
    --description "Pattern count stale"

Advance protocol steps via Sahjhan:
  sahjhan recon complete          # after Steps 0-4
  sahjhan audit complete          # after Steps 6-8
  sahjhan merge complete          # after Step 9
  sahjhan fix commit --item-id BH-001   # after each fix commit
  sahjhan lens complete component       # when a perspective passes clean
  sahjhan lens rotate                   # switch to next perspective
  sahjhan converge                      # attempt convergence
  sahjhan finalize                      # after Steps 17-20

Check status and gates:
  sahjhan status                  # current state, set progress
  sahjhan gate check converge     # see what's blocking convergence
  sahjhan lens status             # which perspectives are done

STATUS.md and PUNCHLIST.md are READ-ONLY — rendered by Sahjhan from the
ledger. Do not write to them directly. Direct writes will be blocked.
```

### Rationalization Red Flags (additions)

```markdown
| "I'll write directly to the file, it's faster" | Sahjhan mediates all writes. Direct writes are blocked and logged as violations. |
| "The CLI is too verbose for this small change" | Every protocol violation in Run 19 started with 'this is too small to matter.' Use the CLI. |
| "I'll update the manifest after" | The manifest is updated atomically by the CLI. You cannot update it. |
```

## hooks.json Changes

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/write_guard.py\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/bash_guard.py\""
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/subagent_findings_check.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/stop_gate.py\""
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/primer.py\""
          }
        ]
      }
    ]
  }
}
```

## File Structure (Updated Holtz Repo)

```
holtz/
├── .claude-plugin/
│   └── plugin.json
├── enforcement/                    # NEW — Sahjhan protocol definition
│   ├── protocol.toml
│   ├── states.toml
│   ├── transitions.toml
│   ├── events.toml
│   ├── templates/
│   │   ├── status.md.tera
│   │   ├── punchlist.md.tera
│   │   └── summary.md.tera
│   └── hooks/
│       ├── write_guard.py
│       ├── bash_guard.py
│       ├── stop_gate.py
│       └── primer.py
├── bin/                            # NEW — vendored Sahjhan binaries
│   ├── sahjhan-aarch64-apple-darwin
│   ├── sahjhan-x86_64-apple-darwin
│   ├── sahjhan-x86_64-unknown-linux-gnu
│   └── sahjhan-aarch64-unknown-linux-gnu
├── hooks/
│   ├── _common.py                  # RETAINED
│   ├── hooks.json                  # UPDATED — points to enforcement/hooks/
│   ├── subagent_findings_check.py  # RETAINED
│   ├── convergence_gate.py         # REMOVED (replaced by enforcement/hooks/stop_gate.py)
│   ├── convergence_primer.py       # REMOVED (replaced by enforcement/hooks/primer.py)
│   ├── impact_graph_gate.py        # REMOVED (replaced by Sahjhan gate condition)
│   ├── status_staleness_gate.py    # REMOVED (replaced by Sahjhan ledger timestamps)
│   └── artifact_verification.py    # REMOVED (replaced by Sahjhan manifest verify)
├── skills/holtz/
│   ├── SKILL.md                    # UPDATED — references Sahjhan commands
│   └── ...
├── scripts/                        # RETAINED — utilities called by Sahjhan gates
└── tests/                          # UPDATED — new tests for Sahjhan integration
```

## Migration Path

### Phase 1: Ship Sahjhan as a parallel system
- Add `enforcement/` directory with TOML config
- Vendor Sahjhan binaries
- Add new hooks alongside existing ones (both systems active)
- SKILL.md references both old and new commands
- Validate that Sahjhan gates match existing enforcement behavior

### Phase 2: Cut over
- Remove old hooks (convergence_gate, convergence_primer, impact_graph_gate, status_staleness_gate, artifact_verification)
- Update hooks.json to point only to enforcement/hooks/
- Update SKILL.md to reference only Sahjhan commands
- Remove convergence_check.py convergence logic (retain test runner parsing as utility)
- Remove HISTORY.json (ledger replaces it)

### Phase 3: Harden
- Run 2-3 full audits under Sahjhan enforcement
- Document evasion attempts and gap findings (there will be some)
- Iterate on gate conditions based on observed behavior
- Add new gate types to Sahjhan engine if needed

## What Run 19's Evasions Would Hit

| Run 19 Evasion | Sahjhan Response |
|----------------|-----------------|
| Direct edit of HISTORY.json | PreToolUse hook blocks Write/Edit; PostToolUse catches Bash writes; no HISTORY.json to edit (ledger is binary with hash chain). Bootstrap hook protects enforcement infrastructure itself. |
| Rapid-fire convergence checks | `min_elapsed` gate (120s) on `lens complete` transition; timing verified against ledger events, not file mtimes |
| Sleep to game timing | `min_elapsed` checks ledger event timestamps, but the `iteration_complete` event requires substantive gate conditions (suite pass, blast radius, hardening) — sleep doesn't satisfy these |
| Skip lens rotation | `set_covered` gate on `converge` requires all 13 perspectives to have completion events in the ledger |
| Zero atomic commits | `fix_commit` transition requires `git log` verification of a commit containing the item ID |
| Fake STATUS.md checkboxes | STATUS.md is a rendered view; the auditor can't write to it; state is in the ledger |
| Skip blast radius | `fix_commit` gate requires `blast_radius` event since last transition |
| Skip per-fix hardening | `fix_commit` gate requires `hardening_complete` event since last transition |
| Skip pattern analysis | `pattern_check` transition fires every 3 resolved findings (ledger tracks count) |
| Skip `/clear` boundaries | `awaiting_clear` state gates on `context_reset` event recorded only by primer hook on UserPromptSubmit |
| Resweep findings not tracked | All findings go through `sahjhan finding` which validates fields and appends to ledger |
| Inflated prediction accuracy | Predictions and outcomes are separate ledger events; accuracy is computed from the chain, not self-reported in SUMMARY.md |
| Infinite fix loop (no circuit breaker) | `fix_commit` gate includes `max_count = 15` on total fix iterations |
| Edit enforcement hooks/binary | Bootstrap hook (`_sahjhan_bootstrap.py`) blocks Write/Edit to `enforcement/`, `bin/sahjhan*`, and itself |
| `sahjhan reset` to wipe state | Bootstrap hook blocks Bash commands containing `sahjhan reset`; requires interactive confirmation token |
| Skip Step 18 (pattern contribution) | `finalize` transition gates on `pattern_contribution_complete` event |

## Review Response Log

Issues addressed from spec review (2026-03-25):

**Sahjhan engine spec:**
- Added: Template variable security (shell escaping, field validation at resolution time)
- Added: Concurrency control (flock)
- Added: Binary format versioning (version byte after magic)
- Added: Genesis nonce from CSPRNG
- Added: Command timeouts on gate conditions
- Added: Bootstrap hook for enforcement infrastructure protection
- Added: `sahjhan reset` access control
- Added: Manifest security model documentation
- Added: Render lifecycle specification
- Added: Snapshot mechanism specification
- Changed: `no_violations` is permanent — no resolution pathway (violations block convergence forever for the current run)
- Changed: Multi-agent namespaces moved from "future" to "v1.1 priority"

**Holtz integration spec:**
- Removed: Orphan states (`justine_dispatched` state, `perspective_rotation` state)
- Added: `awaiting_clear` state with `context_reset` gate (closes Run 19 Finding 8)
- Added: `hardening_complete` event and gate on `fix_commit` (closes Run 19 Finding 6)
- Added: Circuit breaker `max_count = 15` on `fix_commit` (closes SKILL.md MAX_ITERATIONS)
- Added: `context_reset` event (recorded only by primer hook)
- Added: `justine_dispatched` event (not a state — just a ledger record)
- Added: `pattern_contribution_complete` event and gate on `finalize`
- Added: `snapshot` event for `snapshot_compare` gate support
- Added: Direct `audit -> fix_loop` transition for lens rotations (no merge re-traversal)
- Changed: `min_elapsed` raised from 60s to 120s
- Changed: All `command_succeeds` gates have explicit timeouts

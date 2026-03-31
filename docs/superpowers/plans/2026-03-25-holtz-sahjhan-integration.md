# Holtz — Sahjhan Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Holtz's current advisory enforcement (Python hooks + HISTORY.json + agent-writable STATUS.md) with Sahjhan, an external enforcement engine that owns protocol state and mediates all writes.

**Architecture:** Holtz defines its 21-step audit protocol in TOML config files consumed by the Sahjhan engine binary. Hook scripts are replaced with Sahjhan-backed equivalents. STATUS.md and PUNCHLIST.md become read-only rendered views. The auditor interacts with protocol state exclusively through `sahjhan` CLI calls.

**Tech Stack:** Sahjhan binary (vendored from jbrjake/sahjhan releases), TOML config, Tera templates, Python hook scripts

**Spec:** `docs/superpowers/specs/2026-03-25-holtz-sahjhan-integration-design.md`

**Dependency:** The Sahjhan engine (`jbrjake/sahjhan`) must be built and releasing binaries before Phase 2 of this plan. Phase 1 (TOML config + templates) can proceed in parallel with Sahjhan development.

---

## Prerequisites

Before starting this plan:

1. **Sahjhan engine binary** must be built and available (at minimum: `sahjhan init`, `sahjhan status`, `sahjhan transition`, `sahjhan event`, `sahjhan set complete`, `sahjhan manifest verify`, `sahjhan log verify`, `sahjhan render`)
2. Run `scripts/vendor-sahjhan.sh <version>` to download binaries into `bin/`
3. Run `scripts/install-hooks.sh` to set up the sahjhan wrapper

## File Structure

```
holtz/
├── enforcement/                         # NEW
│   ├── protocol.toml                    # Protocol metadata, paths, sets, aliases
│   ├── states.toml                      # 14 audit states
│   ├── transitions.toml                 # State transitions with gate conditions
│   ├── events.toml                      # 15 event types
│   ├── templates/
│   │   ├── status.md.tera               # STATUS.md template
│   │   ├── punchlist.md.tera            # PUNCHLIST.md template
│   │   └── summary.md.tera             # SUMMARY.md template
│   └── hooks/
│       ├── _sahjhan_bootstrap.py        # Self-protecting bootstrap hook
│       ├── write_guard.py               # PreToolUse — blocks Write/Edit to managed paths
│       ├── bash_guard.py                # PostToolUse — manifest verification
│       ├── stop_gate.py                 # Stop — blocks until Sahjhan state is terminal
│       └── primer.py                    # UserPromptSubmit — injects resume context + records context_reset
├── bin/                                 # NEW — vendored Sahjhan binaries
│   ├── sahjhan-aarch64-apple-darwin
│   ├── sahjhan-x86_64-apple-darwin
│   ├── sahjhan-x86_64-unknown-linux-gnu
│   └── sahjhan-aarch64-unknown-linux-gnu
├── scripts/
│   ├── vendor-sahjhan.sh               # NEW — downloads Sahjhan release binaries
│   └── install-hooks.sh                # MODIFIED — adds Sahjhan binary symlink
├── hooks/
│   └── hooks.json                       # MODIFIED — points to enforcement/hooks/
├── skills/holtz/
│   └── SKILL.md                         # MODIFIED — references Sahjhan commands
└── tests/
    └── test_sahjhan_integration.py      # NEW — tests for hook + protocol integration
```

---

## Phase 1: Protocol Definition (no Sahjhan binary needed)

### Task 1: Create TOML Config Files

**Files:**
- Create: `enforcement/protocol.toml`
- Create: `enforcement/states.toml`
- Create: `enforcement/transitions.toml`
- Create: `enforcement/events.toml`

- [ ] **Step 1: Create enforcement/ directory**

```bash
mkdir -p enforcement/templates enforcement/hooks
```

- [ ] **Step 2: Write protocol.toml**

Copy the `protocol.toml` content from the integration spec (Section "enforcement/protocol.toml"). Contains: protocol metadata, managed paths (`docs/holtz`), data dir (`docs/holtz/.sahjhan`), completion set `perspective` with 13 lenses, and command aliases.

- [ ] **Step 3: Write states.toml**

Copy the `states.toml` content from the integration spec. 14 states: `idle`, `recon`, `audit` (parameterized by perspective), `merge_ready`, `merge_done`, `fix_loop` (parameterized by perspective + iteration), `awaiting_clear`, `pattern_analysis`, `perspective_clean`, `all_perspectives_clean`, `final_sweep`, `final_sweep_clean`, `converged`, `finalized`.

- [ ] **Step 4: Write transitions.toml**

Copy the `transitions.toml` content from the integration spec. All transitions with gate conditions, including: `/clear` enforcement (awaiting_clear with context_reset gate), circuit breaker (max 15 fix iterations), per-fix hardening gate, blast radius gate, direct audit→fix_loop for lens rotations, pattern contribution gate on finalize.

- [ ] **Step 5: Write events.toml**

Copy the `events.toml` content from the integration spec. 15 event types: `recon_step`, `finding`, `finding_resolved`, `blast_radius`, `iteration_complete`, `pattern_analysis_complete`, `set_member_complete`, `baseline_updated`, `living_punchlist_updated`, `prediction`, `prediction_outcome`, `protocol_violation`, `hardening_complete`, `context_reset`, `justine_dispatched`, `pattern_contribution_complete`, `snapshot`.

- [ ] **Step 6: Validate TOML syntax**

```bash
python -c "import tomllib; [tomllib.load(open(f'enforcement/{f}','rb')) for f in ['protocol.toml','states.toml','transitions.toml','events.toml']]; print('All TOML valid')"
```

- [ ] **Step 7: Commit**

```bash
git add enforcement/
git commit -m "feat(enforcement): add Holtz protocol definition as Sahjhan TOML config"
```

---

### Task 2: Create Tera Templates

**Files:**
- Create: `enforcement/templates/status.md.tera`
- Create: `enforcement/templates/punchlist.md.tera`
- Create: `enforcement/templates/summary.md.tera`

- [ ] **Step 1: Write status.md.tera**

Template that renders from ledger state. Must produce output equivalent to the current STATUS.md format:

```
{# enforcement/templates/status.md.tera #}
# Holtz Status

**Project:** {{ protocol.name }}
**Started:** {{ genesis.timestamp | date(format="%Y-%m-%d") }}
**Last Updated:** {{ last_event.timestamp | date(format="%Y-%m-%d") }}
**Run:** {{ run_number }}

## Current Position
**Step:** {{ current_state.label }}
**Status:** {{ current_state.status }}

## Completed
{% for t in transitions %}
- [x] {{ t.label }} — {{ t.summary }}
{% endfor %}

## Next Action
{{ next_action }}

## Metrics
| Metric | Baseline | Current |
|--------|----------|---------|
| Tests passing | {{ baseline_tests }} | {{ current_tests }} |
| Punchlist open | — | {{ open_count }} |
| Punchlist resolved | — | {{ resolved_count }} |

## Active Perspective
**Current:** {{ current_perspective | default(value="—") }}
**Perspectives Completed:**
{% for p in perspectives %}
- [{% if p.complete %}x{% else %} {% endif %}] {{ p.name }}
{% endfor %}
```

- [ ] **Step 2: Write punchlist.md.tera**

Template that renders findings from ledger events. Groups by severity, includes all fields from the `finding` event type.

- [ ] **Step 3: Write summary.md.tera**

Template that renders the final convergence summary. Includes: results table, findings list, adversarial merge analysis, prediction accuracy (computed from ledger events), recommendations.

- [ ] **Step 4: Commit**

```bash
git add enforcement/templates/
git commit -m "feat(enforcement): add Tera templates for STATUS.md, PUNCHLIST.md, SUMMARY.md"
```

---

### Task 3: Create Hook Scripts

**Files:**
- Create: `enforcement/hooks/_sahjhan_bootstrap.py`
- Create: `enforcement/hooks/write_guard.py`
- Create: `enforcement/hooks/bash_guard.py`
- Create: `enforcement/hooks/stop_gate.py`
- Create: `enforcement/hooks/primer.py`

- [ ] **Step 1: Write bootstrap hook**

The bootstrap hook protects Sahjhan's own infrastructure from modification. It blocks Write/Edit to `enforcement/`, `bin/sahjhan*`, `hooks/hooks.json`, and itself. Under 30 lines. Self-referential (blocks its own path).

```python
#!/usr/bin/env python3
"""Sahjhan bootstrap hook — protects enforcement infrastructure.
DO NOT MODIFY. This hook protects itself."""
import json, os, sys

PROTECTED = ["enforcement/", "bin/sahjhan", "hooks/hooks.json",
             "_sahjhan_bootstrap.py"]

event = json.loads(sys.stdin.read())
path = event.get("tool_input", {}).get("file_path", "")
cwd = event.get("cwd", os.getcwd())
resolved = os.path.realpath(os.path.join(cwd, path)) if path else ""

for p in PROTECTED:
    full = os.path.realpath(os.path.join(cwd, p))
    if resolved.startswith(full) or resolved == full:
        print(json.dumps({"decision": "block",
            "reason": f"BLOCKED: {path} is protected enforcement infrastructure. "
                      "This file cannot be modified during an audit session."}))
        sys.exit(0)

print(json.dumps({"decision": "allow"}))
```

- [ ] **Step 2: Write write_guard.py**

Blocks Write/Edit to `docs/holtz/`. Uses `_common.py` for exit helpers. Imports `sahjhan_binary()` resolver.

- [ ] **Step 3: Write bash_guard.py**

PostToolUse hook. Calls `sahjhan manifest verify`. If non-zero exit, records `protocol_violation` event and warns.

- [ ] **Step 4: Write stop_gate.py**

Stop hook. Calls `sahjhan status --json`. If current state is not terminal, blocks with convergence message.

- [ ] **Step 5: Write primer.py**

UserPromptSubmit hook. Calls `sahjhan status --json`. If there's an active non-terminal run, records a `context_reset` event in the ledger (this is what the `awaiting_clear → fix_loop` gate checks for) and injects resume context.

- [ ] **Step 6: Test hooks manually**

Create a test TOML config, init Sahjhan, verify each hook script runs without errors when piped valid event JSON.

- [ ] **Step 7: Commit**

```bash
git add enforcement/hooks/
git commit -m "feat(enforcement): add Sahjhan hook scripts (bootstrap, write guard, bash guard, stop gate, primer)"
```

---

### Task 4: Vendor Sahjhan Binary + Install Script

**Files:**
- Create: `scripts/vendor-sahjhan.sh`
- Modify: `scripts/install-hooks.sh`
- Create: `bin/.gitkeep`

- [ ] **Step 1: Write vendor-sahjhan.sh**

```bash
#!/bin/bash
set -euo pipefail
VERSION="${1:?Usage: vendor-sahjhan.sh <version>}"
BASE_URL="https://github.com/jbrjake/sahjhan/releases/download/v${VERSION}"
mkdir -p bin
for target in aarch64-apple-darwin x86_64-apple-darwin x86_64-unknown-linux-gnu aarch64-unknown-linux-gnu; do
    echo "Downloading sahjhan-${target}..."
    curl -sL "${BASE_URL}/sahjhan-${target}" -o "bin/sahjhan-${target}"
    chmod +x "bin/sahjhan-${target}"
done
echo "${VERSION}" > bin/.sahjhan-version
echo "Vendored sahjhan v${VERSION} → bin/"
```

- [ ] **Step 2: Update install-hooks.sh**

Add platform detection and Sahjhan binary symlink:

```bash
# Sahjhan binary setup
ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
case "$ARCH" in arm64) ARCH="aarch64" ;; esac
SAHJHAN_BIN="bin/sahjhan-${ARCH}-${OS}"
if [ -f "$SAHJHAN_BIN" ]; then
    chmod +x "$SAHJHAN_BIN"
    echo "Sahjhan binary: $SAHJHAN_BIN"
else
    echo "WARNING: No Sahjhan binary for ${ARCH}-${OS}. Run scripts/vendor-sahjhan.sh first."
fi
```

- [ ] **Step 3: Add bin/ to .gitignore (except .gitkeep and version file)**

Actually, per the design, binaries ARE committed. Add `bin/.sahjhan-version` to track the version.

- [ ] **Step 4: Commit**

```bash
git add scripts/vendor-sahjhan.sh scripts/install-hooks.sh bin/.gitkeep
git commit -m "feat(enforcement): add Sahjhan binary vendoring and install script"
```

---

## Phase 2: Cutover (requires Sahjhan binary)

### Task 5: Update hooks.json

**Files:**
- Modify: `hooks/hooks.json`

- [ ] **Step 1: Replace hooks.json with Sahjhan-backed version**

Replace all 5 hook entries to point to `enforcement/hooks/`. Add bootstrap hook as FIRST PreToolUse entry. See the hooks.json in the integration spec.

Key change: bootstrap hook must come BEFORE write_guard in the PreToolUse array so it protects the enforcement directory before write_guard protects the managed directory.

- [ ] **Step 2: Verify hooks load**

Run a trivial Claude Code operation and check that hooks fire without errors. The hooks should allow all operations in a repo without an active Sahjhan run (no ledger = no enforcement).

- [ ] **Step 3: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat(enforcement): update hooks.json to use Sahjhan-backed enforcement hooks"
```

---

### Task 6: Update SKILL.md

**Files:**
- Modify: `skills/holtz/SKILL.md`

- [ ] **Step 1: Replace file write instructions with Sahjhan CLI calls**

Every instance of "write to PUNCHLIST.md" becomes `sahjhan finding --id ... --severity ...`. Every instance of "update STATUS.md" becomes implicit (Sahjhan renders it). Every convergence check becomes `sahjhan converge`.

Key sections to update:
- Core Rules: "Write findings to disk IMMEDIATELY" → "Record findings via `sahjhan finding` IMMEDIATELY"
- Rationalization Red Flags: Add the 3 new entries from the integration spec
- Step 6-8: All "write punchlist items" → `sahjhan finding`
- Step 10: All "commit" → `sahjhan fix commit --item-id BH-NNN`
- Step 11: Pattern analysis → `sahjhan event pattern_analysis_complete`
- Step 14: Lens rotation → `sahjhan lens complete <name>` + `sahjhan lens rotate`
- Step 15: Convergence → `sahjhan converge`
- Step 20: Summary → `sahjhan finalize`
- Context Survival Protocol: "STATUS.md is your program counter" → "Sahjhan ledger is your program counter. Run `sahjhan status` to see current position."

- [ ] **Step 2: Add Sahjhan quick reference section**

Add a reference block near the top of SKILL.md listing all Sahjhan commands the auditor uses during an audit.

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "feat(skill): update SKILL.md to reference Sahjhan enforcement commands"
```

---

### Task 7: Remove Old Hooks

**Files:**
- Remove: `hooks/convergence_gate.py`
- Remove: `hooks/convergence_primer.py`
- Remove: `hooks/impact_graph_gate.py`
- Remove: `hooks/status_staleness_gate.py`
- Remove: `hooks/artifact_verification.py`

- [ ] **Step 1: Verify no references to old hooks remain**

```bash
grep -rn "convergence_gate\|convergence_primer\|impact_graph_gate\|status_staleness_gate\|artifact_verification" hooks/ skills/ enforcement/ --include="*.py" --include="*.json" --include="*.md"
```

Expect: no hits in hooks.json or SKILL.md (already updated in Tasks 5-6). Hits in test files are expected (will update in Task 8).

- [ ] **Step 2: Remove old hook files**

```bash
git rm hooks/convergence_gate.py hooks/convergence_primer.py hooks/impact_graph_gate.py hooks/status_staleness_gate.py hooks/artifact_verification.py
```

- [ ] **Step 3: Remove HISTORY.json support from convergence_check.py**

Keep the test runner detection and output parsing functions. Remove the convergence checking logic (`check_convergence`, `save_history`, `MIN_ITERATION_SECONDS`). These are replaced by Sahjhan's state machine and ledger.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(enforcement): remove old hooks replaced by Sahjhan enforcement"
```

---

### Task 8: Integration Tests

**Files:**
- Create: `tests/test_sahjhan_integration.py`
- Modify: `tests/test_hooks.py` (update for new hooks)

- [ ] **Step 1: Write integration tests for new hooks**

```python
# tests/test_sahjhan_integration.py
"""Integration tests for Sahjhan enforcement hooks."""
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_write_guard_blocks_managed_path():
    """Write guard blocks Write/Edit to docs/holtz/."""
    event = {
        "tool_input": {"file_path": "docs/holtz/PUNCHLIST.md"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/write_guard.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "managed by sahjhan" in output["reason"].lower()

def test_write_guard_allows_non_managed_path():
    """Write guard allows writes outside managed paths."""
    event = {
        "tool_input": {"file_path": "src/main.py"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/write_guard.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "allow"

def test_bootstrap_blocks_enforcement_modification():
    """Bootstrap hook blocks edits to enforcement/ directory."""
    event = {
        "tool_input": {"file_path": "enforcement/protocol.toml"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/_sahjhan_bootstrap.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "block"

def test_bootstrap_blocks_binary_modification():
    """Bootstrap hook blocks edits to bin/sahjhan*."""
    event = {
        "tool_input": {"file_path": "bin/sahjhan-aarch64-apple-darwin"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/_sahjhan_bootstrap.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "block"

def test_bootstrap_blocks_self_modification():
    """Bootstrap hook blocks edits to itself."""
    event = {
        "tool_input": {"file_path": "enforcement/hooks/_sahjhan_bootstrap.py"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/_sahjhan_bootstrap.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "block"

def test_bootstrap_blocks_hooks_json_modification():
    """Bootstrap hook blocks edits to hooks.json."""
    event = {
        "tool_input": {"file_path": "hooks/hooks.json"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/_sahjhan_bootstrap.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "block"

def test_bootstrap_allows_source_files():
    """Bootstrap hook allows normal source file edits."""
    event = {
        "tool_input": {"file_path": "skills/holtz/scripts/convergence_check.py"},
        "cwd": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["python", str(REPO_ROOT / "enforcement/hooks/_sahjhan_bootstrap.py")],
        input=json.dumps(event),
        capture_output=True, text=True,
    )
    output = json.loads(result.stdout)
    assert output["decision"] == "allow"
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_sahjhan_integration.py -v
```
Expected: All pass.

- [ ] **Step 3: Update test_hooks.py for removed hooks**

Remove tests for convergence_gate, convergence_primer, impact_graph_gate, status_staleness_gate, artifact_verification. These hooks no longer exist. Keep tests for subagent_findings_check (retained) and _common.py (retained).

- [ ] **Step 4: Run full suite**

```bash
python -m pytest --tb=short -q
```
Expected: All pass, no regressions.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test(enforcement): add Sahjhan integration tests, update hook tests for cutover"
```

---

## Phase 3: Harden

### Task 9: First Enforced Audit Run

**Files:** (no files created — this is a validation task)

- [ ] **Step 1: Initialize Sahjhan for the Holtz repo**

```bash
sahjhan --config-dir enforcement init
```
Verify: `docs/holtz/.sahjhan/ledger.bin` and `docs/holtz/.sahjhan/manifest.json` exist.

- [ ] **Step 2: Run a full Holtz audit under Sahjhan enforcement**

Invoke Holtz normally. The SKILL.md now references Sahjhan commands. The hooks enforce managed-path writes. Document:
- Which Sahjhan commands the auditor calls at each step
- Which gates block and whether the blocks are correct
- Any gate conditions that are too strict (blocking legitimate work)
- Any gate conditions that are too loose (allowing evasion)
- Any missing transitions or events

- [ ] **Step 3: Document findings**

Write observations to `docs/holtz/run-20-sahjhan-shakedown.md`. This is the feedback loop — expect to iterate on gate conditions, timing thresholds, and event schemas based on real usage.

- [ ] **Step 4: Iterate on TOML config**

Adjust gate conditions, add missing events, fix transition edges based on shakedown findings. This is expected to take 2-3 iterations.

- [ ] **Step 5: Commit config changes**

```bash
git add enforcement/ docs/holtz/run-20-sahjhan-shakedown.md
git commit -m "fix(enforcement): tune gate conditions based on Run 20 shakedown"
```

---

## Consumer Dependency Flow Summary

```
jbrjake/sahjhan (Rust repo)
    │
    │  CI tags v0.1.0
    │  cross-compiles 4 platform binaries
    │  uploads as GitHub release assets
    │
    ▼
jbrjake/holtz (plugin repo)
    │
    │  scripts/vendor-sahjhan.sh 0.1.0
    │  downloads binaries → bin/
    │  commits vendored binaries
    │
    │  enforcement/*.toml
    │  defines Holtz-specific protocol
    │  consumed by sahjhan binary at runtime
    │
    │  enforcement/hooks/*.py
    │  call sahjhan binary for enforcement
    │  registered in hooks/hooks.json
    │
    │  scripts/install-hooks.sh
    │  symlinks correct platform binary
    │  sets up git hooks
    │
    ▼
End user installs Holtz plugin
    │
    │  claude --plugin-dir /path/to/holtz
    │  or: /plugin install holtz@jbrjake
    │
    │  First audit: sahjhan init (automatic or prompted)
    │  Subsequent: hooks enforce, CLI mediates
    │
    ▼
Agent runs audit under enforcement
    │
    │  sahjhan finding --id BH-001 ...
    │  sahjhan fix commit --item-id BH-001
    │  sahjhan lens complete component
    │  sahjhan converge
    │
    │  Direct writes → BLOCKED
    │  Bash tampering → DETECTED + VIOLATION
    │  Skipped steps → GATE FAILS
    │
    ▼
Convergence or circuit breaker
```

### Updating Sahjhan

When a new Sahjhan version is released:

1. Check the Sahjhan changelog for breaking changes to the config format
2. Run `scripts/vendor-sahjhan.sh <new-version>`
3. Update `enforcement/protocol.toml` if the config format changed
4. Run tests: `python -m pytest tests/test_sahjhan_integration.py -v`
5. Run a quick audit to verify enforcement still works
6. Commit: `chore: vendor sahjhan v<new-version>`

### Pinning

`bin/.sahjhan-version` contains the vendored version string. The install script can warn if the binary version (from `sahjhan --version`) doesn't match the pinned version. This prevents version drift between the TOML config and the engine binary.

---

## Review Errata

The following issues were identified during plan review and must be addressed during implementation.

### Critical Fixes

**E1. Bootstrap hook uses wrong output protocol.**
The bootstrap hook (Task 3 Step 1) outputs `{"decision": "block", "reason": "..."}` which is the **Stop hook** format. PreToolUse hooks require the full Claude Code format:
```python
print(json.dumps({
    "continue": False,
    "suppressOutput": False,
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "block",
        "permissionDecisionReason": "BLOCKED: ..."
    }
}))
```
And the allow case:
```python
print(json.dumps({
    "continue": True,
    "suppressOutput": True,
}))
```
Fix the bootstrap hook code AND fix all integration tests (Task 8) which assert against `output["decision"]` — they should assert against `output["hookSpecificOutput"]["permissionDecision"]`. Use the existing `assert_blocked()` / `assert_allowed()` helpers from `test_hooks.py`.

**E2. Add `renders.toml` to Task 1.**
Task 1 creates four TOML files but the Sahjhan engine requires a fifth: `renders.toml` configuring which templates render on which events. Add a Step between Steps 5 and 6:
```toml
# enforcement/renders.toml
[[renders]]
target = "STATUS.md"
template = "templates/status.md.tera"
trigger = "on_transition"

[[renders]]
target = "PUNCHLIST.md"
template = "templates/punchlist.md.tera"
trigger = "on_event"
event_types = ["finding", "finding_resolved"]

[[renders]]
target = "SUMMARY.md"
template = "templates/summary.md.tera"
trigger = "on_state"
state = "converged"
```

**E3. Add `test_convergence_check.py` to Task 7/8 scope.**
Task 7 Step 3 removes `check_convergence`, `save_history`, and `MIN_ITERATION_SECONDS` from `convergence_check.py`. But `tests/test_convergence_check.py` has ~50 tests that call `check_convergence()`. These tests must be removed in Task 8 Step 3 (currently only mentions `test_hooks.py`). Update Task 8 Step 3 to: "Remove tests for convergence_gate, convergence_primer, impact_graph_gate, status_staleness_gate, artifact_verification from `test_hooks.py`. Remove convergence logic tests from `test_convergence_check.py` (keep test runner parsing tests)."

### Important Fixes

**E4. Swap Task 7 and Task 8 ordering.**
Task 7 deletes old hooks. Task 8 updates tests. Between them, the test suite is broken. Reorder: update tests first (removing references to deleted hooks), then delete hooks. This keeps the suite green at every commit.

**E5. Create `_common.py` bridge for `enforcement/hooks/`.**
New hooks in `enforcement/hooks/` import from `_common.py` which lives in `hooks/`. Add a step to Task 3: either copy `_common.py` to `enforcement/hooks/`, create a symlink, or add a wrapper that adjusts `sys.path`:
```python
# enforcement/hooks/_common.py (wrapper)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'hooks'))
from _common import *  # noqa: F401,F403
```

**E6. Create `sahjhan_binary()` utility.**
All hooks need to call the Sahjhan binary. Add a shared function (in the `_common.py` wrapper or a new `enforcement/hooks/_resolve.py`) that detects the platform and returns the correct binary path:
```python
def sahjhan_binary():
    import platform
    arch = platform.machine()
    system = platform.system().lower()
    if arch == "arm64":
        arch = "aarch64"
    triple = {"darwin": f"{arch}-apple-darwin", "linux": f"{arch}-unknown-linux-gnu"}.get(system, f"{arch}-{system}")
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(root, "bin", f"sahjhan-{triple}")
```

**E7. Fix Task 4 Step 3 contradiction.**
Remove the "Add bin/ to .gitignore" text. Replace with: "Binaries are committed to git (part of plugin distribution). No .gitignore changes needed for bin/."

**E8. Add migration rollback step to Task 5.**
Before updating hooks.json: `git tag pre-sahjhan-cutover`. Document rollback: `git checkout pre-sahjhan-cutover -- hooks/hooks.json hooks/*.py`.

**E9. Add `.sahjhan/` to `.gitignore`.**
The Sahjhan data directory (`docs/holtz/.sahjhan/`) contains per-run runtime state (ledger.bin, manifest.json). Add to `.gitignore`:
```
docs/holtz/.sahjhan/
```

**E10. Add HISTORY.json cleanup to Task 7.**
Task 7 removes old hooks but does not remove references to HISTORY.json. Add: remove `save_history`/`load_history` functions from `convergence_check.py`, remove HISTORY.json path constant, add `docs/holtz/HISTORY.json` to `.gitignore` (historical runs may have it).

**E11. Bootstrap hook does not protect against Bash modifications.**
The bootstrap hook only fires on Write/Edit (PreToolUse). The agent can bypass via `echo > enforcement/protocol.toml` using Bash. Options:
(a) Add `enforcement/` to `paths.managed` in `protocol.toml` so the bash_guard's manifest verify catches it
(b) Add a second PostToolUse hook entry that checks if Bash commands reference enforcement paths
(c) Document as known limitation
Recommendation: (a) is simplest — add `enforcement/` to the managed paths list alongside `docs/holtz`.

**E12. SKILL.md update needs grep inventory.**
Add a sub-step to Task 6 Step 1:
```bash
grep -n "STATUS.md\|PUNCHLIST.md\|HISTORY.json\|convergence_check\|convergence_gate" skills/holtz/SKILL.md
```
Use this output as the inventory of lines requiring changes. The SKILL.md is 524 lines; the implementer should not find these by reading.

### Suggestions

**E13.** Add `enforcement/hooks/` to the mypy command in CLAUDE.md.
**E14.** Implement version pinning check in install-hooks.sh (currently claimed but not implemented).
**E15.** Add path traversal test for bootstrap hook (e.g., `../../enforcement/protocol.toml`).

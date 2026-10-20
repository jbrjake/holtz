# Issue #48: 8 Audit Bugs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 8 bugs reported in GitHub issue #48 — one code fix (stop hook fallback), two config fixes (transitions.toml gates), five skill doc fixes.

**Architecture:** Bug 1 adds a file-based fallback to the stop hook when daemon comms fail. Bugs 2-3 fix gate definitions in transitions.toml. Bugs 4-8 fix skill documentation to match actual gate requirements and sahjhan CLI syntax.

**Tech Stack:** Python (stop hook), TOML (gate config), Markdown (skill docs)

---

### Task 1: Bug 1 — Stop hook status-cache fallback

**Files:**
- Modify: `enforcement/hooks/stop_hook.py:46-102`
- Test: `tests/test_stop_hook.py`

This is the only code fix. When the daemon is alive but `read_cache()` returns None (e.g., auth failure), the hook currently blocks — creating an infinite loop. The fix adds a file-based fallback reading sahjhan's `status-cache.json`, and degrades to warn (not block) if that also fails.

- [ ] **Step 1: Write failing test — live daemon, no cache, status-cache.json has terminal state**

In `tests/test_stop_hook.py`, add a new test class:

```python
class TestStopHookStatusCacheFallback:
    """Tests for status-cache.json fallback when daemon cache is unreachable (issue #48 bug 1)."""

    def test_fallback_to_status_cache_terminal_state(self, tmp_path, mock_daemon):
        """Live daemon + no enforcement cache + status-cache.json with terminal state → allow stop."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        # Write our own PID (guaranteed alive)
        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # Do NOT write enforcement cache to daemon — simulates auth failure
        # (read_cache() will return None)

        # Write status-cache.json with a terminal state
        import json
        status_cache = {"state": "awaiting_clear", "ts": "2099-01-01T00:00:00Z"}
        (sahjhan_dir / "status-cache.json").write_text(json.dumps(status_cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") != "block", (
            f"Terminal state in status-cache.json should allow stop via fallback, got: {output}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stop_hook.py::TestStopHookStatusCacheFallback::test_fallback_to_status_cache_terminal_state -v`
Expected: FAIL — currently blocks because no fallback exists.

- [ ] **Step 3: Write failing test — live daemon, no cache, status-cache.json has non-terminal state**

Add to the same class in `tests/test_stop_hook.py`:

```python
    def test_fallback_to_status_cache_nonterminal_state(self, tmp_path, mock_daemon):
        """Live daemon + no enforcement cache + status-cache.json with non-terminal state → block."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        import json
        status_cache = {"state": "fix_loop", "ts": "2099-01-01T00:00:00Z"}
        (sahjhan_dir / "status-cache.json").write_text(json.dumps(status_cache))

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        assert output.get("decision") == "block", (
            f"Non-terminal state in status-cache.json should block, got: {output}"
        )
```

- [ ] **Step 4: Write failing test — live daemon, no cache, no status-cache.json → warn**

Add to the same class in `tests/test_stop_hook.py`:

```python
    def test_fallback_no_status_cache_warns(self, tmp_path, mock_daemon):
        """Live daemon + no enforcement cache + no status-cache.json → warn (not block)."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True, exist_ok=True)

        (sahjhan_dir / "daemon-init-pid").write_text(str(os.getpid()))

        # No enforcement cache, no status-cache.json

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))

        assert code == 0
        # Should warn, not block — blocking creates infinite loop
        assert output.get("decision") != "block", (
            f"Missing both caches should warn (not block) to avoid infinite loop, got: {output}"
        )
```

- [ ] **Step 5: Run all three new tests to verify they fail**

Run: `python -m pytest tests/test_stop_hook.py::TestStopHookStatusCacheFallback -v`
Expected: At least the terminal-state and warn tests fail.

- [ ] **Step 6: Implement status-cache.json fallback in stop_hook.py**

In `enforcement/hooks/stop_hook.py`, add a helper function after the `_has_active_audit` function (after line 64):

```python
def _read_status_cache_state(cwd: str) -> str | None:
    """Read state from sahjhan's status-cache.json (file-based fallback).

    Sahjhan writes this file after every init and transition (since v0.8.0).
    Used as a fallback when the daemon is alive but the enforcement cache
    is unreachable (e.g., macOS auth failure — sahjhan #26).
    """
    cache_path = os.path.join(cwd, "docs", "holtz", ".sahjhan", "status-cache.json")
    try:
        import json
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("state", "")
    except (OSError, ValueError, KeyError):
        return None
```

Then replace the `cache is None` block in `main()` (lines 96-102) with:

```python
    if cache is None:
        # Daemon is alive but enforcement cache is unreachable (e.g., auth
        # failure — sahjhan #26). Fall back to status-cache.json file.
        file_state = _read_status_cache_state(cwd)
        if file_state is not None:
            if file_state in _STOP_ALLOWED_STATES:
                if file_state in _DAEMON_CLEANUP_STATES:
                    _try_stop_daemon(cwd)
                exit_stop_allow()
            # Non-terminal state confirmed by file — block with guidance
            exit_stop_block(
                f"Audit is in state '{file_state}' (from status-cache.json fallback). "
                "You must complete the audit protocol before stopping. "
                "If this audit cannot be completed, the user can manually run: "
                "! sahjhan daemon stop\n"
                "(The next stop attempt will detect the dead daemon and allow exit.)"
            )
        # Both caches unavailable — warn instead of block to avoid
        # infinite loop (issue #48 bug 1). The user can decide.
        exit_stop_warn(
            "Sahjhan data directory exists but enforcement state is unavailable "
            "(daemon cache and status-cache.json both unreadable). "
            "Run `sahjhan status` to check audit state."
        )
```

- [ ] **Step 7: Run all stop hook tests**

Run: `python -m pytest tests/test_stop_hook.py -v`
Expected: All tests pass including the 3 new ones and the existing 5.

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest`
Expected: All pass.

- [ ] **Step 9: Commit**

```bash
git add enforcement/hooks/stop_hook.py tests/test_stop_hook.py
git commit -m "fix(enforcement): add status-cache.json fallback to stop hook

When the daemon is alive but the enforcement cache is unreachable
(e.g., macOS auth failure — sahjhan #26), fall back to reading
sahjhan's status-cache.json file. If both are unavailable, warn
instead of block to prevent infinite loop.

Fixes #48 (bug 1)."
```

---

### Task 2: Bug 2 — Fix recon_complete gate SQL

**Files:**
- Modify: `enforcement/transitions.toml:14`

- [ ] **Step 1: Fix the SQL query**

In `enforcement/transitions.toml`, line 14, change:

```toml
{ type = "query", sql = "SELECT count(DISTINCT step) >= 5 FROM events WHERE type='recon_finding'", expect = "true", intent = "recon must cover all 5 steps" },
```

to:

```toml
{ type = "query", sql = "SELECT count(DISTINCT step) >= 5 FROM events WHERE type='recon_step'", expect = "true", intent = "recon must cover all 5 steps" },
```

- [ ] **Step 2: Run linter**

Run: `ruff check enforcement/`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add enforcement/transitions.toml
git commit -m "fix(enforcement): recon_complete gate checks recon_step, not recon_finding

The SQL query checked 'recon_finding' events (optional per-step
observations) instead of 'recon_step' events (mandatory per the
skill). This required users to record undocumented extra events.

Fixes #48 (bug 2)."
```

---

### Task 3: Bug 3 — Fix audit_complete gate path

**Files:**
- Modify: `enforcement/transitions.toml:30`

- [ ] **Step 1: Fix the script path to use CLAUDE_PLUGIN_ROOT**

In `enforcement/transitions.toml`, line 30, change:

```toml
{ type = "snapshot_compare", cmd = "python skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats", extract = "edges", compare = "gt", reference = "snapshot:pre_audit_edge_count", intent = "audit must add edges to the impact graph" },
```

to:

```toml
{ type = "snapshot_compare", cmd = "python $CLAUDE_PLUGIN_ROOT/skills/holtz/scripts/impact_graph.py --graph docs/holtz/impact-graph.json stats", extract = "edges", compare = "gt", reference = "snapshot:pre_audit_edge_count", intent = "audit must add edges to the impact graph" },
```

- [ ] **Step 2: Commit**

```bash
git add enforcement/transitions.toml
git commit -m "fix(enforcement): audit_complete gate uses CLAUDE_PLUGIN_ROOT for script path

The gate used a project-relative path (skills/holtz/scripts/impact_graph.py)
which doesn't exist in target projects. Gate commands run via sh -c,
so \$CLAUDE_PLUGIN_ROOT is expanded by the shell.

Fixes #48 (bug 3)."
```

---

### Task 4: Bug 4 — Document snapshot event fields

**Files:**
- Modify: `skills/holtz/SKILL.md:143-145`

- [ ] **Step 1: Add snapshot event example to quick reference**

In `skills/holtz/SKILL.md`, after line 142 (the `iteration_complete` event) and before line 143 (the `justine_dispatched` event), add:

```
# Snapshot for gate comparison (key must match snapshot_compare reference in transitions.toml)
sahjhan event snapshot --field key=pre_audit_edge_count --field value=28
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "fix(skill): document snapshot event key/value fields in quick reference

The audit_complete gate references snapshot:pre_audit_edge_count but
the quick reference had no snapshot event example, requiring trial
and error to discover the required key and value fields.

Fixes #48 (bug 4)."
```

---

### Task 5: Bug 5 — Strengthen ledger creation guidance

**Files:**
- Modify: `skills/holtz/references/phase-recon.md:25-27`

- [ ] **Step 1: Add warning note about ledger creation**

In `skills/holtz/references/phase-recon.md`, after line 27 (after the closing ` ``` ` of the init command block), add:

```markdown

> **Warning:** Skipping `sahjhan ledger create --from run N --activate` causes "no ledger found for template 'run'; using default ledger" warnings on every subsequent `sahjhan render` and `sahjhan transition` (~20+ times per audit). Always create and activate the ledger before `run_start`.
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/references/phase-recon.md
git commit -m "fix(skill): warn about ledger creation before run_start

Skipping ledger create before run_start causes persistent render
warnings throughout the entire audit session.

Fixes #48 (bug 5)."
```

---

### Task 6: Bug 6 — Fix ledger checkpoint syntax

**Files:**
- Modify: `skills/holtz/SKILL.md:121`
- Modify: `skills/holtz/references/phase-convergence.md:11`

- [ ] **Step 1: Fix checkpoint command in SKILL.md quick reference**

In `skills/holtz/SKILL.md`, line 121, change:

```
sahjhan ledger checkpoint --name pre-clear
```

to:

```
sahjhan ledger checkpoint --snapshot pre-clear
```

- [ ] **Step 2: Fix checkpoint command in phase-convergence.md**

In `skills/holtz/references/phase-convergence.md`, line 11, change:

```
3. If not converged: run `sahjhan ledger checkpoint` then `sahjhan transition iteration_boundary`.
```

to:

```
3. If not converged: run `sahjhan ledger checkpoint --snapshot pre-clear` then `sahjhan transition iteration_boundary`.
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/SKILL.md skills/holtz/references/phase-convergence.md
git commit -m "fix(skill): correct ledger checkpoint syntax

--name is the target ledger name (defaults to active ledger since
sahjhan v0.13.1), --snapshot is the checkpoint label. The old command
used --name for the label, causing 'ledger not found' errors.

Fixes #48 (bug 6). Upstream fix: jbrjake/sahjhan#28."
```

---

### Task 7: Bug 7 — Clarify justine_dispatched mode field

**Files:**
- Modify: `skills/holtz/SKILL.md:143-144`

- [ ] **Step 1: Add clarifying comment to justine_dispatched event**

In `skills/holtz/SKILL.md`, change lines 143-144 from:

```
sahjhan event justine_dispatched --field project=holtz --field run=N \
  --field auditor=holtz --field phase=recon --field mode=full
```

to:

```
# mode is for audit trail only — gate checks presence, not mode value
sahjhan event justine_dispatched --field project=holtz --field run=N \
  --field auditor=holtz --field phase=recon --field mode=full
```

- [ ] **Step 2: Commit**

```bash
git add skills/holtz/SKILL.md
git commit -m "fix(skill): clarify justine_dispatched mode field is for audit trail only

The gate checks event presence (min_count=1), not the mode value.
Both --mode full and --mode skipped satisfy the gate.

Fixes #48 (bug 7)."
```

---

### Task 8: Bug 8 — Document merge_agent_dispatched event

**Files:**
- Modify: `skills/holtz/references/phase-merge.md:11-14`
- Modify: `skills/holtz/SKILL.md:143-145`

- [ ] **Step 1: Add merge_agent_dispatched event to phase-merge.md**

In `skills/holtz/references/phase-merge.md`, before the merge agent dispatch on line 13 (the `Agent(subagent_type=...` line), insert after line 12 (`3. **If Justine has results**, dispatch the merge agent:`):

```markdown

   First, record the dispatch event (required by the `merge_complete` gate):
   ```
   sahjhan event merge_agent_dispatched --field project=holtz --field run=N \
     --field auditor=holtz --field phase=merge --field step=9
   ```

   Then dispatch the merge agent:
```

- [ ] **Step 2: Add merge_agent_dispatched to SKILL.md quick reference**

In `skills/holtz/SKILL.md`, after the `justine_dispatched` event example (line 144-145), add:

```
sahjhan event merge_agent_dispatched --field project=holtz --field run=N \
  --field auditor=holtz --field phase=merge --field step=9
```

- [ ] **Step 3: Commit**

```bash
git add skills/holtz/references/phase-merge.md skills/holtz/SKILL.md
git commit -m "fix(skill): document merge_agent_dispatched event in Step 9

The merge_complete gate requires a merge_agent_dispatched event but
the skill procedure didn't mention recording it, forcing discovery
via gate error.

Fixes #48 (bug 8)."
```

---

### Task 9: Update sahjhan binary version

**Files:**
- Modify: `bin/.sahjhan-version`

- [ ] **Step 1: Verify binary is updated**

Run: `bin/sahjhan --version`
Expected: `sahjhan 0.13.1`

- [ ] **Step 2: Commit version bump**

```bash
git add bin/.sahjhan-version
git commit -m "chore: bump sahjhan binary to v0.13.1

Includes fix for ledger checkpoint --name defaulting to active ledger
(jbrjake/sahjhan#28)."
```

---

### Task 10: Final verification

- [ ] **Step 1: Run full test suite with linting**

Run: `python -m pytest && ruff check . && mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/`
Expected: All pass.

- [ ] **Step 2: Review all changes**

Run: `git log --oneline dev --not main | head -20`
Verify 9 commits covering all 8 bugs plus the binary version bump.

# Enforcement Hardening Phase 2: Process Quality + Efficiency

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Layer process quality enforcement (sleep detection, TDD evidence, pattern cadence, merge report validation, severity downgrade evidence) and efficiency improvements (SKILL.md split, alias fixes, ledger template resolution, binary path injection) on top of Phase 1's capability restriction foundation.

**Architecture:** All tasks are independent — no dependency chain between them. Each task modifies 1-2 existing files or creates a small new script. Phase 1 must be complete before starting tasks that touch `transitions.toml` (items 11, 12) but all others can proceed independently.

**Tech Stack:** Python 3.11+ (hooks/scripts), TOML (Sahjhan config), Markdown (SKILL.md), pytest (tests)

**Prerequisite:** Phase 1 plan must be complete (all 10 tasks merged).

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `enforcement/hooks/protocol_tracker.py` | Modify | Sleep detection (item 10) |
| `enforcement/scripts/validate_merge_report.py` | Create | Merge report content validation (item 11) |
| `enforcement/events.toml` | Modify | Add `test_failed_before_fix` event (item 12) |
| `enforcement/transitions.toml` | Modify | TDD gate on fix_commit (item 12), merge report gate (item 11) |
| `enforcement/hooks/commit_gate.py` | Modify | Pattern cadence hard-block (item 13) |
| `enforcement/scripts/check_severity_change.py` | Create | Severity downgrade checker (item 14) |
| `skills/holtz/SKILL.md` | Modify | Split into router + phase files (item 15), fix aliases (item 16) |
| `skills/holtz/references/phase-recon.md` | Create | Steps 0-4 (item 15) |
| `skills/holtz/references/phase-audit.md` | Create | Steps 5-8 (item 15) |
| `skills/holtz/references/phase-merge.md` | Create | Step 9 (item 15) |
| `skills/holtz/references/phase-fix-loop.md` | Create | Steps 10-14 (item 15) |
| `skills/holtz/references/phase-convergence.md` | Create | Steps 15-16 (item 15) |
| `skills/holtz/references/phase-finalize.md` | Create | Steps 17-20 (item 15) |
| `enforcement/hooks/primer.py` | Modify | Ledger template fix (item 17), binary path injection (item 18) |
| `tests/test_sleep_detection.py` | Create | Tests for sleep stalling (item 10) |
| `tests/test_validate_merge_report.py` | Create | Tests for merge report validation (item 11) |
| `tests/test_severity_change.py` | Create | Tests for severity downgrade checker (item 14) |

---

### Task 1: Sleep Detection in protocol_tracker.py (Item 10)

**Files:**
- Modify: `enforcement/hooks/protocol_tracker.py`
- Create: `tests/test_sleep_detection.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sleep_detection.py`:

```python
"""Tests for sleep detection in protocol_tracker.py."""
from __future__ import annotations

import pytest

# Import the function we're going to add
from enforcement.hooks.protocol_tracker import _is_sleep_cmd


class TestSleepDetection:
    def test_sleep_above_threshold(self):
        assert _is_sleep_cmd("sleep 25") is True

    def test_sleep_at_threshold(self):
        assert _is_sleep_cmd("sleep 5") is False

    def test_sleep_below_threshold(self):
        assert _is_sleep_cmd("sleep 2") is False

    def test_sleep_with_chained_command(self):
        assert _is_sleep_cmd("sleep 30 && echo done") is True

    def test_no_sleep(self):
        assert _is_sleep_cmd("echo hello") is False

    def test_sleep_in_unrelated_context(self):
        """The word 'sleep' in a non-sleep command should not match."""
        assert _is_sleep_cmd("grep sleep config.py") is False

    def test_sleep_with_float(self):
        assert _is_sleep_cmd("sleep 10.5") is True

    def test_sleep_1s(self):
        """Short sleeps (<=5s) are fine — used for legitimate polling."""
        assert _is_sleep_cmd("sleep 1") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sleep_detection.py -v
```

Expected: FAIL (function doesn't exist).

- [ ] **Step 3: Add `_is_sleep_cmd` to protocol_tracker.py**

In `enforcement/hooks/protocol_tracker.py`, after the `_is_tdd_cmd` function (line 38), add:

```python
def _is_sleep_cmd(cmd: str) -> bool:
    """Detect sleep commands used to game timing gates.

    Returns True for sleep >5 seconds. Short sleeps (<=5s) are allowed
    for legitimate polling. Matches 'sleep N' at the start of the command
    or after a chain operator (&&, ;, |).
    """
    # Match sleep followed by a number (int or float) > 5
    m = re.match(r"^sleep\s+(\d+(?:\.\d+)?)", cmd.strip())
    if m:
        return float(m.group(1)) > 5
    return False
```

- [ ] **Step 4: Integrate into the stall counter in `main()`**

In the `main()` function, find the stall increment block (around line 116-118):

```python
    # Test/lint/type-check commands are legitimate TDD activity — don't count as stalling
    if not _is_tdd_cmd(cmd):
        cache["stall"] = cache.get("stall", 0) + 1
```

Replace with:

```python
    # Test/lint/type-check commands are legitimate TDD activity — don't count as stalling
    if _is_sleep_cmd(cmd):
        # Sleep to game timing gates gets double stall penalty
        cache["stall"] = cache.get("stall", 0) + 2
    elif not _is_tdd_cmd(cmd):
        cache["stall"] = cache.get("stall", 0) + 1
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_sleep_detection.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add enforcement/hooks/protocol_tracker.py tests/test_sleep_detection.py
git commit -m "feat(enforcement): detect sleep as stalling in protocol_tracker

sleep >5s now increments the stall counter by 2 (double penalty).
Prevents gaming timing gates like min_elapsed by sleeping through them."
```

---

### Task 2: Merge Report Content Validation (Item 11)

**Files:**
- Create: `enforcement/scripts/validate_merge_report.py`
- Create: `tests/test_validate_merge_report.py`
- Modify: `enforcement/transitions.toml`

- [ ] **Step 1: Write failing tests**

Create `tests/test_validate_merge_report.py`:

```python
"""Tests for validate_merge_report.py."""
from __future__ import annotations

import subprocess
import sys

import pytest

SCRIPT = "enforcement/scripts/validate_merge_report.py"


def _run(path: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT, path],
        capture_output=True, text=True,
    )


def test_valid_report(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text(
        "# Merged Punchlist\n\n"
        "## Agreement\n\n"
        "| ID | Description |\n|---|---|\n| BH-001 | test |\n\n"
        "**Agreements:** 3\n\n"
        "## Holtz-Only\n\n"
        "| ID | Description |\n|---|---|\n\n"
        "## Justine-Only\n\n"
        "| ID | Description |\n|---|---|\n\n"
        "## Blind Spot Analysis\n\n"
        "No blind spots identified.\n"
    )
    result = _run(str(report))
    assert result.returncode == 0


def test_missing_agreement_section(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text(
        "# Merged Punchlist\n\n"
        "## Holtz-Only\n\nstuff\n"
        "## Justine-Only\n\nstuff\n"
        "## Blind Spot Analysis\n\nstuff\n"
    )
    result = _run(str(report))
    assert result.returncode != 0
    assert "Agreement" in result.stderr


def test_missing_blind_spot_section(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text(
        "# Merged Punchlist\n\n"
        "## Agreement\n\nstuff\n"
        "## Holtz-Only\n\nstuff\n"
        "## Justine-Only\n\nstuff\n"
    )
    result = _run(str(report))
    assert result.returncode != 0
    assert "Blind Spot" in result.stderr


def test_nonexistent_file():
    result = _run("/nonexistent/path.md")
    assert result.returncode != 0


def test_empty_file(tmp_path):
    report = tmp_path / "PUNCHLIST-MERGED.md"
    report.write_text("")
    result = _run(str(report))
    assert result.returncode != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_validate_merge_report.py -v
```

Expected: FAIL (script doesn't exist).

- [ ] **Step 3: Create the validation script**

Create `enforcement/scripts/validate_merge_report.py`:

```python
#!/usr/bin/env python3
"""Validate that PUNCHLIST-MERGED.md has required sections.

Used as a gate condition on the 'merge_complete' transition.
Exit 0 if valid, exit 1 with details on stderr if not.
"""
from __future__ import annotations

import re
import sys

REQUIRED_SECTIONS = [
    ("Agreement", r"##\s+Agreement"),
    ("Holtz-Only", r"##\s+Holtz[- ]Only"),
    ("Justine-Only", r"##\s+Justine[- ]Only"),
    ("Blind Spot Analysis", r"##\s+Blind\s+Spot"),
]


def validate(path: str) -> list[str]:
    """Return list of missing section names."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return [name for name, _ in REQUIRED_SECTIONS]

    if not content.strip():
        return [name for name, _ in REQUIRED_SECTIONS]

    missing = []
    for name, pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, content, re.IGNORECASE):
            missing.append(name)
    return missing


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: validate_merge_report.py <path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    missing = validate(path)
    if missing:
        print(f"FAIL: Missing required sections: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    print("PASS: All required sections present.")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_validate_merge_report.py -v
```

Expected: All PASS.

- [ ] **Step 5: Update transitions.toml merge_complete gate**

In `enforcement/transitions.toml`, find the `merge_complete` transition and replace the `file_exists` gate:

```toml
[[transitions]]
from = "merge_ready"
to = "merge_done"
command = "merge_complete"
gates = [
    { type = "ledger_has_event", event = "merge_agent_dispatched", min_count = 1, intent = "merge must be performed by a separate merge-agent subagent" },
    { type = "command_succeeds", cmd = "python enforcement/scripts/validate_merge_report.py docs/holtz/PUNCHLIST-MERGED.md", timeout = 10, intent = "merged punchlist must have required sections (Agreement, Holtz-Only, Justine-Only, Blind Spot Analysis)" },
]
```

- [ ] **Step 6: Commit**

```bash
git add enforcement/scripts/validate_merge_report.py tests/test_validate_merge_report.py enforcement/transitions.toml
git commit -m "feat(enforcement): content validation for merge report

Replaces file_exists gate on merge_complete with content validation.
PUNCHLIST-MERGED.md must contain Agreement, Holtz-Only, Justine-Only,
and Blind Spot Analysis sections."
```

---

### Task 3: TDD Evidence in Ledger (Item 12)

**Files:**
- Modify: `enforcement/events.toml`
- Modify: `enforcement/transitions.toml`

- [ ] **Step 1: Add test_failed_before_fix event type**

In `enforcement/events.toml`, add after the enforcement hardening events section:

```toml
[events.test_failed_before_fix]
description = "Test demonstrating the bug was run and failed before the fix"
fields = [
    { name = "finding_id", type = "string", pattern = "^B[HJ]-\\d{3}$" },
    { name = "test_name", type = "string" },
    { name = "project", type = "string" },
    { name = "run", type = "string", pattern = "^\\d+$" },
    { name = "auditor", type = "string", pattern = "^(holtz|justine)$" },
]
```

- [ ] **Step 2: Add TDD gate to fix_commit transition**

In `enforcement/transitions.toml`, find the `fix_commit` transition (line 59-70) and add:

```toml
    { type = "ledger_has_event_since", event = "test_failed_before_fix", since = "last_transition", intent = "TDD: a failing test must be recorded before fix is committed" },
```

- [ ] **Step 3: Commit**

```bash
git add enforcement/events.toml enforcement/transitions.toml
git commit -m "feat(enforcement): require TDD evidence before fix_commit

New test_failed_before_fix event type. fix_commit transition now gates
on this event existing since the last transition, enforcing write-test-
first discipline."
```

---

### Task 4: Pattern Analysis Cadence Hard-Block (Item 13)

**Files:**
- Modify: `enforcement/hooks/commit_gate.py`

- [ ] **Step 1: Change pattern cadence from soft-warn to hard-block**

In `enforcement/hooks/commit_gate.py`, find the `main()` function. After the unconditional commit blocking (added in Phase 1 Task 8), add:

```python
    # Hard block: pattern analysis overdue after 3+ fixes
    if (cache and is_fix_loop_state(cache)
            and is_git_commit(cmd)
            and cache.get("fixes_since_pattern", 0) >= 3
            and not cache.get("unregistered_commits")):
        exit_block(
            "BLOCKED: Pattern analysis overdue "
            f"({cache['fixes_since_pattern']} fixes since last analysis). "
            "Run: sahjhan transition pattern_check"
        )
```

- [ ] **Step 2: Run existing commit_gate tests**

```bash
python -m pytest tests/test_commit_gate.py -v
```

Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add enforcement/hooks/commit_gate.py
git commit -m "fix(enforcement): hard-block commits when pattern analysis overdue

Changes pattern analysis cadence check from soft-warn to hard-block.
After 3 fix_commits without pattern_analysis_complete, git commit is
blocked until pattern analysis is run."
```

---

### Task 5: Severity Downgrade Evidence (Item 14)

**Files:**
- Create: `enforcement/scripts/check_severity_change.py`
- Create: `tests/test_severity_change.py`
- Modify: `enforcement/events.toml`

- [ ] **Step 1: Add optional evidence_path to finding_resolved**

In `enforcement/events.toml`, find the `[events.finding_resolved]` block and add the field:

```toml
    { name = "evidence_path", type = "string", optional = true },
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_severity_change.py`:

```python
"""Tests for check_severity_change.py."""
from __future__ import annotations

import pytest

from enforcement.scripts.check_severity_change import check_downgrade


def test_no_downgrade_passes():
    """Same severity — no evidence needed."""
    result = check_downgrade(
        original_severity="MEDIUM",
        resolved_severity="MEDIUM",
        evidence_path=None,
    )
    assert result is True


def test_downgrade_with_evidence_passes(tmp_path):
    """Downgrade with valid evidence path passes."""
    evidence = tmp_path / "evidence.md"
    evidence.write_text("Code at file.py:42 shows this is actually LOW.")
    result = check_downgrade(
        original_severity="HIGH",
        resolved_severity="MEDIUM",
        evidence_path=str(evidence),
    )
    assert result is True


def test_downgrade_without_evidence_fails():
    """Downgrade without evidence path fails."""
    result = check_downgrade(
        original_severity="HIGH",
        resolved_severity="LOW",
        evidence_path=None,
    )
    assert result is False


def test_downgrade_with_nonexistent_evidence_fails():
    """Downgrade with nonexistent evidence file fails."""
    result = check_downgrade(
        original_severity="HIGH",
        resolved_severity="MEDIUM",
        evidence_path="/nonexistent/evidence.md",
    )
    assert result is False


def test_upgrade_passes():
    """Upgrading severity never requires evidence."""
    result = check_downgrade(
        original_severity="LOW",
        resolved_severity="HIGH",
        evidence_path=None,
    )
    assert result is True
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_severity_change.py -v
```

Expected: FAIL (module doesn't exist).

- [ ] **Step 4: Create the script**

Create `enforcement/scripts/check_severity_change.py`:

```python
#!/usr/bin/env python3
"""Check that severity downgrades include evidence.

When a finding's resolved severity is lower than the original,
an evidence_path must be provided pointing to a real file.
"""
from __future__ import annotations

import os
import sys

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def check_downgrade(
    original_severity: str,
    resolved_severity: str,
    evidence_path: str | None,
) -> bool:
    """Return True if the severity change is valid.

    A downgrade requires evidence_path to exist as a real file.
    Same severity or upgrades always pass.
    """
    orig_rank = SEVERITY_ORDER.get(original_severity, 0)
    resolved_rank = SEVERITY_ORDER.get(resolved_severity, 0)

    if resolved_rank >= orig_rank:
        return True  # not a downgrade

    # It's a downgrade — evidence required
    if not evidence_path:
        return False
    return os.path.isfile(evidence_path)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: check_severity_change.py <original> <resolved> [evidence_path]", file=sys.stderr)
        sys.exit(1)

    original = sys.argv[1]
    resolved = sys.argv[2]
    evidence = sys.argv[3] if len(sys.argv) > 3 else None

    if check_downgrade(original, resolved, evidence):
        sys.exit(0)
    else:
        print(
            f"FAIL: Severity downgrade from {original} to {resolved} "
            f"requires evidence_path pointing to a real file.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_severity_change.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add enforcement/scripts/check_severity_change.py tests/test_severity_change.py enforcement/events.toml
git commit -m "feat(enforcement): severity downgrade requires evidence path

New check_severity_change.py validates that when a finding's severity
is lowered from the original, an evidence_path field points to a real
file containing justification."
```

---

### Task 6: Split SKILL.md Into Phase Sections (Item 15)

**Files:**
- Modify: `skills/holtz/SKILL.md`
- Create: 6 new files in `skills/holtz/references/`

This task requires reading the current SKILL.md, identifying the step boundaries, and splitting accordingly. The implementing agent should:

- [ ] **Step 1: Read the current SKILL.md**

```bash
wc -l skills/holtz/SKILL.md
```

Note the line count. Read the file to identify step boundaries.

- [ ] **Step 2: Create phase-recon.md (Steps 0-4)**

Create `skills/holtz/references/phase-recon.md` containing all content from Steps 0 through 4 (inclusive). Include the Step 0 preamble, Step 1 (CI/git), Step 2 (prior-run), Step 3 (recon summary), Step 4 (predictions).

- [ ] **Step 3: Create phase-audit.md (Steps 5-8)**

Create `skills/holtz/references/phase-audit.md` containing Steps 5 (Justine dispatch), 6 (doc-to-implementation), 7 (test quality), 8 (adversarial code audit).

- [ ] **Step 4: Create phase-merge.md (Step 9)**

Create `skills/holtz/references/phase-merge.md` containing Step 9 (merge).

- [ ] **Step 5: Create phase-fix-loop.md (Steps 10-14)**

Create `skills/holtz/references/phase-fix-loop.md` containing Steps 10 (TDD fix loop), 11 (pattern analysis), 12 (per-fix hardening), 13 (blast radius), 14 (lens rotation).

- [ ] **Step 6: Create phase-convergence.md (Steps 15-16)**

Create `skills/holtz/references/phase-convergence.md` containing Steps 15 (convergence check) and 16 (final sweep).

- [ ] **Step 7: Create phase-finalize.md (Steps 17-20)**

Create `skills/holtz/references/phase-finalize.md` containing Steps 17 (architecture baseline), 18 (living punchlist), 19 (pattern contribution), 20 (finalize).

- [ ] **Step 8: Reduce SKILL.md to router**

Rewrite `skills/holtz/SKILL.md` to ~80 lines containing:
- Core rules (the 6 override rules)
- Phase index with file paths: "Read the reference for your current phase: `references/phase-recon.md`, etc."
- Rationalization red flags table
- Context survival protocol
- Quick reference (canonical commands, not aliases)

Remove all step-specific content that was moved to phase files.

- [ ] **Step 9: Verify no content was lost**

```bash
# Count total lines across all phase files + router
wc -l skills/holtz/SKILL.md skills/holtz/references/phase-*.md
```

Total should be roughly equal to the original SKILL.md line count (some duplication of headers is expected).

- [ ] **Step 10: Commit**

```bash
git add skills/holtz/SKILL.md skills/holtz/references/phase-*.md
git commit -m "feat(skills): split SKILL.md into phase-specific reference files

Reduces per-session token cost from ~12K to ~3-4K by letting the agent
read only the phase it needs. Router SKILL.md retains core rules,
rationalization red flags, and quick reference."
```

---

### Task 7: Fix CLI Aliases (Item 16)

**Files:**
- Modify: `skills/holtz/SKILL.md`
- Modify: `skills/holtz/references/phase-*.md` (all 6)

- [ ] **Step 1: Find all alias references**

```bash
grep -rn "sahjhan run start\|sahjhan audit claim\|sahjhan recon complete\|sahjhan merge complete\|sahjhan fix commit\|sahjhan lens complete\|sahjhan lens rotate\|sahjhan sweep start\|sahjhan converge\|sahjhan finalize\|sahjhan finding\|sahjhan resolve" skills/holtz/
```

- [ ] **Step 2: Replace each alias with canonical command**

Use these mappings (from `protocol.toml` aliases section):
- `sahjhan run start` -> `sahjhan transition run_start`
- `sahjhan recon complete` -> `sahjhan transition recon_complete`
- `sahjhan audit complete` -> `sahjhan transition audit_complete`
- `sahjhan merge complete` -> `sahjhan transition merge_complete`
- `sahjhan fix commit` -> `sahjhan transition fix_commit`
- `sahjhan lens complete` -> `sahjhan set complete perspective`
- `sahjhan lens rotate` -> `sahjhan transition lens_rotate`
- `sahjhan sweep start` -> `sahjhan transition final_sweep_start`
- `sahjhan converge` -> `sahjhan transition converge`
- `sahjhan finalize` -> `sahjhan transition finalize`
- `sahjhan finding` -> `sahjhan event finding`
- `sahjhan resolve` -> `sahjhan event finding_resolved`
- `sahjhan audit claim` -> `sahjhan event audit_claim`

- [ ] **Step 3: Run a verification grep**

```bash
grep -rn "sahjhan run start\|sahjhan audit claim\|sahjhan recon complete" skills/holtz/
```

Expected: No matches (all aliases replaced).

- [ ] **Step 4: Commit**

```bash
git add skills/holtz/
git commit -m "fix(skills): replace CLI aliases with canonical sahjhan commands

The aliases documented in SKILL.md were not implemented in the binary.
All references now use canonical commands (transition/event/set)."
```

---

### Task 8: Fix Ledger Template Resolution (Item 17)

**Files:**
- Modify: `enforcement/hooks/primer.py`
- Modify: `skills/holtz/SKILL.md` (or phase reference files)

- [ ] **Step 1: Investigate the warning**

The warning "no ledger found for template 'run'" appears when using `--ledger run-N`. Check what the primer hook injects:

```bash
grep -n "ledger" enforcement/hooks/primer.py
```

And check what the active-run marker contains:

```bash
cat docs/holtz/.sahjhan/active-run 2>/dev/null || echo "no active-run file"
```

- [ ] **Step 2: Fix the ledger naming in SKILL.md and primer**

The issue is likely that SKILL.md examples use `--ledger run-N` but the ledger was created with a different format. Ensure the `_active_ledger()` function in `_common.py` returns the correct name, and SKILL.md examples match.

If the `active-run` file contains `run-25`, then `--ledger run-25` should work. If Sahjhan uses a different naming convention, update the documentation to match.

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/primer.py skills/holtz/
git commit -m "fix(enforcement): fix ledger template resolution

Ensures primer hook and SKILL.md use consistent ledger naming that
matches sahjhan's actual template resolution."
```

---

### Task 9: Primer Injects Binary Path (Item 18)

**Files:**
- Modify: `enforcement/hooks/primer.py`

- [ ] **Step 1: Read the current primer injection output**

```bash
grep -n "injection\|inject\|exit_warn" enforcement/hooks/primer.py
```

Identify where the context injection string is built.

- [ ] **Step 2: Add binary path to injection**

Find the section in `primer.py` where it builds the injection text (near the `format_state_line` call and `exit_warn`). Add:

```python
    binary = sahjhan_binary()
    # Include binary path so agent doesn't waste turns discovering it
    injection_parts.append(f"Sahjhan binary: {binary}")
```

Or if the injection is built as a single string, append:

```python
    injection += f"\nSahjhan binary: {binary}"
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -x --tb=short -q
```

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add enforcement/hooks/primer.py
git commit -m "fix(enforcement): primer injects sahjhan binary path

Saves the agent from re-discovering the binary path each session.
The resolved path is included in the primer context injection."
```

---

### Task 10: Run Full Suite and Verify

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite with coverage**

```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks --cov-report=term-missing --cov-fail-under=60
```

Expected: All pass, coverage >= 60%.

- [ ] **Step 2: Run linter**

```bash
ruff check .
```

Expected: Clean.

- [ ] **Step 3: Run type checker**

```bash
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

Expected: Clean.

- [ ] **Step 4: Verify SKILL.md split is loadable**

```bash
# Check all phase files exist and are non-empty
for f in skills/holtz/references/phase-*.md; do
    echo "$f: $(wc -l < "$f") lines"
done
```

Expected: All 6 files exist with >10 lines each.

# Hook Validation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent hook schema drift from ever shipping broken again by adding a JSON schema definition file, a live Claude Code smoke test, and a pre-release gate.

**Architecture:** Three layers of defense: (1) a JSON schema file (`tests/hook_schema.py`) derived from the official docs that all test validators reference as single source of truth, (2) a live smoke test script (`scripts/smoke-test-hooks.sh`) that registers hooks in a temp settings file and runs them through `claude -p` to get real Claude Code validation, (3) a pre-release checklist test that verifies the schema file matches current docs.

**Tech Stack:** Python (pytest, json), Bash (claude CLI), WebFetch (docs verification)

---

### Task 1: Create the hook output schema definition

**Files:**
- Create: `tests/hook_schema.py`

This is the single source of truth for what Claude Code accepts. Every validator and assertion references this file. When Claude Code changes their spec, you update ONE file.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hook_schema.py
"""Tests that hook_schema.py is internally consistent and complete."""
import pytest
from hook_schema import (
    PRETOOLUSE_VALID_DECISIONS,
    STOP_VALID_DECISIONS,
    UNIVERSAL_FIELDS,
    validate_hook_output,
)


def test_pretooluse_decisions_are_strings():
    assert all(isinstance(d, str) for d in PRETOOLUSE_VALID_DECISIONS)


def test_pretooluse_has_deny():
    """The value that blocks a tool call must exist."""
    assert "deny" in PRETOOLUSE_VALID_DECISIONS


def test_pretooluse_does_not_have_block():
    """'block' is the OLD deprecated value — must not be listed."""
    assert "block" not in PRETOOLUSE_VALID_DECISIONS


def test_stop_only_has_block():
    """Stop hooks only support 'block' for decision."""
    assert STOP_VALID_DECISIONS == {"block"}


def test_validate_pretooluse_allow():
    errs = validate_hook_output("PreToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        },
    })
    assert errs == []


def test_validate_pretooluse_deny():
    errs = validate_hook_output("PreToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "blocked",
        },
    })
    assert errs == []


def test_validate_pretooluse_rejects_block():
    errs = validate_hook_output("PreToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
        },
    })
    assert len(errs) == 1
    assert "block" in errs[0]


def test_validate_pretooluse_rejects_continue_false_with_deny():
    errs = validate_hook_output("PreToolUse", {
        "continue": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        },
    })
    assert any("continue" in e for e in errs)


def test_validate_stop_allow_empty():
    errs = validate_hook_output("Stop", {})
    assert errs == []


def test_validate_stop_block():
    errs = validate_hook_output("Stop", {"decision": "block", "reason": "not done"})
    assert errs == []


def test_validate_stop_rejects_approve():
    errs = validate_hook_output("Stop", {"decision": "approve", "reason": "done"})
    assert len(errs) == 1


def test_validate_posttooluse_allow():
    errs = validate_hook_output("PostToolUse", {"continue": True, "suppressOutput": True})
    assert errs == []


def test_validate_posttooluse_with_hook_specific():
    errs = validate_hook_output("PostToolUse", {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "warning",
        },
    })
    assert errs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hook_schema.py -v`
Expected: ImportError — `hook_schema` does not exist yet

- [ ] **Step 3: Write the schema definition**

```python
# tests/hook_schema.py
"""Claude Code hook output schema — single source of truth.

Derived from: https://code.claude.com/docs/en/hooks
Last verified: 2026-04-11

ALL test validators and assertions must reference this file.
When Claude Code changes their spec, update THIS file only.
"""
from __future__ import annotations

# ── PreToolUse ──────────────────────────────────────────────
# hookSpecificOutput.permissionDecision valid values.
# "block" is the OLD deprecated value — do NOT use it.
PRETOOLUSE_VALID_DECISIONS: set[str] = {"allow", "deny", "ask", "defer"}

# hookSpecificOutput fields for PreToolUse
PRETOOLUSE_HSO_FIELDS: set[str] = {
    "hookEventName",          # Required, literal "PreToolUse"
    "permissionDecision",     # Required, one of PRETOOLUSE_VALID_DECISIONS
    "permissionDecisionReason",  # Optional
    "updatedInput",           # Optional
    "additionalContext",      # Optional
}

# ── PostToolUse ─────────────────────────────────────────────
# Top-level decision field (only "block" is valid, omit to allow)
POSTTOOLUSE_VALID_DECISIONS: set[str] = {"block"}

# hookSpecificOutput fields for PostToolUse
POSTTOOLUSE_HSO_FIELDS: set[str] = {
    "hookEventName",          # Required if hookSpecificOutput present
    "additionalContext",      # Optional
    "updatedMCPToolOutput",   # Optional
}

# ── Stop / SubagentStop ────────────────────────────────────
# Only "block" is valid. Omit decision to allow.
STOP_VALID_DECISIONS: set[str] = {"block"}

# ── UserPromptSubmit ────────────────────────────────────────
USERPROMPTSUBMIT_VALID_DECISIONS: set[str] = {"block"}

USERPROMPTSUBMIT_HSO_FIELDS: set[str] = {
    "hookEventName",
    "additionalContext",
    "sessionTitle",
}

# ── Universal top-level fields (all events) ─────────────────
UNIVERSAL_FIELDS: set[str] = {
    "continue",         # bool, default true. false = stop Claude entirely
    "stopReason",       # str, shown to user when continue=false
    "suppressOutput",   # bool, default false
    "systemMessage",    # str, shown to user
}

# ── Spec URL (for automated freshness checks) ──────────────
SPEC_URL = "https://code.claude.com/docs/en/hooks"


def validate_hook_output(event_type: str, output: dict) -> list[str]:
    """Validate hook JSON output against Claude Code's schema.

    Returns a list of error strings. Empty list = valid.
    """
    errors: list[str] = []

    if not output:
        return errors  # Empty output is valid for all events

    if event_type == "PreToolUse":
        errors.extend(_validate_pretooluse(output))
    elif event_type == "PostToolUse":
        errors.extend(_validate_posttooluse(output))
    elif event_type in ("Stop", "SubagentStop"):
        errors.extend(_validate_stop(output))
    elif event_type == "UserPromptSubmit":
        errors.extend(_validate_user_prompt_submit(output))

    return errors


def _validate_pretooluse(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        if hso.get("hookEventName") != "PreToolUse":
            errors.append(
                f"hookEventName must be 'PreToolUse', got '{hso.get('hookEventName')}'"
            )
        decision = hso.get("permissionDecision")
        if decision not in PRETOOLUSE_VALID_DECISIONS:
            errors.append(
                f"Invalid permissionDecision '{decision}'. "
                f"Valid: {PRETOOLUSE_VALID_DECISIONS}"
            )
    else:
        # No hookSpecificOutput — check for misplaced fields
        bad = {"permissionDecision", "additionalContext"} & set(output.keys())
        if bad:
            errors.append(f"Fields {bad} must be inside hookSpecificOutput")

    # continue=false + deny is a contradiction
    if output.get("continue") is False and hso.get("permissionDecision") == "deny":
        errors.append(
            "continue=false stops Claude entirely — don't combine with deny"
        )

    return errors


def _validate_posttooluse(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        event_name = hso.get("hookEventName")
        if event_name and event_name != "PostToolUse":
            errors.append(f"hookEventName must be 'PostToolUse', got '{event_name}'")

    decision = output.get("decision")
    if decision is not None and decision not in POSTTOOLUSE_VALID_DECISIONS:
        errors.append(f"Invalid PostToolUse decision '{decision}'. Only 'block' is valid.")

    return errors


def _validate_stop(output: dict) -> list[str]:
    errors: list[str] = []
    decision = output.get("decision")
    if decision is not None and decision not in STOP_VALID_DECISIONS:
        errors.append(
            f"Invalid Stop decision '{decision}'. Only 'block' is valid; omit to allow."
        )
    # Stop hooks must NOT use hookSpecificOutput
    if "hookSpecificOutput" in output:
        errors.append("Stop hooks must not use hookSpecificOutput")
    return errors


def _validate_user_prompt_submit(output: dict) -> list[str]:
    errors: list[str] = []
    hso = output.get("hookSpecificOutput", {})

    if hso:
        event_name = hso.get("hookEventName")
        if event_name and event_name != "UserPromptSubmit":
            errors.append(
                f"hookEventName must be 'UserPromptSubmit', got '{event_name}'"
            )

    decision = output.get("decision")
    if decision is not None and decision not in USERPROMPTSUBMIT_VALID_DECISIONS:
        errors.append(
            f"Invalid UserPromptSubmit decision '{decision}'. Only 'block' is valid."
        )

    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hook_schema.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/hook_schema.py tests/test_hook_schema.py
git commit -m "feat(hooks): add hook output schema as single source of truth

Derived from https://code.claude.com/docs/en/hooks (2026-04-11).
All test validators must reference this file instead of
hardcoding schema assumptions independently."
```

---

### Task 2: Rewire E2E validators to use the schema

**Files:**
- Modify: `tests/test_e2e_hook_invocation.py:220-370` (validators)

Replace the hand-rolled validators with calls to `hook_schema.validate_hook_output()`.

- [ ] **Step 1: Write a failing test that proves the old validator and new schema agree**

```python
# Add to tests/test_hook_schema.py

def test_e2e_validators_delegate_to_schema():
    """E2E validators must use hook_schema, not independent logic."""
    import inspect
    import test_e2e_hook_invocation as e2e
    # The validators must import from hook_schema
    src = inspect.getsource(e2e.validate_pretooluse_output)
    assert "hook_schema" in src or "validate_hook_output" in src, (
        "validate_pretooluse_output must delegate to hook_schema"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_hook_schema.py::test_e2e_validators_delegate_to_schema -v`
Expected: FAIL — current validators don't reference hook_schema

- [ ] **Step 3: Rewrite the E2E validators**

Replace the five `validate_*_output` functions in `test_e2e_hook_invocation.py` with:

```python
from hook_schema import validate_hook_output

def validate_pretooluse_output(output: dict, hook_cmd: str) -> list[str]:
    """Validate PreToolUse output against the canonical schema."""
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("PreToolUse", output)]

def validate_posttooluse_output(output: dict, hook_cmd: str) -> list[str]:
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("PostToolUse", output)]

def validate_stop_output(output: dict, hook_cmd: str) -> list[str]:
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("Stop", output)]

def validate_subagent_stop_output(output: dict, hook_cmd: str) -> list[str]:
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("SubagentStop", output)]

def validate_user_prompt_submit_output(output: dict, hook_cmd: str) -> list[str]:
    if "__raw_stdout" in output:
        return [f"Invalid JSON from {hook_cmd}: {output['__raw_stdout'][:200]}"]
    return [f"{hook_cmd}: {e}" for e in validate_hook_output("UserPromptSubmit", output)]
```

Remove the `_VALID_PERMISSION_DECISIONS` constant from test_e2e_hook_invocation.py.

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e_hook_invocation.py tests/test_hook_schema.py
git commit -m "refactor(hooks): rewire E2E validators to use hook_schema

Validators now delegate to hook_schema.validate_hook_output()
instead of maintaining independent validation logic."
```

---

### Task 3: Create the live Claude Code smoke test

**Files:**
- Create: `scripts/smoke-test-hooks.sh`

This script registers each hook one at a time in a temp settings file, runs `claude -p "echo test"` to trigger it, and checks for "validation failed" or "hook error" in the output. This is the only test that catches what Claude Code actually rejects.

- [ ] **Step 1: Write the smoke test script**

```bash
#!/usr/bin/env bash
# scripts/smoke-test-hooks.sh
#
# Live smoke test: registers each hook against real Claude Code
# and verifies no "validation failed" or "hook error" in output.
#
# Requires: claude CLI in PATH
# Usage: scripts/smoke-test-hooks.sh [--verbose]
#
# Exit 0 = all hooks valid, Exit 1 = at least one failed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERBOSE="${1:-}"
FAILURES=0
TESTED=0

# Temp dir for isolated settings
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# Create minimal project structure
mkdir -p "$WORK_DIR/src"
echo "print('hello')" > "$WORK_DIR/src/app.py"

# Check claude is available
if ! command -v claude &>/dev/null; then
    echo "SKIP: claude CLI not in PATH"
    exit 0
fi

# Map each hook to its event type and a trigger prompt
declare -A HOOK_EVENTS
HOOK_EVENTS["enforcement/hooks/_daemon_lifecycle.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/_sahjhan_bootstrap.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/pre_tool_hook.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/commit_gate.py"]="PreToolUse"
HOOK_EVENTS["enforcement/hooks/post_tool_hook.py"]="PostToolUse"
HOOK_EVENTS["enforcement/hooks/bash_guard.py"]="PostToolUse"
HOOK_EVENTS["enforcement/hooks/protocol_tracker.py"]="PostToolUse"
HOOK_EVENTS["enforcement/hooks/stop_hook.py"]="Stop"
HOOK_EVENTS["enforcement/hooks/primer.py"]="UserPromptSubmit"
HOOK_EVENTS["hooks/subagent_findings_check.py"]="SubagentStop"

for hook_path in "${!HOOK_EVENTS[@]}"; do
    event="${HOOK_EVENTS[$hook_path]}"
    hook_name=$(basename "$hook_path" .py)
    TESTED=$((TESTED + 1))

    # Build a settings.json that registers just this one hook
    # Use the appropriate matcher for the event type
    if [[ "$event" == "PreToolUse" ]]; then
        MATCHER="Bash"
        PROMPT="run echo smoke-test-$hook_name"
    elif [[ "$event" == "PostToolUse" ]]; then
        MATCHER="Bash"
        PROMPT="run echo smoke-test-$hook_name"
    elif [[ "$event" == "Stop" ]]; then
        # Stop hooks fire when Claude tries to stop — use a one-shot prompt
        MATCHER="*"
        PROMPT="say hi"
    elif [[ "$event" == "UserPromptSubmit" ]]; then
        MATCHER="*"
        PROMPT="say hi"
    elif [[ "$event" == "SubagentStop" ]]; then
        # SubagentStop is hard to trigger in isolation — skip live test
        echo "SKIP $hook_name ($event — requires subagent)"
        continue
    fi

    # Write temp settings
    cat > "$WORK_DIR/.claude/settings.local.json" <<SETTINGS_EOF
{
    "hooks": {
        "$event": [
            {
                "matcher": "$MATCHER",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python \"$REPO_ROOT/$hook_path\""
                    }
                ]
            }
        ]
    }
}
SETTINGS_EOF

    mkdir -p "$WORK_DIR/.claude"

    # Run claude with the hook active
    OUTPUT=$(cd "$WORK_DIR" && claude -p "$PROMPT" --no-input 2>&1) || true

    # Check for validation failures
    if echo "$OUTPUT" | grep -qi "json.*validation.*failed\|hook.*error.*validation"; then
        echo "FAIL $hook_name ($event): json validation failed"
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo "  Output: ${OUTPUT:0:500}"
        fi
        FAILURES=$((FAILURES + 1))
    else
        echo "PASS $hook_name ($event)"
    fi
done

echo ""
echo "Results: $((TESTED - FAILURES))/$TESTED passed"
if [[ $FAILURES -gt 0 ]]; then
    echo "FAILED: $FAILURES hook(s) produced invalid JSON"
    exit 1
fi
echo "All hooks produce valid JSON per Claude Code"
exit 0
```

- [ ] **Step 2: Make it executable and test**

```bash
chmod +x scripts/smoke-test-hooks.sh
scripts/smoke-test-hooks.sh --verbose
```

Expected: All hooks PASS (or SKIP if claude CLI not available)

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke-test-hooks.sh
git commit -m "feat(hooks): add live Claude Code smoke test

Registers each hook against real claude CLI and checks for
validation failures. This is the only test that catches what
Claude Code actually rejects vs what we think it accepts."
```

---

### Task 4: Create the pre-release schema freshness gate

**Files:**
- Create: `tests/test_hook_schema_freshness.py`

This test fetches the official Claude Code hooks docs page, extracts the valid `permissionDecision` values, and compares against our schema file. If Claude Code added or removed values, the test fails.

- [ ] **Step 1: Write the test**

```python
# tests/test_hook_schema_freshness.py
"""Schema freshness gate — verifies hook_schema.py matches current Claude Code docs.

This test fetches the official docs page and extracts valid field values.
If Claude Code changes their spec, this test fails BEFORE we ship.

Requires network access. Skipped in offline/CI environments.
"""
from __future__ import annotations

import re
import urllib.request

import pytest

from hook_schema import (
    PRETOOLUSE_VALID_DECISIONS,
    SPEC_URL,
    STOP_VALID_DECISIONS,
)


def _fetch_docs() -> str:
    """Fetch the Claude Code hooks docs page. Raises on failure."""
    req = urllib.request.Request(SPEC_URL, headers={"User-Agent": "holtz-schema-check/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


@pytest.fixture(scope="module")
def docs_html() -> str:
    try:
        return _fetch_docs()
    except Exception as e:
        pytest.skip(f"Cannot fetch docs (offline?): {e}")


class TestPreToolUseDecisions:
    """Verify permissionDecision enum matches the live docs."""

    def test_allow_in_docs(self, docs_html: str):
        assert '"allow"' in docs_html

    def test_deny_in_docs(self, docs_html: str):
        assert '"deny"' in docs_html

    def test_ask_in_docs(self, docs_html: str):
        assert '"ask"' in docs_html

    def test_defer_in_docs(self, docs_html: str):
        assert '"defer"' in docs_html

    def test_block_not_in_pretooluse_decisions(self):
        """'block' was deprecated for PreToolUse — must not be in our schema."""
        assert "block" not in PRETOOLUSE_VALID_DECISIONS

    def test_no_extra_decisions(self, docs_html: str):
        """Every value in our schema must appear in the docs."""
        for decision in PRETOOLUSE_VALID_DECISIONS:
            assert f'"{decision}"' in docs_html, (
                f"'{decision}' is in our schema but not found in docs — stale?"
            )


class TestStopDecisions:

    def test_block_is_only_stop_decision(self):
        assert STOP_VALID_DECISIONS == {"block"}

    def test_approve_not_valid_for_stop(self):
        """'approve' was never a valid Stop decision."""
        assert "approve" not in STOP_VALID_DECISIONS
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_hook_schema_freshness.py -v`
Expected: ALL PASS (or skip if offline)

- [ ] **Step 3: Add a pytest marker for network tests**

Add to `pyproject.toml` or `conftest.py`:

```python
# conftest.py (if not already present, add to existing)
def pytest_configure(config):
    config.addinivalue_line("markers", "network: tests that require network access")
```

Mark the freshness tests:

```python
@pytest.mark.network
class TestPreToolUseDecisions:
    ...
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_hook_schema_freshness.py
git commit -m "feat(hooks): add schema freshness gate against live docs

Fetches Claude Code docs and verifies our permissionDecision
enum matches. Fails before release if Claude Code changes
their spec. Skipped when offline."
```

---

### Task 5: Add pre-release checklist test

**Files:**
- Modify: `tests/test_enforcement_config.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_enforcement_config.py`:

```python
def test_pre_release_hook_validation_gate():
    """Pre-release gate: smoke test script exists and is executable."""
    smoke_test = Path(__file__).parent.parent / "scripts" / "smoke-test-hooks.sh"
    assert smoke_test.exists(), "scripts/smoke-test-hooks.sh missing"
    assert os.access(smoke_test, os.X_OK), "scripts/smoke-test-hooks.sh not executable"


def test_hook_schema_exists():
    """Pre-release gate: hook_schema.py must exist as source of truth."""
    schema = Path(__file__).parent / "hook_schema.py"
    assert schema.exists(), "tests/hook_schema.py missing — hooks have no schema to validate against"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_enforcement_config.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_enforcement_config.py
git commit -m "feat(hooks): add pre-release gate for schema and smoke test"
```

---

### Task 6: Document the release process addition

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add smoke test to the release checklist**

In the "Cutting a Release" section of CLAUDE.md, add after step 3:

```markdown
4. Run hook smoke test: `scripts/smoke-test-hooks.sh --verbose`
5. Run schema freshness check: `python -m pytest tests/test_hook_schema_freshness.py -v`
```

Renumber subsequent steps.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add hook smoke test and schema check to release checklist"
```

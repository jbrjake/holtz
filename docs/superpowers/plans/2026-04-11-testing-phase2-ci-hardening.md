# Phase 2: CI Pipeline Hardening

## Context

Part of the testing methodology overhaul. CI currently runs pytest + ruff +
mypy with a 60% coverage gate. The two checks that would have caught the last
three broken releases (hook smoke test, schema freshness) run only at release
time, manually. This phase makes CI catch skill/hook drift on every PR.

Depends on: Phase 1 (markers in pyproject.toml).
Enables: Phase 5 (process changes).

## Tasks

### 1. Add Contract Gate to CI

In `.github/workflows/ci.yml`, add a step after the test step:

```yaml
- name: Contract gate
  run: python scripts/contract_gate.py
```

This catches skill/hook drift on every PR. No network access needed.

### 2. Add Skill-File Change Detection to CI

Create `scripts/check_contract_test_sync.sh`:

```bash
#!/bin/bash
# Fail CI if skill/reference files changed without updating contract tests.
# Override with [skip-contract] in commit message.
set -euo pipefail

# Compare against the merge base, not just HEAD~1, so PRs with
# multiple commits are handled correctly.
BASE="${GITHUB_BASE_REF:-main}"
CHANGED_FILES=$(git diff --name-only "origin/${BASE}...HEAD" 2>/dev/null || git diff --name-only HEAD~1)

SKILL_CHANGED=$(echo "$CHANGED_FILES" | grep -c 'skills/.*\.md\|references/.*\.md' || true)
CONTRACT_CHANGED=$(echo "$CHANGED_FILES" | grep -c 'test_contract_commands.py' || true)
GATE_CHANGED=$(echo "$CHANGED_FILES" | grep -c 'contract_gate.py' || true)
SKIP_TAG=$(git log -1 --pretty=%B | grep -c '\[skip-contract\]' || true)

if [ "$SKILL_CHANGED" -gt 0 ] && [ "$CONTRACT_CHANGED" -eq 0 ] && [ "$GATE_CHANGED" -eq 0 ] && [ "$SKIP_TAG" -eq 0 ]; then
    echo "FAIL: Skill/reference files changed but contract tests were not updated."
    echo ""
    echo "Changed skill files:"
    echo "$CHANGED_FILES" | grep 'skills/.*\.md\|references/.*\.md'
    echo ""
    echo "Either update test_contract_commands.py / contract_gate.py,"
    echo "or add [skip-contract] to the commit message."
    exit 1
fi

echo "OK: Contract test sync check passed."
```

Add to CI:
```yaml
- name: Contract test sync check
  run: bash scripts/check_contract_test_sync.sh
```

### 3. Raise Coverage Gate to 80%

In `.github/workflows/ci.yml`, change the pytest invocation:

```yaml
- name: Tests
  run: |
    python -m pytest \
      --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks \
      --cov-report=term-missing --cov-fail-under=80
```

Current coverage is 97%, so this just prevents regression. 80% is the floor
— below that something has gone structurally wrong.

### 4. Local Schema Validation (No Network)

The schema freshness test (`test_hook_schema_freshness.py`) requires network
access and only runs at release time. Create a local schema snapshot that CI
can check without network:

a. Create `tests/fixtures/hook_output_schema.json` containing the expected
   JSON structure for each hook event type (PreToolUse, PostToolUse, Stop,
   SubagentStop, UserPromptSubmit). Derive this from the current working
   hooks.

b. Create `tests/test_hook_output_schema.py` that:
   - Imports the schema from the fixture file
   - Runs each hook with a representative event
   - Validates the output JSON matches the schema structure
   - Checks that `permissionDecision` values are in `{"allow", "deny"}`
   - Checks that required keys exist

c. Add a `scripts/refresh_hook_schema.py` script that regenerates the
   fixture from live hooks. Run this periodically or when Claude Code
   updates its hook protocol.

This way CI catches "hook emits invalid JSON" without needing network access
to fetch Claude Code docs.

### 5. Verify

- Push a PR that changes a skill file without updating contract tests →
  CI fails
- Push a PR that changes a skill file WITH contract test updates → CI passes
- Push a PR with `[skip-contract]` in the commit → CI passes
- Coverage below 80% → CI fails
- Hook emitting wrong JSON structure → CI fails
- All existing tests still pass

## Estimated Scope

~1 hour. Mostly CI config and one new test file for schema validation.

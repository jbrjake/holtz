#!/bin/bash
# Fail CI if skill/reference files changed without updating contract tests.
# Override with [skip-contract] in commit message.
set -euo pipefail

# Compare against the merge base, not just HEAD~1, so PRs with
# multiple commits are handled correctly.
BASE="${GITHUB_BASE_REF:-main}"

# Shallow clones (default in GitHub Actions) don't have origin/<base> or
# parent commits.  Fetch just enough history to compute the diff.
if ! git rev-parse "origin/${BASE}" >/dev/null 2>&1; then
    git fetch --depth=1 origin "${BASE}" 2>/dev/null || true
fi

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

#!/bin/bash
# Fail CI if skill/reference files changed without updating contract tests.
# Override with [skip-contract] in commit message.
set -euo pipefail

# Compare against the base branch to find changed files in this PR.
BASE="${GITHUB_BASE_REF:-main}"

# Shallow clones (default in GitHub Actions) don't have origin/<base> or
# parent commits.  Fetch just the tip so we can compare trees.
if ! git rev-parse "origin/${BASE}" >/dev/null 2>&1; then
    git fetch --depth=1 origin "${BASE}" 2>/dev/null || true
fi

# Two-dot diff compares trees directly — no merge-base needed, so it works
# even when the fetch above creates a disconnected ref.  Three-dot diff
# requires connected history which shallow clones don't have.
# Fall back to empty string if nothing works (contract gate catches real issues).
CHANGED_FILES=$(git diff --name-only "origin/${BASE}" HEAD 2>/dev/null \
    || git diff --name-only HEAD~1 2>/dev/null \
    || echo "")

SKILL_CHANGED=$(echo "$CHANGED_FILES" | grep -c 'skills/.*\.md\|references/.*\.md' || true)
CONTRACT_CHANGED=$(echo "$CHANGED_FILES" | grep -c 'test_contract_commands.py' || true)
GATE_CHANGED=$(echo "$CHANGED_FILES" | grep -c 'contract_gate.py' || true)

# [skip-contract] may live in ANY commit of the PR, not just the tip. On a
# pull_request, GitHub Actions checks out the synthetic merge commit, so
# `git log -1` is always the auto-generated "Merge <sha> into <sha>" message
# and never carries the tag — which made the documented escape unreachable on
# exactly the event where this check runs. Scan the PR head branch's own
# commits instead. Fetch ONLY the head ref so FETCH_HEAD is unambiguous
# (fetching multiple refs makes `git log FETCH_HEAD` read just the first).
SKIP_TAG=0
_scan_for_skip() {
    echo "$1" | grep -q '\[skip-contract\]'
}
if [ -n "${GITHUB_HEAD_REF:-}" ]; then
    git fetch --depth=50 origin "$GITHUB_HEAD_REF" >/dev/null 2>&1 || true
    if _scan_for_skip "$(git log --pretty=%B -50 FETCH_HEAD 2>/dev/null || echo '')"; then
        SKIP_TAG=1
    fi
fi
# Fallback for push events and local runs, where HEAD is a real commit
# (not a merge commit) and carries the tag directly.
if [ "$SKIP_TAG" -eq 0 ]; then
    if _scan_for_skip "$(git log --pretty=%B -50 HEAD 2>/dev/null || echo '')"; then
        SKIP_TAG=1
    fi
fi

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

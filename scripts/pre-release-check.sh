#!/usr/bin/env bash
# scripts/pre-release-check.sh
#
# Run ALL pre-release checks in one command.
# Exit 0 = ready to release. Exit 1 = not ready.
#
# This replaces the multi-step manual checklist. One command,
# impossible to skip steps.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FAILURES=0

run_check() {
    local name="$1"
    shift
    echo ""
    echo "=== $name ==="
    if "$@"; then
        echo "--- $name: PASS ---"
    else
        echo "--- $name: FAIL ---"
        FAILURES=$((FAILURES + 1))
    fi
}

# --- Static analysis ---
run_check "Ruff" ruff check .
run_check "Mypy" mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/

# --- Contract and schema gates ---
run_check "Contract Gate" python scripts/contract_gate.py
run_check "Schema Freshness" python -m pytest tests/test_hook_schema_freshness.py -v

# --- Full test suite with coverage ---
run_check "Full Test Suite" python -m pytest \
    --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks \
    --cov-report=term-missing --cov-fail-under=80

# --- Live hook validation ---
run_check "Hook Smoke Test" scripts/smoke-test-hooks.sh --verbose

# --- Version bump check ---
run_check "Version Bump" bash -c '
    CURRENT=$(python -c "import json; print(json.load(open(\".claude-plugin/plugin.json\"))[\"version\"])")
    LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    LATEST_VER=${LATEST_TAG#v}
    if [ "$CURRENT" = "$LATEST_VER" ]; then
        echo "FAIL: Version $CURRENT matches latest tag. No version bump detected."
        exit 1
    fi
    echo "Version: $CURRENT (latest tag: $LATEST_TAG)"
'

# --- Summary ---
echo ""
echo "========================================"
if [ "$FAILURES" -gt 0 ]; then
    echo "PRE-RELEASE CHECK: $FAILURES FAILURE(S)"
    echo "Fix failures before releasing."
    exit 1
fi
echo "PRE-RELEASE CHECK: ALL PASSED"
echo "Ready to release."

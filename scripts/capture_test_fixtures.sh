#!/usr/bin/env bash
# Capture real test runner output from this project for parser test fixtures.
#
# Usage: scripts/capture_test_fixtures.sh
#
# Outputs are saved to tests/fixtures/real_*.txt and can be used alongside
# the synthetic fixtures in runner_fixtures.py for parser validation.
#
# Note: pytest -q with all-pass produces no summary line (just dots), so we
# use --tb=short -q which includes the summary on failure. The -x flag
# stops at first failure to keep output small.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FIXTURE_DIR="$REPO_ROOT/tests/fixtures"

# Activate the project venv so python3/pytest/ruff/mypy resolve to the
# installed dependencies (mirrors git-hooks/pre-commit).
if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.venv/bin/activate"
fi

mkdir -p "$FIXTURE_DIR"

echo "Capturing pytest output (with summary line)..."
python3 -m pytest tests/ --tb=short -q \
    -m "not slow and not machine_specific and not network" \
    --ignore=tests/test_real_daemon_integration.py \
    -x 2>&1 \
    > "$FIXTURE_DIR/real_pytest_verbose.txt" || true

echo "Capturing ruff output..."
ruff check . 2>&1 \
    > "$FIXTURE_DIR/real_ruff_output.txt" || true

echo "Capturing mypy output..."
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/ 2>&1 \
    > "$FIXTURE_DIR/real_mypy_output.txt" || true

echo ""
echo "Fixtures written to $FIXTURE_DIR:"
ls -la "$FIXTURE_DIR"/real_*.txt

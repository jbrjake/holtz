# Phase 5: Release Process Hardening

## Context

Part of the testing methodology overhaul. The release process is a 10-step
manual checklist in CLAUDE.md. Steps 4-5 (smoke test, schema freshness) are
easy to skip and have been skipped. This phase consolidates everything into
a single pre-release gate script and adds branch protection.

Depends on: Phase 2 (CI contract gate).

## Tasks

### 1. Consolidate Pre-Release Checks

Create `scripts/pre-release-check.sh`:

```bash
#!/bin/bash
# scripts/pre-release-check.sh
# Run ALL pre-release checks in one command.
# Exit 0 = ready to release. Exit 1 = not ready.
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

run_check "Ruff" ruff check .
run_check "Mypy" mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
run_check "Contract Gate" python scripts/contract_gate.py
run_check "Full Test Suite" python -m pytest \
    --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks \
    --cov-report=term-missing --cov-fail-under=80
run_check "Hook Smoke Test" scripts/smoke-test-hooks.sh --verbose
run_check "Schema Freshness" python -m pytest tests/test_hook_schema_freshness.py -v

echo ""
echo "========================================"
if [ "$FAILURES" -gt 0 ]; then
    echo "PRE-RELEASE CHECK: $FAILURES FAILURE(S)"
    echo "Fix failures before releasing."
    exit 1
fi
echo "PRE-RELEASE CHECK: ALL PASSED"
echo "Ready to release."
```

### 2. Simplify Release Checklist in CLAUDE.md

Replace the current 10-step checklist with:

```markdown
## Cutting a Release

1. Ensure dev is up to date and CI is green.
2. Review commits since last release: `git log dev --not main --oneline`
3. Read the version from `.claude-plugin/plugin.json` (already bumped by hook).
4. Run pre-release checks: `scripts/pre-release-check.sh`
5. Generate changelog: `python scripts/generate-changelog.py --write`
   (preview without `--write` first). Review the output, commit it.
6. Create a release PR:
   ```
   gh pr create --base main --head dev \
     --title "chore: release vX.Y.Z" \
     --body "<highlights and commit summary>"
   ```
7. Wait for CI to pass on the PR.
8. Merge: `gh pr merge <number> --merge --subject "chore: release vX.Y.Z"`
9. The release GitHub Action automatically creates the git tag and Release.
```

The old steps 4 (smoke test), 5 (schema freshness), and the pytest step are
now inside `pre-release-check.sh`. One command, impossible to skip steps.

### 3. Branch Protection (Document Only)

Document the recommended branch protection settings for `main`. Don't
configure them automatically (that requires repo admin access and is a
human decision).

Add to CLAUDE.md or a new `docs/CONTRIBUTING.md`:

```markdown
## Branch Protection (recommended)

For `main` branch:
- Require status checks: CI must pass
- Require up-to-date branches before merging
- No direct pushes (all changes via PR from dev)
- No force pushes

For `dev` branch:
- Require status checks: CI must pass
- Allow direct pushes (for iterative development)
```

### 4. Version Alignment Check

Add a check to `pre-release-check.sh` that verifies the version in
`plugin.json` has been bumped since the last release tag:

```bash
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
```

### 5. Verify

- `scripts/pre-release-check.sh` runs all checks in sequence
- If any check fails, the script exits 1 with a clear error
- If all checks pass, the script exits 0 with "Ready to release"
- CLAUDE.md release checklist references the single script
- A release following the new checklist works end-to-end

## Estimated Scope

~30 minutes. Mostly writing the shell script and editing CLAUDE.md.
The branch protection is documentation only.

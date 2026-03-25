# Release Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a dev-branch workflow with automatic version bumping, PR-based releases, and GitHub Action-driven tagging.

**Architecture:** A `commit-msg` git hook auto-bumps `.claude-plugin/plugin.json` on conventional commits. Releases merge `dev -> main` via PR. A GitHub Action creates tags and GitHub Releases from the merge commit body.

**Tech Stack:** Bash (git hook, install script), GitHub Actions YAML, Python 3 (JSON manipulation in hook), `gh` CLI (branch protection)

**Spec:** `docs/superpowers/specs/2026-03-24-release-workflow-design.md`

**Repository:** `jbrjake/holtz` (remote: `git@github.com:jbrjake/holtz.git`)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `git-hooks/commit-msg` | Create | Parse conventional commit prefix, bump plugin.json version, stage it |
| `scripts/install-hooks.sh` | Create | Symlink `git-hooks/*` into `.git/hooks/`, with safety checks |
| `.github/workflows/release.yml` | Create | On push to main: read version, create tag + GitHub Release |
| `.github/workflows/ci.yml` | Modify | Add `dev` to push/PR triggers |
| `CLAUDE.md` | Create | Document branch workflow, conventional commits, release process |
| `tests/test_commit_msg_hook.py` | Create | Unit tests for the version bumping logic |

---

## Task 1: Write and test the commit-msg hook

This is the core piece. The hook is a bash script that calls Python for JSON manipulation.

**Files:**
- Create: `git-hooks/commit-msg`
- Create: `tests/test_commit_msg_hook.py`

- [ ] **Step 1: Write the hook script**

Create `git-hooks/commit-msg`:

```bash
#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG_FILE="$1"
PLUGIN_JSON=".claude-plugin/plugin.json"

# Read the first line of the commit message
FIRST_LINE=$(head -1 "$COMMIT_MSG_FILE")

# Skip merge commits
if [[ "$FIRST_LINE" =~ ^Merge ]]; then
    exit 0
fi

# Check for BREAKING CHANGE in body
HAS_BREAKING=false
if grep -q "^BREAKING CHANGE" "$COMMIT_MSG_FILE" 2>/dev/null; then
    HAS_BREAKING=true
fi

# Parse conventional commit prefix
# Matches: type(scope)!: or type!: or type(scope): or type:
if [[ "$FIRST_LINE" =~ ^([a-z]+)(\([^)]+\))?(!)?: ]]; then
    TYPE="${BASH_REMATCH[1]}"
    BANG="${BASH_REMATCH[3]}"
else
    # Not a conventional commit — no bump
    exit 0
fi

# Determine bump type
BUMP=""
if [[ "$BANG" == "!" ]] || [[ "$HAS_BREAKING" == "true" ]]; then
    BUMP="major"
elif [[ "$TYPE" == "feat" ]]; then
    BUMP="minor"
elif [[ "$TYPE" == "fix" ]] || [[ "$TYPE" == "perf" ]]; then
    BUMP="patch"
else
    # docs, chore, refactor, test, ci, style — no bump
    exit 0
fi

# Guard: skip if plugin.json has unstaged changes (manual edit in progress)
if [[ -n "$(git diff --name-only -- "$PLUGIN_JSON" 2>/dev/null)" ]]; then
    echo "commit-msg: plugin.json already modified, skipping auto-bump." >&2
    exit 0
fi

# Check plugin.json exists
if [[ ! -f "$PLUGIN_JSON" ]]; then
    echo "commit-msg: $PLUGIN_JSON not found, aborting." >&2
    exit 1
fi

# Bump version using Python for reliable JSON handling
NEW_VERSION=$(python3 -c "
import json, sys

with open('$PLUGIN_JSON') as f:
    data = json.load(f)

version = data.get('version', '0.0.0')
parts = version.split('.')
if len(parts) != 3:
    print(f'commit-msg: malformed version \"{version}\"', file=sys.stderr)
    sys.exit(1)

try:
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
except ValueError:
    print(f'commit-msg: non-numeric version \"{version}\"', file=sys.stderr)
    sys.exit(1)

bump = '$BUMP'
if bump == 'major':
    major += 1
    minor = 0
    patch = 0
elif bump == 'minor':
    minor += 1
    patch = 0
elif bump == 'patch':
    patch += 1

new_version = f'{major}.{minor}.{patch}'
data['version'] = new_version

with open('$PLUGIN_JSON', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')

print(new_version)
") || {
    echo "commit-msg: version bump failed" >&2
    exit 1
}

# Stage the updated plugin.json
git add "$PLUGIN_JSON"

echo "commit-msg: bumped version to $NEW_VERSION ($BUMP)" >&2
```

- [ ] **Step 2: Make the hook executable**

Run: `chmod +x git-hooks/commit-msg`

- [ ] **Step 3: Write tests for the version bump logic**

Create `tests/test_commit_msg_hook.py`. These tests exercise the hook's logic by running it against a temporary git repo with a real plugin.json.

```python
"""Tests for the commit-msg git hook version bumping logic."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "git-hooks" / "commit-msg"


def _setup_git_repo(tmp_path: Path, version: str = "0.4.0") -> Path:
    """Create a minimal git repo with plugin.json and the commit-msg hook installed."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)

    # Create plugin.json
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    plugin_json = plugin_dir / "plugin.json"
    plugin_json.write_text(json.dumps({"name": "test", "version": version}, indent=2) + "\n")

    # Install our hook
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_dest = hooks_dir / "commit-msg"
    hook_dest.symlink_to(HOOK_PATH.resolve())

    # Initial commit (without hook — use a no-bump prefix)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "chore: initial commit"],
        check=True,
        capture_output=True,
    )

    return tmp_path


def _make_commit(repo: Path, msg: str, touch_file: str = "dummy.txt", body: str = "") -> subprocess.CompletedProcess:
    """Create a file and commit with the given message. Returns the completed process."""
    dummy = repo / touch_file
    dummy.write_text(msg)
    subprocess.run(["git", "-C", str(repo), "add", touch_file], check=True, capture_output=True)
    cmd = ["git", "-C", str(repo), "commit", "-m", msg]
    if body:
        cmd.extend(["-m", body])
    return subprocess.run(cmd, capture_output=True, text=True)


def _get_version(repo: Path) -> str:
    """Read the current version from plugin.json."""
    plugin_json = repo / ".claude-plugin" / "plugin.json"
    return json.loads(plugin_json.read_text())["version"]


class TestMinorBump:
    def test_feat_bumps_minor(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "feat: add new feature", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.0"

    def test_feat_with_scope_bumps_minor(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "feat(auth): add login", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.0"


class TestPatchBump:
    def test_fix_bumps_patch(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.5.0")
        result = _make_commit(repo, "fix: resolve crash", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.1"

    def test_perf_bumps_patch(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.5.0")
        result = _make_commit(repo, "perf: optimize query", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.1"

    def test_fix_with_scope_bumps_patch(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "fix(parser): handle edge case", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "1.2.4"


class TestMajorBump:
    def test_feat_bang_bumps_major(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "feat!: redesign API", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "2.0.0"

    def test_fix_bang_bumps_major(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "fix!: breaking change in error format", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "2.0.0"

    def test_breaking_change_in_body_bumps_major(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "feat: add new API", "a.txt", body="BREAKING CHANGE: removes old endpoint")
        assert result.returncode == 0
        assert _get_version(repo) == "2.0.0"


class TestNoBump:
    def test_docs_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "docs: update README", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_chore_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "chore: clean up deps", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_refactor_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "refactor: simplify logic", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_test_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "test: add coverage", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_ci_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "ci: update workflow", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_style_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "style: format code", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_merge_commit_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "Merge branch 'feature/foo' into dev", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_non_conventional_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "random commit message", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"


class TestCumulativeBumping:
    def test_feat_then_fix_then_feat(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        _make_commit(repo, "feat: first feature", "a.txt")
        assert _get_version(repo) == "0.5.0"
        _make_commit(repo, "fix: a fix", "b.txt")
        assert _get_version(repo) == "0.5.1"
        _make_commit(repo, "feat: second feature", "c.txt")
        assert _get_version(repo) == "0.6.0"


class TestGuards:
    def test_skips_if_plugin_json_already_modified(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        # Modify plugin.json without staging it
        plugin_json = repo / ".claude-plugin" / "plugin.json"
        data = json.loads(plugin_json.read_text())
        data["version"] = "1.0.0"
        plugin_json.write_text(json.dumps(data, indent=2) + "\n")
        # Now make a feat commit — hook should skip, version stays at manual edit
        result = _make_commit(repo, "feat: should not auto-bump", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "1.0.0"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_commit_msg_hook.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add git-hooks/commit-msg tests/test_commit_msg_hook.py
git commit -m "feat: add commit-msg hook with automatic version bumping from conventional commits"
```

Note: This commit itself will trigger the hook (once installed). For this first commit on main before dev exists, commit directly.

---

## Task 2: Write the install-hooks script

**Files:**
- Create: `scripts/install-hooks.sh`

- [ ] **Step 1: Write the install script**

Create `scripts/install-hooks.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"
SRC_DIR="$REPO_ROOT/git-hooks"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: $SRC_DIR not found. Run from the repository root." >&2
    exit 1
fi

for hook in "$SRC_DIR"/*; do
    hook_name="$(basename "$hook")"
    dest="$GIT_HOOKS_DIR/$hook_name"

    # Check for existing hook that isn't our symlink
    if [[ -e "$dest" ]] && [[ ! -L "$dest" ]]; then
        echo "Error: $dest already exists and is not a symlink. Remove it manually or back it up first." >&2
        exit 1
    fi

    # If it's already our symlink, skip
    if [[ -L "$dest" ]] && [[ "$(readlink "$dest")" == "$hook" ]]; then
        echo "$hook_name: already installed"
        continue
    fi

    ln -sf "$hook" "$dest"
    echo "$hook_name: installed"
done
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/install-hooks.sh`

- [ ] **Step 3: Test the install script locally**

Run: `scripts/install-hooks.sh`
Expected: Output `commit-msg: installed` and `.git/hooks/commit-msg` is a symlink to `git-hooks/commit-msg`.

Verify: `ls -la .git/hooks/commit-msg`
Expected: symlink pointing to `../../git-hooks/commit-msg` or the absolute path.

- [ ] **Step 4: Commit**

```bash
git add scripts/install-hooks.sh
git commit -m "chore: add install-hooks script for git hook setup"
```

---

## Task 3: Update CI to include dev branch

**Files:**
- Modify: `.github/workflows/ci.yml:3-7`

- [ ] **Step 1: Update the CI triggers**

Change lines 3-7 of `.github/workflows/ci.yml` from:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

To:

```yaml
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add dev branch to CI triggers"
```

This must land on main before branch protection is enabled (bootstrap ordering).

---

## Task 4: Create the release GitHub Action

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write the release workflow**

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          fetch-tags: true

      - name: Read version from plugin.json
        id: version
        run: |
          VERSION=$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])")
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          echo "tag=v$VERSION" >> "$GITHUB_OUTPUT"

      - name: Check if tag already exists
        id: check_tag
        run: |
          if git rev-parse "v${{ steps.version.outputs.version }}" >/dev/null 2>&1; then
            echo "exists=true" >> "$GITHUB_OUTPUT"
          else
            echo "exists=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Extract merge commit body
        if: steps.check_tag.outputs.exists == 'false'
        id: body
        run: |
          {
            echo "body<<RELEASE_BODY_EOF"
            git log -1 --format=%b HEAD
            echo "RELEASE_BODY_EOF"
          } >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        if: steps.check_tag.outputs.exists == 'false'
        run: |
          gh release create "$TAG" \
            --title "$TAG" \
            --notes-file <(echo "$RELEASE_BODY") \
            --target "$GITHUB_SHA"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAG: ${{ steps.version.outputs.tag }}
          RELEASE_BODY: ${{ steps.body.outputs.body }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow for automatic tagging and GitHub Releases"
```

---

## Task 5: Create CLAUDE.md with workflow documentation

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md**

Create `CLAUDE.md`:

```markdown
# Holtz — Development Guide

## Branch Model

- **`main`** — default branch, releases only. What users see on GitHub.
- **`dev`** — integration branch. All work happens here or on feature branches off dev.
- Feature branches: `feat/name`, `fix/name`, etc. PRs target `dev`.
- Releases: merge `dev -> main` via PR. No direct pushes to main.

## Conventional Commits (Required)

All commits MUST use conventional commit format:

- `feat:` / `feat(scope):` — new feature (bumps minor)
- `fix:` / `fix(scope):` — bug fix (bumps patch)
- `perf:` / `perf(scope):` — performance improvement (bumps patch)
- `feat!:` / `fix!:` / `BREAKING CHANGE` in body — breaking change (bumps major)
- `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `style:` — no version bump

A `commit-msg` git hook automatically bumps `.claude-plugin/plugin.json` version on feat/fix/perf commits. No manual version management needed.

## Setup

After cloning, install git hooks:

```bash
scripts/install-hooks.sh
```

## Cutting a Release

1. Ensure dev is up to date and CI is green.
2. Review commits since last release: `git log dev --not main --oneline`
3. Read the version from `.claude-plugin/plugin.json` (already bumped by hook).
4. Create a release PR:
   ```
   gh pr create --base main --head dev \
     --title "chore: release vX.Y.Z" \
     --body "<highlights and commit summary>"
   ```
5. Wait for CI to pass on the PR.
6. Merge: `gh pr merge <number> --merge --subject "chore: release vX.Y.Z" --body "<summary>"`
7. The release GitHub Action automatically creates the git tag and GitHub Release.

## Running Tests

```bash
python -m pytest --tb=short -q
ruff check .
mypy skills/holtz/scripts/ hooks/
```
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with branch model and release workflow"
```

---

## Task 6: Bootstrap — create dev branch and configure branch protection

This task is the one-time setup that transitions the repo to the new workflow. It must be done AFTER all previous tasks are committed and pushed to main.

**Files:** None (git/GitHub operations only)

- [ ] **Step 1: Push all changes to main**

Run: `git push origin main`

All files from Tasks 1-5 must be on main before creating dev or enabling branch protection.

- [ ] **Step 2: Create and push the dev branch**

Run:
```bash
git checkout -b dev
git push -u origin dev
```

- [ ] **Step 3: Install git hooks locally**

Run: `scripts/install-hooks.sh`
Expected: `commit-msg: installed`

- [ ] **Step 4: Configure branch protection on main**

Run:
```bash
gh api repos/jbrjake/holtz/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["test"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

Note: `enforce_admins: false` allows the repo owner to bypass in emergencies. `required_approving_review_count: 0` requires a PR but no approvals (solo project).

- [ ] **Step 4b: Restrict merge strategy to merge commits only**

Run:
```bash
gh api repos/jbrjake/holtz \
  --method PATCH \
  --field allow_squash_merge=false \
  --field allow_rebase_merge=false \
  --field allow_merge_commit=true
```

This ensures the release action can reliably extract the merge commit body.

- [ ] **Step 5: Verify branch protection**

Run: `gh api repos/jbrjake/holtz/branches/main/protection --jq '.required_status_checks.contexts'`
Expected: `["test"]`

- [ ] **Step 6: Verify the full workflow with a test commit on dev**

Run:
```bash
git checkout dev
echo "test" > /tmp/test-release-workflow.txt
```

Make a test feat commit to verify the hook bumps the version:
```bash
cp /tmp/test-release-workflow.txt test-release-workflow.txt
git add test-release-workflow.txt
git commit -m "feat: verify release workflow"
```

Expected: Hook output `commit-msg: bumped version to 0.5.0 (minor)` on stderr.
Verify: `python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"` outputs `0.5.0`.

Then clean up the test commit:
```bash
git reset --hard HEAD~1
```

- [ ] **Step 7: Confirm dev is the working branch**

Run: `git branch` — should show `* dev`

The repository is now on the new workflow. All future work happens on `dev` or feature branches off `dev`.

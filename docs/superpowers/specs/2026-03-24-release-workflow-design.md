# Release Workflow Design

## Goal

Establish a dev-branch workflow with automatic versioning from conventional commits, PR-based releases to main, and GitHub Action-driven tagging and release notes. The only human intervention is telling Claude Code to cut a release. No new skills, no new dependencies.

## Branch Model

```
feature/foo --> dev --(release PR)--> main --(GH Action)--> tag + GitHub Release
```

- **`main`** is the default branch. What people see on GitHub, what they clone. Contains only released code.
- **`dev`** is the integration branch. All feature branches branch from and merge back to `dev`.
- Feature branch PRs target `dev`.
- Releases merge `dev -> main` via PR. No other path to main.

## Version Source of Truth

`.claude-plugin/plugin.json` field `"version"` is the canonical version. Git tags mirror it but plugin.json is authoritative.

## Automatic Version Bumping

A `commit-msg` git hook fires on every commit:

1. Reads the commit message first line.
2. Parses the conventional commit prefix.
3. Determines bump type:
   - `feat!:`, `fix!:`, or `BREAKING CHANGE` in body -> **major**
   - `feat:`, `feat(scope):` -> **minor**
   - `fix:`, `fix(scope):`, `perf:`, `perf(scope):` -> **patch**
   - `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `style:` (without `!`) -> **no bump**
   - Merge commits (`Merge ...`) -> **no bump**
4. **Guard:** If plugin.json has unstaged changes (`git diff --name-only .claude-plugin/plugin.json` is non-empty), skip auto-bump and emit a message to stderr: `"commit-msg: plugin.json already modified, skipping auto-bump."` This preserves intentional manual version edits.
5. If bump warranted:
   - Reads current version from `.claude-plugin/plugin.json`
   - Calculates new version (cumulative from current, not from last tag)
   - Writes new version to plugin.json using **Python** (`python3 -c "..."`) for reliable cross-platform JSON handling
   - Runs `git add .claude-plugin/plugin.json` to stage it into the commit
6. On any error (malformed version, missing file, python failure), the hook exits 1 with a descriptive message to stderr, aborting the commit.

### Cumulative Versioning Model

Each commit advances from the current version, not from the last tag:

```
0.4.0 + feat: -> 0.5.0
0.5.0 + fix:  -> 0.5.1
0.5.1 + feat: -> 0.6.0
```

This is intentional. Version numbers are cumulative and chronological, reflecting the full sequence of changes on dev.

### Hook Location

The hook script lives tracked at `git-hooks/commit-msg` (separate from the `hooks/` directory, which contains Claude Code plugin hooks). A setup script (`scripts/install-hooks.sh`) symlinks it into `.git/hooks/`.

The install script checks for a pre-existing `.git/hooks/commit-msg`. If one exists and is not a symlink to our hook, it aborts with a message rather than overwriting.

### Note on Merge Commits

The `commit-msg` hook only runs on local git operations. Merge commits created by GitHub (via `gh pr merge`) do not trigger the hook. This is correct behavior — release merge commits use the `chore:` prefix and should not bump the version.

## CI

Updated `.github/workflows/ci.yml`:

```yaml
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
```

Same jobs as today: lint, type check, test.

## Branch Protection on `main`

Configured once via `gh` CLI:

- Require PR for all changes (no direct pushes)
- Require the `test` status check to pass (must match `jobs.test` in ci.yml — renaming the CI job requires updating this rule)
- Require branch to be up to date before merging
- Merge strategy: merge commit only (not squash or rebase) — required for merge commit body extraction in the release action
- No force pushes
- No branch deletion

## Release Workflow

When told to cut a release, Claude Code:

1. Inspects `git log dev --not main --oneline` for commits since last release.
2. Reads the version from plugin.json on dev (already bumped cumulatively).
3. Generates a release summary with highlights (user-facing value) and a commit list.
4. Creates PR: `gh pr create --base main --head dev --title "chore: release v0.6.0" --body "<summary>"`
5. Waits for CI to pass (all green or bust — branch protection enforces this).
6. Merges: `gh pr merge <number> --merge --subject "chore: release v0.6.0" --body "<summary>"`

The `--merge` flag creates a merge commit. The `--subject` and `--body` flags set the merge commit message, ensuring the Claude-generated summary is in the merge commit body for the release action to extract.

## GitHub Action: Release on Merge

New `.github/workflows/release.yml`:

1. **Trigger:** `on: push: branches: [main]`
2. **Read version** from `.claude-plugin/plugin.json` using `python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"`.
3. **Check if tag exists** (idempotency — skip if tag already present).
4. **Extract merge commit body:**
   ```bash
   BODY=$(git log -1 --format=%b HEAD)
   ```
   This returns everything after the first line (subject) and blank separator. Safe because the merge strategy is locked to merge commits via branch protection.
5. **Create tag + GitHub Release:**
   - Tag: `vX.Y.Z`
   - Title: `vX.Y.Z`
   - Body: the merge commit body (Claude's summary) only — no `--generate-notes`, to avoid duplicating the commit list that Claude already curated.

## Bootstrap Procedure

One-time setup, in this order:

1. Update `ci.yml` on main to include `dev` in triggers (must land on main first so CI works on dev from the start).
2. Create `dev` branch from main: `git checkout -b dev && git push -u origin dev`.
3. Install git hooks locally: `scripts/install-hooks.sh`.
4. Configure branch protection on main via `gh` CLI.
5. Add CLAUDE.md with workflow documentation.

This ordering prevents the deadlock where branch protection requires CI but CI hasn't been configured for the new branch yet.

## Files Changed / Created

| File | Action | Purpose |
|------|--------|---------|
| `git-hooks/commit-msg` | Create | Shell script that auto-bumps plugin.json |
| `scripts/install-hooks.sh` | Create | Symlinks git-hooks into .git/hooks/ |
| `.github/workflows/release.yml` | Create | Tags + creates GitHub Release on push to main |
| `.github/workflows/ci.yml` | Modify | Add dev branch to triggers |
| `CLAUDE.md` | Create/modify | Document branch workflow and release process |

## Not Included (Intentionally)

- No changelog file (GitHub Release notes serve this purpose)
- No new skills or plugins
- No pre-commit framework
- No third-party versioning tools (no release-please, no bump2version)

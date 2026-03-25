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

A `post-commit` git hook automatically bumps `.claude-plugin/plugin.json` version on feat/fix/perf commits and amends the commit to include the change. No manual version management needed.

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

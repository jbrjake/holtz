# Holtz — Development Guide

## Before claiming anything works

**Do not report success, "in-flight," "should pass," "likely fixed," or
any future-tense verification claim without observed evidence.**

Banned phrases when reporting status:
- "should work" / "should pass" / "should fix it" / "likely passes"
- "CI runs in-flight" (as a stand-in for "I don't know, but probably OK")
- "good to go" / "ready to push" before gates ran
- "I think this is fixed" without pasted output

A claim of "CI passed" must be backed by `gh run view <id>` showing
`conclusion=success`. A claim of "tests pass" must be backed by an
observed `pytest` exit 0. A claim of "no type errors" must be backed
by an observed `mypy` exit 0. Assertion without evidence is the
violation — not just inaccurate prediction.

The local gate *is* the CI gate. `git-hooks/pre-commit` runs the fast
CI subset; `git-hooks/pre-push` runs the full CI-equivalent for
pushes to `main` or `dev`. If you've bypassed a hook with
`--no-verify`, say so explicitly.

## Don't run the plugin against itself

`scripts/install-hooks.sh` defaults to **dev mode**: it installs git
hooks and the sahjhan binary but does NOT wire the plugin's
`PreToolUse`/`PostToolUse` hooks into this repo's Claude Code session.
Running the plugin against its own development repo creates circular
blocks — the hooks protect `enforcement/`, but dev work edits
`enforcement/`.

To simulate a downstream consumer (e.g. verify the hooks still block
what they should), run:

```bash
scripts/install-hooks.sh --simulate-downstream
```

To return to dev mode after simulating:

```bash
scripts/install-hooks.sh --no-simulate-downstream
```

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

**Note:** Plugin-vended markdown files (SKILL.md, references/, agents/, patterns/) are functional deliverables, not documentation. Changes to these files are `feat:` or `fix:`, not `docs:`. Reserve `docs:` for README, CHANGELOG, CONTRIBUTING, and other non-plugin files.

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
4. Run pre-release checks: `scripts/pre-release-check.sh`
   (runs ruff, mypy, contract gate, schema freshness, full test suite with 80% coverage gate, hook smoke test, and version bump check — one command, impossible to skip steps)
5. Generate changelog: `python scripts/generate-changelog.py --write`
   (preview without `--write` first). Review the output in CHANGELOG.md, commit it.
6. Create a release PR:
   ```
   gh pr create --base main --head dev \
     --title "chore: release vX.Y.Z" \
     --body "<highlights and commit summary>"
   ```
7. Wait for CI to pass on the PR.
8. Merge: `gh pr merge <number> --merge --subject "chore: release vX.Y.Z" --body "<summary>"`
9. The release GitHub Action automatically creates the git tag and GitHub Release.

## Running Tests

Quick (subagents, iterative work):
```bash
python -m pytest
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/ scripts/ enforcement/scripts/
```

Full (main agent, pre-commit, CI — includes coverage gate):
```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks --cov-report=term-missing --cov-fail-under=80
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/ scripts/ enforcement/scripts/
```

Coverage is excluded from default addopts because concurrent pytest processes (subagents, parallel sessions) deadlock on the SQLite `.coverage` file. Only the main agent should run with `--cov`.

Subprocess coverage: hooks are tested via subprocess (the correct approach — it tests the interface Claude Code actually uses). Coverage for these subprocess-invoked hooks is collected via `parallel = true` in `[tool.coverage.run]` and `COVERAGE_PROCESS_START` set in `conftest.py`. Never lower coverage thresholds — if coverage is low, fix the measurement or the code.

Targeted test commands:
```bash
# After skill file changes:
pytest -m contract
python scripts/contract_gate.py

# After hook changes:
pytest -m hook_e2e

# Fast feedback (subagents):
pytest -m "not slow and not machine_specific"
```

## Testing Methodology

**Test categories:**

| Category | When to Write | Marker | Example |
|----------|--------------|--------|---------|
| Contract | Skill file or hook command parsing changed | `@pytest.mark.contract` | Skill says `sahjhan status 2>&1`, test verifies hook allows it |
| Hook E2E | Any enforcement/hooks/ change | `@pytest.mark.hook_e2e` | Hook subprocess receives JSON event, returns correct decision |
| Unit | New utility function or parser | (none) | `_extract_sahjhan_subcmd` returns correct tuple |
| Integration | Hook chain or cross-module behavior | `@pytest.mark.integration` | Full PreToolUse chain for a real command |

**Rules:**

1. Skill file changed → update contract tests in same commit. Run `python scripts/contract_gate.py` to verify.
2. Hook changed → test via subprocess (`_run_hook(event)`), not function import. Subprocess tests the interface Claude Code actually uses.
3. New shell idiom in a skill file → add it to the combinatorial matrix in `test_contract_commands.py` (`_SHELL_IDIOMS`, `_SHELL_WRAPPER_IDIOMS`, or `_SHELL_CHAIN_IDIOMS`). Parametrized tests auto-combine it with all subcommands.
4. Coverage is necessary but not sufficient. 100% coverage with synthetic inputs is worse than 80% coverage with real inputs. Prefer testing real commands from skill files over hand-crafted examples.

## Branch Protection (recommended)

For `main` branch:
- Require status checks: CI must pass
- Require up-to-date branches before merging
- No direct pushes (all changes via PR from dev)
- No force pushes

For `dev` branch:
- Require status checks: CI must pass
- Allow direct pushes (for iterative development)

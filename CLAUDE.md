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

`git-hooks/pre-commit` runs the fast CI subset (ruff + mypy + fast
pytest + contract gate) so trivial regressions fail locally in
seconds instead of in CI minutes later. `git-hooks/pre-push` runs
the same fast subset again — CI handles the full test suite on dev
pushes, and main is PR-only so release-gate checks happen on the
release PR, not on push. If you've bypassed a hook with
`--no-verify`, say so explicitly when reporting status.

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

Full (main agent, release, CI — includes coverage gate):
```bash
python -m pytest --cov=skills/holtz/scripts --cov=hooks --cov=enforcement/hooks --cov-report=term-missing --cov-fail-under=80
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/ scripts/ enforcement/scripts/
```

**The full suite runs once, at the end — RULED (Jon, 2026-09-08).** It is a release gate, not a commit gate. Per-unit evidence is the fast subset, the targeted `slow`/`integration` files for what the change touched, and the gates (ruff, mypy, contract gate, `enforcement_lint`, `sahjhan lint`, `enforcement_contract --check`); commit on that, and say in the message that the full suite has not run. The full run takes about 25 minutes, longer than the Bash cap: run it in the background, never edit the tree while it runs, and read its last line — `-q` is in `addopts` and drops test names, not the `N passed` summary — then confirm `grep -cE "^(FAILED|ERROR)"` is 0. A partial `.....` line is not a result.

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
5. **Subagent behavior is enforcement, not just prose.** Claude Code fires PreToolUse/PostToolUse hooks for subagent tool calls too and adds an `agent_id` field. The enforcement hooks are **agent-agnostic by design** — a fix subagent is under the same TDD gate as the orchestrator (see `references/phase-fix-loop.md`). So: (a) never exempt `agent_id`-bearing calls from a gate without a `hook_e2e` test proving the new behavior is intended (see `TestPreToolHookSubagentTddParity`); and (b) if a skill file changes what a subagent may do, add/adjust that hook_e2e test **and** the doc-consistency test (`test_subagent_contract_consistency.py`) in the same commit. A skill claim about subagent permissions that no test enforces is how `800624f` shipped a contradictory, unenforced contract.

## Standing traps

Each of these has cost a session.

**Process**
- **Read the filing before asking.** `gh issue view` the filing and re-read the plan item before putting a design question to Jon; if the record answers it, build it.

**Commits**
- **Stage by path, never `git add -A`.** The tree carries untracked-by-design plan docs and vendored sahjhan binaries of 100–140 MB each. One bad path makes `git add` stage nothing, so read column 1 of `git status --short` before committing.
- **`git commit` prints two `[dev …]` hashes and one is orphaned** — `post-commit` amends, and which one survives varies. Take the hash from `git log -1 --format=%H`, and confirm one with `git merge-base --is-ancestor <hash> HEAD`, never `git cat-file`.
- **`git commit` can outlive the 2-minute Bash default** — `pre-commit` runs the fast subset. Pass an explicit timeout; a killed commit leaves everything staged and looks like a hook failure.
- **The README test badge is a gated derived number.** Bump it in the same commit that adds tests, before the run you intend to cite; `passed + skipped` equals the badge.
- **A test that is RED while its ruling is pending cannot sit in the tree across a commit** — `pre-commit` runs the working tree, not the index. `git stash push -- <that file>`, commit, pop.
- **Pushing:** SSH to `origin` is refused from this machine's sessions (`Permission denied (publickey)`). Push over HTTPS with gh as the credential helper: `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push https://github.com/jbrjake/holtz.git dev:dev`.

**Testing**
- **Run every new test RED against the unmodified tree first**, and read the reason, not the colour. Unchanged-behaviour tests must be green before, during the non-vacuity mutation, and after.
- **A whole-fix stash is usually not that control.** If the test module imports the function the fix adds, the unmodified tree fails at collection — one `ERROR`, zero `FAILED`, every assertion skipped. Use a targeted single-line mutation per claim and read which tests go red; a mutation that takes down a test you did not predict is a finding.
- **Undo a mutation with a reverse Edit when the file carries other changes** — `git checkout -- <file>` also discards that file's uncommitted work.
- **A green run after a change is not evidence when the failure is load-flaky.** Re-run the unmodified tree under the same conditions in the same sitting. The hook tests that flake under concurrent pytest (`TestPrimer`, `TestPrimerWithMockBinary`, `TestProtocolTrackerDaemonTeardown`, `test_source_write_allowed_once_gate_satisfied`) fail on a clean tree too: retry the commit, and do not `--no-verify` or bisect against them.

**Enforcement and the daemon**
- **Editing a daemon-calling hook silently disables enforcement** until `bash scripts/hash-trusted-callers.sh` reruns, and only `real_daemon` tests catch it. It does not present as an authentication failure: a refused write can leave the cache uncreated, so the test sees an empty state line, which reads like a broken trigger. Before debugging a `real_daemon` test that suddenly sees no state, rerun the manifest.
- **A real daemon refuses `enforcement_write` from a test process** (`auth_failed` / `pid_resolution_failed`), so no test can write a `restricted` event. Assert gates that depend on one by what they read; `tests/test_fix_commit_caller_anchor.py` is the pattern, including deriving a probe config from `enforcement/` at test time rather than pasting a copy that cannot drift-fail.
- **`gate check <transition>` without its arguments reports parameterised gates as `? unevaluable`, not as passing** — the line is there and carries no ✗. Bind them (`gate check "set complete perspective" current_perspective=security`); `_Run.gate_check` in `tests/test_amplification_breaker.py` forwards `key=value` args.
- **A transition's `state_transition` row lands below the events it emits**, with a `gate_attestation` between them. A window anchored on "the last `state_transition`" is moved by the very transitions whose emits it bounds. Before writing `seq > MAX(state_transition)`, ask which transitions emit into the set you are windowing.
- **`sahjhan query --format json` spells an absent optional column `"NULL"`** — the four-character string, not `null` or `""` — and a pattern-constrained field refuses it on the way back in. Use `_optional()` in `enforcement/scripts/merge_punchlists.py`.

**The sahjhan pin**
- `SAHJHAN_VERSION` in `enforcement/hooks/_resolve.py` governs; the marker and binary self-heal to it. Move it with `scripts/update_sahjhan_pin.py`. `scripts/check_sahjhan_pin.py` exiting 0 says the places agree, not that they agree on the version you want — check `bin/sahjhan --version` itself.
- sahjhan 0.28.0 and later reserve the ledger entry's own column names — `recorded_by`, `seq`, `ts`, `type`, `hash`, `prev`, `schema`, `engine`, `protocol`. A config declaring a field with one fails validation.

## Branch Protection (recommended)

For `main` branch:
- Require status checks: CI must pass
- Require up-to-date branches before merging
- No direct pushes (all changes via PR from dev)
- No force pushes

For `dev` branch:
- Require status checks: CI must pass
- Allow direct pushes (for iterative development)

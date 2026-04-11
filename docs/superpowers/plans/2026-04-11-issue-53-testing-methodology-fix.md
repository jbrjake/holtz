# Issue #53: Testing Methodology Root Cause & Fix Plan

## Problem Statement

Third consecutive broken release. The test suite has 1197 tests covering
code paths, schema validation, bypass vectors, and hook chain invocation.
Yet obvious bugs — `--help` blocking, redirect fragment parsing, missing
`sahjhan init` in the initialization sequence — shipped to users.

## Root Cause: Tests Verify Code, Not Contract

Every bootstrap hook test uses sanitized, artificial commands:
- `"sahjhan status"` — no redirects, no flags
- `"sahjhan reset --confirm"` — no shell operators
- `"sahjhan --config-dir /path status"` — only `_VALUE_FLAGS` flags tested

No test uses commands from `phase-recon.md` — the actual contract the agent
follows. The commands the agent runs are:
```bash
sahjhan init                                              # never tested
nohup sahjhan daemon start > /dev/null 2>&1 &             # tested once, passed by accident
sahjhan ledger create --from run 1 --activate             # not tested through hook
sahjhan transition run_start                              # not tested through hook
sahjhan status 2>&1                                       # not tested (the redirect that broke)
sahjhan --help                                            # not tested (blocked by hook)
```

The testing methodology is: "read the code, test the code paths." The
missing methodology is: "read the skill, test the skill's commands."

## Three Broken Releases — Same Failure Class

| Release | Bug | Category |
|---------|-----|----------|
| v0.127.5 | Hook schema wrong, broke on first invocation | Contract mismatch: tested against wrong schema |
| v0.131.x | Content truncation in pattern_brief, lens parser crash | Contract mismatch: tested parsing logic, not real input |
| v0.131.5 | --help blocked, redirect fragment parsing, missing init | Contract mismatch: tested clean commands, not real commands |

All three are the same bug: **the tests exercise the implementation but
not the interface the user actually encounters.**

## Fix Plan

### 1. Contract Test Suite (new file: `tests/test_contract_commands.py`)

A test file that ONLY contains commands extracted from skill files. Every
command in `phase-recon.md`, `SKILL.md`, and other reference docs that
the agent is told to run gets a test verifying the bootstrap hook allows it.

**Methodology:**
- `grep` all fenced code blocks from skill/reference files
- Extract every `sahjhan` command
- Each becomes a test case: `_run_hook(event) → allow`
- Each blocked command from the skill's "do not run" list → `deny`

**Maintenance rule:** When a skill file is changed, the contract test
file must be updated in the same commit. A CI check can enforce this
(changed `*.md` in `skills/` or `references/` → require
`test_contract_commands.py` to be in the diff, or a `[skip-contract]`
commit tag).

### 2. Shell Idiom Fuzzing (addition to `TestExtractSahjhanSubcmd`)

Parameterized tests that combine every allowed subcommand with every
common shell idiom:
- `2>&1`, `2>/dev/null`, `>/tmp/log`, `1>&2`, `&>/dev/null`
- `--help`, `-h`, `--version`
- Trailing `&`, `; echo done`, `| cat`
- `nohup ... &`

This is a combinatorial expansion: `N_subcmds × N_idioms` tests. Ensures
that adding a new subcommand to the allowlist automatically tests it with
all shell patterns.

### 3. First-Run Smoke Test

A test that simulates the complete first-run initialization sequence:
1. Fresh temp directory (no `.sahjhan/`)
2. Run every command from phase-recon.md Step 0 through the hook
3. Verify each is allowed
4. Verify the sequence makes semantic sense (init before daemon, etc.)

### 4. Pre-Release Contract Gate

Before any release, a CI step (or manual pre-release check) that:
1. Extracts all sahjhan commands from `skills/**/*.md` and `references/**/*.md`
2. Runs each through the bootstrap hook
3. Fails if any allowed command is blocked
4. Fails if any blocked command is allowed

This catches drift between skill instructions and hook enforcement even
if someone forgets to update `test_contract_commands.py`.

### 5. Error Message Validation

Every deny test should assert the error message is coherent:
- No redirect fragments in the message (`'sahjhan 2'`)
- The blocked subcommand matches what was actually typed
- The message includes useful guidance (allowed subcommands list)

## Priority

1. Contract test suite — blocks this release
2. Shell idiom fuzzing — blocks this release
3. First-run smoke test — blocks this release
4. Pre-release contract gate — implement before next release
5. Error message validation — implement before next release

## Success Criterion

A release can only ship when:
1. Every command in the skill files passes through the hook
2. Every command + shell idiom combination passes
3. The first-run initialization sequence works end-to-end
4. No error message contains parse artifacts

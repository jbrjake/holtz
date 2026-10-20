# Testing Methodology Overhaul

## The Problem Beyond Issue #53

Issue #53's plan fixed the immediate symptom: contract tests for skill
commands. But three consecutive broken releases don't come from one missing
test file. They come from a system that rewards green CI over actual
correctness. This plan addresses the structural, architectural, and
process-level reasons that broken code ships.

## Diagnosis: Why 1368 Tests and 97% Coverage Failed

### 1. Coverage Measures Effort, Not Effectiveness

97% line coverage means 97% of lines execute during tests. It says nothing
about whether the tests assert the right things, use realistic inputs, or
exercise the actual interface users encounter.

The three broken releases all had 97% coverage. Coverage didn't drop because
the tests exercised the code — they just exercised it with the wrong inputs.
`sahjhan status` was tested. `sahjhan status 2>&1` was not. Same line of code,
100% covered, completely broken in production.

**Concrete number:** Before the contract test fix, zero of the ~40 sahjhan
commands in skill files appeared in any test. The code paths were covered.
The contract was not.

### 2. Tests Verify Implementation, Not Interface

Almost every test in the suite follows this pattern:
1. Import a function
2. Call it with a hand-crafted synthetic input
3. Assert the output matches expectations

This tests "does the code do what I think it does." It doesn't test "does the
code handle what users actually send it."

The skill files are the interface contract. The shell is the execution
environment. Neither was represented in tests until issue #53.

### 3. The Daemon Is a Testability Barrier

The sahjhan daemon holds enforcement state in memory, serves it over a Unix
socket, and signs events with an HMAC key that exists only in daemon memory.
This design is correct for security (no secrets on disk), but it makes testing
hard:

- Hooks that query the daemon need either a real daemon or a mock
- The mock daemon (`conftest.py:mock_daemon`) is 50 lines. The real daemon is
  a compiled binary. The mock cannot faithfully reproduce the real daemon's
  behavior under edge cases (timeouts, socket failures, PID reuse).
- Most tests sidestep the daemon entirely by testing functions in isolation
- Result: the daemon interaction layer is the least-tested and most
  failure-prone part of the system

### 4. CI Gates Are Necessary But Not Sufficient

CI runs: pytest (60% coverage gate), ruff, mypy. That's it.

Two critical gates run only at release time, manually:
- `scripts/smoke-test-hooks.sh` — verifies hooks against live Claude Code
- `test_hook_schema_freshness.py` — verifies schema against live docs

If someone forgets to run these (or the schema changes between the last
release and now), broken hooks ship. This happened.

### 5. CLAUDE.md Tells Agents WHAT To Run, Not HOW To Test

The testing section of CLAUDE.md is:
```
python -m pytest
ruff check .
mypy --explicit-package-bases skills/holtz/scripts/ hooks/ enforcement/hooks/
```

No guidance on:
- What makes a good test (contract vs. unit vs. integration)
- When to write a contract test vs. a unit test
- How to test hooks (subprocess invocation, not function import)
- How to test against skill file commands
- What the `contract_gate.py` script is and when to run it

An agent following CLAUDE.md can add a hook, write unit tests that import the
function, get 100% coverage, pass CI, and ship code that breaks on real input.
That's exactly what happened three times.

### 6. No Test Categories or Fast/Slow Separation

All 1368 tests run in one undifferentiated batch. There's one marker
(`machine_specific`) and no separation between:
- Fast unit tests (< 1ms each, no subprocess)
- Integration tests (subprocess invocation, ~50ms each)
- Contract tests (skill-file-derived, ~50ms each)
- Schema tests (network-dependent, seconds each)

This means:
- Subagents run ALL tests when they only need fast feedback
- No way to say "run only contract tests" after changing a skill file
- No way to say "run only hook E2E tests" after changing a hook

---

## The Plan

### Phase 1: Testing Documentation (Unblocks Everything Else)

**Goal:** Future agents (and humans) know HOW to test, not just what commands
to run.

#### 1a. Add Testing Methodology Section to CLAUDE.md

Add after the "Running Tests" section:

```markdown
## Testing Philosophy

Tests must verify the CONTRACT (what users encounter), not just the CODE
(what developers wrote). Three broken releases shipped because tests used
synthetic inputs that didn't match real commands from skill files.

### Test Categories

| Category | When to Write | How to Run | Example |
|----------|--------------|------------|---------|
| Contract | Any change to skill files, references, or hook command parsing | `pytest tests/test_contract_commands.py` | Skill says `sahjhan status 2>&1`, test verifies hook allows it |
| Unit | New utility function or parser | `pytest tests/test_<module>.py` | `_extract_sahjhan_subcmd` returns correct tuple |
| Hook E2E | Any change to enforcement/hooks/ | `pytest tests/test_bootstrap_read_guard.py tests/test_protocol_enforcement.py tests/test_e2e_hook_invocation.py` | Hook subprocess receives JSON event, returns correct decision |
| Contract Gate | Before any release | `python scripts/contract_gate.py` | Extracts commands from ALL skill files, runs each through hook |

### Rules

1. **Skill file changed? Update contract tests.** If you add/change a
   `sahjhan` command in any `.md` file under `skills/` or `references/`,
   the corresponding test in `test_contract_commands.py` must be updated
   in the same commit. Run `python scripts/contract_gate.py` to verify.

2. **Hook changed? Test via subprocess, not import.** Hook tests must use
   `_run_hook(event)` (subprocess invocation), not direct function calls.
   Direct imports test the function; subprocess tests the actual interface
   Claude Code uses.

3. **New shell idiom? Add to the combinatorial matrix.** If a skill file
   uses a new shell pattern (new redirect syntax, new wrapper), add it to
   `_SHELL_IDIOMS`, `_SHELL_WRAPPER_IDIOMS`, or `_SHELL_CHAIN_IDIOMS` in
   `test_contract_commands.py`. The parametrized tests automatically
   combine it with all subcommands.

4. **Coverage is necessary but not sufficient.** 100% coverage with
   synthetic inputs is worse than 80% coverage with real inputs. Prefer
   testing real commands from skill files over hand-crafted minimal
   examples.
```

#### 1b. Add Test Markers to pyproject.toml

```toml
markers = [
    "machine_specific: tests that depend on local file paths",
    "contract: tests derived from skill file commands",
    "hook_e2e: tests that invoke hooks via subprocess",
    "slow: tests that take >1s (network, large fixtures)",
]
```

Then mark existing tests accordingly. This enables:
```bash
pytest -m contract          # after skill file changes
pytest -m hook_e2e          # after hook changes  
pytest -m "not slow"        # fast feedback loop
```

#### 1c. Update Release Checklist in CLAUDE.md

Add `python scripts/contract_gate.py` as a required pre-release step,
between the smoke test and the schema freshness check.

---

### Phase 2: CI Pipeline Hardening

**Goal:** CI catches what broke the last 3 releases, not just coverage
thresholds.

#### 2a. Add Contract Gate to CI

The `contract_gate.py` script (just implemented) doesn't require network
access or a live daemon. It should run in CI alongside pytest:

```yaml
- name: Contract gate
  run: python scripts/contract_gate.py
```

This catches skill/hook drift on every PR, not just at release time.

#### 2b. Add Skill-File Change Detection

A CI step that checks: if any `.md` file under `skills/` or `references/`
changed, require `test_contract_commands.py` to also be in the diff (or a
`[skip-contract]` tag in the commit message). This is the maintenance rule
from the issue #53 plan.

Implementation: a small shell script in CI:
```bash
#!/bin/bash
# scripts/check_contract_test_sync.sh
SKILL_CHANGED=$(git diff --name-only HEAD~1 | grep -c 'skills/.*\.md\|references/.*\.md')
CONTRACT_CHANGED=$(git diff --name-only HEAD~1 | grep -c 'test_contract_commands.py')
SKIP_TAG=$(git log -1 --pretty=%B | grep -c '\[skip-contract\]')

if [ "$SKILL_CHANGED" -gt 0 ] && [ "$CONTRACT_CHANGED" -eq 0 ] && [ "$SKIP_TAG" -eq 0 ]; then
    echo "FAIL: Skill files changed but test_contract_commands.py was not updated."
    echo "Either update contract tests or add [skip-contract] to commit message."
    exit 1
fi
```

#### 2c. Raise Coverage Gate

60% is too low for a security-critical enforcement system. Raise to 80% now,
with a plan to reach 90% over the next 2-3 releases. The current coverage is
already 97%, so this gate just prevents regression.

#### 2d. Add Hook Schema Validation to CI (Without Network)

`test_hook_schema_freshness.py` requires network access (fetches live docs).
Create a LOCAL schema validation test that checks hook output against a
checked-in schema snapshot. Update the snapshot periodically. This way CI
catches schema drift even without network access.

---

### Phase 3: Architectural Testability Improvements

**Goal:** Make it structurally easier to write good tests.

#### 3a. Daemon Test Harness

The `mock_daemon` fixture in conftest.py is minimal. Build a richer test
harness that:

- Accepts a state configuration (protocol state, cache contents, active
  ledger)
- Responds to socket queries with realistic payloads
- Can simulate failure modes (timeout, connection refused, corrupt response)
- Can simulate PID lifecycle (alive -> dead -> PID reused)

This doesn't replace the real daemon for smoke tests, but it makes it
possible to test hook behavior under failure conditions that are hard to
reproduce with the real daemon.

#### 3b. Test Fixtures from Real Data

The `runner_fixtures.py` file contains fake pytest output for "the cheese
shop" test suite. Replace with captured output from real pytest/ruff/mypy
runs against actual Python projects. This prevents the "tests parse what
we think output looks like, not what it actually looks like" failure mode.

Approach: a `scripts/capture_test_fixtures.sh` that runs the test suite
against itself and captures stdout/stderr into `tests/fixtures/`. These
captured outputs become the ground truth for parser tests.

#### 3c. Extract Hook Protocol Into a Testable Interface

Currently each hook implements its own JSON parsing, decision output, and
subprocess invocation of sahjhan. Extract the common patterns into a shared
module with a clear interface:

```python
# enforcement/hooks/_protocol.py
class HookDecision:
    """Structured hook decision with validation."""
    
    def __init__(self, decision: str, reason: str = ""):
        assert decision in ("allow", "deny"), f"Invalid decision: {decision}"
        self.decision = decision
        self.reason = reason
    
    def to_json(self) -> str:
        """Emit Claude Code-compatible JSON."""
        ...
```

This makes it impossible to emit an invalid decision (the "perhaps" or
`null` problem). The interface itself becomes the test surface.

NOTE: This is the most invasive change and should be evaluated carefully.
The current hook code is simple and direct. An abstraction layer adds
indirection. The tradeoff is: slightly more complexity in exchange for a
guaranteed-correct output format. Worth doing only if invalid output format
has actually caused bugs (check release history).

#### 3d. Separate Fast and Slow Tests

Configure pytest to support running subsets:

```toml
[tool.pytest.ini_options]
markers = [
    "contract: skill-file-derived contract tests",
    "hook_e2e: subprocess hook invocation tests",
    "slow: tests taking >1s",
    "machine_specific: local path dependent",
]
```

Subagents should run `pytest -m "not slow and not machine_specific"` for fast
feedback. The full suite runs in CI and before releases.

---

### Phase 4: Test Suite Substance Improvements

**Goal:** The tests that exist are more effective, not just more numerous.

#### 4a. Property-Based Testing for Parsers

hypothesis is already in the project dependencies. Use it for:

- `_extract_sahjhan_subcmd`: generate arbitrary shell command strings, verify
  the parser never crashes (even if it returns wrong results). This catches
  regex catastrophic backtracking and edge cases.
- `_check_bash_write`: generate arbitrary paths and command patterns, verify
  the write guard never allows writes to protected paths.
- Punchlist parser: generate arbitrary markdown, verify the parser either
  produces a valid result or raises a clean error (never silently corrupts).

Property-based tests don't replace contract tests (which verify specific
real-world commands). They supplement them by exploring the input space
systematically.

#### 4b. Hook Chain Integration Tests

Current tests invoke hooks individually. In production, hooks chain:
`_daemon_lifecycle` -> `_sahjhan_bootstrap` -> `pre_tool_hook` -> (tool runs)
-> `post_tool_hook` -> `bash_guard` -> `protocol_tracker`.

Write tests that simulate a full chain: construct a realistic event, pass it
through each hook in sequence, verify the final decision and all side effects
(cache writes, event recordings, etc.).

Start with the critical path: a Bash event containing `sahjhan transition
run_start` going through the full PreToolUse chain. Then expand to PostToolUse
and Stop chains.

#### 4c. Failure Mode Tests

The agent audit found these untested failure modes across hooks:

| Failure | Hooks Affected | Current Behavior | Test Status |
|---------|---------------|-----------------|-------------|
| Socket timeout during event recording | lens_quiz, primer | Event silently dropped | Untested |
| PID reuse (daemon PID recycled by OS) | daemon_lifecycle, stop_hook, primer | False "alive" | Untested |
| Base64 corruption in vault | lens_quiz | Hook crashes | Untested |
| status-cache.json stale/corrupt | stop_hook | Falls back, may use stale data | Untested |
| `sahjhan status` subprocess timeout | protocol_tracker, primer | Returns stale cache | Untested |
| Concurrent cache read/write | protocol_tracker, commit_gate | Race condition | Untested |

Each of these is a test case. Most can be tested by extending the daemon test
harness (Phase 3a) to simulate the failure, then verifying the hook degrades
correctly.

#### 4d. Error Message Quality Tests

Expand the `TestDenyMessageQuality` pattern to ALL hooks that produce user-
facing messages. Every deny message should:
- Name the blocked action specifically
- Not contain parse artifacts (redirect fragments, token indices)
- Suggest a corrective action or list allowed alternatives
- Be readable by an LLM agent (the primary consumer of these messages)

---

### Phase 5: Process Changes

**Goal:** The release process structurally prevents broken releases.

#### 5a. Pre-Release Gate Script

Consolidate all pre-release checks into a single script:

```bash
#!/bin/bash
# scripts/pre-release-check.sh
set -euo pipefail

echo "=== Contract Gate ==="
python scripts/contract_gate.py

echo "=== Hook Smoke Test ==="
scripts/smoke-test-hooks.sh --verbose

echo "=== Schema Freshness ==="
python -m pytest tests/test_hook_schema_freshness.py -v

echo "=== Full Test Suite ==="
python -m pytest --cov=... --cov-fail-under=80

echo "=== All pre-release checks passed ==="
```

This replaces the multi-step manual checklist in CLAUDE.md with a single
command that either passes or fails. Harder to skip steps.

#### 5b. Branch Protection

If not already configured, add GitHub branch protection rules for `main`:
- Require CI to pass
- Require at least the contract gate CI step
- No direct pushes

This makes it impossible to merge to main with broken contract tests.

---

## Priority and Dependencies

```
Phase 1 (docs) ──────── no dependencies, do first
  ├── 1a: CLAUDE.md testing section
  ├── 1b: pytest markers
  └── 1c: release checklist update

Phase 2 (CI) ────────── depends on 1b (markers) and contract_gate.py (done)
  ├── 2a: contract gate in CI
  ├── 2b: skill-change detection
  ├── 2c: raise coverage gate
  └── 2d: local schema validation

Phase 3 (architecture) ─ independent, can parallelize with Phase 2
  ├── 3a: daemon test harness
  ├── 3b: real data fixtures
  ├── 3c: hook protocol interface (evaluate carefully)
  └── 3d: fast/slow test separation (depends on 1b)

Phase 4 (substance) ──── depends on 3a (daemon harness) for failure tests
  ├── 4a: property-based testing
  ├── 4b: hook chain integration
  ├── 4c: failure mode tests
  └── 4d: error message quality

Phase 5 (process) ────── depends on 2a (CI contract gate)
  ├── 5a: pre-release gate script
  └── 5b: branch protection
```

## What NOT To Do

- **Don't chase 100% coverage.** The problem was never coverage percentage.
  Going from 97% to 100% adds tests for error handling paths that rarely
  execute. The ROI is in contract tests and failure mode tests, not line
  coverage.

- **Don't add test infrastructure before tests.** Phase 3 improves
  testability, but the most valuable tests (contract tests, failure mode
  tests) can be written today with the existing infrastructure. Don't let
  "we should build a better harness first" delay writing the tests that would
  have caught the last three broken releases.

- **Don't test the daemon itself.** The daemon is a compiled binary. Testing
  it requires running it. The hooks' behavior when the daemon is unavailable,
  slow, or returning errors is what needs testing — not the daemon's internal
  correctness.

- **Don't centralize all tests into one file.** `test_contract_commands.py`
  is the right place for contract tests. Hook E2E tests belong in their
  respective files. Don't create a monolithic "test_everything.py".

## Success Criteria

After this plan is executed:

1. A skill file change that breaks a hook is caught by CI (not release).
2. Every shell idiom in skill files is tested combinatorially.
3. Hook failure modes (daemon death, socket timeout, PID reuse) have tests.
4. CLAUDE.md tells agents HOW to write tests, not just how to run them.
5. The release process is a single script, not a multi-step checklist.
6. An agent that has never seen this codebase can read CLAUDE.md and write
   a correct contract test for a new hook command.

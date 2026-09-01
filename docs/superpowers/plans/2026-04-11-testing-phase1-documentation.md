# Phase 1: Testing Documentation

## Context

Part of the testing methodology overhaul. Three broken releases shipped
because agents know what commands to run but not how to write effective tests.
CLAUDE.md says `python -m pytest` and nothing else. This phase adds the
missing guidance so every future session has the methodology built in.

Depends on: nothing (do first).
Enables: all other phases.

## Tasks

### 1. Add Testing Methodology Section to CLAUDE.md

After the existing "Running Tests" section, add a new "Testing Methodology"
section. The content should cover:

**Test categories table:**

| Category | When to Write | Marker | Example |
|----------|--------------|--------|---------|
| Contract | Skill file or hook command parsing changed | `@pytest.mark.contract` | Skill says `sahjhan status 2>&1`, test verifies hook allows it |
| Hook E2E | Any enforcement/hooks/ change | `@pytest.mark.hook_e2e` | Hook subprocess receives JSON event, returns correct decision |
| Unit | New utility function or parser | (none) | `_extract_sahjhan_subcmd` returns correct tuple |
| Integration | Hook chain or cross-module behavior | `@pytest.mark.integration` | Full PreToolUse chain for a real command |

**Four rules:**
1. Skill file changed → update contract tests in same commit. Run
   `python scripts/contract_gate.py` to verify.
2. Hook changed → test via subprocess (`_run_hook(event)`), not function
   import. Subprocess tests the interface Claude Code actually uses.
3. New shell idiom in a skill file → add it to the combinatorial matrix in
   `test_contract_commands.py` (`_SHELL_IDIOMS`, `_SHELL_WRAPPER_IDIOMS`,
   or `_SHELL_CHAIN_IDIOMS`). Parametrized tests auto-combine it with all
   subcommands.
4. Coverage is necessary but not sufficient. 100% coverage with synthetic
   inputs is worse than 80% coverage with real inputs. Prefer testing real
   commands from skill files over hand-crafted examples.

**Targeted test commands** (new subsection after "Running Tests"):
```
After skill file changes:
pytest -m contract
python scripts/contract_gate.py

After hook changes:
pytest -m hook_e2e

Fast feedback (subagents):
pytest -m "not slow and not machine_specific"
```

### 2. Add Test Markers to pyproject.toml

In `[tool.pytest.ini_options]`, add markers:

```toml
markers = [
    "machine_specific: tests that depend on local file paths",
    "contract: tests derived from skill file commands (run after skill changes)",
    "hook_e2e: tests that invoke hooks via subprocess (run after hook changes)",
    "integration: cross-module or hook-chain tests",
    "slow: tests taking >1s (network, real daemon, large fixtures)",
]
```

### 3. Apply Markers to Existing Test Files

Mark existing tests with the new categories:

- `tests/test_contract_commands.py`: all classes and functions get
  `@pytest.mark.contract`. The `TestContractGate` class also gets
  `@pytest.mark.slow` (it spawns a subprocess per skill-file command).

- `tests/test_bootstrap_read_guard.py`: all classes get
  `@pytest.mark.hook_e2e`. The `TestExtractSahjhanSubcmd` class is unit-level
  (imports the function directly) and should NOT get the marker.

- `tests/test_e2e_hook_invocation.py`: `@pytest.mark.hook_e2e`

- `tests/test_protocol_enforcement.py`: `@pytest.mark.hook_e2e`

- `tests/test_sahjhan_integration.py`: `@pytest.mark.hook_e2e` and
  `@pytest.mark.integration`

- `tests/test_hook_schema_freshness.py`: already has a `network` marker;
  add `@pytest.mark.slow`

- `tests/test_integration.py`: `@pytest.mark.integration`

### 4. Update Release Checklist in CLAUDE.md

In the "Cutting a Release" section, add step 4.5 (between smoke test and
schema freshness):

```
4.5. Run contract gate: `python scripts/contract_gate.py`
```

### 5. Verify

- `pytest -m contract` runs only contract tests
- `pytest -m hook_e2e` runs only hook E2E tests
- `pytest -m "not slow"` skips slow tests
- `pytest` (no markers) still runs everything
- `ruff check .` passes
- All tests still pass

## Estimated Scope

~30 minutes. Mostly editing CLAUDE.md, pyproject.toml, and adding
`pytestmark` lines to existing test files. No new tests.

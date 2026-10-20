# Phase 4: Test Suite Substance

## Context

Part of the testing methodology overhaul. The test suite has good numerical
coverage but weak input diversity and no systematic exploration of failure
modes. This phase adds property-based testing, hook chain integration tests,
and failure mode tests.

Depends on: Phase 3 (real daemon fixture for integration and failure tests).
Can partially start without Phase 3 — property-based tests and error message
tests don't need the daemon.

## Tasks

### 1. Property-Based Testing for Parsers

hypothesis is already a project dependency. Add property-based tests for the
three most regex-heavy, parse-heavy functions:

a. **`_extract_sahjhan_subcmd`** in `test_bootstrap_read_guard.py`:

   ```python
   from hypothesis import given, strategies as st

   @given(st.text(min_size=1, max_size=200))
   def test_extract_never_crashes(self, segment):
       """Parser must never crash on arbitrary input."""
       extract = self._get_extract()
       result = extract(segment)
       # Result is either None or a tuple of two strings
       assert result is None or (
           isinstance(result, tuple)
           and len(result) == 2
           and isinstance(result[0], str)
           and isinstance(result[1], str)
       )
   ```

   Also generate structured inputs: `sahjhan` + random tokens + random
   redirects. Verify the parser extracts a valid subcommand or returns None.

b. **`_check_bash_write`** — generate command strings containing protected
   paths with various write operators (>, >>, tee, cp, mv, etc.). Verify
   that any command writing to a protected path returns a block reason.

   ```python
   @given(
       cmd=st.sampled_from(["cp", "mv", "rm", "tee"]),
       protected=st.sampled_from(ALL_PROTECTED),
       prefix=st.text(max_size=20),
   )
   def test_write_to_protected_always_blocked(cmd, protected, prefix):
       """Writing to a protected path must always be blocked."""
       ...
   ```

c. **Punchlist parser** (in `test_validate_punchlist.py`) — generate
   markdown with valid section headers and varying item formats. Verify the
   parser either produces a valid result or raises a clean error.

d. **Convergence check** — generate item count combinations and verify the
   convergence logic is consistent (if zero items remain, convergence is
   reachable; if items remain, it isn't).

Mark all hypothesis tests with `@pytest.mark.slow` since they run many
iterations by default (100+). Use `@settings(max_examples=50)` for CI to
keep runtime reasonable.

### 2. Hook Chain Integration Tests

Current tests invoke hooks individually. In production, hooks chain via
hooks.json. Write tests that simulate realistic multi-hook sequences.

Create `tests/test_hook_chains.py`:

a. **PreToolUse chain for Bash**: Construct a realistic Bash event
   (e.g., `sahjhan transition run_start`). Run it through the chain:
   `_daemon_lifecycle.py` -> `_sahjhan_bootstrap.py` -> `commit_gate.py`.
   Verify all three allow. Verify the cumulative output is valid.

b. **PostToolUse chain for Bash**: After a simulated `git commit`, run
   through: `post_tool_hook.py` -> `bash_guard.py` -> `protocol_tracker.py`.
   Verify events are recorded and state is updated.

c. **Full round trip**: PreToolUse (allow) -> simulate tool execution ->
   PostToolUse (record). Verify the enforcement cache reflects the complete
   operation.

d. **Chain with one hook blocking**: `_sahjhan_bootstrap.py` blocks
   `sahjhan reset`. Verify the chain short-circuits — `commit_gate.py`
   never runs for a blocked command.

e. **SubagentStop chain**: `subagent_findings_check.py` ->
   `lens_quiz.py`. This is the hardest to test in isolation. With the real
   daemon fixture (Phase 3), it becomes possible to test the full quiz
   flow: pose questions, provide answers, verify scoring.

These tests use the real daemon fixture from Phase 3 where they need real
enforcement state. For chain tests that only need to verify output format,
the mock daemon is sufficient.

### 3. Failure Mode Tests

The agent audit identified these untested failure modes. Each gets a test.

Create `tests/test_failure_modes.py`:

a. **Daemon socket timeout**: Configure mock daemon to delay responses by
   >5 seconds. Verify hooks that query the daemon (lens_quiz, primer,
   protocol_tracker) degrade gracefully — they should either fail closed
   (block) or fail open (allow) based on enforcement freshness, not crash.

b. **Daemon death mid-session**: Using the real daemon fixture, start a
   session (init + ledger + transition). Kill the daemon process (`kill -9`).
   Verify `_daemon_lifecycle.py` detects death and writes the terminated
   marker. Verify `stop_hook.py` allows stop after death.

c. **Corrupt enforcement cache**: Write invalid JSON to the cache socket
   response (using mock daemon). Verify hooks that read the cache handle
   the corruption without crashing.

d. **Stale status-cache.json**: Write a `status-cache.json` file with an
   old timestamp. Kill the daemon. Verify `stop_hook.py` falls back to the
   file and handles the staleness (warns, doesn't crash).

e. **Concurrent cache access**: Launch two hook invocations in parallel
   (using threads or subprocesses). Both write to the enforcement cache.
   Verify no data corruption (the daemon serializes access, so this is
   really testing that the daemon handles concurrency).

f. **Binary unavailable**: Mock `ensure_sahjhan()` to return None. Verify
   hooks that need the binary degrade gracefully (hooks that call
   `sahjhan status`, `sahjhan event`, etc. should fall back or skip, not
   crash).

g. **PID reuse simulation**: Write a daemon-init-pid file containing a PID
   of a known-alive process (e.g., PID 1 or the test process itself).
   With the daemon actually dead. Verify `_daemon_lifecycle.py` correctly
   identifies the daemon as dead despite `os.kill(pid, 0)` succeeding.

   NOTE: This one may not be testable cleanly — PID reuse detection is a
   fundamental limitation of the PID-based liveness check. If the test
   reveals that the code can't handle it, that's a real finding worth
   documenting as a known limitation rather than papering over with a
   test.

### 4. Error Message Quality Tests

Expand the `TestDenyMessageQuality` pattern from `test_contract_commands.py`
to cover all hooks that produce user-facing deny messages.

Create `tests/test_deny_message_quality.py`:

For each hook that can deny:

a. Trigger a deny (e.g., write to protected path, blocked subcommand,
   commit gate obligation).

b. Assert the deny message:
   - Names the specific action that was blocked
   - Does not contain parse artifacts (redirect fragments, token indices,
     raw regex matches)
   - Contains actionable guidance (what to do instead)
   - Is grammatically coherent (an LLM agent is the primary consumer)

c. Test deny messages with shell idioms appended (the redirect fragment
   bug from issue #53 — verify it doesn't regress in other hooks).

### 5. Verify

- `pytest tests/test_hook_chains.py` — chain tests pass
- `pytest tests/test_failure_modes.py` — failure mode tests pass
- `pytest -m slow` — includes property-based and daemon tests
- `pytest -m "not slow"` — fast subset still works
- `ruff check .` and `mypy` pass
- Total test count reflects new additions

## Estimated Scope

~3-4 hours. This is the largest phase. Property-based tests and failure
mode tests require careful setup. Hook chain tests require understanding
the full hooks.json wiring.

## Prioritization Within Phase

If time is limited, do in this order:
1. Failure mode tests (3) — highest ROI, tests what actually breaks
2. Property-based parser tests (1a, 1b) — catches edge cases systematically
3. Error message quality (4) — prevents issue #53 class regressions
4. Hook chain tests (2) — valuable but complex to set up
5. Property-based data tests (1c, 1d) — nice to have

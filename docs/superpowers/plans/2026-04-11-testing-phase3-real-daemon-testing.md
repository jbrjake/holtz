# Phase 3: Real Daemon Testing Infrastructure

## Context

Part of the testing methodology overhaul. Currently ALL tests mock the
sahjhan daemon — a 50-line `MockEnforcementDaemon` in conftest.py that
speaks a simplified socket protocol. The real daemon is a Rust binary
available via `ensure_sahjhan()` from GitHub Releases.

The mock can't reproduce real daemon behavior under edge cases (concurrent
access, socket timeouts, state transitions, HMAC signing). Tests that use
the mock are testing against an impersonator, not the dependency.

The fix is simple: use the real binary. Start a real daemon for integration
tests. It's a project dependency like any other.

Depends on: Phase 1 (markers).
Enables: Phase 4 (failure mode tests, hook chain tests).

## Tasks

### 1. Real Daemon Fixture

Create a pytest fixture in `tests/conftest.py` that:

a. Calls `ensure_sahjhan()` to get the binary path. If the binary isn't
   available (CI without download, etc.), skip with `pytest.skip("sahjhan
   binary not available")`.

b. Creates a temp directory for `.sahjhan/` state.

c. Runs `sahjhan init` against the temp directory.

d. Starts a real daemon: `sahjhan daemon start` with a custom socket path
   (use `/tmp/` prefix to avoid macOS 104-char AF_UNIX limit).

e. Records the daemon PID for cleanup.

f. Sets `SAHJHAN_DAEMON_SOCKET` env var so hooks find the real daemon.

g. On teardown: stops the daemon (`sahjhan daemon stop` or `kill`), removes
   the temp directory.

```python
@pytest.fixture
def real_daemon(tmp_path):
    """Start a real sahjhan daemon for integration tests.
    
    Requires the sahjhan binary (downloaded via ensure_sahjhan).
    Skip if binary unavailable.
    """
    from enforcement.hooks._resolve import ensure_sahjhan
    
    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    
    # Use /tmp to stay under macOS 104-char socket limit
    import tempfile
    data_dir = tempfile.mkdtemp(prefix="sahjhan-test-")
    sock_path = os.path.join(data_dir, "daemon.sock")
    
    # Initialize
    subprocess.run([binary, "--data-dir", data_dir, "init"], check=True)
    
    # Start daemon
    subprocess.run(
        [binary, "--data-dir", data_dir, "daemon", "start"],
        env={**os.environ, "SAHJHAN_DAEMON_SOCKET": sock_path},
    )
    # Wait for socket to appear
    for _ in range(50):
        if os.path.exists(sock_path):
            break
        time.sleep(0.1)
    
    old_env = os.environ.get("SAHJHAN_DAEMON_SOCKET")
    os.environ["SAHJHAN_DAEMON_SOCKET"] = sock_path
    
    yield {
        "binary": binary,
        "data_dir": data_dir,
        "sock_path": sock_path,
    }
    
    # Cleanup
    subprocess.run([binary, "--data-dir", data_dir, "daemon", "stop"],
                   timeout=5, capture_output=True)
    if old_env is None:
        os.environ.pop("SAHJHAN_DAEMON_SOCKET", None)
    else:
        os.environ["SAHJHAN_DAEMON_SOCKET"] = old_env
    shutil.rmtree(data_dir, ignore_errors=True)
```

Mark tests using this fixture with `@pytest.mark.slow` since daemon
start/stop adds ~1s overhead.

### 2. Vendor Binary for CI

In `.github/workflows/ci.yml`, add a step to download the sahjhan binary
before tests run:

```yaml
- name: Download sahjhan binary
  run: |
    python -c "
    import sys; sys.path.insert(0, 'enforcement/hooks')
    from _resolve import ensure_sahjhan
    path = ensure_sahjhan()
    print(f'Binary at: {path}' if path else 'Download failed')
    "
```

Alternatively, use `scripts/vendor-sahjhan.sh` with the pinned version.

This ensures the real binary is available in CI for integration tests.

### 3. Real Daemon Integration Tests

Create `tests/test_real_daemon_integration.py` with tests that exercise
hooks against the real daemon:

a. **Full init sequence**: Using the `real_daemon` fixture, run every
   command from phase-recon.md Step 0 through the actual hooks AND verify
   the daemon state changes correctly:
   ```python
   def test_full_init_sequence(real_daemon):
       # sahjhan init (already done by fixture)
       # ledger create
       _run_hook(bash_event("sahjhan ledger create --from run 1 --activate"))
       # transition run_start
       _run_hook(bash_event("sahjhan transition run_start"))
       # Verify daemon reports correct state
       status = subprocess.run(
           [real_daemon["binary"], "--data-dir", real_daemon["data_dir"], "status"],
           capture_output=True, text=True,
       )
       assert "fix_loop" in status.stdout or "recon" in status.stdout
   ```

b. **Hook chain with real state**: Run a PreToolUse event through the
   bootstrap hook, then simulate the tool executing, then run the
   PostToolUse event through post_tool_hook and bash_guard. Verify the
   enforcement cache reflects the real state.

c. **Authed events with real HMAC**: Record an authed event through the
   real daemon and verify the HMAC signature is valid.

d. **Daemon death detection**: Start daemon, kill -9 it, verify
   `_daemon_lifecycle.py` hook detects the death and writes the
   terminated marker.

e. **Stop hook with real state**: Advance to a non-terminal state, verify
   stop_hook blocks. Advance to finalized, verify stop_hook allows.

### 4. Capture Real Test Runner Output for Fixtures

Replace `tests/runner_fixtures.py` synthetic data with captured output from
real test runs:

a. Create `scripts/capture_test_fixtures.sh` that runs the project's own
   test suite and captures:
   - pytest verbose output (passed/failed/error formatting)
   - pytest summary line (N passed, M failed, etc.)
   - ruff output with violations
   - mypy output with errors

b. Save these to `tests/fixtures/` as text files.

c. Update tests that parse runner output to use the captured fixtures
   instead of the hand-crafted "cheese shop" data. Keep the synthetic
   fixtures as additional test cases (they test known edge cases), but
   ADD real fixtures alongside.

### 5. Verify

- `pytest -m slow` runs daemon integration tests and they pass
- `pytest -m "not slow"` skips them (fast feedback for subagents)
- CI downloads binary and runs integration tests
- Real daemon fixture starts, serves real state, cleans up
- Runner fixture tests use real captured output

## Estimated Scope

~2 hours. The fixture itself is ~40 lines. Most time goes into the
integration tests that exercise real daemon behavior and capturing
real runner output.

## Note on the Mock Daemon

The mock daemon in conftest.py should NOT be removed. It's still useful for:
- Testing hook behavior when the daemon is unreachable (failure mode)
- Fast unit tests that don't need real daemon overhead
- Tests that need to control exact daemon responses

The real daemon fixture is for integration tests that verify the full stack.
Both coexist.

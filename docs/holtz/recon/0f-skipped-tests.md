# 0f: Skipped/Disabled Tests

## pytest.skip calls
- `tests/test_token_profiler_integration.py:41` — conditional skip when Run 14 session JSONL is not available. This is an environment-dependent skip, not a disabled test.

## Permanently disabled tests
None found. No `@pytest.mark.skip`, `@pytest.mark.skipIf`, `xfail`, or `xit` decorators used on any test.

## Notes
- All 619 tests pass locally with 0 skips
- CI environment skips 8 token profiler integration tests (session data not available)
- No disabled or deferred test debt

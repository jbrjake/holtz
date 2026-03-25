# Step 0f: Skipped Tests

**Date:** 2026-03-24
**Run:** 15

## Results
No tests use `@pytest.mark.skip`, `xfail`, or `xit`.

One conditional skip: `tests/test_token_profiler_integration.py:39` — `skip_if_no_session` fixture skips integration tests when run-14 session JSONL is not available. This is expected (large binary not checked in).

## Assessment
Clean — no tech debt hidden behind skipped tests.

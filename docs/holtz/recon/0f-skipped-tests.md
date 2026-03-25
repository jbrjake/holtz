# Step 0f: Skipped/Disabled Tests

**Date:** 2026-03-24

## Findings
- **0 pytest.mark.skip decorators** found in test files
- **0 xfail markers** found
- **1 conditional skip:** `tests/test_token_profiler_integration.py` — `skip_if_no_session` fixture skips profiler integration tests when Run 14 session JSONL is not available. This is environment-conditional, not a test gap.

## Assessment
No disabled or skipped tests. All 613 tests execute on every run.

# Test Anti-Patterns

## Tier 1: Actively Harmful

**1. Tautology Test** — Asserts what the code does, not what it should do. Detection: test passes regardless of production code changes; assertions reference the function being tested or values configured in the mock.

**2. Green Bar Addict** — Exists only for CI green. Detection: assertions limited to `is not None` / `toBeDefined()` / `assertTrue(True)`, or entirely absent. Exception handlers swallowing test failures.

**3. The Mockingbird** — So much mocked that no production code executes. Detection: mock/patch decorators outnumber real calls. Function under test wouldn't notice if its implementation changed entirely.

**4. Inspector Clouseau** — Tests implementation details not behavior. Detection: assertions on private methods, call order, or internal state outside the public contract. Refactoring internals breaks the test even when behavior is correct.

## Tier 2: False Security

**5. Happy Path Tourist** — Only tests success case. Detection: function with 5+ code paths but 1 test. Any function with conditionals/error handling having only one test.

**6. Snapshot Trap** — Snapshots accepted without review, cementing bugs. Detection: large snapshot files, snapshots committed in same PR as the component, TODO/FIXME in snapshot output.

**7. Time Bomb** — Hardcoded dates or time-dependent behavior. Detection: hardcoded years, `time.sleep`/`setTimeout` in tests, intermittent failures.

**8. Schrodinger Test** — Passes alone, fails in combination (or vice versa). Detection: run tests in random order. Shared mutable state: globals, DB records, temp files, env vars set by other tests.

## Tier 3: Missed Opportunities

**9. Shallow End** — Unit tests exist but integration path untested. Detection: map critical call chains; if no test exercises the full path, it's a gap.

**10. Copy-Paste Archipelago** — 80% duplicated setup, slight variations. Detection: high line count vs assertion count. Missing fixtures/factories/helpers.

**11. Rubber Stamp** — Asserts structure not correctness. Detection: assertions only check types/keys/lengths, never computed values. Would pass with random data.

**12. Permissive Validator** — Overly broad assertions accepting wrong answers. Detection: uses `>`, `>=`, `in`, `isinstance` where exact values are knowable.

## Audit Checklist

For each test file, score against:

| Check | Red Flag |
|-------|----------|
| Mutation resilience | Passes regardless of code changes |
| Mock ratio | >60% of system mocked |
| Assertion density | <1 meaningful assertion per test |
| Edge coverage | Only happy path |
| Integration scope | All isolated units, no full-path tests |
| Determinism | Time/order dependent |
| Behavioral focus | Tests implementation details |

0-2 red flags = decent. 3-4 = needs work. 5+ = rewrite.

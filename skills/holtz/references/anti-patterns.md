# Test Anti-Patterns

## Tier 1: Actively Harmful

**1. Tautology Test** — Asserts what the code does, not what it should do. Detection: test passes regardless of production code changes; assertions reference the function being tested or values configured in the mock.

**2. Green Bar Addict** — Exists only for CI green. Detection: assertions limited to `is not None` / `toBeDefined()` / `assertTrue(True)`, or entirely absent. Exception handlers swallowing test failures.

**3. The Mockingbird** — So much mocked that no production code executes. Detection: mock/patch decorators outnumber real calls. Function under test wouldn't notice if its implementation changed entirely.

**4. Inspector Clouseau** — Tests implementation details not behavior. Detection: assertions on private methods, call order, or internal state outside the public contract. Refactoring internals breaks the test even when behavior is correct.

**13. Assertion Roulette** — Multiple assertions per test with no messages; when one fails, you can't tell which or why without reading source. Detection: count bare `assert` / `assertEqual` calls per test method with no `msg=` parameter. >5 undifferentiated assertions in a single test is a strong signal. Distinct from Green Bar Addict (which has TOO FEW assertions) — this has plenty, but they're anonymous.

**14. Choose Your Own Adventure** — Test contains conditional logic (`if`, `for`, `try/except`) creating branches within the test itself. The test is now a program that itself needs testing. Detection: any `if`/`for`/`while`/`try` inside a test method body (excluding context managers). If the test has branches, some branches are untested. 97% of surveyed developers in test-smell studies recognize this as harmful.

## Tier 2: False Security

**5. Happy Path Tourist** — Only tests success case. Detection: function with 5+ code paths but 1 test. Any function with conditionals/error handling having only one test.

**6. Snapshot Trap** — Snapshots accepted without review, cementing bugs. Detection: large snapshot files, snapshots committed in same PR as the component, TODO/FIXME in snapshot output.

**7. Time Bomb** — Hardcoded dates or time-dependent behavior. Detection: hardcoded years, `time.sleep`/`setTimeout` in tests, intermittent failures.

**8. Schrodinger Test** — Passes alone, fails in combination (or vice versa). Detection: run tests in random order. Shared mutable state: globals, DB records, temp files, env vars set by other tests.

**15. Mystery Guest** — Test depends on external state invisible in the test body: files on disk, database records from another test's setup, environment variables, system locale, or network services. Cause-and-effect is opaque — the test fails and you can't tell why by reading it. Detection: test references file paths, env vars, or external URLs not created within the test or its fixture. Subsumes "The Local Hero" (fails on different OS/timezone/locale) as a specific variant.

**16. The Eager Beaver** — Single test exercises multiple independent production behaviors. When it fails, you know *something* broke but not *what*. Defect localization is destroyed. Detection: test calls 2+ unrelated production methods and asserts on results from each. Test name requires "and" to describe what it tests.

## Tier 3: Missed Opportunities

**9. Shallow End** — Unit tests exist but integration path untested. Detection: map critical call chains; if no test exercises the full path, it's a gap.

**10. Copy-Paste Archipelago** — 80% duplicated setup, slight variations. Detection: high line count vs assertion count. Missing fixtures/factories/helpers.

**11. Rubber Stamp** — Asserts structure not correctness. Detection: assertions only check types/keys/lengths, never computed values. Would pass with random data.

**12. Permissive Validator** — Overly broad assertions accepting wrong answers. Detection: uses `>`, `>=`, `in`, `isinstance` where exact values are knowable.

**17. The Ice Cream Cone** — Inverted test pyramid: mostly manual or end-to-end tests, minimal unit tests, almost no integration tests. Feedback loop is hours instead of seconds; developers stop running tests locally. Detection: count test files by type (unit vs integration vs e2e). If e2e > unit, the pyramid is inverted. A codebase-level antipattern, not per-test — score it during project audits, not file audits.

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
| Assertion identifiability | >5 assertions per test with no messages |
| Test logic complexity | Conditionals/loops inside test body |
| External dependency visibility | Test relies on state not created in test/fixture |
| Behavioral isolation | Single test exercises multiple unrelated behaviors |
| Pyramid shape | E2E test count exceeds unit test count |

0-2 red flags = decent. 3-4 = needs work. 5+ = rewrite.

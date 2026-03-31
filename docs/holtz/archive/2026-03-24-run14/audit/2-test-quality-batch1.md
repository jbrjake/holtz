# Audit 2 — Test Quality (Batch 1)

**Auditor:** Claude Opus 4.6 (1M context)
**Date:** 2026-03-24
**Status:** DONE

Audited 4 test files against 12 anti-patterns. Overall quality is high across
all four files — tests are behavior-focused, cover edge cases extensively, and
include meaningful failure messages. Most items below are cosmetic.

---

## tests/test_validate_punchlist.py (2578 lines, ~76 tests)

**Red flags: 1**

| # | Anti-pattern | Lines | Severity | Notes |
|---|---|---|---|---|
| 1 | **Copy-Paste Archipelago (#10)** | ~10-996 (most pre-`make_item` tests) | Cosmetic | The first ~65 tests each construct a full punchlist item inline (7-15 lines of boilerplate per test). The `make_item` fixture was added later and is used from line ~2288 onward. The pre-fixture tests work correctly and their inline content makes boundary conditions very explicit, so this is a style issue, not a quality issue. Refactoring would reduce ~500 lines but risks obscuring the exact input each test cares about. |

**What's good:**
- Every test checks *behavior* ("empty Problem should be detected as empty") not implementation.
- Excellent boundary testing (threshold at 10/11 chars, 5/6 chars).
- Code-fence poisoning tests are thorough and test a real attack surface.
- Multi-item isolation tests catch cross-contamination bugs.
- CLI integration tests (lines 2486-2578) exercise the real subprocess path.
- Failure messages include context values, making diagnosis easy.

**Verdict:** Decent. The copy-paste is pre-fixture legacy and each test's inline content makes the edge case under test crystal clear.

---

## tests/test_convergence_check.py (1289 lines, ~55 tests)

**Red flags: 1**

| # | Anti-pattern | Lines | Severity | Notes |
|---|---|---|---|---|
| 1 | **Copy-Paste Archipelago (#10)** | 388-617 (test runner output parsing) | Cosmetic | The 24 test runner parsing tests (pytest/jest/vitest/cargo/go/swift/mocha) each follow the exact same pattern: `monkeypatch.setattr(subprocess, "run", _fake_run(fx.FIXTURE))` then `assert result == {...}`. A parametrize decorator could compress these. However, each test has a distinct whimsical docstring and the pattern is trivial enough that duplication doesn't obscure intent. |

**What's good:**
- False convergence tests are excellent: empty punchlist, deletion-based, partial deletion, re-opened items.
- Cross-parser agreement tests (lines 683-869) validate that `count_items` and `parse_punchlist` agree — this is a genuine integration concern.
- Stall detection tests cover the 4-entry threshold boundary.
- Error path coverage: malformed JSON, missing files, corrupted history, timeout, missing binary.
- No test depends on execution order (each uses `tmp_path` or `monkeypatch` for isolation).

**Verdict:** Decent. The runner output tests are repetitive but individually correct and well-labeled.

---

## tests/test_impact_graph.py (983 lines, ~56 tests)

**Red flags: 0**

No anti-patterns found.

**What's good:**
- Numbered test scheme (01-38) with clear categories makes navigation easy.
- Systematic coverage: basic CRUD, blast radius, cycles, multi-edge, risk scores, pruning, node updates, large graph, drift check, CLI, edge cases.
- The `_chain_graph` helper (line 164) extracts shared setup without hiding test intent.
- Corruption/malformation tests (lines 877-983) validate that `load()` filters bad entries rather than crashing — this is real defensive quality.
- 200-node/500-edge round-trip (test 38) with deterministic seed is a solid stress test.
- Drift check tests cover Python (sync+async), JavaScript, Go, classes, binary files, and `line=None`.
- CLI integration via subprocess (line 712) confirms the script entry point works end-to-end.

**Verdict:** This file is the strongest of the four. No issues found.

---

## tests/test_hooks.py (531 lines, ~30 tests)

**Red flags: 0**

No anti-patterns found.

**What's good:**
- `run_hook` / `assert_allowed` / `assert_blocked` / `assert_warned` helpers (lines 21-67) are clean abstractions that eliminate boilerplate without hiding assertion logic.
- `TestModernOutputFormat` tests the `_common.py` primitives (`exit_ok`, `exit_warn`, `exit_block`) independently from the hooks that use them — proper unit/integration separation.
- Every hook test runs the actual Python script as a subprocess, so they are true integration tests.
- Both allow and block paths are tested for each gate hook.
- Edge cases covered: empty stdin, malformed JSON, empty file_path, shell variables in paths, Justine namespace scoping.
- PostToolUse/SubagentStop hooks correctly verify they do NOT include `hookSpecificOutput` (lines 467-472, 526-531).

**Verdict:** Clean. Well-structured with reusable helpers and no anti-patterns.

---

## Anti-pattern Summary

| Anti-pattern | test_validate_punchlist | test_convergence_check | test_impact_graph | test_hooks |
|---|---|---|---|---|
| 1. Tautology Test | -- | -- | -- | -- |
| 2. Green Bar Addict | -- | -- | -- | -- |
| 3. Mockingbird | -- | -- | -- | -- |
| 4. Inspector Clouseau | -- | -- | -- | -- |
| 5. Happy Path Tourist | -- | -- | -- | -- |
| 6. Snapshot Trap | -- | -- | -- | -- |
| 7. Time Bomb | -- | -- | -- | -- |
| 8. Schrodinger Test | -- | -- | -- | -- |
| 9. Shallow End | -- | -- | -- | -- |
| 10. Copy-Paste Archipelago | Cosmetic | Cosmetic | -- | -- |
| 11. Rubber Stamp | -- | -- | -- | -- |
| 12. Permissive Validator | -- | -- | -- | -- |

**Notes on patterns considered but not flagged:**

- **Time Bomb (#7):** The convergence tests use hardcoded timestamps like `"2026-03-19T01:00:00"` but these are fixture data for ordering, not values compared to `datetime.now()`. No test will break when the date passes. Not a time bomb.
- **Mockingbird (#3):** `test_convergence_check.py` uses `monkeypatch.setattr(subprocess, "run", ...)` heavily for runner output parsing, but the mock is minimal (just stdout/returncode) and the real parsing logic is fully exercised. The alternative — running 7 different test frameworks in CI — is not practical. Appropriate use of mocking.
- **Shallow End (#9):** Could argue the validate_punchlist unit tests lack an integration path, but `test_sample_punchlist_parses_cleanly` (line 1978) exercises the real sample file, and CLI tests (lines 2486-2578) run the script end-to-end.
- **Happy Path Tourist (#5):** All four files test error paths, corruption, boundary conditions, and malformed input extensively.

---

## Overall Assessment

All four files are in good shape. The two Copy-Paste Archipelago flags are cosmetic:
the inline punchlist content in `test_validate_punchlist.py` makes boundary conditions
self-documenting, and the runner fixture tests in `test_convergence_check.py` are trivially
simple. Neither warrants a refactor unless the files continue growing.

No real quality concerns. No rewrite candidates.

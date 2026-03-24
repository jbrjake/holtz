# Audit 2: Test Quality

Audited 2026-03-23 against the 12 anti-patterns in `references/anti-patterns.md`.

---

## 1. tests/test_validate_punchlist.py

| Metric | Value |
|--------|-------|
| Lines | 2309 |
| Tests | 68 |
| Lines/test | 34 |

### Anti-pattern flags

**#10 Copy-Paste Archipelago (MINOR).** Most tests construct a full punchlist item
inline (Severity/Category/Location/Status/Problem/Evidence/AC/VC), repeating
~15 identical boilerplate lines per test. A fixture or factory function
(`make_item(overrides)`) would cut each test to 3-5 lines of signal. However,
the duplication is cosmetic -- each test *does* vary the specific field under
test, and the assertions are specific. The high lines/test ratio (34) is mostly
boilerplate, not meaningless assertions.

**Assessment: not a real flag.** The duplication inflates line count but does not
reduce test effectiveness. Each test would still catch the bug it guards.

### What the tests do well

- **Behavioral assertions on computed values.** Tests check parsed field values
  (`items[0].status == "OPEN"`, `items[0].severity == "CRITICAL"`), not just
  types or lengths. Passes the Rubber Stamp (#11) and Permissive Validator (#12)
  checks.
- **Error/boundary paths thoroughly covered.** Empty sections (lines 7-35),
  code fence poisoning (lines 579-762), CRLF (lines 373-400), trailing text
  (lines 98-125), duplicate IDs (lines 187-232), invalid severity (lines
  471-498), empty punchlist (lines 237-241), threshold boundaries at exactly
  10/11 chars and 5/6 chars (lines 1487-1599). Passes Happy Path Tourist (#5).
- **Mutation resilience.** Breaking the Status regex, section extraction, or
  code-fence masking would cause specific tests to fail with descriptive messages.
  Passes Tautology (#1) and Green Bar Addict (#2).
- **No mocking.** All tests call real production code. Passes Mockingbird (#3).

### Score: GREEN (0 flags)

No punchlist-worthy findings.

---

## 2. tests/test_convergence_check.py

| Metric | Value |
|--------|-------|
| Lines | 1289 |
| Tests | 87 |
| Lines/test | 15 |

### Anti-pattern flags

**#10 Copy-Paste Archipelago (MINOR).** The snapshot dicts used in convergence
tests repeat the same 6-key structure (`timestamp`, `punchlist` with 5-6 status
keys, `tests`). A helper like `snap(open=3, resolved=2, tests=None)` would
reduce noise. Similar pattern in the `detect_test_runner` block (lines 256-353)
where each test creates a single config file and asserts the runner name.

**Assessment: not a real flag.** The repetition is in test data construction,
not in assertions. Each test targets a distinct code path and would break if
its guarded behavior changed.

### What the tests do well

- **Broad error path coverage.** Empty punchlist false convergence (line 7),
  malformed JSON (line 83), dict-not-list JSON (line 94), nonexistent file
  (line 904), unknown status blocking convergence (line 134), data gaps (line
  161), deletion-based false convergence (line 209), stall detection (line 941),
  missing punchlist key (line 188), test failures blocking convergence (line
  1159), partial deletion (line 1196), re-opened items (line 1222). Passes
  Happy Path Tourist (#5).
- **Exact value assertions.** `result == {"passed": 11, "failed": 0,
  "skipped": 0}` throughout the runner output parsing tests. Not permissive.
  Passes Permissive Validator (#12) and Rubber Stamp (#11).
- **Cross-parser agreement tests** (lines 683-773, 822-869) verify that
  `count_items` and `parse_punchlist` agree on the same input -- an integration
  check within a unit test file. Good.
- **Runner crash/timeout/not-found paths** all tested (lines 619-648).

### Score: GREEN (0 flags)

No punchlist-worthy findings.

---

## 3. tests/test_impact_graph.py

| Metric | Value |
|--------|-------|
| Lines | 901 |
| Tests | 60 |
| Lines/test | 15 |

### Anti-pattern flags

None identified.

### What the tests do well

- **Behavioral focus across all 10 operations.** Tests cover add/query,
  persistence round-trip, blast radius with depth/cycle/type filters, risk
  score clamping and NaN/Inf rejection, pruning with edge cascades, drift
  check across Python/JS/Go/async, CLI integration, and corrupt/null/wrong-type
  JSON loading. Passes Happy Path Tourist (#5).
- **Exact value assertions.** `blast_radius("chain.py::A", depth=1) ==
  ["chain.py::B"]`, `stats == {"nodes": 0, "edges": 0, ...}`, `edge["metadata"]
  ["note"] == "passes frequency as float Hz"`. Passes Rubber Stamp (#11) and
  Permissive Validator (#12).
- **Edge cases well-represented.** Empty graph (test_05), nonexistent nodes
  (test_10, test_22, test_36), self-referencing cycles (test_15), 200-node
  round-trip (test_38), binary files (line 843), null JSON values (line 138),
  wrong-typed JSON (line 877), missing metadata key (line 892), empty types
  filter (line 743), negative `top` (line 396).
- **Shared fixture (`graph`) is minimal and well-scoped.** Each test builds
  its own graph state, avoiding Schrodinger Test (#8).
- **CLI subprocess test** (line 712) exercises the real script entry point.

### Score: GREEN (0 flags)

No punchlist-worthy findings.

---

## 4. tests/test_markdown_utils.py

| Metric | Value |
|--------|-------|
| Lines | 233 |
| Tests | 25 |
| Lines/test | 9 |

### Anti-pattern flags

**#12 Permissive Validator (MINOR).** Several tests use `in` checks
(`"fenced line" not in masked`, `"after" in masked`) rather than asserting
exact output. For example, `test_language_tagged_fence` (lines 31-38) checks
`"const x = 1;" not in masked` and `"more text" in masked` but does not
verify the exact masked output.

**Assessment: borderline, not a real flag.** The `in`/`not in` assertions
are testing the *behavior* of masking (content inside fences disappears,
content outside survives). The exact output depends on line-by-line blanking,
and the tests that *do* check exact line output (e.g., `test_basic_fence_masking`
lines 7-18, `test_nested_fences` lines 41-52) anchor the behavior precisely.
The `in`-based tests add coverage for language tags, tilde fences, indented
fences, and mixed fence types -- cases where exact line matching would be
fragile without adding safety. A function returning random data would fail
these tests (it would not contain "after" while also not containing "fenced").

### What the tests do well

- **Both exact and behavioral assertions.** Some tests verify line-by-line
  output (lines 7-18, 21-28, 41-52), others verify content membership. The
  combination covers correctness without brittleness.
- **Boundary cases covered.** Unclosed fences (line 55), fence on first line
  (line 66), CRLF normalization (line 87), 4-space indent rejection (line 154),
  tilde-in-info-string (line 181), `has_unclosed_fence` with empty/no-fence/
  CRLF inputs (lines 200-233). Passes Happy Path Tourist (#5).
- **No mocking.** Pure function tests on real code.

### Score: GREEN (0 flags)

No punchlist-worthy findings.

---

## 5. tests/test_integration.py

| Metric | Value |
|--------|-------|
| Lines | 252 |
| Tests | 5 |
| Lines/test | 50 |

### Anti-pattern flags

**#5 Happy Path Tourist (REAL FLAG).** The integration tests verify agreement
between `validate_punchlist` and `convergence_check` on well-formed and
mildly-tricky inputs (shared multi-status punchlist, code fence immunity,
trailing status text). However, there is no integration test for the
*disagreement* path -- what happens when the two parsers produce conflicting
results on malformed input. The unit test files individually cover this
(e.g., `test_cross_parser_agreement` in test_convergence_check.py), but the
dedicated integration file does not test error propagation across the two
modules. This is a minor gap, not a critical one, since the unit-level
cross-parser tests are thorough.

**#11 Rubber Stamp (MINOR CONCERN) -- `test_readme_metrics_match_actual`.**
Lines 215-252 test that README-claimed test counts match actual counts. This
is a meta-test that validates documentation, not code behavior. It *will*
fail if a test is added without updating README, which is useful, but it does
not test any production logic. It also shells out to `pytest --co` at test
time, making it dependent on the test environment.

**Assessment: 1 real flag (#5).** The Happy Path Tourist flag is genuine but
low-severity since the cross-parser agreement tests exist in the unit files.

### What the tests do well

- **Cross-module agreement checks.** `test_item_count_agreement` and
  `test_status_distribution_agreement` verify that both parsers produce
  identical results from the same input -- the core integration concern.
- **Exact value assertions** on status counts and item counts.
- **Code fence immunity** tested across both parsers simultaneously (line 142).

### Score: GREEN (1 flag, but it is low-severity and mitigated by unit tests)

### Punchlist-worthy finding

The integration file would benefit from a negative-path test: feed both parsers
deliberately malformed input (e.g., missing Status field, unclosed fence with
phantom item) and verify they agree on the degraded result. The unit tests
cover this individually, but the integration file's purpose is specifically
to catch *disagreements*, so a malformed-input disagreement test belongs here.
Severity: LOW.

---

## Overall Summary

| File | Lines | Tests | Flags | Score |
|------|-------|-------|-------|-------|
| test_validate_punchlist.py | 2309 | 68 | 0 | GREEN |
| test_convergence_check.py | 1289 | 87 | 0 | GREEN |
| test_impact_graph.py | 901 | 60 | 0 | GREEN |
| test_markdown_utils.py | 233 | 25 | 0 | GREEN |
| test_integration.py | 252 | 5 | 1 (low) | GREEN |
| **Total** | **4984** | **245** | **1** | **GREEN** |

### Key observations

1. **No Tier 1 (Actively Harmful) anti-patterns found.** No tautologies,
   green-bar-only tests, over-mocking, or implementation-detail testing.

2. **Error and boundary paths are well-covered.** All five files test
   failure modes, edge cases, and malformed inputs. The test suite would
   catch regressions from production code changes.

3. **Assertions are specific and behavioral.** Tests check computed values
   (parsed fields, status counts, blast radius results, exact dict equality),
   not just types or truthiness.

4. **Copy-paste boilerplate is cosmetic, not harmful.** The punchlist markup
   repeated in test_validate_punchlist.py inflates line count but each test
   varies the signal field and would break independently. A factory fixture
   would improve readability but would not improve bug-catching ability.

5. **One low-severity gap:** test_integration.py lacks a malformed-input
   cross-parser disagreement test. This is mitigated by unit-level cross-parser
   tests in test_convergence_check.py (lines 683-773, 822-869).

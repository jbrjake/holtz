# Holtz Punchlist
> Generated: 2026-03-25 | Project: holtz (Justine self-audit) | Baseline: 639 pass, 1 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 1 | 0 | 0 |
| MEDIUM | 3 | 0 | 0 |
| LOW | 2 | 0 | 0 |

## Patterns

## Pattern: PAT-005: README-count-drift
**Instances:** BJ-001, BJ-002
**Root Cause:** README contains hardcoded counts that must be manually updated when files are added. No test covers all prose count mentions.
**Systemic Fix:** Either replace prose counts with a generation script, or extend test_readme_metrics_match_actual to cover all count claims in the README.
**Detection Rule:** `grep -nE "(fourteen|Fourteen|sixteen|Sixteen|nine |twelve|Twelve) " README.md` and verify against actual counts.

## Items

### BJ-001: README seed pattern count says 14, actual 16
**Severity:** HIGH
**Category:** doc/drift
**Location:** `README.md:108,216`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract
**Predicted:** Prediction 2 (confidence: HIGH)

**Problem:** README line 108 says "Fourteen seed patterns" and lists 14 names. README line 216 says "14 seed patterns". Actual count on disk is 16. Two patterns were added (numeric-precision-exhaustion, cross-language-dead-interface) without updating the README. The existing test_readme_metrics_match_actual catches this (it is currently failing), confirming this is a real defect requiring a README fix.

**Evidence:** `ls skills/holtz/patterns/*.md | wc -l` returns 16. README line 108 and 216 both say 14. test_readme_metrics_match_actual fails with "seed patterns: README says 14, actual 16".

**Discovery Chain:** inherited recon flagged pattern count drift -> verified with file count -> confirmed by test failure

**Acceptance Criteria:**
- [ ] README line 108 updated to say "Sixteen seed patterns" and list all 16
- [ ] README line 216 updated to say "16 seed patterns"
- [ ] test_readme_metrics_match_actual passes

**Validation Command:**
```bash
python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -x
```

### BJ-002: README lens count inconsistency -- says "nine" in two places, "thirteen" in one
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:38,114,146`
**Status:** OPEN
**Pattern:** PAT-005
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 38 says "nine analytical lenses." README line 146 says "all nine lenses" and then lists 9 by name (component through public contract). README line 114 says "thirteen analytical lenses." The actual lens registry has 13 lenses. Lines 38 and 146 are stale from before concurrency, resource-lifecycle, idempotency, and observability were added. Line 146 also names only 9 lenses instead of all 13. No existing test checks these prose counts.

**Evidence:** `grep -c '^## ' skills/holtz/references/lens-registry.md` returns 13. README line 38 says "nine." README line 146 says "nine" and lists only 9 names.

**Discovery Chain:** prediction from recon -> grep for "nine" in README -> counted lens registry headings -> confirmed drift

**Acceptance Criteria:**
- [ ] README line 38 updated to say "thirteen analytical lenses"
- [ ] README line 146 updated to list all 13 lenses
- [ ] README line 114 already says "thirteen" -- verify consistency

**Validation Command:**
```bash
grep -n "nine.*lens\|nine.*lenses" README.md | grep -v "^#"
```

### BJ-003: README anti-pattern count says "twelve", actual 17
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:50,138`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction 7 (confidence: MEDIUM)

**Problem:** README line 50 says "twelve anti-patterns across three tiers." README line 138 says "twelve anti-patterns." The local anti-patterns.md reference file contains 17 numbered anti-patterns (5 added: Assertion Roulette, Choose Your Own Adventure, Mystery Guest, The Eager Beaver, The Ice Cream Cone). No existing test checks this count.

**Evidence:** `grep -c '^\*\*[0-9]' skills/holtz/references/anti-patterns.md` returns 17. README lines 50 and 138 say "twelve."

**Discovery Chain:** README says twelve -> counted anti-patterns in reference file -> found 17 -> confirmed drift

**Acceptance Criteria:**
- [ ] README line 50 updated to say "seventeen anti-patterns across three tiers"
- [ ] README line 138 updated to say "seventeen anti-patterns"

**Validation Command:**
```bash
count=$(grep -c '^\*\*[0-9]' skills/holtz/references/anti-patterns.md); echo "Anti-patterns: $count"; grep -n "twelve anti-pattern" README.md
```

### BJ-004: README run count and stats stale
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:160,190,192`
**Status:** OPEN
**Lens:** public-contract
**Predicted:** Prediction 1 (confidence: HIGH)

**Problem:** README line 160 says "Sixteen runs." Line 190 says "After 16 runs: 619 tests across 13,800 lines." Line 192 references "all 16 runs." Current state is Run 19 with 639+ tests across 13,900+ lines. These prose counts are not covered by any automated test.

**Evidence:** Holtz recon says "Run 19." README says "Sixteen runs" (line 160) and "After 16 runs" (line 190). Test suite shows 640 tests collected.

**Discovery Chain:** inherited recon reports Run 19 -> README says "Sixteen runs" -> confirmed drift

**Acceptance Criteria:**
- [ ] README line 160 updated to reflect current run count
- [ ] README line 190 updated with current test count and line count
- [ ] README line 192 updated to reference current run count

**Validation Command:**
```bash
grep -n "Sixteen runs\|After 16 runs\|all 16 runs" README.md
```

### BJ-005: test_token_profiler_analyze uses permissive > 0 assertions where exact values are computable
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_analyze.py:630-632,663,665`
**Status:** OPEN
**Lens:** contract

**Problem:** Five assertions in test_token_profiler_analyze.py use `> 0` or `isinstance` checks where the inputs are fully deterministic and exact expected values are computable. Specifically: (1) `assert len(profile.summary.hottest_turns) > 0` should assert exact count, (2) `assert len(profile.summary.hottest_tools) > 0` should assert exact count, (3) `assert isinstance(profile.summary.hottest_tools[0], tuple)` checks type not value, (4) `assert css.total_billed_tokens > 0` should assert exact value, (5) `assert css.total_session_cost_tokens > 0` should assert exact value. These are Permissive Validator (anti-pattern #12) instances -- they would pass with any positive integer, including wrong values.

**Evidence:** In test_hottest_turns_and_tools (line 600+): inputs are 2 deterministic turns with known token counts. In test_produces_cross_session_summary (line 641+): inputs are 2 sessions with known turns. All outputs are computable from these fixed inputs but the test only checks `> 0`.

**Discovery Chain:** anti-pattern sweep of cold files -> found `> 0` assertions on deterministic inputs -> confirmed values are computable -> classified as Permissive Validator

**Acceptance Criteria:**
- [ ] Assertions on lines 630-632, 663, 665 replaced with exact expected values
- [ ] Assertions verify the right number, not just that a number exists

**Validation Command:**
```bash
grep -n "assert.*> 0\|assert isinstance.*tuple" tests/test_token_profiler_analyze.py
```

### BJ-006: TestSectionsPresent in test_token_profiler_report checks format without checking values
**Severity:** LOW
**Category:** test/shallow
**Location:** `tests/test_token_profiler_report.py:283-319`
**Status:** OPEN
**Lens:** contract

**Problem:** The TestSectionsPresent class (9 tests) only checks that section heading strings exist in the generated markdown. It does not check that any content beneath those headings is correct. These tests would pass even if the section content was completely wrong or empty, as long as the heading string appeared. This is the Rubber Stamp anti-pattern (#11) -- checking structure without checking correctness. However, other test classes in the same file DO check content values (TestSummaryFormatting, TestDollarCosts, etc.), so the risk is partially mitigated. The section-present tests add value as format regression guards but would be strengthened by at least one content assertion per section.

**Evidence:** TestSectionsPresent methods at lines 285-318 all follow the pattern: `md = generate_markdown(...)` then `assert "## SectionName" in md`. No assertion on section content.

**Discovery Chain:** anti-pattern sweep -> found 9 format-only tests -> cross-checked with value tests in same file -> classified as Rubber Stamp with mitigation

**Acceptance Criteria:**
- [ ] Each TestSectionsPresent test augmented with at least one content value assertion, OR the class is documented as intentionally format-only with a comment explaining the companion value tests

**Validation Command:**
```bash
grep -A2 "def test_" tests/test_token_profiler_report.py | grep -B1 "assert.*in md" | head -20
```

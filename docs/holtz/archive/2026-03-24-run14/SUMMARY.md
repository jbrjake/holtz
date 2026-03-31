# Holtz Summary

**Project:** holtz
**Run:** 14 (full audit with Justine)
**Date:** 2026-03-24
**Duration:** Phases 0-6 complete

## Before / After

| Metric | Baseline | Final |
|--------|----------|-------|
| Tests passing | 321 | 324 |
| Tests failing | 0 | 0 |
| Tests skipped | 0 | 0 |
| Test time | 2.63s | 2.67s |
| Ruff errors | 0 | 0 |
| Mypy errors | 0 | 0 |
| Coverage | 67% | 67% |
| Punchlist items | — | 8 |
| Resolved | — | 8 |
| Open | — | 0 |
| Deferred | — | 0 |

**Net new tests:** 3 (empty field, code fence, \s convention check)

## Items by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| MEDIUM | 6 | BH-001, BH-002, BH-003, BH-004, BH-005, BH-006 |
| LOW | 2 | BH-007, BH-008 |

## Items by Category

| Category | Count | IDs |
|----------|-------|-----|
| bug/logic | 2 | BH-004, BH-005 |
| design/inconsistency | 4 | BH-001, BH-002, BH-007, BH-008 |
| test/shallow | 1 | BH-003 |
| doc/drift | 1 | BH-006 |

## Key Fixes

1. **BH-004 (MEDIUM, bug/logic):** `parse_brief()` field extraction used `\s*`
   after field markers. When a field had an empty value, `\s*` consumed the
   newline and `(.*?)` captured the next field's content. Fixed by replacing
   `\s*` with `[ \t]*`. Predicted by global pattern library (regex-newline-leak).

2. **BH-005 (MEDIUM, bug/logic):** `parse_brief()` applied header regex
   directly to content without masking code fences. Pattern headers inside
   code examples were matched as real entries. Fixed by adding
   `mask_code_fences()` before header matching. This is PAT-001 family.

3. **BH-001 (MEDIUM, design/inconsistency):** `test_readme_metrics_match_actual`
   extracted 9 fields but only asserted on test count. Expanded to validate all
   9 fields (skills, agents, ref docs, examples, scripts, patterns, hooks,
   tests, lines). 4th consecutive audit summary with this recommendation.

4. **BH-002 (MEDIUM, design/inconsistency):** No CI check for `\s` convention.
   Added `test_no_backslash_s_in_source_regex` to enforce `[ \t]` convention.

5. **BH-006 (MEDIUM, doc/drift):** README "321 tests across 8,500 lines" was
   ambiguous. Updated to "324 tests across 8,600 lines of code".

6. **BH-007 (LOW, design/inconsistency):** Hook path matching uses `in` for
   substring checks. Documented as design decision — Claude Code provides
   absolute or cwd-relative paths, making these path components safe.

7. **BH-008 (LOW, design/inconsistency):** Stall detection reported "STALLED"
   for both flat and growing open item counts. Now reports "REGRESSING" when
   items are growing.

## Adversarial Self-Play Results

| Classification | Count |
|----------------|-------|
| Agreement | 2 (BH-001, BH-002) |
| Holtz-only | 3 (BH-003, BH-004, BH-005) |
| Justine-only | 3 (BH-006, BH-007, BH-008) |
| Severity disagreements | 0 |
| Contradictions | 0 |

**Blind spots:** Holtz missed README wording ambiguity (BH-006) and hook design
concerns (BH-007). Justine missed the actual code bugs in parse_brief (BH-004,
BH-005) — she noted the convention violation but tested the wrong edge cases
(CRLF, cross-entry bleeding) instead of the right ones (empty fields, code
fences).

## Prediction Accuracy

| Confidence | Predicted | Confirmed | Accuracy |
|------------|-----------|-----------|----------|
| HIGH       | 2         | 1         | 50%      |
| MEDIUM     | 2         | 1         | 50%      |
| LOW        | 1         | 0         | 0%       |
| **Total**  | **5**     | **2**     | **40%**  |

- Prediction 1 (HIGH, regex-newline-leak): CONFIRMED via BH-004
- Prediction 2 (MEDIUM, CRLF in header regex): UNCONFIRMED — `\s*$` correctly handles CRLF
- Prediction 3 (MEDIUM, code-fence-unaware): CONFIRMED via BH-005
- Prediction 4 (HIGH, README counts stale): UNCONFIRMED — counts were correct (BH-001 is about test coverage, not drift)
- Prediction 5 (LOW, hook coverage): UNCONFIRMED — hooks are tested via subprocess

## Convergence Trajectory

| Run | Findings | Severity Profile | Pattern | Tests Added |
|-----|----------|-----------------|---------|-------------|
| 12 | 6 | 4 MEDIUM, 2 LOW | None | 9 |
| 13 | 4 | 2 MEDIUM, 2 LOW | None | 1 |
| 14 | 8 | 6 MEDIUM, 2 LOW | None | 3 |

Run 14 is the first full audit with Justine since run 12. Findings increased
from 4 (targeted) to 8 (full) due to Justine's 3 net-new items and the
recommendation escalation yielding 2 items. The 2 real code bugs (BH-004,
BH-005) were both in `pattern_brief_compact.py` — the newest and least-audited
module. Both are PAT-001/PAT-003 family: the pattern library predicted them
before a line of code was read.

## Recommendations

1. **Consider adding a stall-vs-regress test** for convergence_check.py.
   The BH-008 fix changed the message but no test verifies the distinction.

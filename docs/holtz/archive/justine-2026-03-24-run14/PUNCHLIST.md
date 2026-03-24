# Holtz Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 321 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM   | 3    | 0        | 0        |
| LOW      | 2    | 0        | 0        |

## Patterns

## Items

### BJ-001: README "8,500 lines" claim is ambiguous and unvalidated
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:1` (the "What's inside" line)
**Status:** OPEN
**Lens:** contract

**Problem:** README states "321 tests across 8,500 lines" which implies the tests themselves span 8,500 lines. The actual test file line count is 6,509 (all files in tests/). The 8,500 figure matches the combined test + source + hook line count (8,545). The phrasing is misleading: "tests across N lines" naturally reads as "the test code is N lines long," not "the total codebase including production code is N lines." Additionally, the existing `test_readme_metrics_match_actual` test validates the test count (321) but does not validate the line count, so this number can drift silently.

**Evidence:** `wc -l tests/*.py` yields 6,509 total. `wc -l tests/*.py skills/holtz/scripts/*.py hooks/*.py` yields 8,545 total. README claims 8,500. The test at `tests/test_integration.py:215` extracts the line count via regex but never asserts on it -- only the test count is validated.

**Discovery Chain:** README review -> "8,500 lines" claim -> `wc -l tests/*.py` = 6,509 -> `wc -l tests/*.py + scripts/*.py + hooks/*.py` = 8,545 -> claim is ambiguous and unverified by any test

**Acceptance Criteria:**
- [ ] README "What's inside" line clarifies what "lines" refers to (test lines only, or total codebase)
- [ ] Line count is accurate for the chosen definition
- [ ] `test_readme_metrics_match_actual` validates the line count against the actual count

**Validation Command:**
```bash
python -c "
import re
from pathlib import Path
readme = Path('README.md').read_text()
m = re.search(r'(\d+) tests across ([\d,]+) lines', readme)
claimed_lines = int(m.group(2).replace(',', ''))
import subprocess
result = subprocess.run(['wc', '-l'] + list(map(str, Path('tests').glob('*.py'))) + list(map(str, Path('skills/holtz/scripts').glob('*.py'))) + list(map(str, Path('hooks').glob('*.py'))), capture_output=True, text=True)
actual = int(result.stdout.strip().split(chr(10))[-1].split()[0])
print(f'Claimed: {claimed_lines}, Actual: {actual}')
assert abs(claimed_lines - actual) <= 100, f'Line count drift: {claimed_lines} vs {actual}'
"
```

### BJ-002: test_readme_metrics_match_actual only validates 1 of 9 extracted fields
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_integration.py:215`
**Status:** OPEN
**Lens:** contract

**Problem:** The test `test_readme_metrics_match_actual` extracts all 9 numeric claims from the README "What's inside" line (skills, agents, reference docs, examples, Python scripts, seed patterns, enforcement hooks, tests, lines) but only asserts on the test count. The other 8 fields -- including reference doc count (17), script count (5), hook count (4), and seed pattern count (6) -- are extracted but never validated. Any of these counts can drift without test failure. This is a Rubber Stamp anti-pattern (checks that values exist without checking they are correct). This finding matches Holtz BH-001 on the current punchlist.

**Evidence:** Test at `tests/test_integration.py:215` contains `claimed_tests = int(m.group(8))` and `assert claimed_tests == actual_tests` but no assertions on groups 1-7 or group 9.

**Discovery Chain:** Anti-pattern scan (Rubber Stamp #11) -> test extracts 9 groups but asserts 1 -> 8 unchecked claims can drift silently -> matches Holtz BH-001

**Acceptance Criteria:**
- [ ] All 9 extracted README claims are validated against actual file counts
- [ ] Validation: changing any README count causes test failure

**Validation Command:**
```bash
python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v
```

### BJ-003: impact_graph_gate path matching uses substring containment instead of path prefix
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/impact_graph_gate.py:28-38`
**Status:** OPEN
**Lens:** security

**Problem:** The impact graph gate checks `"docs/holtz/audit/" in normalized` and `"docs/holtz/justine/" in normalized` using Python `in` operator for substring matching. This means a path like `vendor/docs/holtz/audit/file.md` or `docs/holtz/../holtz/not-audit/file.md` could theoretically match or fail to match incorrectly. In practice, Claude Code provides clean cwd-relative paths, so this is not exploitable. However, the contract between the hook and Claude Code is implicit -- the hook assumes well-formed paths without documenting or enforcing that assumption.

**Evidence:** `impact_graph_gate.py:28`: `if any(p in normalized for p in justine_paths)`. The `in` operator checks for substring anywhere in the string, not just at path prefix positions. Status_staleness_gate.py has the same pattern at line 39.

**Discovery Chain:** Security lens scan -> hook uses `in` for path matching -> `in` is substring not prefix -> theoretical false match on embedded paths -> Claude Code normalizes paths so not practically exploitable

**Acceptance Criteria:**
- [ ] Path matching documents the assumption that file_path values are clean cwd-relative paths
- [ ] OR path matching uses startswith/endswith or pathlib for proper prefix checking

**Validation Command:**
```bash
python -c "
# Verify the current behavior
path = 'vendor/docs/holtz/audit/file.md'
normalized = path.replace('\\\\', '/')
print(f'Embedded path match: {\"docs/holtz/audit/\" in normalized}')  # True = potential false match
"
```

### BJ-004: pattern_brief_compact.py uses \s in regex (convention violation)
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:41,53`
**Status:** OPEN
**Lens:** contract

**Problem:** The project convention documented in architecture-baseline.md is to use `[ \t]` instead of `\s` in source regex to prevent newline leaks (per PAT-003: regex-newline-leak). `pattern_brief_compact.py` has two `\s` usages: `\s*` on line 41 (in `_extract` function regex) and `\s*` on line 53 (in `parse_brief` header regex). While testing confirmed these usages do not cause functional bugs in the current code (the `_extract` regex intentionally uses DOTALL and the terminators prevent cross-entry bleeding), the convention violation means future edits to these patterns could introduce newline leak bugs without warning. This matches Holtz BH-002 on the current punchlist.

**Evidence:** `grep -rnP '\\s[*+?]' skills/holtz/scripts/pattern_brief_compact.py` returns 2 hits. Architecture baseline: "All regex in source uses `[ \t]` not `\s` for horizontal whitespace."

**Discovery Chain:** Convention check -> `grep` finds 2 `\s` usages -> tested functionally, no current bug -> convention violation creates future regression risk

**Acceptance Criteria:**
- [ ] All `\s` quantified usages in pattern_brief_compact.py replaced with `[ \t]` or `\n` as appropriate
- [ ] No quantified `\s` remains in skills/holtz/scripts/*.py

**Validation Command:**
```bash
grep -rnP '\\s[*+?]' skills/holtz/scripts/ && echo "FAIL" || echo "PASS"
```

### BJ-005: No test validates stall detection message distinguishes flat vs growing open items
**Severity:** LOW
**Category:** test/shallow
**Location:** `skills/holtz/scripts/convergence_check.py:272-277`
**Status:** OPEN
**Lens:** contract

**Problem:** The stall detection in `check_convergence()` fires when open items are not decreasing across 3+ iterations. This correctly catches both flat (3,3,3,3) and growing (3,4,5,6) open counts. However, the message is identical in both cases: "STALLED: N items remain open but no progress in last 3 iterations." For a growing case, "STALLED" is semantically misleading -- the situation is getting worse, not stalled. No test verifies the message content for the growing case. The functional behavior is correct (returns False in both cases), so this is a message quality issue rather than a logic bug.

**Evidence:** Tested manually: 4 snapshots with open items growing from 3 to 6 returns `(False, "STALLED: 6 items remain open...")`. The stall check uses `>=` which catches both flat and growing.

**Discovery Chain:** Adversarial testing of convergence paths -> stall detector fires on growing items -> message says "STALLED" when "REGRESSING" would be more accurate -> no test checks this distinction

**Acceptance Criteria:**
- [ ] Stall detection message distinguishes between flat (no change) and growing (regression) open item counts
- [ ] OR documentation explicitly states that "STALLED" covers both cases by design

**Validation Command:**
```bash
python -c "
import sys
sys.path.insert(0, 'skills/holtz/scripts')
import convergence_check as cc
snap = lambda n: {'timestamp': '2026-03-19T00:00:00', 'punchlist': {'OPEN': n, 'IN PROGRESS': 0, 'RESOLVED': 2, 'DEFERRED': 0, 'unknown': 0, 'total': n+2}, 'tests': {'passed': 10, 'failed': 0, 'skipped': 0}}
_, msg = cc.check_convergence([snap(3), snap(4), snap(5), snap(6)])
print(f'Growing: {msg}')
_, msg2 = cc.check_convergence([snap(3), snap(3), snap(3), snap(3)])
print(f'Flat: {msg2}')
"
```

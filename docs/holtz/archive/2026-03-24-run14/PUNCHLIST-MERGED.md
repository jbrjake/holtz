# Holtz Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 321 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM   | 0    | 6        | 0        |
| LOW      | 0    | 2        | 0        |

## Patterns

## Items

### BH-001: README metrics test only validates test count
<!-- Was: Holtz BH-001 + Justine BJ-002 -->
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `tests/test_integration.py:215`
**Status:** RESOLVED
**Found by:** both auditors

**Problem:** This recommendation has appeared in 4 consecutive audit summaries
without being fully implemented: "Automate README metrics check for all
counts". The test `test_readme_metrics_match_actual` validates the test count
but not reference doc count (claimed 17), line count (claimed 8,500), skill
count, agent count, script count, seed pattern count, or hook count. Any of
these can drift silently.

**Evidence:** Found in: run 9 (2026-03-22), run 10 (2026-03-22), run 13
(2026-03-24), Justine run 1 (2026-03-22). Current test at
test_integration.py:215 extracts all 9 fields from the regex but only asserts
on `claimed_tests`.

**Discovery Chain:** Prior summary scan → recommendation "automate README
metrics" found in 4 summaries → test exists but only checks 1 of 9 extracted
fields → 8 unchecked fields can drift silently

**Acceptance Criteria:**
- [ ] All numeric claims in README "What's inside" line are validated against actual file counts
- [ ] Validation: `python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v` passes with all fields checked

**Validation Command:**
```bash
python -m pytest tests/test_integration.py::test_readme_metrics_match_actual -v
```

### BH-002: No automated \s convention check
<!-- Was: Holtz BH-002 + Justine BJ-004 -->
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/pattern_brief_compact.py`
**Status:** RESOLVED
**Found by:** both auditors

**Problem:** This recommendation has appeared in 2 consecutive audit summaries
without being implemented: "Add \s convention check to CI". The project
convention is `[ \t]` instead of `\s` in source regex to prevent newline leaks
(PAT-003). `pattern_brief_compact.py` currently violates this convention with
`\s` on lines 41 and 53. No CI check or pre-commit hook prevents future
regressions.

**Evidence:** Found in: run 11 (2026-03-22), Justine run 11 (2026-03-22).
`grep -rn '\\s[*+?]' skills/holtz/scripts/` finds 2 hits in
pattern_brief_compact.py.

**Discovery Chain:** Prior summary scan → recommendation "add \s convention
check to CI" found in 2 summaries → `grep` confirms 2 violations exist →
CI workflow has no convention check step

**Acceptance Criteria:**
- [ ] All `\s` quantified usages in source regex replaced with `[ \t]` equivalents
- [ ] CI includes a check that prevents `\s` in source files (or a test that greps for it)
- [ ] Validation: `grep -rnP '\\s[*+?]' skills/holtz/scripts/` returns no hits

**Validation Command:**
```bash
grep -rnP '\\s[*+?]' skills/holtz/scripts/ && echo "FAIL: \\s found" || echo "PASS: no \\s"
```

### BH-003: parse_brief has no edge case tests for empty fields or code fences
<!-- Was: Holtz BH-003 -->
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_pattern_brief_compact.py`
**Status:** RESOLVED
**Found by:** Holtz only
**Predicted:** Prediction 1 (confidence: HIGH), Prediction 3 (confidence: MEDIUM)

**Problem:** `parse_brief()` has 5 tests, all using well-formed SAMPLE_BRIEF
with values on the same line as each field. No test exercises: (1) a field with
an empty value on its line, which triggers the `\s*` regex to consume the
newline and capture the next field's content; (2) a code fence containing a
`## PAT-NNN:` header, which parse_brief matches as a real entry since it
doesn't mask code fences.

**Evidence:** test_pattern_brief_compact.py SAMPLE_BRIEF has all fields
populated. `parse_brief()` at line 44 calls `header_re.finditer(content)`
without masking. The `_extract` function at line 53 uses `\s*` which matches
newlines.

**Discovery Chain:** Prediction 1 (regex-newline-leak heuristic) → verified
`\s*` in field extraction regex → checked test file → all tests use well-formed
input → empty-field and code-fence edge cases untested

**Acceptance Criteria:**
- [ ] Test exists for parse_brief with a field that has no value on its line (empty after `:**`)
- [ ] Test exists for parse_brief with a code fence containing `## PAT-NNN:` header
- [ ] Both tests assert correct behavior (empty field returns empty string, code fence header is not matched)

**Validation Command:**
```bash
python -m pytest tests/test_pattern_brief_compact.py -v -k "empty or fence"
```

### BH-004: parse_brief field extraction leaks across fields on empty values
<!-- Was: Holtz BH-004 -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:53`
**Status:** RESOLVED
**Determinism:** deterministic
**Found by:** Holtz only
**Predicted:** Prediction 1 (confidence: HIGH)
**Lens:** component

**Problem:** The `_extract()` function uses `\s*` after the field bold marker
(`**Field:**\s*`). When a field has an empty value on its line (e.g.,
`**What to look for:**\n`), `\s*` consumes the newline and `(.*?)` with DOTALL
captures content from the next field. Result: the empty field gets populated
with the next field's entire content including its bold marker.

**Evidence:** Reproduction:
```python
brief = '## PAT-001: test (Run 1, 2026-03-20)\n**What to look for:**\n**Detection heuristic:** `grep foo`\n**Example:** bar\n'
entries = parse_brief(brief)
# entries[0].what_to_look_for == '**Detection heuristic:** `grep foo`'
# Expected: ''
```

**Discovery Chain:** Global pattern regex-newline-leak heuristic → `\s*` on
line 53 matches newline → tested with empty field → confirmed content bleed
from next field

**Acceptance Criteria:**
- [ ] `\s*` replaced with `[ \t]*` in the _extract regex (line 53)
- [ ] parse_brief returns empty string for fields with no value on their line
- [ ] Existing tests still pass

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'skills/holtz/scripts')
from pattern_brief_compact import parse_brief
brief = '## PAT-001: test (Run 1, 2026-03-20)\n**What to look for:**\n**Detection heuristic:** \`grep\`\n**Example:** bar\n'
e = parse_brief(brief)
assert e[0].what_to_look_for == '', f'Expected empty, got: {e[0].what_to_look_for}'
print('PASS')
"
```

### BH-005: parse_brief matches pattern headers inside code fences
<!-- Was: Holtz BH-005 -->
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:44`
**Status:** RESOLVED
**Determinism:** deterministic
**Found by:** Holtz only
**Predicted:** Prediction 3 (confidence: MEDIUM)
**Lens:** component

**Problem:** `parse_brief()` applies `header_re.finditer(content)` directly to
content without masking code fences. If the pattern brief contains a code
example with a `## PAT-NNN: name (Run N, YYYY-MM-DD)` header inside a code
fence, parse_brief matches it as a real entry. This is the same root cause
family as PAT-001 (code-fence-unaware parsing).

**Evidence:** Reproduction:
```python
brief = '## PAT-001: real (Run 1, 2026-03-20)\n...\n```\n## PAT-999: fake (Run 99, 2099-01-01)\n```\n'
entries = parse_brief(brief)
# len(entries) == 2 — PAT-999 matched inside code fence
# Expected: len(entries) == 1
```

**Discovery Chain:** Code-fence-unaware-parsing heuristic → parse_brief uses
finditer(content) without masking → tested with fenced header → confirmed
false match

**Acceptance Criteria:**
- [ ] parse_brief masks code fences before applying header regex
- [ ] Pattern headers inside code fences are not matched
- [ ] Existing tests still pass

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'skills/holtz/scripts')
from pattern_brief_compact import parse_brief
brief = '## PAT-001: real (Run 1, 2026-03-20)\n**What to look for:** x\n**Detection heuristic:** y\n**Example:** z\n\n\`\`\`\n## PAT-999: fake (Run 99, 2099-01-01)\n\`\`\`\n'
assert len(parse_brief(brief)) == 1, 'Code fence header matched as real entry'
print('PASS')
"
```

### BH-006: README line count phrasing is ambiguous
<!-- Was: Justine BJ-001 -->
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:172`
**Status:** RESOLVED
**Found by:** Justine only
**Lens:** contract

**Problem:** README states "321 tests across 8,500 lines" which reads as "the
test code spans 8,500 lines." The actual test file line count is 6,509. The
8,500 figure matches the combined test + source + hook line count (8,545).
The phrasing is misleading.

**Evidence:** `wc -l tests/*.py` yields 6,509 total. `wc -l tests/*.py
skills/holtz/scripts/*.py hooks/*.py` yields 8,545 total. README claims 8,500.

**Discovery Chain:** README review → "8,500 lines" claim → `wc -l tests/*.py`
= 6,509 → total codebase = 8,545 → phrasing is ambiguous

**Acceptance Criteria:**
- [ ] README "What's inside" line clarifies what "lines" refers to (e.g., "8,500 lines of code" or "across 8,500 total lines")
- [ ] Line count is accurate for the chosen definition

**Validation Command:**
```bash
python -c "
from pathlib import Path
total = sum(1 for f in list(Path('tests').glob('*.py')) + list(Path('skills/holtz/scripts').glob('*.py')) + list(Path('hooks').glob('*.py')) for _ in open(f))
print(f'Total lines: {total}')
"
```

### BH-007: Hook path matching uses substring containment
<!-- Was: Justine BJ-003 -->
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `hooks/impact_graph_gate.py:35-37`
**Status:** RESOLVED
**Found by:** Justine only
**Lens:** security

**Problem:** The impact graph gate checks paths using Python `in` operator
for substring matching (e.g., `"docs/holtz/audit/" in normalized`). A path
like `vendor/docs/holtz/audit/file.md` would theoretically match. Not
practically exploitable because Claude Code provides clean cwd-relative paths.

**Evidence:** `impact_graph_gate.py:35`: `any(p in normalized for p in
justine_paths)`. `status_staleness_gate.py:39` has the same pattern.

**Discovery Chain:** Security lens scan → hook uses `in` for path matching →
`in` is substring not prefix → theoretical false match on embedded paths →
Claude Code normalizes paths so not practically exploitable

**Acceptance Criteria:**
- [ ] Path matching documents the assumption that paths are clean cwd-relative
- [ ] OR path matching uses startswith or pathlib for proper prefix checking

**Validation Command:**
```bash
python -c "print('docs/holtz/audit/' in 'vendor/docs/holtz/audit/file.md')"
```

### BH-008: Stall detection message doesn't distinguish flat vs growing
<!-- Was: Justine BJ-005 -->
**Severity:** LOW
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/convergence_check.py:272-277`
**Status:** RESOLVED
**Found by:** Justine only
**Lens:** contract

**Problem:** The stall detection reports "STALLED" for both flat (3,3,3,3) and
growing (3,4,5,6) open item counts. For a growing case, "STALLED" is
misleading — the situation is regressing. The functional behavior is correct
(returns False in both cases).

**Evidence:** Stall check uses `>=` which catches both flat and growing. Same
message for both cases.

**Discovery Chain:** Adversarial testing of convergence paths → stall detector
fires on growing items → message says "STALLED" when "REGRESSING" more
accurate → no test checks this distinction

**Acceptance Criteria:**
- [ ] Stall message distinguishes flat vs growing open items
- [ ] OR documentation states "STALLED" covers both cases by design

**Validation Command:**
```bash
python -c "
import sys; sys.path.insert(0, 'skills/holtz/scripts')
import convergence_check as cc
snap = lambda n: {'timestamp': '2026-03-19T00:00:00', 'punchlist': {'OPEN': n, 'IN PROGRESS': 0, 'RESOLVED': 2, 'DEFERRED': 0, 'unknown': 0, 'total': n+2}, 'tests': {'passed': 10, 'failed': 0, 'skipped': 0}}
_, msg = cc.check_convergence([snap(3), snap(4), snap(5), snap(6)])
print(f'Growing: {msg}')
"
```

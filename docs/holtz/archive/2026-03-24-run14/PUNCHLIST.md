# Holtz Punchlist
> Generated: 2026-03-24 | Project: holtz | Baseline: 321 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| MEDIUM   | 5    | 0        | 0        |

## Patterns

## Items

### BH-001: README metrics test only validates test count
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `tests/test_integration.py:215`
**Status:** OPEN

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
**Severity:** MEDIUM
**Category:** design/inconsistency
**Location:** `skills/holtz/scripts/pattern_brief_compact.py`
**Status:** OPEN

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
**Severity:** MEDIUM
**Category:** test/shallow
**Location:** `tests/test_pattern_brief_compact.py`
**Status:** OPEN
**Predicted:** Prediction 1 (confidence: HIGH), Prediction 3 (confidence: MEDIUM)

**Problem:** `parse_brief()` has 5 tests, all using well-formed SAMPLE_BRIEF
with values on the same line as each field. No test exercises: (1) a field with
an empty value on its line, which would trigger the `\s*` regex to consume the
newline and potentially capture the next field's content; (2) a code fence
containing a `## PAT-NNN:` header, which parse_brief would match as a real
entry since it doesn't mask code fences.

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
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:53`
**Status:** OPEN
**Determinism:** deterministic
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
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/pattern_brief_compact.py:44`
**Status:** OPEN
**Determinism:** deterministic
**Predicted:** Prediction 3 (confidence: MEDIUM)
**Lens:** component

**Problem:** `parse_brief()` applies `header_re.finditer(content)` directly to
content without masking code fences. If the pattern brief contains a code
example with a `## PAT-NNN: name (Run N, YYYY-MM-DD)` header inside a code
fence, parse_brief matches it as a real entry. This is the same root cause
family as PAT-001 (code-fence-unaware parsing).

**Evidence:** Reproduction:
```python
brief = '## PAT-001: real (Run 1, 2026-03-20)\n**What to look for:** x\n**Detection heuristic:** y\n**Example:** z\n\n```\n## PAT-999: fake (Run 99, 2099-01-01)\n**What to look for:** should not match\n```\n'
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

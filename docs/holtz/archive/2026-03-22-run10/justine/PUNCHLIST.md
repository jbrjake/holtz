# Holtz Punchlist
> Generated: 2026-03-22 | Project: holtz | Baseline: 261 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 4 | 0 | 0 |
| MEDIUM | 4 | 0 | 0 |
| LOW | 2 | 0 | 0 |

## Patterns

## Items

### BH-101: Empty types list treated as no filter in neighbors() and blast_radius()
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/impact_graph.py:149`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract

**Problem:** `neighbors()` and `blast_radius()` treat `types=[]` as `types=None` (no filter) because `[]` is falsy in Python. An empty list is semantically "filter to no types" (return nothing), but the implementation returns everything. This is documented with tests that explicitly assert the current behavior, but the contract is wrong -- an empty list should mean "match nothing", not "match everything".

**Evidence:** `impact_graph.py:149`: `type_set = set(types) if types else None` -- `set([])` is `set()` which is also falsy, so even `set(types)` wouldn't help. But the truthiness check on the input list means `[]` maps to `None`. Tests `test_neighbors_empty_types_is_no_filter` and `test_blast_radius_empty_types_is_no_filter` document this behavior but don't question whether it's correct.

**Discovery Chain:** read neighbors() → saw `if types` guard → `[]` is falsy → empty list treated as "no filter" → contract violation

**Acceptance Criteria:**
- [ ] `types=[]` returns empty result (filter to zero types matches nothing)
- [ ] Test updated to verify empty list behavior is "match nothing"
- [ ] Or: explicit documentation that empty list means "no filter" (if this is intentional)

**Validation Command:**
```bash
python -c "from impact_graph import ImpactGraph; g = ImpactGraph('/dev/null'); g.add_node('a','function','a.py'); g.add_node('b','function','b.py'); g.add_edge('a','b','calls'); print(g.neighbors('a', types=[]))"
```

### BH-102: os.rename not atomic on Windows when target exists
**Severity:** LOW
**Category:** bug/error-handling
**Location:** `skills/holtz/scripts/impact_graph.py:76`, `skills/holtz/scripts/convergence_check.py:266`
**Status:** OPEN
**Determinism:** theoretical
**Lens:** error-propagation

**Problem:** Both `ImpactGraph.save()` and `save_history()` use `os.rename(tmp_path, str(target))` for atomic writes. The comment says "os.rename is atomic on POSIX for same-filesystem renames" but on Windows, `os.rename` raises `OSError` if the target already exists. This would cause data loss (temp file deleted in except handler, original file still exists but was the target of a failed rename). `os.replace()` is atomic on both POSIX and Windows.

**Evidence:** `impact_graph.py:76`: `os.rename(tmp_path, str(self.path))`. `convergence_check.py:266`: `os.rename(tmp_path, str(target))`. Python docs: "On Windows, if dst exists, OSError will be raised... os.replace() is the same as os.rename() but if dst exists, it is replaced silently."

**Discovery Chain:** read save() → saw os.rename → checked Python docs → os.rename fails on Windows if target exists → os.replace is the correct function

**Acceptance Criteria:**
- [ ] Both save functions use `os.replace()` instead of `os.rename()`
- [ ] Test verifies overwrite of existing file works

**Validation Command:**
```bash
grep -n 'os\.rename' skills/holtz/scripts/impact_graph.py skills/holtz/scripts/convergence_check.py
```

### BH-103: detect_test_runner false positive on pyproject.toml with [tool.pytest] in TOML value
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:94`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow

**Problem:** `detect_test_runner` checks for `[tool.pytest` at the start of a line in pyproject.toml using `re.search(r'^\[tool\.pytest[\].]', content, re.MULTILINE)`. This regex matches `[tool.pytest.ini_options]` correctly. However, TOML allows multiline strings and array values. A line like `requires = ["[tool.pytest]"]` would match the regex even though it's inside a string value. The regex does not parse TOML -- it does substring matching on raw text.

**Evidence:** `convergence_check.py:94`: `if not re.search(r'^\[tool\.pytest[\].]', content, re.MULTILINE): continue`. A pyproject.toml with `dependencies = [\n"[tool.pytest]"\n]` would have `[tool.pytest]` at the start of a line inside a string literal, matching the regex.

**Discovery Chain:** read detect_test_runner → regex matches raw lines → TOML string values can start at column 0 → false positive on values containing bracket text

**Acceptance Criteria:**
- [ ] Test added: pyproject.toml with `[tool.pytest]` inside a TOML string value does NOT trigger detection
- [ ] Or: documented as known limitation with comment in code

**Validation Command:**
```bash
python -c "
import convergence_check as cc
from pathlib import Path
import tempfile, os
d = tempfile.mkdtemp()
p = Path(d) / 'pyproject.toml'
p.write_text('[build-system]\nrequires = [\n\"[tool.pytest]\"\n]\n')
print(cc.detect_test_runner(project_root=Path(d)))
"
```

### BH-104: status_staleness_gate allows bypass when STATUS.md is deleted mid-run
**Severity:** HIGH
**Category:** bug/security
**Location:** `hooks/status_staleness_gate.py:53`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** security
**Predicted:** Prediction 3 (confidence: MEDIUM)

**Problem:** The staleness gate allows all writes when STATUS.md does not exist (`if not os.path.isfile(status_path): exit_ok()`). This is intended for the first write of a run, but it means that if STATUS.md is accidentally or deliberately deleted mid-run, the staleness check is completely bypassed for all subsequent writes. The hook cannot distinguish "STATUS.md hasn't been created yet" from "STATUS.md was deleted."

**Evidence:** `status_staleness_gate.py:53`: `if not os.path.isfile(status_path): exit_ok()`. No check for whether other docs/holtz/ files already exist (which would indicate a run is in progress and STATUS.md should exist).

**Discovery Chain:** read staleness gate → "not exist" path exits OK → deleting STATUS.md bypasses all staleness checks → enforcement gap

**Acceptance Criteria:**
- [ ] When STATUS.md does not exist but other docs/holtz/ files do exist, the hook warns or blocks (run in progress without program counter)
- [ ] Test added for this scenario

**Validation Command:**
```bash
python -c "
import json, subprocess, sys, os, tempfile
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, 'docs', 'holtz', 'recon'), exist_ok=True)
open(os.path.join(d, 'docs', 'holtz', 'recon', '0a.md'), 'w').write('data')
# STATUS.md does NOT exist but recon files do
event = {'tool_input': {'file_path': os.path.join(d, 'docs', 'holtz', 'PUNCHLIST.md')}, 'cwd': d}
r = subprocess.run([sys.executable, 'hooks/status_staleness_gate.py'], input=json.dumps(event), capture_output=True, text=True)
print(f'Exit code: {r.returncode}')  # Expected: non-zero (run in progress). Actual: 0 (bypass)
"
```

### BH-105: impact_graph_gate only gates "audit/" subdirectory, not PUNCHLIST.md or other Phase 1+ files
**Severity:** HIGH
**Category:** bug/logic
**Location:** `hooks/impact_graph_gate.py:30-35`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract

**Problem:** The impact graph gate is intended to enforce that Phase 1+ audit files cannot be written without a live impact graph. But it only checks writes to `docs/holtz/audit/` or `docs/holtz/justine/audit/`. PUNCHLIST.md, investigation files, and other Phase 1+ artifacts are written to `docs/holtz/PUNCHLIST.md` and `docs/holtz/investigations/` -- paths that are not gated. The HARD-GATE described in the skill file says "Before any write to a Phase 1+ audit file" but the hook implementation is narrower than the requirement.

**Evidence:** `impact_graph_gate.py:30-35`:
```python
if "docs/holtz/justine/audit/" in normalized:
    required = "docs/holtz/justine/impact-graph.json"
elif "docs/holtz/audit/" in normalized:
    required = "docs/holtz/impact-graph.json"
else:
    exit_ok()
```
Writes to `docs/holtz/PUNCHLIST.md` or `docs/holtz/justine/PUNCHLIST.md` pass through without checking the graph.

**Discovery Chain:** read impact_graph_gate → only checks "audit/" subdir → PUNCHLIST.md bypasses gate → enforcement gap wider than intended

**Acceptance Criteria:**
- [ ] Hook gates writes to PUNCHLIST.md, investigations/, and other Phase 1+ output files
- [ ] Or: hook documentation updated to clarify it only gates audit/ directory

**Validation Command:**
```bash
python -c "
import json, subprocess, sys, tempfile
d = tempfile.mkdtemp()
event = {'tool_input': {'file_path': d + '/docs/holtz/PUNCHLIST.md'}, 'cwd': d}
r = subprocess.run([sys.executable, 'hooks/impact_graph_gate.py'], input=json.dumps(event), capture_output=True, text=True)
print(f'Exit: {r.returncode}')  # Expected: 2 (blocked). Actual: 0 (allowed)
"
```

### BH-106: No test for convergence_check save_history atomic write correctness
**Severity:** MEDIUM
**Category:** test/missing
**Location:** `tests/test_convergence_check.py`
**Status:** OPEN
**Lens:** integration

**Problem:** `save_history()` performs atomic writes using tempfile + rename. There is no test that verifies the round-trip: save history, reload it, verify contents match. The `load_history()` function has tests for corrupt files and missing files, but no test verifies that `save_history()` produces output that `load_history()` can read back correctly. This is the kind of integration test that catches silent data corruption.

**Evidence:** Searched test_convergence_check.py for "save_history" -- no test calls save_history then load_history to verify round-trip. The function is only tested indirectly through `main()`.

**Discovery Chain:** searched test file for save_history → no round-trip test → atomic write correctness untested → integration gap

**Acceptance Criteria:**
- [ ] Test writes history via save_history(), reads back via load_history(), asserts equality
- [ ] Test verifies overwrite of existing history file preserves new data

**Validation Command:**
```bash
python -m pytest tests/test_convergence_check.py -k save_history -v 2>&1 | head -5
```

### BH-107: subagent_findings_check regex matches paths inside code fences without masking
**Severity:** LOW
**Category:** bug/logic
**Location:** `hooks/subagent_findings_check.py:33`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow

**Problem:** The subagent findings check scans the raw message text for `docs/holtz/*.md` paths using regex. It does not mask code fences, so paths mentioned in code examples (e.g., in a markdown code block showing the expected file structure) will trigger false positive warnings. The docstring acknowledges this ("Path extraction operates on raw message text without code-fence masking... This is acceptable because the hook only warns") and the hook uses exit(1) not exit(2), so this is a known limitation with intentional mitigation. Filing as LOW because the docstring documents the trade-off.

**Evidence:** `subagent_findings_check.py:33`: `paths = re.findall(r'docs/holtz/[^\s"\')\]]+\.md', message)` -- no code fence awareness. Docstring at line 9-12 documents the limitation.

**Discovery Chain:** read subagent hook → regex on raw text → paths in code fences trigger warnings → documented trade-off but still produces noise

**Acceptance Criteria:**
- [ ] Document the false positive rate from code fence paths in hook comments
- [ ] Or: add optional code fence masking using markdown_utils (would require import path change)

**Validation Command:**
```bash
python -c "
import json, subprocess, sys
event = {'last_assistant_message': 'Example:\n\`\`\`\ndocs/holtz/PUNCHLIST.md\n\`\`\`', 'cwd': '/tmp'}
r = subprocess.run([sys.executable, 'hooks/subagent_findings_check.py'], input=json.dumps(event), capture_output=True, text=True)
print(f'Exit: {r.returncode}, stderr: {r.stderr}')  # Will warn about missing file
"
```

### BH-108: Vitest parser regex does not match "Tests" line with failed-only output
**Severity:** MEDIUM
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:162`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow

**Problem:** The Vitest parser regex `r'^\s*Tests\s+(.+\d+ (?:passed|failed))'` requires the line to end with either "passed" or "failed". But Vitest can output a line like `Tests  5 failed (5)` without any "passed" component. The regex requires the line to contain the word "passed" or "failed" as the last word before the capture group ends. If Vitest outputs only `Tests  5 skipped (5)` (all tests skipped, none passed or failed), the regex would not match at all, returning None. This is an edge case but violates the invariant that parsers should handle any valid output.

**Evidence:** `convergence_check.py:162`: `vitest_line = re.search(r'^\s*Tests\s+(.+\d+ (?:passed|failed))', output, re.MULTILINE)`. The regex requires either "passed" or "failed" to appear. A Vitest run where all tests are skipped (`Tests  5 skipped (5)`) would return None.

**Discovery Chain:** read vitest parser regex → requires "passed" or "failed" → all-skipped output has neither → returns None for valid output

**Acceptance Criteria:**
- [ ] Vitest parser handles all-skipped output (no passed, no failed)
- [ ] Test added for vitest all-skipped scenario

**Validation Command:**
```bash
python -c "
import convergence_check as cc
import subprocess
def fake(*a, **kw):
    class R: pass
    r = R(); r.stdout = ' Test Files  1 skipped (1)\n      Tests  3 skipped (3)\n   Duration  100ms\n'; r.stderr = ''; r.returncode = 0
    return r
import types
subprocess.run = fake
print(cc.get_test_counts('vitest'))  # Expected: {passed:0, failed:0, skipped:3}. Actual: None
"
```

### BH-109: Go test parser counts subtests through pattern exclusion, but pattern could match non-test lines
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/convergence_check.py:191`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** data-flow

**Problem:** The Go test parser uses `r'^--- PASS: \w+[ (]'` to match top-level test results, relying on the pattern `\w+[ (]` to exclude subtests (which contain `/` in their names). However, `\w` matches `[a-zA-Z0-9_]` only, and Go test names can contain only those characters, so the exclusion works. But the pattern `[ (]` requires either a space or open-paren after the test name. Go's verbose output format is `--- PASS: TestName (duration)`. If Go changes its output format (e.g., adds a colon or newline), the pattern silently returns None. More critically, the regex also matches if the string `--- PASS: ` appears in test output (e.g., a test that prints its own status).

**Evidence:** `convergence_check.py:191`: `passed = len(re.findall(r'^--- PASS: \w+[ (]', output, re.MULTILINE))`. This relies on Go's exact output format. The Go test runner DOES print in this exact format, and subtests use `/` which `\w` correctly excludes. But test functions that `fmt.Println("--- PASS: FakeTest (0.00s)")` would inflate the count.

**Discovery Chain:** read Go parser → regex depends on exact output format → fake output in test stdout could inflate count → no test for this edge case

**Acceptance Criteria:**
- [ ] Test added: Go test that prints fake PASS/FAIL lines in stdout does not inflate counts
- [ ] Or: regex anchored more specifically to Go's output format

**Validation Command:**
```bash
python -c "
import convergence_check as cc
import subprocess
def fake(*a, **kw):
    class R: pass
    r = R()
    r.stdout = '=== RUN   TestReal\n--- PASS: TestReal (0.00s)\nTest output: --- PASS: FakeTest (injected)\nPASS\nok\n'
    r.stderr = ''; r.returncode = 0
    return r
subprocess.run = fake
result = cc.get_test_counts('go')
print(result)  # passed should be 1, not 2
"
```

### BH-110: Punchlist validator hardcoded to BH- prefix, cannot parse Justine's BJ- namespace
**Severity:** HIGH
**Category:** bug/logic
**Location:** `skills/holtz/scripts/validate_punchlist.py:84`
**Status:** OPEN
**Determinism:** deterministic
**Lens:** contract

**Problem:** The punchlist parser regex is hardcoded to `r'^### (BH-\d+):[ \t]*(.*)$'` which only matches items with the `BH-` prefix. The architecture baseline documents that Justine uses `BJ-NNN` namespace. Any punchlist written by Justine with BJ- prefixed items would be invisible to the validator and convergence checker. The same issue exists in convergence_check.py count_items at line 43.

**Evidence:** `validate_punchlist.py:84`: `item_pattern = re.compile(r'^### (BH-\d+):[ \t]*(.*)$', re.MULTILINE)`. `convergence_check.py:43`: `item_pattern = re.compile(r'^### BH-\d+:', re.MULTILINE)`. Architecture baseline: "Punchlist items: `BH-NNN` namespace (Holtz), `BJ-NNN` namespace (Justine)".

**Discovery Chain:** tried to validate Justine punchlist with BJ- prefix → validator found 0 items → traced to hardcoded BH- regex → architecture says BJ- is valid

**Acceptance Criteria:**
- [ ] Both parsers accept BJ- prefix in addition to BH-
- [ ] Test added for BJ-prefixed items
- [ ] convergence_check.py count_items also updated

**Validation Command:**
```bash
python -c "
import validate_punchlist as vp
content = '### BJ-001: Test\n**Severity:** HIGH\n**Category:** bug/logic\n**Status:** OPEN\n'
items = vp.parse_punchlist(content)
print(f'Items found: {len(items)}')  # Expected: 1. Actual: 0
"
```

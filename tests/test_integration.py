"""Integration tests: validate_punchlist + convergence_check parse the same format."""

import convergence_check as cc
import validate_punchlist as vp

# A realistic multi-status punchlist that both parsers must agree on.
SHARED_PUNCHLIST = """\
# Bug Hunter Punchlist
> Generated: 2026-03-21 | Project: test | Baseline: 50 pass, 0 fail, 0 skip

## Summary
| Severity | Open | Resolved | Deferred |
|----------|------|----------|----------|
| HIGH | 1 | 1 | 0 |
| MEDIUM | 0 | 1 | 1 |

## Patterns

## Items

### BH-001: Auth bypass via token reuse
**Severity:** HIGH
**Category:** bug/security
**Location:** `auth.py:42`
**Status:** OPEN
**Determinism:** deterministic

**Problem:** Expired tokens are accepted because expiry check uses wrong clock source.

**Evidence:** `auth.py:42` calls `time.time()` but tokens use `datetime.utcnow()`.

**Discovery Chain:** observed expired token accepted → traced to clock mismatch

**Acceptance Criteria:**
- [ ] Token expiry uses consistent clock source
- [ ] Test with expired token fails auth

**Validation Command:**
```bash
pytest -k token_expiry
```

### BH-002: SQL injection in search
**Severity:** HIGH
**Category:** bug/security
**Location:** `search.py:15`
**Status:** RESOLVED
**Determinism:** deterministic

**Problem:** User input interpolated directly into SQL query string.

**Evidence:** `search.py:15`: `f"SELECT * FROM users WHERE name = '{user_input}'"`.

**Discovery Chain:** code review → found string interpolation → confirmed injectable

**Acceptance Criteria:**
- [x] Parameterized queries used
- [x] Injection test passes

**Validation Command:**
```bash
pytest -k sql_injection
```

**Resolution:** Fixed in commit abc123. Parameterized query, validated by injection test.

### BH-003: Stale cache after delete
**Severity:** MEDIUM
**Category:** bug/state
**Location:** `cache.py:55`
**Status:** DEFERRED
**Determinism:** intermittent

**Problem:** Cache not invalidated on delete. Deleted users appear for up to 5 minutes.

**Evidence:** `cache.py:55` has `set()` in `getUser()` but `deleteUser()` does not call `cache.del()`.

**Discovery Chain:** user report → reproduced in staging → traced to missing invalidation

**Acceptance Criteria:**
- [ ] deleteUser() invalidates cache entry

**Validation Command:**
```bash
pytest -k cache_delete
```

### BH-004: README claims feature X exists
**Severity:** MEDIUM
**Category:** doc/drift
**Location:** `README.md:15`
**Status:** RESOLVED

**Problem:** README claims feature X exists but it was removed in v2.

**Evidence:** grep for feature X in codebase returns no results.

**Discovery Chain:** doc review → feature claim → grep confirms removal

**Acceptance Criteria:**
- [x] README updated

**Validation Command:**
```bash
grep -r "feature X" README.md
```

**Resolution:** README updated to remove feature X reference in commit def456.
"""


def test_item_count_agreement(tmp_path):
    """Both parsers should find the same number of items."""
    vp_items = vp.parse_punchlist(SHARED_PUNCHLIST)
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(SHARED_PUNCHLIST)
    cc_counts = cc.count_items(punchlist)
    assert len(vp_items) == cc_counts["total"]


def test_status_distribution_agreement(tmp_path):
    """Both parsers should agree on status counts."""
    vp_items = vp.parse_punchlist(SHARED_PUNCHLIST)
    vp_counts = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0}
    for item in vp_items:
        if item.status in vp_counts:
            vp_counts[item.status] += 1
        else:
            vp_counts["unknown"] += 1

    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(SHARED_PUNCHLIST)
    cc_counts = cc.count_items(punchlist)

    for status in ("OPEN", "IN PROGRESS", "RESOLVED", "DEFERRED", "unknown"):
        assert vp_counts[status] == cc_counts[status], (
            f"Status '{status}': validate_punchlist says {vp_counts[status]}, "
            f"convergence_check says {cc_counts[status]}"
        )


def test_code_fence_immunity_agreement(tmp_path):
    """Both parsers should ignore items inside code fences."""
    content = """\
# Bug Hunter Punchlist
## Summary
## Items

### BH-001: Real item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Example punchlist:
```markdown
### BH-002: Phantom item
**Status:** RESOLVED
```

**Discovery Chain:** found X → leads to Y

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    vp_items = vp.parse_punchlist(content)
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(content)
    cc_counts = cc.count_items(punchlist)

    assert len(vp_items) == 1, f"validate_punchlist found {len(vp_items)} items, expected 1"
    assert cc_counts["total"] == 1, f"convergence_check found {cc_counts['total']} items, expected 1"
    assert vp_items[0].status == "OPEN"
    assert cc_counts["OPEN"] == 1


def test_trailing_status_text_agreement(tmp_path):
    """Both parsers should handle trailing text after status the same way."""
    content = """\
### BH-001: Test item
**Severity:** HIGH
**Category:** bug/logic
**Location:** `file.py:1`
**Status:** OPEN but see notes

**Problem:** This is a real problem that describes what went wrong in enough detail.

**Evidence:** Evidence content here with enough detail to pass threshold.

**Acceptance Criteria:**
- [ ] Fix the bug

**Validation Command:**
```bash
echo test
```
"""
    vp_items = vp.parse_punchlist(content)
    punchlist = tmp_path / "PUNCHLIST.md"
    punchlist.write_text(content)
    cc_counts = cc.count_items(punchlist)

    assert vp_items[0].status == "OPEN"
    assert cc_counts["OPEN"] == 1
    assert cc_counts["unknown"] == 0


def test_readme_metrics_match_actual():
    """README component counts match actual file counts.

    This test automates the README metrics check that was a recurring
    recommendation across Holtz runs 9-11. If this test fails, update
    the counts on the 'What's inside' line of README.md.
    """
    import re
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text()

    # Extract claimed counts from README
    m = re.search(
        r"(\d+) skills?, (\d+) agents?, (\d+) reference docs?, (\d+) examples?, "
        r"(\d+) Python scripts?, (\d+) seed patterns?, (\d+) enforcement hooks?, "
        r"(\d+) tests across ([\d,]+) lines",
        readme,
    )
    assert m, "Could not find 'What's inside' line in README.md"

    claimed_skills = int(m.group(1))
    claimed_agents = int(m.group(2))
    claimed_ref_docs = int(m.group(3))
    claimed_examples = int(m.group(4))
    claimed_scripts = int(m.group(5))
    claimed_patterns = int(m.group(6))
    claimed_hooks = int(m.group(7))
    claimed_tests = int(m.group(8))
    claimed_lines = int(m.group(9).replace(",", ""))

    # Count actual values
    actual_skills = len(list((root / "skills").rglob("SKILL.md")))
    actual_agents = len(list((root / "agents").glob("*.md")))
    actual_ref_docs = len(list((root / "skills" / "holtz" / "references").glob("*.md")))
    actual_examples = len(list((root / "skills" / "holtz" / "examples").glob("*.md")))
    actual_scripts = len(list((root / "skills" / "holtz" / "scripts").glob("*.py")))
    actual_patterns = len(list((root / "skills" / "holtz" / "patterns").glob("*.md")))
    actual_hooks = len([f for f in (root / "hooks").glob("*.py") if f.name != "_common.py"])

    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "--co", "-q"],
        capture_output=True, text=True, cwd=str(root),
    )
    test_line = result.stdout.strip().split("\n")[-1]
    actual_tests = int(re.search(r"(\d+) test", test_line).group(1))

    actual_lines = 0
    for d in [root / "tests", root / "skills" / "holtz" / "scripts", root / "hooks"]:
        for f in d.glob("*.py"):
            actual_lines += len(f.read_text().splitlines())

    errors = []
    for label, claimed, actual in [
        ("skills", claimed_skills, actual_skills),
        ("agents", claimed_agents, actual_agents),
        ("reference docs", claimed_ref_docs, actual_ref_docs),
        ("examples", claimed_examples, actual_examples),
        ("Python scripts", claimed_scripts, actual_scripts),
        ("seed patterns", claimed_patterns, actual_patterns),
        ("enforcement hooks", claimed_hooks, actual_hooks),
        ("tests", claimed_tests, actual_tests),
    ]:
        if claimed != actual:
            errors.append(f"{label}: README says {claimed}, actual {actual}")

    # Line count: allow ±100 tolerance for rounding (README says "8,500" for 8,545)
    if abs(claimed_lines - actual_lines) > 100:
        errors.append(f"lines: README says {claimed_lines}, actual {actual_lines}")

    assert not errors, (
        "README 'What's inside' counts are stale. Update README.md:\n  "
        + "\n  ".join(errors)
    )


def test_no_backslash_s_in_source_regex():
    r"""Source regex must use [ \t] not \s for horizontal whitespace (PAT-003).

    The project convention documented in architecture-baseline.md is to use
    [ \t] instead of \s in regex to prevent newline leaks. This test prevents
    regression. BH-002 run 14.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    scripts_dir = root / "skills" / "holtz" / "scripts"

    violations = []
    for py_file in sorted(scripts_dir.glob("*.py")):
        content = py_file.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            # Skip comments and docstrings (rough heuristic: lines starting
            # with # or inside triple quotes are not regex)
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # Look for \s with quantifier in regex context (inside r'' or r"")
            if re.search(r"r['\"].*\\s[*+?]", line):
                violations.append(f"{py_file.name}:{i}: {stripped}")

    assert not violations, (
        "Source regex uses \\s instead of [ \\t]. "
        "Replace \\s with [ \\t] to prevent newline leaks:\n  "
        + "\n  ".join(violations)
    )

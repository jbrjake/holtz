#!/usr/bin/env python3
"""
Holtz Audit Utilities

Punchlist parsing, test runner detection, and test suite execution.
Convergence enforcement is now handled by the Sahjhan engine.
"""

import re
import subprocess
from pathlib import Path

from markdown_utils import mask_code_fences


def count_items(punchlist_path: Path) -> dict:
    """Count punchlist items by status.

    Only counts Status fields that appear within item blocks (between
    ``### BH-NNN:`` headers).  Status fields in Pattern descriptions,
    preamble text, or item prose outside the first Status field per block
    are ignored.
    """
    if not punchlist_path.exists():
        raise FileNotFoundError(
            f"{punchlist_path} not found. "
            "Provide a valid punchlist path or let auto-detection find it."
        )
    content = punchlist_path.read_text()
    _, masked = mask_code_fences(content)
    counts = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0}

    # Split on item headers so we only look inside item blocks.
    # Supports both BH- (Holtz) and BJ- (Justine) namespaces.
    item_pattern = re.compile(r'^### B[HJ]-\d+:', re.MULTILINE)
    item_starts = [m.start() for m in item_pattern.finditer(masked)]

    for idx, start in enumerate(item_starts):
        end = item_starts[idx + 1] if idx + 1 < len(item_starts) else len(masked)
        block = masked[start:end]
        # Take only the FIRST Status field per item block.
        status_match = re.search(r'\*\*Status:\*\*[ \t]*(OPEN|IN PROGRESS|RESOLVED|DEFERRED)', block)
        if status_match:
            status = status_match.group(1)
            if status in counts:
                counts[status] += 1
            else:
                counts["unknown"] += 1
        else:
            counts["unknown"] += 1

    counts["total"] = sum(counts.values())
    return counts


def detect_test_runner(project_root: Path | None = None) -> str | None:
    """Auto-detect the project's test runner.

    Args:
        project_root: Directory to search for config files. Defaults to cwd.
    """
    root = project_root or Path(".")
    # Priority order matters: first match wins. Ordered by specificity —
    # Dict insertion order IS the detection priority (CPython 3.7+ guarantees
    # dict ordering). pytest first (most common Python runner), then JS runners,
    # then compiled-language runners. A project with both conftest.py and
    # jest.config.js will detect pytest. Do NOT reorder without updating tests.
    markers = {
        "pytest": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
        "jest": ["jest.config.js", "jest.config.ts"],
        "vitest": ["vitest.config.ts", "vitest.config.js"],
        "cargo": ["Cargo.toml"],
        "go": ["go.mod"],
        "swift": ["Package.swift"],
        "mocha": [".mocharc.yml", ".mocharc.json"],
    }
    for runner, files in markers.items():
        for f in files:
            filepath = root / f
            if filepath.exists():
                # Extra check for pytest in config files that may not be pytest-related.
                # Check for TOML section headers or INI sections, not bare substrings,
                # to avoid false positives from comments or unrelated text.
                if runner == "pytest" and f in ("pyproject.toml", "setup.cfg"):
                    content = filepath.read_text()
                    if f == "pyproject.toml":
                        if not re.search(r'^\[tool\.pytest[\].]', content, re.MULTILINE):
                            continue
                    else:  # setup.cfg
                        if "[tool:pytest]" not in content and not re.search(r'^\[pytest\]', content, re.MULTILINE):
                            continue
                return runner
    return None


def get_test_counts(runner: str | None) -> dict | None:
    """Run test suite and extract pass/fail counts."""
    if not runner:
        return None

    commands = {
        "pytest": ["python", "-m", "pytest", "--tb=no", "-q", "--no-header"],
        "jest": ["npx", "jest", "--silent", "--no-coverage"],
        "vitest": ["npx", "vitest", "run", "--reporter=verbose"],
        "cargo": ["cargo", "test", "--", "--format=terse"],
        "go": ["go", "test", "-v", "./..."],
        "swift": ["swift", "test"],
        "mocha": ["npx", "mocha", "--reporter=min"],
    }

    cmd = commands.get(runner)
    if not cmd:
        return None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr

        if runner == "pytest":
            m = re.search(r'(\d+) passed', output)
            f = re.search(r'(\d+) failed', output)
            s = re.search(r'(\d+) skipped', output)
            if not m and not f and not s:
                return None  # unparseable output (crash, permission error, etc.)
            return {
                "passed": int(m.group(1)) if m else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": int(s.group(1)) if s else 0,
            }

        if runner == "jest":
            # Jest output: Tests: N failed, N skipped, N passed, N total
            # Components are optional and Jest orders them by count descending,
            # so the order is NOT fixed. Extract each component independently.
            jest_line = re.search(r'Tests:[ \t]+(.+\d+ total)', output)
            if not jest_line:
                return None
            line = jest_line.group(1)
            p = re.search(r'(\d+) passed', line)
            f = re.search(r'(\d+) failed', line)
            s = re.search(r'(\d+) skipped', line)
            if not p and not f and not s:
                return None
            return {
                "passed": int(p.group(1)) if p else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": int(s.group(1)) if s else 0,
            }

        if runner == "vitest":
            # Vitest summary line: "Tests  N passed" or "Tests  N failed | N skipped | N passed"
            # Must match the Tests summary line specifically to avoid counting
            # "Test Files  N passed" which is a different metric.
            # Components are extracted independently (like Jest) to handle any order.
            vitest_line = re.search(r'^[ \t]*Tests[ \t]+(.+\d+ (?:passed|failed|skipped))', output, re.MULTILINE)
            if not vitest_line:
                return None
            line = vitest_line.group(1)
            p = re.search(r'(\d+) passed', line)
            f = re.search(r'(\d+) failed', line)
            s = re.search(r'(\d+) skipped', line)
            if not p and not f and not s:
                return None
            return {
                "passed": int(p.group(1)) if p else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": int(s.group(1)) if s else 0,
            }

        if runner == "cargo":
            # Cargo: test result: ok. N passed; N failed; N ignored
            m = re.search(r'(\d+) passed;[ \t]*(\d+) failed;[ \t]*(\d+) ignored', output)
            if not m:
                return None
            return {
                "passed": int(m.group(1)),
                "failed": int(m.group(2)),
                "skipped": int(m.group(3)),
            }

        if runner == "go":
            # Go verbose output: individual test results as --- PASS/FAIL/SKIP lines.
            # Only count top-level tests (no slash in name) to avoid double-counting subtests.
            # Known limitation: test functions that print "--- PASS: FakeName (" to stdout
            # at line start will inflate the count. No reliable way to distinguish runner
            # output from test output since they share stdout.
            passed = len(re.findall(r'^--- PASS: \w+[ (]', output, re.MULTILINE))
            failed = len(re.findall(r'^--- FAIL: \w+[ (]', output, re.MULTILINE))
            skipped = len(re.findall(r'^--- SKIP: \w+[ (]', output, re.MULTILINE))
            if passed == 0 and failed == 0 and skipped == 0:
                return None
            return {
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            }

        if runner == "swift":
            # Swift XCTest output: individual "Test Case '...' passed/failed/skipped" lines.
            passed = len(re.findall(r"^Test Case '.*' passed", output, re.MULTILINE))
            failed = len(re.findall(r"^Test Case '.*' failed", output, re.MULTILINE))
            skipped = len(re.findall(r"^Test Case '.*' skipped", output, re.MULTILINE))
            if passed == 0 and failed == 0 and skipped == 0:
                return None
            return {
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            }

        if runner == "mocha":
            # Mocha min reporter: N passing, N pending, N failing
            p = re.search(r'(\d+) passing', output)
            f = re.search(r'(\d+) failing', output)
            s = re.search(r'(\d+) pending', output)
            if not p and not f and not s:
                return None
            return {
                "passed": int(p.group(1)) if p else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": int(s.group(1)) if s else 0,
            }

        # Unknown runner (shouldn't reach here — checked at function entry)
        return None

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


#!/usr/bin/env python3
"""
Holtz Convergence Tracker

Tracks progress across fix iterations and determines when the codebase
has converged to a stable, clean state. Reads PUNCHLIST.md
and test suite output to compute convergence metrics.

Usage: python convergence_check.py [punchlist_path]
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from markdown_utils import mask_code_fences

HISTORY_FILE = "docs/holtz/HISTORY.json"


def count_items(punchlist_path: Path) -> dict:
    """Count punchlist items by status.

    Only counts Status fields that appear within item blocks (between
    ``### BH-NNN:`` headers).  Status fields in Pattern descriptions,
    preamble text, or item prose outside the first Status field per block
    are ignored.
    """
    if not punchlist_path.exists():
        print(f"WARNING: {punchlist_path} not found, treating as empty punchlist", file=sys.stderr)
        content = ""
    else:
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


def load_history() -> list:
    """Load convergence history from JSON file."""
    path = Path(HISTORY_FILE)
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, ValueError):
            print(f"WARNING: {path} is corrupted, starting fresh history", file=sys.stderr)
            return []
        if not isinstance(data, list):
            print(f"WARNING: {path} is not a JSON array, starting fresh history", file=sys.stderr)
            return []
        return data
    return []


def save_history(history: list) -> None:
    """Save convergence history to JSON file atomically.

    Writes to a temp file in the same directory, then renames.
    os.rename is atomic on POSIX for same-filesystem renames,
    preventing corruption from interrupted writes.
    """
    target = Path(HISTORY_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    closed = False
    try:
        os.write(fd, json.dumps(history, indent=2).encode())
        os.close(fd)
        closed = True
        os.replace(tmp_path, str(target))
    except BaseException:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _get_punchlist(entry: dict) -> dict:
    """Safely extract punchlist counts from a history entry."""
    default = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0, "total": 0}
    pl = entry.get("punchlist")
    if not isinstance(pl, dict):
        return default
    return {k: pl.get(k, 0) for k in default}


def check_convergence(history: list) -> tuple[bool, str]:
    """Determine if the fix loop has converged."""
    if len(history) < 3:
        return False, f"Not enough data points (need at least 3 iterations, have {len(history)})"

    curr_pl = _get_punchlist(history[-1])
    unknown_items = curr_pl.get("unknown", 0)
    open_items = curr_pl["OPEN"] + curr_pl["IN PROGRESS"] + unknown_items

    # Convergence requires that items were actually found and resolved at some point.
    # A punchlist that has always been empty (total == 0 across all history) cannot converge.
    max_total = max(_get_punchlist(h)["total"] for h in history)
    if max_total == 0:
        return False, "NO ITEMS: Punchlist has never contained any items. Run audit phases first."

    # Convergence requires items to have been resolved/deferred, not just deleted.
    # If items existed but current total is 0, they were deleted not resolved.
    curr_resolved_deferred = curr_pl["RESOLVED"] + curr_pl["DEFERRED"]
    if max_total > 0 and curr_resolved_deferred == 0 and open_items == 0:
        return False, (
            "ITEMS DELETED: Items existed previously but none are resolved or deferred. "
            "Resolve items, don't delete them."
        )

    # Detect partial item deletion: if total items decreased at any point
    # in the history, items were removed rather than resolved.
    # Known limitation: equal-count replacement (delete N, add N) is invisible
    # to this count-based check. Convergence still requires zero open items,
    # so false convergence cannot occur — only the deletion warning is bypassed.
    prev_max_total = max(_get_punchlist(h)["total"] for h in history[:-1])
    if prev_max_total > 0 and curr_pl["total"] < prev_max_total:
        deleted_count = prev_max_total - curr_pl["total"]
        return False, (
            f"ITEMS DELETED: {deleted_count} item(s) disappeared from punchlist "
            f"(was {prev_max_total}, now {curr_pl['total']}). "
            "Resolve items, don't delete them."
        )

    # Convergence requires 2 consecutive clean iterations (3 data points)
    last_3 = history[-3:]
    last_3_pls = [_get_punchlist(h) for h in last_3]
    no_new_2_iters = all(
        last_3_pls[i+1]["total"] <= last_3_pls[i]["total"]
        for i in range(2)
    )

    # Test suite must be stable or improving across the window.
    # Compare all snapshots with test data, not just adjacent pairs,
    # so a None gap doesn't hide a regression.
    tests_stable = True
    tests_verified = False
    snapshots_with_tests = [
        s for s in last_3
        if s.get("tests") and "failed" in s.get("tests", {})
    ]
    if len(snapshots_with_tests) >= 2:
        tests_verified = True
        first_failures = snapshots_with_tests[0]["tests"]["failed"]
        last_failures = snapshots_with_tests[-1]["tests"]["failed"]
        if last_failures > first_failures:
            tests_stable = False

    test_note = "" if tests_verified else " (test stability not verified — no test data)"

    if open_items == 0 and no_new_2_iters and tests_stable:
        return True, f"CONVERGED: No open items, no new items in 2 consecutive iterations, tests stable{test_note}"

    if open_items == 0 and no_new_2_iters and not tests_stable:
        return False, "BLOCKED: No open punchlist items, but test failures increased"

    # Stall detection: 3+ iterations with no progress on open items
    if len(history) >= 4:
        last_4_pls = [_get_punchlist(h) for h in history[-4:]]
        no_open_progress = all(
            (last_4_pls[i+1]["OPEN"] + last_4_pls[i+1]["IN PROGRESS"] + last_4_pls[i+1].get("unknown", 0))
            >= (last_4_pls[i]["OPEN"] + last_4_pls[i]["IN PROGRESS"] + last_4_pls[i].get("unknown", 0))
            for i in range(3)
        )
        if no_open_progress and open_items > 0:
            return False, (
                f"STALLED: {open_items} items remain open but no progress "
                f"in last 3 iterations. Consider deferring remaining items."
            )

    prev_pl = _get_punchlist(history[-2])
    new_items = curr_pl["total"] - prev_pl["total"]
    items_resolved = curr_pl["RESOLVED"] - prev_pl["RESOLVED"]

    parts = [f"IN PROGRESS: {open_items} items open"]
    if new_items > 0:
        parts.append(f"+{new_items} new")
    if items_resolved > 0:
        parts.append(f"{items_resolved} resolved this iteration")
    elif items_resolved < 0:
        parts.append(f"{-items_resolved} re-opened this iteration")
    else:
        parts.append("0 resolved this iteration")
    return False, ", ".join(parts)


def main() -> None:
    punchlist_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/holtz/PUNCHLIST.md")

    # Gather current state
    punchlist_counts = count_items(punchlist_path)
    runner = detect_test_runner()
    test_counts = get_test_counts(runner) if runner else None

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "punchlist": punchlist_counts,
        "test_runner": runner,
        "tests": test_counts,
    }

    # Load history and append
    history = load_history()
    history.append(snapshot)
    save_history(history)

    # Check convergence
    converged, message = check_convergence(history)

    # Report
    print(f"\n{'='*60}")
    print(f"Holtz Convergence Check -- Iteration {len(history)}")
    print(f"{'='*60}")
    print(f"\nPunchlist: {punchlist_counts}")
    if test_counts:
        print(f"Tests:     {test_counts}")
    print(f"\n{message}")

    if converged:
        print("\nThe fix loop has converged. Run a final Phase 1-3 sweep to confirm.")
        sys.exit(0)
    else:
        sys.exit(1)  # non-zero = keep going


if __name__ == "__main__":
    main()

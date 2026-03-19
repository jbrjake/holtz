#!/usr/bin/env python3
"""
Holtz Convergence Tracker

Tracks progress across fix iterations and determines when the codebase
has converged to a stable, clean state. Reads PUNCHLIST.md
and test suite output to compute convergence metrics.

Usage: python convergence_check.py [punchlist_path]
"""

import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime


HISTORY_FILE = "docs/holtz/HISTORY.json"


def count_items(punchlist_path: Path) -> dict:
    """Count punchlist items by status."""
    content = punchlist_path.read_text() if punchlist_path.exists() else ""
    counts = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0, "unknown": 0}

    for match in re.finditer(r'\*\*Status:\*\*[ \t]*(\w[\w ]*\w)', content):
        status = match.group(1).strip()
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1

    counts["total"] = sum(counts.values())
    return counts


def detect_test_runner() -> str | None:
    """Auto-detect the project's test runner."""
    markers = {
        "pytest": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
        "jest": ["jest.config.js", "jest.config.ts"],
        "vitest": ["vitest.config.ts", "vitest.config.js"],
        "cargo": ["Cargo.toml"],
        "go": ["go.mod"],
        "mocha": [".mocharc.yml", ".mocharc.json"],
    }
    for runner, files in markers.items():
        for f in files:
            if Path(f).exists():
                # Extra check for pytest in config files that may not be pytest-related
                if runner == "pytest" and f in ("pyproject.toml", "setup.cfg"):
                    content = Path(f).read_text()
                    if "pytest" not in content and "tool.pytest" not in content and "tool:pytest" not in content:
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
        "go": ["go", "test", "./..."],
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
            return {
                "passed": int(m.group(1)) if m else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": int(s.group(1)) if s else 0,
            }

        if runner == "jest":
            # Jest output: Tests: N failed, N passed, N total
            m = re.search(r'Tests:\s+(?:(\d+) failed,\s+)?(\d+) passed', output)
            if m:
                return {
                    "passed": int(m.group(2)),
                    "failed": int(m.group(1)) if m.group(1) else 0,
                    "skipped": 0,
                }

        if runner == "vitest":
            # Vitest output: Tests N passed | N failed (N)
            p = re.search(r'(\d+) passed', output)
            f = re.search(r'(\d+) failed', output)
            return {
                "passed": int(p.group(1)) if p else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": 0,
            }

        if runner == "cargo":
            # Cargo: test result: ok. N passed; N failed; N ignored
            m = re.search(r'(\d+) passed;\s*(\d+) failed;\s*(\d+) ignored', output)
            if m:
                return {
                    "passed": int(m.group(1)),
                    "failed": int(m.group(2)),
                    "skipped": int(m.group(3)),
                }

        if runner == "go":
            # Go: ok/FAIL per package, count lines
            passed = len(re.findall(r'^ok\s', output, re.MULTILINE))
            failed = len(re.findall(r'^FAIL\s', output, re.MULTILINE))
            return {
                "passed": passed,
                "failed": failed,
                "skipped": 0,
            }

        if runner == "mocha":
            # Mocha min reporter: N passing, N failing
            p = re.search(r'(\d+) passing', output)
            f = re.search(r'(\d+) failing', output)
            return {
                "passed": int(p.group(1)) if p else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": 0,
            }

        # Fallback
        return {"raw_output_lines": len(output.splitlines())}

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


def save_history(history: list):
    """Save convergence history to JSON file."""
    Path(HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(HISTORY_FILE).write_text(json.dumps(history, indent=2))


def check_convergence(history: list) -> tuple[bool, str]:
    """Determine if the fix loop has converged."""
    if len(history) < 3:
        return False, f"Not enough data points (need at least 3 iterations, have {len(history)})"

    curr = history[-1]
    unknown_items = curr["punchlist"].get("unknown", 0)
    open_items = curr["punchlist"]["OPEN"] + curr["punchlist"]["IN PROGRESS"] + unknown_items

    # Convergence requires that items were actually found and resolved at some point.
    # A punchlist that has always been empty (total == 0 across all history) cannot converge.
    max_total = max(h["punchlist"]["total"] for h in history)
    if max_total == 0:
        return False, "NO ITEMS: Punchlist has never contained any items. Run audit phases first."

    # Convergence requires 2 consecutive clean iterations (3 data points)
    last_3 = history[-3:]
    no_new_2_iters = all(
        last_3[i+1]["punchlist"]["total"] <= last_3[i]["punchlist"]["total"]
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
        last_4 = history[-4:]
        no_open_progress = all(
            (last_4[i+1]["punchlist"]["OPEN"] + last_4[i+1]["punchlist"]["IN PROGRESS"])
            >= (last_4[i]["punchlist"]["OPEN"] + last_4[i]["punchlist"]["IN PROGRESS"])
            for i in range(3)
        )
        if no_open_progress and open_items > 0:
            return False, (
                f"STALLED: {open_items} items remain open but no progress "
                f"in last 3 iterations. Consider deferring remaining items."
            )

    prev = history[-2]
    new_items = curr["punchlist"]["total"] - prev["punchlist"]["total"]
    items_resolved = curr["punchlist"]["RESOLVED"] - prev["punchlist"]["RESOLVED"]
    return False, (
        f"IN PROGRESS: {open_items} items open, "
        f"+{max(0, new_items)} new, {max(0, items_resolved)} resolved this iteration"
    )


def main():
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

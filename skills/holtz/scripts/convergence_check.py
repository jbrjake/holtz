#!/usr/bin/env python3
"""
Bug Hunter Convergence Tracker

Tracks progress across fix iterations and determines when the codebase
has converged to a stable, clean state. Reads BUG-HUNTER-PUNCHLIST.md
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
    counts = {"OPEN": 0, "IN PROGRESS": 0, "RESOLVED": 0, "DEFERRED": 0}

    for match in re.finditer(r'\*\*Status:\*\*\s*(\w[\w\s]*\w)', content):
        status = match.group(1).strip()
        if status in counts:
            counts[status] += 1

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
                # Extra check for pytest in pyproject.toml
                if runner == "pytest" and f == "pyproject.toml":
                    content = Path(f).read_text()
                    if "pytest" not in content and "tool.pytest" not in content:
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

        # Parse based on runner
        if runner == "pytest":
            m = re.search(r'(\d+) passed', output)
            f = re.search(r'(\d+) failed', output)
            s = re.search(r'(\d+) skipped', output)
            return {
                "passed": int(m.group(1)) if m else 0,
                "failed": int(f.group(1)) if f else 0,
                "skipped": int(s.group(1)) if s else 0,
            }

        # Generic fallback: count lines
        return {"raw_output_lines": len(output.splitlines())}

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def load_history() -> list:
    """Load convergence history from JSON file."""
    path = Path(HISTORY_FILE)
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_history(history: list):
    """Save convergence history to JSON file."""
    Path(HISTORY_FILE).write_text(json.dumps(history, indent=2))


def check_convergence(history: list) -> tuple[bool, str]:
    """Determine if the fix loop has converged."""
    if len(history) < 2:
        return False, "Not enough data points (need at least 2 iterations)"

    recent = history[-2:]
    prev, curr = recent

    # Convergence criteria:
    # 1. No new items added in last iteration
    new_items = curr["punchlist"]["total"] - prev["punchlist"]["total"]
    items_resolved = curr["punchlist"]["RESOLVED"] - prev["punchlist"]["RESOLVED"]

    # 2. No open items remaining
    open_items = curr["punchlist"]["OPEN"] + curr["punchlist"]["IN PROGRESS"]

    # 3. Test suite is stable or improving
    tests_stable = True
    if curr.get("tests") and prev.get("tests"):
        if "failed" in curr["tests"] and "failed" in prev["tests"]:
            tests_stable = curr["tests"]["failed"] <= prev["tests"]["failed"]

    if open_items == 0 and new_items <= 0:
        return True, "CONVERGED: No open items, no new items generated"

    if len(history) >= 3:
        last_3 = history[-3:]
        no_new = all(
            last_3[i+1]["punchlist"]["total"] <= last_3[i]["punchlist"]["total"]
            for i in range(len(last_3)-1)
        )
        no_open_change = all(
            (last_3[i+1]["punchlist"]["OPEN"] + last_3[i+1]["punchlist"]["IN PROGRESS"])
            >= (last_3[i]["punchlist"]["OPEN"] + last_3[i]["punchlist"]["IN PROGRESS"])
            for i in range(len(last_3)-1)
        )
        if no_new and no_open_change and open_items > 0:
            return False, (
                f"STALLED: {open_items} items remain open but no progress "
                f"in last 3 iterations. Consider deferring remaining items."
            )

    return False, (
        f"IN PROGRESS: {open_items} items open, "
        f"+{max(0, new_items)} new, {items_resolved} resolved this iteration"
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
    print(f"Bug Hunter Convergence Check -- Iteration {len(history)}")
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

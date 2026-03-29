#!/usr/bin/env python3
"""Validate that PUNCHLIST-MERGED.md has required sections.

Used as a gate condition on the 'merge_complete' transition.
Exit 0 if valid, exit 1 with details on stderr if not.
"""
from __future__ import annotations

import re
import sys

REQUIRED_SECTIONS = [
    ("Agreement", r"##\s+Agreement"),
    ("Holtz-Only", r"##\s+Holtz[- ]Only"),
    ("Justine-Only", r"##\s+Justine[- ]Only"),
    ("Blind Spot Analysis", r"##\s+Blind\s+Spot"),
]


def validate(path: str) -> list[str]:
    """Return list of missing section names."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return [name for name, _ in REQUIRED_SECTIONS]

    if not content.strip():
        return [name for name, _ in REQUIRED_SECTIONS]

    missing = []
    for name, pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, content, re.IGNORECASE):
            missing.append(name)
    return missing


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: validate_merge_report.py <path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    missing = validate(path)
    if missing:
        print(f"FAIL: Missing required sections: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    print("PASS: All required sections present.")
    sys.exit(0)


if __name__ == "__main__":
    main()

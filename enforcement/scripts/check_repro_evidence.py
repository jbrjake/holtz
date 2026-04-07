#!/usr/bin/env python3
"""Check that a can't-reproduce deferral has sufficient evidence.

Verifies that an investigation file exists at
docs/holtz/investigations/{item_id}.md and is non-empty.

Usage: python check_repro_evidence.py <finding_id> [--holtz-dir PATH]
Exit 0 if evidence found, exit 1 otherwise.
"""
from __future__ import annotations

import os
import re
import sys

FINDING_ID_RE = re.compile(r"^B[HJ]-\d{3}$")


def check_repro_evidence(finding_id: str, holtz_dir: str) -> bool:
    """Return True if reproduction evidence exists for the finding.

    Args:
        finding_id: The punchlist item ID (e.g., BH-042).
        holtz_dir: Path to the docs/holtz directory.
    """
    if not FINDING_ID_RE.match(finding_id):
        raise ValueError(
            f"Invalid finding ID '{finding_id}'. Expected format: BH-NNN or BJ-NNN"
        )

    investigation_path = os.path.join(
        holtz_dir, "investigations", f"{finding_id}.md"
    )

    if not os.path.isfile(investigation_path):
        return False

    # File must be non-empty
    return os.path.getsize(investigation_path) > 0


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: check_repro_evidence.py <finding_id> [--holtz-dir PATH]",
            file=sys.stderr,
        )
        sys.exit(1)

    finding_id = sys.argv[1]
    holtz_dir = "docs/holtz"
    if "--holtz-dir" in sys.argv:
        idx = sys.argv.index("--holtz-dir")
        if idx + 1 < len(sys.argv):
            holtz_dir = sys.argv[idx + 1]

    try:
        if check_repro_evidence(finding_id, holtz_dir):
            print(f"PASS: Evidence found for {finding_id}")
            sys.exit(0)
        else:
            print(
                f"FAIL: No evidence for {finding_id}. "
                f"Expected investigation file at {holtz_dir}/investigations/{finding_id}.md",
                file=sys.stderr,
            )
            sys.exit(1)
    except ValueError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

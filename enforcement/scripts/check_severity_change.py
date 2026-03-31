#!/usr/bin/env python3
"""Check that severity downgrades include evidence.

When a finding's resolved severity is lower than the original,
an evidence_path must be provided pointing to a real file.
"""
from __future__ import annotations

import os
import sys

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def check_downgrade(
    original_severity: str,
    resolved_severity: str,
    evidence_path: str | None,
) -> bool:
    """Return True if the severity change is valid.

    A downgrade requires evidence_path to exist as a real file.
    Same severity or upgrades always pass.
    """
    if original_severity not in SEVERITY_ORDER:
        raise ValueError(
            f"Unknown original severity '{original_severity}'. "
            f"Valid: {', '.join(SEVERITY_ORDER)}"
        )
    if resolved_severity not in SEVERITY_ORDER:
        raise ValueError(
            f"Unknown resolved severity '{resolved_severity}'. "
            f"Valid: {', '.join(SEVERITY_ORDER)}"
        )
    orig_rank = SEVERITY_ORDER[original_severity]
    resolved_rank = SEVERITY_ORDER[resolved_severity]

    if resolved_rank >= orig_rank:
        return True  # not a downgrade

    # It's a downgrade — evidence required
    if not evidence_path:
        return False
    return os.path.isfile(evidence_path)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: check_severity_change.py <original> <resolved> [evidence_path]", file=sys.stderr)
        sys.exit(1)

    original = sys.argv[1]
    resolved = sys.argv[2]
    evidence = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        valid = check_downgrade(original, resolved, evidence)
    except ValueError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    if valid:
        sys.exit(0)
    else:
        print(
            f"FAIL: Severity downgrade from {original} to {resolved} "
            f"requires evidence_path pointing to a real file.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

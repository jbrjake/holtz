#!/usr/bin/env python3
"""Defer every open finding of a severity, in one command.

    defer_batch.py --severity low
    defer_batch.py --severity low,medium

`defer_low` and `defer_medium` gate on nothing but severity and the finding
still being open, so a batch is a loop over the transitions the agent would
otherwise run one at a time. On the run this was measured against, 133 of 273
open findings were legally deferrable and the transitions were used zero times:
one command per finding is a cost nobody pays.

The pass for a severity stops at the first refusal, because the listing already
satisfies each transition's severity and open-ness gates: the only gate left to
refuse is MEDIUM's budget cap, whose answer cannot change within a batch that
only spends budget. Reaching the cap is the policy working, so it caps the
MEDIUM pass and exits zero. LOW has no cap, so a LOW refusal means the listing
and the gate disagree about the ledger — that abandons the batch and exits
non-zero rather than spending MEDIUM budget on a wrong reading.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from findings import collect, target  # noqa: E402

# Severity -> the transition that defers it, in the order a batch spends them.
# LOW and MEDIUM only: HIGH and CRITICAL are deferrable solely through
# `defer_cant_reproduce`, which requires a per-finding investigation file and
# so is not a batch.
TRANSITIONS = [("LOW", "defer_low"), ("MEDIUM", "defer_medium")]


def _defer(binary: str, config_dir: str, cwd: str, command: str,
           finding_id: str) -> str:
    """Run one deferral transition; return "" on success, else the reason."""
    result = subprocess.run(
        [binary, "--config-dir", config_dir, "transition", command, finding_id],
        capture_output=True, text=True, cwd=cwd, timeout=60,
    )
    if result.returncode == 0:
        return ""
    reason = " ".join((result.stderr or result.stdout).split())
    return reason or f"exit {result.returncode}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Defer every open finding of a severity")
    parser.add_argument(
        "--severity", default="low",
        help="comma-separated: low, medium (default: low)")
    args = parser.parse_args(argv)

    known = {severity for severity, _ in TRANSITIONS}
    wanted = {s.strip().upper() for s in args.severity.split(",") if s.strip()}
    unknown = sorted(wanted - known)
    if unknown:
        parser.error(f"cannot batch-defer {', '.join(unknown)} — "
                     f"choose from {', '.join(sorted(s.lower() for s in known))}")

    cwd = os.getcwd()
    binary, config_dir = target(cwd)
    findings = collect(binary, config_dir, cwd)

    deferred: list[str] = []
    failure: str | None = None
    capped = 0

    for severity, command in TRANSITIONS:
        if severity not in wanted:
            continue
        remaining = [f for f in findings
                     if f["status"] == "OPEN" and f["severity"].upper() == severity]
        while remaining:
            finding = remaining.pop(0)
            reason = _defer(binary, config_dir, cwd, command, finding["id"])
            if not reason:
                deferred.append(finding["id"])
                continue
            if severity == "MEDIUM":
                capped = len(remaining) + 1
            else:
                failure = f"{finding['id']}: {reason}"
            break
        if failure:
            break

    print(f"deferred {len(deferred)} finding(s)"
          + (f": {', '.join(deferred)}" if deferred else ""))
    if capped:
        print(f"MEDIUM budget spent — {capped} MEDIUM finding(s) stay open")
    sys.stdout.flush()
    if failure:
        print(f"FAIL: defer_low refused {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

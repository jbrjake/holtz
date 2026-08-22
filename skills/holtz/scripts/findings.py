#!/usr/bin/env python3
"""Query findings from the ledger.

    findings.py list             open findings, one line each
    findings.py list --all       every finding, with status
    findings.py list --severity CRITICAL HIGH
    findings.py show BH-001      one finding's full record

The punchlist is a rendered *view*; this reads the thing it is a view of, so
the answer is current and no markdown is parsed on the way.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_HOOKS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "enforcement", "hooks",
)
sys.path.insert(0, _HOOKS)

from _common import resolve_config_dir  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _query(binary: str, config_dir: str, cwd: str, event_type: str) -> list[dict]:
    """Every event of one type, oldest first."""
    result = subprocess.run(
        [binary, "--config-dir", config_dir, "query",
         "--type", event_type, "--format", "jsonl"],
        capture_output=True, text=True, cwd=cwd, timeout=60,
    )
    if result.returncode != 0:
        print(f"ERROR: sahjhan query failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    events = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _field(event: dict, name: str, default: str = "") -> str:
    """Read a field, tolerating both flat and nested record shapes."""
    if name in event:
        return str(event[name])
    fields = event.get("fields")
    if isinstance(fields, dict) and name in fields:
        return str(fields[name])
    return default


def collect(binary: str, config_dir: str, cwd: str) -> list[dict]:
    """Findings, deduped by id (last filing wins), each with a status.

    Last-filing-wins and resolved-before-deferred are the same rules
    ``punchlist.md.tera`` renders by, so this and the punchlist cannot
    disagree about a finding.
    """
    by_id: dict[str, dict] = {}
    for event in _query(binary, config_dir, cwd, "finding"):
        finding_id = _field(event, "id")
        if finding_id:
            by_id[finding_id] = event

    resolved = {_field(e, "id") for e in _query(binary, config_dir, cwd, "finding_resolved")}
    deferred = {_field(e, "id") for e in _query(binary, config_dir, cwd, "finding_deferred")}

    findings = []
    for finding_id, event in by_id.items():
        if finding_id in resolved:
            status = "RESOLVED"
        elif finding_id in deferred:
            status = "DEFERRED"
        else:
            status = "OPEN"
        findings.append({
            "id": finding_id,
            "status": status,
            "severity": _field(event, "severity", "?"),
            "category": _field(event, "category"),
            "location": _field(event, "location"),
            "perspective": _field(event, "perspective"),
            "description": _field(event, "description"),
        })

    def sort_key(f: dict) -> tuple[int, str]:
        try:
            rank = SEVERITY_ORDER.index(f["severity"])
        except ValueError:
            rank = len(SEVERITY_ORDER)
        return rank, f["id"]

    return sorted(findings, key=sort_key)


def target(cwd: str) -> tuple[str, str]:
    """The sahjhan binary and the enforcement config governing ``cwd``.

    Exits rather than returning a sentinel: every caller needs both, and a
    half-resolved target reads the wrong ledger.
    """
    binary = ensure_sahjhan()
    if binary is None:
        print("ERROR: sahjhan binary unavailable", file=sys.stderr)
        sys.exit(1)
    config_dir, found = resolve_config_dir(cwd)
    if not found:
        print("ERROR: enforcement config not found", file=sys.stderr)
        sys.exit(1)
    return binary, config_dir


def _one_line(finding: dict, width: int = 90) -> str:
    summary = " ".join(finding["description"].split())
    if len(summary) > width:
        summary = summary[: width - 1] + "…"
    return (f"{finding['id']}  {finding['severity']:<8} {finding['status']:<8} "
            f"{finding['location']}  {summary}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="list findings, one line each")
    listing.add_argument("--all", action="store_true",
                         help="include resolved and deferred findings")
    listing.add_argument("--severity", nargs="+", metavar="SEV",
                         help="only these severities")
    listing.add_argument("--count", action="store_true", help="print the count only")

    show = sub.add_parser("show", help="one finding's full record")
    show.add_argument("finding_id")

    args = parser.parse_args()

    cwd = os.getcwd()
    binary, config_dir = target(cwd)
    findings = collect(binary, config_dir, cwd)

    if args.command == "show":
        for finding in findings:
            if finding["id"] == args.finding_id:
                for key in ("id", "status", "severity", "category", "location",
                            "perspective", "description"):
                    print(f"{key}: {finding[key]}")
                return
        print(f"ERROR: no finding {args.finding_id}", file=sys.stderr)
        sys.exit(1)

    if not args.all:
        findings = [f for f in findings if f["status"] == "OPEN"]
    if args.severity:
        wanted = {s.upper() for s in args.severity}
        findings = [f for f in findings if f["severity"].upper() in wanted]

    if args.count:
        print(len(findings))
        return

    for finding in findings:
        print(_one_line(finding))
    print(f"\n{len(findings)} finding(s)")


if __name__ == "__main__":
    main()

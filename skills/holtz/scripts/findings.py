#!/usr/bin/env python3
"""Query findings from the ledger.

    findings.py list             open findings, one line each
    findings.py list --all       every finding, with status
    findings.py list --severity CRITICAL HIGH
    findings.py show BH-001      one finding's full record
    findings.py audited-files    every file any run's findings have named

The punchlist is a rendered *view*; this reads the thing it is a view of, so
the answer is current and no markdown is parsed on the way.

`audited-files` reads every run's ledger rather than the active one, because
what it answers — has this file ever been audited — is a question about the
project, not about this run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

# Every ledger this project has: the active run's, the ones earlier runs left
# behind, and the copies inside `docs/holtz/archive/`. All three layouts sit
# under `docs/holtz`, and `sahjhan query --glob` reads a set of them as one.
LEDGER_GLOB = "docs/holtz/**/ledger.jsonl"

# `location` is free text. Runs write `file.py:88`, two paths separated by a
# comma, and `a.py:1 | b.py:2` — all three appear in this repo's own archived
# ledgers, so all three are split here rather than argued about.
_LOCATION_SPLIT = re.compile(r"[,|]")
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")


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


def _collect(binary: str, config_dir: str, cwd: str) -> list[dict]:
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
            "reachability": _field(event, "reachability", "?"),
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


def _paths_in(location: str) -> list[str]:
    """The file paths one `location` names, without their line numbers."""
    paths = []
    for piece in _LOCATION_SPLIT.split(location):
        path = _LINE_SUFFIX.sub("", piece.strip().strip("`").rstrip(":"))
        if path:
            paths.append(path)
    return paths


def _audited_files(binary: str, config_dir: str, cwd: str) -> list[str]:
    """Every file path any finding, in any run of this project, has named.

    Status is deliberately not consulted: a resolved finding is proof the file
    was audited just as much as an open one, and it is the *converged* run —
    every finding closed — whose files the punchlist read used to lose.
    """
    result = subprocess.run(
        [binary, "--config-dir", config_dir, "query", "--glob", LEDGER_GLOB,
         "SELECT DISTINCT location FROM events WHERE type='finding'",
         "--format", "jsonl"],
        capture_output=True, text=True, cwd=cwd, timeout=120,
    )
    if result.returncode != 0:
        if "no files matched pattern" in result.stderr:
            # A project with no ledger has audited nothing. That is the answer,
            # not an error: it is the first run, and every file is cold.
            return []
        print(f"ERROR: sahjhan query failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    paths: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        paths.update(_paths_in(str(row.get("location", ""))))
    return sorted(paths)


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
    # P0.5's routing (D34): only `user_reachable` findings are fix-loop
    # eligible, and `fix_commit` refuses the rest. Without this the agent picks
    # blind and learns at the end of a cycle that the work could not be
    # committed — the gate would cost exactly what the clause was written to
    # save.
    listing.add_argument("--reachability", nargs="+", metavar="GRADE",
                         help="only these reachability grades")
    # Item 3 scoped `set complete perspective` to one lens, so the block names
    # a population this read is the only way to see. Without it the agent meets
    # a lens-scoped gate holding a board-wide list, which is the same cost
    # `--reachability` exists to avoid one field over. `--lens` and not
    # `--perspective`: the axis is a Lens everywhere a reader sees it
    # (Jon, 2026-09-01); `perspective` is the event field's spelling.
    listing.add_argument("--lens", nargs="+", metavar="LENS",
                         help="only findings filed under these lenses")
    listing.add_argument("--count", action="store_true", help="print the count only")

    show = sub.add_parser("show", help="one finding's full record")
    show.add_argument("finding_id")

    sub.add_parser("audited-files",
                   help="every file any run's findings have named, one per line")

    args = parser.parse_args()

    binary = ensure_sahjhan()
    if binary is None:
        print("ERROR: sahjhan binary unavailable", file=sys.stderr)
        sys.exit(1)
    cwd = os.getcwd()
    config_dir, found = resolve_config_dir(cwd)
    if not found:
        print("ERROR: enforcement config not found", file=sys.stderr)
        sys.exit(1)

    if args.command == "audited-files":
        for path in _audited_files(binary, config_dir, cwd):
            print(path)
        return

    findings = _collect(binary, config_dir, cwd)

    if args.command == "show":
        for finding in findings:
            if finding["id"] == args.finding_id:
                for key in ("id", "status", "severity", "reachability",
                            "category", "location", "perspective", "description"):
                    print(f"{key}: {finding[key]}")
                return
        print(f"ERROR: no finding {args.finding_id}", file=sys.stderr)
        sys.exit(1)

    if not args.all:
        findings = [f for f in findings if f["status"] == "OPEN"]
    if args.severity:
        wanted = {s.upper() for s in args.severity}
        findings = [f for f in findings if f["severity"].upper() in wanted]
    if args.reachability:
        grades = {g.lower() for g in args.reachability}
        findings = [f for f in findings if f["reachability"].lower() in grades]
    if args.lens:
        lenses = {p.lower() for p in args.lens}
        findings = [f for f in findings if f["perspective"].lower() in lenses]

    if args.count:
        print(len(findings))
        return

    for finding in findings:
        print(_one_line(finding))
    print(f"\n{len(findings)} finding(s)")


if __name__ == "__main__":
    main()

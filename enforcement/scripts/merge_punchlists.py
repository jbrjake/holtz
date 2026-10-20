#!/usr/bin/env python3
"""Merge Justine's punchlist into Holtz's ledger (P4.1).

``merge-protocol.md`` calls the merge mechanical and deterministic, and it is —
every rule in it is a comparison of two records. It ran 36.7 minutes as a
subagent hand-writing throwaway ``python3 -c`` scripts over 354 findings. This
is that protocol, executed.

What stays with the agent is the one classification the protocol itself excepts:
a contradiction, where one auditor verified as correct what the other filed as a
bug. That is a judgment about two prose arguments, so the script surfaces
*candidates* — a verification phrase over a file both auditors named — and
records each finding under its ordinary class regardless. Nothing here defers,
drops or resolves a candidate.

Reads the ledger through ``sahjhan query`` (daemon-free, so it runs in the
agent's sandboxed shell) and writes through ``sahjhan event finding``, which is
a normal event and therefore a direct ledger append — no courier needed, unlike
the restricted events ``stale_sweep.py`` and ``pattern_round.py`` produce.

Usage::

    python3 merge_punchlists.py --justine docs/holtz/justine/PUNCHLIST.md
    python3 merge_punchlists.py --justine <path> --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_SKILL_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "skills", "holtz", "scripts",
)
sys.path.insert(0, _SKILL_SCRIPTS)

from _ledger_query import query_ledger, sahjhan_target  # noqa: E402

from impact_graph import ENTITY_PATTERNS  # noqa: E402
from validate_punchlist import parse_punchlist  # noqa: E402

# Where the merge happens: `phase-merge.md`, Step 9. Constants rather than
# arguments for the same reason `stale_sweep.py` carries SWEEP_STEP — a value
# the agent supplies is a value the agent can get wrong. Pinned against the
# document by `test_the_stamp_names_the_step_that_teaches_the_merge`.
MERGE_PHASE = "merge"
MERGE_STEP = "9"

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# `merge-protocol.md:67`: "within 5 of each other (inclusive)".
LINE_PROXIMITY = 5

# A finding that never stated its reachability has not established one, which
# is `theoretical`'s own definition — the same answer `migrate_legacy.py` gives
# an archived finding filed before the field existed.
DEFAULT_REACHABILITY = "theoretical"

# A fail-safe, not a value the board should carry: it is not a member of
# `[sets.perspective]`, so a finding wearing it belongs to no lens and no lens
# gate will ask about it. `validate_punchlist.py` rejects a punchlist item that
# does not state a declared `**Lens:**`, so nothing reaching the merge from
# Justine's side can be defaulted here. Kept rather than deleted: the Holtz
# side is read from the ledger, and a row that somehow lacks the field should
# produce an obviously-wrong perspective rather than a KeyError mid-merge.
DEFAULT_PERSPECTIVE = "unspecified"

# `merge-protocol.md:81`: an explicit statement that the other auditor's
# finding is not a bug. Deliberately over-broad — these are candidates for a
# human-equivalent reading, and a missed contradiction is the expensive one.
_CONTRADICTION_PHRASES = (
    "not a bug",
    "not actually a bug",
    "correct behavior",
    "correct behaviour",
    "working as intended",
    "by design",
    "intentional",
    "false positive",
    "verified correct",
    "is correct",
)

_LOCATION_LINE = re.compile(r":(\d+)(?:-\d+)?\s*$")
_LOCATION_SYMBOL = re.compile(
    r"\(\s*(?:function|method|class)\s+`?([A-Za-z_][\w.]*)`?\s*\)", re.I
)


class Location(NamedTuple):
    """What a `location` string locates: a file, maybe a line, maybe a symbol."""

    path: str
    line: int | None
    symbol: str | None


@dataclass
class Finding:
    """One auditor's record of one defect, from either side of the merge."""

    id: str
    severity: str
    category: str
    location: str
    description: str
    reachability: str = DEFAULT_REACHABILITY
    perspective: str = DEFAULT_PERSPECTIVE
    # Carried, not re-derived. Both are facts about a finding that only its
    # filing knows, and the merge re-files on escalation: dropping them here
    # meant the one path that says "this is worse than you thought" was the
    # path that took the finding out of its round (`pattern_id`) and off the
    # prediction-accuracy table (`predicted_by`).
    #
    # `pattern_id` defaults empty and is *omitted* at the write rather than
    # sent blank — the engine's `^PAT-\d+$` refuses an empty string, so a
    # blank one is a rejected event, not an absent field.
    pattern_id: str = ""
    predicted_by: str = "none"


@dataclass
class Merge:
    """The protocol's five classes.

    ``severity_disagreements`` is a **subset** of ``agreements``, not a sixth
    class: `merge-protocol.md:56` counts it inside the Agreement total and says
    explicitly that it is not double-counted. Keeping one list and a view of it
    is what makes the two numbers unable to disagree.
    """

    agreements: list[tuple[Finding, Finding]] = field(default_factory=list)
    severity_disagreements: list[tuple[Finding, Finding]] = field(default_factory=list)
    holtz_only: list[Finding] = field(default_factory=list)
    justine_only: list[Finding] = field(default_factory=list)
    contradiction_candidates: list[tuple[Finding, str]] = field(default_factory=list)


# ── Locations ────────────────────────────────────────────────────────────────


def parse_location(raw: str) -> Location:
    """Split a `location` into path, line and symbol.

    Runs write ``file.py:88``, ``` `file.py:88` ``` and
    ``file.py:88 (function save_order)``; all three appear in this repo's own
    archived ledgers and in `merge-examples.md`.
    """
    text = (raw or "").strip()
    symbol = None
    match = _LOCATION_SYMBOL.search(text)
    if match:
        symbol = match.group(1)
        text = text[: match.start()] + text[match.end():]
    text = text.strip().strip("`").strip()

    line = None
    line_match = _LOCATION_LINE.search(text)
    if line_match:
        line = int(line_match.group(1))
        text = text[: line_match.start()]
    return Location(text.strip().strip("`").strip(), line, symbol)


def _symbol_body(cwd: str, path: str, symbol: str) -> tuple[int, int] | None:
    """The 1-indexed line span of ``symbol``'s body, or None if unresolvable.

    Definition line by the same patterns `impact_graph.py` locates entities
    with; extent by indentation, which is exact for Python and an
    approximation elsewhere. Unresolvable is a real answer: the file may not
    exist in this checkout, and an unresolved span must not manufacture a
    match — the pair simply falls through to the other proximity options.
    """
    try:
        with open(os.path.join(cwd, path), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None

    patterns = [
        re.compile(p.format(name=re.escape(symbol)))
        for p in ENTITY_PATTERNS["function"] + ENTITY_PATTERNS["class"]
    ]
    start = None
    for index, text in enumerate(lines):
        if any(p.search(text) for p in patterns):
            start = index
            break
    if start is None:
        return None

    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        text = lines[index]
        if text.strip() and (len(text) - len(text.lstrip())) <= indent:
            end = index
            break
    return start + 1, end


def same_bug(holtz: Finding, justine: Finding, cwd: str = ".") -> bool:
    """`merge-protocol.md:62` — all three conditions, in order."""
    left = parse_location(holtz.location)
    right = parse_location(justine.location)

    if not left.path or left.path != right.path:
        return False
    if holtz.category != justine.category:
        return False

    if left.line is not None and right.line is not None:
        return abs(left.line - right.line) <= LINE_PROXIMITY
    if left.symbol and right.symbol:
        return left.symbol == right.symbol

    # One side names a line, the other a symbol: the line must fall inside the
    # symbol's body.
    for line_side, symbol_side in ((left, right), (right, left)):
        if line_side.line is not None and symbol_side.symbol:
            span = _symbol_body(cwd, left.path, symbol_side.symbol)
            return span is not None and span[0] <= line_side.line <= span[1]

    # `merge-protocol.md:77` — neither locates, so file and category suffice.
    return (left.line is None and left.symbol is None
            and right.line is None and right.symbol is None)


# ── Classification ───────────────────────────────────────────────────────────


def _severity_rank(severity: str) -> int:
    try:
        return SEVERITY_ORDER.index(severity.upper())
    except ValueError:
        return len(SEVERITY_ORDER)


def _item_number(finding_id: str) -> int:
    match = re.search(r"(\d+)", finding_id)
    return int(match.group(1)) if match else 0


def _sort_key(finding: Finding) -> tuple[str, str, int, str]:
    """`merge-protocol.md:75` — file, then category, then location.

    Items carrying a line number sort before items carrying only a symbol,
    which is what the ``0``/``1`` discriminator does.
    """
    location = parse_location(finding.location)
    if location.line is not None:
        return location.path, finding.category, 0, f"{location.line:012d}"
    return location.path, finding.category, 1, location.symbol or ""


def _contradiction_quote(text: str) -> str | None:
    """The sentence carrying a verification phrase, if there is one."""
    for sentence in re.split(r"(?<=[.!?])\s+", " ".join((text or "").split())):
        lowered = sentence.lower()
        if any(phrase in lowered for phrase in _CONTRADICTION_PHRASES):
            return sentence.strip()
    return None


def classify(
    holtz: list[Finding], justine: list[Finding], cwd: str = "."
) -> Merge:
    """Match one-to-one, then bucket by the protocol's five classes.

    Matching consumes the pool: `merge-protocol.md:76` says a matched Justine
    item "is removed from the candidate pool and cannot match another Holtz
    item". Deciding each Holtz item independently — the natural shape, and the
    one an LLM merge falls into — lets one Justine finding agree with two
    Holtz findings and inflates the agreement count.
    """
    result = Merge()
    pool = sorted(justine, key=_sort_key)
    taken: set[str] = set()

    for holtz_finding in sorted(holtz, key=_sort_key):
        candidates = [
            f for f in pool
            if f.id not in taken and same_bug(holtz_finding, f, cwd)
        ]
        if not candidates:
            result.holtz_only.append(holtz_finding)
            continue

        holtz_line = parse_location(holtz_finding.location).line

        def distance(candidate: Finding, _line: int | None = holtz_line) -> int:
            other = parse_location(candidate.location).line
            if _line is None or other is None:
                return 0
            return abs(_line - other)

        match = min(candidates, key=lambda c: (distance(c), _item_number(c.id)))
        taken.add(match.id)
        result.agreements.append((holtz_finding, match))
        if holtz_finding.severity.upper() != match.severity.upper():
            result.severity_disagreements.append((holtz_finding, match))

    result.justine_only = [f for f in pool if f.id not in taken]

    # A contradiction is a disagreement, so a verification phrase only counts
    # against a file the other auditor also named.
    holtz_files = {parse_location(f.location).path for f in holtz}
    justine_files = {parse_location(f.location).path for f in justine}
    for finding, other_files in (
        [(f, holtz_files) for f in justine] + [(f, justine_files) for f in holtz]
    ):
        quote = _contradiction_quote(finding.description)
        if quote and parse_location(finding.location).path in other_files:
            result.contradiction_candidates.append((finding, quote))

    return result


# ── Reading each side ────────────────────────────────────────────────────────


def justine_findings(path: str) -> list[Finding]:
    """Her punchlist, parsed. It is the only copy — she keeps no ledger."""
    with open(path, encoding="utf-8") as fh:
        content = fh.read()

    findings = []
    for item in parse_punchlist(content):
        description = "\n\n".join(
            part for part in (
                item.problem,
                f"Evidence: {item.evidence}" if item.evidence else "",
                f"Discovery Chain: {item.discovery_chain}" if item.discovery_chain else "",
            ) if part
        ) or item.title
        findings.append(Finding(
            id=item.id,
            severity=item.severity or "LOW",
            category=item.category,
            location=item.location,
            description=description,
            reachability=item.reachability or DEFAULT_REACHABILITY,
            perspective=item.perspective or DEFAULT_PERSPECTIVE,
        ))
    return findings


# Every field the merge can re-file, not just the ones it compares. A column
# missing here does not read as absent downstream — it reads as the dataclass
# default, and `apply_merge` then writes that default back over a graded row.
# `reachability` is the one that cost: absent from this list, every Holtz
# finding was built `theoretical`, and escalation re-filed it that way.
_HOLTZ_SQL = """
SELECT id, severity, category, location, perspective, description,
       reachability, pattern_id, predicted_by, seq
FROM events WHERE type='finding' ORDER BY seq
"""

_CONTEXT_SQL = """
SELECT project, run FROM events
WHERE project IS NOT NULL AND run IS NOT NULL ORDER BY seq DESC LIMIT 1
"""


def _optional(value: object) -> str:
    """An optional ledger column as a string, with SQL's absent spelled "".

    `sahjhan query --format json` renders an absent optional column as the
    **string** ``"NULL"``, not as ``null`` and not as ``""`` — so
    ``str(row.get(...) or "")`` keeps it, and the merge would then re-file
    ``pattern_id=NULL``, which the engine's ``^PAT-\\d+$`` refuses outright.
    The whole escalation fails on a finding that simply had no pattern.
    """
    text = "" if value is None else str(value)
    return "" if text.upper() == "NULL" else text


def holtz_findings(binary: str, config_dir: str, cwd: str) -> tuple[list[Finding], str]:
    """Holtz's board, last filing per id — the rule the punchlist renders by."""
    rows, problem = query_ledger(binary, config_dir, cwd, _HOLTZ_SQL)
    if rows is None:
        return [], problem
    by_id: dict[str, Finding] = {}
    for row in rows:
        finding_id = str(row.get("id") or "")
        if not finding_id:
            continue
        by_id[finding_id] = Finding(
            id=finding_id,
            severity=str(row.get("severity") or "LOW"),
            category=str(row.get("category") or ""),
            location=str(row.get("location") or ""),
            description=str(row.get("description") or ""),
            perspective=str(row.get("perspective") or DEFAULT_PERSPECTIVE),
            # `DEFAULT_REACHABILITY` is Justine's fail-safe, not this side's:
            # `reachability` is a required, pattern-enforced field on
            # `[events.finding]`, so a row on this board always states one and
            # the fallback is unreachable here. Defaulting a *stated* grading
            # is what item 25 was.
            reachability=str(row.get("reachability") or DEFAULT_REACHABILITY),
            pattern_id=_optional(row.get("pattern_id")),
            predicted_by=str(row.get("predicted_by") or "none"),
        )
    return list(by_id.values()), ""


def run_context(binary: str, config_dir: str, cwd: str) -> tuple[tuple[str, str] | None, str]:
    """``(project, run)`` as Holtz has been recording them.

    Read from the ledger rather than taken as arguments: every value a merge
    needs is already on the record Holtz wrote, and a second spelling of it is
    a second thing that can be wrong.
    """
    rows, problem = query_ledger(binary, config_dir, cwd, _CONTEXT_SQL)
    if rows is None:
        return None, problem
    if not rows:
        return None, "no event in this ledger names a project and run"
    return (str(rows[0].get("project") or ""), str(rows[0].get("run") or "")), ""


# ── Writing ──────────────────────────────────────────────────────────────────


def _record(
    binary: str, config_dir: str, cwd: str, finding: Finding,
    auditor: str, project: str, run: str,
) -> str:
    """Append one `finding` event. Returns "" or a problem."""
    result = subprocess.run(
        [binary, "--config-dir", config_dir, "event", "finding",
         "--field", f"project={project}", "--field", f"run={run}",
         "--field", f"auditor={auditor}",
         "--field", f"phase={MERGE_PHASE}", "--field", f"step={MERGE_STEP}",
         "--field", f"id={finding.id}", "--field", f"severity={finding.severity}",
         "--field", f"category={finding.category}",
         "--field", f"location={finding.location}",
         "--field", f"perspective={finding.perspective}",
         "--field", f"reachability={finding.reachability}",
         "--field", f"predicted_by={finding.predicted_by}",
         "--field", f"description={finding.description}",
         # Omitted when the finding has none: `pattern_id` is `optional` in
         # `[events.finding]` but pattern-constrained, so a blank one is a
         # refused event rather than an unset field.
         *(["--field", f"pattern_id={finding.pattern_id}"]
           if finding.pattern_id else [])],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return f"{finding.id}: {result.stderr.strip() or result.stdout.strip()}"
    return ""


def apply_merge(
    binary: str, config_dir: str, cwd: str, merge: Merge, project: str, run: str,
) -> list[str]:
    """Record what the merge owes the ledger. Returns the problems.

    Two writes, both from `merge-protocol.md:38-39`: every unmatched Justine
    finding under her own id, and Holtz's id re-filed where her severity is
    higher. An Agreement records nothing.
    """
    problems = []
    for finding in merge.justine_only:
        if problem := _record(binary, config_dir, cwd, finding, "justine", project, run):
            problems.append(problem)

    for holtz_finding, justine_finding in merge.severity_disagreements:
        if _severity_rank(justine_finding.severity) >= _severity_rank(holtz_finding.severity):
            continue
        # Her severity, and Holtz's everything-else. The escalation decides
        # exactly one field; every other value is the finding's own and is
        # carried through rather than re-derived — item 25 was three of them
        # being silently re-derived as defaults.
        raised = replace(holtz_finding, severity=justine_finding.severity.upper())
        if problem := _record(binary, config_dir, cwd, raised, "holtz", project, run):
            problems.append(problem)
    return problems


# ── The impact graph ─────────────────────────────────────────────────────────


def _edge_key(edge: dict) -> tuple[str, str, str]:
    """Edge identity. Same nodes but a different `type` is a different edge —
    `merge-protocol.md:150` keeps both."""
    return (str(edge.get("source", "")), str(edge.get("target", "")),
            str(edge.get("type", "")))


def _edge_time(edge: dict) -> str:
    meta = edge.get("metadata") or {}
    return str(meta.get("timestamp") or meta.get("discovered") or "")


def merge_graphs(canonical: dict, other: dict) -> dict:
    """`merge-protocol.md:146`'s conflict table, applied."""
    nodes = {node_id: dict(node) for node_id, node in (canonical.get("nodes") or {}).items()}
    for node_id, incoming in (other.get("nodes") or {}).items():
        existing = nodes.get(node_id)
        if existing is None:
            nodes[node_id] = dict(incoming)
            continue
        merged = dict(existing)
        merged["risk_score"] = max(existing.get("risk_score", 0.0),
                                   incoming.get("risk_score", 0.0))
        if "audit_count" in existing or "audit_count" in incoming:
            merged["audit_count"] = existing.get("audit_count", 0) + incoming.get("audit_count", 0)
        last = max(str(existing.get("last_audited", "")), str(incoming.get("last_audited", "")))
        if last:
            merged["last_audited"] = last
        nodes[node_id] = merged

    edges: dict[tuple[str, str, str], dict] = {}
    for edge in canonical.get("edges") or []:
        edges[_edge_key(edge)] = dict(edge)
    for incoming in other.get("edges") or []:
        key = _edge_key(incoming)
        existing = edges.get(key)
        if existing is None:
            edges[key] = dict(incoming)
            continue
        keep, drop = ((incoming, existing)
                      if _edge_time(incoming) > _edge_time(existing)
                      else (existing, incoming))
        merged = dict(keep)
        metadata = dict(keep.get("metadata") or {})
        notes = [str((drop.get("metadata") or {}).get("note", "")),
                 str(metadata.get("note", ""))]
        joined = " | ".join(sorted({n for n in notes if n}))
        if joined:
            metadata["note"] = joined
        if metadata:
            merged["metadata"] = metadata
        edges[key] = merged

    return {"nodes": nodes, "edges": list(edges.values())}


# ── The report ───────────────────────────────────────────────────────────────


def _blind_spot(findings: list[Finding]) -> str:
    """What one auditor missed, as the categories the other found without them.

    Deterministic by construction — `merge-protocol.md:126`'s own example is a
    category count ("missed 3 surface-level doc/drift items"), so nothing here
    needs a reader.
    """
    if not findings:
        return "nothing — every finding of the other auditor's was matched"
    counts = Counter(f.category or "uncategorised" for f in findings)
    parts = [f"{n} {category}" for category, n in counts.most_common(3)]
    return f"missed {len(findings)} item(s) — {', '.join(parts)}"


def _lines(entries: list[str]) -> str:
    return "\n".join(entries) if entries else "_none_"


def render_report(merge: Merge, date: str, holtz_total: int | None = None,
                  justine_total: int | None = None) -> str:
    """`merge-protocol.md:89`'s template, filled.

    Every section carries a body even at zero, because `merge_complete`'s gate
    fails an *empty* section as hard as a missing one — and the merge that
    agrees on nothing is a real merge.
    """
    if holtz_total is None:
        holtz_total = len(merge.agreements) + len(merge.holtz_only)
    if justine_total is None:
        justine_total = len(merge.agreements) + len(merge.justine_only)
    merged_total = len(merge.agreements) + len(merge.holtz_only) + len(merge.justine_only)

    agreement_rows = [f"- **{h.id}** ↔ **{j.id}** — `{h.location}` ({h.category})"
                      for h, j in merge.agreements]
    holtz_rows = [f"- **{f.id}** — `{f.location}` ({f.category}, {f.severity})"
                  for f in merge.holtz_only]
    justine_rows = [f"- **{f.id}** — `{f.location}` ({f.category}, {f.severity})"
                    for f in merge.justine_only]
    severity_rows = [
        f"- **{h.id}:** Holtz={h.severity}, Justine={j.severity}. Using "
        f"{h.severity if _severity_rank(h.severity) <= _severity_rank(j.severity) else j.severity}."
        for h, j in merge.severity_disagreements
    ]
    candidate_rows = [f"- **{f.id}** (`{f.location}`): \"{quote}\" — review required."
                      for f, quote in merge.contradiction_candidates]

    return f"""# Adversarial Self-Play Merge Report

**Date:** {date}
**Holtz findings:** {holtz_total}
**Justine findings:** {justine_total}
**Merged total:** {merged_total}

## Agreement
{len(merge.agreements)} item(s) found by both auditors\
{f", including {len(merge.severity_disagreements)} with severity disagreements"
 if merge.severity_disagreements else ""}

{_lines(agreement_rows)}

## Holtz-only
{len(merge.holtz_only)} item(s) — depth-first analysis

{_lines(holtz_rows)}

## Justine-only
{len(merge.justine_only)} item(s) — breadth-first analysis

{_lines(justine_rows)}

## Severity Disagreements
{len(merge.severity_disagreements)} item(s) — higher severity wins

{_lines(severity_rows)}

## Contradictions
{len(merge.contradiction_candidates)} candidate(s) — not adjudicated by the merge

{_lines(candidate_rows)}

## Blind Spot Analysis
- **Holtz's blind spots:** {_blind_spot(merge.justine_only)}
- **Justine's blind spots:** {_blind_spot(merge.holtz_only)}
"""


# ── Entrypoint ───────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge Justine's punchlist into Holtz's ledger")
    parser.add_argument("--justine", default="docs/holtz/justine/PUNCHLIST.md",
                        help="Justine's punchlist — the only copy of her findings")
    parser.add_argument("--report", default="docs/holtz/MERGE-REPORT.md",
                        help="where to write the merge report")
    parser.add_argument("--graph", default="docs/holtz/impact-graph.json",
                        help="the canonical impact graph")
    parser.add_argument("--justine-graph", default="docs/holtz/justine/impact-graph.json",
                        help="Justine's impact graph, merged into the canonical one")
    parser.add_argument("--cwd", default=".", help="target project directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="classify and report without writing the ledger")
    return parser


def _merge_graph_files(cwd: str, canonical_path: str, other_path: str) -> str:
    """Fold Justine's graph into the canonical one. Returns "" or a problem."""
    canonical_full = os.path.join(cwd, canonical_path)
    other_full = os.path.join(cwd, other_path)
    if not os.path.exists(other_full):
        return ""
    try:
        with open(other_full, encoding="utf-8") as fh:
            other = json.load(fh)
        canonical: dict = {"nodes": {}, "edges": []}
        if os.path.exists(canonical_full):
            with open(canonical_full, encoding="utf-8") as fh:
                canonical = json.load(fh)
        merged = merge_graphs(canonical, other)
        with open(canonical_full, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(merged, indent=2) + "\n")
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        return f"impact graph not merged: {exc}"
    return ""


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cwd = os.path.abspath(args.cwd)

    justine_path = args.justine if os.path.isabs(args.justine) else os.path.join(cwd, args.justine)
    if not os.path.exists(justine_path):
        print(f"FAIL: {justine_path} does not exist — nothing to merge.", file=sys.stderr)
        return 1

    binary, config_dir, problem = sahjhan_target(cwd)
    if binary is None or config_dir is None:
        print(f"FAIL: cannot reach the ledger — {problem}", file=sys.stderr)
        return 1

    holtz, problem = holtz_findings(binary, config_dir, cwd)
    if problem:
        print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    justine = justine_findings(justine_path)
    if not justine:
        print(f"FAIL: no items parsed from {justine_path}.", file=sys.stderr)
        return 1

    merge = classify(holtz, justine, cwd)

    if not args.dry_run:
        context, problem = run_context(binary, config_dir, cwd)
        if context is None:
            print(f"FAIL: {problem}", file=sys.stderr)
            return 1
        problems = apply_merge(binary, config_dir, cwd, merge, *context)
        if problems:
            print("FAIL: the ledger refused " + str(len(problems)) + " filing(s):",
                  file=sys.stderr)
            for entry in problems:
                print(f"  {entry}", file=sys.stderr)
            return 1
        if graph_problem := _merge_graph_files(cwd, args.graph, args.justine_graph):
            print(f"WARN: {graph_problem}", file=sys.stderr)

    report_path = args.report if os.path.isabs(args.report) else os.path.join(cwd, args.report)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(render_report(merge, date.today().isoformat(),
                               holtz_total=len(holtz), justine_total=len(justine)))

    print(
        f"merged: {len(merge.agreements)} agreement(s), "
        f"{len(merge.holtz_only)} Holtz-only, {len(merge.justine_only)} Justine-only, "
        f"{len(merge.severity_disagreements)} severity disagreement(s)",
        file=sys.stderr,
    )
    if merge.contradiction_candidates:
        print(
            f"\n{len(merge.contradiction_candidates)} contradiction candidate(s) — "
            f"adjudicate each and rewrite the Contradictions section of {args.report}:",
            file=sys.stderr,
        )
        for finding, quote in merge.contradiction_candidates:
            print(f"  {finding.id} ({finding.location}): {quote}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

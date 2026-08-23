#!/usr/bin/env python3
"""Close a pattern round, with the round's yield read off the brief.

``patterns_found`` used to be a number the agent typed. On the one run it has
been measured against, it was wrong in the rounds that mattered: rounds 14 and
15 recorded ``5`` and ``2`` while ``patterns-brief.md`` states in its own words
that both added no new pattern. A number nobody derives is a number nobody can
gate on.

So the round's yield is derived here instead, from the artifact the round
exists to produce. A pattern round's durable output is a ``## PAT-NNN:`` entry
in ``docs/holtz/patterns-brief.md``; the yield is how many entries *this run*
has that no earlier round in this ledger already reported. Claiming a pattern
now means writing one.

The split mirrors ``verify_suite.py``: this script runs in the agent's shell,
which is sandboxed and cannot reach the daemon, so it derives and prints. The
``pattern_courier.py`` PostToolUse hook runs outside the sandbox and writes the
event — and it re-derives every field it records rather than reading them off
this script's output, so the marker below carries only ``siblings_found``,
which no gate consults.

Two consequences of reading the brief that are load-bearing:

* **The archive counts.** The rolling policy moves the five oldest entries to
  ``patterns-brief-archive.md`` once the brief passes twenty. An entry this run
  added can therefore leave the brief while still being this run's yield, so
  both files are scanned. Scanning only the live file would make a long run's
  early rounds silently un-count themselves.
* **Code fences are masked.** Pattern entries quote code, and a quoted
  ``## PAT-001:`` heading inside a fence is an example, not an entry — the
  defect the brief's own parser records as BH-005 of run 14.

Usage::

    python3 pattern_round.py --record --siblings-found N [--cwd .]
    python3 pattern_round.py --show [--cwd .]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ledger_query import query_ledger, sahjhan_target  # noqa: E402

BRIEF_PATH = os.path.join("docs", "holtz", "patterns-brief.md")
ARCHIVE_PATH = os.path.join("docs", "holtz", "patterns-brief-archive.md")

# The line `--record` prints and `pattern_courier.py` requires before it writes
# anything. Named here, imported there — the two ends of a channel that would
# fail silently if they ever disagreed about the word.
RECORD_MARKER = "PATTERN-ROUND:"

# Where a round happens: `phase-fix-loop.md`, Step 11. Every other protocol
# event carries these, and the courier writes an event the agent no longer can,
# so it stamps them on the round's behalf. Constants rather than a read of the
# doc: the courier resolves `$CLAUDE_PLUGIN_ROOT` in a tree the agent can write,
# and a writer of restricted events reads nothing from there. The
# correspondence to the document is pinned by
# `tests/test_pattern_round.py::test_the_stamp_names_the_step_that_teaches_the_round`.
ROUND_PHASE = "fix_loop"
ROUND_STEP = "11"

# `## PAT-007: name (Run 3, 2026-08-11)`. The run tag is what separates this
# run's entries from the ones a prior audit of the same project left behind —
# without it, the first round of every run would report the whole inherited
# brief as its own yield.
_ENTRY_RE = re.compile(
    r"^## (PAT-\d+):.*?\(Run (\d+), \d{4}-\d{2}-\d{2}\)\s*$", re.MULTILINE
)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_PAT_ID_RE = re.compile(r"^PAT-\d+$")
_COUNT_RE = re.compile(r"^\d+$")


# ── The brief ────────────────────────────────────────────────────────────────


def _mask_fences(content: str) -> str:
    """Blank every line inside a fenced code block, preserving line count."""
    out: list[str] = []
    fence: str | None = None
    for line in content.replace("\r\n", "\n").split("\n"):
        match = _FENCE_RE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)[0]
                out.append("")
                continue
            out.append(line)
            continue
        out.append("")
        if match and match.group(1)[0] == fence:
            # A tilde fence cannot close a backtick fence, per CommonMark.
            fence = None
    return "\n".join(out)


def brief_entries(cwd: str) -> dict[str, str]:
    """Every ``PAT-NNN`` in the brief and its archive, mapped to its run tag.

    Later files win on a duplicate id, which cannot happen in a well-formed
    pair — an entry is *moved* to the archive, not copied — and if it does, the
    two tags name the same round anyway.
    """
    found: dict[str, str] = {}
    for rel in (BRIEF_PATH, ARCHIVE_PATH):
        try:
            with open(os.path.join(cwd, rel), encoding="utf-8") as fh:
                content = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for pat_id, run in _ENTRY_RE.findall(_mask_fences(content)):
            found[pat_id] = run
    return found


# ── The ledger ───────────────────────────────────────────────────────────────


def _current_run(binary: str, config_dir: str, cwd: str) -> tuple[str | None, str]:
    """The run number the agent has been recording against.

    Read from the ledger rather than from the ``active-ledger`` marker,
    because that marker is frequently absent and defaults to ``0`` while the
    events carry the real number — and the brief's ``(Run N, …)`` tag is
    written by the same agent from the same number. Comparing the ledger's
    answer to the brief's compares like with like.
    """
    rows, problem = query_ledger(
        binary,
        config_dir,
        cwd,
        "SELECT run FROM events WHERE run IS NOT NULL ORDER BY seq DESC LIMIT 1",
    )
    if rows is None:
        return None, problem
    if not rows:
        return None, "no event in this ledger names a run"
    run = str(rows[0].get("run") or "")
    if not _COUNT_RE.match(run):
        return None, f"the ledger's most recent run is not a number ({run!r})"
    return run, ""


def _reported_ids(binary: str, config_dir: str, cwd: str) -> tuple[set[str], str]:
    """PAT ids that an earlier round in this ledger already counted."""
    rows, problem = query_ledger(
        binary,
        config_dir,
        cwd,
        "SELECT pattern_ids FROM events WHERE type='pattern_analysis_complete'",
    )
    if rows is None:
        return set(), problem
    reported: set[str] = set()
    for row in rows:
        for token in str(row.get("pattern_ids") or "").split(","):
            token = token.strip()
            if _PAT_ID_RE.match(token):
                reported.add(token)
    return reported, ""


# ── The yield ────────────────────────────────────────────────────────────────


class Yield(NamedTuple):
    """What a round produced, as the ledger will record it."""

    run: str
    new_ids: list[str]


def round_yield(cwd: str) -> tuple[Yield | None, str]:
    """PAT ids this run has added that no earlier round reported, or a problem.

    Sorted, so the recorded field and anything comparing two rounds see a
    stable order.
    """
    binary, config_dir, problem = sahjhan_target(cwd)
    if binary is None or config_dir is None:
        return None, f"cannot reach the ledger — {problem}"

    run, problem = _current_run(binary, config_dir, cwd)
    if run is None:
        return None, problem

    reported, problem = _reported_ids(binary, config_dir, cwd)
    if problem:
        return None, problem

    entries = brief_entries(cwd)
    mine = {
        pat_id for pat_id, tag in entries.items() if tag.lstrip("0") == run.lstrip("0")
    }
    if entries and not mine:
        # Every entry belongs to an earlier audit. True on a first round, and
        # also what a brief whose headings carry the wrong run tag looks like,
        # so say which it is rather than reporting a bare zero.
        print(
            f"pattern_round: no entry in the brief is tagged (Run {run}, …) — "
            f"{len(entries)} entries carry other runs",
            file=sys.stderr,
        )
    return Yield(run, sorted(mine - reported)), ""


# ── Command recognition ──────────────────────────────────────────────────────

# One recognizer, defined beside the command it recognizes. `pattern_courier.py`
# imports it rather than carrying a second regex: the courier records only for a
# command it can identify, so a drift between what the skill file teaches and
# what the courier accepts would be a silent deadlock.
_SCRIPT_TAIL = os.path.join("enforcement", "scripts", "pattern_round.py")
_INTERPRETERS = frozenset({"python", "python3", "py"})


def siblings_of(segment: str) -> str | None:
    """The ``--siblings-found`` value if ``segment`` is the record command.

    Read from the command text *as typed*, which is what the host reports to a
    PostToolUse hook — ``${CLAUDE_PLUGIN_ROOT}`` is still a literal there, so
    the script is identified by its tail rather than by resolving a path the
    hook cannot expand the way the shell did.

    ``--cwd`` is rejected rather than parsed: the courier derives the round
    against the *event's* cwd, so a run pointed elsewhere would attach another
    project's brief to this ledger. The flag is for tests and diagnostics.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return None
    if len(tokens) < 3:
        return None
    if os.path.basename(tokens[0]) not in _INTERPRETERS:
        return None
    if not tokens[1].endswith(_SCRIPT_TAIL):
        return None

    siblings: str | None = None
    seen_record = False
    rest = tokens[2:]
    while rest:
        flag = rest.pop(0)
        if flag == "--record":
            seen_record = True
        elif flag == "--siblings-found" and rest and _COUNT_RE.match(rest[0]):
            siblings = rest.pop(0)
        else:
            return None
    return siblings if seen_record else None


# ── Modes ────────────────────────────────────────────────────────────────────


def mode_record(cwd: str, siblings: str) -> int:
    """Print the round's derived yield and the line the courier records for."""
    result, problem = round_yield(cwd)
    if result is None:
        print(
            f"FAIL: cannot derive this round's yield — {problem}\n"
            "  Nothing was recorded, so the pattern round is still owed.",
            file=sys.stderr,
        )
        return 1

    print(
        f"pattern_round: {len(result.new_ids)} new pattern(s) in {BRIEF_PATH}"
        + (f": {', '.join(result.new_ids)}" if result.new_ids else ""),
        file=sys.stderr,
    )
    # Printed last so it survives output truncation. It carries only the one
    # field the courier cannot derive; everything a reader might gate on the
    # courier computes for itself.
    print(f"{RECORD_MARKER} {json.dumps({'siblings_found': siblings}, sort_keys=True)}")
    return 0


def mode_show(cwd: str) -> int:
    """Print the yield without recording anything (diagnostic)."""
    result, problem = round_yield(cwd)
    if result is None:
        print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print("\n".join(result.new_ids))
    return 0


# ── Entrypoint ───────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Close a pattern round with the yield derived from the brief"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record",
        action="store_true",
        help="emit the evidence the courier turns into pattern_analysis_complete",
    )
    group.add_argument(
        "--show",
        action="store_true",
        help="print the PAT ids this round added, one per line (diagnostic)",
    )
    parser.add_argument(
        "--siblings-found",
        help="how many sibling findings this round filed (required with --record)",
    )
    parser.add_argument("--cwd", default=".", help="target project directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cwd = os.path.abspath(args.cwd)

    if args.show:
        return mode_show(cwd)
    if args.siblings_found is None or not _COUNT_RE.match(args.siblings_found):
        parser.error("--record requires --siblings-found <non-negative integer>")
    return mode_record(cwd, args.siblings_found)


if __name__ == "__main__":
    sys.exit(main())

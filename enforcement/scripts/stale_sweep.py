#!/usr/bin/env python3
"""Close a stale sweep, with the swept population read off the ledger.

P0.2's swap (D8): past ~round 8 the owed round is satisfied by a stale sweep
instead of pattern analysis. Nothing recorded a sweep before this. Step 11b
emits ``fix_start`` and ``defer cant-reproduce`` only for the findings it
*retires*, so a sweep where everything still reproduces left no trace at all,
and that deferral is reachable outside a sweep anyway. An obligation cannot be
discharged by a fact the ledger does not hold.

What makes the claim cost something is coverage. D21 settled the population —
**every open finding, at every severity, at each sweep** — so a sweep is only a
sweep if it produced a verdict for all of them. This script derives that
population from the ledger and refuses unless the verdicts name exactly it:
nothing missing, nothing invented. Claiming a sweep now means triaging the
board.

The split mirrors ``pattern_round.py``: this runs in the agent's shell, which
is sandboxed and cannot reach the daemon, so it derives and prints. The
``stale_sweep_courier.py`` PostToolUse hook runs outside the sandbox, re-derives
the same population, and writes the restricted event — so the numbers a gate
reads never pass through the agent.

Two parts of the population that are easy to get wrong:

* **The sweep's own retirements are still its work.** A finding deferred
  `cant_reproduce` during this sweep is no longer open by the time ``--record``
  runs. Counting only what is open now would fail a sweep for the findings it
  successfully retired, which is exactly backwards.
* **Deferred is not swept.** A finding retired by an *earlier* sweep, or
  deferred LOW by the breaker's escape, is off the board and out of the
  population. Only `cant_reproduce` deferrals since the last sweep rejoin it.

**"Since the last sweep" is as precisely as the ledger can say "this sweep."**
A `cant_reproduce` deferral records the same `phase` and `step` whether Step
11b made it or a Step 10 fix did, and no event marks a sweep *beginning* — so
a retirement made between two sweeps is one this sweep is asked to state a
verdict for. That is the wider of the two readings and the safe one: the
narrower would have to guess which deferrals were the sweep's, and guessing
wrong drops a finding off the board with nobody accounting for it.

The window is deliberately **not** the one `defer_cant_reproduce`'s own
`fix_start` gate uses. That gate asks "has this actor started work on this
item", and `since = "last_transition"` is the right span for it — Step 11b even
teaches recording each `fix_start` after the previous deferral because of it.
Reusing it here made "this sweep" mean "since anybody's last transition",
which the sweep's own deferral transitions then moved out from under it.

Usage::

    python3 stale_sweep.py --record --present BH-001,BH-002 --retired BH-004
    python3 stale_sweep.py --show [--cwd .]
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ledger_query import query_ledger, sahjhan_target  # noqa: E402

# The line `--record` prints and `stale_sweep_courier.py` requires before it
# writes anything. Named here, imported there — the two ends of a channel that
# would fail silently if they ever disagreed about the word.
RECORD_MARKER = "STALE-SWEEP:"

# Where a sweep happens: `phase-fix-loop.md`, Step 11b. Constants for the same
# reason `pattern_round.py` carries ROUND_STEP — the courier writes an event the
# agent no longer can, and a writer of restricted events reads nothing out of a
# tree the agent can edit. Pinned against the document by
# `test_the_stamp_names_the_step_that_teaches_the_sweep`.
SWEEP_PHASE = "fix_loop"
SWEEP_STEP = "11"

# Where this sweep starts. A sweep's own first recorded event is whatever
# landed after the previous sweep closed, so the floor is that sweep's
# `stale_sweep_complete` — the only event that marks a sweep having happened,
# and the only one no other actor writes.
#
# It used to be `MAX(seq)` over *any* `state_transition`, which is a run-global
# watermark and not this sweep's anything. Two ways that lost the sweep's own
# work, both measured against the pinned binary:
#
# * **The sweep moves it itself.** `defer cant-reproduce` is a transition, and
#   the engine writes its `state_transition` *below* the `finding_deferred` it
#   emits. So the second retirement's own transition stepped the watermark past
#   the first retirement's row: a sweep retiring two findings lost one, with no
#   concurrency in it at all.
# * **A sibling moves it.** In a three-wide loop a `fix_commit` landing
#   mid-sweep stepped it past every retirement already recorded.
#
# Both end the same way — `check` reports "verdicts name findings this sweep
# does not cover", the courier writes nothing, and the round stays owed.
#
# A seq floor rather than a `LIMIT` over an ordered subquery: sahjhan applies an
# outer `WHERE` before a derived table's `LIMIT`, so that form answers "any
# event anywhere" and agrees with this one on exactly the consecutive cases.
SWEEP_WINDOW_FLOOR = (
    "COALESCE((SELECT MAX(s.seq) FROM events s "
    "WHERE s.type='stale_sweep_complete'), 0)"
)


def _population_sql(floor: str) -> str:
    """The population, in one place, over one named window.

    ``floor`` is a parameter so a test can put the run-global watermark back
    and require this to break — the window is the whole of the fix, so a
    permanent mutation of it is the only thing that says so.
    """
    return f"""
SELECT DISTINCT f.id FROM events f WHERE f.type='finding'
  AND (
    (f.id NOT IN (SELECT r.id FROM events r WHERE r.type='finding_resolved')
     AND f.id NOT IN (SELECT d.id FROM events d WHERE d.type='finding_deferred'))
    OR f.id IN (
      SELECT c.id FROM events c WHERE c.type='finding_deferred'
        AND c.reason='cant_reproduce'
        AND c.seq > {floor})
  )
"""


_POPULATION_SQL = _population_sql(SWEEP_WINDOW_FLOOR)


class Coverage(NamedTuple):
    """The population a sweep has to account for, as the ledger states it."""

    run: str
    population: list[str]


def _current_run(binary: str, config_dir: str, cwd: str) -> tuple[str | None, str]:
    """The run number the agent has been recording against.

    Same read as `pattern_round.py`: the `active-ledger` marker is frequently
    absent and defaults to 0 while the events carry the real number.
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
    if not run.isdigit():
        return None, f"the ledger's most recent run is not a number ({run!r})"
    return run, ""


def sweep_coverage(cwd: str) -> tuple[Coverage | None, str]:
    """Every finding this sweep must account for, sorted, or a problem."""
    binary, config_dir, problem = sahjhan_target(cwd)
    if binary is None or config_dir is None:
        return None, f"cannot reach the ledger — {problem}"

    run, problem = _current_run(binary, config_dir, cwd)
    if run is None:
        return None, problem

    rows, problem = query_ledger(binary, config_dir, cwd, _POPULATION_SQL)
    if rows is None:
        return None, problem
    return Coverage(run, sorted({str(row.get("id") or "") for row in rows if row.get("id")})), ""


def _ids(raw: str | None) -> list[str]:
    """A comma-separated id list, empty entries dropped."""
    return [token.strip() for token in (raw or "").split(",") if token.strip()]


def check(cwd: str, present: list[str], retired: list[str]) -> tuple[Coverage | None, str]:
    """The coverage, if the verdicts name exactly the population."""
    result, problem = sweep_coverage(cwd)
    if result is None:
        return None, problem

    claimed = set(present) | set(retired)
    expected = set(result.population)
    if overlap := set(present) & set(retired):
        return None, (
            f"{len(overlap)} finding(s) reported both present and retired: "
            f"{', '.join(sorted(overlap))}"
        )
    if missing := expected - claimed:
        return None, (
            f"{len(missing)} open finding(s) have no verdict: "
            f"{', '.join(sorted(missing))}"
        )
    if unknown := claimed - expected:
        return None, (
            f"{len(unknown)} verdict(s) name findings this sweep does not "
            f"cover: {', '.join(sorted(unknown))}"
        )
    return result, ""


# ── Command recognition ──────────────────────────────────────────────────────

# One recognizer, defined beside the command it recognizes, imported by the
# courier rather than restated there — a drift between what the skill file
# teaches and what the courier accepts would be a silent deadlock.
_SCRIPT_TAIL = os.path.join("enforcement", "scripts", "stale_sweep.py")
_INTERPRETERS = frozenset({"python", "python3", "py"})


def verdicts_of(segment: str) -> tuple[list[str], list[str]] | None:
    """The ``--present``/``--retired`` ids if ``segment`` is the record command.

    Read from the command text *as typed*, which is what the host reports to a
    PostToolUse hook — ``${CLAUDE_PLUGIN_ROOT}`` is still a literal there, so
    the script is identified by its tail rather than by resolving a path the
    hook cannot expand the way the shell did.

    ``--cwd`` is rejected rather than parsed: the courier derives against the
    *event's* cwd, so a sweep pointed elsewhere would attach another project's
    board to this ledger. The flag is for tests and diagnostics.
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

    present: list[str] | None = None
    retired: list[str] = []
    seen_record = False
    rest = tokens[2:]
    while rest:
        flag = rest.pop(0)
        if flag == "--record":
            seen_record = True
        elif flag == "--present" and rest:
            present = _ids(rest.pop(0))
        elif flag == "--retired" and rest:
            retired = _ids(rest.pop(0))
        else:
            return None
    if not seen_record or present is None:
        return None
    return present, retired


# ── Modes ────────────────────────────────────────────────────────────────────


def mode_record(cwd: str, present: list[str], retired: list[str]) -> int:
    """Check the verdicts against the board and print the courier's line."""
    result, problem = check(cwd, present, retired)
    if result is None:
        print(
            f"FAIL: this is not a sweep of the whole board — {problem}\n"
            "  Nothing was recorded, so the round is still owed.",
            file=sys.stderr,
        )
        return 1

    print(
        f"stale_sweep: {len(result.population)} finding(s) triaged, "
        f"{len(retired)} retired",
        file=sys.stderr,
    )
    # Printed last so it survives output truncation. It carries nothing a gate
    # reads — the courier re-derives the population for itself.
    print(f"{RECORD_MARKER} {json.dumps({'retired': str(len(retired))}, sort_keys=True)}")
    return 0


def mode_show(cwd: str) -> int:
    """Print the population without recording anything (diagnostic)."""
    result, problem = sweep_coverage(cwd)
    if result is None:
        print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print("\n".join(result.population))
    return 0


# ── Entrypoint ───────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Close a stale sweep with the population derived from the ledger"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record",
        action="store_true",
        help="emit the evidence the courier turns into stale_sweep_complete",
    )
    group.add_argument(
        "--show",
        action="store_true",
        help="print the ids this sweep must account for, one per line (diagnostic)",
    )
    parser.add_argument("--present", help="ids the sweep found still present")
    parser.add_argument("--retired", help="ids the sweep could not reproduce")
    parser.add_argument("--cwd", default=".", help="target project directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cwd = os.path.abspath(args.cwd)

    if args.show:
        return mode_show(cwd)
    if args.present is None and args.retired is None:
        parser.error("--record requires --present and/or --retired")
    return mode_record(cwd, _ids(args.present), _ids(args.retired))


if __name__ == "__main__":
    sys.exit(main())

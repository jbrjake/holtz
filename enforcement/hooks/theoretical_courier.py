#!/usr/bin/env python3
"""PostToolUse courier: a `theoretical` finding takes itself off the board.

P0.5's third route (D29). `theoretical` is a finding's own confession that no
path to it was found — reachability itself unestablished — and the audited run
gave several of them full fix cycles while 51 of its 75 open HIGHs were never
worked at all.

D29 chose a courier over teaching the openness predicates to skip
`theoretical`. The courier writes a real `finding_deferred`, so there stays
exactly one definition of closed: every counter, render and gate that already
reads deferral sees this one, and `DEFERRED.md` needs no second rule.

The command is only the *wake-up*. The population is re-derived from the
ledger through the `open_theoretical_findings` predicate, which is why a
finding filed by `merge_punchlists.py` — whose inner ``sahjhan event finding``
runs in a subprocess no hook ever sees — is swept exactly like one the agent
filed itself. Re-derivation also makes the courier idempotent: an id already
carrying a deferral has left the population, so a second filing cannot spend a
second row.

Nothing here is invented. Each deferral is stamped with the project, run,
auditor, phase and step of the filing it defers, all read off that filing.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    bash_exit_code,
    exit_ok,
    exit_warn,
    read_event,
    record_authed_event,
    resolve_config_dir,
)
from _protocol_cache import _split_shell_segments, named_query_sql  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

# The predicate, by name. Resolved out of `protocol.toml` at runtime rather
# than restated here — H7 exists because a hook carrying its own copy of a
# gate's SQL is how #77 shipped.
POPULATION_QUERY = "open_theoretical_findings"

# `defer_low`'s `low_priority` would be a lie: nothing about a theoretical
# finding says it is low priority, only that nobody has found a way to reach
# it. A reason of its own keeps `DEFERRED.md` readable and keeps this row out
# of `medium_deferral_budget`, which counts `medium_budget` alone.
DEFER_REASON = "theoretical"

_MERGE_SCRIPT = "merge_punchlists.py"


def files_a_finding(command: str) -> bool:
    """True if this Bash line could have put a finding on the ledger.

    Two paths, and the second is not optional: `merge_punchlists.py` files
    every Justine-only finding through a subprocess, so the outer command is
    the only signal a PostToolUse hook ever gets for those.

    Read-only commands carrying the same tokens are the #77 shape — a `query`
    naming ``type='finding'`` must not wake anything — so the sahjhan branch
    requires the ``event finding`` verb pair, not the word.
    """
    for segment in _split_shell_segments(command):
        tokens = segment.split()
        for index, token in enumerate(tokens[:-1]):
            if token == "event" and tokens[index + 1] == "finding":
                return True
        if any(_MERGE_SCRIPT in token for token in tokens):
            return True
    return False


def pending(cwd: str) -> tuple[list[dict], str]:
    """Every open finding whose latest filing grades it theoretical.

    Returns ``(rows, "")`` or ``([], problem)``. Each row carries the run
    context of the filing it came from, so the courier writes nothing it had
    to make up.
    """
    binary = ensure_sahjhan()
    config_dir, found = resolve_config_dir(cwd)
    if binary is None or not found:
        return [], (
            f"sahjhan binary={'missing' if binary is None else 'ok'}, "
            f"config={'not found' if not found else 'ok'}"
        )

    sql = named_query_sql(config_dir, POPULATION_QUERY)
    if sql is None:
        return [], f"protocol.toml has no [queries.{POPULATION_QUERY}]"

    import json  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "query", sql, "--format", "json"],
            capture_output=True, text=True, timeout=30, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"cannot query the ledger: {exc}"
    if result.returncode != 0:
        return [], f"ledger query failed (exit {result.returncode}): {result.stderr.strip()}"
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [], f"cannot read the ledger query result: {exc}"
    if not isinstance(rows, list):
        return [], f"ledger query returned {type(rows).__name__}, not a list"
    return [row for row in rows if isinstance(row, dict) and row.get("id")], ""


def _show_cwd(argv: list[str]) -> str:
    """The `--cwd` value for a `--show` run, defaulting to here."""
    if "--cwd" in argv:
        index = argv.index("--cwd")
        if index + 1 < len(argv):
            return argv[index + 1]
    return "."


def main() -> None:
    # `--show` prints the population without recording anything, the way
    # `stale_sweep.py --show` does. It is the first thing to run when a board
    # is carrying findings that should have come off it, and — because a hook
    # is reached as its own process, with its own directory first on the import
    # path — it is also the only honest way to exercise this from a test. Two
    # different `_common.py` modules ship in this tree, and an in-process
    # import binds whichever one some earlier test reached first.
    if "--show" in sys.argv:
        rows, problem = pending(os.path.abspath(_show_cwd(sys.argv)))
        if problem:
            print(f"FAIL: {problem}", file=sys.stderr)
            raise SystemExit(1)
        import json  # noqa: PLC0415

        print(json.dumps(rows, sort_keys=True))
        raise SystemExit(0)

    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    if not files_a_finding(event.get("tool_input", {}).get("command", "")):
        exit_ok()
    if bash_exit_code(event) != 0:
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    rows, problem = pending(cwd)
    if problem:
        # Warned rather than passed over: the findings stay open, and the
        # convergence gates will later refuse a board nobody knows is dirty.
        exit_warn(
            f"theoretical findings NOT auto-deferred: {problem}",
            "PostToolUse",
        )
    if not rows:
        exit_ok()

    refused = []
    for row in rows:
        fields = {
            "id": str(row["id"]),
            "reason": DEFER_REASON,
            "project": str(row.get("project") or ""),
            "run": str(row.get("run") or ""),
            "auditor": str(row.get("auditor") or ""),
            "phase": str(row.get("phase") or ""),
            "step": str(row.get("step") or ""),
        }
        try:
            record_authed_event("finding_deferred", fields, cwd)
        except (OSError, RuntimeError) as exc:
            refused.append(f"{row['id']} ({exc})")

    if refused:
        exit_warn(
            "theoretical findings NOT auto-deferred: the daemon refused "
            + ", ".join(refused),
            "PostToolUse",
        )
    exit_ok()


if __name__ == "__main__":
    main()

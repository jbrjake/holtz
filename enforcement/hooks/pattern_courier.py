#!/usr/bin/env python3
"""PostToolUse courier: record `pattern_analysis_complete` for a closed round.

`pattern_round.py --record` runs in the agent's shell — inside the sandbox,
where the daemon socket is unreachable — so it cannot write a restricted event.
This hook runs outside the sandbox and can.

The division is the same one `suite_courier.py` draws, for the same reason:
nothing a gate reads passes through the agent.

  patterns_found / pattern_ids  — re-derived here from `patterns-brief.md` and
                                  the ledger, never read from the run's report
  project / run                 — from the tree and the ledger
  phase / step                  — constants: a round is Step 11 of the fix
                                  loop, and the doc that teaches it is pinned
                                  against them in the suite
  siblings_found                — from the marker; how many siblings the round
                                  filed is a fact only the round knows, and no
                                  gate reads it

Two signals must agree before anything is written. The host says the command
succeeded, and the script says it got far enough to print its marker. The
marker alone is text on a stream the agent owns, and "PostToolUse fired" alone
would become a false record the day the harness starts firing on failure.

What the agent controls is what it should control: whether a round happened at
all, and what goes in the brief. Claiming a pattern now costs writing one.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from pattern_round import (  # noqa: E402
    RECORD_MARKER,
    ROUND_PHASE,
    ROUND_STEP,
    round_yield,
    siblings_of,
)
from verify_suite import repo_root  # noqa: E402

from _common import (  # noqa: E402
    bash_exit_code,
    bash_output,
    exit_ok,
    exit_warn,
    read_event,
    record_authed_event,
)
from _protocol_cache import _split_shell_segments  # noqa: E402


def _evidence(output: str) -> dict | None:
    """The `PATTERN-ROUND:` payload from the tool output, or None if absent.

    Scanned from the end: the marker is printed last so it survives output
    truncation.
    """
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if not stripped.startswith(RECORD_MARKER):
            continue
        try:
            payload = json.loads(stripped[len(RECORD_MARKER):])
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _siblings(command: str) -> str | None:
    """The sibling count this Bash line records, if it is exactly that command.

    A single segment, deliberately. Accepting `pattern_round.py --record && …`
    would let arbitrary work ride the one Bash line whose success this hook
    converts into a ledger entry.
    """
    segments = _split_shell_segments(command)
    if len(segments) != 1:
        return None
    return siblings_of(segments[0])


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    siblings = _siblings(command)
    if siblings is None:
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    if _evidence(bash_output(event)) is None:
        # The command the host says succeeded, without the line the script
        # prints once it has derived the round. Warned rather than passed over
        # in silence: nothing was recorded, so the round is still owed and the
        # next `iteration_boundary` will block with no obvious connection to
        # this moment.
        exit_warn(
            "pattern_analysis_complete NOT recorded: the round command reported "
            f"success but its '{RECORD_MARKER}' evidence line is missing from "
            "the output. Run the same command again.",
            "PostToolUse",
        )

    cwd = event.get("cwd", os.getcwd())
    root = repo_root(cwd)
    if root is None:
        exit_warn(
            "pattern_analysis_complete NOT recorded: this is not a git working "
            "tree, so the project this round belongs to cannot be named.",
            "PostToolUse",
        )

    result, problem = round_yield(cwd)
    if result is None:
        exit_warn(
            f"pattern_analysis_complete NOT recorded: {problem}",
            "PostToolUse",
        )

    # The exit helpers are re-exported through importlib, which costs mypy the
    # NoReturn annotation and with it the narrowing above. Same idiom as
    # suite_courier.py.
    assert siblings is not None
    assert root is not None
    assert result is not None

    fields = {
        "project": os.path.basename(root),
        "run": result.run,
        "auditor": "holtz",
        "phase": ROUND_PHASE,
        "step": ROUND_STEP,
        "patterns_found": str(len(result.new_ids)),
        "siblings_found": siblings,
    }
    # Omitted rather than sent empty when the round added nothing: the field's
    # pattern admits a list of ids, and a dry round is the common case.
    if result.new_ids:
        fields["pattern_ids"] = ",".join(result.new_ids)

    try:
        record_authed_event("pattern_analysis_complete", fields, cwd)
    except (OSError, RuntimeError) as exc:
        exit_warn(
            f"pattern_analysis_complete NOT recorded: the daemon refused ({exc}). "
            "The round is still owed and iteration_boundary will block.",
            "PostToolUse",
        )

    exit_ok()


if __name__ == "__main__":
    main()

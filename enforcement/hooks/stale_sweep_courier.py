#!/usr/bin/env python3
"""PostToolUse courier: record `stale_sweep_complete` for a closed sweep.

`stale_sweep.py --record` runs in the agent's shell — inside the sandbox, where
the daemon socket is unreachable — so it cannot write a restricted event. This
hook runs outside the sandbox and can.

Same division `pattern_courier.py` and `suite_courier.py` draw, for the same
reason: nothing a gate reads passes through the agent.

  triaged / retired  — re-derived here from the ledger and the command as
                       typed, never read from the script's report
  project / run      — from the tree and the ledger
  phase / step       — constants: a sweep is Step 11b of the fix loop, and the
                       doc that teaches it is pinned against them in the suite

Two signals must agree before anything is written. The host says the command
succeeded, and the script says it got far enough to print its marker. The
marker alone is text on a stream the agent owns, and "PostToolUse fired" alone
would become a false record the day the harness starts firing on failure.

The coverage check runs again here rather than being trusted from the script's
exit code. The script is in a tree the agent can edit; the ledger is not.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from stale_sweep import (  # noqa: E402
    RECORD_MARKER,
    SWEEP_PHASE,
    SWEEP_STEP,
    check,
    verdicts_of,
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
    """The `STALE-SWEEP:` payload from the tool output, or None if absent.

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


def _verdicts(command: str) -> tuple[list[str], list[str]] | None:
    """The verdicts this Bash line records, if it is exactly that command.

    A single segment, deliberately. Accepting `stale_sweep.py --record && …`
    would let arbitrary work ride the one Bash line whose success this hook
    converts into a ledger entry.
    """
    segments = _split_shell_segments(command)
    if len(segments) != 1:
        return None
    return verdicts_of(segments[0])


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    verdicts = _verdicts(command)
    if verdicts is None:
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    if _evidence(bash_output(event)) is None:
        # The command the host says succeeded, without the line the script
        # prints once it has checked the board. Warned rather than passed over
        # in silence: nothing was recorded, so the round is still owed and the
        # next `iteration_boundary` will block with no obvious connection to
        # this moment.
        exit_warn(
            "stale_sweep_complete NOT recorded: the sweep command reported "
            f"success but its '{RECORD_MARKER}' evidence line is missing from "
            "the output. Run the same command again.",
            "PostToolUse",
        )

    cwd = event.get("cwd", os.getcwd())
    root = repo_root(cwd)
    if root is None:
        exit_warn(
            "stale_sweep_complete NOT recorded: this is not a git working "
            "tree, so the project this sweep belongs to cannot be named.",
            "PostToolUse",
        )

    # `exit_ok` is re-exported through importlib, which costs mypy the NoReturn
    # annotation and with it the narrowing from the guard above.
    assert verdicts is not None
    present, retired = verdicts
    result, problem = check(cwd, present, retired)
    if result is None:
        exit_warn(
            f"stale_sweep_complete NOT recorded: {problem}",
            "PostToolUse",
        )

    # The exit helpers are re-exported through importlib, which costs mypy the
    # NoReturn annotation and with it the narrowing above. Same idiom as
    # pattern_courier.py.
    assert root is not None
    assert result is not None

    fields = {
        "project": os.path.basename(root),
        "run": result.run,
        "auditor": "holtz",
        "phase": SWEEP_PHASE,
        "step": SWEEP_STEP,
        "triaged": str(len(result.population)),
        "retired": str(len(retired)),
    }

    try:
        record_authed_event("stale_sweep_complete", fields, cwd)
    except (OSError, RuntimeError) as exc:
        exit_warn(
            f"stale_sweep_complete NOT recorded: the daemon refused ({exc}). "
            "The round is still owed and iteration_boundary will block.",
            "PostToolUse",
        )

    exit_ok()


if __name__ == "__main__":
    main()

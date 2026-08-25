#!/usr/bin/env python3
"""PostToolUse courier: name the actor behind a `test_failed_before_fix`.

The fix-loop TDD gate asks the ledger whether a failing test was recorded since
the last transition. `test_failed_before_fix` names no actor, so that question
can only ever be "did *anyone*" — and with two fix agents working, each one's
source edit is authorised by the other's failing test. That is why
`phase-fix-loop.md` had to mandate one-at-a-time, and it is P0.3's whole
subject.

The actor cannot be an agent-stated field. Claude Code puts `agent_id` on the
hook event, not into the model's context, so an agent has no honest way to
state it and a dishonest one would be indistinguishable from an honest one.
This hook reads it off the hook payload, where the host set it, and writes a
`restricted` event the agent's shell cannot forge — the same division
`pattern_courier.py` and `stale_sweep_courier.py` draw.

  finding_id / test_name  — re-read from the ledger row the command just wrote,
  run / auditor / project   never parsed out of the command text. The row
                            already carries all five, so the courier needs
                            nothing from the working tree and works wherever
                            the ledger does.
  agent_id                — from the hook payload; "" is the orchestrator, a
                            real actor and never a wildcard

Two signals must agree before anything is written. The host says the command
succeeded, and the ledger actually holds a `test_failed_before_fix` newer than
the last evidence row. Exit status alone would mint a second evidence row for
old work every time a Bash line was replayed.

What this does *not* do is verify that a test failed. That was agent-attested
before and stays agent-attested; only the actor is host-attested. The gate this
feeds is about which agent may edit next, not about whether the test was real.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from _ledger_query import query_ledger, sahjhan_target  # noqa: E402

from _common import (  # noqa: E402
    bash_exit_code,
    exit_ok,
    exit_warn,
    read_event,
    record_authed_event,
)
from _protocol_cache import _split_shell_segments, event_actor  # noqa: E402
from _sahjhan_bootstrap import _extract_sahjhan_subcmd  # noqa: E402

# The newest failing-test row this courier has not already paired with an
# evidence row. `seq > COALESCE(MAX(seq of tdd_evidence), 0)` is spelled inline
# rather than as a named query because a hook is not a gate — nothing else
# decides this fact, so there is no second site to keep in agreement.
_UNPAIRED = (
    "SELECT finding_id, test_name, run, auditor, project FROM events "
    "WHERE type='test_failed_before_fix' "
    "AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='tdd_evidence'), 0) "
    "ORDER BY seq DESC LIMIT 1"
)


def _records_a_failing_test(command: str) -> bool:
    """Whether this Bash line is exactly the failing-test recording command.

    A single segment, deliberately. Accepting `sahjhan event
    test_failed_before_fix && …` would let arbitrary work ride the one Bash
    line whose success this hook converts into a ledger entry.
    """
    segments = _split_shell_segments(command)
    if len(segments) != 1:
        return False
    parsed = _extract_sahjhan_subcmd(segments[0])
    return parsed == ("event", "test_failed_before_fix")


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    if not _records_a_failing_test(command):
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    binary, config_dir, problem = sahjhan_target(cwd)
    if binary is None or config_dir is None:
        exit_warn(
            f"tdd_evidence NOT recorded: {problem}. The TDD gate will still "
            "block your next source edit.",
            "PostToolUse",
        )

    rows, problem = query_ledger(binary, config_dir, cwd, _UNPAIRED)
    if rows is None:
        exit_warn(
            f"tdd_evidence NOT recorded: {problem}. The TDD gate will still "
            "block your next source edit.",
            "PostToolUse",
        )
    if not rows:
        # The host says the command succeeded and the ledger gained nothing —
        # a replayed line, or an event the engine refused. Either way there is
        # no new work to attribute, and silently minting an evidence row would
        # hand the next edit a gate pass it did not earn.
        exit_warn(
            "tdd_evidence NOT recorded: the command reported success but the "
            "ledger holds no new test_failed_before_fix. Record the failing "
            "test again before editing source.",
            "PostToolUse",
        )

    # The exit helpers are re-exported through importlib, which costs mypy the
    # NoReturn annotation and with it the narrowing above. Same idiom as
    # pattern_courier.py.
    assert rows is not None

    row = rows[0]
    fields = {
        "finding_id": str(row.get("finding_id") or ""),
        "test_name": str(row.get("test_name") or ""),
        "agent_id": event_actor(event),
        "project": str(row.get("project") or ""),
        "run": str(row.get("run") or ""),
        "auditor": str(row.get("auditor") or ""),
    }

    try:
        record_authed_event("tdd_evidence", fields, cwd)
    except (OSError, RuntimeError) as exc:
        exit_warn(
            f"tdd_evidence NOT recorded: the daemon refused ({exc}). The TDD "
            "gate will still block your next source edit.",
            "PostToolUse",
        )

    exit_ok()


if __name__ == "__main__":
    main()

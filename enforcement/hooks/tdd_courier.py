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
import re
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

# The failing-test row *this Bash line* wrote, unpaired.
#
# Both halves are keyed on the finding id the command names. Keyed on neither,
# the courier read the newest `test_failed_before_fix` on the whole ledger past
# a run-global watermark and stamped the caller's `agent_id` on it — so with
# both records landing before either courier ran, which is what a three-wide
# dispatch produces, each actor's evidence named the other's finding:
#
#   agent-A records BH-001 / test_A       seq 100
#   agent-B records BH-002 / test_B       seq 101
#   courier(agent-A) -> tdd_evidence { agent_id: A, finding_id: BH-002 }
#   courier(agent-B) -> "the ledger holds no new test_failed_before_fix"
#
# Three consequences, and the first is a gate bypass: A could then edit source
# having recorded nothing of its own, B was starved with a warning that did not
# say why, and `LIMIT 1` lost the older row for good.
#
# The watermark is per-finding for the same reason: a run-global MAX(seq) means
# any actor's evidence row retires every other actor's unpaired record.
_UNPAIRED_TEMPLATE = (
    "SELECT finding_id, test_name, run, auditor, project FROM events "
    "WHERE type='test_failed_before_fix' AND finding_id='{finding_id}' "
    "AND seq > COALESCE((SELECT MAX(seq) FROM events "
    "WHERE type='tdd_evidence' AND finding_id='{finding_id}'), 0) "
    "ORDER BY seq DESC LIMIT 1"
)

#: `events.toml` gives `finding_id` this exact pattern. Matching it here is
#: what makes interpolating the id into the SQL safe: `query_ledger` takes a
#: statement, not bound parameters, so the id has to be a closed character set
#: rather than anything the command line happened to carry.
_FINDING_ID_RE = re.compile(r"--field\s+finding_id=(B[HJ]-\d{3})(?!\S)")


def _finding_id_of(command: str) -> str | None:
    """The finding id this recording command names, or None if it names none.

    Reading the command text is safe *here* and nowhere else in this hook. The
    courier already refuses anything but a single canonical segment, so an id
    cannot ride in on a chained command; the id is pattern-checked against the
    one `events.toml` declares; and every field the courier goes on to write is
    still re-read from the ledger row this selects, never from the text. An id
    that names no unpaired row simply selects nothing, which is the same
    "recorded nothing" path a replayed line takes.
    """
    match = _FINDING_ID_RE.search(command)
    return match.group(1) if match else None


def unpaired_sql(finding_id: str) -> str:
    """The `_UNPAIRED_TEMPLATE` bound to one finding id."""
    if not _FINDING_ID_RE.fullmatch(f"--field finding_id={finding_id}"):
        raise ValueError(f"not a finding id: {finding_id!r}")
    return _UNPAIRED_TEMPLATE.format(finding_id=finding_id)


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


def _chains_the_record(command: str) -> bool:
    """Is the recording command in here, riding on a longer shell line?

    The refusal above is right and stays. What was wrong was its silence: a
    subagent writing `pytest …; sahjhan event test_failed_before_fix …` records
    nothing, and the next thing it sees is the TDD gate refusing its source
    edit — which is item 19's mis-attribution one step further on, except there
    is no evidence row to mis-attribute. `phase-fix-loop.md` teaches this step
    without the "run it alone" warning its three siblings carry, so the shape
    is one the document invites.
    """
    segments = _split_shell_segments(command)
    return len(segments) > 1 and any(
        _extract_sahjhan_subcmd(segment) == ("event", "test_failed_before_fix")
        for segment in segments
    )


def main() -> None:
    event = read_event()
    if event.get("tool_name") != "Bash":
        exit_ok()

    command = event.get("tool_input", {}).get("command", "")
    if not _records_a_failing_test(command):
        if bash_exit_code(event) == 0 and _chains_the_record(command):
            exit_warn(
                "tdd_evidence NOT recorded: the recording command was chained "
                "with other work, and this courier records only for a line "
                "that is nothing else. The event itself landed; the evidence "
                "row that pairs it to you did not, so the TDD gate will refuse "
                "your source edit. Run the `sahjhan ... event "
                "test_failed_before_fix ...` line again, alone on its own Bash "
                "line.",
                "PostToolUse",
            )
        exit_ok()

    if bash_exit_code(event) != 0:
        exit_ok()

    finding_id = _finding_id_of(command)
    if finding_id is None:
        # The engine requires `finding_id` on `test_failed_before_fix`, so a
        # command without a well-formed one exited 4 and wrote nothing — but
        # the host may still report success for a line that only *looks* like
        # the recording command. Warned rather than passed over, because the
        # gate is about to block for a reason this message explains and the
        # block itself will not.
        exit_warn(
            "tdd_evidence NOT recorded: the command names no finding_id, so "
            "there is no row to attribute. Re-record with "
            "`--field finding_id=BH-NNN` before editing source.",
            "PostToolUse",
        )

    # The exit helpers are re-exported through importlib, which costs mypy the
    # NoReturn annotation and with it the narrowing above.
    assert finding_id is not None

    cwd = event.get("cwd", os.getcwd())
    binary, config_dir, problem = sahjhan_target(cwd)
    if binary is None or config_dir is None:
        exit_warn(
            f"tdd_evidence NOT recorded: {problem}. The TDD gate will still "
            "block your next source edit.",
            "PostToolUse",
        )

    rows, problem = query_ledger(binary, config_dir, cwd, unpaired_sql(finding_id))
    if rows is None:
        exit_warn(
            f"tdd_evidence NOT recorded: {problem}. The TDD gate will still "
            "block your next source edit.",
            "PostToolUse",
        )
    if not rows:
        # The host says the command succeeded and the ledger gained nothing for
        # *this finding* — a replayed line, or an event the engine refused.
        # Either way there is no new work to attribute, and silently minting an
        # evidence row would hand the next edit a gate pass it did not earn.
        exit_warn(
            f"tdd_evidence NOT recorded: the command reported success but the "
            f"ledger holds no new test_failed_before_fix for {finding_id}. "
            f"Record the failing test again before editing source.",
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
